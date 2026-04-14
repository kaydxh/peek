#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebServer 模块

提供 Web 服务器框架能力，包括：
- GenericWebServer: 通用 Web 服务器
- 生命周期钩子: PostStartHook, PreShutdownHook
- 健康检查: HealthzController
- 配置管理: YAML 配置文件支持
- 中间件: 限流、超时、追踪、指标等
"""

from peek.net.webserver.config import (  # 配置模型; 限流配置; 配置加载; 配置构建器; 工具函数
    AppConfig,
    ConfigLoader,
    DebugConfig,
    GrpcConfig,
    HttpConfig,
    MethodQPSConfigItem,
    NetConfig,
    OpenTelemetryConfig,
    QPSLimitConfig,
    ShutdownConfig,
    WebConfig,
    WebServerConfigBuilder,
    load_config,
    load_config_from_file,
    parse_duration,
)
from peek.net.webserver.factory import (
    create_web_server,
    install_grpc_interceptors,
    install_qps_limit_middleware,
)
from peek.net.webserver.healthz import (
    CompositeHealthChecker,
    FuncHealthChecker,
    HealthChecker,
    HealthzController,
    HTTPHealthChecker,
    PingHealthChecker,
    TCPHealthChecker,
)
from peek.net.webserver.hooks import (
    HookEntry,
    PostStartHookFunc,
    PreShutdownHookFunc,
)
from peek.net.webserver.server import GenericWebServer, WebHandler

__all__ = [
    # Server
    "GenericWebServer",
    "WebHandler",
    # Config Models
    "WebConfig",
    "NetConfig",
    "GrpcConfig",
    "HttpConfig",
    "DebugConfig",
    "OpenTelemetryConfig",
    "ShutdownConfig",
    "AppConfig",
    # Rate Limit Config
    "QPSLimitConfig",
    "MethodQPSConfigItem",
    # Config Loader
    "ConfigLoader",
    "load_config",
    "load_config_from_file",
    # Config Builder
    "WebServerConfigBuilder",
    # Utils
    "parse_duration",
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
    # Factory
    "create_web_server",
    "install_grpc_interceptors",
    "install_qps_limit_middleware",
]
