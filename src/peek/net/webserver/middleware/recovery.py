#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
异常恢复中间件

捕获未处理的异常，返回 500 错误
"""

import traceback
from datetime import datetime, timezone
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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
