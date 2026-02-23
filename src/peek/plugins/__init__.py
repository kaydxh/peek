#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Peek Plugins - 公共插件模块

提供框架级别的公共插件功能，可被上层框架（如 tide）直接复用：
- logs: 日志安装函数式接口
- otel: OpenTelemetry 安装函数式接口
- monitor: 进程监控安装函数式接口
- base_options: 服务器运行选项基类（模板方法模式）
"""

from peek.plugins.base_options import (
    WebConfig,
    LogConfig,
    BaseServerRunOptions,
    BaseCompletedOptions,
    parse_web_config,
    parse_log_config,
    parse_monitor_config,
)
from peek.plugins.logs import install_logs
from peek.plugins.otel import install_opentelemetry, get_opentelemetry_service
from peek.plugins.monitor import install_monitor, uninstall_monitor, get_monitor_service

__all__ = [
    # 公共配置 dataclass
    "WebConfig",
    "LogConfig",
    # 配置解析函数
    "parse_web_config",
    "parse_log_config",
    "parse_monitor_config",
    # 基类
    "BaseServerRunOptions",
    "BaseCompletedOptions",
    # 函数式接口
    "install_logs",
    "install_opentelemetry",
    "get_opentelemetry_service",
    "install_monitor",
    "uninstall_monitor",
    "get_monitor_service",
]
