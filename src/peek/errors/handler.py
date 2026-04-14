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
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from peek.errors.errors import AppError

logger = logging.getLogger(__name__)


# ============ 校验错误格式化工具 ============


def format_validation_error(
    raw_error: Dict[str, Any],
) -> Dict[str, Any]:
    """
    将 Pydantic/FastAPI 原始校验错误格式化为友好格式

    原始格式（Pydantic v2）:
        {
            "type": "string_too_short",
            "loc": ["body", "name"],
            "msg": "String should have at least 2 characters",
            "input": "a",
            "ctx": {"min_length": 2}
        }

    友好格式:
        {
            "field": "name",
            "message": "String should have at least 2 characters",
            "type": "string_too_short",
            "input": "a"
        }

    Args:
        raw_error: Pydantic/FastAPI 原始校验错误字典

    Returns:
        格式化后的错误字典
    """
    # 提取字段路径
    loc = raw_error.get("loc", [])
    # 过滤掉 "body"/"query"/"path" 等前缀
    field_parts = [
        str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")
    ]
    field = ".".join(field_parts) if field_parts else "unknown"

    result = {
        "field": field,
        "message": raw_error.get("msg", "Validation error"),
    }

    # 添加错误类型（如 "string_too_short"、"missing" 等）
    error_type = raw_error.get("type", "")
    if error_type:
        result["type"] = error_type

    # 添加输入值（脱敏处理：截断过长的输入）
    input_val = raw_error.get("input")
    if input_val is not None:
        input_str = str(input_val)
        if len(input_str) > 100:
            input_str = input_str[:100] + "..."
        result["input"] = input_str

    return result


def format_validation_errors(
    raw_errors: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    批量格式化 Pydantic/FastAPI 校验错误列表

    Args:
        raw_errors: Pydantic/FastAPI 原始校验错误列表

    Returns:
        格式化后的错误列表
    """
    return [format_validation_error(e) for e in raw_errors]


def build_validation_response(
    raw_errors: List[Dict[str, Any]],
    message: str = "Validation failed",
) -> Dict[str, Any]:
    """
    构建统一的校验错误响应体

    Args:
        raw_errors: Pydantic/FastAPI 原始校验错误列表
        message: 错误消息

    Returns:
        统一格式的错误响应字典
    """
    formatted_errors = format_validation_errors(raw_errors)

    # 生成人类可读的摘要信息
    if formatted_errors:
        fields = [e["field"] for e in formatted_errors]
        summary = f"{message}: {', '.join(fields)}"
    else:
        summary = message

    return {
        "code": 400,
        "message": summary,
        "details": {
            "errors": formatted_errors,
            "error_count": len(formatted_errors),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============ HTTP 错误处理器 ============


def install_error_handlers(app: Any) -> None:
    """
    在 FastAPI 应用上安装统一错误处理器

    自动将 AppError 和各类校验错误转换为统一的 JSON 响应格式。
    处理的异常类型：
    - AppError 及其子类 → 对应 HTTP 状态码 + 统一错误格式
    - Pydantic ValidationError → 400 + 友好的字段级错误列表
    - FastAPI RequestValidationError → 400 + 友好的字段级错误列表

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
            request_id,
            exc.code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.to_dict(),
        )

    # 处理 Pydantic ValidationError → 统一转为 400 友好格式
    try:
        from pydantic import ValidationError as PydanticValidationError

        @app.exception_handler(PydanticValidationError)
        async def pydantic_error_handler(
            request: Request, exc: PydanticValidationError
        ) -> JSONResponse:
            """将 Pydantic 校验错误统一转为友好格式"""
            request_id = getattr(request.state, "request_id", "-")
            raw_errors = exc.errors() if hasattr(exc, "errors") else []
            response_body = build_validation_response(raw_errors, "Validation failed")
            logger.warning(
                "[%s] ValidationError: %s",
                request_id,
                response_body["message"],
            )
            return JSONResponse(
                status_code=400,
                content=response_body,
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
            """将 FastAPI 请求参数校验错误统一转为友好格式"""
            request_id = getattr(request.state, "request_id", "-")
            raw_errors = exc.errors() if hasattr(exc, "errors") else []
            response_body = build_validation_response(
                raw_errors, "Request validation failed"
            )
            logger.warning(
                "[%s] RequestValidationError: %s",
                request_id,
                response_body["message"],
            )
            return JSONResponse(
                status_code=400,
                content=response_body,
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
                method_name,
                e.code,
                e.message,
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
                request,
                context,
                handler_call_details.method,
                original_handler,
            )

        return grpc.unary_unary_rpc_method_handler(
            wrapped_unary,
            request_deserializer=next_handler.request_deserializer,
            response_serializer=next_handler.response_serializer,
        )
