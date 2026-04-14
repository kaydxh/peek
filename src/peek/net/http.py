#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP 客户端模块

提供线程安全的同步 HTTP 客户端，复用项目自身的 ExponentialBackOff 重试机制。

特性：
- 线程安全的 Session 管理（每线程独立 Session）
- 基于 ExponentialBackOff 的指数退避重试
- 可配置超时和重试参数
- Google style docstring

使用示例：
    # 基础使用（使用默认配置）
    response = get("https://api.example.com/data")
    response = post("https://api.example.com/data", json={"key": "value"})

    # 自定义客户端
    client = HttpClient(timeout=10, max_retries=5)
    response = client.get("https://api.example.com/data")
    client.close()
"""

import logging
import threading
from typing import Any, Optional

try:
    import requests
except ImportError:
    raise ImportError(
        "The 'requests' package is required for peek.net.http. "
        "Install it with: pip install peek[http]"
    ) from None

from peek.time.backoff import ExponentialBackOff

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_TIMEOUT = 30  # 秒
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_INTERVAL = 0.1  # 100ms
DEFAULT_MAX_INTERVAL = 5.0  # 5s


class HttpClient:
    """线程安全的 HTTP 客户端

    每个线程维护独立的 requests.Session，避免多线程竞争。
    内置基于 ExponentialBackOff 的重试机制。

    Args:
        timeout: 请求超时时间（秒），默认 30
        max_retries: 最大重试次数，默认 3
        initial_interval: 初始重试间隔（秒），默认 0.1
        max_interval: 最大重试间隔（秒），默认 5.0
        headers: 默认请求头

    使用示例：
        client = HttpClient(timeout=10, max_retries=5)
        response = client.get("https://api.example.com/data")
        client.close()
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_interval: float = DEFAULT_INITIAL_INTERVAL,
        max_interval: float = DEFAULT_MAX_INTERVAL,
        headers: Optional[dict] = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_interval = initial_interval
        self.max_interval = max_interval
        self.default_headers = headers or {}
        self._local = threading.local()
        self._sessions_lock = threading.Lock()
        self._sessions: list = []  # 跟踪所有线程创建的 session

    def _get_session(self) -> requests.Session:
        """获取当前线程的 Session 实例

        Returns:
            当前线程的 requests.Session
        """
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update(self.default_headers)
            self._local.session = session
            with self._sessions_lock:
                self._sessions.append(session)
        return self._local.session

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        """带重试的 HTTP 请求

        Args:
            method: HTTP 方法（GET, POST 等）
            url: 请求 URL
            **kwargs: 传递给 requests 的参数

        Returns:
            requests.Response 响应对象

        Raises:
            requests.HTTPError: HTTP 错误（重试耗尽后）
            requests.ConnectionError: 连接错误（重试耗尽后）
            requests.Timeout: 超时错误（重试耗尽后）
        """
        kwargs.setdefault("timeout", self.timeout)
        session = self._get_session()

        backoff = ExponentialBackOff(
            initial_interval=self.initial_interval,
            max_interval=self.max_interval,
            max_elapsed_count=self.max_retries,
            retry_exceptions=(
                requests.ConnectionError,
                requests.Timeout,
                requests.HTTPError,
            ),
        )

        def do_request() -> requests.Response:
            response = session.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        return backoff.retry_sync(do_request)

    def get(
        self, url: str, params: Any = None, headers: Any = None, **kwargs: Any
    ) -> requests.Response:
        """发送 GET 请求

        Args:
            url: 请求 URL
            params: 查询参数
            headers: 请求头
            **kwargs: 传递给 requests 的额外参数

        Returns:
            requests.Response 响应对象
        """
        return self._request_with_retry(
            "GET", url, params=params, headers=headers, **kwargs
        )

    def post(
        self,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: Any = None,
        **kwargs: Any,
    ) -> requests.Response:
        """发送 POST 请求

        Args:
            url: 请求 URL
            data: 表单数据
            json: JSON 数据
            headers: 请求头
            **kwargs: 传递给 requests 的额外参数

        Returns:
            requests.Response 响应对象
        """
        return self._request_with_retry(
            "POST", url, data=data, json=json, headers=headers, **kwargs
        )

    def post_json(self, url: str, data: Any = None, **kwargs: Any) -> requests.Response:
        """发送 JSON POST 请求

        Args:
            url: 请求 URL
            data: JSON 数据
            **kwargs: 传递给 requests 的额外参数

        Returns:
            requests.Response 响应对象
        """
        return self.post(url, json=data, **kwargs)

    def put(
        self, url: str, data: Any = None, json: Any = None, **kwargs: Any
    ) -> requests.Response:
        """发送 PUT 请求

        Args:
            url: 请求 URL
            data: 表单数据
            json: JSON 数据
            **kwargs: 传递给 requests 的额外参数

        Returns:
            requests.Response 响应对象
        """
        return self._request_with_retry("PUT", url, data=data, json=json, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> requests.Response:
        """发送 DELETE 请求

        Args:
            url: 请求 URL
            **kwargs: 传递给 requests 的额外参数

        Returns:
            requests.Response 响应对象
        """
        return self._request_with_retry("DELETE", url, **kwargs)

    def close(self) -> None:
        """关闭当前线程的 Session"""
        if hasattr(self._local, "session"):
            self._local.session.close()
            del self._local.session

    def close_all(self) -> None:
        """关闭所有线程的 Session

        在应用关闭时调用，确保所有线程创建的 TCP 连接都被释放。
        """
        with self._sessions_lock:
            for session in self._sessions:
                try:
                    session.close()
                except Exception:
                    pass
            self._sessions.clear()


# ======================== 模块级便捷函数（向后兼容） ========================

# 默认全局客户端实例
_default_client = HttpClient()


def get(
    url: str, params: Any = None, headers: Any = None, **kwargs: Any
) -> requests.Response:
    """发送 GET 请求（模块级便捷函数）

    Args:
        url: 请求 URL
        params: 查询参数
        headers: 请求头
        **kwargs: 传递给 requests 的额外参数

    Returns:
        requests.Response 响应对象
    """
    return _default_client.get(url, params=params, headers=headers, **kwargs)


def post(
    url: str, data: Any = None, json: Any = None, **kwargs: Any
) -> requests.Response:
    """发送 POST 请求（模块级便捷函数）

    Args:
        url: 请求 URL
        data: 表单数据
        json: JSON 数据
        **kwargs: 传递给 requests 的额外参数

    Returns:
        requests.Response 响应对象
    """
    return _default_client.post(url, data=data, json=json, **kwargs)


def post_json(url: str, data: Any = None, **kwargs: Any) -> requests.Response:
    """发送 JSON POST 请求（模块级便捷函数）

    Args:
        url: 请求 URL
        data: JSON 数据
        **kwargs: 传递给 requests 的额外参数

    Returns:
        requests.Response 响应对象
    """
    return _default_client.post_json(url, data=data, **kwargs)
