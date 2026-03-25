#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vLLM installation/uninstallation and global instance management.
"""

import logging
from typing import Any, Callable, Coroutine, Optional

from peek.plugins.vllm.config import VLLMConfig
from peek.plugins.vllm.manager import VLLMServerManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global functional interface
# ---------------------------------------------------------------------------

# 全局 vLLM server 管理器实例
_vllm_server_manager: Optional[VLLMServerManager] = None


def get_vllm_server_manager() -> Optional[VLLMServerManager]:
    """Get the global vLLM server manager instance"""
    return _vllm_server_manager


# 注册客户端回调类型：接收 (config, server_manager) 并完成 client 创建 + provider 注册
ClientRegistrar = Callable[[VLLMConfig, Optional[VLLMServerManager]], Coroutine[Any, Any, None]]


async def install_vllm(
    config: Optional[VLLMConfig],
    register_client: Optional[ClientRegistrar] = None,
) -> None:
    """Install vLLM client (and optionally start vLLM server).

    Common logic (auto_start / server management) is handled by peek;
    client creation and provider registration are delegated to cmd-side via register_client callback.

    Args:
        config: vLLM config, skip if None or enabled=False
        register_client: Optional callback for creating vLLM client and registering to provider.
                         Signature: async def(config, server_manager) -> None
    """
    global _vllm_server_manager

    if config is None or not config.enabled:
        logger.info("vLLM client is not enabled")
        return

    try:
        # 如果配置了自动启动，先启动 vLLM server
        if config.auto_start:
            logger.info("auto_start=True, starting vLLM server...")
            _vllm_server_manager = VLLMServerManager(config)
            await _vllm_server_manager.start()
            await _vllm_server_manager.wait_for_ready()

            # vLLM 已就绪，启动看门狗并标记为 ready
            await _vllm_server_manager.start_watchdog(mark_ready=True)

        # 由 cmd 端提供的回调完成 client 创建 + provider 注册
        if register_client is not None:
            await register_client(config, _vllm_server_manager)

        logger.info(
            "vLLM client installed: host=%s, port=%s, model=%s, auto_start=%s",
            config.host, config.port, config.model_name, config.auto_start,
        )

    except Exception as e:
        logger.error("Failed to install vLLM client: %s", e)
        raise


async def uninstall_vllm():
    """Uninstall vLLM (stop watchdog and server process)"""
    global _vllm_server_manager

    if _vllm_server_manager:
        await _vllm_server_manager.stop()
        _vllm_server_manager = None
        logger.info("vLLM server stopped")
