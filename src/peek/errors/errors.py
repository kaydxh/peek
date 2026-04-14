#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一错误类定义

提供应用级统一错误体系，支持自动映射到 HTTP 状态码和 gRPC Status Code。

用法示例：
    from peek.errors import NotFoundError, ValidationError

    # 抛出业务错误
    raise NotFoundError("用户不存在", details={"user_id": 123})
    raise ValidationError("参数校验失败", details={"field": "email"})

    # 自定义错误码
    raise AppError(code=ErrorCode.CUSTOM, message="自定义错误", http_status=400)
"""

import enum
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ErrorCode(enum.IntEnum):
    """
    标准错误码枚举

    与 HTTP 状态码和 gRPC Status Code 对应。
    """

    # 客户端错误
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    GONE = 410
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429

    # 服务端错误
    INTERNAL = 500
    NOT_IMPLEMENTED = 501
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

    # 自定义（业务可扩展）
    CUSTOM = 10000


class AppError(Exception):
    """
    应用统一错误基类

    所有业务错误都应继承此类。
    支持自动映射到 HTTP 状态码和 gRPC Status Code。

    Attributes:
        code: 错误码（ErrorCode 枚举或自定义整数）
        message: 人类可读的错误信息
        details: 错误详情（字典，可选）
        http_status: 对应的 HTTP 状态码
        grpc_status: 对应的 gRPC Status Code 名称
    """

    # HTTP 状态码 → gRPC Status Code 映射
    _GRPC_STATUS_MAP = {
        400: "INVALID_ARGUMENT",
        401: "UNAUTHENTICATED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        409: "ALREADY_EXISTS",
        410: "NOT_FOUND",
        422: "INVALID_ARGUMENT",
        429: "RESOURCE_EXHAUSTED",
        500: "INTERNAL",
        501: "UNIMPLEMENTED",
        503: "UNAVAILABLE",
        504: "DEADLINE_EXCEEDED",
    }

    def __init__(
        self,
        message: str = "Internal server error",
        code: int = ErrorCode.INTERNAL,
        details: Optional[Dict[str, Any]] = None,
        http_status: Optional[int] = None,
        cause: Optional[Exception] = None,
    ):
        """
        初始化应用错误

        Args:
            message: 错误消息
            code: 错误码
            details: 错误详情字典
            http_status: HTTP 状态码（如不指定，默认使用 code 值）
            cause: 原始异常（用于链式异常追踪）
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status or code
        self.cause = cause

    @property
    def grpc_status(self) -> str:
        """获取对应的 gRPC Status Code 名称"""
        return self._GRPC_STATUS_MAP.get(self.http_status, "INTERNAL")

    @property
    def grpc_status_code(self) -> Any:
        """
        获取 grpc.StatusCode 枚举值

        Returns:
            grpc.StatusCode 枚举值，如果 grpc 不可用则返回 None
        """
        try:
            import grpc

            status_map = {
                "INVALID_ARGUMENT": grpc.StatusCode.INVALID_ARGUMENT,
                "UNAUTHENTICATED": grpc.StatusCode.UNAUTHENTICATED,
                "PERMISSION_DENIED": grpc.StatusCode.PERMISSION_DENIED,
                "NOT_FOUND": grpc.StatusCode.NOT_FOUND,
                "ALREADY_EXISTS": grpc.StatusCode.ALREADY_EXISTS,
                "RESOURCE_EXHAUSTED": grpc.StatusCode.RESOURCE_EXHAUSTED,
                "INTERNAL": grpc.StatusCode.INTERNAL,
                "UNIMPLEMENTED": grpc.StatusCode.UNIMPLEMENTED,
                "UNAVAILABLE": grpc.StatusCode.UNAVAILABLE,
                "DEADLINE_EXCEEDED": grpc.StatusCode.DEADLINE_EXCEEDED,
            }
            return status_map.get(self.grpc_status, grpc.StatusCode.INTERNAL)
        except ImportError:
            return None

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（用于 HTTP JSON 响应）

        Returns:
            错误信息字典
        """
        result = {
            "code": int(self.code),
            "message": self.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.details:
            result["details"] = self.details
        return result

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.code}, "
            f"message='{self.message}', "
            f"http_status={self.http_status}"
            f")"
        )


class NotFoundError(AppError):
    """资源未找到错误（HTTP 404 / gRPC NOT_FOUND）"""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            details=details,
            http_status=404,
            cause=cause,
        )


class ValidationError(AppError):
    """参数校验错误（HTTP 400 / gRPC INVALID_ARGUMENT）"""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.BAD_REQUEST,
            details=details,
            http_status=400,
            cause=cause,
        )


class PermissionDeniedError(AppError):
    """权限不足错误（HTTP 403 / gRPC PERMISSION_DENIED）"""

    def __init__(
        self,
        message: str = "Permission denied",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN,
            details=details,
            http_status=403,
            cause=cause,
        )


class UnauthenticatedError(AppError):
    """未认证错误（HTTP 401 / gRPC UNAUTHENTICATED）"""

    def __init__(
        self,
        message: str = "Unauthenticated",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHORIZED,
            details=details,
            http_status=401,
            cause=cause,
        )


class ConflictError(AppError):
    """资源冲突错误（HTTP 409 / gRPC ALREADY_EXISTS）"""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.CONFLICT,
            details=details,
            http_status=409,
            cause=cause,
        )


class InternalError(AppError):
    """内部服务错误（HTTP 500 / gRPC INTERNAL）"""

    def __init__(
        self,
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL,
            details=details,
            http_status=500,
            cause=cause,
        )


class ServiceUnavailableError(AppError):
    """服务不可用错误（HTTP 503 / gRPC UNAVAILABLE）"""

    def __init__(
        self,
        message: str = "Service unavailable",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            details=details,
            http_status=503,
            cause=cause,
        )


class AppTimeoutError(AppError):
    """超时错误（HTTP 504 / gRPC DEADLINE_EXCEEDED）

    注意：命名为 AppTimeoutError 而非 TimeoutError，避免遮蔽 Python 内置的 builtins.TimeoutError。
    """

    def __init__(
        self,
        message: str = "Request timeout",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.GATEWAY_TIMEOUT,
            details=details,
            http_status=504,
            cause=cause,
        )


class RateLimitError(AppError):
    """限流错误（HTTP 429 / gRPC RESOURCE_EXHAUSTED）"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.TOO_MANY_REQUESTS,
            details=details,
            http_status=429,
            cause=cause,
        )
