#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC 中间件模块

提供 gRPC 服务端和客户端拦截器：
- 限流拦截器
- OpenTelemetry 追踪和指标拦截器
- 日志拦截器
"""

from peek.net.grpc.middleware.opentelemetry import (
    MetricInterceptor,
    TraceInterceptor,
)
from peek.net.grpc.middleware.ratelimit import (
    ConcurrencyLimitInterceptor,
    MethodQPSLimitInterceptor,
    QPSLimitInterceptor,
)

# 参数校验拦截器（延迟导入避免循环依赖）
try:
    from peek.validation.grpc_interceptor import ValidationInterceptor
except ImportError:
    ValidationInterceptor = None

__all__ = [
    # 限流
    "QPSLimitInterceptor",
    "ConcurrencyLimitInterceptor",
    "MethodQPSLimitInterceptor",
    # OpenTelemetry
    "TraceInterceptor",
    "MetricInterceptor",
    # 参数校验
    "ValidationInterceptor",
]
