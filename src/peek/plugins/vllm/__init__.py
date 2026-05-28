#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
peek.plugins.vllm - vLLM server management and configuration

Provides:
1. VLLMConfig dataclass - vLLM 顶层配置（组合子配置）
2. VLLMServerConfig / VLLMNsysConfig / VLLMWatchdogConfig / VLLMInferenceConfig - 子配置
3. VLLMServerManager - vLLM Server process manager
4. install_vllm / uninstall_vllm / get_vllm_server_manager - functional interface
5. parse_vllm_config - configuration parsing utility
"""

from peek.plugins.vllm.config import (
    VLLMConfig,
    VLLMInferenceConfig,
    VLLMNsysConfig,
    VLLMServerConfig,
    VLLMWatchdogConfig,
    parse_vllm_config,
)
from peek.plugins.vllm.health import (
    get_vllm_server_manager,
    install_vllm,
    uninstall_vllm,
)
from peek.plugins.vllm.manager import VLLMServerManager

__all__ = [
    "VLLMConfig",
    "VLLMServerConfig",
    "VLLMNsysConfig",
    "VLLMWatchdogConfig",
    "VLLMInferenceConfig",
    "parse_vllm_config",
    "VLLMServerManager",
    "install_vllm",
    "uninstall_vllm",
    "get_vllm_server_manager",
]
