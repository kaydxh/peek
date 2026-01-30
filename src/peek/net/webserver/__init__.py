#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebServer 模块

提供类似 Go 版本 golang 库的 Web 服务器框架能力，包括：
- GenericWebServer: 通用 Web 服务器
- 生命周期钩子: PostStartHook, PreShutdownHook
- 中间件链: HandlerChain
- 健康检查: HealthzController
- 配置管理: Config, Option 模式
- QPS 限流: QPSRateLimitMiddleware
- OpenTelemetry: TraceMiddleware, MetricMiddleware
"""

from peek.net.webserver.server import GenericWebServer, WebHandler
from peek.net.webserver.config import (
    Config,
    CompletedConfig,
    WebServerConfig,
    WebConfig,
    BindAddress,
    HTTPConfig,
    DebugConfig,
    QPSLimitConfig,
    OpenTelemetryConfig,
    # Option 函数
    with_bind_address,
    with_external_address,
    with_shutdown_delay_duration,
    with_shutdown_timeout_duration,
    with_title,
    with_description,
    with_version,
    with_docs_url,
    with_redoc_url,
)
from peek.net.webserver.hooks import (
    PostStartHookFunc,
    PreShutdownHookFunc,
    HookEntry,
)
from peek.net.webserver.healthz import (
    HealthzController,
    HealthChecker,
    PingHealthChecker,
    HTTPHealthChecker,
    TCPHealthChecker,
    FuncHealthChecker,
    CompositeHealthChecker,
)
from peek.net.webserver.middleware import (
    HandlerChain,
    RequestIDMiddleware,
    TimerMiddleware,
    RecoveryMiddleware,
    LoggerMiddleware,
    MaxBodySizeMiddleware,
    create_default_handler_chain,
)
from peek.net.webserver.middleware.ratelimit import (
    QPSLimiter,
    QPSRateLimitMiddleware,
    TokenBucketLimiter,
    ConcurrencyLimitMiddleware,
)
from peek.net.webserver.middleware.opentelemetry import (
    TraceMiddleware,
    MetricMiddleware,
)

__all__ = [
    # Server
    "GenericWebServer",
    "WebHandler",
    # Config
    "Config",
    "CompletedConfig",
    "WebServerConfig",
    "WebConfig",
    "BindAddress",
    "HTTPConfig",
    "DebugConfig",
    "QPSLimitConfig",
    "OpenTelemetryConfig",
    # Option 函数
    "with_bind_address",
    "with_external_address",
    "with_shutdown_delay_duration",
    "with_shutdown_timeout_duration",
    "with_title",
    "with_description",
    "with_version",
    "with_docs_url",
    "with_redoc_url",
    # Hooks
    "PostStartHookFunc",
    "PreShutdownHookFunc",
    "HookEntry",
    # Healthz
    "HealthzController",
    "HealthChecker",
    "PingHealthChecker",
    "HTTPHealthChecker",
    "TCPHealthChecker",
    "FuncHealthChecker",
    "CompositeHealthChecker",
    # Middleware
    "HandlerChain",
    "RequestIDMiddleware",
    "TimerMiddleware",
    "RecoveryMiddleware",
    "LoggerMiddleware",
    "MaxBodySizeMiddleware",
    "create_default_handler_chain",
    # Rate Limit
    "QPSLimiter",
    "QPSRateLimitMiddleware",
    "TokenBucketLimiter",
    "ConcurrencyLimitMiddleware",
    # OpenTelemetry
    "TraceMiddleware",
    "MetricMiddleware",
]
