# Copyright 2024 The peek Authors.
# Licensed under the MIT License.

"""Process resource collector module.

Provides unified interface for collecting process metrics including
CPU, memory, GPU, and VRAM usage.
"""

import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from collections import deque

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False


@dataclass
class GPUStats:
    """GPU statistics for a single GPU device.

    Attributes:
        index: GPU device index.
        name: GPU device name.
        utilization_percent: GPU utilization percentage (0-100).
        memory_used_mb: Used GPU memory in MB.
        memory_total_mb: Total GPU memory in MB.
        memory_percent: GPU memory usage percentage.
        temperature: GPU temperature in Celsius.
        power_usage_w: Power usage in watts.
    """

    index: int = 0
    name: str = ""
    utilization_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    memory_percent: float = 0.0
    temperature: Optional[float] = None
    power_usage_w: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "name": self.name,
            "utilization_percent": self.utilization_percent,
            "memory_used_mb": self.memory_used_mb,
            "memory_total_mb": self.memory_total_mb,
            "memory_percent": self.memory_percent,
            "temperature": self.temperature,
            "power_usage_w": self.power_usage_w,
        }


@dataclass
class ProcessStats:
    """Process statistics snapshot.

    Attributes:
        timestamp: Timestamp of the snapshot.
        pid: Process ID.
        name: Process name.
        cpu_percent: CPU usage percentage.
        cpu_count: Number of CPU cores.
        memory_mb: Memory usage in MB.
        memory_percent: Memory usage percentage.
        memory_rss_mb: Resident Set Size in MB.
        memory_vms_mb: Virtual Memory Size in MB.
        num_threads: Number of threads.
        num_fds: Number of file descriptors.
        io_read_mb: IO read in MB.
        io_write_mb: IO write in MB.
        gpu_stats: List of GPU statistics.
    """

    timestamp: datetime = field(default_factory=datetime.now)
    pid: int = 0
    name: str = ""
    cpu_percent: float = 0.0
    cpu_count: int = 1
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    num_threads: int = 0
    num_fds: int = 0
    io_read_mb: float = 0.0
    io_write_mb: float = 0.0
    gpu_stats: List[GPUStats] = field(default_factory=list)

    @property
    def total_gpu_memory_mb(self) -> float:
        """Total GPU memory used across all GPUs."""
        return sum(g.memory_used_mb for g in self.gpu_stats)

    @property
    def avg_gpu_utilization(self) -> float:
        """Average GPU utilization across all GPUs."""
        if not self.gpu_stats:
            return 0.0
        return sum(g.utilization_percent for g in self.gpu_stats) / len(self.gpu_stats)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "pid": self.pid,
            "name": self.name,
            "cpu_percent": self.cpu_percent,
            "cpu_count": self.cpu_count,
            "memory_mb": self.memory_mb,
            "memory_percent": self.memory_percent,
            "memory_rss_mb": self.memory_rss_mb,
            "memory_vms_mb": self.memory_vms_mb,
            "num_threads": self.num_threads,
            "num_fds": self.num_fds,
            "io_read_mb": self.io_read_mb,
            "io_write_mb": self.io_write_mb,
            "gpu_stats": [g.to_dict() for g in self.gpu_stats],
            "total_gpu_memory_mb": self.total_gpu_memory_mb,
            "avg_gpu_utilization": self.avg_gpu_utilization,
        }


@dataclass
class MonitorConfig:
    """Monitor configuration.

    Attributes:
        interval: Sampling interval in seconds.
        history_size: Maximum number of samples to keep in history.
        enable_gpu: Enable GPU monitoring.
        enable_io: Enable IO monitoring.
        gpu_indices: List of GPU indices to monitor (None for all).
    """

    interval: float = 1.0
    history_size: int = 3600  # 1 hour at 1s interval
    enable_gpu: bool = True
    enable_io: bool = True
    gpu_indices: Optional[List[int]] = None


class GPUMonitor:
    """GPU monitoring using NVIDIA Management Library (NVML).

    This class provides GPU metrics collection including utilization,
    memory usage, temperature, and power consumption.
    """

    def __init__(self, gpu_indices: Optional[List[int]] = None):
        """Initialize GPU monitor.

        Args:
            gpu_indices: List of GPU indices to monitor. None for all GPUs.
        """
        self._initialized = False
        self._device_count = 0
        self._gpu_indices = gpu_indices
        self._handles: Dict[int, Any] = {}

        if HAS_PYNVML:
            self._init_nvml()

    def _init_nvml(self) -> None:
        """Initialize NVML library."""
        try:
            pynvml.nvmlInit()
            self._device_count = pynvml.nvmlDeviceGetCount()
            self._initialized = True

            # Get device handles
            indices = self._gpu_indices or range(self._device_count)
            for i in indices:
                if i < self._device_count:
                    self._handles[i] = pynvml.nvmlDeviceGetHandleByIndex(i)
        except Exception:
            self._initialized = False

    def is_available(self) -> bool:
        """Check if GPU monitoring is available."""
        return self._initialized and self._device_count > 0

    def get_device_count(self) -> int:
        """Get number of GPU devices."""
        return self._device_count

    def get_stats(self, pid: Optional[int] = None) -> List[GPUStats]:
        """Get GPU statistics.

        Args:
            pid: Process ID for per-process GPU stats. None for system-wide.

        Returns:
            List of GPUStats for each monitored GPU.
        """
        if not self._initialized:
            return []

        stats = []
        for idx, handle in self._handles.items():
            try:
                gpu_stat = self._get_device_stats(idx, handle, pid)
                stats.append(gpu_stat)
            except Exception:
                continue

        return stats

    def _get_device_stats(
        self, idx: int, handle: Any, pid: Optional[int] = None
    ) -> GPUStats:
        """Get statistics for a single GPU device."""
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")

        # Get utilization
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            utilization_percent = util.gpu
        except Exception:
            utilization_percent = 0.0

        # Get memory info
        try:
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_total_mb = mem_info.total / (1024 * 1024)
            memory_used_mb = mem_info.used / (1024 * 1024)
            memory_percent = (mem_info.used / mem_info.total) * 100
        except Exception:
            memory_total_mb = 0.0
            memory_used_mb = 0.0
            memory_percent = 0.0

        # Get per-process memory if pid specified
        if pid is not None:
            try:
                procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                for proc in procs:
                    if proc.pid == pid:
                        memory_used_mb = proc.usedGpuMemory / (1024 * 1024)
                        memory_percent = (proc.usedGpuMemory / mem_info.total) * 100
                        break
                else:
                    # Process not using this GPU
                    memory_used_mb = 0.0
                    memory_percent = 0.0
            except Exception:
                pass

        # Get temperature
        try:
            temperature = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
        except Exception:
            temperature = None

        # Get power usage
        try:
            power_usage_w = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
        except Exception:
            power_usage_w = None

        return GPUStats(
            index=idx,
            name=name,
            utilization_percent=utilization_percent,
            memory_used_mb=memory_used_mb,
            memory_total_mb=memory_total_mb,
            memory_percent=memory_percent,
            temperature=temperature,
            power_usage_w=power_usage_w,
        )

    def shutdown(self) -> None:
        """Shutdown NVML library."""
        if self._initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._initialized = False

    def __del__(self):
        """Cleanup on deletion."""
        self.shutdown()


class ProcessMonitor:
    """Process resource monitor.

    Monitors CPU, memory, GPU, and IO usage of a process.

    Example:
        >>> monitor = ProcessMonitor(pid=os.getpid())
        >>> monitor.start()
        >>> time.sleep(5)
        >>> monitor.stop()
        >>> for stats in monitor.history:
        ...     print(f"CPU: {stats.cpu_percent}%")
    """

    def __init__(
        self,
        pid: Optional[int] = None,
        config: Optional[MonitorConfig] = None,
    ):
        """Initialize process monitor.

        Args:
            pid: Process ID to monitor. None for current process.
            config: Monitor configuration.
        """
        self._pid = pid or os.getpid()
        self._config = config or MonitorConfig()
        self._process: Optional[Any] = None
        self._gpu_monitor: Optional[GPUMonitor] = None
        self._history: deque = deque(maxlen=self._config.history_size)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[ProcessStats], None]] = []

        if not HAS_PSUTIL:
            raise ImportError(
                "psutil is required for process monitoring. "
                "Install it with: pip install psutil"
            )

        self._init_process()

        if self._config.enable_gpu:
            self._gpu_monitor = GPUMonitor(self._config.gpu_indices)

    def _init_process(self) -> None:
        """Initialize psutil Process object."""
        try:
            self._process = psutil.Process(self._pid)
            # Warm up CPU percent calculation
            self._process.cpu_percent()
        except psutil.NoSuchProcess:
            raise ValueError(f"Process with PID {self._pid} not found")

    @property
    def pid(self) -> int:
        """Get monitored process ID."""
        return self._pid

    @property
    def is_running(self) -> bool:
        """Check if monitoring is running."""
        return self._running

    @property
    def history(self) -> List[ProcessStats]:
        """Get monitoring history."""
        with self._lock:
            return list(self._history)

    @property
    def gpu_available(self) -> bool:
        """Check if GPU monitoring is available."""
        return self._gpu_monitor is not None and self._gpu_monitor.is_available()

    def add_callback(self, callback: Callable[[ProcessStats], None]) -> None:
        """Add callback to be called on each sample.

        Args:
            callback: Function to call with ProcessStats.
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[ProcessStats], None]) -> None:
        """Remove a callback.

        Args:
            callback: Callback function to remove.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def snapshot(self) -> ProcessStats:
        """Take a single snapshot of process stats.

        Returns:
            ProcessStats with current metrics.
        """
        if self._process is None:
            raise RuntimeError("Process not initialized")

        try:
            # Get process info
            with self._process.oneshot():
                cpu_percent = self._process.cpu_percent()
                mem_info = self._process.memory_info()
                mem_percent = self._process.memory_percent()
                num_threads = self._process.num_threads()

                try:
                    num_fds = self._process.num_fds()
                except (psutil.AccessDenied, AttributeError):
                    num_fds = 0

                # IO counters
                io_read_mb = 0.0
                io_write_mb = 0.0
                if self._config.enable_io:
                    try:
                        io_counters = self._process.io_counters()
                        io_read_mb = io_counters.read_bytes / (1024 * 1024)
                        io_write_mb = io_counters.write_bytes / (1024 * 1024)
                    except (psutil.AccessDenied, AttributeError):
                        pass

            # Get GPU stats
            gpu_stats = []
            if self._gpu_monitor and self._config.enable_gpu:
                gpu_stats = self._gpu_monitor.get_stats(pid=self._pid)

            stats = ProcessStats(
                timestamp=datetime.now(),
                pid=self._pid,
                name=self._process.name(),
                cpu_percent=cpu_percent,
                cpu_count=psutil.cpu_count() or 1,
                memory_mb=mem_info.rss / (1024 * 1024),
                memory_percent=mem_percent,
                memory_rss_mb=mem_info.rss / (1024 * 1024),
                memory_vms_mb=mem_info.vms / (1024 * 1024),
                num_threads=num_threads,
                num_fds=num_fds,
                io_read_mb=io_read_mb,
                io_write_mb=io_write_mb,
                gpu_stats=gpu_stats,
            )

            return stats

        except psutil.NoSuchProcess:
            raise RuntimeError(f"Process {self._pid} no longer exists")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                stats = self.snapshot()

                with self._lock:
                    self._history.append(stats)

                # Call callbacks
                for callback in self._callbacks:
                    try:
                        callback(stats)
                    except Exception:
                        pass

                time.sleep(self._config.interval)

            except Exception:
                if self._running:
                    time.sleep(self._config.interval)

    def start(self) -> None:
        """Start background monitoring."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def clear_history(self) -> None:
        """Clear monitoring history."""
        with self._lock:
            self._history.clear()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics from history.

        Returns:
            Dictionary with min, max, avg for each metric.
        """
        history = self.history
        if not history:
            return {}

        cpu_values = [s.cpu_percent for s in history]
        mem_values = [s.memory_mb for s in history]
        gpu_util_values = [s.avg_gpu_utilization for s in history]
        gpu_mem_values = [s.total_gpu_memory_mb for s in history]

        def calc_stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"min": 0, "max": 0, "avg": 0}
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }

        return {
            "samples": len(history),
            "duration_seconds": (
                (history[-1].timestamp - history[0].timestamp).total_seconds()
                if len(history) > 1
                else 0
            ),
            "cpu_percent": calc_stats(cpu_values),
            "memory_mb": calc_stats(mem_values),
            "gpu_utilization": calc_stats(gpu_util_values),
            "gpu_memory_mb": calc_stats(gpu_mem_values),
        }

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


@dataclass
class MultiProcessStats:
    """Statistics snapshot for multiple processes.

    Attributes:
        timestamp: Timestamp of the snapshot.
        process_stats: Dictionary mapping PID to ProcessStats.
    """

    timestamp: datetime = field(default_factory=datetime.now)
    process_stats: Dict[int, ProcessStats] = field(default_factory=dict)

    @property
    def total_cpu_percent(self) -> float:
        """Total CPU usage across all processes."""
        return sum(s.cpu_percent for s in self.process_stats.values())

    @property
    def total_memory_mb(self) -> float:
        """Total memory usage across all processes."""
        return sum(s.memory_mb for s in self.process_stats.values())

    @property
    def total_gpu_memory_mb(self) -> float:
        """Total GPU memory usage across all processes."""
        return sum(s.total_gpu_memory_mb for s in self.process_stats.values())

    @property
    def avg_gpu_utilization(self) -> float:
        """Average GPU utilization (from all processes' perspective)."""
        gpu_utils = [s.avg_gpu_utilization for s in self.process_stats.values() if s.gpu_stats]
        if not gpu_utils:
            return 0.0
        return sum(gpu_utils) / len(gpu_utils)

    @property
    def pids(self) -> List[int]:
        """List of monitored PIDs."""
        return list(self.process_stats.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_cpu_percent": self.total_cpu_percent,
            "total_memory_mb": self.total_memory_mb,
            "total_gpu_memory_mb": self.total_gpu_memory_mb,
            "avg_gpu_utilization": self.avg_gpu_utilization,
            "processes": {pid: stats.to_dict() for pid, stats in self.process_stats.items()},
        }


class MultiProcessMonitor:
    """Monitor multiple processes simultaneously.

    Monitors CPU, memory, GPU, and IO usage of multiple processes
    and provides aggregated statistics.

    Example:
        >>> monitor = MultiProcessMonitor(pids=[1234, 5678, 9012])
        >>> monitor.start()
        >>> time.sleep(10)
        >>> monitor.stop()
        >>> for stats in monitor.history:
        ...     print(f"Total CPU: {stats.total_cpu_percent}%")
        ...     for pid, proc_stats in stats.process_stats.items():
        ...         print(f"  PID {pid}: {proc_stats.cpu_percent}%")
    """

    def __init__(
        self,
        pids: List[int],
        config: Optional[MonitorConfig] = None,
    ):
        """Initialize multi-process monitor.

        Args:
            pids: List of process IDs to monitor.
            config: Monitor configuration.
        """
        if not pids:
            raise ValueError("At least one PID is required")

        self._pids = list(pids)
        self._config = config or MonitorConfig()
        self._monitors: Dict[int, ProcessMonitor] = {}
        self._history: deque = deque(maxlen=self._config.history_size)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[MultiProcessStats], None]] = []

        # Initialize monitors for each PID
        self._init_monitors()

    def _init_monitors(self) -> None:
        """Initialize ProcessMonitor for each PID."""
        # Create a shared GPU monitor to avoid multiple NVML initializations
        shared_gpu_monitor = None
        if self._config.enable_gpu:
            shared_gpu_monitor = GPUMonitor(self._config.gpu_indices)

        failed_pids = []
        for pid in self._pids:
            try:
                monitor = ProcessMonitor(pid=pid, config=self._config)
                # Share GPU monitor to avoid redundant initialization
                if shared_gpu_monitor:
                    monitor._gpu_monitor = shared_gpu_monitor
                self._monitors[pid] = monitor
            except (ValueError, psutil.NoSuchProcess) as e:
                failed_pids.append((pid, str(e)))

        if failed_pids:
            msg = ", ".join(f"PID {pid}: {err}" for pid, err in failed_pids)
            if not self._monitors:
                raise ValueError(f"All processes failed to initialize: {msg}")
            print(f"⚠️  Warning: Some processes could not be monitored: {msg}")

    @property
    def pids(self) -> List[int]:
        """Get list of monitored PIDs."""
        return list(self._monitors.keys())

    @property
    def is_running(self) -> bool:
        """Check if monitoring is running."""
        return self._running

    @property
    def history(self) -> List[MultiProcessStats]:
        """Get monitoring history."""
        with self._lock:
            return list(self._history)

    @property
    def gpu_available(self) -> bool:
        """Check if GPU monitoring is available."""
        for monitor in self._monitors.values():
            if monitor.gpu_available:
                return True
        return False

    def add_callback(self, callback: Callable[[MultiProcessStats], None]) -> None:
        """Add callback to be called on each sample."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[MultiProcessStats], None]) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def snapshot(self) -> MultiProcessStats:
        """Take a single snapshot of all process stats.

        Returns:
            MultiProcessStats with current metrics for all processes.
        """
        process_stats = {}
        dead_pids = []

        for pid, monitor in self._monitors.items():
            try:
                stats = monitor.snapshot()
                process_stats[pid] = stats
            except (psutil.NoSuchProcess, RuntimeError):
                dead_pids.append(pid)

        # Remove dead processes
        for pid in dead_pids:
            del self._monitors[pid]

        return MultiProcessStats(
            timestamp=datetime.now(),
            process_stats=process_stats,
        )

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running and self._monitors:
            try:
                stats = self.snapshot()

                with self._lock:
                    self._history.append(stats)

                # Call callbacks
                for callback in self._callbacks:
                    try:
                        callback(stats)
                    except Exception:
                        pass

                time.sleep(self._config.interval)

            except Exception:
                if self._running:
                    time.sleep(self._config.interval)

    def start(self) -> None:
        """Start background monitoring."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def clear_history(self) -> None:
        """Clear monitoring history."""
        with self._lock:
            self._history.clear()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics from history.

        Returns:
            Dictionary with aggregated stats and per-process breakdown.
        """
        history = self.history
        if not history:
            return {}

        # Aggregated stats
        total_cpu = [s.total_cpu_percent for s in history]
        total_mem = [s.total_memory_mb for s in history]
        total_gpu_mem = [s.total_gpu_memory_mb for s in history]
        avg_gpu_util = [s.avg_gpu_utilization for s in history]

        def calc_stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"min": 0, "max": 0, "avg": 0}
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }

        # Per-process stats
        per_process = {}
        all_pids = set()
        for stats in history:
            all_pids.update(stats.pids)

        for pid in all_pids:
            cpu_values = []
            mem_values = []
            gpu_mem_values = []
            proc_name = ""

            for stats in history:
                if pid in stats.process_stats:
                    proc_stats = stats.process_stats[pid]
                    cpu_values.append(proc_stats.cpu_percent)
                    mem_values.append(proc_stats.memory_mb)
                    gpu_mem_values.append(proc_stats.total_gpu_memory_mb)
                    proc_name = proc_stats.name

            per_process[pid] = {
                "name": proc_name,
                "cpu_percent": calc_stats(cpu_values),
                "memory_mb": calc_stats(mem_values),
                "gpu_memory_mb": calc_stats(gpu_mem_values),
            }

        return {
            "samples": len(history),
            "process_count": len(all_pids),
            "duration_seconds": (
                (history[-1].timestamp - history[0].timestamp).total_seconds()
                if len(history) > 1
                else 0
            ),
            "total": {
                "cpu_percent": calc_stats(total_cpu),
                "memory_mb": calc_stats(total_mem),
                "gpu_memory_mb": calc_stats(total_gpu_mem),
                "gpu_utilization": calc_stats(avg_gpu_util),
            },
            "per_process": per_process,
        }

    def get_per_process_history(self) -> Dict[int, List[ProcessStats]]:
        """Get history organized by process.

        Returns:
            Dictionary mapping PID to list of ProcessStats.
        """
        result: Dict[int, List[ProcessStats]] = {}
        for stats in self.history:
            for pid, proc_stats in stats.process_stats.items():
                if pid not in result:
                    result[pid] = []
                result[pid].append(proc_stats)
        return result

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
