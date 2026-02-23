#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
App 模块

提供应用程序核心组件：
- BaseApp: 应用程序基类
- Command: 命令行支持
- Plugin: 插件基类与插件管理器
- HookManager: 钩子函数管理
- Provider: 全局依赖注入容器
"""

from peek.app.application import BaseApp
from peek.app.command import Command, CommandContext
from peek.app.hooks import (
    AsyncHookFunc,
    HookEntry,
    HookFunc,
    HookManager,
    HookType,
    PostStartHook,
    PreShutdownHook,
)
from peek.app.plugin import Plugin, PluginManager
from peek.app.provider import Provider, get_provider

__all__ = [
    # Application
    "BaseApp",
    # Command
    "Command",
    "CommandContext",
    # Plugin
    "Plugin",
    "PluginManager",
    # Hooks
    "HookType",
    "HookEntry",
    "HookFunc",
    "AsyncHookFunc",
    "HookManager",
    "PostStartHook",
    "PreShutdownHook",
    # Provider
    "Provider",
    "get_provider",
]
