#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command - 命令和上下文

提供通用的命令定义和执行上下文。
上层框架可以继承 CommandContext 添加具体类型约束。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict


@dataclass
class Command:
    """
    命令定义

    Attributes:
        name: 命令名称
        func: 命令函数
        description: 命令描述
        aliases: 命令别名
    """

    name: str
    func: Callable
    description: str = ""
    aliases: list = field(default_factory=list)


@dataclass
class CommandContext:
    """
    命令执行上下文

    提供命令执行所需的所有依赖。
    上层框架（如 tide）可以继承此类并添加具体类型约束。

    Attributes:
        app: 应用实例
        config: 配置对象
        provider: 依赖提供者
        extra: 额外数据
    """

    app: Any = None
    config: Any = None
    provider: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """获取额外数据"""
        return self.extra.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置额外数据"""
        self.extra[key] = value
