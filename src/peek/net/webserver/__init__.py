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

from peek.net.webserver.server import GenericWebServer, WebHandler
from peek.net.webserver.config import (
    # 配置模型
    WebConfig,
    NetConfig,
    GrpcConfig,
    HttpConfig,
    DebugConfig,
    OpenTelemetryConfig,
    ShutdownConfig,
    AppConfig,
    # 限流配置
    QPSLimitConfig,
    MethodQPSConfigItem,
    # 配置加载
    ConfigLoader,
    load_config,
    load_config_from_file,
    # 配置构建器
    WebServerConfigBuilder,
    # 工具函数
    parse_duration,
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
]
