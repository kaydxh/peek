#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
计时器中间件

记录请求处理时间并写入响应头
"""

import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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
