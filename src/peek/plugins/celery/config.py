#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 配置模型

提供 CeleryConfig dataclass 与 parse_celery_config()，
以及从 peek 的 RedisConfig 派生 broker_url 的辅助函数 build_redis_url()。

设计目标：
- yaml 中通常无需显式配置 celery 段，broker / backend 默认从 database.redis 派生
- 仅在需要让 Celery 走与业务缓存不同的 Redis 实例 / db 时才显式覆盖
- 所有解析逻辑在 peek 内复用，避免每个上层服务重复实现
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

# 仅类型注解时引用，避免循环依赖；运行时通过 duck typing 处理
try:
    from peek.database.redis.config import RedisConfig
except ImportError:  # pragma: no cover - peek redis 模块缺失时降级
    RedisConfig = None  # type: ignore


@dataclass
class CeleryConfig:
    """Celery 配置（broker / backend）。

    broker_url / result_backend 默认 None 表示未在 yaml 中显式配置，
    此时调用方应回退到 database.redis 派生的 URL。
    """

    broker_url: Optional[str] = None
    result_backend: Optional[str] = None

    # Celery worker 通用参数，子类/上层可按需扩展
    task_serializer: str = "json"
    result_serializer: str = "json"
    timezone: str = "Asia/Shanghai"
    task_track_started: bool = True


def parse_celery_config(data: Optional[Dict[str, Any]]) -> CeleryConfig:
    """解析 yaml 中的 celery 段。

    yaml 中通常无需配置 celery 段；如未配置，broker_url / result_backend 为 None，
    由调用方（factory）从 database.redis 派生。

    Args:
        data: yaml 中 celery 段对应的 dict（可为 None）

    Returns:
        CeleryConfig 实例
    """
    data = data or {}
    return CeleryConfig(
        broker_url=data.get("broker_url"),
        result_backend=data.get("result_backend"),
        task_serializer=data.get("task_serializer", "json"),
        result_serializer=data.get("result_serializer", "json"),
        timezone=data.get("timezone", "Asia/Shanghai"),
        task_track_started=data.get("task_track_started", True),
    )


def build_redis_url(redis_cfg: Optional[Any]) -> Optional[str]:
    """从 peek 的 RedisConfig 派生 redis://[:password@]host:port/db URL。

    若 redis_cfg 为空或 enabled=False，返回 None，由调用方决定如何兜底。
    兼容 peek RedisConfig（addresses 列表）和单 host/port 形式的 dataclass。

    Args:
        redis_cfg: peek.database.redis.config.RedisConfig 或兼容对象

    Returns:
        redis URL 字符串，未启用则返回 None
    """
    if not redis_cfg or not getattr(redis_cfg, "enabled", False):
        return None

    # 优先取 RedisConfig.host / port 属性（peek RedisConfig 已实现 @property）
    host = getattr(redis_cfg, "host", None) or "localhost"
    port = getattr(redis_cfg, "port", None) or 6379
    password = getattr(redis_cfg, "password", "") or ""
    db = getattr(redis_cfg, "db", 0) or 0

    auth = f":{password}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"
