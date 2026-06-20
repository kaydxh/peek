#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通用取消令牌（CancellationToken）

提供统一的协作式取消能力，跨线程 / 协程 / 子进程边界传播取消信号。
设计参考 .NET CancellationToken / Go context.Context Done()。

主要类型：
    CancellationToken: 只读取消令牌，业务代码 / 第三方库通过 is_cancelled()
                       或 raise_if_cancelled() 协作式响应取消。
    CancellationTokenSource: 可写源，持有 token 的所有方调用 cancel()
                             触发已注册的回调并把 token 标记为已取消。

典型用法（跨线程长任务）::

    from peek.context.cancel import CancellationTokenSource

    cts = CancellationTokenSource()
    token = cts.token

    def worker():
        for item in stream:
            token.raise_if_cancelled()
            process(item)

    t = threading.Thread(target=worker)
    t.start()
    # 在另一处需要取消时
    cts.cancel()

与 ``threading.Event`` 的差异：
    - Event 只能 wait/clear，CancellationToken 不可解除取消（一旦取消即终态）
    - 支持注册回调（cancel 时同步触发），便于把"取消"事件广播给子进程 / IO
    - 提供 ``as_check`` 闭包，可直接传给只接受 ``Callable[[], bool]`` 参数的库
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class CancelledError(Exception):
    """协作式取消错误。

    业务可在循环 / 长 IO 调用前 ``token.raise_if_cancelled()`` 时被抛出，
    上层调用方应识别并优雅清理资源。
    """

    pass


class CancellationToken:
    """只读取消令牌。

    业务代码持有此对象用于检查 / 阻塞等待取消信号；不能调用 cancel。
    cancel 由持有 :class:`CancellationTokenSource` 的一方触发。
    """

    def __init__(
        self,
        event: threading.Event,
        callbacks: List[Callable[[], None]],
        callbacks_lock: threading.Lock,
    ) -> None:
        self._event = event
        self._callbacks = callbacks
        self._callbacks_lock = callbacks_lock

    def is_cancelled(self) -> bool:
        """是否已被取消（非阻塞）。"""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """已取消则立即抛 :class:`CancelledError`。"""
        if self._event.is_set():
            raise CancelledError("Operation cancelled")

    def wait(self, timeout: Optional[float] = None) -> bool:
        """阻塞等待取消（或超时）。

        Returns:
            True 表示在 timeout 内被取消，False 表示超时仍未取消。
        """
        return self._event.wait(timeout=timeout)

    def register(self, callback: Callable[[], None]) -> None:
        """注册取消回调；若 token 已取消会立即同步执行回调。

        典型场景：把 callback 用于关闭子进程、关闭 socket、唤醒等待线程等。
        """
        if self._event.is_set():
            self._safe_invoke(callback)
            return
        with self._callbacks_lock:
            if self._event.is_set():
                # 双重检查，避免注册期间 cancel 已发生导致回调丢失
                self._safe_invoke(callback)
                return
            self._callbacks.append(callback)

    def as_check(self) -> Callable[[], bool]:
        """返回 ``Callable[[], bool]`` 闭包，便于传给只支持回调的旧库。

        例如 promptfoo bridge 的 ``cancel_check`` 参数。
        """
        event = self._event
        return event.is_set

    @staticmethod
    def _safe_invoke(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception as exc:  # 回调失败不影响其他回调
            logger.warning("CancellationToken callback raised: %s", exc)


class CancellationTokenSource:
    """可写取消源，持有 :attr:`token` 的所有方都可以调用 :meth:`cancel`。

    线程安全：内部使用 threading.Event + lock 保护回调列表，
    cancel 是幂等操作（重复调用无副作用）。
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self._callbacks: List[Callable[[], None]] = []
        self._lock = threading.Lock()
        self._token = CancellationToken(self._event, self._callbacks, self._lock)

    @property
    def token(self) -> CancellationToken:
        """取出对应的只读 token，分发给业务代码。"""
        return self._token

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        """触发取消：

        1. 把 event set 起来
        2. 取出已注册回调并在锁外按注册顺序执行（防止回调中再注册造成死锁）

        Idempotent：重复调用只第一次触发回调，之后是 no-op。
        """
        with self._lock:
            if self._event.is_set():
                return
            self._event.set()
            pending = list(self._callbacks)
            self._callbacks.clear()

        for callback in pending:
            CancellationToken._safe_invoke(callback)


def with_cancel_check(
    token: CancellationToken,
    extra_check: Optional[Callable[[], bool]] = None,
) -> Callable[[], bool]:
    """将 token 与一个可选的额外检查函数组合成单个 ``cancel_check`` 闭包。

    场景：底层库依然可通过外部信号（如 DB 标记）触发取消时使用。
    任意一边为 True，闭包就返回 True。

    Args:
        token: 优先检查的 token
        extra_check: 兜底检查函数（如基于 DB 标记的轮询）

    Returns:
        ``Callable[[], bool]`` —— 调用方期望的 cancel check 闭包
    """
    if extra_check is None:
        return token.as_check()

    is_set = token._event.is_set  # 直接复用 Event.is_set，避免一次额外的属性访问

    def _check() -> bool:
        if is_set():
            return True
        try:
            return bool(extra_check())
        except Exception as exc:
            logger.warning("extra cancel check raised: %s", exc)
            return False

    return _check


__all__ = [
    "CancelledError",
    "CancellationToken",
    "CancellationTokenSource",
    "with_cancel_check",
]
