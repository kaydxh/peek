#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
后台任务注册中心（BackgroundTaskRegistry）

集中管理跨线程 / 跨协程的长任务（如评测任务、批处理任务等），
配合 :class:`peek.context.cancel.CancellationTokenSource` 提供：

- ``register(key, cts)``: 任务启动时注册，进程优雅关停时统一收割
- ``cancel(key)``: 单点取消（如用户在 UI 点取消按钮）
- ``cancel_all(reason)``: 进程接到 SIGTERM / SIGINT 时广播取消所有正在跑的任务
- ``unregister(key)``: 任务自然结束时清理，避免内存泄漏
- ``wait_all_finished(timeout)``: 关停期等待任务自己优雅退出后再返回

设计原则：
    - 注册中心只持有 ``CancellationTokenSource``，不持有线程 / 协程对象本身，
      上层业务可自由选择 Thread / asyncio Task / Celery Task 实现
    - 线程安全；register / unregister 频繁调用，使用细粒度锁
    - cancel 是协作式：调用 ``cts.cancel()`` 后，业务侧 token 检查点会自然退出，
      registry 不强制 kill 线程

典型用法（与 peek shutdown hook 配合）::

    from peek.context.task_registry import get_task_registry
    from peek.context.cancel import CancellationTokenSource

    # 业务侧：启动任务
    cts = CancellationTokenSource()
    registry = get_task_registry()
    registry.register(f"eval-{run_id}", cts)
    try:
        do_long_work(cts.token)
    finally:
        registry.unregister(f"eval-{run_id}")

    # 服务启动时：注册到 peek 的 pre_shutdown_hook
    web_server.add_pre_shutdown_hook(
        "background-tasks-cancel",
        lambda: get_task_registry().cancel_all_and_wait(timeout=30),
    )
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional

from peek.context.cancel import CancellationTokenSource

logger = logging.getLogger(__name__)


class BackgroundTaskRegistry:
    """进程级后台任务注册中心。"""

    def __init__(self) -> None:
        self._tasks: Dict[str, CancellationTokenSource] = {}
        self._lock = threading.Lock()
        # 一旦设置为 True，新的 register 会立即收到一个已 cancelled 的 token，
        # 让进程关停期间新派发的任务直接快速失败而非进入死循环
        self._shutting_down = False

    # ------------------------------------------------------------------
    # 注册 / 注销
    # ------------------------------------------------------------------

    def register(self, key: str, cts: CancellationTokenSource) -> None:
        """注册一个后台任务的 :class:`CancellationTokenSource`。

        若已存在同 key 任务，旧任务会先被 cancel 再被替换（典型场景：
        同一 run_id 重复 dispatch，旧线程应让位给新线程）。

        若 registry 已进入 shutdown 态，立即对新 cts 调用 cancel，避免新任务做无用功。
        """
        with self._lock:
            old = self._tasks.pop(key, None)
            self._tasks[key] = cts
            shutting_down = self._shutting_down

        if old is not None and not old.is_cancelled:
            # 旧 token 在锁外取消，避免回调 → register 形成循环锁竞争
            old.cancel()
            logger.info("BackgroundTaskRegistry: replaced and cancelled old task key=%s", key)

        if shutting_down:
            cts.cancel()

    def unregister(self, key: str) -> Optional[CancellationTokenSource]:
        """任务自然结束时调用，从 registry 清掉。"""
        with self._lock:
            return self._tasks.pop(key, None)

    # ------------------------------------------------------------------
    # 取消
    # ------------------------------------------------------------------

    def cancel(self, key: str) -> bool:
        """取消单个任务；任务不存在时返回 False。"""
        with self._lock:
            cts = self._tasks.get(key)
        if cts is None:
            return False
        cts.cancel()
        return True

    def cancel_all(self, reason: str = "shutdown") -> int:
        """广播取消所有任务，返回被触发的任务数。

        本方法**不删除注册项**——业务侧 unregister 调用是自然清理路径，
        registry 只负责通知；如果业务侧因取消信号已经退出，会自己 unregister。
        """
        with self._lock:
            self._shutting_down = True
            pending = list(self._tasks.items())

        triggered = 0
        for key, cts in pending:
            if not cts.is_cancelled:
                logger.info("BackgroundTaskRegistry: cancel task key=%s reason=%s", key, reason)
                cts.cancel()
                triggered += 1
        return triggered

    def cancel_all_and_wait(self, timeout: float = 30.0, reason: str = "shutdown") -> int:
        """广播取消并阻塞等待所有任务自行 unregister，返回未在 timeout 内退出的任务数。

        典型用作 peek ``add_pre_shutdown_hook`` 的回调：在进程退出前先把所有
        长任务温和地终止，留出最多 ``timeout`` 秒时间给业务侧清理。

        Args:
            timeout: 等待任务自行结束的最长秒数
            reason: 取消原因（仅记录日志）

        Returns:
            未在 timeout 内退出的任务数。0 表示所有任务都正常关停。
        """
        triggered = self.cancel_all(reason=reason)
        if triggered == 0:
            return 0

        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            with self._lock:
                if not self._tasks:
                    return 0
            time.sleep(0.1)

        with self._lock:
            remaining = list(self._tasks.keys())
        if remaining:
            logger.warning(
                "BackgroundTaskRegistry: %d task(s) did not exit in %.1fs: %s",
                len(remaining), timeout, remaining,
            )
        return len(remaining)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def keys(self) -> List[str]:
        """返回当前已注册的所有 key（快照）。"""
        with self._lock:
            return list(self._tasks.keys())

    def size(self) -> int:
        with self._lock:
            return len(self._tasks)

    def is_shutting_down(self) -> bool:
        with self._lock:
            return self._shutting_down

    # 仅供测试使用：重置 shutdown 标记
    def _reset_for_test(self) -> None:
        with self._lock:
            self._shutting_down = False
            self._tasks.clear()


# 进程级单例（lazy）
_default_registry: Optional[BackgroundTaskRegistry] = None
_default_registry_lock = threading.Lock()


def get_task_registry() -> BackgroundTaskRegistry:
    """获取进程级 BackgroundTaskRegistry 单例。"""
    global _default_registry
    if _default_registry is None:
        with _default_registry_lock:
            if _default_registry is None:
                _default_registry = BackgroundTaskRegistry()
    return _default_registry


__all__ = [
    "BackgroundTaskRegistry",
    "get_task_registry",
]
