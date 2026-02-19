#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
最大请求体大小限制中间件
"""

from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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
