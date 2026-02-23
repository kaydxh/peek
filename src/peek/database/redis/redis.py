#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis 连接工厂

对应 Go 版本 golang/pkg/database/redis/redis.go。
提供纯工厂函数创建 Redis 异步连接，不依赖框架上下文（Plugin/Provider）。
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Union

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
        logger.warning("redis[asyncio] 未安装，跳过 Redis")
        return None

    # 构建连接参数
    if config.is_sentinel:
        # Sentinel 模式，对应 Go 版本 redis.NewFailoverClient
        from redis.asyncio.sentinel import Sentinel

        sentinel = Sentinel(
            [(addr.rsplit(":", 1)[0], int(addr.rsplit(":", 1)[1]))
             for addr in config.addresses],
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
            socket_connect_timeout=config.dial_timeout if config.dial_timeout > 0 else None,
            socket_timeout=config.read_timeout if config.read_timeout > 0 else None,
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
                raise RuntimeError(
                    f"Redis 连接失败，已超过 {fail_after}s: {e}"
                ) from e
            logger.warning(f"Redis 连接失败，{elapsed:.1f}s 后重试: {e}")
            await asyncio.sleep(min(wait_interval, max(fail_after - elapsed, 0.1)))

    logger.info(f"Redis 连接成功: {config.host}:{config.port}/{config.db}")
    return client


async def close_redis_client(client: Any) -> None:
    """
    关闭 Redis 客户端

    Args:
        client: redis.asyncio.Redis 实例
    """
    if client is not None:
        await client.close()
        logger.info("Redis 连接已关闭")
