#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP 请求耗时中间件

参考 Go 版本 golang 库的 ServerInterceptorOfTimer 实现，提供：
- 记录每个 HTTP 请求的处理耗时
- 以日志形式打印 method + path 和总耗时
- 支持跳过指定路径（如健康检查）
"""

import logging
import time
from typing import Awaitable, Callable, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from peek.context import get_request_id as _ctx_get_request_id
from peek.context import get_trace_id as _ctx_get_trace_id

logger = logging.getLogger(__name__)


class HttpTimerMiddleware(BaseHTTPMiddleware):
    """
    HTTP 请求耗时中间件

    类似 Go 版本的 ServerInterceptorOfTimer，在请求处理完毕后
    以日志打印 method + path 和总耗时

    示例日志输出:
        http cost POST /wx_video_scene_audit: 1234.56ms
    """

    def __init__(
        self,
        app: ASGIApp,
        log: Optional[logging.Logger] = None,
        header_name: str = "X-Response-Time",
        skip_paths: Optional[List[str]] = None,
    ):
        """
        初始化 HTTP 请求耗时中间件

        Args:
            app: ASGI 应用
            log: 日志记录器，默认使用模块级 logger
            header_name: 响应头中耗时字段名
            skip_paths: 跳过记录的路径列表（如 /health, /metrics）
        """
        super().__init__(app)
        self.log = log or logger
        self.header_name = header_name
        self.skip_paths = skip_paths or [
            "/healthz", "/readyz",
            "/livez", "/metrics",
        ]

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 跳过指定路径
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # 记录开始时间
        start_time = time.perf_counter()

        # 执行请求
        response = await call_next(request)

        # 计算耗时
        duration = time.perf_counter() - start_time
        duration_ms = round(duration * 1000, 2)

        # 存储到 request.state
        request.state.duration_ms = duration_ms

        # 添加耗时到响应头
        response.headers[self.header_name] = f"{duration_ms}ms"

        # 获取 request_id（如果存在），用于日志关联
        # 优先从 request.state 获取，备选从 contextvars 获取
        request_id = getattr(request.state, "request_id", "") or _ctx_get_request_id() or "-"

        # 获取 trace_id（如果存在），用于日志关联
        trace_id = _ctx_get_trace_id()

        # 格式化日志前缀，与 gRPC 拦截器保持一致
        if trace_id:
            prefix = f"[{request_id}] [trace_id={trace_id}]"
        else:
            prefix = f"[{request_id}]"

        # 打印耗时日志，格式类似 Go 版本:
        # [request_id] [trace_id=xxx] http cost POST /wx_video_scene_audit: 1234.56ms
        callee_method = f"{request.method} {request.url.path}"
        self.log.info("%s http cost %s: %sms", prefix, callee_method, duration_ms)

        return response
