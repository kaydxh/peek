#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
公共监控安装模块（函数式接口）

提供 install_monitor() / uninstall_monitor() 函数式接口。
上层框架（如 tide）可直接调用，无需重复实现监控安装逻辑。

MonitorPlugin（Plugin 类形式）仍保留在上层框架中，因为它依赖框架特有的 CommandContext。
"""

import logging
from typing import Any, Optional

# MonitorConfig 从 peek.config.schema 导入
from peek.config.schema import MonitorConfig

logger = logging.getLogger(__name__)


# 全局 MonitorService 实例
_monitor_service = None


def get_monitor_service():
    """获取全局 MonitorService 实例。

    Returns:
        MonitorService 实例，如果未初始化则返回 None
    """
    return _monitor_service


async def install_monitor(
    config: Optional[MonitorConfig], web_server=None
) -> Optional[Any]:
    """安装监控插件（函数式接口）。

    Args:
        config: 监控配置，为 None 或 enabled=False 时跳过安装
        web_server: Web 服务器实例（用于注册 API 路由）

    Returns:
        MonitorService 实例，如果未启用则返回 None
    """
    global _monitor_service

    if config is None or not config.enabled:
        logger.info("Monitor plugin is not enabled")
        return None

    try:
        # 检查依赖
        try:
            import psutil  # noqa: F401
        except ImportError:
            logger.error(
                "psutil 未安装，监控插件需要 psutil。请运行: pip install psutil"
            )
            return None

        try:
            from peek.os.monitor.service import (
                MonitorService,
                MonitorServiceConfig,
                register_monitor_routes,
            )
        except ImportError:
            logger.error("peek.os.monitor.service 模块未安装，监控插件需要 peek 库")
            return None

        # 将 peek MonitorConfig 转换为 peek MonitorServiceConfig
        service_config = MonitorServiceConfig(
            enabled=config.enabled,
            auto_start=config.auto_start,
            interval=config.interval,
            enable_gpu=config.enable_gpu,
            include_children=config.include_children,
            history_size=config.history_size,
        )

        # 创建监控服务
        service = MonitorService(service_config)
        _monitor_service = service

        # 注册 API 路由
        if web_server is not None:
            app = getattr(web_server, "app", None)
            if app is None:
                router = getattr(web_server, "router", None)
                if router is not None:
                    app = router
            if app is not None:
                register_monitor_routes(app, service)
            else:
                logger.warning(
                    "web_server 没有 app 或 router 属性，无法注册监控 API 路由"
                )

        # 如果配置了自动启动，则开始持续采集
        if config.auto_start:
            logger.info("monitor.auto_start=true, starting continuous collection...")
            result = service.start_collecting()
            logger.info("Continuous collection start result: %s", result)

        logger.info(
            f"监控插件已安装: interval={config.interval}s, "
            f"enable_gpu={config.enable_gpu}, "
            f"include_children={config.include_children}, "
            f"auto_start={config.auto_start}"
        )

        return service

    except Exception as e:
        logger.error("Failed to install monitor plugin: %s", e, exc_info=True)
        raise


async def uninstall_monitor() -> None:
    """卸载监控插件。"""
    global _monitor_service

    if _monitor_service is not None:
        _monitor_service.shutdown()
        _monitor_service = None
        logger.info("Monitor plugin uninstalled")
