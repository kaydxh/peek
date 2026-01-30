#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
中间件链

参考 Go 版本 golang 库的 http_handler_interceptor.go 实现
提供 HTTP 中间件链支持
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


# 中间件函数类型
MiddlewareFunc = Callable[[Request, Callable], Awaitable[Response]]
PreHandlerFunc = Callable[[Request], Awaitable[Optional[Response]]]
PostHandlerFunc = Callable[[Request, Response], Awaitable[None]]


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

    记录请求和响应信息
    """

    def __init__(
        self,
        app: ASGIApp,
        logger: Any = None,
    ):
        super().__init__(app)
        self.logger = logger

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start_time = time.perf_counter()

        # 获取 request_id（如果存在）
        request_id = getattr(request.state, "request_id", "-")

        # 记录请求
        log_msg = (
            f"[{request_id}] --> {request.method} {request.url.path}"
        )
        if self.logger:
            self.logger.info(log_msg)
        else:
            print(log_msg)

        response = await call_next(request)

        # 计算耗时
        duration = time.perf_counter() - start_time
        duration_ms = round(duration * 1000, 2)

        # 记录响应
        log_msg = (
            f"[{request_id}] <-- {request.method} {request.url.path} "
            f"{response.status_code} {duration_ms}ms"
        )
        if self.logger:
            self.logger.info(log_msg)
        else:
            print(log_msg)

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
) -> HandlerChain:
    """
    创建默认的中间件链

    包含：
    - RequestIDMiddleware: Request ID 生成
    - RecoveryMiddleware: 异常恢复
    - TimerMiddleware: 计时器
    - LoggerMiddleware: 日志记录
    - MaxBodySizeMiddleware: 请求体大小限制（如果设置）

    Args:
        debug: 是否开启调试模式
        max_body_size: 最大请求体大小（0 表示不限制）
        logger: 日志记录器

    Returns:
        HandlerChain 实例
    """
    chain = HandlerChain()

    # 注意：中间件按添加顺序的反序执行
    # 所以先添加的最后执行
    chain.add_handler(LoggerMiddleware, logger=logger)
    chain.add_handler(TimerMiddleware)
    chain.add_handler(RecoveryMiddleware, debug=debug)
    chain.add_handler(RequestIDMiddleware)

    if max_body_size > 0:
        chain.add_handler(MaxBodySizeMiddleware, max_body_size=max_body_size)

    return chain
