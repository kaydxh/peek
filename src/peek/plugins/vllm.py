#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
peek.plugins.vllm - vLLM 服务器管理与配置

提供：
1. VLLMConfig dataclass - vLLM 通用配置
2. VLLMServerManager - vLLM Server 进程管理器
3. install_vllm / uninstall_vllm / get_vllm_server_manager - 函数式接口
4. parse_vllm_config - 配置解析工具函数
"""

import asyncio
import atexit
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, Optional, Union

import httpx

logger = logging.getLogger(__name__)


@dataclass
class VLLMConfig:
    """vLLM 通用服务配置。

    各 cmd 可直接使用此 dataclass，通过 parse_vllm_config 的 defaults 参数
    覆盖默认值以满足不同场景需求。
    """

    # vLLM 服务器配置
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
    gpu_memory_utilization: float = 0.9
    tensor_parallel_size: int = 1
    max_num_seqs: int = 256
    max_num_batched_tokens: int = 8192
    max_model_len: int = 4096
    dtype: str = "auto"
    startup_timeout: int = 600  # vLLM server 启动超时时间（单位：秒），默认 600s（10 分钟）
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
    nsys_enabled: bool = False             # 是否启用 nsys profile 包裹 vLLM 进程
    nsys_output: str = "/app/log/vllm_nsys_report"  # nsys 报告输出路径
    nsys_trace: str = "cuda,nvtx"          # nsys 追踪类型
    nsys_delay: int = 30                   # 延迟采集秒数（跳过模型加载阶段）
    nsys_duration: int = 60                # 采集持续秒数

    # 自动重启配置（仅当 auto_start=True 时有效）
    auto_restart: bool = True              # 是否启用进程看门狗自动重启
    watchdog_interval: int = 10            # 看门狗检查间隔（秒）
    max_restart_attempts: int = 3          # 最大连续重启次数
    restart_cooldown: int = 60             # 两次重启之间的冷却时间（秒）

    # 推理探活配置（检测 vLLM 推理引擎是否卡死）
    inference_probe_enabled: bool = True   # 是否启用推理级别探活
    inference_probe_timeout: int = 30      # 推理探活超时时间（单位：秒），超时视为引擎卡死
    inference_probe_max_failures: int = 3  # 连续探活失败次数达到此值后触发重启


def parse_vllm_config(
    data: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
) -> VLLMConfig:
    """解析 vLLM 配置。

    Args:
        data: 原始配置字典（通常来自 YAML 的 vllm 段）
        defaults: 可选的默认值覆盖字典，用于各 cmd 定制不同的默认值

    Returns:
        VLLMConfig 实例
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
        f"解析 vLLM 配置: model_name={data.get('model_name', '未设置')}, "
        f"model_path={data.get('model_path', '未设置')}, "
        f"host={data.get('host', '未设置')}, "
        f"port={data.get('port', '未设置')}, "
        f"auto_start={data.get('auto_start', '未设置')}"
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
        gpu_memory_utilization=data.get("gpu_memory_utilization", defs["gpu_memory_utilization"]),
        tensor_parallel_size=data.get("tensor_parallel_size", defs["tensor_parallel_size"]),
        max_num_seqs=data.get("max_num_seqs", defs["max_num_seqs"]),
        max_num_batched_tokens=data.get("max_num_batched_tokens", defs["max_num_batched_tokens"]),
        max_model_len=data.get("max_model_len", defs["max_model_len"]),
        dtype=data.get("dtype", defs["dtype"]),
        startup_timeout=data.get("startup_timeout", defs["startup_timeout"]),
        enable_prefix_caching=data.get("enable_prefix_caching", defs["enable_prefix_caching"]),
        enable_chunked_prefill=data.get("enable_chunked_prefill", defs["enable_chunked_prefill"]),
        mm_processor_kwargs=data.get("mm_processor_kwargs", defs["mm_processor_kwargs"]),
        media_io_kwargs=data.get("media_io_kwargs", defs["media_io_kwargs"]),
        logprobs=data.get("logprobs", defs["logprobs"]),
        top_logprobs=data.get("top_logprobs", defs["top_logprobs"]),
        seed=data.get("seed", defs["seed"]),
        scene_cls_threshold=data.get("scene_cls_threshold", defs["scene_cls_threshold"]),
        max_concurrent_requests=data.get("max_concurrent_requests", defs["max_concurrent_requests"]),
        video_decode=data.get("video_decode", defs["video_decode"]),
        auto_restart=data.get("auto_restart", defs["auto_restart"]),
        watchdog_interval=data.get("watchdog_interval", defs["watchdog_interval"]),
        max_restart_attempts=data.get("max_restart_attempts", defs["max_restart_attempts"]),
        restart_cooldown=data.get("restart_cooldown", defs["restart_cooldown"]),
        inference_probe_enabled=data.get("inference_probe_enabled", defs["inference_probe_enabled"]),
        inference_probe_timeout=data.get("inference_probe_timeout", defs["inference_probe_timeout"]),
        inference_probe_max_failures=data.get("inference_probe_max_failures", defs["inference_probe_max_failures"]),
        nsys_enabled=data.get("nsys_enabled", defs["nsys_enabled"]),
        nsys_output=data.get("nsys_output", defs["nsys_output"]),
        nsys_trace=data.get("nsys_trace", defs["nsys_trace"]),
        nsys_delay=data.get("nsys_delay", defs["nsys_delay"]),
        nsys_duration=data.get("nsys_duration", defs["nsys_duration"]),
    )


class VLLMServerManager:
    """vLLM Server 进程管理器

    负责启动、停止和监控 vLLM server 进程。
    """

    def __init__(self, config: VLLMConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.log_task: Optional[asyncio.Task] = None
        self._api_url = f"http://{config.host}:{config.port}/v1"

        # 看门狗相关状态
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_enabled: bool = False
        self._ready: bool = False  # vLLM 是否已完成启动并就绪
        self._restart_count: int = 0
        self._last_restart_time: float = 0
        self._restarting: bool = False  # 防止重启过程中重复触发
        self._inference_probe_failures: int = 0  # 推理探活连续失败计数

        # 注册退出清理
        atexit.register(self._cleanup_on_exit)

    def _cleanup_on_exit(self):
        """程序退出时清理 vLLM server 进程"""
        if self.process:
            logger.info("程序退出，停止 vLLM server...")
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except Exception as e:
                logger.error(f"停止 vLLM server 时出错: {e}")

    async def start(self) -> None:
        """启动 vLLM server 进程"""
        if self.process is not None:
            logger.warning("vLLM server 已经在运行中")
            return

        cmd = self._build_vllm_command()

        logger.info(f"启动 vLLM server，命令: {' '.join(cmd)}")

        try:
            env = os.environ.copy()

            self.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=False,
                bufsize=0,
                preexec_fn=os.setsid,
            )

            logger.info(f"vLLM server 已启动，PID: {self.process.pid}")

            self.log_task = asyncio.create_task(self._log_vllm_output())

        except FileNotFoundError:
            logger.error(
                "vLLM 命令未找到！请确保已安装 vLLM：\n"
                "  pip install vllm\n"
                "或者设置 auto_start=false 并手动启动 vLLM server"
            )
            raise RuntimeError(
                "vLLM 命令未找到，请先安装 vLLM (pip install vllm) "
                "或设置 auto_start=false"
            )
        except Exception as e:
            logger.error(f"启动 vLLM server 失败: {e}", exc_info=True)
            raise RuntimeError(f"vLLM server 启动失败: {e}")

    def _build_vllm_command(self) -> list:
        """构建 vLLM 启动命令

        当 nsys_enabled=True 时，使用 nsys profile 包裹 vLLM 命令，
        直接对 vLLM server 进程进行 GPU 性能分析，无需外层 nsys。
        """
        cmd = []

        # nsys 性能分析包裹
        if self.config.nsys_enabled:
            logger.info(
                f"[nsys] 启用 nsys profile 包裹 vLLM 进程: "
                f"trace={self.config.nsys_trace}, "
                f"delay={self.config.nsys_delay}s, "
                f"duration={self.config.nsys_duration}s, "
                f"output={self.config.nsys_output}"
            )
            cmd += [
                "nsys", "profile",
                f"--trace={self.config.nsys_trace}",
                "--sample=none",
                "--cpuctxsw=none",
                f"--output={self.config.nsys_output}",
                "--force-overwrite=true",
                f"--delay={self.config.nsys_delay}",
                f"--duration={self.config.nsys_duration}",
            ]

        cmd += [
            "vllm",
            "serve",
            self.config.model_path,
            "--host", self.config.host,
            "--port", str(self.config.port),
            "--served-model-name", self.config.model_name,
            "--gpu-memory-utilization", str(self.config.gpu_memory_utilization),
            "--max-num-batched-tokens", str(self.config.max_num_batched_tokens),
            "--max-num-seqs", str(self.config.max_num_seqs),
            "--max-model-len", str(self.config.max_model_len),
            "--tensor-parallel-size", str(self.config.tensor_parallel_size),
        ]

        if self.config.dtype and self.config.dtype != "auto":
            cmd += ["--dtype", self.config.dtype]

        # 多模态处理器参数（视频帧采样等）
        if self.config.mm_processor_kwargs:
            import json
            try:
                mm_kwargs_str = json.dumps(self.config.mm_processor_kwargs, separators=(",", ":"))
                cmd += ["--mm-processor-kwargs", mm_kwargs_str]
            except (TypeError, ValueError) as e:
                logger.error(f"无效的 mm_processor_kwargs: {self.config.mm_processor_kwargs}, 错误: {e}")

        # 媒体IO参数（视频帧数控制等）
        if self.config.media_io_kwargs:
            import json
            try:
                media_io_str = json.dumps(self.config.media_io_kwargs, separators=(",", ":"))
                cmd += ["--media-io-kwargs", media_io_str]
            except (TypeError, ValueError) as e:
                logger.error(f"无效的 media_io_kwargs: {self.config.media_io_kwargs}, 错误: {e}")
        else:
            # 默认：使用所有视频帧（-1 表示不限制帧数）
            cmd += ["--media-io-kwargs", '{"video":{"num_frames":-1}}']

        if self.config.enable_prefix_caching:
            cmd.append("--enable-prefix-caching")

        if self.config.enable_chunked_prefill:
            cmd.append("--enable-chunked-prefill")

        return cmd

    async def _log_vllm_output(self) -> None:
        """记录 vLLM server 输出"""
        if not self.process:
            return

        try:
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            transport, _ = await asyncio.get_event_loop().connect_read_pipe(
                lambda: protocol, self.process.stdout
            )

            try:
                while self.process and self.process.poll() is None:
                    try:
                        line = await asyncio.wait_for(reader.readline(), timeout=1.0)
                        if line:
                            line_str = line.decode("utf-8", errors="replace").strip()
                            logger.info(f"[vLLM] {line_str}")
                        else:
                            break
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        logger.debug("vLLM 日志读取任务已取消")
                        break
            finally:
                transport.close()
        except asyncio.CancelledError:
            logger.debug("vLLM 日志读取任务已取消")
        except Exception as e:
            logger.error(f"读取 vLLM 输出时出错: {e}", exc_info=True)

    async def wait_for_ready(self, timeout: Optional[int] = None) -> None:
        """等待 vLLM server 就绪

        Args:
            timeout: 超时时间（秒），默认使用配置的 startup_timeout
        """
        if timeout is None:
            timeout = self.config.startup_timeout

        logger.info(f"等待 vLLM server 就绪（超时: {timeout}s）...")
        logger.info("模型加载可能需要几分钟，请耐心等待...")

        start_time = time.time()
        last_log_time = start_time

        while time.time() - start_time < timeout:
            if self.process and self.process.poll() is not None:
                exit_code = self.process.returncode
                logger.error(f"vLLM server 进程意外终止，退出码: {exit_code}")
                raise RuntimeError(f"vLLM server 进程终止，退出码: {exit_code}")

            try:
                if await self._check_server_ready():
                    elapsed = time.time() - start_time
                    logger.info(f"vLLM server 已就绪！耗时: {elapsed:.1f}s")
                    return
            except Exception as e:
                logger.debug(f"vLLM server 就绪检查失败: {e}")

            current_time = time.time()
            if current_time - last_log_time >= 30:
                elapsed = current_time - start_time
                remaining = timeout - elapsed
                logger.info(
                    f"仍在等待 vLLM server... "
                    f"（已等待 {elapsed:.0f}s，剩余 {remaining:.0f}s）"
                )
                last_log_time = current_time

            await asyncio.sleep(2)

        logger.error(f"vLLM server 启动超时（{timeout}s）")
        raise TimeoutError(f"vLLM server 未能在 {timeout}s 内就绪")

    async def _check_server_ready(self) -> bool:
        """检查 vLLM server 是否就绪"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._api_url}/models")
                if response.status_code == 200:
                    data = response.json()
                    model_names = [model["id"] for model in data.get("data", [])]
                    is_ready = self.config.model_name in model_names
                    if not is_ready:
                        logger.debug(
                            f"模型 {self.config.model_name} 尚未就绪，"
                            f"当前可用模型: {model_names}"
                        )
                    return is_ready
                else:
                    logger.debug(f"vLLM server 返回状态码: {response.status_code}")
                    return False
        except Exception as e:
            logger.debug(f"检查 vLLM server 就绪状态失败: {e}")
            return False

    async def health_check(self) -> bool:
        """健康检查"""
        if self.process and self.process.poll() is not None:
            logger.warning(f"vLLM 进程已终止，退出码: {self.process.returncode}")
            return False

        # 如果进程为 None 且 auto_start 为 True，也视为不健康
        if self.process is None and self.config.auto_start:
            logger.warning("vLLM 进程不存在，auto_start 已启用")
            return False

        return await self._check_server_ready()

    async def inference_probe(self, timeout: Optional[float] = None) -> bool:
        """推理级别探活：发送轻量推理请求检测引擎是否正常工作

        解决 vLLM server 进程存活、/health 正常，但推理引擎卡死的问题。
        例如：GPU OOM、KV Cache 耗尽、Scheduler 死锁等场景。

        Args:
            timeout: 推理请求超时时间（秒），默认使用配置的 inference_probe_timeout

        Returns:
            True 表示推理引擎正常，False 表示引擎异常（超时或错误）
        """
        if timeout is None:
            timeout = self.config.inference_probe_timeout

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self._api_url}/chat/completions",
                    json={
                        "model": self.config.model_name,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                        "temperature": 0.0,
                    },
                )
                if response.status_code == 200:
                    return True
                else:
                    logger.warning(
                        f"[InferenceProbe] 推理探活返回异常状态码: {response.status_code}"
                    )
                    return False
        except httpx.TimeoutException:
            logger.warning(
                f"[InferenceProbe] 推理探活超时（{timeout}s），引擎可能已卡死"
            )
            return False
        except Exception as e:
            logger.warning(
                f"[InferenceProbe] 推理探活异常: {type(e).__name__}: {e}"
            )
            return False

    # -----------------------------------------------------------------------
    # Watchdog（看门狗）：定期检查 vLLM 进程状态，挂掉后自动重启
    # 仅在 auto_start=True 且 auto_restart=True 时启用
    # -----------------------------------------------------------------------

    async def start_watchdog(self, mark_ready: bool = False) -> None:
        """启动看门狗后台任务

        Args:
            mark_ready: 是否立即标记 vLLM 已就绪。
                       若为 True，看门狗将立即开始监控；
                       若为 False，看门狗会等待 mark_as_ready() 被调用后才开始检查，
                       避免在 vLLM 启动/模型加载阶段（可能需要数分钟）误触发重启。
        """
        if not self.config.auto_start:
            logger.info("auto_start 未启用，跳过看门狗")
            return
        if not self.config.auto_restart:
            logger.info("auto_restart 未启用，跳过看门狗")
            return
        if self._watchdog_task is not None:
            logger.warning("看门狗已在运行中")
            return

        if mark_ready:
            self._ready = True

        self._watchdog_enabled = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info(
            f"vLLM 看门狗已启动（检查间隔: {self.config.watchdog_interval}s，"
            f"最大重启次数: {self.config.max_restart_attempts}，"
            f"冷却时间: {self.config.restart_cooldown}s，"
            f"已就绪: {self._ready}）"
        )

    def mark_as_ready(self) -> None:
        """标记 vLLM 已完成启动并就绪，看门狗将开始监控进程状态"""
        self._ready = True
        logger.info("[Watchdog] vLLM 已标记为就绪，看门狗将开始监控")

    async def stop_watchdog(self) -> None:
        """停止看门狗后台任务"""
        self._watchdog_enabled = False
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
            logger.info("vLLM 看门狗已停止")

    async def _watchdog_loop(self) -> None:
        """看门狗主循环：定期检查 vLLM 进程和推理引擎，异常则自动重启

        检查两个层面：
        1. 进程级别：检查 vLLM 进程是否存活（process.poll()）
        2. 推理级别：发送轻量推理请求检测引擎是否卡死（inference_probe）
           - 解决 "进程活着但推理引擎 hang 住" 的问题
           - 连续 N 次探活失败后触发 kill + 重启

        注意：vLLM 启动阶段（模型加载）可能需要数分钟，
        此期间看门狗不应检查，避免误判进程异常而触发重启。
        通过 _ready 标志控制：只有 _ready=True 后才开始检查。
        """
        # 等待 vLLM 首次就绪后再开始检查
        while self._watchdog_enabled and not self._ready:
            await asyncio.sleep(self.config.watchdog_interval)
            logger.debug("[Watchdog] vLLM 尚未就绪，跳过检查（启动阶段）")

        logger.info("[Watchdog] vLLM 已就绪，开始进程监控")
        self._inference_probe_failures = 0

        while self._watchdog_enabled:
            try:
                await asyncio.sleep(self.config.watchdog_interval)

                # 正在重启中（包括模型加载阶段），跳过本次检查
                if self._restarting:
                    logger.debug("[Watchdog] 重启进行中，跳过检查")
                    continue

                # ---- 第 1 层：进程级别检查 ----
                if self.process is None:
                    logger.warning("[Watchdog] vLLM 进程为 None，尝试自动重启...")
                    await self._try_restart()
                    continue

                if self.process.poll() is not None:
                    exit_code = self.process.returncode
                    logger.error(
                        f"[Watchdog] vLLM 进程已终止！退出码: {exit_code}，"
                        f"尝试自动重启..."
                    )
                    await self._try_restart()
                    continue

                # ---- 第 2 层：推理级别探活 ----
                if self.config.inference_probe_enabled:
                    probe_ok = await self.inference_probe()
                    if probe_ok:
                        # 探活成功，重置失败计数
                        if self._inference_probe_failures > 0:
                            logger.info(
                                f"[Watchdog] 推理探活恢复正常，"
                                f"之前连续失败 {self._inference_probe_failures} 次"
                            )
                        self._inference_probe_failures = 0
                    else:
                        self._inference_probe_failures += 1
                        logger.warning(
                            f"[Watchdog] 推理探活失败（连续第 {self._inference_probe_failures}/"
                            f"{self.config.inference_probe_max_failures} 次）"
                        )
                        if self._inference_probe_failures >= self.config.inference_probe_max_failures:
                            logger.error(
                                f"[Watchdog] 推理探活连续失败 {self._inference_probe_failures} 次，"
                                f"推理引擎可能已卡死，强制重启 vLLM server..."
                            )
                            self._inference_probe_failures = 0
                            await self._try_restart()
                            continue

            except asyncio.CancelledError:
                logger.info("[Watchdog] 看门狗任务已取消")
                break
            except Exception as e:
                logger.error(f"[Watchdog] 看门狗检查异常: {e}", exc_info=True)

    async def _try_restart(self) -> None:
        """尝试重启 vLLM server（带频率限制和最大重启次数保护）"""
        now = time.time()

        # 冷却检查：距离上次重启不足冷却时间则跳过
        if now - self._last_restart_time < self.config.restart_cooldown:
            remaining = self.config.restart_cooldown - (now - self._last_restart_time)
            logger.warning(
                f"[Watchdog] 重启冷却中，{remaining:.0f}s 后可再次尝试"
            )
            return

        # 连续重启次数检查
        if self._restart_count >= self.config.max_restart_attempts:
            logger.error(
                f"[Watchdog] 连续重启已达上限（{self.config.max_restart_attempts} 次），"
                f"停止自动重启，请人工排查！"
            )
            self._watchdog_enabled = False
            return

        # 标记正在重启
        self._restarting = True
        self._restart_count += 1
        self._last_restart_time = now

        logger.info(
            f"[Watchdog] 第 {self._restart_count}/{self.config.max_restart_attempts} 次重启 vLLM server..."
        )

        try:
            # 先清理旧进程
            if self.process is not None:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    self.process.wait(timeout=5)
                except Exception:
                    pass
                self.process = None

            if self.log_task:
                self.log_task.cancel()
                self.log_task = None

            # 重新启动（重启阶段 _restarting=True，看门狗不会检查）
            await self.start()
            await self.wait_for_ready()

            # 重启成功，重置连续重启计数，标记为就绪
            self._ready = True
            self._restart_count = 0
            logger.info("[Watchdog] vLLM server 重启成功 ✅")

        except Exception as e:
            logger.error(f"[Watchdog] 重启失败: {e}", exc_info=True)
        finally:
            self._restarting = False

    async def stop(self) -> None:
        """停止 vLLM server 进程"""
        # 先停止看门狗，避免停止进程后被自动重启
        await self.stop_watchdog()

        if self.process is None:
            return

        logger.info("正在停止 vLLM server...")

        if self.log_task:
            self.log_task.cancel()
            self.log_task = None

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

            try:
                self.process.wait(timeout=10)
                logger.info("vLLM server 已优雅停止")
            except subprocess.TimeoutExpired:
                logger.warning("vLLM server 未能优雅停止，强制终止...")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()
                logger.info("vLLM server 已强制终止")
        except Exception as e:
            logger.error(f"停止 vLLM server 时出错: {e}", exc_info=True)
        finally:
            self.process = None


# ---------------------------------------------------------------------------
# 全局函数式接口
# ---------------------------------------------------------------------------

# 全局 vLLM server 管理器实例
_vllm_server_manager: Optional[VLLMServerManager] = None


def get_vllm_server_manager() -> Optional[VLLMServerManager]:
    """获取全局 vLLM server 管理器实例"""
    return _vllm_server_manager


# 注册客户端回调类型：接收 (config, server_manager) 并完成 client 创建 + provider 注册
ClientRegistrar = Callable[[VLLMConfig, Optional[VLLMServerManager]], Coroutine[Any, Any, None]]


async def install_vllm(
    config: Optional[VLLMConfig],
    register_client: Optional[ClientRegistrar] = None,
) -> None:
    """安装 vLLM 客户端（以及可选的 vLLM server）。

    通用逻辑（auto_start / server 管理）由 peek 处理；
    client 创建和 provider 注册通过 register_client 回调交由 cmd 端自定义。

    Args:
        config: vLLM 配置，为 None 或 enabled=False 则跳过
        register_client: 可选回调，用于创建 vLLM client 并注册到 provider。
                         签名: async def(config, server_manager) -> None
    """
    global _vllm_server_manager

    if config is None or not config.enabled:
        logger.info("vLLM 客户端未启用")
        return

    try:
        # 如果配置了自动启动，先启动 vLLM server
        if config.auto_start:
            logger.info("配置了 auto_start=True，正在启动 vLLM server...")
            _vllm_server_manager = VLLMServerManager(config)
            await _vllm_server_manager.start()
            await _vllm_server_manager.wait_for_ready()

            # vLLM 已就绪，启动看门狗并标记为 ready
            # mark_ready=True 表示启动阶段已完成，看门狗可立即开始监控
            await _vllm_server_manager.start_watchdog(mark_ready=True)

        # 由 cmd 端提供的回调完成 client 创建 + provider 注册
        if register_client is not None:
            await register_client(config, _vllm_server_manager)

        logger.info(
            f"vLLM 客户端已安装: host={config.host}, "
            f"port={config.port}, model={config.model_name}, "
            f"auto_start={config.auto_start}"
        )

    except Exception as e:
        logger.error(f"安装 vLLM 客户端失败: {e}")
        raise


async def uninstall_vllm():
    """卸载 vLLM（停止看门狗和 server 进程）"""
    global _vllm_server_manager

    if _vllm_server_manager:
        await _vllm_server_manager.stop()
        _vllm_server_manager = None
        logger.info("vLLM server 已停止")
