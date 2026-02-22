# Copyright 2024 The peek Authors.
# Licensed under the MIT License.

"""Process monitoring module.

This module provides tools for monitoring process resources including:
- CPU usage
- Memory usage
- GPU utilization
- GPU memory (VRAM)

Example:
    >>> from peek.os.monitor import ProcessMonitor
    >>> monitor = ProcessMonitor(pid=1234)
    >>> stats = monitor.snapshot()
    >>> print(f"CPU: {stats.cpu_percent}%, Memory: {stats.memory_mb} MB")

    >>> # Monitor multiple processes
    >>> from peek.os.monitor import MultiProcessMonitor
    >>> monitor = MultiProcessMonitor(pids=[1234, 5678])
    >>> monitor.start()
"""

from peek.os.monitor.collector import (
    ProcessMonitor,
    ProcessStats,
    GPUStats,
    MonitorConfig,
    MultiProcessMonitor,
    MultiProcessStats,
)
from peek.os.monitor.visualizer import (
    MonitorVisualizer,
    RealtimeChart,
    MultiProcessVisualizer,
    MultiProcessRealtimeChart,
)
from peek.os.monitor.service import (
    MonitorService,
    MonitorServiceConfig,
    register_monitor_routes,
)

__all__ = [
    "ProcessMonitor",
    "ProcessStats",
    "GPUStats",
    "MonitorConfig",
    "MonitorVisualizer",
    "RealtimeChart",
    "MultiProcessMonitor",
    "MultiProcessStats",
    "MultiProcessVisualizer",
    "MultiProcessRealtimeChart",
    "MonitorService",
    "MonitorServiceConfig",
    "register_monitor_routes",
]
