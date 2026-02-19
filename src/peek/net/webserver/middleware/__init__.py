#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP 中间件模块

提供 HTTP 中间件链支持：
- 基础中间件：RequestID、Timer、Recovery、Logger
- 限流中间件：QPS 限流、并发限流
- 超时中间件：请求超时控制
- OpenTelemetry 中间件：追踪、指标
"""

import asyncio
import time
import traceback
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# 导出限流中间件
from peek.net.webserver.middleware.ratelimit import (
    # 配置
    MethodQPSConfig,
    QPSLimitConfig,
    QPSStats,
    # 限流器
    TokenBucketLimiter,
    ConcurrencyLimiter,
    MethodLimiter,
    MethodQPSLimiter,
    QPSLimiter,
    # 中间件
    QPSRateLimitMiddleware,
    ConcurrencyLimitMiddleware,
    # 工厂函数
    create_qps_limiter,
    limit_all_qps,
    limit_all_concurrency,
    # 统计处理器
    RateLimitStatsHandler,
)

# 导出超时中间件
from peek.net.webserver.middleware.timeout import (
    TimeoutMiddleware,
    PathTimeoutMiddleware,
    timeout,
)

# 导出请求耗时中间件
from peek.net.webserver.middleware.timer import (
    HttpTimerMiddleware,
)

# 导出 OpenTelemetry 中间件
from peek.net.webserver.middleware.opentelemetry import (
    TraceMiddleware,
    MetricMiddleware,
)

# 中间件函数类型
MiddlewareFunc = Callable[[Request, Callable], Awaitable[Response]]
PreHandlerFunc = Callable[[Request], Awaitable[Optional[Response]]]
PostHandlerFunc = Callable[[Request, Response], Awaitable[None]]

__all__ = [
    # 基础中间件
    "HandlerChain",
    "HandlerChainMiddleware",
    "RequestIDMiddleware",
    "TimerMiddleware",
    "RecoveryMiddleware",
    "LoggerMiddleware",
    "MaxBodySizeMiddleware",
    "create_default_handler_chain",
    # 限流
    "MethodQPSConfig",
    "QPSLimitConfig",
    "QPSStats",
    "TokenBucketLimiter",
    "ConcurrencyLimiter",
    "MethodLimiter",
    "MethodQPSLimiter",
    "QPSLimiter",
    "QPSRateLimitMiddleware",
    "ConcurrencyLimitMiddleware",
    "create_qps_limiter",
    "limit_all_qps",
    "limit_all_concurrency",
    "RateLimitStatsHandler",
    # 超时
    "TimeoutMiddleware",
    "PathTimeoutMiddleware",
    "timeout",
    # 请求耗时
    "HttpTimerMiddleware",
    # OpenTelemetry
    "TraceMiddleware",
    "MetricMiddleware",
    # 类型
    "MiddlewareFunc",
    "PreHandlerFunc",
    "PostHandlerFunc",
]


class HandlerChain:
    """
    HTTP 中间件链

    类似 Go 版本的 HandlerChain，支持：
    - PreHandlers: 前置处理器
    - Handlers: 中间件列表（按顺序执行）
    - PostHandlers: 后置处理器
    """

    def __init__(self):
        self._pre_handlers: List[PreHandlerFunc] = []
        self._handlers: List[BaseHTTPMiddleware] = []
        self._post_handlers: List[PostHandlerFunc] = []

    def add_pre_handler(self, handler: PreHandlerFunc) -> "HandlerChain":
        """
        添加前置处理器

        Args:
            handler: 前置处理器函数，返回 Response 则终止请求

        Returns:
            self
        """
        self._pre_handlers.append(handler)
        return self

    def add_handler(self, middleware_class: type, **kwargs) -> "HandlerChain":
        """
        添加中间件

        Args:
            middleware_class: 中间件类
            **kwargs: 中间件参数

        Returns:
            self
        """
        self._handlers.append((middleware_class, kwargs))
        return self

    def add_post_handler(self, handler: PostHandlerFunc) -> "HandlerChain":
        """
        添加后置处理器

        Args:
            handler: 后置处理器函数

        Returns:
            self
        """
        self._post_handlers.append(handler)
        return self

    def install(self, app: FastAPI) -> None:
        """
        安装中间件链到 FastAPI 应用

        Args:
            app: FastAPI 应用实例
        """
        # 反向添加中间件（保证执行顺序）
        for middleware_class, kwargs in reversed(self._handlers):
            app.add_middleware(middleware_class, **kwargs)

        # 添加 PreHandler 和 PostHandler 包装中间件
        if self._pre_handlers or self._post_handlers:
            app.add_middleware(
                HandlerChainMiddleware,
                pre_handlers=self._pre_handlers,
                post_handlers=self._post_handlers,
            )


class HandlerChainMiddleware(BaseHTTPMiddleware):
    """
    HandlerChain 包装中间件

    执行 PreHandlers 和 PostHandlers
    """

    def __init__(
        self,
        app: ASGIApp,
        pre_handlers: List[PreHandlerFunc] = None,
        post_handlers: List[PostHandlerFunc] = None,
    ):
        super().__init__(app)
        self._pre_handlers = pre_handlers or []
        self._post_handlers = post_handlers or []

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 执行前置处理器
        for pre_handler in self._pre_handlers:
            result = await pre_handler(request)
            if result is not None:
                return result

        # 执行主处理逻辑
        response = await call_next(request)

        # 执行后置处理器
        for post_handler in self._post_handlers:
            await post_handler(request, response)

        return response


# ==================== 内置中间件 ====================


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Request ID 中间件

    为每个请求生成唯一的 Request ID
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
    ):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 尝试从请求头获取 Request ID，否则生成新的
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())

        # 存储到 request.state
        request.state.request_id = request_id

        # 调用下一个处理器
        response = await call_next(request)

        # 添加到响应头
        response.headers[self.header_name] = request_id

        return response


class TimerMiddleware(BaseHTTPMiddleware):
    """
    计时器中间件

    记录请求处理时间
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Response-Time",
    ):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start_time
        duration_ms = round(duration * 1000, 2)

        # 存储到 request.state
        request.state.duration_ms = duration_ms

        # 添加到响应头
        response.headers[self.header_name] = f"{duration_ms}ms"

        return response


class RecoveryMiddleware(BaseHTTPMiddleware):
    """
    异常恢复中间件

    捕获未处理的异常，返回 500 错误
    """

    def __init__(
        self,
        app: ASGIApp,
        debug: bool = False,
    ):
        super().__init__(app)
        self.debug = debug

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            # 打印堆栈
            traceback.print_exc()

            # 构建错误响应
            error_detail = str(e) if self.debug else "Internal Server Error"

            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=500,
                content={
                    "error": error_detail,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )


class LoggerMiddleware(BaseHTTPMiddleware):
    """
    日志中间件

    记录请求和响应信息，包括请求体和响应体内容
    对大字符串字段只打印前 N 个字节和总长度
    """

    # 默认字符串截断长度
    DEFAULT_MAX_STRING_LENGTH = 10

    def __init__(
        self,
        app: ASGIApp,
        logger: Any = None,
        log_request_body: bool = True,
        log_response_body: bool = True,
        log_request_headers: bool = False,
        log_response_headers: bool = False,
        max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
        skip_paths: List[str] = None,
    ):
        """
        初始化日志中间件

        Args:
            app: ASGI 应用
            logger: 日志记录器
            log_request_body: 是否记录请求体
            log_response_body: 是否记录响应体
            log_request_headers: 是否记录请求头（类似 Go 版 InOutputHeaderPrinter）
            log_response_headers: 是否记录响应头（类似 Go 版 InOutputHeaderPrinter）
            max_string_length: 字符串字段的最大打印长度，超过则截断
            skip_paths: 跳过记录的路径列表（如 /health, /metrics）
        """
        super().__init__(app)
        self.logger = logger
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.log_request_headers = log_request_headers
        self.log_response_headers = log_response_headers
        self.max_string_length = max_string_length
        self.skip_paths = skip_paths or ["/health", "/healthz", "/metrics", "/ready"]

    def _log(self, msg: str, level: str = "info") -> None:
        """统一日志输出"""
        if self.logger:
            log_func = getattr(self.logger, level, self.logger.info)
            log_func(msg)
        else:
            print(msg)

    def _truncate_string(self, value: str) -> str:
        """
        截断字符串，对于超过限制的字符串只保留前 N 个字节并显示总长度

        Args:
            value: 原始字符串

        Returns:
            截断后的字符串，格式: "前N字节...(总长度:X bytes)"
        """
        if len(value) <= self.max_string_length:
            return value

        # 对于超长字符串，只显示前 N 个字节和总长度
        truncated = value[:self.max_string_length]
        return f"{truncated}...(len:{len(value)} bytes)"

    def _truncate_value(self, value: Any) -> Any:
        """
        递归处理值，对字符串进行截断

        Args:
            value: 任意类型的值

        Returns:
            处理后的值
        """
        if isinstance(value, str):
            return self._truncate_string(value)
        elif isinstance(value, bytes):
            # 对 bytes 类型也进行截断
            if len(value) <= self.max_string_length:
                return f"<bytes:{len(value)}>"
            return f"<bytes:{self.max_string_length}+...>(len:{len(value)} bytes)"
        elif isinstance(value, dict):
            return {k: self._truncate_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._truncate_value(item) for item in value]
        elif isinstance(value, tuple):
            return tuple(self._truncate_value(item) for item in value)
        else:
            return value

    async def _get_request_body(self, request: Request) -> Optional[str]:
        """
        获取请求体内容

        Args:
            request: FastAPI Request 对象

        Returns:
            请求体字符串或 None
        """
        try:
            # 读取请求体
            body = await request.body()
            if not body:
                return None

            # 尝试解析为 JSON
            try:
                import json
                body_json = json.loads(body)
                # 对 JSON 内容进行截断处理
                truncated_body = self._truncate_value(body_json)
                return json.dumps(truncated_body, ensure_ascii=False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 非 JSON 内容，直接截断原始字符串
                body_str = body.decode("utf-8", errors="replace")
                return self._truncate_string(body_str)

        except Exception as e:
            return f"<error reading body: {e}>"

    def _format_response_body(self, body: bytes) -> str:
        """
        格式化响应体内容

        Args:
            body: 响应体字节

        Returns:
            格式化后的字符串
        """
        if not body:
            return "<empty>"

        try:
            import json
            body_json = json.loads(body)
            # 对 JSON 内容进行截断处理
            truncated_body = self._truncate_value(body_json)
            return json.dumps(truncated_body, ensure_ascii=False)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 非 JSON 内容
            try:
                body_str = body.decode("utf-8", errors="replace")
                return self._truncate_string(body_str)
            except Exception:
                return f"<binary data, len:{len(body)} bytes>"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 检查是否跳过该路径
        if request.url.path in self.skip_paths:
            return await call_next(request)

        start_time = time.perf_counter()

        # 获取 request_id（如果存在）
        request_id = getattr(request.state, "request_id", "-")

        # 记录请求
        log_msg = f"[{request_id}] --> {request.method} {request.url.path}"

        # 记录请求头（类似 Go 版 InOutputHeaderPrinter 的 recv headers）
        if self.log_request_headers:
            headers_dict = dict(request.headers)
            log_msg += f" | headers: {headers_dict}"

        # 记录请求体
        if self.log_request_body:
            request_body = await self._get_request_body(request)
            if request_body:
                log_msg += f" | body: {request_body}"

        self._log(log_msg)

        # 调用下一个处理器，并捕获响应体
        if self.log_response_body:
            # 需要捕获响应体，使用自定义的响应包装
            response = await call_next(request)

            # 读取响应体
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # 计算耗时
            duration = time.perf_counter() - start_time
            duration_ms = round(duration * 1000, 2)

            # 记录响应
            response_body_str = self._format_response_body(response_body)
            log_msg = (
                f"[{request_id}] <-- {request.method} {request.url.path} "
                f"{response.status_code} {duration_ms}ms"
            )

            # 记录响应头（类似 Go 版 InOutputHeaderPrinter 的 send headers）
            if self.log_response_headers:
                resp_headers_dict = dict(response.headers)
                log_msg += f" | headers: {resp_headers_dict}"

            log_msg += f" | body: {response_body_str}"
            self._log(log_msg)

            # 重新构建响应（因为 body_iterator 只能读取一次）
            from starlette.responses import Response as StarletteResponse
            return StarletteResponse(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        else:
            response = await call_next(request)

            # 计算耗时
            duration = time.perf_counter() - start_time
            duration_ms = round(duration * 1000, 2)

            # 记录响应
            log_msg = (
                f"[{request_id}] <-- {request.method} {request.url.path} "
                f"{response.status_code} {duration_ms}ms"
            )

            # 记录响应头
            if self.log_response_headers:
                resp_headers_dict = dict(response.headers)
                log_msg += f" | headers: {resp_headers_dict}"

            self._log(log_msg)

            return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """
    最大请求体大小限制中间件
    """

    def __init__(
        self,
        app: ASGIApp,
        max_body_size: int,
    ):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if self.max_body_size > 0:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_body_size:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Request body too large",
                        "max_size": self.max_body_size,
                    },
                )

        return await call_next(request)


def create_default_handler_chain(
    debug: bool = False,
    max_body_size: int = 0,
    logger: Any = None,
    log_request_body: bool = True,
    log_response_body: bool = True,
    log_request_headers: bool = False,
    log_response_headers: bool = False,
    max_string_length: int = LoggerMiddleware.DEFAULT_MAX_STRING_LENGTH,
    skip_log_paths: List[str] = None,
) -> HandlerChain:
    """
    创建默认的中间件链

    包含：
    - RequestIDMiddleware: Request ID 生成
    - RecoveryMiddleware: 异常恢复
    - TimerMiddleware: 计时器
    - LoggerMiddleware: 日志记录（支持请求/响应的 body 和 headers）
    - MaxBodySizeMiddleware: 请求体大小限制（如果设置）

    Args:
        debug: 是否开启调试模式
        max_body_size: 最大请求体大小（0 表示不限制）
        logger: 日志记录器
        log_request_body: 是否记录请求体
        log_response_body: 是否记录响应体
        log_request_headers: 是否记录请求头
        log_response_headers: 是否记录响应头
        max_string_length: 字符串字段的最大打印长度，超过则截断
        skip_log_paths: 跳过记录的路径列表

    Returns:
        HandlerChain 实例
    """
    chain = HandlerChain()

    # 注意：中间件按添加顺序的反序执行
    # 所以先添加的最后执行
    chain.add_handler(
        LoggerMiddleware,
        logger=logger,
        log_request_body=log_request_body,
        log_response_body=log_response_body,
        log_request_headers=log_request_headers,
        log_response_headers=log_response_headers,
        max_string_length=max_string_length,
        skip_paths=skip_log_paths,
    )
    chain.add_handler(TimerMiddleware)
    chain.add_handler(RecoveryMiddleware, debug=debug)
    chain.add_handler(RequestIDMiddleware)

    if max_body_size > 0:
        chain.add_handler(MaxBodySizeMiddleware, max_body_size=max_body_size)

    return chain
