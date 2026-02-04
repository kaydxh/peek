#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC 模块

提供 gRPC 服务端和客户端能力，包括：
- GRPCServer: gRPC 服务器
- GRPCGateway: HTTP/gRPC 网关
- 拦截器链: 支持各类 gRPC 拦截器
- 中间件: 限流、追踪、指标
- 健康检查: gRPC Health Checking Protocol
"""

from peek.net.grpc.server import GRPCServer, AsyncGRPCServer
from peek.net.grpc.gateway import GRPCGateway
from peek.net.grpc.interceptor import (
    UnaryServerInterceptor,
    StreamServerInterceptor,
    InterceptorChain,
    RequestIDInterceptor,
    RecoveryInterceptor,
    LoggingInterceptor,
    TimerInterceptor,
    QPSLimitInterceptor,
    ConcurrencyLimitInterceptor,
    create_default_interceptor_chain,
    get_request_id,
    get_start_time,
)
from peek.net.grpc.config import (
    GRPCConfig,
    GRPCServerConfig,
    GRPCClientConfig,
    GRPCGatewayConfig,
)

# 中间件模块
from peek.net.grpc.middleware import (
    # 限流
    QPSLimitInterceptor as MiddlewareQPSLimitInterceptor,
    ConcurrencyLimitInterceptor as MiddlewareConcurrencyLimitInterceptor,
    MethodQPSLimitInterceptor,
    # OpenTelemetry
    TraceInterceptor,
    MetricInterceptor,
)

__all__ = [
    # Server
    "GRPCServer",
    "AsyncGRPCServer",
    "GRPCGateway",
    # Interceptors
    "UnaryServerInterceptor",
    "StreamServerInterceptor",
    "InterceptorChain",
    "RequestIDInterceptor",
    "RecoveryInterceptor",
    "LoggingInterceptor",
    "TimerInterceptor",
    "QPSLimitInterceptor",
    "ConcurrencyLimitInterceptor",
    "create_default_interceptor_chain",
    "get_request_id",
    "get_start_time",
    # Middleware
    "MethodQPSLimitInterceptor",
    "TraceInterceptor",
    "MetricInterceptor",
    # Config
    "GRPCConfig",
    "GRPCServerConfig",
    "GRPCClientConfig",
    "GRPCGatewayConfig",
]
