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
    startup_timeout: int = 600
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
        """构建 vLLM 启动命令"""
        cmd = [
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

        return await self._check_server_ready()

    async def stop(self) -> None:
        """停止 vLLM server 进程"""
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
    """卸载 vLLM（停止 server 进程）"""
    global _vllm_server_manager

    if _vllm_server_manager:
        await _vllm_server_manager.stop()
        _vllm_server_manager = None
        logger.info("vLLM server 已停止")
