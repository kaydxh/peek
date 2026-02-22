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
- 🌐 **HTTP API**: 内置 `/debug/monitor/*` 端点，支持实时快照、持续采集、报告生成
- 🔌 **框架集成**: 通过 `tide.plugins.monitor` 一行代码集成到 tide 应用

## 架构设计

监控能力采用**两层架构**设计，确保最大程度的复用性：

```
┌─────────────────────────────────────────────────────────────┐
│                    tide cmd 应用层                            │
│  tide-date / tide-vllm / tide-vllm-wxvideosceneaudit / ...  │
│  （只需在 options.py 中调用 install_monitor 即可）             │
└──────────────────────────┬──────────────────────────────────┘
                           │ 调用
┌──────────────────────────▼──────────────────────────────────┐
│                  tide 框架层                                  │
│            tide.plugins.monitor                              │
│  MonitorConfig / MonitorPlugin / install_monitor()           │
│  （配置定义、Plugin 基类实现、函数式安装接口）                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ 调用
┌──────────────────────────▼──────────────────────────────────┐
│                  peek 基础库层                                │
│          peek.os.monitor.service                             │
│  MonitorService / MonitorServiceConfig                       │
│  register_monitor_routes()                                   │
│  （核心逻辑：进程发现、监控器管理、HTTP 路由注册）               │
├─────────────────────────────────────────────────────────────┤
│          peek.os.monitor.collector                           │
│  ProcessMonitor / MultiProcessMonitor / MonitorConfig        │
│  （底层采集器：CPU/内存/GPU 数据采集）                         │
├─────────────────────────────────────────────────────────────┤
│          peek.os.monitor.visualizer                          │
│  MonitorVisualizer / MultiProcessVisualizer                  │
│  （可视化：HTML 报告、实时图表）                               │
└─────────────────────────────────────────────────────────────┘
```

### 各层职责

| 层 | 模块 | 职责 |
|------|------|------|
| **peek** | `peek.os.monitor.collector` | 底层进程监控采集（CPU、内存、GPU、IO） |
| **peek** | `peek.os.monitor.visualizer` | 可视化报告生成（HTML、实时图表） |
| **peek** | `peek.os.monitor.service` | 监控服务管理器 + HTTP API 路由注册。**不依赖 tide** |
| **tide 框架** | `tide.plugins.monitor` | 配置定义（`MonitorConfig`）、Plugin 基类实现、函数式安装接口 |
| **cmd 应用** | 各应用 `options.py` | 导入 `MonitorConfig` 和调用 `install_monitor()` 完成集成 |

### 设计原则

- **peek 层不依赖 tide**：`MonitorService` 只依赖 `fastapi`（可选），不引入 tide 的任何代码
- **配置文件为主 + API 动态控制为辅**：配置文件决定能力边界，API 提供运行时灵活性
- **零侵入**：监控插件完全遵循 tide 的插件模式，不侵入业务代码

## 安装

```bash
# 基础安装（仅支持 CPU/内存监控）
pip install peek

# 完整安装（包含 GPU 监控和可视化）
pip install "peek[monitor]"
```

## HTTP API 端点

当监控插件启用后，以下 API 端点自动注册到 Web 服务器：

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| `GET` | `/debug/monitor/snapshot` | 实时资源快照 | 按需采集，零后台开销 |
| `GET` | `/debug/monitor/summary` | 统计摘要 | 持续采集期间的 min/max/avg |
| `POST` | `/debug/monitor/start` | 启动持续采集 | 开始后台定时采集 |
| `POST` | `/debug/monitor/stop` | 停止持续采集 | 返回采集期间统计摘要 |
| `GET` | `/debug/monitor/report` | 生成报告 | 支持 `?format=html` 或 `?format=json` |

### API 使用示例

```bash
# 1. 获取实时快照（无需启动持续采集）
curl http://localhost:10001/debug/monitor/snapshot

# 2. 启动持续采集
curl -X POST http://localhost:10001/debug/monitor/start

# 3. 查看统计摘要（avg/max/min）
curl http://localhost:10001/debug/monitor/summary

# 4. 生成 HTML 可视化报告（用浏览器打开）
curl http://localhost:10001/debug/monitor/report > report.html

# 5. 生成 JSON 格式数据
curl "http://localhost:10001/debug/monitor/report?format=json"

# 6. 停止采集
curl -X POST http://localhost:10001/debug/monitor/stop
```

### 快照响应示例

```json
{
  "timestamp": "2026-02-22T09:00:00.123456",
  "pids": [12345, 12346],
  "is_collecting": false,
  "total": {
    "cpu_percent": 45.2,
    "memory_mb": 1024.5,
    "gpu_memory_mb": 8192.0,
    "gpu_utilization": 78.3
  },
  "processes": {
    "12345": { "pid": 12345, "name": "python", "cpu_percent": 30.1, "memory_mb": 512.3, "..." : "..." },
    "12346": { "pid": 12346, "name": "vllm_worker", "cpu_percent": 15.1, "memory_mb": 512.2, "..." : "..." }
  }
}
```

## 两种监控模式

| 模式 | 说明 | 适用场景 | 开销 |
|------|------|----------|------|
| **按需快照** | 请求时实时采集一次，返回当前状态 | 健康检查、快速诊断 | 零后台开销 |
| **持续采集** | 后台线程定期采集，积累历史数据 | 性能分析、生成监控报告 | 后台线程定期运行 |

## YAML 配置

在应用的 YAML 配置文件中添加 `monitor` 配置段：

```yaml
# 进程资源监控配置
monitor:
  # 是否启用监控插件（启用后提供 /debug/monitor/* API 端点）
  enabled: false

  # 是否在启动时自动开始持续采集（false 则只提供按需快照 API）
  auto_start: false

  # 采集间隔（秒），仅持续采集模式有效
  interval: 5

  # 是否启用 GPU 监控（需要 pynvml）
  enable_gpu: true

  # 是否监控子进程（如 vLLM server）
  include_children: true

  # 历史记录最大条数（按采集间隔计算，3600 条 × 5 秒 = 5 小时）
  history_size: 3600
```

### 推荐配置场景

| 场景 | enabled | auto_start | enable_gpu | 说明 |
|------|---------|------------|------------|------|
| **生产环境** | `false` | - | - | 默认关闭，需要时改配置重启 |
| **开发/测试** | `true` | `false` | `true` | 按需快照，不持续采集 |
| **性能压测** | `true` | `true` | `true` | 启动即自动采集，压测结束后生成报告 |
| **无 GPU 服务** | `true` | `false` | `false` | 如 tide-date，关闭 GPU 监控 |

### 启动流程

```
服务启动
  └─ 加载 YAML 配置
       └─ monitor.enabled?
            ├─ false → 不安装监控插件（零开销）
            └─ true  → 创建 MonitorService，注册 /debug/monitor/* 路由
                 └─ monitor.auto_start?
                      ├─ true  → 自动开始持续采集
                      └─ false → 仅提供按需快照 API（运行时可通过 API 启动采集）
```

## tide 应用集成指南

### 方式一：函数式接口（推荐）

在各 cmd 应用的 `options.py` 中，只需 3 步：

**第 1 步：导入并添加配置字段**

```python
from tide.plugins.monitor import MonitorConfig

@dataclass
class ServerRunOptions:
    # ... 原有字段 ...
    monitor_config: Optional[MonitorConfig] = None
```

**第 2 步：解析配置**

```python
def _load_config(self, config_path: str):
    # ... 原有配置解析 ...
    self.monitor_config = MonitorConfig.from_dict(
        self.config.get("monitor", {})
    )
```

**第 3 步：安装插件（在子进程启动之后）**

```python
class CompletedServerRunOptions:
    async def run(self):
        # ... 安装其他插件 ...
        web_server = await self._create_web_server()
        await self._install_vllm()  # 先启动子进程
        self._install_web_handler(web_server)

        # 安装监控插件（在子进程启动之后，确保能发现子进程 PID）
        await self._install_monitor(web_server)

        # 运行服务器
        await web_server.run()

    async def _install_monitor(self, web_server):
        """安装监控插件。"""
        from tide.plugins.monitor import install_monitor
        await install_monitor(self._options.monitor_config, web_server)
```

### 方式二：Plugin 基类（适用于 PluginManager）

```python
from tide.plugins.monitor import MonitorPlugin

plugin_manager.register(MonitorPlugin())
await plugin_manager.install_all(ctx)
```

## MonitorService（peek 层）

`peek.os.monitor.service.MonitorService` 是核心监控服务管理器，不依赖任何 Web 框架。

### Python API

```python
from peek.os.monitor import MonitorService, MonitorServiceConfig, register_monitor_routes

# 创建配置
config = MonitorServiceConfig(
    enabled=True,
    auto_start=False,
    interval=5.0,
    enable_gpu=True,
    include_children=True,
    history_size=3600,
)

# 创建监控服务
service = MonitorService(config)

# 按需快照
snapshot = service.snapshot()
print(f"CPU: {snapshot['total']['cpu_percent']}%")
print(f"Memory: {snapshot['total']['memory_mb']} MB")
print(f"GPU Util: {snapshot['total']['gpu_utilization']}%")
print(f"GPU Memory: {snapshot['total']['gpu_memory_mb']} MB")

# 持续采集
result = service.start_collecting()
print(result)  # {"status": "started", "pids": [...], ...}

# 获取统计摘要
summary = service.get_summary()
print(summary)

# 停止采集
result = service.stop_collecting()
print(result)  # {"status": "stopped", "summary": {...}}

# 生成报告
html_report = service.generate_report(format="html")
json_report = service.generate_report(format="json")

# 关闭服务
service.shutdown()

# 注册到 FastAPI
from fastapi import FastAPI
app = FastAPI()
register_monitor_routes(app, service)
```

### MonitorService 方法一览

| 方法 | 说明 | 返回 |
|------|------|------|
| `snapshot()` | 实时获取资源快照 | `Dict` |
| `start_collecting()` | 启动持续后台采集 | `Dict`（操作结果） |
| `stop_collecting()` | 停止持续采集 | `Dict`（含摘要统计） |
| `get_summary()` | 获取统计摘要 | `Dict` |
| `generate_report(format)` | 生成 HTML/JSON 报告 | `str` 或 `None` |
| `shutdown()` | 关闭服务，释放资源 | `None` |
| `is_collecting` (属性) | 是否正在持续采集 | `bool` |
| `pids` (属性) | 当前监控的 PID 列表 | `List[int]` |

### 子进程自动发现

MonitorService 会自动发现主进程及其所有子进程（递归）。例如：

- `tide-vllm-wxvideosceneaudit` 主进程（FastAPI/uvicorn）
- vLLM Server 子进程（通过 `subprocess.Popen` 启动）
- vLLM Worker 子进程（由 vLLM Server fork）

通过 `psutil.Process(pid).children(recursive=True)` 获取完整进程树。

## 底层采集器使用

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

### Python API（底层）

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

### MonitorServiceConfig

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | `bool` | `False` | 是否启用监控服务 |
| `auto_start` | `bool` | `False` | 是否自动开始持续采集 |
| `interval` | `float` | `5.0` | 采集间隔（秒） |
| `enable_gpu` | `bool` | `True` | 是否启用 GPU 监控 |
| `include_children` | `bool` | `True` | 是否监控子进程 |
| `history_size` | `int` | `3600` | 历史记录最大条数 |

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
| `fastapi` | HTTP API 路由注册 | ❌ (可选，仅 MonitorService 的 HTTP 功能需要) |

如果没有 NVIDIA GPU 或未安装 `pynvml`，GPU 监控将自动禁用。

## 注意事项

1. **权限问题**: 监控其他用户的进程可能需要 root 权限
2. **GPU 监控**: 需要 NVIDIA GPU 和 CUDA 驱动
3. **性能影响**: 高频采样（< 0.5s）可能影响目标进程性能。GPU 监控（pynvml）有一定开销，建议采集间隔不低于 5 秒
4. **内存使用**: 长时间监控会积累历史数据，注意 `history_size` 配置
5. **安全性**: 监控端点在 `/debug/` 前缀下，生产环境建议通过配置关闭（`enabled: false`）
6. **子进程退出**: 如果子进程意外退出，MonitorService 的 `_ensure_monitor` 会在下次调用时自动重新发现存活的进程
7. **GPU 争用**: pynvml 只是读取 GPU 状态（nvidia-smi 级别），不会影响 GPU 推理性能

## `history_size` 内存消耗估算

历史记录存储在 `deque(maxlen=history_size)` 中。当 `include_children: true` 时，使用 `MultiProcessMonitor`，每条记录是一个 `MultiProcessStats` 对象。

### 每条记录的数据结构

| 层级 | 数据结构 | 字段内容 | 估算大小 |
|------|---------|---------|---------|
| `MultiProcessStats` | dataclass | `timestamp`(datetime) + `process_stats`(dict) | ~200 bytes 基础开销 |
| └─ `ProcessStats`（每个进程） | dataclass | 13 个标量字段 + `gpu_stats` 列表 | ~400 bytes |
| └─ `GPUStats`（每张 GPU 卡） | dataclass | 8 个标量字段 | ~200 bytes |

### 分场景内存估算

以下以 `history_size: 36000`（5 秒间隔 × 36000 条 = 50 小时）为例：

**场景 1：仅主进程，GPU 关闭**

每条记录 ≈ ~600 bytes（`MultiProcessStats` + 1 个 `ProcessStats`）

```
36000 条 × 600 bytes ≈ 21.6 MB
```

**场景 2：主进程 + 1 个 vLLM 子进程，GPU 关闭**（典型配置）

每条记录 ≈ ~1000 bytes（`MultiProcessStats` + 2 个 `ProcessStats`）

```
36000 条 × 1000 bytes ≈ 36 MB
```

**场景 3：主进程 + 1 个 vLLM 子进程，GPU 开启（1 张卡）**

每条记录 ≈ ~1400 bytes（每个 `ProcessStats` 多一个 `GPUStats` 约 200 bytes）

```
36000 条 × 1400 bytes ≈ 50.4 MB
```

### 不同 `history_size` 的内存对照表

以「主进程 + 1 个 vLLM 子进程，GPU 关闭」为基准（每条 ~1000 bytes）：

| `history_size` | 覆盖时长（5s 间隔） | 估算内存 |
|----------------|---------------------|---------|
| 3600（默认值） | 5 小时 | **~3.5 MB** |
| 7200 | 10 小时 | **~7 MB** |
| 36000 | 50 小时 | **~36 MB** |

### 完整场景对照表

| 场景 | history_size=3600 | history_size=36000 |
|------|-------------------|-------------------|
| 仅主进程，GPU 关闭 | ~2 MB | ~20-25 MB |
| 主进程 + vLLM 子进程，GPU 关闭 | ~3.5 MB | ~35-40 MB |
| 主进程 + vLLM 子进程，GPU 开启（1 卡） | ~5 MB | ~50 MB |
| 主进程 + vLLM 子进程，GPU 开启（4 卡） | ~7 MB | ~70-80 MB |

> **说明**：以上估算已包含 Python 对象的额外开销（对象头、引用计数、字典等），实际内存可能比纯数据量大 2-3 倍。对于模型推理服务来说，36000 条记录的内存占用（35-40 MB）影响很小。

## 文件清单

### peek 层

| 文件 | 说明 |
|------|------|
| `peek/src/peek/os/monitor/__init__.py` | 模块导出 |
| `peek/src/peek/os/monitor/collector.py` | 底层采集器（ProcessMonitor / MultiProcessMonitor） |
| `peek/src/peek/os/monitor/visualizer.py` | 可视化报告（HTML / 实时图表） |
| `peek/src/peek/os/monitor/service.py` | MonitorService + register_monitor_routes |
| `peek/tools/process_monitor.py` | 命令行监控工具 |

### tide 框架层

| 文件 | 说明 |
|------|------|
| `tide/src/tide/plugins/monitor.py` | MonitorPlugin / MonitorConfig / install_monitor / uninstall_monitor |
| `tide/src/tide/plugins/__init__.py` | 导出 MonitorPlugin / MonitorConfig |
