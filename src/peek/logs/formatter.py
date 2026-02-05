# -*- coding: utf-8 -*-
"""
Glog 格式化器

参考 golang/pkg/logs/logrus/glog_formatter.go 实现。

Glog 格式：
[IWEF]yyyymmdd hh:mm:ss.uuuuuu threadid file:line] msg

示例：
[INFO] [20210917 23:00:00.123456] [12345] [main.py:10](main) Hello World
"""

import logging
import os
import sys
import threading
from datetime import datetime
from typing import Optional


# 获取进程 ID
_PID = os.getpid()


class GlogFormatter(logging.Formatter):
    """Google Log 格式化器
    
    输出格式：
    [LEVEL] [DATETIME] [PID/TID] [FILE:LINE](FUNC) MESSAGE key=value ...
    
    示例：
    [INFO] [20210917 23:00:00.123456] [12345] [main.py:10](main) Hello World request_id=abc123
    """
    
    # 日志级别缩写映射
    LEVEL_MAP = {
        logging.DEBUG: "DEBU",
        logging.INFO: "INFO",
        logging.WARNING: "WARN",
        logging.ERROR: "ERRO",
        logging.CRITICAL: "FATA",
    }
    
    # 颜色代码
    COLORS = {
        logging.DEBUG: "\033[37m",     # 灰色
        logging.INFO: "\033[36m",      # 青色
        logging.WARNING: "\033[33m",   # 黄色
        logging.ERROR: "\033[31m",     # 红色
        logging.CRITICAL: "\033[35m",  # 紫色
    }
    RESET = "\033[0m"
    
    def __init__(
        self,
        datefmt: str = "%Y%m%d %H:%M:%S",
        enable_colors: bool = False,
        enable_thread_id: bool = False,
        disable_timestamp: bool = False,
        full_timestamp: bool = True,
        report_caller: bool = True,
    ):
        """初始化格式化器
        
        Args:
            datefmt: 日期格式
            enable_colors: 是否启用颜色
            enable_thread_id: 是否显示线程 ID（而不是进程 ID）
            disable_timestamp: 是否禁用时间戳
            full_timestamp: 是否显示完整时间戳
            report_caller: 是否报告调用者信息
        """
        super().__init__()
        self.datefmt = datefmt
        self.enable_colors = enable_colors
        self.enable_thread_id = enable_thread_id
        self.disable_timestamp = disable_timestamp
        self.full_timestamp = full_timestamp
        self.report_caller = report_caller
        
        # 检测是否为终端
        self._is_terminal = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    
    def _get_level_text(self, level: int) -> str:
        """获取级别文本
        
        Args:
            level: 日志级别
            
        Returns:
            str: 级别缩写文本
        """
        return self.LEVEL_MAP.get(level, "UNKN")
    
    def _colorize(self, text: str, level: int) -> str:
        """添加颜色
        
        Args:
            text: 文本
            level: 日志级别
            
        Returns:
            str: 带颜色的文本
        """
        if not self.enable_colors or not self._is_terminal:
            return text
        
        color = self.COLORS.get(level, "")
        if color:
            return f"{color}{text}{self.RESET}"
        return text
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录
        
        Args:
            record: 日志记录
            
        Returns:
            str: 格式化后的日志文本
        """
        # 构建各部分
        parts = []
        
        # 1. 级别
        level_text = self._get_level_text(record.levelno)
        level_part = f"[{level_text}]"
        level_part = self._colorize(level_part, record.levelno)
        parts.append(level_part)
        
        # 2. 时间戳
        if not self.disable_timestamp:
            if self.full_timestamp:
                # 完整时间戳，包含微秒
                dt = datetime.fromtimestamp(record.created)
                timestamp = dt.strftime(self.datefmt)
                # 添加微秒
                microseconds = int((record.created - int(record.created)) * 1000000)
                timestamp = f"{timestamp}.{microseconds:06d}"
            else:
                timestamp = datetime.fromtimestamp(record.created).strftime(self.datefmt)
            parts.append(f"[{timestamp}]")
        
        # 3. 进程/线程 ID
        if self.enable_thread_id:
            tid = threading.current_thread().ident
            parts.append(f"[{tid}]")
        else:
            parts.append(f"[{_PID}]")
        
        # 4. 文件:行号 和函数名
        if self.report_caller:
            # 获取简短的文件名
            filename = os.path.basename(record.pathname)
            lineno = record.lineno
            funcname = record.funcName
            parts.append(f"[{filename}:{lineno}]({funcname})")
        
        # 5. 消息
        message = record.getMessage()
        parts.append(message)
        
        # 6. 额外字段（如果有）
        if hasattr(record, "extra_fields") and record.extra_fields:
            for key, value in record.extra_fields.items():
                parts.append(f"{key}={value}")
        
        return " ".join(parts)


class TextFormatter(logging.Formatter):
    """文本格式化器
    
    输出格式：
    DATETIME - NAME - LEVEL - MESSAGE
    """
    
    def __init__(
        self,
        datefmt: str = "%Y-%m-%d %H:%M:%S",
        report_caller: bool = True,
    ):
        """初始化
        
        Args:
            datefmt: 日期格式
            report_caller: 是否报告调用者
        """
        if report_caller:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        else:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        super().__init__(fmt=fmt, datefmt=datefmt)


class JsonFormatter(logging.Formatter):
    """JSON 格式化器
    
    输出 JSON 格式的日志
    """
    
    def __init__(self, report_caller: bool = True):
        """初始化
        
        Args:
            report_caller: 是否报告调用者
        """
        super().__init__()
        self.report_caller = report_caller
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录
        
        Args:
            record: 日志记录
            
        Returns:
            str: JSON 格式的日志
        """
        import json
        
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        
        if self.report_caller:
            log_data["file"] = record.pathname
            log_data["line"] = record.lineno
            log_data["function"] = record.funcName
        
        # 添加额外字段
        if hasattr(record, "extra_fields") and record.extra_fields:
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data, ensure_ascii=False)
