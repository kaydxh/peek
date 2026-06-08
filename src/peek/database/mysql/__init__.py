#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MySQL 模块

对应 Go 版本 golang/pkg/database/mysql。

子模块：
- peek.database.mysql.config: MySQL 配置模型（纯 pydantic，无外部依赖）
- peek.database.mysql.engine: MySQL 连接工厂（异步 + 同步）
- peek.database.mysql.session: Session 管理与 FastAPI 依赖注入

设计原则：
    本模块只导出纯配置类，不触发 sqlalchemy 依赖。
    需要实际连接 MySQL 时，请显式导入：
        from peek.database.mysql.engine import create_mysql_engine
        from peek.database.mysql.engine import create_sync_mysql_engine
        from peek.database.mysql.session import create_session_factory
"""

from peek.database.mysql.config import MySQLConfig

__all__ = [
    "MySQLConfig",
]