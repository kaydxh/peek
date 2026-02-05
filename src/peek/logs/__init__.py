# -*- coding: utf-8 -*-
"""
Peek Logs - 日志库

参考 golang/pkg/logs 实现的 Python 日志库，支持：
- 多种日志格式（glog、text、json）
- 日志文件轮转（按大小、按时间间隔）
- 自动清理过期日志文件
- 标准输出和文件输出
"""

from .config import (
    LogConfig,
    LogFormatter,
    LogLevel,
    LogRedirect,
    install_logs,
    get_logger,
)
from .rotate import RotatingFileWriter
from .formatter import GlogFormatter

__all__ = [
    # 配置类
    "LogConfig",
    "LogFormatter",
    "LogLevel",
    "LogRedirect",
    # 核心函数
    "install_logs",
    "get_logger",
    # 轮转写入器
    "RotatingFileWriter",
    # 格式化器
    "GlogFormatter",
]
