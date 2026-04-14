#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vLLM Server process manager.

Handles starting, stopping, monitoring (watchdog), and health checking
of the vLLM server subprocess.
"""

import asyncio
import atexit
import json
import logging
import os
import signal
import subprocess
import time
from typing import Optional

import httpx

from peek.plugins.vllm.config import VLLMConfig

logger = logging.getLogger(__name__)


class VLLMServerManager:
    """vLLM Server process manager.

    Responsible for starting, stopping and monitoring the vLLM server process.
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

        # nsys 相关状态
        self._nsys_start_time: float = 0
        self._nsys_collection_done: bool = False

        # 注册退出清理
        atexit.register(self._cleanup_on_exit)

    def _cleanup_on_exit(self):
        """Clean up vLLM server process on program exit"""
        if self.process:
            logger.info("Program exiting, stopping vLLM server...")
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except Exception as e:
                logger.error("Error stopping vLLM server on exit: %s", e)

    async def start(self) -> None:
        """Start vLLM server process"""
        if self.process is not None:
            logger.warning("vLLM server is already running")
            return

        cmd = self._build_vllm_command()

        logger.info("Starting vLLM server, command: %s", " ".join(cmd))

        try:
            env = os.environ.copy()

            # 记录 nsys 启动时间，用于看门狗判断 nsys 采集是否结束
            if self.config.nsys_enabled:
                self._nsys_start_time = time.time()
                self._nsys_collection_done = False
                nsys_total = self.config.nsys_delay + self.config.nsys_duration
                logger.info(
                    "[nsys] Estimated collection completion: %ds "
                    "(delay=%ds + duration=%ds)",
                    nsys_total,
                    self.config.nsys_delay,
                    self.config.nsys_duration,
                )

            self.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=False,
                bufsize=0,
                preexec_fn=os.setsid,
            )

            logger.info("vLLM server started, PID: %s", self.process.pid)

            self.log_task = asyncio.create_task(self._log_vllm_output())

        except FileNotFoundError:
            logger.error(
                "vLLM command not found! Please install vLLM:\n"
                "  pip install vllm\n"
                "or set auto_start=false and start vLLM server manually"
            )
            raise RuntimeError(
                "vLLM command not found, please install vLLM (pip install vllm) "
                "or set auto_start=false"
            )
        except Exception as e:
            logger.error("Failed to start vLLM server: %s", e, exc_info=True)
            raise RuntimeError(f"vLLM server failed to start: {e}")

    def _build_vllm_command(self) -> list:
        """Build vLLM startup command.

        When nsys_enabled=True, wraps vLLM with nsys profile for GPU profiling.
        """
        cmd = []

        # nsys 性能分析包裹
        if self.config.nsys_enabled:
            logger.info(
                "[nsys] Enabling nsys profile wrapper for vLLM process: "
                "trace=%s, delay=%ds, duration=%ds, output=%s",
                self.config.nsys_trace,
                self.config.nsys_delay,
                self.config.nsys_duration,
                self.config.nsys_output,
            )
            cmd += [
                "nsys",
                "profile",
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
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
            "--served-model-name",
            self.config.model_name,
            "--gpu-memory-utilization",
            str(self.config.gpu_memory_utilization),
            "--max-model-len",
            str(self.config.max_model_len),
            "--tensor-parallel-size",
            str(self.config.tensor_parallel_size),
        ]

        # runner 类型（如 pooling 用于分类模型）
        if self.config.runner:
            cmd += ["--runner", self.config.runner]

        # 信任远程代码
        if self.config.trust_remote_code:
            cmd.append("--trust-remote-code")

        # HuggingFace 模型配置覆盖
        if self.config.hf_overrides:
            try:
                hf_overrides_str = json.dumps(
                    self.config.hf_overrides, separators=(",", ":")
                )
                cmd += ["--hf-overrides", hf_overrides_str]
            except (TypeError, ValueError) as e:
                logger.error(
                    "Invalid hf_overrides: %s, error: %s", self.config.hf_overrides, e
                )

        if self.config.dtype and self.config.dtype != "auto":
            cmd += ["--dtype", self.config.dtype]

        # 以下参数仅在非 pooling runner 模式下添加（pooling 模式不需要这些生成相关参数）
        is_pooling = self.config.runner == "pooling"

        if not is_pooling:
            cmd += [
                "--max-num-batched-tokens",
                str(self.config.max_num_batched_tokens),
                "--max-num-seqs",
                str(self.config.max_num_seqs),
            ]

        # 多模态处理器参数（视频帧采样等）
        if self.config.mm_processor_kwargs:
            try:
                mm_kwargs_str = json.dumps(
                    self.config.mm_processor_kwargs, separators=(",", ":")
                )
                cmd += ["--mm-processor-kwargs", mm_kwargs_str]
            except (TypeError, ValueError) as e:
                logger.error(
                    "Invalid mm_processor_kwargs: %s, error: %s",
                    self.config.mm_processor_kwargs,
                    e,
                )

        # 媒体IO参数（视频帧数控制等），仅在非 pooling 模式下添加
        if not is_pooling:
            if self.config.media_io_kwargs:
                try:
                    media_io_str = json.dumps(
                        self.config.media_io_kwargs, separators=(",", ":")
                    )
                    cmd += ["--media-io-kwargs", media_io_str]
                except (TypeError, ValueError) as e:
                    logger.error(
                        "Invalid media_io_kwargs: %s, error: %s",
                        self.config.media_io_kwargs,
                        e,
                    )
            else:
                # 默认：使用所有视频帧（-1 表示不限制帧数）
                cmd += ["--media-io-kwargs", '{"video":{"num_frames":-1}}']

        if not is_pooling and self.config.enable_prefix_caching:
            cmd.append("--enable-prefix-caching")

        if not is_pooling and self.config.enable_chunked_prefill:
            cmd.append("--enable-chunked-prefill")

        return cmd

    async def _log_vllm_output(self) -> None:
        """Stream and log vLLM server output"""
        if not self.process:
            return

        try:
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            transport, _ = await asyncio.get_running_loop().connect_read_pipe(
                lambda: protocol, self.process.stdout
            )

            try:
                while self.process and self.process.poll() is None:
                    try:
                        line = await asyncio.wait_for(reader.readline(), timeout=1.0)
                        if line:
                            line_str = line.decode("utf-8", errors="replace").strip()
                            logger.info("[vLLM] %s", line_str)
                        else:
                            break
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        logger.debug("vLLM log reader task cancelled")
                        break
            finally:
                transport.close()
        except asyncio.CancelledError:
            logger.debug("vLLM log reader task cancelled")
        except Exception as e:
            logger.error("Error reading vLLM output: %s", e, exc_info=True)

    async def wait_for_ready(self, timeout: Optional[int] = None) -> None:
        """Wait for vLLM server to become ready.

        Args:
            timeout: Timeout in seconds, defaults to config's startup_timeout
        """
        if timeout is None:
            timeout = self.config.startup_timeout

        logger.info("Waiting for vLLM server to be ready (timeout: %ds)...", timeout)
        logger.info("Model loading may take several minutes, please be patient...")

        start_time = time.time()
        last_log_time = start_time

        while time.time() - start_time < timeout:
            if self.process and self.process.poll() is not None:
                exit_code = self.process.returncode
                logger.error(
                    "vLLM server process terminated unexpectedly, exit code: %s",
                    exit_code,
                )
                raise RuntimeError(
                    f"vLLM server process terminated, exit code: {exit_code}"
                )

            try:
                if await self._check_server_ready():
                    elapsed = time.time() - start_time
                    logger.info("vLLM server is ready! Elapsed: %.1fs", elapsed)
                    return
            except Exception as e:
                logger.debug("vLLM server readiness check failed: %s", e)

            current_time = time.time()
            if current_time - last_log_time >= 30:
                elapsed = current_time - start_time
                remaining = timeout - elapsed
                logger.info(
                    "Still waiting for vLLM server... "
                    "(elapsed: %.0fs, remaining: %.0fs)",
                    elapsed,
                    remaining,
                )
                last_log_time = current_time

            await asyncio.sleep(2)

        logger.error("vLLM server startup timed out (%ds)", timeout)
        raise TimeoutError(f"vLLM server did not become ready within {timeout}s")

    async def _check_server_ready(self) -> bool:
        """Check if vLLM server is ready"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._api_url}/models")
                if response.status_code == 200:
                    data = response.json()
                    model_names = [model["id"] for model in data.get("data", [])]
                    is_ready = self.config.model_name in model_names
                    if not is_ready:
                        logger.debug(
                            "Model %s not ready yet, available models: %s",
                            self.config.model_name,
                            model_names,
                        )
                    return is_ready
                else:
                    logger.debug(
                        "vLLM server returned status code: %s", response.status_code
                    )
                    return False
        except Exception as e:
            logger.debug("Failed to check vLLM server readiness: %s", e)
            return False

    async def health_check(self) -> bool:
        """Health check"""
        if self.process and self.process.poll() is not None:
            logger.warning(
                "vLLM process has terminated, exit code: %s", self.process.returncode
            )
            return False

        # 如果进程为 None 且 auto_start 为 True，也视为不健康
        if self.process is None and self.config.auto_start:
            logger.warning("vLLM process is None, auto_start is enabled")
            return False

        return await self._check_server_ready()

    async def inference_probe(self, timeout: Optional[float] = None) -> bool:
        """Inference-level probe: send a lightweight inference request to detect engine health.

        Detects issues where vLLM server process is alive and /health is OK,
        but the inference engine is stuck (e.g. GPU OOM, KV Cache exhaustion, Scheduler deadlock).

        Args:
            timeout: Inference request timeout in seconds, defaults to config's inference_probe_timeout

        Returns:
            True if inference engine is healthy, False if abnormal (timeout or error)
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
                        "[InferenceProbe] Probe returned abnormal status code: %s",
                        response.status_code,
                    )
                    return False
        except httpx.TimeoutException:
            logger.warning(
                "[InferenceProbe] Probe timed out (%ss), engine may be stuck",
                timeout,
            )
            return False
        except Exception as e:
            logger.warning(
                "[InferenceProbe] Probe error: %s: %s",
                type(e).__name__,
                e,
            )
            return False

    # -----------------------------------------------------------------------
    # Watchdog: periodically check vLLM process status, auto-restart on failure
    # Only enabled when auto_start=True and auto_restart=True
    # -----------------------------------------------------------------------

    async def start_watchdog(self, mark_ready: bool = False) -> None:
        """Start watchdog background task.

        Args:
            mark_ready: If True, mark vLLM as ready immediately so watchdog starts monitoring;
                       if False, watchdog waits until mark_as_ready() is called.
        """
        if not self.config.auto_start:
            logger.info("auto_start is not enabled, skipping watchdog")
            return
        if not self.config.auto_restart:
            logger.info("auto_restart is not enabled, skipping watchdog")
            return
        if self._watchdog_task is not None:
            logger.warning("Watchdog is already running")
            return

        if mark_ready:
            self._ready = True

        self._watchdog_enabled = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info(
            "vLLM watchdog started (interval: %ds, max_restarts: %d, "
            "cooldown: %ds, ready: %s)",
            self.config.watchdog_interval,
            self.config.max_restart_attempts,
            self.config.restart_cooldown,
            self._ready,
        )

    def mark_as_ready(self) -> None:
        """Mark vLLM as ready, watchdog will start monitoring process status"""
        self._ready = True
        logger.info("[Watchdog] vLLM marked as ready, watchdog will begin monitoring")

    async def stop_watchdog(self) -> None:
        """Stop watchdog background task"""
        self._watchdog_enabled = False
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
            logger.info("vLLM watchdog stopped")

    async def _watchdog_loop(self) -> None:
        """Watchdog main loop: periodically check vLLM process and inference engine.

        Checks two levels:
        1. Process level: check if vLLM process is alive (process.poll())
        2. Inference level: send lightweight probe to detect stuck engine (inference_probe)
        """
        # 等待 vLLM 首次就绪后再开始检查
        while self._watchdog_enabled and not self._ready:
            await asyncio.sleep(self.config.watchdog_interval)
            logger.debug(
                "[Watchdog] vLLM not ready yet, skipping check (startup phase)"
            )

        logger.info("[Watchdog] vLLM is ready, starting process monitoring")
        self._inference_probe_failures = 0

        while self._watchdog_enabled:
            try:
                await asyncio.sleep(self.config.watchdog_interval)

                # 正在重启中（包括模型加载阶段），跳过本次检查
                if self._restarting:
                    logger.debug("[Watchdog] Restart in progress, skipping check")
                    continue

                # ---- 第 1 层：进程级别检查 ----
                if self.process is None:
                    logger.warning(
                        "[Watchdog] vLLM process is None, attempting auto-restart..."
                    )
                    await self._try_restart()
                    continue

                if self.process.poll() is not None:
                    exit_code = self.process.returncode

                    # nsys 模式特殊处理：采集完成后切换回普通模式重启
                    if self.config.nsys_enabled and not self._nsys_collection_done:
                        nsys_handled = await self._handle_nsys_completion(exit_code)
                        if nsys_handled:
                            continue

                    logger.error(
                        "[Watchdog] vLLM process has terminated! Exit code: %s, "
                        "attempting auto-restart...",
                        exit_code,
                    )
                    await self._try_restart()
                    continue

                # ---- 第 2 层：推理级别探活 ----
                if self.config.inference_probe_enabled:
                    probe_ok = await self.inference_probe()
                    if probe_ok:
                        if self._inference_probe_failures > 0:
                            logger.info(
                                "[Watchdog] Inference probe recovered, "
                                "previous consecutive failures: %d",
                                self._inference_probe_failures,
                            )
                        self._inference_probe_failures = 0
                    else:
                        self._inference_probe_failures += 1
                        logger.warning(
                            "[Watchdog] Inference probe failed (consecutive %d/%d)",
                            self._inference_probe_failures,
                            self.config.inference_probe_max_failures,
                        )
                        if (
                            self._inference_probe_failures
                            >= self.config.inference_probe_max_failures
                        ):
                            logger.error(
                                "[Watchdog] Inference probe failed %d consecutive times, "
                                "engine may be stuck, force-restarting vLLM server...",
                                self._inference_probe_failures,
                            )
                            self._inference_probe_failures = 0
                            await self._try_restart()
                            continue

            except asyncio.CancelledError:
                logger.info("[Watchdog] Watchdog task cancelled")
                break
            except Exception as e:
                logger.error("[Watchdog] Watchdog check error: %s", e, exc_info=True)

    async def _handle_nsys_completion(self, exit_code: int) -> bool:
        """Handle nsys collection completion when vLLM process terminates.

        Checks whether nsys profiling has finished. If so, collects the report
        and restarts vLLM in normal mode (without nsys). If the process terminated
        before nsys collection was expected to finish, logs a warning and returns
        False so the caller can proceed with a normal restart.

        Args:
            exit_code: The exit code of the terminated vLLM process

        Returns:
            True if nsys completion was handled (caller should continue/skip),
            False if nsys collection was not yet complete (caller should proceed
            with normal restart logic).
        """
        elapsed = time.time() - self._nsys_start_time
        nsys_total = self.config.nsys_delay + self.config.nsys_duration

        if elapsed < nsys_total:
            # nsys 采集尚未完成就终止了，交给正常重启流程处理
            logger.warning(
                "[Watchdog][nsys] vLLM process terminated during nsys collection "
                "(ran %.0fs / expected %ds), exit code: %s",
                elapsed,
                nsys_total,
                exit_code,
            )
            return False

        # nsys 采集已完成，收集报告并切换到普通模式重启
        self._nsys_collection_done = True
        nsys_report_path = f"{self.config.nsys_output}.nsys-rep"
        logger.info(
            "[Watchdog][nsys] Collection finished (%.0fs), "
            "waiting for report file: %s",
            elapsed,
            nsys_report_path,
        )
        await asyncio.sleep(15)

        if os.path.exists(nsys_report_path):
            file_size = os.path.getsize(nsys_report_path)
            logger.info(
                "[Watchdog][nsys] Report generated: %s (%.1f MB)",
                nsys_report_path,
                file_size / 1024 / 1024,
            )
        else:
            logger.warning(
                "[Watchdog][nsys] Report not found: %s, "
                "check nsys installation and output path permissions",
                nsys_report_path,
            )

        logger.info(
            "[Watchdog][nsys] Collection complete, restarting vLLM server (without nsys)..."
        )
        self.config.nsys_enabled = False
        self.process = None
        if self.log_task:
            self.log_task.cancel()
            self.log_task = None
        await self.start()
        await self.wait_for_ready()
        self._ready = True
        self._restart_count = 0
        logger.info("[Watchdog][nsys] vLLM server restarted (normal mode, no nsys)")
        return True

    async def _try_restart(self) -> None:
        """Attempt to restart vLLM server (with rate limiting and max restart protection)"""
        now = time.time()

        # 冷却检查
        if now - self._last_restart_time < self.config.restart_cooldown:
            remaining = self.config.restart_cooldown - (now - self._last_restart_time)
            logger.warning("[Watchdog] Restart cooling down, retry in %.0fs", remaining)
            return

        # 连续重启次数检查
        if self._restart_count >= self.config.max_restart_attempts:
            logger.error(
                "[Watchdog] Max restart attempts reached (%d), "
                "stopping auto-restart, please investigate manually!",
                self.config.max_restart_attempts,
            )
            self._watchdog_enabled = False
            return

        # 标记正在重启
        self._restarting = True
        self._restart_count += 1
        self._last_restart_time = now

        logger.info(
            "[Watchdog] Restart attempt %d/%d for vLLM server...",
            self._restart_count,
            self.config.max_restart_attempts,
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

            # 重新启动
            await self.start()
            await self.wait_for_ready()

            self._ready = True
            self._restart_count = 0
            logger.info("[Watchdog] vLLM server restarted successfully")

        except Exception as e:
            logger.error("[Watchdog] Restart failed: %s", e, exc_info=True)
        finally:
            self._restarting = False

    async def stop(self) -> None:
        """Stop vLLM server process"""
        # 先停止看门狗，避免停止进程后被自动重启
        await self.stop_watchdog()

        # 反注册 atexit 回调，解除强引用，避免实例无法被 GC 回收
        atexit.unregister(self._cleanup_on_exit)

        if self.process is None:
            return

        logger.info("Stopping vLLM server...")

        if self.log_task:
            self.log_task.cancel()
            self.log_task = None

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

            try:
                self.process.wait(timeout=10)
                logger.info("vLLM server stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("vLLM server did not stop gracefully, force-killing...")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()
                logger.info("vLLM server force-killed")
        except Exception as e:
            logger.error("Error stopping vLLM server: %s", e, exc_info=True)
        finally:
            self.process = None
