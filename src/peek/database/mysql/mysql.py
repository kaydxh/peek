#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MySQL 连接工厂

对应 Go 版本 golang/pkg/database/mysql/mysql.go。
提供纯工厂函数创建 MySQL 异步连接，不依赖框架上下文（Plugin/Provider）。
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Union

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from peek.database.mysql.config import MySQLConfig

logger = logging.getLogger(__name__)


async def create_mysql_engine(
    config: Union[MySQLConfig, Dict[str, Any]],
) -> Optional[Any]:
    """
    创建 MySQL 异步引擎

    对应 Go 版本 DB.GetDatabaseUntil()，支持重试等待直到连接成功。

    Args:
        config: MySQLConfig 实例或 dict 配置

    Returns:
        SQLAlchemy AsyncEngine 实例，未启用时返回 None

    Raises:
        ImportError: 缺少 sqlalchemy 或 aiomysql 依赖
        Exception: 超过 fail_after_duration 仍无法连接
    """
    # 支持 dict 或 MySQLConfig
    if isinstance(config, dict):
        config = MySQLConfig.model_validate(config)

    if not config.enabled:
        logger.debug("MySQL is disabled, skipping")
        return None

    engine = create_async_engine(
        config.dsn,
        pool_size=config.max_idle_connections,
        max_overflow=max(config.max_connections - config.max_idle_connections, 0),
        pool_recycle=int(config.max_life_time) if config.max_life_time > 0 else -1,
        pool_pre_ping=config.pool_pre_ping,
        pool_timeout=config.pool_timeout if config.pool_timeout > 0 else 30,
        echo=False,
    )

    # 重试等待连接，对应 Go 版本的 GetDatabaseUntil
    fail_after = config.fail_after_duration
    wait_interval = config.max_wait_duration
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            async with engine.connect() as conn:
                await conn.execute(sqlalchemy.text("SELECT 1"))
            break
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            if fail_after > 0 and elapsed >= fail_after:
                await engine.dispose()
                raise RuntimeError(
                    f"MySQL 连接失败，已超过 {fail_after}s: {e}"
                ) from e
            logger.warning("MySQL connection failed, retrying in %.1fs: %s", elapsed, e)
            await asyncio.sleep(min(wait_interval, max(fail_after - elapsed, 0.1)))

    logger.info("MySQL connected: %s/%s", config.address, config.db_name)
    return engine


async def close_mysql_engine(engine: Any) -> None:
    """
    关闭 MySQL 引擎

    Args:
        engine: SQLAlchemy AsyncEngine 实例
    """
    if engine is not None:
        await engine.dispose()
        logger.info("MySQL connection closed")


async def check_mysql_health(engine: Any) -> Optional[Exception]:
    """
    检查 MySQL 连接健康状态

    可用于注册到 HealthzController 的 readyz_checkers。

    Args:
        engine: SQLAlchemy AsyncEngine 实例

    Returns:
        None 表示健康，Exception 表示不健康
    """
    if engine is None:
        return Exception("MySQL engine is None")

    try:
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        return None
    except Exception as e:
        return Exception(f"MySQL health check failed: {e}")


def get_mysql_pool_stats(engine: Any) -> Dict:
    """
    获取 MySQL 连接池统计信息

    Args:
        engine: SQLAlchemy AsyncEngine 实例

    Returns:
        连接池统计字典，包含：
        - pool_size: 连接池大小
        - checked_in: 空闲连接数
        - checked_out: 使用中的连接数
        - overflow: 溢出连接数
        - invalid: 无效连接数
    """
    if engine is None:
        return {}

    try:
        pool = engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalidated if hasattr(pool, 'invalidated') else 0,
        }
    except Exception:
        return {}
