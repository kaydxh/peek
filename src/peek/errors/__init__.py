#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一错误处理模块

提供应用级统一错误体系，对应 Go 版本的 errors 包。

子模块：
- peek.errors.errors: 应用级错误类定义
- peek.errors.handler: HTTP/gRPC 错误处理器
"""

from peek.errors.errors import (
    AppError,
    AppTimeoutError,
    ConflictError,
    ErrorCode,
    InternalError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthenticatedError,
    ValidationError,
)
from peek.errors.handler import (
    build_validation_response,
    format_validation_error,
    format_validation_errors,
    install_error_handlers,
)

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationError",
    "PermissionDeniedError",
    "UnauthenticatedError",
    "ConflictError",
    "InternalError",
    "ServiceUnavailableError",
    "AppTimeoutError",
    "RateLimitError",
    "ErrorCode",
    "install_error_handlers",
    "format_validation_error",
    "format_validation_errors",
    "build_validation_response",
]
