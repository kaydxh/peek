# Copyright 2024 The peek Authors.
# Licensed under the MIT License.

"""Process monitoring visualization module.

Provides visualization tools for process metrics including:
- Real-time terminal charts
- HTML report generation
- Matplotlib-based charts
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, TextIO

from peek.os.monitor.collector import ProcessStats, ProcessMonitor

# Check for optional dependencies
try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


@dataclass
class ChartConfig:
    """Chart configuration.

    Attributes:
        width: Chart width in inches.
        height: Chart height in inches.
        dpi: Dots per inch for image output.
        style: Matplotlib style.
        colors: Color scheme for different metrics.
    """

    width: float = 12
    height: float = 8
    dpi: int = 100
    style: str = "default"
    colors: Dict[str, str] = None

    def __post_init__(self):
        if self.colors is None:
            self.colors = {
                "cpu": "#2196F3",  # Blue
                "memory": "#4CAF50",  # Green
                "gpu_util": "#FF9800",  # Orange
                "gpu_memory": "#E91E63",  # Pink
                "io_read": "#9C27B0",  # Purple
                "io_write": "#00BCD4",  # Cyan
            }


class RealtimeChart:
    """Real-time terminal-based chart display.

    Displays process metrics in terminal using ASCII characters.

    Example:
        >>> from peek.os.monitor import ProcessMonitor, RealtimeChart
        >>> monitor = ProcessMonitor()
        >>> chart = RealtimeChart(monitor)
        >>> chart.start()  # Press Ctrl+C to stop
    """

    def __init__(
        self,
        monitor: ProcessMonitor,
        refresh_interval: float = 1.0,
        output: TextIO = None,
    ):
        """Initialize real-time chart.

        Args:
            monitor: ProcessMonitor instance.
            refresh_interval: Refresh interval in seconds.
            output: Output stream (default: sys.stdout).
        """
        self._monitor = monitor
        self._refresh_interval = refresh_interval
        self._output = output or sys.stdout
        self._running = False
        self._bar_width = 50

    def _draw_bar(self, value: float, max_value: float, label: str, unit: str) -> str:
        """Draw a progress bar."""
        if max_value <= 0:
            percent = 0
        else:
            percent = min(100, (value / max_value) * 100)

        filled = int((percent / 100) * self._bar_width)
        empty = self._bar_width - filled

        bar = "█" * filled + "░" * empty
        return f"{label:12} [{bar}] {value:8.1f} {unit} ({percent:5.1f}%)"

    def _clear_screen(self) -> None:
        """Clear terminal screen."""
        if os.name == "nt":
            os.system("cls")
        else:
            self._output.write("\033[2J\033[H")
            self._output.flush()

    def _draw_frame(self, stats: ProcessStats) -> None:
        """Draw a single frame."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append(
            f" 📊 Process Monitor - PID: {stats.pid} ({stats.name})"
        )
        lines.append(f" 🕐 {stats.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)
        lines.append("")

        # CPU
        lines.append("📈 CPU")
        lines.append(
            self._draw_bar(stats.cpu_percent, 100 * stats.cpu_count, "Usage", "%")
        )
        lines.append(f"   Threads: {stats.num_threads}")
        lines.append("")

        # Memory
        lines.append("💾 Memory")
        lines.append(self._draw_bar(stats.memory_percent, 100, "Usage", "%"))
        lines.append(
            f"   RSS: {stats.memory_rss_mb:.1f} MB | VMS: {stats.memory_vms_mb:.1f} MB"
        )
        lines.append("")

        # GPU (if available)
        if stats.gpu_stats:
            lines.append("🎮 GPU")
            for gpu in stats.gpu_stats:
                lines.append(f"   [{gpu.index}] {gpu.name}")
                lines.append(
                    self._draw_bar(gpu.utilization_percent, 100, "Util", "%")
                )
                lines.append(
                    self._draw_bar(
                        gpu.memory_used_mb, gpu.memory_total_mb, "VRAM", "MB"
                    )
                )
                if gpu.temperature is not None:
                    lines.append(f"   Temperature: {gpu.temperature}°C")
                if gpu.power_usage_w is not None:
                    lines.append(f"   Power: {gpu.power_usage_w:.1f}W")
                lines.append("")

        # IO
        if stats.io_read_mb > 0 or stats.io_write_mb > 0:
            lines.append("💿 I/O")
            lines.append(f"   Read:  {stats.io_read_mb:.1f} MB")
            lines.append(f"   Write: {stats.io_write_mb:.1f} MB")
            lines.append("")

        # Footer
        lines.append("-" * 80)
        lines.append(" Press Ctrl+C to stop")

        # Output
        self._clear_screen()
        self._output.write("\n".join(lines) + "\n")
        self._output.flush()

    def start(self) -> None:
        """Start real-time display.

        Blocks until interrupted with Ctrl+C.
        """
        self._running = True
        self._monitor.start()

        try:
            while self._running:
                history = self._monitor.history
                if history:
                    self._draw_frame(history[-1])
                time.sleep(self._refresh_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            self._monitor.stop()
            self._output.write("\n\n✅ Monitoring stopped.\n")

    def stop(self) -> None:
        """Stop real-time display."""
        self._running = False


class MonitorVisualizer:
    """Process monitoring visualization.

    Generates charts and reports from monitoring data.

    Example:
        >>> from peek.os.monitor import ProcessMonitor, MonitorVisualizer
        >>> monitor = ProcessMonitor(pid=1234)
        >>> monitor.start()
        >>> time.sleep(60)
        >>> monitor.stop()
        >>> visualizer = MonitorVisualizer(monitor.history)
        >>> visualizer.save_html("report.html")
        >>> visualizer.save_charts("charts/")
    """

    def __init__(
        self,
        history: List[ProcessStats],
        config: Optional[ChartConfig] = None,
    ):
        """Initialize visualizer.

        Args:
            history: List of ProcessStats from monitoring.
            config: Chart configuration.
        """
        self._history = history
        self._config = config or ChartConfig()

    def _extract_data(self) -> Dict[str, List]:
        """Extract time series data from history."""
        timestamps = []
        cpu_percent = []
        memory_mb = []
        memory_percent = []
        gpu_util = []
        gpu_memory = []
        io_read = []
        io_write = []

        for stats in self._history:
            timestamps.append(stats.timestamp)
            cpu_percent.append(stats.cpu_percent)
            memory_mb.append(stats.memory_mb)
            memory_percent.append(stats.memory_percent)
            gpu_util.append(stats.avg_gpu_utilization)
            gpu_memory.append(stats.total_gpu_memory_mb)
            io_read.append(stats.io_read_mb)
            io_write.append(stats.io_write_mb)

        return {
            "timestamps": timestamps,
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "memory_percent": memory_percent,
            "gpu_util": gpu_util,
            "gpu_memory": gpu_memory,
            "io_read": io_read,
            "io_write": io_write,
        }

    def create_figure(self) -> Optional["Figure"]:
        """Create matplotlib figure with all metrics.

        Returns:
            Matplotlib Figure object, or None if matplotlib not available.
        """
        if not HAS_MATPLOTLIB:
            return None

        if not self._history:
            return None

        data = self._extract_data()
        colors = self._config.colors

        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(self._config.width, self._config.height))
        fig.suptitle(
            f"Process Monitor - PID: {self._history[0].pid} ({self._history[0].name})",
            fontsize=14,
            fontweight="bold",
        )

        # CPU Usage
        ax1 = axes[0, 0]
        ax1.plot(
            data["timestamps"],
            data["cpu_percent"],
            color=colors["cpu"],
            linewidth=1.5,
            label="CPU %",
        )
        ax1.set_ylabel("CPU (%)")
        ax1.set_title("CPU Usage")
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc="upper right")

        # Memory Usage
        ax2 = axes[0, 1]
        ax2.plot(
            data["timestamps"],
            data["memory_mb"],
            color=colors["memory"],
            linewidth=1.5,
            label="Memory (MB)",
        )
        ax2.set_ylabel("Memory (MB)")
        ax2.set_title("Memory Usage")
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="upper right")

        # GPU Usage
        ax3 = axes[1, 0]
        if any(v > 0 for v in data["gpu_util"]):
            ax3.plot(
                data["timestamps"],
                data["gpu_util"],
                color=colors["gpu_util"],
                linewidth=1.5,
                label="GPU Util %",
            )
            ax3_twin = ax3.twinx()
            ax3_twin.plot(
                data["timestamps"],
                data["gpu_memory"],
                color=colors["gpu_memory"],
                linewidth=1.5,
                linestyle="--",
                label="GPU Memory (MB)",
            )
            ax3.set_ylabel("GPU Utilization (%)")
            ax3_twin.set_ylabel("GPU Memory (MB)")
            ax3.legend(loc="upper left")
            ax3_twin.legend(loc="upper right")
        else:
            ax3.text(
                0.5,
                0.5,
                "No GPU Data",
                ha="center",
                va="center",
                transform=ax3.transAxes,
                fontsize=14,
                color="gray",
            )
        ax3.set_title("GPU Usage")
        ax3.grid(True, alpha=0.3)

        # I/O
        ax4 = axes[1, 1]
        if any(v > 0 for v in data["io_read"]) or any(v > 0 for v in data["io_write"]):
            ax4.plot(
                data["timestamps"],
                data["io_read"],
                color=colors["io_read"],
                linewidth=1.5,
                label="Read (MB)",
            )
            ax4.plot(
                data["timestamps"],
                data["io_write"],
                color=colors["io_write"],
                linewidth=1.5,
                label="Write (MB)",
            )
            ax4.legend(loc="upper right")
        else:
            ax4.text(
                0.5,
                0.5,
                "No I/O Data",
                ha="center",
                va="center",
                transform=ax4.transAxes,
                fontsize=14,
                color="gray",
            )
        ax4.set_ylabel("I/O (MB)")
        ax4.set_title("I/O Statistics")
        ax4.grid(True, alpha=0.3)

        # Format x-axis for all subplots
        for ax in axes.flat:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        plt.tight_layout()
        return fig

    def save_charts(self, output_dir: str, format: str = "png") -> List[str]:
        """Save charts to files.

        Args:
            output_dir: Output directory path.
            format: Image format (png, svg, pdf).

        Returns:
            List of saved file paths.
        """
        if not HAS_MATPLOTLIB:
            raise ImportError(
                "matplotlib is required for chart generation. "
                "Install it with: pip install matplotlib"
            )

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        saved_files = []

        # Save combined figure
        fig = self.create_figure()
        if fig:
            combined_path = output_path / f"combined.{format}"
            fig.savefig(combined_path, dpi=self._config.dpi, bbox_inches="tight")
            plt.close(fig)
            saved_files.append(str(combined_path))

        return saved_files

    def generate_html_report(self) -> str:
        """Generate HTML report with embedded charts.

        Returns:
            HTML string.
        """
        if not self._history:
            return "<html><body><p>No data to display</p></body></html>"

        data = self._extract_data()
        first_stats = self._history[0]
        summary = self._calculate_summary()

        # Prepare chart data for Chart.js
        chart_labels = [ts.strftime("%H:%M:%S") for ts in data["timestamps"]]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Process Monitor Report - PID {first_stats.pid}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            color: #1a1a2e;
            font-size: 28px;
            margin-bottom: 8px;
        }}
        .header .meta {{
            color: #666;
            font-size: 14px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        .summary-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .summary-card .label {{
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .summary-card .value {{
            font-size: 32px;
            font-weight: bold;
            margin: 8px 0;
        }}
        .summary-card .detail {{
            color: #888;
            font-size: 12px;
        }}
        .summary-card.cpu .value {{ color: #2196F3; }}
        .summary-card.memory .value {{ color: #4CAF50; }}
        .summary-card.gpu .value {{ color: #FF9800; }}
        .summary-card.vram .value {{ color: #E91E63; }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .chart-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .chart-card h3 {{
            color: #1a1a2e;
            margin-bottom: 16px;
            font-size: 16px;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
        }}
        .footer {{
            text-align: center;
            color: white;
            padding: 20px;
            opacity: 0.8;
        }}
        @media (max-width: 768px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Process Monitor Report</h1>
            <div class="meta">
                <strong>PID:</strong> {first_stats.pid} ({first_stats.name}) |
                <strong>Duration:</strong> {summary['duration']:.1f} seconds |
                <strong>Samples:</strong> {summary['samples']} |
                <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>

        <div class="summary-grid">
            <div class="summary-card cpu">
                <div class="label">CPU Usage (Avg)</div>
                <div class="value">{summary['cpu_avg']:.1f}%</div>
                <div class="detail">Max: {summary['cpu_max']:.1f}% | Min: {summary['cpu_min']:.1f}%</div>
            </div>
            <div class="summary-card memory">
                <div class="label">Memory Usage (Avg)</div>
                <div class="value">{summary['mem_avg']:.1f} MB</div>
                <div class="detail">Max: {summary['mem_max']:.1f} MB | Min: {summary['mem_min']:.1f} MB</div>
            </div>
            <div class="summary-card gpu">
                <div class="label">GPU Utilization (Avg)</div>
                <div class="value">{summary['gpu_util_avg']:.1f}%</div>
                <div class="detail">Max: {summary['gpu_util_max']:.1f}% | Min: {summary['gpu_util_min']:.1f}%</div>
            </div>
            <div class="summary-card vram">
                <div class="label">GPU Memory (Avg)</div>
                <div class="value">{summary['gpu_mem_avg']:.1f} MB</div>
                <div class="detail">Max: {summary['gpu_mem_max']:.1f} MB | Min: {summary['gpu_mem_min']:.1f} MB</div>
            </div>
        </div>

        <div class="charts-grid">
            <div class="chart-card">
                <h3>📈 CPU Usage Over Time</h3>
                <div class="chart-container">
                    <canvas id="cpuChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>💾 Memory Usage Over Time</h3>
                <div class="chart-container">
                    <canvas id="memoryChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>🎮 GPU Utilization Over Time</h3>
                <div class="chart-container">
                    <canvas id="gpuChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>🧠 GPU Memory (VRAM) Over Time</h3>
                <div class="chart-container">
                    <canvas id="vramChart"></canvas>
                </div>
            </div>
        </div>

        <div class="footer">
            Generated by peek.os.monitor | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>

    <script>
        const labels = {json.dumps(chart_labels)};
        const cpuData = {json.dumps(data['cpu_percent'])};
        const memoryData = {json.dumps(data['memory_mb'])};
        const gpuUtilData = {json.dumps(data['gpu_util'])};
        const gpuMemData = {json.dumps(data['gpu_memory'])};

        const chartOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{ display: false }}
            }},
            scales: {{
                x: {{
                    ticks: {{
                        maxTicksLimit: 10,
                        maxRotation: 45
                    }}
                }},
                y: {{
                    beginAtZero: true
                }}
            }},
            elements: {{
                point: {{ radius: 0 }},
                line: {{ tension: 0.4 }}
            }}
        }};

        new Chart(document.getElementById('cpuChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    data: cpuData,
                    borderColor: '#2196F3',
                    backgroundColor: 'rgba(33, 150, 243, 0.1)',
                    fill: true,
                    borderWidth: 2
                }}]
            }},
            options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'CPU (%)' }} }} }} }}
        }});

        new Chart(document.getElementById('memoryChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    data: memoryData,
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    fill: true,
                    borderWidth: 2
                }}]
            }},
            options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'Memory (MB)' }} }} }} }}
        }});

        new Chart(document.getElementById('gpuChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    data: gpuUtilData,
                    borderColor: '#FF9800',
                    backgroundColor: 'rgba(255, 152, 0, 0.1)',
                    fill: true,
                    borderWidth: 2
                }}]
            }},
            options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'GPU Utilization (%)' }}, max: 100 }} }} }}
        }});

        new Chart(document.getElementById('vramChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    data: gpuMemData,
                    borderColor: '#E91E63',
                    backgroundColor: 'rgba(233, 30, 99, 0.1)',
                    fill: true,
                    borderWidth: 2
                }}]
            }},
            options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'GPU Memory (MB)' }} }} }} }}
        }});
    </script>
</body>
</html>"""
        return html

    def _calculate_summary(self) -> Dict[str, float]:
        """Calculate summary statistics."""
        if not self._history:
            return {
                "samples": 0,
                "duration": 0,
                "cpu_avg": 0,
                "cpu_max": 0,
                "cpu_min": 0,
                "mem_avg": 0,
                "mem_max": 0,
                "mem_min": 0,
                "gpu_util_avg": 0,
                "gpu_util_max": 0,
                "gpu_util_min": 0,
                "gpu_mem_avg": 0,
                "gpu_mem_max": 0,
                "gpu_mem_min": 0,
            }

        cpu = [s.cpu_percent for s in self._history]
        mem = [s.memory_mb for s in self._history]
        gpu_util = [s.avg_gpu_utilization for s in self._history]
        gpu_mem = [s.total_gpu_memory_mb for s in self._history]

        duration = 0
        if len(self._history) > 1:
            duration = (
                self._history[-1].timestamp - self._history[0].timestamp
            ).total_seconds()

        return {
            "samples": len(self._history),
            "duration": duration,
            "cpu_avg": sum(cpu) / len(cpu),
            "cpu_max": max(cpu),
            "cpu_min": min(cpu),
            "mem_avg": sum(mem) / len(mem),
            "mem_max": max(mem),
            "mem_min": min(mem),
            "gpu_util_avg": sum(gpu_util) / len(gpu_util) if gpu_util else 0,
            "gpu_util_max": max(gpu_util) if gpu_util else 0,
            "gpu_util_min": min(gpu_util) if gpu_util else 0,
            "gpu_mem_avg": sum(gpu_mem) / len(gpu_mem) if gpu_mem else 0,
            "gpu_mem_max": max(gpu_mem) if gpu_mem else 0,
            "gpu_mem_min": min(gpu_mem) if gpu_mem else 0,
        }

    def save_html(self, output_path: str) -> str:
        """Save HTML report to file.

        Args:
            output_path: Output file path.

        Returns:
            Path to saved file.
        """
        html = self.generate_html_report()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return str(path)

    def save_json(self, output_path: str) -> str:
        """Save monitoring data as JSON.

        Args:
            output_path: Output file path.

        Returns:
            Path to saved file.
        """
        data = {
            "metadata": {
                "pid": self._history[0].pid if self._history else 0,
                "name": self._history[0].name if self._history else "",
                "samples": len(self._history),
                "generated_at": datetime.now().isoformat(),
            },
            "summary": self._calculate_summary(),
            "history": [s.to_dict() for s in self._history],
        }

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(path)
