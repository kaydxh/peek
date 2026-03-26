#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin - 插件机制

提供组件的插件化加载和管理。
插件通过 install/uninstall 生命周期方法实现初始化与清理。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """
    插件基类

    所有插件必须继承此类并实现 install/uninstall 方法。

    使用示例：
        class MySQLPlugin(Plugin):
            name = "mysql"
            priority = 10

            async def install(self, ctx: Any) -> None:
                # 初始化 MySQL 连接
                pass

            async def uninstall(self, ctx: Any) -> None:
                # 关闭连接
                pass
    """

    # 插件名称
    name: str = "base"

    # 优先级（越大越先安装，越小越先卸载）
    priority: int = 0

    # 是否启用（可以根据配置动态决定）
    enabled: bool = True

    @abstractmethod
    async def install(self, ctx: Any) -> None:
        """
        安装插件

        Args:
            ctx: 命令上下文（由上层框架定义具体类型）
        """
        pass

    @abstractmethod
    async def uninstall(self, ctx: Any) -> None:
        """
        卸载插件

        Args:
            ctx: 命令上下文（由上层框架定义具体类型）
        """
        pass

    def should_install(self, ctx: Any) -> bool:
        """
        判断是否应该安装

        可以覆盖此方法，根据配置决定是否安装

        Args:
            ctx: 命令上下文

        Returns:
            是否应该安装
        """
        return self.enabled


class PluginManager:
    """
    插件管理器

    管理插件的注册、安装、卸载
    """

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._installed: List[str] = []

    def register(self, plugin: Plugin) -> "PluginManager":
        """
        注册插件

        Args:
            plugin: 插件实例

        Returns:
            self
        """
        if plugin.name in self._plugins:
            logger.warning("Plugin '%s' already registered, overwriting", plugin.name)

        self._plugins[plugin.name] = plugin
        logger.debug("Plugin '%s' registered with priority %s", plugin.name, plugin.priority)
        return self

    def unregister(self, name: str) -> Optional[Plugin]:
        """
        取消注册插件

        Args:
            name: 插件名称

        Returns:
            被移除的插件，如果不存在则返回 None
        """
        return self._plugins.pop(name, None)

    def get(self, name: str) -> Optional[Plugin]:
        """
        获取插件

        Args:
            name: 插件名称

        Returns:
            插件实例
        """
        return self._plugins.get(name)

    async def install_all(self, ctx: Any) -> None:
        """
        安装所有插件

        按优先级从高到低安装

        Args:
            ctx: 命令上下文
        """
        # 按优先级排序（从高到低）
        sorted_plugins = sorted(
            self._plugins.values(),
            key=lambda p: p.priority,
            reverse=True,
        )

        for plugin in sorted_plugins:
            if not plugin.should_install(ctx):
                logger.debug("Skipping plugin '%s' (disabled)", plugin.name)
                continue

            try:
                logger.info("Installing plugin '%s'...", plugin.name)
                await plugin.install(ctx)
                self._installed.append(plugin.name)
                logger.info("Plugin '%s' installed successfully", plugin.name)
            except Exception as e:
                logger.error("Failed to install plugin '%s': %s", plugin.name, e)
                raise

    async def uninstall_all(self, ctx: Any) -> None:
        """
        卸载所有已安装的插件

        按安装顺序的反序卸载

        Args:
            ctx: 命令上下文
        """
        # 反序卸载
        for name in reversed(self._installed):
            plugin = self._plugins.get(name)
            if not plugin:
                continue

            try:
                logger.info("Uninstalling plugin '%s'...", name)
                await plugin.uninstall(ctx)
                logger.info("Plugin '%s' uninstalled successfully", name)
            except Exception as e:
                logger.error("Failed to uninstall plugin '%s': %s", name, e)
                # 继续卸载其他插件

        self._installed.clear()

    @property
    def plugins(self) -> Dict[str, Plugin]:
        """获取所有插件"""
        return self._plugins.copy()

    @property
    def installed(self) -> List[str]:
        """获取已安装的插件名称列表"""
        return self._installed.copy()
