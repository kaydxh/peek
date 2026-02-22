#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2024 The peek Authors.
# Licensed under the MIT License.

"""Monitor Service - 进程资源监控服务

提供通用的进程资源监控管理能力，包括：
1. 按需快照（snapshot）— 实时获取 CPU、内存、GPU、显存使用情况
2. 持续后台采集（start/stop）— 后台定时采集并记录历史
3. 统计摘要（summary）— 获取采集期间的 min/max/avg 统计
4. 报告生成（report）— 生成 HTML/JSON 格式的可视化报告

该模块不依赖 tide 框架，可以被任何 Python 项目使用。

API 端点（通过 register_monitor_routes 注册）：
- GET  /debug/monitor/snapshot  - 获取实时资源快照
- GET  /debug/monitor/summary   - 获取持续采集的统计摘要
- POST /debug/monitor/start     - 启动持续采集
- POST /debug/monitor/stop      - 停止持续采集
- GET  /debug/monitor/report    - 生成 HTML/JSON 监控报告

Example:
    >>> from peek.os.monitor import MonitorService, MonitorServiceConfig
    >>> config = MonitorServiceConfig(enable_gpu=True, include_children=True)
    >>> service = MonitorService(config)
    >>> snapshot = service.snapshot()
    >>> print(f"CPU: {snapshot['total']['cpu_percent']}%")

    >>> # 注册到 FastAPI
    >>> from peek.os.monitor import register_monitor_routes
    >>> register_monitor_routes(app, service)
"""

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from peek.os.monitor.collector import (
    MonitorConfig,
    MultiProcessMonitor,
    ProcessMonitor,
)

logger = logging.getLogger(__name__)


@dataclass
class MonitorServiceConfig:
    """监控服务配置。

    Attributes:
        enabled: 是否启用监控服务。
        auto_start: 是否在初始化后自动开始持续采集。
        interval: 采集间隔（秒），仅持续采集模式有效。
        enable_gpu: 是否启用 GPU 监控（需要 pynvml）。
        include_children: 是否监控子进程。
        history_size: 历史记录最大条数。
    """

    enabled: bool = False
    auto_start: bool = False
    interval: float = 5.0
    enable_gpu: bool = True
    include_children: bool = True
    history_size: int = 3600


class MonitorService:
    """进程资源监控服务

    提供进程监控的生命周期管理，支持：
    - 按需快照（snapshot）
    - 持续后台采集（start/stop）
    - 统计摘要和报告生成

    该类不依赖任何 Web 框架，可以在纯 Python 环境中使用。
    HTTP API 通过 register_monitor_routes() 函数注册。

    Example:
        >>> config = MonitorServiceConfig(enable_gpu=True, interval=5.0)
        >>> service = MonitorService(config)
        >>> # 按需快照
        >>> result = service.snapshot()
        >>> # 持续采集
        >>> service.start_collecting()
        >>> # ... 等待一段时间 ...
        >>> summary = service.get_summary()
        >>> service.stop_collecting()
    """

    def __init__(self, config: MonitorServiceConfig):
        """初始化监控服务。

        Args:
            config: 监控服务配置。
        """
        self.config = config
        self._monitor = None  # MultiProcessMonitor 或 ProcessMonitor 实例
        self._is_collecting = False  # 是否正在持续采集
        self._lock = threading.Lock()
        self._pids: List[int] = []
        self._monitor_config = None  # peek MonitorConfig

    def _get_monitored_pids(self) -> List[int]:
        """获取需要监控的进程 PID 列表。

        包括主进程和子进程（递归发现）。

        Returns:
            PID 列表
        """
        pids = [os.getpid()]  # 主进程

        if self.config.include_children:
            try:
                import psutil

                main_process = psutil.Process(os.getpid())
                children = main_process.children(recursive=True)
                for child in children:
                    try:
                        if child.is_running():
                            pids.append(child.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except ImportError:
                logger.warning("psutil 未安装，无法监控子进程")
            except Exception as e:
                logger.warning(f"获取子进程列表失败: {e}")

        return pids

    def _ensure_monitor(self, force_refresh: bool = False) -> None:
        """确保监控器已初始化。

        当 PID 列表发生变化或首次初始化时，会创建新的监控器。

        Args:
            force_refresh: 是否强制刷新（重新获取子进程列表）
        """
        current_pids = self._get_monitored_pids()

        # 如果 PID 列表变化了或者还没初始化，则重新创建监控器
        if (
            self._monitor is None
            or force_refresh
            or set(current_pids) != set(self._pids)
        ):
            self._pids = current_pids
            self._monitor_config = MonitorConfig(
                interval=self.config.interval,
                history_size=self.config.history_size,
                enable_gpu=self.config.enable_gpu,
                enable_io=True,
            )

            if len(self._pids) > 1:
                try:
                    self._monitor = MultiProcessMonitor(
                        pids=self._pids,
                        config=self._monitor_config,
                    )
                    logger.debug(f"多进程监控器已创建: pids={self._pids}")
                except Exception as e:
                    logger.error(f"创建多进程监控器失败: {e}")
                    # 退回到单进程监控
                    self._monitor = ProcessMonitor(
                        pid=os.getpid(),
                        config=self._monitor_config,
                    )
                    self._pids = [os.getpid()]
            else:
                self._monitor = ProcessMonitor(
                    pid=self._pids[0],
                    config=self._monitor_config,
                )

    @property
    def is_collecting(self) -> bool:
        """是否正在持续采集。"""
        return self._is_collecting

    @property
    def pids(self) -> List[int]:
        """当前被监控的 PID 列表。"""
        return list(self._pids)

    def snapshot(self) -> Dict[str, Any]:
        """获取实时资源快照。

        Returns:
            包含所有进程资源使用情况的字典，结构如下：
            {
                "timestamp": "...",
                "pids": [...],
                "is_collecting": bool,
                "total": {"cpu_percent": ..., "memory_mb": ..., ...},
                "processes": {pid: {...}, ...}
            }
        """
        with self._lock:
            self._ensure_monitor()

        try:
            stats = self._monitor.snapshot()
            result = {
                "timestamp": datetime.now().isoformat(),
                "pids": self._pids,
                "is_collecting": self._is_collecting,
            }

            if hasattr(stats, "process_stats"):
                # MultiProcessStats
                result["total"] = {
                    "cpu_percent": stats.total_cpu_percent,
                    "memory_mb": stats.total_memory_mb,
                    "gpu_memory_mb": stats.total_gpu_memory_mb,
                    "gpu_utilization": stats.avg_gpu_utilization,
                }
                result["processes"] = {}
                for pid, proc_stats in stats.process_stats.items():
                    result["processes"][pid] = proc_stats.to_dict()
            else:
                # ProcessStats
                result["total"] = {
                    "cpu_percent": stats.cpu_percent,
                    "memory_mb": stats.memory_mb,
                    "gpu_memory_mb": stats.total_gpu_memory_mb,
                    "gpu_utilization": stats.avg_gpu_utilization,
                }
                result["processes"] = {stats.pid: stats.to_dict()}

            return result

        except Exception as e:
            logger.error(f"获取资源快照失败: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "pids": self._pids,
                "is_collecting": self._is_collecting,
            }

    def start_collecting(self) -> Dict[str, Any]:
        """启动持续采集。

        Returns:
            操作结果字典
        """
        with self._lock:
            if self._is_collecting:
                return {
                    "status": "already_running",
                    "message": "持续采集已在运行中",
                    "pids": self._pids,
                }

            # 强制刷新以获取最新子进程列表
            self._ensure_monitor(force_refresh=True)

            try:
                self._monitor.start()
                self._is_collecting = True
                logger.info(
                    f"持续采集已启动: pids={self._pids}, "
                    f"interval={self.config.interval}s"
                )
                return {
                    "status": "started",
                    "message": f"持续采集已启动，采集间隔 {self.config.interval}s",
                    "pids": self._pids,
                    "interval": self.config.interval,
                }
            except Exception as e:
                logger.error(f"启动持续采集失败: {e}")
                return {
                    "status": "error",
                    "message": f"启动失败: {e}",
                }

    def stop_collecting(self) -> Dict[str, Any]:
        """停止持续采集。

        Returns:
            操作结果字典（包含摘要统计）
        """
        with self._lock:
            if not self._is_collecting:
                return {
                    "status": "not_running",
                    "message": "持续采集未在运行",
                }

            try:
                self._monitor.stop()
                self._is_collecting = False

                # 返回摘要
                summary = self._monitor.get_summary()
                logger.info("持续采集已停止")
                return {
                    "status": "stopped",
                    "message": "持续采集已停止",
                    "summary": summary,
                }
            except Exception as e:
                logger.error(f"停止持续采集失败: {e}")
                self._is_collecting = False
                return {
                    "status": "error",
                    "message": f"停止失败: {e}",
                }

    def get_summary(self) -> Dict[str, Any]:
        """获取持续采集的统计摘要。

        Returns:
            统计摘要信息字典
        """
        if self._monitor is None:
            return {
                "status": "not_initialized",
                "message": "监控器尚未初始化，请先进行快照或启动采集",
            }

        try:
            summary = self._monitor.get_summary()
            if not summary:
                return {
                    "status": "no_data",
                    "message": "暂无采集数据",
                    "is_collecting": self._is_collecting,
                }

            return {
                "status": "ok",
                "is_collecting": self._is_collecting,
                "pids": self._pids,
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"获取统计摘要失败: {e}")
            return {
                "status": "error",
                "message": str(e),
            }

    def generate_report(self, format: str = "html") -> Optional[str]:
        """生成监控报告。

        Args:
            format: 报告格式，支持 "html" 和 "json"

        Returns:
            报告内容字符串，如果没有数据则返回 None
        """
        if self._monitor is None:
            return None

        history = self._monitor.history
        if not history:
            return None

        try:
            if hasattr(history[0], "process_stats"):
                # 多进程报告
                from peek.os.monitor.visualizer import MultiProcessVisualizer

                visualizer = MultiProcessVisualizer(history)
            else:
                # 单进程报告
                from peek.os.monitor.visualizer import MonitorVisualizer

                visualizer = MonitorVisualizer(history)

            if format == "json":
                # 直接将历史数据序列化为 JSON
                return json.dumps(
                    [s.to_dict() for s in history],
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
            else:
                # HTML 报告
                return visualizer.generate_html_report()

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return None

    def shutdown(self) -> None:
        """关闭监控服务，释放资源。"""
        if self._is_collecting:
            try:
                self._monitor.stop()
            except Exception:
                pass
            self._is_collecting = False

        self._monitor = None
        logger.info("监控服务已关闭")


def register_monitor_routes(app, service: MonitorService) -> None:
    """将监控 API 路由注册到 FastAPI 应用。

    注册以下端点：
    - GET  /debug/monitor/snapshot  - 获取实时资源快照
    - GET  /debug/monitor/summary   - 获取持续采集的统计摘要
    - POST /debug/monitor/start     - 启动持续采集
    - POST /debug/monitor/stop      - 停止持续采集
    - GET  /debug/monitor/report    - 生成 HTML/JSON 监控报告

    Args:
        app: FastAPI 应用实例（或任何支持 @app.get/@app.post 的路由对象）
        service: MonitorService 实例

    Example:
        >>> from fastapi import FastAPI
        >>> from peek.os.monitor import MonitorService, MonitorServiceConfig, register_monitor_routes
        >>> app = FastAPI()
        >>> config = MonitorServiceConfig(enabled=True)
        >>> service = MonitorService(config)
        >>> register_monitor_routes(app, service)
    """
    from fastapi import Response
    from fastapi.responses import HTMLResponse, JSONResponse

    @app.get("/debug/monitor/snapshot")
    async def monitor_snapshot():
        """获取实时资源快照

        返回当前所有被监控进程的 CPU、内存、GPU、显存使用情况。
        """
        result = service.snapshot()
        return JSONResponse(content=result)

    @app.get("/debug/monitor/summary")
    async def monitor_summary():
        """获取持续采集的统计摘要

        返回持续采集期间的最小值、最大值、平均值等统计信息。
        """
        result = service.get_summary()
        return JSONResponse(content=result)

    @app.post("/debug/monitor/start")
    async def monitor_start():
        """启动持续采集

        开始后台持续采集进程资源使用数据。
        """
        result = service.start_collecting()
        return JSONResponse(content=result)

    @app.post("/debug/monitor/stop")
    async def monitor_stop():
        """停止持续采集

        停止后台持续采集，返回采集期间的统计摘要。
        """
        result = service.stop_collecting()
        return JSONResponse(content=result)

    @app.get("/debug/monitor/report")
    async def monitor_report(format: str = "html"):
        """生成监控报告

        根据持续采集的数据生成可视化报告。

        Args:
            format: 报告格式，支持 html（默认）和 json
        """
        if format not in ("html", "json"):
            return JSONResponse(
                status_code=400,
                content={"error": f"不支持的格式: {format}，支持 html 和 json"},
            )

        report = service.generate_report(format=format)
        if report is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "暂无监控数据，请先启动持续采集并等待一段时间"
                },
            )

        if format == "json":
            return Response(content=report, media_type="application/json")
        else:
            return HTMLResponse(content=report)

    logger.info(
        "监控 API 路由已注册: "
        "GET /debug/monitor/snapshot, "
        "GET /debug/monitor/summary, "
        "POST /debug/monitor/start, "
        "POST /debug/monitor/stop, "
        "GET /debug/monitor/report"
    )
