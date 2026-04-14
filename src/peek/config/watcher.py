#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置热更新模块

监听配置文件变更并触发回调，对应 Go 版本 viper.WatchConfig() 机制。

用法示例：
    from peek.config.watcher import ConfigWatcher

    watcher = ConfigWatcher("conf/app.yaml")
    watcher.on_change(lambda old, new: print("配置变更:", new))
    watcher.start()

    # 停止监听
    watcher.stop()
"""

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)

# 变更回调类型：(旧配置字典, 新配置字典)
OnChangeCallback = Callable[[Dict[str, Any], Dict[str, Any]], None]


class ConfigWatcher:
    """
    配置文件热更新监听器

    基于文件内容哈希检测变更（不依赖 watchdog 第三方库），
    当检测到配置文件内容变化时触发注册的回调函数。

    特性：
    - 基于文件哈希检测，跨平台兼容
    - 支持注册多个回调
    - 支持防抖（debounce），避免频繁触发
    - 线程安全
    - 优雅停止
    """

    def __init__(
        self,
        config_path: Union[str, Path],
        poll_interval: float = 2.0,
        debounce_seconds: float = 1.0,
    ):
        """
        初始化配置文件监听器

        Args:
            config_path: 配置文件路径
            poll_interval: 轮询间隔（秒），默认 2 秒
            debounce_seconds: 防抖时间（秒），默认 1 秒
        """
        self._config_path = Path(config_path)
        self._poll_interval = poll_interval
        self._debounce_seconds = debounce_seconds

        # 回调列表
        self._callbacks: List[OnChangeCallback] = []
        self._lock = threading.Lock()

        # 监听线程
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 文件状态
        self._last_hash: Optional[str] = None
        self._last_config: Dict[str, Any] = {}
        self._last_change_time: float = 0

        # 初始化当前文件哈希
        self._initialize()

    def _initialize(self) -> None:
        """初始化：读取当前配置并计算哈希"""
        if self._config_path.exists():
            self._last_hash = self._compute_hash()
            self._last_config = self._load_config()
        else:
            logger.warning("Config file does not exist: %s", self._config_path)

    def _compute_hash(self) -> Optional[str]:
        """计算配置文件的 MD5 哈希"""
        try:
            with open(self._config_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error("Failed to compute config file hash: %s", e)
            return None

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件为字典"""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("Failed to load config file: %s", e)
            return {}

    def on_change(self, callback: OnChangeCallback) -> None:
        """
        注册配置变更回调

        回调函数签名：callback(old_config: dict, new_config: dict)

        Args:
            callback: 变更回调函数
        """
        with self._lock:
            self._callbacks.append(callback)

    def remove_callback(self, callback: OnChangeCallback) -> None:
        """
        移除配置变更回调

        Args:
            callback: 要移除的回调函数
        """
        with self._lock:
            self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def start(self) -> None:
        """启动配置文件监听（后台线程）"""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("ConfigWatcher is already running")
            return

        # 确保旧的 stop event 已清除
        self._stop_event.clear()
        # 清除可能残留的已结束线程引用
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="config-watcher",
            daemon=True,
        )
        self._thread.start()
        logger.info("ConfigWatcher started, watching: %s", self._config_path)

    def stop(self) -> None:
        """停止配置文件监听"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning(
                    "ConfigWatcher thread did not stop within 5s, "
                    "it may still be running in the background"
                )
            else:
                self._thread = None
        logger.info("ConfigWatcher stopped")

    def _poll_loop(self) -> None:
        """轮询检测文件变更"""
        while not self._stop_event.is_set():
            try:
                self._check_change()
            except Exception as e:
                logger.error("ConfigWatcher change detection error: %s", e)

            self._stop_event.wait(self._poll_interval)

    def _check_change(self) -> None:
        """检测配置文件是否变更"""
        if not self._config_path.exists():
            return

        current_hash = self._compute_hash()
        if current_hash is None or current_hash == self._last_hash:
            return

        # 防抖：距离上次变更不足 debounce_seconds，跳过
        now = time.time()
        if now - self._last_change_time < self._debounce_seconds:
            return

        # 加载新配置
        new_config = self._load_config()
        old_config = self._last_config

        # 更新状态
        self._last_hash = current_hash
        self._last_config = new_config
        self._last_change_time = now

        logger.info("Config change detected: %s", self._config_path)

        # 触发回调
        with self._lock:
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback(old_config, new_config)
            except Exception as e:
                logger.error("Config change callback error: %s", e)

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._thread is not None and self._thread.is_alive()

    @property
    def current_config(self) -> Dict[str, Any]:
        """获取当前配置（副本）"""
        return dict(self._last_config)
