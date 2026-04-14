#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vLLM configuration data classes and parsing utilities.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class VLLMConfig:
    """vLLM common service configuration.

    Each cmd can use this dataclass directly, overriding defaults
    via parse_vllm_config's defaults parameter for different scenarios.
    """

    # vLLM server configuration
    enabled: bool = False
    host: str = "localhost"
    port: int = 8000
    api_key: str = ""

    # 是否自动启动 vLLM server
    auto_start: bool = False

    # 模型配置
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    model_path: str = "Qwen/Qwen2.5-7B-Instruct"

    # 生成参数
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9

    # 请求超时配置
    timeout: int = 60

    # vLLM server 启动参数（仅当 auto_start=True 时有效）
    runner: str = (
        ""  # vLLM runner 类型，如 "pooling"（分类模型），留空则使用默认 generate runner
    )
    trust_remote_code: bool = False  # 是否信任远程代码
    hf_overrides: Optional[Dict[str, Any]] = None  # HuggingFace 模型配置覆盖
    gpu_memory_utilization: float = 0.9
    tensor_parallel_size: int = 1
    max_num_seqs: int = 256
    max_num_batched_tokens: int = 8192
    max_model_len: int = 4096
    dtype: str = "auto"
    startup_timeout: int = (
        600  # vLLM server 启动超时时间（单位：秒），默认 600s（10 分钟）
    )
    enable_prefix_caching: bool = True
    enable_chunked_prefill: bool = True

    # 多模态处理参数
    mm_processor_kwargs: Optional[Dict[str, Any]] = None
    media_io_kwargs: Optional[Dict[str, Any]] = None

    # 扩展配置（各 cmd 可通过此字段传递特有配置）
    logprobs: bool = True
    top_logprobs: int = 10
    seed: int = 42
    scene_cls_threshold: float = 0.1
    max_concurrent_requests: int = 4

    # 视频解码配置
    video_decode: Optional[Dict[str, Any]] = None

    # nsys 性能分析配置（仅当 auto_start=True 时有效）
    nsys_enabled: bool = False
    nsys_output: str = "/app/log/vllm_nsys_report"
    nsys_trace: str = "cuda,nvtx"
    nsys_delay: int = 30
    nsys_duration: int = 60

    # 自动重启配置（仅当 auto_start=True 时有效）
    auto_restart: bool = True
    watchdog_interval: int = 10
    max_restart_attempts: int = 3
    restart_cooldown: int = 60

    # 推理探活配置（检测 vLLM 推理引擎是否卡死）
    inference_probe_enabled: bool = True
    inference_probe_timeout: int = 30
    inference_probe_max_failures: int = 3


def parse_vllm_config(
    data: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
) -> VLLMConfig:
    """Parse vLLM configuration.

    Args:
        data: Raw configuration dict (usually from YAML vllm section)
        defaults: Optional default value overrides for cmd-specific customization

    Returns:
        VLLMConfig instance
    """
    # 合并默认值：先用 VLLMConfig 字段默认值，再用 cmd 传入的 defaults 覆盖，最后用实际配置覆盖
    defs = {
        "enabled": False,
        "host": "localhost",
        "port": 8000,
        "api_key": "",
        "auto_start": False,
        "model_name": "Qwen/Qwen2.5-7B-Instruct",
        "model_path": "Qwen/Qwen2.5-7B-Instruct",
        "max_tokens": 2048,
        "temperature": 0.7,
        "top_p": 0.9,
        "timeout": 60,
        "runner": "",
        "trust_remote_code": False,
        "hf_overrides": None,
        "gpu_memory_utilization": 0.9,
        "tensor_parallel_size": 1,
        "max_num_seqs": 256,
        "max_num_batched_tokens": 8192,
        "max_model_len": 4096,
        "dtype": "auto",
        "startup_timeout": 600,
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "mm_processor_kwargs": None,
        "media_io_kwargs": None,
        "logprobs": True,
        "top_logprobs": 10,
        "seed": 42,
        "scene_cls_threshold": 0.1,
        "max_concurrent_requests": 4,
        "video_decode": None,
        "nsys_enabled": False,
        "nsys_output": "/app/log/vllm_nsys_report",
        "nsys_trace": "cuda,nvtx",
        "nsys_delay": 30,
        "nsys_duration": 60,
        "auto_restart": True,
        "watchdog_interval": 10,
        "max_restart_attempts": 3,
        "restart_cooldown": 60,
        "inference_probe_enabled": True,
        "inference_probe_timeout": 30,
        "inference_probe_max_failures": 3,
    }
    if defaults:
        defs.update(defaults)

    logger.info(
        "Parsing vLLM config: model_name=%s, model_path=%s, host=%s, port=%s, auto_start=%s",
        data.get("model_name", "unset"),
        data.get("model_path", "unset"),
        data.get("host", "unset"),
        data.get("port", "unset"),
        data.get("auto_start", "unset"),
    )
    # nsys 配置调试日志
    logger.info(
        "Parsing vLLM nsys config: nsys_enabled=%s (type=%s), nsys_output=%s, "
        "nsys_trace=%s, nsys_delay=%s, nsys_duration=%s",
        data.get("nsys_enabled", "unset"),
        type(data.get("nsys_enabled")).__name__,
        data.get("nsys_output", "unset"),
        data.get("nsys_trace", "unset"),
        data.get("nsys_delay", "unset"),
        data.get("nsys_duration", "unset"),
    )

    return VLLMConfig(
        enabled=data.get("enabled", defs["enabled"]),
        host=data.get("host", defs["host"]),
        port=data.get("port", defs["port"]),
        api_key=data.get("api_key", defs["api_key"]),
        auto_start=data.get("auto_start", defs["auto_start"]),
        model_name=data.get("model_name", defs["model_name"]),
        model_path=data.get("model_path", defs["model_path"]),
        max_tokens=data.get("max_tokens", defs["max_tokens"]),
        temperature=data.get("temperature", defs["temperature"]),
        top_p=data.get("top_p", defs["top_p"]),
        timeout=data.get("timeout", defs["timeout"]),
        runner=data.get("runner", defs["runner"]),
        trust_remote_code=data.get("trust_remote_code", defs["trust_remote_code"]),
        hf_overrides=data.get("hf_overrides", defs["hf_overrides"]),
        gpu_memory_utilization=data.get(
            "gpu_memory_utilization", defs["gpu_memory_utilization"]
        ),
        tensor_parallel_size=data.get(
            "tensor_parallel_size", defs["tensor_parallel_size"]
        ),
        max_num_seqs=data.get("max_num_seqs", defs["max_num_seqs"]),
        max_num_batched_tokens=data.get(
            "max_num_batched_tokens", defs["max_num_batched_tokens"]
        ),
        max_model_len=data.get("max_model_len", defs["max_model_len"]),
        dtype=data.get("dtype", defs["dtype"]),
        startup_timeout=data.get("startup_timeout", defs["startup_timeout"]),
        enable_prefix_caching=data.get(
            "enable_prefix_caching", defs["enable_prefix_caching"]
        ),
        enable_chunked_prefill=data.get(
            "enable_chunked_prefill", defs["enable_chunked_prefill"]
        ),
        mm_processor_kwargs=data.get(
            "mm_processor_kwargs", defs["mm_processor_kwargs"]
        ),
        media_io_kwargs=data.get("media_io_kwargs", defs["media_io_kwargs"]),
        logprobs=data.get("logprobs", defs["logprobs"]),
        top_logprobs=data.get("top_logprobs", defs["top_logprobs"]),
        seed=data.get("seed", defs["seed"]),
        scene_cls_threshold=data.get(
            "scene_cls_threshold", defs["scene_cls_threshold"]
        ),
        max_concurrent_requests=data.get(
            "max_concurrent_requests", defs["max_concurrent_requests"]
        ),
        video_decode=data.get("video_decode", defs["video_decode"]),
        auto_restart=data.get("auto_restart", defs["auto_restart"]),
        watchdog_interval=data.get("watchdog_interval", defs["watchdog_interval"]),
        max_restart_attempts=data.get(
            "max_restart_attempts", defs["max_restart_attempts"]
        ),
        restart_cooldown=data.get("restart_cooldown", defs["restart_cooldown"]),
        inference_probe_enabled=data.get(
            "inference_probe_enabled", defs["inference_probe_enabled"]
        ),
        inference_probe_timeout=data.get(
            "inference_probe_timeout", defs["inference_probe_timeout"]
        ),
        inference_probe_max_failures=data.get(
            "inference_probe_max_failures", defs["inference_probe_max_failures"]
        ),
        nsys_enabled=data.get("nsys_enabled", defs["nsys_enabled"]),
        nsys_output=data.get("nsys_output", defs["nsys_output"]),
        nsys_trace=data.get("nsys_trace", defs["nsys_trace"]),
        nsys_delay=data.get("nsys_delay", defs["nsys_delay"]),
        nsys_duration=data.get("nsys_duration", defs["nsys_duration"]),
    )
