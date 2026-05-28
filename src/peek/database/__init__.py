#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库模块

提供通用的数据库配置模型，对应 Go 版本 golang/pkg/database。

子模块：
- peek.database.mysql.config: MySQL 配置模型（纯 pydantic，无外部依赖）
- peek.database.mysql.engine: MySQL 异步连接工厂（依赖 sqlalchemy）
- peek.database.redis.config: Redis 配置模型（纯 pydantic，无外部依赖）
- peek.database.redis.client: Redis 异步连接工厂（依赖 redis）

设计原则：
    本模块只导出纯配置类（pydantic 模型），不触发任何外部依赖（sqlalchemy/redis）。
    需要实际连接数据库时，请显式导入实现模块：
        from peek.database.mysql.engine import create_mysql_engine
        from peek.database.redis.client import create_redis_client
"""

from peek.database.mysql.config import MySQLConfig
from peek.database.redis.config import RedisConfig

__all__ = [
    "MySQLConfig",
    "RedisConfig",
]