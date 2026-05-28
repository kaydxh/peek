#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis 模块

对应 Go 版本 golang/pkg/database/redis。

子模块：
- peek.database.redis.config: Redis 配置模型（纯 pydantic，无外部依赖）
- peek.database.redis.client: Redis 异步连接工厂（依赖 redis 库）

设计原则：
    本模块只导出纯配置类，不触发 redis 库依赖。
    需要实际连接 Redis 时，请显式导入：
        from peek.database.redis.client import create_redis_client
"""

from peek.database.redis.config import RedisConfig

__all__ = [
    "RedisConfig",
]