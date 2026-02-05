# -*- coding: utf-8 -*-
"""
日志轮转模块

参考 golang/pkg/file-rotate 实现，支持：
- 按文件大小轮转
- 按时间间隔轮转
- 自动清理过期日志文件
- 序列文件命名（foo.log, foo.log.1, foo.log.2, ...）
"""

import glob
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class RotatingFileWriter:
    """日志文件轮转写入器
    
    参考 golang RotateFiler 实现，支持按大小和时间间隔轮转日志文件。
    
    文件命名格式：
    - 基础名: {prefix}{time_layout}{suffix}
    - 序列名: {prefix}{time_layout}{suffix}.{seq}
    
    示例：
    - logs.20210917230000.log
    - logs.20210917230000.log.1
    - logs.20210917230000.log.2
    """
    
    # 日志目录
    filedir: str
    # 文件前缀名
    prefix_name: str = ""
    # 文件后缀名
    suffix_name: str = ".log"
    # 时间格式（用于轮转间隔）
    file_time_layout: str = "%Y%m%d%H%M%S"
    # 最大保留时间（秒），0 表示无限制
    max_age: float = 72 * 3600  # 72 hours
    # 最大保留文件数，0 表示无限制
    max_count: int = 72
    # 按大小轮转（字节），0 表示不按大小轮转
    rotate_size: int = 100 * 1024 * 1024  # 100MB
    # 按时间间隔轮转（秒），0 表示不按时间轮转
    rotate_interval: float = 3600  # 1 hour
    # 符号链接路径
    link_path: str = ""
    # 轮转回调函数
    rotate_callback: Optional[Callable[[str], None]] = None
    
    # 内部状态
    _file: Optional[object] = field(default=None, init=False, repr=False)
    _cur_filepath: str = field(default="", init=False, repr=False)
    _seq: int = field(default=0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _last_rotate_time: float = field(default=0.0, init=False, repr=False)
    
    def __post_init__(self):
        """初始化"""
        # 确保日志目录存在
        Path(self.filedir).mkdir(parents=True, exist_ok=True)
        
        # 设置默认符号链接路径
        if not self.link_path:
            prog_name = self._get_program_name()
            self.link_path = f"{prog_name}.log"
        
        # 如果有时间间隔轮转但没有时间格式，使用默认格式
        if self.rotate_interval > 0 and not self.file_time_layout:
            self.file_time_layout = "%Y%m%d%H%M%S"
    
    @staticmethod
    def _get_program_name() -> str:
        """获取程序名称
        
        Returns:
            str: 程序名称（不包含路径和扩展名）
        """
        import sys
        if sys.argv and sys.argv[0]:
            name = Path(sys.argv[0]).stem
            # 如果是 -c 或空，使用默认名称
            if name in ("-c", "", "-"):
                return "app"
            return name
        return "app"
    
    def write(self, data: bytes) -> int:
        """写入数据
        
        Args:
            data: 要写入的字节数据
            
        Returns:
            int: 写入的字节数
        """
        with self._lock:
            return self._write_nolock(data)
    
    def _write_nolock(self, data: bytes) -> int:
        """内部写入方法（不加锁）"""
        writer = self._get_writer_nolock(len(data))
        if writer is None:
            return 0
        
        n = writer.write(data)
        writer.flush()  # 确保立即写入
        return n
    
    def _generate_rotate_filename(self) -> str:
        """生成轮转文件名的时间部分"""
        if self.rotate_interval > 0:
            now = datetime.now()
            # 截断到轮转间隔
            interval_seconds = int(self.rotate_interval)
            timestamp = int(now.timestamp())
            truncated_timestamp = (timestamp // interval_seconds) * interval_seconds
            truncated_time = datetime.fromtimestamp(truncated_timestamp)
            return truncated_time.strftime(self.file_time_layout)
        return ""
    
    def _get_writer_nolock(self, length: int):
        """获取写入器（不加锁）
        
        Args:
            length: 准备写入的数据长度
            
        Returns:
            文件对象
        """
        basename = self._generate_rotate_filename()
        filename = f"{self.prefix_name}{basename}{self.suffix_name}"
        if not filename:
            filename = "default.log"
        
        # 完整文件路径
        filepath = os.path.join(self.filedir, filename)
        glob_path = os.path.join(self.filedir, self.prefix_name)
        
        # 获取当前序列文件
        if not self._cur_filepath:
            self._cur_filepath = self._get_cur_seq_filename(glob_path)
            self._seq = self._extract_seq(self._cur_filepath)
        
        # 如果当前文件路径与新的轮转时间不同，需要重置
        if filename not in self._cur_filepath:
            self._cur_filepath = filepath
            self._seq = 0
        
        rotated = False
        
        # 检查文件状态
        try:
            stat_info = os.stat(self._cur_filepath)
            file_size = stat_info.st_size
        except FileNotFoundError:
            # 文件不存在，需要创建
            rotated = True
            file_size = 0
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return None
        
        # 按大小轮转
        if not rotated and self.rotate_size > 0 and (file_size + length) > self.rotate_size:
            new_filepath = self._generate_next_seq_filename(filepath)
            if new_filepath:
                self._cur_filepath = new_filepath
                rotated = True
        
        # 创建或打开文件
        if self._file is None or rotated:
            try:
                # 关闭旧文件
                if self._file is not None:
                    old_path = self._file.name
                    self._file.close()
                    # 轮转回调
                    if self.rotate_callback:
                        try:
                            self.rotate_callback(old_path)
                        except Exception as e:
                            logger.error(f"Rotate callback error: {e}")
                
                # 打开新文件
                self._file = open(self._cur_filepath, "ab")
                self._seq = self._extract_seq(self._cur_filepath)
                
                # 创建符号链接
                self._create_symlink(self._cur_filepath, self.link_path)
                
                # 清理旧文件
                self._cleanup_old_files(glob_path)
                
            except Exception as e:
                logger.error(f"Failed to create file {self._cur_filepath}: {e}")
                return None
        
        return self._file
    
    def _generate_next_seq_filename(self, filepath: str) -> Optional[str]:
        """生成下一个序列文件名
        
        Args:
            filepath: 基础文件路径
            
        Returns:
            str: 新的文件路径，如果失败返回 None
        """
        seq = self._seq
        
        while True:
            if seq == 0:
                new_filepath = filepath
            else:
                new_filepath = f"{filepath}.{seq}"
            
            if not os.path.exists(new_filepath):
                self._seq = seq
                return new_filepath
            
            seq += 1
            
            # 防止无限循环
            if seq > 10000:
                logger.error("Too many sequence files")
                return None
    
    def _get_cur_seq_filename(self, glob_path: str) -> str:
        """获取当前序列文件名
        
        Args:
            glob_path: glob 匹配路径
            
        Returns:
            str: 当前文件路径
        """
        glob_pattern = f"{glob_path}*"
        matches = glob.glob(glob_pattern)
        
        if not matches:
            return glob_path
        
        # 按修改时间排序，取最新的
        matches.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0)
        return matches[-1]
    
    def _extract_seq(self, filepath: str) -> int:
        """从文件路径中提取序列号
        
        Args:
            filepath: 文件路径
            
        Returns:
            int: 序列号，如果没有则返回 0
        """
        if not filepath:
            return 0
        
        # 尝试从扩展名提取序列号
        ext = os.path.splitext(filepath)[1]
        if ext and ext.startswith("."):
            try:
                return int(ext[1:])
            except ValueError:
                pass
        
        # 尝试从路径中匹配 .数字 模式
        match = re.search(r"\.(\d+)$", filepath)
        if match:
            return int(match.group(1))
        
        return 0
    
    def _create_symlink(self, target: str, link_name: str):
        """创建符号链接
        
        Args:
            target: 目标文件路径
            link_name: 链接名称
        """
        if not link_name:
            return
        
        try:
            link_path = os.path.join(os.path.dirname(target), link_name)
            
            # 删除已存在的链接
            if os.path.islink(link_path):
                os.unlink(link_path)
            elif os.path.exists(link_path):
                os.remove(link_path)
            
            # 创建相对路径的符号链接
            os.symlink(os.path.basename(target), link_path)
        except Exception as e:
            logger.debug(f"Failed to create symlink: {e}")
    
    def _cleanup_old_files(self, glob_path: str):
        """清理过期的日志文件
        
        Args:
            glob_path: glob 匹配路径
        """
        glob_pattern = f"{glob_path}*"
        matches = glob.glob(glob_pattern)
        
        if not matches:
            return
        
        now = time.time()
        files_to_delete = []
        
        # 按修改时间排序
        matches_with_time = []
        for filepath in matches:
            try:
                mtime = os.path.getmtime(filepath)
                matches_with_time.append((filepath, mtime))
            except Exception:
                continue
        
        matches_with_time.sort(key=lambda x: x[1])
        
        # 按时间清理
        if self.max_age > 0:
            cutoff_time = now - self.max_age
            for filepath, mtime in matches_with_time:
                if mtime < cutoff_time and filepath != self._cur_filepath:
                    files_to_delete.append(filepath)
        
        # 按数量清理
        if self.max_count > 0:
            remaining = [
                (f, t) for f, t in matches_with_time 
                if f not in files_to_delete and f != self._cur_filepath
            ]
            if len(remaining) > self.max_count:
                # 删除最旧的文件
                excess = len(remaining) - self.max_count
                for filepath, _ in remaining[:excess]:
                    if filepath not in files_to_delete:
                        files_to_delete.append(filepath)
        
        # 执行删除
        for filepath in files_to_delete:
            try:
                os.remove(filepath)
                logger.debug(f"Deleted old log file: {filepath}")
            except Exception as e:
                logger.debug(f"Failed to delete {filepath}: {e}")
    
    def close(self):
        """关闭文件"""
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None
    
    def __del__(self):
        """析构函数"""
        self.close()


class RotatingFileHandler(logging.Handler):
    """基于 RotatingFileWriter 的日志处理器
    
    集成到 Python logging 模块中使用。
    """
    
    def __init__(
        self,
        filedir: str,
        prefix_name: str = "",
        suffix_name: str = ".log",
        max_age: float = 72 * 3600,
        max_count: int = 72,
        rotate_size: int = 100 * 1024 * 1024,
        rotate_interval: float = 3600,
        level: int = logging.NOTSET,
    ):
        """初始化
        
        Args:
            filedir: 日志目录
            prefix_name: 文件前缀名
            suffix_name: 文件后缀名
            max_age: 最大保留时间（秒）
            max_count: 最大保留文件数
            rotate_size: 按大小轮转（字节）
            rotate_interval: 按时间间隔轮转（秒）
            level: 日志级别
        """
        super().__init__(level)
        
        self.writer = RotatingFileWriter(
            filedir=filedir,
            prefix_name=prefix_name,
            suffix_name=suffix_name,
            max_age=max_age,
            max_count=max_count,
            rotate_size=rotate_size,
            rotate_interval=rotate_interval,
        )
    
    def emit(self, record: logging.LogRecord):
        """发射日志记录
        
        Args:
            record: 日志记录
        """
        try:
            msg = self.format(record)
            self.writer.write((msg + "\n").encode("utf-8"))
        except Exception:
            self.handleError(record)
    
    def close(self):
        """关闭处理器"""
        self.writer.close()
        super().close()
