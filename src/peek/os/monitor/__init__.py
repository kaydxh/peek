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
"""

from peek.os.monitor.collector import (
    ProcessMonitor,
    ProcessStats,
    GPUStats,
    MonitorConfig,
)
from peek.os.monitor.visualizer import (
    MonitorVisualizer,
    RealtimeChart,
)

__all__ = [
    "ProcessMonitor",
    "ProcessStats",
    "GPUStats",
    "MonitorConfig",
    "MonitorVisualizer",
    "RealtimeChart",
]
