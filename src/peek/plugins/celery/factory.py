#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 应用工厂

提供 create_celery_app() 工厂函数，封装 Celery 实例创建和 broker URL 解析的事实标准：

broker / backend 解析优先级：
  1. 环境变量 CELERY_BROKER_URL / CELERY_RESULT_BACKEND（最高，便于 K8s 临时覆盖）
  2. 显式传入的 CeleryConfig.broker_url / result_backend（来自 yaml）
  3. 由 peek RedisConfig 派生（单一数据源，推荐）
  4. 兜底默认值 redis://127.0.0.1:6379/0

上层服务（eduprobe / 其它）只需提供 CeleryConfig + 可选 RedisConfig，
不再重复实现 yaml 加载 / 优先级解析 / Celery 实例化逻辑。
"""

import logging
import os
from typing import Any, Optional, Tuple

from peek.plugins.celery.config import CeleryConfig, build_redis_url

logger = logging.getLogger(__name__)

_DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"


def resolve_broker_urls(
    celery_config: Optional[CeleryConfig] = None,
    redis_config: Optional[Any] = None,
    default_url: str = _DEFAULT_REDIS_URL,
) -> Tuple[str, str]:
    """解析 (broker_url, result_backend)，遵循上述优先级。

    Args:
        celery_config: yaml 中显式配置的 CeleryConfig
        redis_config: peek RedisConfig，用于派生 broker
        default_url: 兜底默认值

    Returns:
        (broker_url, result_backend) 二元组
    """
    env_broker = os.environ.get("CELERY_BROKER_URL")
    env_backend = os.environ.get("CELERY_RESULT_BACKEND")

    yaml_broker = celery_config.broker_url if celery_config else None
    yaml_backend = celery_config.result_backend if celery_config else None

    derived = build_redis_url(redis_config)

    broker = env_broker or yaml_broker or derived or default_url
    backend = env_backend or yaml_backend or derived or broker
    return broker, backend


def create_celery_app(
    name: str,
    celery_config: Optional[CeleryConfig] = None,
    redis_config: Optional[Any] = None,
    default_url: str = _DEFAULT_REDIS_URL,
) -> Any:
    """创建并配置 Celery 应用实例。

    使用懒连接：模块导入时不会真正连接 Redis，第一次发任务/拉任务时才连。

    Args:
        name: Celery 应用名（通常用服务名，如 "eduprobe"）
        celery_config: yaml 中显式配置的 CeleryConfig（可为 None）
        redis_config: peek RedisConfig，用于派生 broker（可为 None）
        default_url: 兜底默认值

    Returns:
        配置好的 celery.Celery 实例

    Raises:
        ImportError: celery 未安装
    """
    try:
        from celery import Celery
    except ImportError as exc:
        raise ImportError(
            "celery is required for peek.plugins.celery; "
            "install via `pip install celery`"
        ) from exc

    broker, backend = resolve_broker_urls(
        celery_config=celery_config,
        redis_config=redis_config,
        default_url=default_url,
    )

    app = Celery(name, broker=broker, backend=backend)

    cfg = celery_config or CeleryConfig()
    app.conf.update(
        task_serializer=cfg.task_serializer,
        result_serializer=cfg.result_serializer,
        accept_content=[cfg.result_serializer],
        timezone=cfg.timezone,
        task_track_started=cfg.task_track_started,
    )

    # 不打印 password
    safe_broker = _mask_password(broker)
    logger.info(
        "Celery app initialized: name=%s broker=%s backend=%s",
        name,
        safe_broker,
        _mask_password(backend),
    )
    return app


def _mask_password(url: str) -> str:
    """将 redis://:pwd@host:port/db 中的密码替换为 ***，避免日志泄露。"""
    if not url or "@" not in url:
        return url
    try:
        scheme_sep = url.find("://")
        if scheme_sep == -1:
            return url
        scheme = url[: scheme_sep + 3]
        rest = url[scheme_sep + 3 :]
        auth, host = rest.split("@", 1)
        if ":" in auth:
            user, _ = auth.split(":", 1)
            return f"{scheme}{user}:***@{host}"
        return f"{scheme}***@{host}"
    except Exception:
        return url
