#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Request ID 中间件

为每个请求生成唯一的 Request ID
"""

import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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
