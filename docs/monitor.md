# Process Monitor

`peek.os.monitor` 模块提供了一套完整的进程监控和可视化工具，支持监控 CPU、内存、GPU 和显存等资源使用情况。

## 功能特性

- 📈 **CPU 监控**: 监控进程 CPU 使用率、线程数
- 💾 **内存监控**: 监控 RSS、VMS、内存百分比
- 🎮 **GPU 监控**: 监控 GPU 利用率、温度、功耗
- 🧠 **显存监控**: 监控 GPU 显存使用量
- 📊 **可视化**: 终端实时图表 + HTML 报告 + JSON 数据导出
- 🔧 **命令行工具**: 开箱即用的监控脚本
- 🔀 **多进程监控**: 同时监控多个进程，汇总展示

## 安装

```bash
# 基础安装（仅支持 CPU/内存监控）
pip install peek

# 完整安装（包含 GPU 监控和可视化）
pip install "peek[monitor]"
```

## 快速开始

### 命令行使用

```bash
# 监控当前进程（实时显示）
python -m peek.os.monitor

# 或使用工具脚本
python tools/process_monitor.py

# 监控指定 PID
python tools/process_monitor.py --pid 1234

# 监控多个进程（用逗号分隔）
python tools/process_monitor.py --pids 1234,5678,9012

# 监控 60 秒并生成 HTML 报告
python tools/process_monitor.py --pid 1234 --duration 60 --output report.html

# 无限监控，直到 Ctrl+C 退出时自动生成报告
python tools/process_monitor.py --pid 1234 --duration 0 --output report.html

# 运行命令并监控
python tools/process_monitor.py --command "python train.py" --output training_report.html
```

### Python API 使用

```python
import time
from peek.os.monitor import ProcessMonitor, MonitorConfig, MonitorVisualizer

# 创建监控配置
config = MonitorConfig(
    interval=1.0,        # 采样间隔（秒）
    history_size=3600,   # 历史记录大小
    enable_gpu=True,     # 启用 GPU 监控
    enable_io=True,      # 启用 IO 监控
)

# 创建监控器
monitor = ProcessMonitor(pid=1234, config=config)

# 方式一：单次快照
stats = monitor.snapshot()
print(f"CPU: {stats.cpu_percent}%")
print(f"Memory: {stats.memory_mb} MB")
print(f"GPU Util: {stats.avg_gpu_utilization}%")
print(f"GPU Memory: {stats.total_gpu_memory_mb} MB")

# 方式二：后台持续监控
monitor.start()
time.sleep(60)  # 监控 60 秒
monitor.stop()

# 获取摘要统计
summary = monitor.get_summary()
print(f"Avg CPU: {summary['cpu_percent']['avg']:.1f}%")
print(f"Max Memory: {summary['memory_mb']['max']:.1f} MB")

# 生成可视化报告
visualizer = MonitorVisualizer(monitor.history)
visualizer.save_html("report.html")
visualizer.save_json("data.json")
```

### 使用上下文管理器

```python
from peek.os.monitor import ProcessMonitor

with ProcessMonitor(pid=1234) as monitor:
    # 执行一些操作...
    time.sleep(30)
    
# 退出时自动停止监控
print(monitor.get_summary())
```

### 实时终端显示

```python
from peek.os.monitor import ProcessMonitor, RealtimeChart

monitor = ProcessMonitor(pid=1234)
chart = RealtimeChart(monitor)

# 阻塞显示，按 Ctrl+C 停止
chart.start()
```

### 注册回调函数

```python
from peek.os.monitor import ProcessMonitor, ProcessStats

def on_sample(stats: ProcessStats):
    if stats.cpu_percent > 80:
        print(f"⚠️ High CPU usage: {stats.cpu_percent}%")
    if stats.total_gpu_memory_mb > 10000:
        print(f"⚠️ High GPU memory: {stats.total_gpu_memory_mb} MB")

monitor = ProcessMonitor(pid=1234)
monitor.add_callback(on_sample)
monitor.start()
```

### 多进程监控

```python
from peek.os.monitor import MultiProcessMonitor, MultiProcessVisualizer

# 创建多进程监控器
monitor = MultiProcessMonitor(pids=[1234, 5678, 9012])

# 方式一：上下文管理器
with MultiProcessMonitor(pids=[1234, 5678]) as monitor:
    time.sleep(60)

# 获取汇总统计
summary = monitor.get_summary()
print(f"Total CPU: {summary['total']['cpu_percent']['avg']:.1f}%")
print(f"Process count: {summary['process_count']}")

# 获取每个进程的独立历史
per_process_history = monitor.get_per_process_history()
for pid, history in per_process_history.items():
    print(f"PID {pid}: {len(history)} samples")

# 生成多进程报告
visualizer = MultiProcessVisualizer(monitor.history)
visualizer.save_html("multi_process_report.html")
```

### 多进程实时显示

```python
from peek.os.monitor import MultiProcessMonitor, MultiProcessRealtimeChart

monitor = MultiProcessMonitor(pids=[1234, 5678])
chart = MultiProcessRealtimeChart(monitor)

# 阻塞显示，按 Ctrl+C 停止
monitor = chart.start()  # 返回带有数据的 monitor
```

## 数据结构

### ProcessStats

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | `datetime` | 采样时间戳 |
| `pid` | `int` | 进程 ID |
| `name` | `str` | 进程名称 |
| `cpu_percent` | `float` | CPU 使用率 (%) |
| `memory_mb` | `float` | 内存使用量 (MB) |
| `memory_percent` | `float` | 内存使用率 (%) |
| `memory_rss_mb` | `float` | RSS 内存 (MB) |
| `memory_vms_mb` | `float` | VMS 内存 (MB) |
| `num_threads` | `int` | 线程数 |
| `io_read_mb` | `float` | IO 读取量 (MB) |
| `io_write_mb` | `float` | IO 写入量 (MB) |
| `gpu_stats` | `List[GPUStats]` | GPU 统计列表 |

### GPUStats

| 字段 | 类型 | 说明 |
|------|------|------|
| `index` | `int` | GPU 索引 |
| `name` | `str` | GPU 名称 |
| `utilization_percent` | `float` | GPU 利用率 (%) |
| `memory_used_mb` | `float` | 已用显存 (MB) |
| `memory_total_mb` | `float` | 总显存 (MB) |
| `memory_percent` | `float` | 显存使用率 (%) |
| `temperature` | `float` | 温度 (°C) |
| `power_usage_w` | `float` | 功耗 (W) |

## 命令行参数

```
usage: process_monitor.py [-h] [--pid PID | --pids PIDS | --command COMMAND]
                          [--duration DURATION] [--interval INTERVAL]
                          [--output OUTPUT] [--format {html,json,both}]
                          [--realtime] [--no-realtime] [--quiet]
                          [--no-gpu] [--no-io] [--gpu-indices GPU_INDICES]

参数说明:
  --pid PID            要监控的进程 ID
  --pids PIDS          要监控的多个进程 ID（逗号分隔，如 "1234,5678,9012"）
  --command, -c        运行并监控的命令
  --duration, -d       监控时长（秒），0 表示无限监控直到 Ctrl+C
  --interval, -i       采样间隔（秒），默认 1.0
  --output, -o         输出文件路径（支持无限监控退出时生成报告）
  --format, -f         输出格式：html/json/both
  --realtime, -r       实时显示（默认开启）
  --no-realtime        禁用实时显示
  --quiet, -q          静默模式
  --no-gpu             禁用 GPU 监控
  --no-io              禁用 IO 监控
  --gpu-indices        指定要监控的 GPU 索引，如 "0,1"
```

## 使用示例

### 监控训练脚本

```bash
# 运行训练并监控资源使用（命令结束时自动生成报告）
python tools/process_monitor.py \
    --command "python train.py --epochs 100" \
    --output training_report.html

# 无限监控训练进程，Ctrl+C 时生成报告
python tools/process_monitor.py \
    --pid 1234 \
    --duration 0 \
    --output training_report.html

# 仅监控 GPU 0 和 GPU 1
python tools/process_monitor.py \
    --pid 1234 \
    --gpu-indices "0,1" \
    --duration 300 \
    --output gpu_report.html
```

### 监控分布式训练（多进程）

```bash
# 监控多个 worker 进程
python tools/process_monitor.py \
    --pids 1234,5678,9012 \
    --duration 0 \
    --output distributed_training.html

# 静默收集多进程数据
python tools/process_monitor.py \
    --pids 1234,5678 \
    --duration 3600 \
    --quiet \
    --format both \
    --output multi_process_metrics
```

### 快速诊断

```bash
# 10 秒快照
python tools/process_monitor.py \
    --pid $(pgrep -f myapp) \
    --duration 10 \
    --output snapshot.html
```

### 静默收集数据

```bash
# 后台收集 1 小时数据
python tools/process_monitor.py \
    --pid 1234 \
    --duration 3600 \
    --quiet \
    --format json \
    --output metrics.json
```

## HTML 报告示例

生成的 HTML 报告包含：

1. **摘要卡片**: CPU、内存、GPU 利用率、显存的平均/最大/最小值
2. **时序图表**: 各项指标随时间变化的曲线图
3. **交互式图表**: 基于 Chart.js，支持缩放、悬停查看

## 依赖说明

| 依赖 | 用途 | 必需 |
|------|------|------|
| `psutil` | CPU/内存监控 | ✅ |
| `pynvml` | GPU/显存监控 | ❌ (可选) |
| `matplotlib` | 图表生成 | ❌ (可选) |

如果没有 NVIDIA GPU 或未安装 `pynvml`，GPU 监控将自动禁用。

## 注意事项

1. **权限问题**: 监控其他用户的进程可能需要 root 权限
2. **GPU 监控**: 需要 NVIDIA GPU 和 CUDA 驱动
3. **性能影响**: 高频采样（< 0.5s）可能影响目标进程性能
4. **内存使用**: 长时间监控会积累历史数据，注意 `history_size` 配置
