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
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from .formatter import GlogFormatter, JsonFormatter, TextFormatter
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


@dataclass
class LogConfig:
    """日志配置
    
    Attributes:
        formatter: 日志格式（glog、text、json）
        level: 日志级别
        filepath: 日志文件目录
        redirect: 输出重定向目标
        max_age: 最大保留时间（秒或带单位字符串，如 "604800s"）
        max_count: 最大保留文件数
        rotate_size: 按大小轮转（字节）
        rotate_interval: 按时间间隔轮转（秒或带单位字符串，如 "3600s"）
        report_caller: 是否报告调用者信息
        enable_colors: 是否启用颜色输出
        prefix_name: 日志文件前缀名
        suffix_name: 日志文件后缀名
    """
    formatter: str = "glog"
    level: str = "info"
    filepath: str = "./log"
    redirect: str = "stdout"
    max_age: Any = "604800s"  # 7 days
    max_count: int = 200
    rotate_size: int = 104857600  # 100MB
    rotate_interval: Any = "3600s"  # 1 hour
    report_caller: bool = True
    enable_colors: bool = False
    prefix_name: str = ""
    suffix_name: str = ".log"
    
    def __post_init__(self):
        """后处理，转换时间单位"""
        # 转换 max_age
        if isinstance(self.max_age, str):
            self.max_age = self._parse_duration(self.max_age)
        
        # 转换 rotate_interval
        if isinstance(self.rotate_interval, str):
            self.rotate_interval = self._parse_duration(self.rotate_interval)
    
    @staticmethod
    def _parse_duration(duration_str: str) -> float:
        """解析时间字符串
        
        支持格式：
        - "3600" -> 3600 秒
        - "3600s" -> 3600 秒
        - "60m" -> 3600 秒
        - "1h" -> 3600 秒
        
        Args:
            duration_str: 时间字符串
            
        Returns:
            float: 秒数
        """
        if not duration_str:
            return 0.0
        
        duration_str = duration_str.strip().lower()
        
        # 纯数字
        if duration_str.isdigit():
            return float(duration_str)
        
        # 带单位
        multipliers = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
        }
        
        for suffix, multiplier in multipliers.items():
            if duration_str.endswith(suffix):
                try:
                    value = float(duration_str[:-1])
                    return value * multiplier
                except ValueError:
                    pass
        
        # 默认按秒处理
        try:
            return float(duration_str)
        except ValueError:
            return 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogConfig":
        """从字典创建配置
        
        Args:
            data: 配置字典
            
        Returns:
            LogConfig: 日志配置实例
        """
        return cls(
            formatter=data.get("formatter", "glog"),
            level=data.get("level", "info"),
            filepath=data.get("filepath", "./log"),
            redirect=data.get("redirect", "stdout"),
            max_age=data.get("max_age", "604800s"),
            max_count=data.get("max_count", 200),
            rotate_size=data.get("rotate_size", 104857600),
            rotate_interval=data.get("rotate_interval", "3600s"),
            report_caller=data.get("report_caller", True),
            enable_colors=data.get("enable_colors", False),
            prefix_name=data.get("prefix_name", ""),
            suffix_name=data.get("suffix_name", ".log"),
        )


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
        root_logger.addHandler(file_handler)
    
    # 输出安装信息
    logger = logging.getLogger(__name__)
    logger.info(
        f"日志初始化完成: level={config.level}, formatter={config.formatter}, "
        f"redirect={config.redirect}, filepath={config.filepath}"
    )


def get_logger(name: Optional[str] = None, request_id: Optional[str] = None) -> logging.Logger:
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
