#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
peek.plugins.vllm - vLLM server management and configuration

Provides:
1. VLLMConfig dataclass - vLLM common configuration
2. VLLMServerManager - vLLM Server process manager
3. install_vllm / uninstall_vllm / get_vllm_server_manager - functional interface
4. parse_vllm_config - configuration parsing utility
"""

from peek.plugins.vllm.config import VLLMConfig, parse_vllm_config
from peek.plugins.vllm.manager import VLLMServerManager
from peek.plugins.vllm.health import (
    install_vllm,
    uninstall_vllm,
    get_vllm_server_manager,
)

__all__ = [
    "VLLMConfig",
    "parse_vllm_config",
    "VLLMServerManager",
    "install_vllm",
    "uninstall_vllm",
    "get_vllm_server_manager",
]
