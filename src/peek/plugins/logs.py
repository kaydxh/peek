#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共日志安装模块（函数式接口）

提供 install_logs() 函数，将 LogConfig 转换为 peek.logs.LogConfig 并安装日志系统。
上层框架（如 tide）可直接调用此函数，无需重复实现日志安装逻辑。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def install_logs(config):
    """安装日志配置。

    使用 peek.logs 库来初始化日志系统。

    Args:
        config: 日志配置（LogConfig 实例），如果为 None 则使用默认配置
    """
    if config is None:
        from peek.plugins.base_options import LogConfig
        config = LogConfig()

    try:
        # 使用 peek 的日志库
        from peek.logs import LogConfig as PeekLogConfig, install_logs as peek_install_logs

        # 转换为 peek 的日志配置
        peek_config = PeekLogConfig(
            formatter=config.formatter,
            level=config.level,
            filepath=config.filepath,
            redirect=config.redirect,
            max_age=config.max_age,
            max_count=config.max_count,
            rotate_size=config.rotate_size,
            rotate_interval=config.rotate_interval,
            report_caller=config.report_caller,
        )

        # 安装日志
        peek_install_logs(peek_config)

    except ImportError:
        # 如果 peek.logs 内部模块不可用，使用内置的简单实现
        logger.warning("peek.logs 库不可用，使用内置日志实现")
        _install_logs_fallback(config)


def _install_logs_fallback(config):
    """内置日志实现（当 peek.logs 不可用时使用）

    Args:
        config: 日志配置
    """
    import sys
    from logging.handlers import RotatingFileHandler
    from pathlib import Path

    # 设置日志级别
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "fatal": logging.CRITICAL,
    }
    level = level_map.get(config.level.lower(), logging.DEBUG)

    # 创建格式化器
    if config.formatter == "glog":
        # Google log 格式
        fmt = "[%(levelname).4s] [%(asctime)s] [%(process)d] [%(filename)s:%(lineno)d](%(funcName)s) %(message)s"
        datefmt = "%Y%m%d %H:%M:%S"
    else:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有处理器
    root_logger.handlers.clear()

    redirect = config.redirect.lower() if config.redirect else "stdout"

    # 添加控制台处理器
    if redirect in ("stdout", "", "both"):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 添加文件处理器
    if redirect in ("file", "both"):
        log_path = Path(config.filepath)
        log_path.mkdir(parents=True, exist_ok=True)

        # 生成日志文件名
        prog_name = Path(sys.argv[0]).stem if sys.argv else "app"
        log_file = log_path / f"{prog_name}.log"

        # 轮转文件处理器
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=config.rotate_size,
            backupCount=config.max_count,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logger.info(f"日志初始化完成，级别: {config.level}, 格式: {config.formatter}, 输出: {config.redirect}")
