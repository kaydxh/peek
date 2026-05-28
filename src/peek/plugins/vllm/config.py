#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vLLM configuration data classes and parsing utilities.

配置按职责拆分为子配置：
- VLLMServerConfig: vLLM 引擎启动参数
- VLLMNsysConfig: nsys 性能分析配置
- VLLMWatchdogConfig: 自动重启和探活配置
- VLLMInferenceConfig: 推理参数配置
- VLLMConfig: 顶层配置（组合所有子配置）
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class VLLMServerConfig:
    """vLLM 引擎启动参数（仅当 auto_start=True 时有效）"""

    runner: str = ""  # vLLM runner 类型，如 "pooling"（分类模型），留空则使用默认 generate runner
    trust_remote_code: bool = False  # 是否信任远程代码
    hf_overrides: Optional[Dict[str, Any]] = None  # HuggingFace 模型配置覆盖
    gpu_memory_utilization: float = 0.9
    tensor_parallel_size: int = 1
    max_num_seqs: int = 256
    max_num_batched_tokens: int = 8192
    max_model_len: int = 4096
    dtype: str = "auto"
    startup_timeout: int = 600  # vLLM server 启动超时时间（单位：秒）
    enable_prefix_caching: bool = True
    enable_chunked_prefill: bool = True
    # 多模态处理参数
    mm_processor_kwargs: Optional[Dict[str, Any]] = None
    media_io_kwargs: Optional[Dict[str, Any]] = None


@dataclass
class VLLMNsysConfig:
    """nsys 性能分析配置（仅当 auto_start=True 时有效）"""

    enabled: bool = False
    output: str = "/app/log/vllm_nsys_report"
    trace: str = "cuda,nvtx"
    delay: int = 30
    duration: int = 60


@dataclass
class VLLMWatchdogConfig:
    """自动重启和推理探活配置（仅当 auto_start=True 时有效）"""

    auto_restart: bool = True
    watchdog_interval: int = 10
    max_restart_attempts: int = 3
    restart_cooldown: int = 60
    # 推理探活配置（检测 vLLM 推理引擎是否卡死）
    inference_probe_enabled: bool = True
    inference_probe_timeout: int = 30
    inference_probe_max_failures: int = 3


@dataclass
class VLLMInferenceConfig:
    """推理参数配置（各 cmd 可通过此字段传递特有配置）"""

    logprobs: bool = True
    top_logprobs: int = 10
    seed: int = 42
    scene_cls_threshold: float = 0.1
    max_concurrent_requests: int = 4
    # 视频解码配置
    video_decode: Optional[Dict[str, Any]] = None


@dataclass
class VLLMConfig:
    """vLLM 顶层配置

    组合所有子配置，同时保留 flat 属性访问以向后兼容。
    Each cmd can use this dataclass directly, overriding defaults
    via parse_vllm_config's defaults parameter for different scenarios.
    """

    # 基础连接配置
    enabled: bool = False
    host: str = "localhost"
    port: int = 8000
    api_key: str = ""
    auto_start: bool = False

    # 模型配置
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    model_path: str = "Qwen/Qwen2.5-7B-Instruct"

    # 生成参数
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    timeout: int = 60

    # 子配置（按职责分组）
    server: VLLMServerConfig = field(default_factory=VLLMServerConfig)
    nsys: VLLMNsysConfig = field(default_factory=VLLMNsysConfig)
    watchdog: VLLMWatchdogConfig = field(default_factory=VLLMWatchdogConfig)
    inference: VLLMInferenceConfig = field(default_factory=VLLMInferenceConfig)

    # ========== 向后兼容属性（代理到子配置） ==========
    # 以下 property 保证现有代码 self.config.xxx 的访问方式不变

    # --- VLLMServerConfig 代理 ---
    @property
    def runner(self) -> str:
        return self.server.runner

    @runner.setter
    def runner(self, value: str):
        self.server.runner = value

    @property
    def trust_remote_code(self) -> bool:
        return self.server.trust_remote_code

    @trust_remote_code.setter
    def trust_remote_code(self, value: bool):
        self.server.trust_remote_code = value

    @property
    def hf_overrides(self) -> Optional[Dict[str, Any]]:
        return self.server.hf_overrides

    @hf_overrides.setter
    def hf_overrides(self, value: Optional[Dict[str, Any]]):
        self.server.hf_overrides = value

    @property
    def gpu_memory_utilization(self) -> float:
        return self.server.gpu_memory_utilization

    @gpu_memory_utilization.setter
    def gpu_memory_utilization(self, value: float):
        self.server.gpu_memory_utilization = value

    @property
    def tensor_parallel_size(self) -> int:
        return self.server.tensor_parallel_size

    @tensor_parallel_size.setter
    def tensor_parallel_size(self, value: int):
        self.server.tensor_parallel_size = value

    @property
    def max_num_seqs(self) -> int:
        return self.server.max_num_seqs

    @max_num_seqs.setter
    def max_num_seqs(self, value: int):
        self.server.max_num_seqs = value

    @property
    def max_num_batched_tokens(self) -> int:
        return self.server.max_num_batched_tokens

    @max_num_batched_tokens.setter
    def max_num_batched_tokens(self, value: int):
        self.server.max_num_batched_tokens = value

    @property
    def max_model_len(self) -> int:
        return self.server.max_model_len

    @max_model_len.setter
    def max_model_len(self, value: int):
        self.server.max_model_len = value

    @property
    def dtype(self) -> str:
        return self.server.dtype

    @dtype.setter
    def dtype(self, value: str):
        self.server.dtype = value

    @property
    def startup_timeout(self) -> int:
        return self.server.startup_timeout

    @startup_timeout.setter
    def startup_timeout(self, value: int):
        self.server.startup_timeout = value

    @property
    def enable_prefix_caching(self) -> bool:
        return self.server.enable_prefix_caching

    @enable_prefix_caching.setter
    def enable_prefix_caching(self, value: bool):
        self.server.enable_prefix_caching = value

    @property
    def enable_chunked_prefill(self) -> bool:
        return self.server.enable_chunked_prefill

    @enable_chunked_prefill.setter
    def enable_chunked_prefill(self, value: bool):
        self.server.enable_chunked_prefill = value

    @property
    def mm_processor_kwargs(self) -> Optional[Dict[str, Any]]:
        return self.server.mm_processor_kwargs

    @mm_processor_kwargs.setter
    def mm_processor_kwargs(self, value: Optional[Dict[str, Any]]):
        self.server.mm_processor_kwargs = value

    @property
    def media_io_kwargs(self) -> Optional[Dict[str, Any]]:
        return self.server.media_io_kwargs

    @media_io_kwargs.setter
    def media_io_kwargs(self, value: Optional[Dict[str, Any]]):
        self.server.media_io_kwargs = value

    # --- VLLMNsysConfig 代理 ---
    @property
    def nsys_enabled(self) -> bool:
        return self.nsys.enabled

    @nsys_enabled.setter
    def nsys_enabled(self, value: bool):
        self.nsys.enabled = value

    @property
    def nsys_output(self) -> str:
        return self.nsys.output

    @nsys_output.setter
    def nsys_output(self, value: str):
        self.nsys.output = value

    @property
    def nsys_trace(self) -> str:
        return self.nsys.trace

    @nsys_trace.setter
    def nsys_trace(self, value: str):
        self.nsys.trace = value

    @property
    def nsys_delay(self) -> int:
        return self.nsys.delay

    @nsys_delay.setter
    def nsys_delay(self, value: int):
        self.nsys.delay = value

    @property
    def nsys_duration(self) -> int:
        return self.nsys.duration

    @nsys_duration.setter
    def nsys_duration(self, value: int):
        self.nsys.duration = value

    # --- VLLMWatchdogConfig 代理 ---
    @property
    def auto_restart(self) -> bool:
        return self.watchdog.auto_restart

    @auto_restart.setter
    def auto_restart(self, value: bool):
        self.watchdog.auto_restart = value

    @property
    def watchdog_interval(self) -> int:
        return self.watchdog.watchdog_interval

    @watchdog_interval.setter
    def watchdog_interval(self, value: int):
        self.watchdog.watchdog_interval = value

    @property
    def max_restart_attempts(self) -> int:
        return self.watchdog.max_restart_attempts

    @max_restart_attempts.setter
    def max_restart_attempts(self, value: int):
        self.watchdog.max_restart_attempts = value

    @property
    def restart_cooldown(self) -> int:
        return self.watchdog.restart_cooldown

    @restart_cooldown.setter
    def restart_cooldown(self, value: int):
        self.watchdog.restart_cooldown = value

    @property
    def inference_probe_enabled(self) -> bool:
        return self.watchdog.inference_probe_enabled

    @inference_probe_enabled.setter
    def inference_probe_enabled(self, value: bool):
        self.watchdog.inference_probe_enabled = value

    @property
    def inference_probe_timeout(self) -> int:
        return self.watchdog.inference_probe_timeout

    @inference_probe_timeout.setter
    def inference_probe_timeout(self, value: int):
        self.watchdog.inference_probe_timeout = value

    @property
    def inference_probe_max_failures(self) -> int:
        return self.watchdog.inference_probe_max_failures

    @inference_probe_max_failures.setter
    def inference_probe_max_failures(self, value: int):
        self.watchdog.inference_probe_max_failures = value

    # --- VLLMInferenceConfig 代理 ---
    @property
    def logprobs(self) -> bool:
        return self.inference.logprobs

    @logprobs.setter
    def logprobs(self, value: bool):
        self.inference.logprobs = value

    @property
    def top_logprobs(self) -> int:
        return self.inference.top_logprobs

    @top_logprobs.setter
    def top_logprobs(self, value: int):
        self.inference.top_logprobs = value

    @property
    def seed(self) -> int:
        return self.inference.seed

    @seed.setter
    def seed(self, value: int):
        self.inference.seed = value

    @property
    def scene_cls_threshold(self) -> float:
        return self.inference.scene_cls_threshold

    @scene_cls_threshold.setter
    def scene_cls_threshold(self, value: float):
        self.inference.scene_cls_threshold = value

    @property
    def max_concurrent_requests(self) -> int:
        return self.inference.max_concurrent_requests

    @max_concurrent_requests.setter
    def max_concurrent_requests(self, value: int):
        self.inference.max_concurrent_requests = value

    @property
    def video_decode(self) -> Optional[Dict[str, Any]]:
        return self.inference.video_decode

    @video_decode.setter
    def video_decode(self, value: Optional[Dict[str, Any]]):
        self.inference.video_decode = value


def parse_vllm_config(
    data: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
) -> VLLMConfig:
    """Parse vLLM configuration.

    支持两种 YAML 格式：
    1. flat 格式（向后兼容）：所有字段平铺在 vllm 节点下
    2. 嵌套格式（推荐）：按子配置分组

    示例（嵌套格式）：
        vllm:
          enabled: true
          host: localhost
          port: 8000
          model_name: Qwen/Qwen2.5-VL-72B-Instruct
          server:
            gpu_memory_utilization: 0.9
            tensor_parallel_size: 2
          nsys:
            enabled: false
          watchdog:
            auto_restart: true
          inference:
            logprobs: true
            seed: 42

    Args:
        data: Raw configuration dict (usually from YAML vllm section)
        defaults: Optional default value overrides for cmd-specific customization

    Returns:
        VLLMConfig instance
    """
    # 合并默认值
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

    # 支持嵌套格式：从子节点中提取配置并合并到 flat 视图
    server_data = data.get("server", {})
    nsys_data = data.get("nsys", {})
    watchdog_data = data.get("watchdog", {})
    inference_data = data.get("inference", {})

    # 辅助函数：优先从 flat 取值，其次从嵌套子节点取值，最后用默认值
    def _get(key: str, nested_data: Optional[Dict] = None, nested_key: Optional[str] = None):
        """从配置中获取值，支持 flat 和嵌套两种格式"""
        if key in data:
            return data[key]
        if nested_data and (nested_key or key) in nested_data:
            return nested_data[nested_key or key]
        return defs[key]

    logger.info(
        "Parsing vLLM config: model_name=%s, model_path=%s, host=%s, port=%s, auto_start=%s",
        data.get("model_name", "unset"),
        data.get("model_path", "unset"),
        data.get("host", "unset"),
        data.get("port", "unset"),
        data.get("auto_start", "unset"),
    )
    logger.info(
        "Parsing vLLM nsys config: nsys_enabled=%s (type=%s), nsys_output=%s, "
        "nsys_trace=%s, nsys_delay=%s, nsys_duration=%s",
        data.get("nsys_enabled", nsys_data.get("enabled", "unset")),
        type(data.get("nsys_enabled", nsys_data.get("enabled"))).__name__,
        data.get("nsys_output", nsys_data.get("output", "unset")),
        data.get("nsys_trace", nsys_data.get("trace", "unset")),
        data.get("nsys_delay", nsys_data.get("delay", "unset")),
        data.get("nsys_duration", nsys_data.get("duration", "unset")),
    )

    # 构建子配置
    server_config = VLLMServerConfig(
        runner=_get("runner", server_data),
        trust_remote_code=_get("trust_remote_code", server_data),
        hf_overrides=_get("hf_overrides", server_data),
        gpu_memory_utilization=_get("gpu_memory_utilization", server_data),
        tensor_parallel_size=_get("tensor_parallel_size", server_data),
        max_num_seqs=_get("max_num_seqs", server_data),
        max_num_batched_tokens=_get("max_num_batched_tokens", server_data),
        max_model_len=_get("max_model_len", server_data),
        dtype=_get("dtype", server_data),
        startup_timeout=_get("startup_timeout", server_data),
        enable_prefix_caching=_get("enable_prefix_caching", server_data),
        enable_chunked_prefill=_get("enable_chunked_prefill", server_data),
        mm_processor_kwargs=_get("mm_processor_kwargs", server_data),
        media_io_kwargs=_get("media_io_kwargs", server_data),
    )

    nsys_config = VLLMNsysConfig(
        enabled=_get("nsys_enabled", nsys_data, "enabled"),
        output=_get("nsys_output", nsys_data, "output"),
        trace=_get("nsys_trace", nsys_data, "trace"),
        delay=_get("nsys_delay", nsys_data, "delay"),
        duration=_get("nsys_duration", nsys_data, "duration"),
    )

    watchdog_config = VLLMWatchdogConfig(
        auto_restart=_get("auto_restart", watchdog_data),
        watchdog_interval=_get("watchdog_interval", watchdog_data),
        max_restart_attempts=_get("max_restart_attempts", watchdog_data),
        restart_cooldown=_get("restart_cooldown", watchdog_data),
        inference_probe_enabled=_get("inference_probe_enabled", watchdog_data),
        inference_probe_timeout=_get("inference_probe_timeout", watchdog_data),
        inference_probe_max_failures=_get("inference_probe_max_failures", watchdog_data),
    )

    inference_config = VLLMInferenceConfig(
        logprobs=_get("logprobs", inference_data),
        top_logprobs=_get("top_logprobs", inference_data),
        seed=_get("seed", inference_data),
        scene_cls_threshold=_get("scene_cls_threshold", inference_data),
        max_concurrent_requests=_get("max_concurrent_requests", inference_data),
        video_decode=_get("video_decode", inference_data),
    )

    return VLLMConfig(
        enabled=_get("enabled"),
        host=_get("host"),
        port=_get("port"),
        api_key=_get("api_key"),
        auto_start=_get("auto_start"),
        model_name=_get("model_name"),
        model_path=_get("model_path"),
        max_tokens=_get("max_tokens"),
        temperature=_get("temperature"),
        top_p=_get("top_p"),
        timeout=_get("timeout"),
        server=server_config,
        nsys=nsys_config,
        watchdog=watchdog_config,
        inference=inference_config,
    )