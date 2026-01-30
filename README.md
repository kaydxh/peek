# peek

Python Base Libraries - A collection of utilities for Python development.

## 安装

```bash
# 基础安装
pip install -e .

# 开发模式（含测试、格式化工具）
pip install -e .[dev]

# 生产模式（含 OpenTelemetry、gRPC）
pip install -e .[prod]

# 全部依赖
pip install -e .[all]
```

## 项目结构

```
peek/
├── src/
│   └── peek/                # 主包
│       ├── ai/              # AI/GPU 工具
│       ├── cv/              # 计算机视觉
│       ├── encoding/        # 编码工具
│       ├── git/             # Git 操作
│       ├── net/             # 网络模块
│       │   ├── http.py      # HTTP 客户端
│       │   ├── ip.py        # IP 工具
│       │   ├── webserver/   # Web 服务器框架
│       │   └── grpc/        # gRPC 服务
│       ├── os/              # 系统工具
│       ├── time/            # 时间工具
│       └── uuid/            # UUID 生成
├── tests/                   # 测试
│   ├── unit/               # 单元测试
│   └── integration/        # 集成测试
├── examples/               # 示例代码
├── docs/                   # 文档
├── requirements/           # 分环境依赖
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
└── scripts/                # 辅助脚本
```

## 使用示例

### HTTP 客户端

```python
from peek.net import http

# 发送 GET 请求
response = http.do_http_get("https://api.example.com/data")

# 发送 POST 请求
response = http.do_http_post("https://api.example.com/data", json={"key": "value"})
```

### Web 服务器

#### 基础使用

```python
from peek.net.webserver import GenericWebServer, WebHandler

class MyHandler(WebHandler):
    def set_routes(self, app):
        @app.get("/hello")
        async def hello():
            return {"message": "Hello, World!"}

server = GenericWebServer(host="0.0.0.0", port=8080)
server.install_web_handler(MyHandler())
server.run()
```

#### 从 YAML 配置文件创建（推荐）

```yaml
# config.yaml
web:
  bind_address:
    host: "0.0.0.0"
    port: 8080
  grpc:
    port: 50051
    max_workers: 10
    timeout: "30s"
  http:
    timeout: "30s"
  shutdown:
    delay_duration: "0s"
    timeout_duration: "5s"
  title: "My Web Server"
  version: "1.0.0"
```

```python
from peek.net.webserver import GenericWebServer

# 从 YAML 配置文件创建
server = GenericWebServer.from_config_file("config.yaml")
server.run()
```

#### 使用 Builder 创建配置

```python
from peek.net.webserver import GenericWebServer, WebServerConfigBuilder

config = (
    WebServerConfigBuilder()
    .with_bind_address("0.0.0.0", 8080)
    .with_grpc(port=50051, max_workers=10)
    .with_http(timeout="30s")
    .with_shutdown(delay="5s", timeout="10s")
    .build()
)

server = GenericWebServer.from_config(config)
server.run()
```

### gRPC 服务

```python
from peek.net.webserver import GenericWebServer
from peek.net.grpc import create_default_interceptor_chain

# 同时支持 HTTP 和 gRPC
server = GenericWebServer(
    host="0.0.0.0",
    port=8080,        # HTTP 端口
    grpc_port=50051,  # gRPC 端口
)

# 添加 gRPC 拦截器
server.add_grpc_interceptors(create_default_interceptor_chain())

# 注册 gRPC 服务
server.register_grpc_service(
    lambda s: my_pb2_grpc.add_MyServiceServicer_to_server(MyServicer(), s),
    service_name="my.service.MyService"
)

server.run()
```

## 开发

```bash
# 格式化代码
./scripts/format.sh

# 代码检查
./scripts/lint.sh

# 运行测试
./scripts/test.sh

# 运行特定测试
pytest tests/unit/test_http.py -v
```

## License

MIT License
