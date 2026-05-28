#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis 连接工厂

对应 Go 版本 golang/pkg/database/redis/redis.go。
提供纯工厂函数创建 Redis 异步连接，不依赖框架上下文（Plugin/Provider）。
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Union

from peek.database.redis.config import RedisConfig

logger = logging.getLogger(__name__)


async def create_redis_client(
    config: Union[RedisConfig, Dict[str, Any]],
) -> Optional[Any]:
    """
    创建 Redis 异步客户端

    对应 Go 版本 RedisClient.GetDatabaseUntil()，支持重试等待直到连接成功。
    支持单节点和 Sentinel 模式（多地址时自动使用 Sentinel）。

    Args:
        config: RedisConfig 实例或 dict 配置

    Returns:
        redis.asyncio.Redis 客户端实例，未启用时返回 None

    Raises:
        ImportError: 缺少 redis 依赖
        Exception: 超过 fail_after_duration 仍无法连接
    """
    # 支持 dict 或 RedisConfig
    if isinstance(config, dict):
        config = RedisConfig.model_validate(config)

    if not config.enabled:
        logger.debug("Redis is disabled, skipping")
        return None

    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("redis[asyncio] not installed, skipping Redis")
        return None

    # 构建连接参数
    if config.is_sentinel:
        # Sentinel 模式，对应 Go 版本 redis.NewFailoverClient
        from redis.asyncio.sentinel import Sentinel

        sentinel = Sentinel(
            [
                (addr.rsplit(":", 1)[0], int(addr.rsplit(":", 1)[1]))
                for addr in config.addresses
            ],
            socket_timeout=config.dial_timeout if config.dial_timeout > 0 else None,
            password=config.password or None,
        )
        client = sentinel.master_for(
            config.master_name,
            db=config.db,
        )
    else:
        # 单节点模式，对应 Go 版本 redis.NewClient
        connect_kwargs = dict(
            host=config.host,
            port=config.port,
            password=config.password or None,
            db=config.db,
            max_connections=config.max_connections,
            socket_connect_timeout=(
                config.dial_timeout if config.dial_timeout > 0 else None
            ),
            socket_timeout=config.read_timeout if config.read_timeout > 0 else None,
            health_check_interval=(
                config.health_check_interval if config.health_check_interval > 0 else 0
            ),
        )
        if config.ssl:
            connect_kwargs["ssl"] = True
            connect_kwargs["ssl_cert_reqs"] = None  # 不验证服务端证书

        client = aioredis.Redis(**connect_kwargs)

    # 重试等待连接，对应 Go 版本的 GetDatabaseUntil
    fail_after = config.fail_after_duration
    wait_interval = config.max_wait_duration
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            await client.ping()
            break
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            if fail_after > 0 and elapsed >= fail_after:
                await client.close()
                raise RuntimeError(f"Redis 连接失败，已超过 {fail_after}s: {e}") from e
            logger.warning("Redis connection failed, retrying in %.1fs: %s", elapsed, e)
            await asyncio.sleep(min(wait_interval, max(fail_after - elapsed, 0.1)))

    logger.info("Redis connected: %s:%s/%s", config.host, config.port, config.db)
    return client


async def close_redis_client(client: Any) -> None:
    """
    关闭 Redis 客户端

    Args:
        client: redis.asyncio.Redis 实例
    """
    if client is not None:
        await client.close()
        logger.info("Redis connection closed")


async def check_redis_health(client: Any) -> Optional[Exception]:
    """
    检查 Redis 连接健康状态

    可用于注册到 HealthzController 的 readyz_checkers。

    Args:
        client: redis.asyncio.Redis 实例

    Returns:
        None 表示健康，Exception 表示不健康
    """
    if client is None:
        return Exception("Redis client is None")

    try:
        result = await client.ping()
        if result:
            return None
        return Exception("Redis PING returned False")
    except Exception as e:
        return Exception(f"Redis health check failed: {e}")


def get_redis_pool_stats(client: Any) -> Dict:
    """
    获取 Redis 连接池统计信息

    Args:
        client: redis.asyncio.Redis 实例

    Returns:
        连接池统计字典，包含：
        - max_connections: 最大连接数
        - current_connections: 当前连接数（使用中 + 空闲）
        - available_connections: 可用连接数
        - in_use_connections: 使用中的连接数
    """
    if client is None:
        return {}

    try:
        pool = client.connection_pool
        return {
            "max_connections": pool.max_connections,
            "current_connections": (
                len(pool._created_connections)
                if hasattr(pool, "_created_connections")
                else 0
            ),
            "available_connections": (
                len(pool._available_connections)
                if hasattr(pool, "_available_connections")
                else 0
            ),
            "in_use_connections": (
                len(pool._in_use_connections)
                if hasattr(pool, "_in_use_connections")
                else 0
            ),
        }
    except Exception:
        return {}


@asynccontextmanager
async def redis_client_context(
    config: Union[RedisConfig, Dict[str, Any]],
) -> AsyncIterator[Optional[Any]]:
    """Redis 客户端异步上下文管理器

    自动管理客户端的创建和关闭，避免资源泄漏。

    Args:
        config: RedisConfig 实例或 dict 配置

    Yields:
        redis.asyncio.Redis 客户端实例，未启用时 yield None

    使用示例：
        async with redis_client_context(config) as client:
            if client:
                await client.set("key", "value")
                value = await client.get("key")
    """
    client = await create_redis_client(config)
    try:
        yield client
    finally:
        await close_redis_client(client)
