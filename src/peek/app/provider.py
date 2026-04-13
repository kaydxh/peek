#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Provider - 全局依赖注入容器

提供全局单例的依赖管理，支持：
- 实例注册与获取
- 工厂函数延迟创建
- 类型安全获取
- 配置存储
"""

import logging
import threading
from typing import Any, Callable, Dict, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Provider:
    """
    全局依赖注入容器

    提供：
    - 配置存储
    - 自定义依赖注册
    - 工厂函数延迟创建

    使用示例：
        provider = get_provider()

        # 设置配置
        provider.set_config(config)

        # 注册依赖
        provider.register("mysql", mysql_client)

        # 获取依赖
        mysql = provider.get("mysql")
    """

    _instance: Optional["Provider"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "Provider":
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._config: Optional[Any] = None
        self._dependencies: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._lock = threading.Lock()
        self._initialized = True

    def set_config(self, config: Any) -> None:
        """
        设置配置

        Args:
            config: 配置对象
        """
        with self._lock:
            self._config = config
            logger.debug("Config set in provider")

    def get_config(self) -> Optional[Any]:
        """
        获取配置

        Returns:
            配置对象
        """
        with self._lock:
            return self._config

    def register(
        self,
        name: str,
        instance: Any,
        overwrite: bool = False,
    ) -> "Provider":
        """
        注册依赖实例

        Args:
            name: 依赖名称
            instance: 依赖实例
            overwrite: 是否覆盖已存在的

        Returns:
            self
        """
        with self._lock:
            if name in self._dependencies and not overwrite:
                logger.warning("Dependency '%s' already exists, skipping", name)
                return self

            self._dependencies[name] = instance
            logger.debug("Registered dependency: %s", name)
        return self

    def register_factory(
        self,
        name: str,
        factory: Callable[[], Any],
    ) -> "Provider":
        """
        注册依赖工厂

        用于延迟创建依赖

        Args:
            name: 依赖名称
            factory: 工厂函数

        Returns:
            self
        """
        with self._lock:
            self._factories[name] = factory
            logger.debug("Registered factory: %s", name)
        return self

    def get(self, name: str, default: Any = None) -> Any:
        """
        获取依赖

        Args:
            name: 依赖名称
            default: 默认值

        Returns:
            依赖实例
        """
        with self._lock:
            # 先查找已创建的实例
            if name in self._dependencies:
                return self._dependencies[name]

            # 尝试使用工厂创建
            if name in self._factories:
                self._dependencies[name] = self._factories[name]()
                logger.debug("Created dependency from factory: %s", name)
                return self._dependencies[name]

        return default

    def get_typed(self, name: str, type_class: Type[T]) -> Optional[T]:
        """
        获取指定类型的依赖

        Args:
            name: 依赖名称
            type_class: 类型类

        Returns:
            依赖实例（如果类型匹配）
        """
        instance = self.get(name)
        if instance is not None and isinstance(instance, type_class):
            return instance
        return None

    def unregister(self, name: str) -> Optional[Any]:
        """
        取消注册依赖

        Args:
            name: 依赖名称

        Returns:
            被移除的依赖
        """
        with self._lock:
            instance = self._dependencies.pop(name, None)
            self._factories.pop(name, None)
            if instance:
                logger.debug("Unregistered dependency: %s", name)
            return instance

    def has(self, name: str) -> bool:
        """
        检查是否存在依赖

        Args:
            name: 依赖名称

        Returns:
            是否存在
        """
        with self._lock:
            return name in self._dependencies or name in self._factories

    def clear(self) -> None:
        """清除所有依赖"""
        with self._lock:
            self._dependencies.clear()
            self._factories.clear()
            self._config = None
            logger.debug("Provider cleared")

    @classmethod
    def reset(cls) -> None:
        """重置单例实例（仅用于测试场景）

        清除单例实例，使下次调用 Provider() 或 get_provider() 时
        重新创建全新的实例。

        警告：此方法仅应在单元测试的 setup/teardown 中使用，
        不要在生产代码中调用。

        使用示例：
            def teardown_method(self):
                Provider.reset()
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance._dependencies.clear()
                cls._instance._factories.clear()
                cls._instance._config = None
            cls._instance = None

    @property
    def dependencies(self) -> Dict[str, Any]:
        """获取所有依赖"""
        return self._dependencies.copy()


# 全局单例获取函数
def get_provider() -> Provider:
    """
    获取全局 Provider 实例

    Returns:
        Provider 单例
    """
    return Provider()
