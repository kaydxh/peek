#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP 中间件链模块

提供中间件链管理支持：
- HandlerChain: 中间件链管理器
- HandlerChainMiddleware: PreHandler/PostHandler 包装中间件
"""

from typing import Awaitable, Callable, List, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

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
