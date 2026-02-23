#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
公共 Redis 安装模块（函数式接口）

提供 install_redis() / uninstall_redis() / get_redis_client() 函数式接口。
上层框架（如 tide）可直接调用，无需重复实现 Redis 安装逻辑。

通过 register_callback 回调将 client 注册到上层 Provider，
通过 web_server 自动注册 shutdown hook 以优雅关闭连接。

RedisPlugin（Plugin 类形式）仍保留在上层框架中，因为它依赖框架特有的 CommandContext。
"""

import logging
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)

# 全局 Redis client 实例
_redis_client = None


def get_redis_client():
    """获取全局 Redis client 实例。

    Returns:
        redis.asyncio.Redis 实例，如果未初始化则返回 None
    """
    return _redis_client


# 注册回调类型：接收 client 并完成 provider 注册
ClientRegistrar = Callable[[Any], Coroutine[Any, Any, None]]


async def install_redis(
    config: Dict[str, Any],
    web_server=None,
    register_callback: Optional[ClientRegistrar] = None,
) -> Optional[Any]:
    """安装 Redis 连接（函数式接口）。

    通用逻辑（创建 client、shutdown hook 注册）由 peek 处理；
    provider 注册通过 register_callback 回调交由上层自定义。

    Args:
        config: Redis 配置字典
        web_server: GenericWebServer 实例，用于注册 shutdown hook 以优雅关闭连接
        register_callback: 可选回调，用于将 client 注册到 provider。
                          签名: async def(client) -> None

    Returns:
        redis.asyncio.Redis 实例，未启用则返回 None
    """
    global _redis_client

    if not config or not config.get("enabled", False):
        logger.debug("Redis is disabled, skipping installation")
        return None

    try:
        from peek.database.redis import create_redis_client, close_redis_client

        client = await create_redis_client(config)

        if client is not None:
            _redis_client = client

            # 通过回调将 client 注册到上层 provider
            if register_callback is not None:
                await register_callback(client)

            # 注册 shutdown hook，在服务退出前主动关闭 Redis 连接
            if web_server is not None:
                web_server.add_pre_shutdown_hook(
                    "redis-close",
                    lambda: close_redis_client(client),
                )
                logger.info("Registered Redis shutdown hook")

            return client

    except ImportError:
        logger.warning("Redis dependencies not installed, skipping")
    except Exception as e:
        logger.warning(f"Failed to install Redis: {e}, skipping Redis plugin")

    return None


async def uninstall_redis() -> None:
    """卸载 Redis（关闭连接）。"""
    global _redis_client

    if _redis_client is not None:
        try:
            from peek.database.redis import close_redis_client

            await close_redis_client(_redis_client)
        except Exception as e:
            logger.error(f"Failed to uninstall Redis: {e}")
        finally:
            _redis_client = None
            logger.info("Redis 连接已关闭")
