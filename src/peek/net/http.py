#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP 客户端模块

提供线程安全的同步 HTTP 客户端，复用项目自身的 ExponentialBackOff 重试机制。

特性：
- 线程安全的 Session 管理（每线程独立 Session）
- 基于 ExponentialBackOff 的指数退避重试
- 可配置超时和重试参数
- 可选的请求/响应 body 日志（支持截断）
- Google style docstring

使用示例：
    # 基础使用（使用默认配置）
    response = get("https://api.example.com/data")
    response = post("https://api.example.com/data", json={"key": "value"})

    # 自定义客户端（开启请求/响应日志）
    client = HttpClient(timeout=10, max_retries=5, log_request_body=True, log_response_body=True)
    response = client.get("https://api.example.com/data")
    client.close()
"""

import json
import logging
import threading
import time
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
# 默认 body 日志截断长度（1024 字节）
DEFAULT_MAX_BODY_LOG_BYTES = 1024


class HttpClient:
    """线程安全的 HTTP 客户端

    每个线程维护独立的 requests.Session，避免多线程竞争。
    内置基于 ExponentialBackOff 的重试机制。
    支持可选的 outgoing 请求/响应 body 日志记录。

    Args:
        timeout: 请求超时时间（秒），默认 30
        max_retries: 最大重试次数，默认 3
        initial_interval: 初始重试间隔（秒），默认 0.1
        max_interval: 最大重试间隔（秒），默认 5.0
        headers: 默认请求头
        log_request_body: 是否记录请求 body，默认 False
        log_response_body: 是否记录响应 body，默认 False
        max_body_log_bytes: body 日志最大截断长度（字节），默认 1024

    使用示例：
        client = HttpClient(timeout=10, max_retries=5, log_request_body=True, log_response_body=True)
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
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_log_bytes: int = DEFAULT_MAX_BODY_LOG_BYTES,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_interval = initial_interval
        self.max_interval = max_interval
        self.default_headers = headers or {}
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_log_bytes = max_body_log_bytes
        self._local = threading.local()
        self._sessions_lock = threading.Lock()
        self._sessions: list = []  # 跟踪所有线程创建的 session

    # ============================================================
    # 日志辅助方法
    # ============================================================

    def _truncate(self, content: str) -> str:
        """截断字符串，超过限制时保留前 N 字节并附加总长度信息。

        Args:
            content: 原始字符串

        Returns:
            截断后的字符串，格式: "前N字节...(total_len:X)"
        """
        if len(content) <= self.max_body_log_bytes:
            return content
        return f"{content[:self.max_body_log_bytes]}...(total_len:{len(content)})"

    def _format_request_body(self, kwargs: dict) -> str:
        """从请求参数中提取并格式化 request body 用于日志。

        Args:
            kwargs: 传递给 requests 的参数字典

        Returns:
            格式化后的 body 字符串
        """
        if "json" in kwargs and kwargs["json"] is not None:
            try:
                body_str = json.dumps(kwargs["json"], ensure_ascii=False)
            except (TypeError, ValueError):
                body_str = str(kwargs["json"])
            return self._truncate(body_str)
        elif "data" in kwargs and kwargs["data"] is not None:
            data = kwargs["data"]
            if isinstance(data, bytes):
                return f"<bytes>(total_len:{len(data)})"
            body_str = str(data)
            return self._truncate(body_str)
        return ""

    def _format_response_body(self, response: "requests.Response") -> str:
        """格式化响应 body 用于日志。

        Args:
            response: requests.Response 对象

        Returns:
            格式化后的 body 字符串
        """
        try:
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                body_str = response.text
            elif "text/" in content_type:
                body_str = response.text
            else:
                # 二进制内容只记录大小
                return f"<binary>(total_len:{len(response.content)})"
            return self._truncate(body_str)
        except Exception:
            return "<error reading response body>"

    # ============================================================
    # 核心请求方法
    # ============================================================

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
        """带重试的 HTTP 请求，支持请求/响应 body 日志。

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

        # 记录请求日志
        if self.log_request_body:
            req_body = self._format_request_body(kwargs)
            if req_body:
                logger.info(
                    "--> %s %s | body: %s", method, url, req_body,
                )
            else:
                logger.info("--> %s %s", method, url)

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

        start_time = time.perf_counter()

        def do_request() -> requests.Response:
            response = session.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        response = backoff.retry_sync(do_request)

        # 记录响应日志
        if self.log_response_body:
            cost_ms = round((time.perf_counter() - start_time) * 1000, 2)
            resp_body = self._format_response_body(response)
            if resp_body:
                logger.info(
                    "<-- %s %s %s | cost: %sms | body: %s",
                    method, url, response.status_code, cost_ms, resp_body,
                )
            else:
                logger.info(
                    "<-- %s %s %s | cost: %sms",
                    method, url, response.status_code, cost_ms,
                )

        return response

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