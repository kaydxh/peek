#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库模块

提供通用的数据库连接创建能力，对应 Go 版本 golang/pkg/database。

子模块：
- peek.database.mysql: MySQL 异步连接工厂
- peek.database.redis: Redis 异步连接工厂
"""

from peek.database.mysql import (
    MySQLConfig,
    create_mysql_engine,
    close_mysql_engine,
    check_mysql_health,
    get_mysql_pool_stats,
    mysql_engine_context,
)
from peek.database.redis import (
    RedisConfig,
    create_redis_client,
    close_redis_client,
    check_redis_health,
    get_redis_pool_stats,
    redis_client_context,
)

__all__ = [
    "MySQLConfig",
    "create_mysql_engine",
    "close_mysql_engine",
    "check_mysql_health",
    "get_mysql_pool_stats",
    "mysql_engine_context",
    "RedisConfig",
    "create_redis_client",
    "close_redis_client",
    "check_redis_health",
    "get_redis_pool_stats",
    "redis_client_context",
]
