# -*- coding: utf-8 -*-
"""
日志配置模块

参考 golang/pkg/logs/config.go 实现，支持：
- 多种日志格式（glog、text、json）
- 多种日志级别
- 多种输出目标（stdout、file）
- 日志文件轮转
"""

import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from peek.time.parse import parse_duration as _parse_duration_util

from .formatter import GlogFormatter, JsonFormatter, ShortFilenameFilter, TextFormatter
from .rotate import RotatingFileHandler


def _get_program_name() -> str:
    """获取程序名称

    Returns:
        str: 程序名称（不包含路径和扩展名）
    """
    if sys.argv and sys.argv[0]:
        name = Path(sys.argv[0]).stem
        # 如果是 -c 或空，使用默认名称
        if name in ("-c", "", "-"):
            return "app"
        return name
    return "app"


class LogFormatter(str, Enum):
    """日志格式枚举"""

    GLOG = "glog"
    TEXT = "text"
    JSON = "json"


class LogLevel(str, Enum):
    """日志级别枚举"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"
    CRITICAL = "critical"


class LogRedirect(str, Enum):
    """日志重定向目标枚举"""

    STDOUT = "stdout"
    FILE = "file"
    BOTH = "both"  # 同时输出到 stdout 和文件


# 日志级别映射
LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
    "critical": logging.CRITICAL,
}


class LogConfig(BaseModel):
    """日志配置

    Attributes:
        formatter: 日志格式（glog、text、json）
        level: 日志级别
        filepath: 日志文件目录
        redirect: 输出重定向目标
        max_age: 最大保留时间（秒）
        max_count: 最大保留文件数
        rotate_size: 按大小轮转（字节）
        rotate_interval: 按时间间隔轮转（秒）
        report_caller: 是否报告调用者信息
        enable_colors: 是否启用颜色输出
        prefix_name: 日志文件前缀名
        suffix_name: 日志文件后缀名
    """

    formatter: str = Field(default="glog", description="日志格式（glog、text、json）")
    level: str = Field(default="info", description="日志级别")
    filepath: str = Field(default="./log", description="日志文件目录")
    redirect: str = Field(default="stdout", description="输出重定向目标")
    max_age: float = Field(default=604800, ge=0, description="最大保留时间（秒）")
    max_count: int = Field(default=200, ge=0, description="最大保留文件数")
    rotate_size: int = Field(default=104857600, ge=0, description="按大小轮转（字节）")
    rotate_interval: float = Field(
        default=3600, ge=0, description="按时间间隔轮转（秒）"
    )
    report_caller: bool = Field(default=True, description="是否报告调用者信息")
    enable_colors: bool = Field(default=False, description="是否启用颜色输出")
    prefix_name: str = Field(default="", description="日志文件前缀名")
    suffix_name: str = Field(default=".log", description="日志文件后缀名")

    @field_validator("max_age", "rotate_interval", mode="before")
    @classmethod
    def parse_duration_field(cls, v):
        """解析时间字符串，复用 peek.time.parse.parse_duration"""
        return _parse_duration_util(v)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogConfig":
        """从字典创建配置

        Args:
            data: 配置字典

        Returns:
            LogConfig: 日志配置实例
        """
        return cls.model_validate(data)


def install_logs(config: Optional[LogConfig] = None) -> None:
    """安装日志配置

    参考 golang logs.Config.install() 实现。

    Args:
        config: 日志配置，如果为 None 则使用默认配置
    """
    if config is None:
        config = LogConfig()

    # 获取日志级别
    level = LEVEL_MAP.get(config.level.lower(), logging.INFO)

    # 创建格式化器
    if config.formatter.lower() == "glog":
        formatter = GlogFormatter(
            enable_colors=config.enable_colors,
            report_caller=config.report_caller,
        )
    elif config.formatter.lower() == "json":
        formatter = JsonFormatter(report_caller=config.report_caller)
    else:
        formatter = TextFormatter(report_caller=config.report_caller)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有处理器
    root_logger.handlers.clear()

    redirect = config.redirect.lower()

    # 添加控制台处理器
    if redirect in ("stdout", "", "both"):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        # 添加短文件名过滤器，让 %(filename)s 显示 "目录/文件名" 格式
        console_handler.addFilter(ShortFilenameFilter())
        root_logger.addHandler(console_handler)

    # 添加文件处理器
    if redirect in ("file", "both"):
        # 确保日志目录存在
        log_path = Path(config.filepath)
        log_path.mkdir(parents=True, exist_ok=True)

        # 生成默认前缀名
        prefix_name = config.prefix_name
        if not prefix_name:
            prog_name = _get_program_name()
            prefix_name = f"{prog_name}."

        # 创建轮转文件处理器
        file_handler = RotatingFileHandler(
            filedir=str(log_path),
            prefix_name=prefix_name,
            suffix_name=config.suffix_name,
            max_age=config.max_age,
            max_count=config.max_count,
            rotate_size=config.rotate_size,
            rotate_interval=config.rotate_interval,
            level=level,
        )
        file_handler.setFormatter(formatter)
        # 添加短文件名过滤器
        file_handler.addFilter(ShortFilenameFilter())
        root_logger.addHandler(file_handler)

    # 输出安装信息
    logger = logging.getLogger(__name__)
    logger.info(
        "日志初始化完成: level=%s, formatter=%s, " "redirect=%s, filepath=%s",
        config.level,
        config.formatter,
        config.redirect,
        config.filepath,
    )


def get_logger(
    name: Optional[str] = None, request_id: Optional[str] = None
) -> logging.Logger:
    """获取日志记录器

    Args:
        name: 日志记录器名称，如果为 None 则使用调用者模块名
        request_id: 请求 ID，用于链路追踪

    Returns:
        logging.Logger: 日志记录器
    """
    logger = logging.getLogger(name)

    if request_id:
        # 创建一个带 request_id 的适配器
        return LoggerAdapter(logger, {"request_id": request_id})

    return logger


class LoggerAdapter(logging.LoggerAdapter):
    """带额外字段的日志适配器"""

    def process(self, msg, kwargs):
        """处理日志消息

        Args:
            msg: 日志消息
            kwargs: 关键字参数

        Returns:
            tuple: 处理后的消息和参数
        """
        # 添加 request_id 到消息前
        request_id = self.extra.get("request_id", "")
        if request_id:
            msg = f"[request_id={request_id}] {msg}"
        return msg, kwargs
