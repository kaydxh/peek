#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
peek.plugins.celery - Celery 应用工厂 + 链路追踪装饰器

提供能力：
1. CeleryConfig dataclass + parse_celery_config()：yaml 段解析
2. build_redis_url()：从 peek RedisConfig 派生 broker URL
3. create_celery_app()：工厂函数，封装 broker URL 优先级（env > yaml > redis 派生 > default）
4. resolve_broker_urls()：仅做 URL 解析（不创建 Celery 实例，便于测试）
5. @traceable_task：装饰器，让 worker 进程的日志自动带上 caller 端 trace_id
6. inject_trace_kwargs()：HTTP handler 调用 task.delay() 前的辅助函数

典型使用场景见 decorator.py 顶部 docstring。
"""

from peek.plugins.celery.config import (
    CeleryConfig,
    build_redis_url,
    parse_celery_config,
)
from peek.plugins.celery.decorator import (
    inject_trace_kwargs,
    traceable_task,
)
from peek.plugins.celery.factory import (
    create_celery_app,
    resolve_broker_urls,
)

__all__ = [
    "CeleryConfig",
    "parse_celery_config",
    "build_redis_url",
    "create_celery_app",
    "resolve_broker_urls",
    "traceable_task",
    "inject_trace_kwargs",
]
