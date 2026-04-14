#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MySQL 模块

对应 Go 版本 golang/pkg/database/mysql。
提供 MySQL 配置模型和异步连接工厂函数。
"""

from peek.database.mysql.config import MySQLConfig
from peek.database.mysql.mysql import (
    check_mysql_health,
    close_mysql_engine,
    create_mysql_engine,
    get_mysql_pool_stats,
    mysql_engine_context,
)

__all__ = [
    "MySQLConfig",
    "create_mysql_engine",
    "close_mysql_engine",
    "check_mysql_health",
    "get_mysql_pool_stats",
    "mysql_engine_context",
]
