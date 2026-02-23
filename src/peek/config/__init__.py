#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块

提供通用的配置加载能力和配置模型：
- ConfigLoader: 配置加载器（YAML + 环境变量 + 多文件合并）
- load_config_from_file: 从文件加载配置的快捷函数
- load_config: 从字典加载配置的快捷函数
- 通用配置模型：WebConfig, LogConfig, GrpcConfig 等
"""

from peek.config.loader import (
    ConfigLoader,
    load_config,
    load_config_from_file,
)
from peek.config.schema import (
    NetConfig,
    GrpcConfig,
    HttpConfig,
    MethodQPSConfig,
    QPSLimitConfig,
    DebugConfig,
    ShutdownConfig,
    WebConfig,
    LogConfig,
    OpenTelemetryConfig,
    MonitorConfig,
    DatabaseConfig,
)
from peek.config.watcher import ConfigWatcher

__all__ = [
    # Loader
    "ConfigLoader",
    "load_config",
    "load_config_from_file",
    # Watcher
    "ConfigWatcher",
    # Config Models
    "NetConfig",
    "GrpcConfig",
    "HttpConfig",
    "MethodQPSConfig",
    "QPSLimitConfig",
    "DebugConfig",
    "ShutdownConfig",
    "WebConfig",
    "LogConfig",
    "OpenTelemetryConfig",
    "MonitorConfig",
    "DatabaseConfig",
]
