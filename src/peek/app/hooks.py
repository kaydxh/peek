#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hooks - 钩子函数管理

提供 PostStart / PreShutdown 钩子的注册与执行。
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class HookType(Enum):
    """钩子类型"""

    POST_START = "post_start"
    PRE_SHUTDOWN = "pre_shutdown"


# 钩子函数类型
HookFunc = Union[Callable[[], None], Callable[[], Any]]
AsyncHookFunc = Union[Callable[[], None], Callable[[], Any]]
PostStartHook = HookFunc
PreShutdownHook = HookFunc


@dataclass
class HookEntry:
    """
    钩子条目

    Attributes:
        name: 钩子名称
        func: 钩子函数
        priority: 优先级（越大越先执行）
        hook_type: 钩子类型
    """

    name: str
    func: Union[HookFunc, AsyncHookFunc]
    priority: int = 0
    hook_type: HookType = HookType.POST_START


class HookManager:
    """
    钩子管理器

    管理钩子的注册和执行
    """

    def __init__(self):
        self._hooks: Dict[HookType, List[HookEntry]] = {
            HookType.POST_START: [],
            HookType.PRE_SHUTDOWN: [],
        }

    def register(
        self,
        hook_type: HookType,
        name: str,
        func: Union[HookFunc, AsyncHookFunc],
        priority: int = 0,
    ) -> "HookManager":
        """
        注册钩子

        Args:
            hook_type: 钩子类型
            name: 钩子名称
            func: 钩子函数
            priority: 优先级

        Returns:
            self
        """
        entry = HookEntry(
            name=name,
            func=func,
            priority=priority,
            hook_type=hook_type,
        )
        self._hooks[hook_type].append(entry)
        logger.debug("Hook '%s' registered for %s", name, hook_type.value)
        return self

    def register_post_start(
        self,
        name: str,
        func: Union[HookFunc, AsyncHookFunc],
        priority: int = 0,
    ) -> "HookManager":
        """注册启动后钩子"""
        return self.register(HookType.POST_START, name, func, priority)

    def register_pre_shutdown(
        self,
        name: str,
        func: Union[HookFunc, AsyncHookFunc],
        priority: int = 0,
    ) -> "HookManager":
        """注册关闭前钩子"""
        return self.register(HookType.PRE_SHUTDOWN, name, func, priority)

    async def run_hooks(self, hook_type: HookType) -> None:
        """
        执行指定类型的所有钩子

        Args:
            hook_type: 钩子类型
        """
        hooks = self._hooks.get(hook_type, [])
        if not hooks:
            return

        # 按优先级排序（从高到低）
        sorted_hooks = sorted(hooks, key=lambda h: h.priority, reverse=True)

        for hook in sorted_hooks:
            try:
                logger.debug("Running hook '%s' (%s)", hook.name, hook_type.value)

                if asyncio.iscoroutinefunction(hook.func):
                    await hook.func()
                else:
                    hook.func()

                logger.debug("Hook '%s' completed", hook.name)
            except Exception as e:
                logger.error("Hook '%s' failed: %s", hook.name, e)
                # 根据钩子类型决定是否继续
                if hook_type == HookType.POST_START:
                    raise

    async def run_post_start_hooks(self) -> None:
        """执行启动后钩子"""
        await self.run_hooks(HookType.POST_START)

    async def run_pre_shutdown_hooks(self) -> None:
        """执行关闭前钩子"""
        await self.run_hooks(HookType.PRE_SHUTDOWN)

    def get_hooks(self, hook_type: HookType) -> List[HookEntry]:
        """获取指定类型的所有钩子"""
        return self._hooks.get(hook_type, []).copy()

    def clear(self, hook_type: Optional[HookType] = None) -> None:
        """
        清除钩子

        Args:
            hook_type: 钩子类型，如果为 None 则清除所有
        """
        if hook_type:
            self._hooks[hook_type] = []
        else:
            for ht in HookType:
                self._hooks[ht] = []
