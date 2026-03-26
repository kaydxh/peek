#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
公共 MySQL 安装模块（函数式接口）

提供 install_mysql() / uninstall_mysql() / get_mysql_engine() 函数式接口。
上层框架（如 tide）可直接调用，无需重复实现 MySQL 安装逻辑。

通过 register_callback 回调将 engine 注册到上层 Provider，
通过 web_server 自动注册 shutdown hook 以优雅关闭连接池。

MySQLPlugin（Plugin 类形式）仍保留在上层框架中，因为它依赖框架特有的 CommandContext。
"""

import logging
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)

# 全局 MySQL engine 实例
_mysql_engine = None


def get_mysql_engine():
    """获取全局 MySQL engine 实例。

    Returns:
        SQLAlchemy AsyncEngine 实例，如果未初始化则返回 None
    """
    return _mysql_engine


# 注册回调类型：接收 engine 并完成 provider 注册
EngineRegistrar = Callable[[Any], Coroutine[Any, Any, None]]


async def install_mysql(
    config: Dict[str, Any],
    web_server=None,
    register_callback: Optional[EngineRegistrar] = None,
) -> Optional[Any]:
    """安装 MySQL 连接（函数式接口）。

    通用逻辑（创建 engine、shutdown hook 注册）由 peek 处理；
    provider 注册通过 register_callback 回调交由上层自定义。

    Args:
        config: MySQL 配置字典
        web_server: GenericWebServer 实例，用于注册 shutdown hook 以优雅关闭连接池
        register_callback: 可选回调，用于将 engine 注册到 provider。
                          签名: async def(engine) -> None

    Returns:
        SQLAlchemy AsyncEngine 实例，未启用则返回 None
    """
    global _mysql_engine

    if not config or not config.get("enabled", False):
        logger.debug("MySQL is disabled, skipping installation")
        return None

    try:
        from peek.database.mysql import create_mysql_engine, close_mysql_engine

        engine = await create_mysql_engine(config)

        if engine is not None:
            _mysql_engine = engine

            # 通过回调将 engine 注册到上层 provider
            if register_callback is not None:
                await register_callback(engine)

            # 注册 shutdown hook，在服务退出前主动关闭连接池
            # 避免事件循环关闭后 aiomysql Connection.__del__ 报 RuntimeError
            if web_server is not None:
                web_server.add_pre_shutdown_hook(
                    "mysql-close",
                    lambda: close_mysql_engine(engine),
                )
                logger.info("Registered MySQL shutdown hook")

            return engine

    except ImportError:
        logger.warning("MySQL dependencies not installed, skipping")
    except Exception as e:
        logger.error("Failed to install MySQL: %s", e)
        raise

    return None


async def uninstall_mysql() -> None:
    """卸载 MySQL（关闭连接池）。"""
    global _mysql_engine

    if _mysql_engine is not None:
        try:
            from peek.database.mysql import close_mysql_engine

            await close_mysql_engine(_mysql_engine)
        except Exception as e:
            logger.error("Failed to uninstall MySQL: %s", e)
        finally:
            _mysql_engine = None
            logger.info("MySQL connection closed")
