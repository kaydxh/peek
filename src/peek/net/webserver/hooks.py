#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
生命周期钩子

参考 Go 版本 golang 库的 hooks.go 实现
提供 PostStartHook 和 PreShutdownHook 支持
"""

import threading
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Generic, TypeVar, Union

# 钩子函数类型
PostStartHookFunc = Callable[[], Union[None, Awaitable[None]]]
PreShutdownHookFunc = Callable[[], Union[None, Awaitable[None]]]

T = TypeVar("T", PostStartHookFunc, PreShutdownHookFunc)


@dataclass
class HookEntry(Generic[T]):
    """
    钩子条目

    包含钩子函数和调试信息

    Attributes:
        hook: 钩子函数
        originating_stack: 注册时的堆栈信息（用于调试重复注册）
        done: 执行完成事件
    """

    hook: T
    originating_stack: str = ""
    done: threading.Event = field(default_factory=threading.Event)

    def wait(self, timeout: float = None) -> bool:
        """
        等待钩子执行完成

        Args:
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            是否在超时前完成
        """
        return self.done.wait(timeout)

    def is_done(self) -> bool:
        """检查钩子是否已执行完成"""
        return self.done.is_set()
