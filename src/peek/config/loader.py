#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通用配置加载器

支持：
- YAML 文件加载
- 环境变量覆盖
- 多文件合并
- Pydantic 模型转换
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Union

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ConfigLoader:
    """
    通用配置加载器

    支持：
    - YAML 文件加载
    - 环境变量覆盖（按前缀过滤，下划线分层）
    - 多文件合并（后加载覆盖先加载）
    - 转换为 Pydantic 模型
    """

    def __init__(self, env_prefix: str = "APP"):
        """
        初始化配置加载器

        Args:
            env_prefix: 环境变量前缀，默认为 "APP"
        """
        self._data: Dict[str, Any] = {}
        self._env_prefix: str = env_prefix

    def load_file(self, path: Union[str, Path]) -> "ConfigLoader":
        """
        加载配置文件

        Args:
            path: 配置文件路径（YAML 格式）

        Returns:
            self（支持链式调用）

        Raises:
            FileNotFoundError: 文件不存在
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._merge_data(self._data, data)
        logger.info("Loaded config from %s", path)
        return self

    def load_env(self, prefix: Optional[str] = None) -> "ConfigLoader":
        """
        从环境变量加载配置

        环境变量命名规则（以前缀 APP 为例）：
        - APP_WEB_BIND_ADDRESS_PORT=8080
        - APP_LOG_LEVEL=debug

        Args:
            prefix: 环境变量前缀（如不指定则使用初始化时的前缀）

        Returns:
            self（支持链式调用）
        """
        prefix = prefix or self._env_prefix
        prefix = prefix.upper() + "_"

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # 移除前缀并转换为配置路径
            config_key = key[len(prefix) :].lower()
            keys = config_key.split("_")

            # 尝试解析值
            parsed_value = self._parse_env_value(value)

            # 设置到配置中
            self._set_nested(self._data, keys, parsed_value)
            logger.debug("Loaded env config: %s=%s", key, parsed_value)

        return self

    def _parse_env_value(self, value: str) -> Any:
        """解析环境变量值"""
        # 布尔值
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False

        # 整数
        try:
            return int(value)
        except ValueError:
            pass

        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass

        # 列表（逗号分隔）
        if "," in value:
            return [v.strip() for v in value.split(",")]

        return value

    def _set_nested(self, data: Dict, keys: list, value: Any) -> None:
        """设置嵌套字典值"""
        for key in keys[:-1]:
            data = data.setdefault(key, {})
        data[keys[-1]] = value

    def _merge_data(self, base: Dict, override: Dict) -> None:
        """合并配置数据（深度合并，override 覆盖 base）"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_data(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键（支持点分隔，如 "web.bind_address.port"）
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def to_model(self, model_class: Type[T]) -> T:
        """
        转换为 Pydantic 模型

        Args:
            model_class: Pydantic 模型类

        Returns:
            模型实例
        """
        return model_class.model_validate(self._data)

    @property
    def data(self) -> Dict[str, Any]:
        """获取原始数据（返回副本）"""
        return self._data.copy()


def load_config_from_file(
    path: Union[str, Path],
    model_class: Type[T] = None,
    load_env: bool = True,
    env_prefix: str = "APP",
) -> T:
    """
    从文件加载配置

    Args:
        path: 配置文件路径
        model_class: Pydantic 模型类（必须指定）
        load_env: 是否加载环境变量
        env_prefix: 环境变量前缀

    Returns:
        配置模型实例

    Raises:
        ValueError: 未指定 model_class
    """
    if model_class is None:
        raise ValueError("model_class must be specified")

    loader = ConfigLoader(env_prefix=env_prefix)
    loader.load_file(path)

    if load_env:
        loader.load_env()

    return loader.to_model(model_class)


def load_config(
    data: Dict[str, Any],
    model_class: Type[T] = None,
) -> T:
    """
    从字典加载配置

    Args:
        data: 配置字典
        model_class: Pydantic 模型类（必须指定）

    Returns:
        配置模型实例

    Raises:
        ValueError: 未指定 model_class
    """
    if model_class is None:
        raise ValueError("model_class must be specified")

    return model_class.model_validate(data)
