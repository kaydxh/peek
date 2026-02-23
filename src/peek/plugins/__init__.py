#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Peek Plugins - 公共插件模块

提供框架级别的公共插件功能，可被上层框架（如 tide）直接复用：
- logs: 日志安装函数式接口
- otel: OpenTelemetry 安装函数式接口
- monitor: 进程监控安装函数式接口
- vllm: vLLM 服务器管理与配置
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
from peek.plugins.mysql import install_mysql, uninstall_mysql, get_mysql_engine
from peek.plugins.redis import install_redis, uninstall_redis, get_redis_client
from peek.plugins.vllm import (
    VLLMConfig,
    VLLMServerManager,
    parse_vllm_config,
    install_vllm,
    uninstall_vllm,
    get_vllm_server_manager,
)

__all__ = [
    # 公共配置 dataclass
    "WebConfig",
    "LogConfig",
    "VLLMConfig",
    # 配置解析函数
    "parse_web_config",
    "parse_log_config",
    "parse_monitor_config",
    "parse_vllm_config",
    # 基类
    "BaseServerRunOptions",
    "BaseCompletedOptions",
    # 类
    "VLLMServerManager",
    # 函数式接口
    "install_logs",
    "install_opentelemetry",
    "get_opentelemetry_service",
    "install_monitor",
    "uninstall_monitor",
    "get_monitor_service",
    "install_mysql",
    "uninstall_mysql",
    "get_mysql_engine",
    "install_redis",
    "uninstall_redis",
    "get_redis_client",
    "install_vllm",
    "uninstall_vllm",
    "get_vllm_server_manager",
]
