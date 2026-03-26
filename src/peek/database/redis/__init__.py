#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis 模块

对应 Go 版本 golang/pkg/database/redis。
提供 Redis 配置模型和异步连接工厂函数。
"""

from peek.database.redis.config import RedisConfig
from peek.database.redis.redis import (
    create_redis_client,
    close_redis_client,
    check_redis_health,
    get_redis_pool_stats,
    redis_client_context,
)

__all__ = [
    "RedisConfig",
    "create_redis_client",
    "close_redis_client",
    "check_redis_health",
    "get_redis_pool_stats",
    "redis_client_context",
]
