#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
超时中间件

提供请求超时控制：
- 请求处理超时
- 优雅超时处理
- 可配置的超时响应
"""

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    超时中间件

    为请求处理设置超时限制，超时后返回 504 Gateway Timeout
    """

    def __init__(
        self,
        app: ASGIApp,
        timeout: float,
        timeout_response: Optional[Response] = None,
    ):
        """
        初始化超时中间件

        Args:
            app: ASGI 应用
            timeout: 超时时间（秒）
            timeout_response: 自定义超时响应
        """
        super().__init__(app)
        self.timeout = timeout
        self.timeout_response = timeout_response

    def _default_timeout_response(self, request: Request) -> Response:
        """生成默认超时响应"""
        return JSONResponse(
            status_code=504,
            content={
                "error": "Gateway Timeout",
                "message": f"Request timeout after {self.timeout}s",
                "path": request.url.path,
            },
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if self.timeout <= 0:
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Request timeout after {self.timeout}s: {request.method} {request.url.path}"
            )
            if self.timeout_response:
                return self.timeout_response
            return self._default_timeout_response(request)


class PathTimeoutMiddleware(BaseHTTPMiddleware):
    """
    路径级超时中间件

    支持为不同路径设置不同的超时时间
    """

    def __init__(
        self,
        app: ASGIApp,
        default_timeout: float = 0,
        path_timeouts: Optional[dict] = None,
    ):
        """
        初始化路径级超时中间件

        Args:
            app: ASGI 应用
            default_timeout: 默认超时时间（秒），0 表示不限制
            path_timeouts: 路径超时配置 {path: timeout}，支持前缀匹配（以 * 结尾）
        """
        super().__init__(app)
        self.default_timeout = default_timeout
        self.path_timeouts = path_timeouts or {}

    def _get_timeout(self, path: str) -> float:
        """获取路径对应的超时时间"""
        # 精确匹配
        if path in self.path_timeouts:
            return self.path_timeouts[path]

        # 前缀匹配
        for pattern, timeout in self.path_timeouts.items():
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if path.startswith(prefix):
                    return timeout

        return self.default_timeout

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        timeout = self._get_timeout(request.url.path)

        if timeout <= 0:
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Request timeout after {timeout}s: {request.method} {request.url.path}"
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Gateway Timeout",
                    "message": f"Request timeout after {timeout}s",
                    "path": request.url.path,
                },
            )


def timeout(timeout_seconds: float):
    """
    创建超时中间件的工厂函数

    Args:
        timeout_seconds: 超时时间（秒）

    Returns:
        返回一个可用于 app.add_middleware 的中间件配置

    示例:
        ```python
        app.add_middleware(TimeoutMiddleware, timeout=30.0)
        ```
    """

    def middleware_factory(app: ASGIApp) -> TimeoutMiddleware:
        return TimeoutMiddleware(app, timeout=timeout_seconds)

    return middleware_factory
