#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP/gRPC 错误处理器

将 AppError 自动转换为对应的 HTTP 响应 / gRPC Status Code。

用法示例：
    # HTTP - 安装到 FastAPI
    from peek.errors.handler import install_error_handlers
    install_error_handlers(app)

    # gRPC - 添加拦截器
    from peek.errors.handler import ErrorHandlerInterceptor
    chain.add(ErrorHandlerInterceptor())
"""

import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from peek.errors.errors import AppError

logger = logging.getLogger(__name__)


# ============ HTTP 错误处理器 ============

def install_error_handlers(app: Any) -> None:
    """
    在 FastAPI 应用上安装统一错误处理器

    自动将 AppError 转换为 JSON 响应，并处理 Pydantic ValidationError。

    Args:
        app: FastAPI 应用实例
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """处理 AppError 及其子类"""
        request_id = getattr(request.state, "request_id", "-")
        logger.warning(
            "[%s] AppError: code=%d, message=%s",
            request_id, exc.code, exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.to_dict(),
        )

    # 处理 Pydantic ValidationError → 统一转为 400 格式
    try:
        from pydantic import ValidationError as PydanticValidationError

        @app.exception_handler(PydanticValidationError)
        async def pydantic_error_handler(
            request: Request, exc: PydanticValidationError
        ) -> JSONResponse:
            """将 Pydantic 校验错误统一转为 AppError 格式"""
            request_id = getattr(request.state, "request_id", "-")
            errors = exc.errors() if hasattr(exc, "errors") else []
            logger.warning(
                "[%s] ValidationError: %s", request_id, errors,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "code": 400,
                    "message": "Validation failed",
                    "details": {"errors": errors},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
    except ImportError:
        pass

    # 处理 FastAPI 自身的 RequestValidationError
    try:
        from fastapi.exceptions import RequestValidationError

        @app.exception_handler(RequestValidationError)
        async def request_validation_error_handler(
            request: Request, exc: RequestValidationError
        ) -> JSONResponse:
            """将 FastAPI 请求参数校验错误统一转为 AppError 格式"""
            request_id = getattr(request.state, "request_id", "-")
            errors = exc.errors() if hasattr(exc, "errors") else []
            logger.warning(
                "[%s] RequestValidationError: %s", request_id, errors,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "code": 400,
                    "message": "Request validation failed",
                    "details": {"errors": errors},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
    except ImportError:
        pass


# ============ gRPC 错误处理器 ============

class ErrorHandlerInterceptor:
    """
    gRPC 错误处理拦截器

    捕获 AppError 并自动转换为对应的 gRPC Status Code。
    """

    def intercept_unary(
        self,
        request: Any,
        context: Any,
        method_name: str,
        handler: Callable,
    ) -> Any:
        """拦截 Unary 请求"""
        try:
            return handler(request, context)
        except AppError as e:
            logger.warning(
                "gRPC AppError in %s: code=%d, message=%s",
                method_name, e.code, e.message,
            )
            grpc_code = e.grpc_status_code
            if grpc_code is not None:
                context.abort(grpc_code, e.message)
            else:
                # 没有 grpc 模块时，直接 re-raise
                raise
        except Exception:
            # 非 AppError，由 RecoveryInterceptor 处理
            raise

    def intercept_service(self, continuation, handler_call_details):
        """实现 grpc.ServerInterceptor 接口"""
        try:
            import grpc
        except ImportError:
            return continuation(handler_call_details)

        next_handler = continuation(handler_call_details)

        if next_handler is None:
            return None

        if next_handler.unary_unary is None:
            return next_handler

        original_handler = next_handler.unary_unary

        def wrapped_unary(request, context):
            return self.intercept_unary(
                request, context,
                handler_call_details.method,
                original_handler,
            )

        return grpc.unary_unary_rpc_method_handler(
            wrapped_unary,
            request_deserializer=next_handler.request_deserializer,
            response_serializer=next_handler.response_serializer,
        )
