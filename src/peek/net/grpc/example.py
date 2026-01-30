#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC + HTTP 双协议服务示例

展示如何使用 peek 框架同时提供 HTTP 和 gRPC 服务。
"""

import logging
from typing import Optional

from fastapi import FastAPI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ==================== 示例 1: 仅 HTTP 服务 ====================


def example_http_only():
    """仅 HTTP 服务示例"""
    from peek.net.webserver import GenericWebServer, WebHandler

    class MyHandler(WebHandler):
        def set_routes(self, app: FastAPI) -> None:
            @app.get("/api/hello")
            async def hello(name: str = "World"):
                return {"message": f"Hello, {name}!"}

            @app.post("/api/echo")
            async def echo(data: dict):
                return {"echo": data}

    # 创建服务器
    server = GenericWebServer(
        host="0.0.0.0",
        port=8080,
        title="HTTP Only Service",
        description="仅提供 HTTP 服务的示例",
    )

    # 安装业务处理器
    server.install_web_handler(MyHandler())

    # 添加生命周期钩子
    server.add_post_start_hook("startup", lambda: logger.info("HTTP service started"))
    server.add_pre_shutdown_hook("cleanup", lambda: logger.info("Cleaning up..."))

    # 启动服务
    server.run()


# ==================== 示例 2: HTTP + gRPC 双协议服务 ====================


def example_http_and_grpc():
    """HTTP + gRPC 双协议服务示例

    注意：需要先生成 proto 文件对应的 Python 代码：
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. example.proto
    """
    from peek.net.webserver import GenericWebServer, WebHandler
    from peek.net.grpc import (
        create_default_interceptor_chain,
        QPSLimitInterceptor,
    )

    # 假设已经生成了 proto 文件对应的代码
    # from example_pb2 import HelloRequest, HelloResponse
    # from example_pb2_grpc import add_HelloServiceServicer_to_server, HelloServiceServicer

    class MyHTTPHandler(WebHandler):
        def set_routes(self, app: FastAPI) -> None:
            @app.get("/api/hello")
            async def hello(name: str = "World"):
                return {"message": f"Hello, {name}!"}

    # 创建服务器（同时支持 HTTP 和 gRPC）
    server = GenericWebServer(
        host="0.0.0.0",
        port=8080,      # HTTP 端口
        grpc_port=50051,  # gRPC 端口
        title="HTTP + gRPC Service",
        description="同时提供 HTTP 和 gRPC 服务的示例",
    )

    # 安装 HTTP 处理器
    server.install_web_handler(MyHTTPHandler())

    # 添加 gRPC 拦截器
    server.add_grpc_interceptors(create_default_interceptor_chain())
    server.add_grpc_interceptor(QPSLimitInterceptor(qps=1000))

    # 注册 gRPC 服务（取消注释以使用）
    # class HelloServicer(HelloServiceServicer):
    #     def SayHello(self, request, context):
    #         return HelloResponse(message=f"Hello, {request.name}!")
    #
    # server.register_grpc_service(
    #     lambda s: add_HelloServiceServicer_to_server(HelloServicer(), s),
    #     service_name="example.HelloService",
    # )

    # 启动服务
    server.run()


# ==================== 示例 3: 使用 GRPCGateway ====================


def example_grpc_gateway():
    """gRPC Gateway 示例

    使用 GRPCGateway 实现 HTTP 到 gRPC 的代理转发。
    """
    from peek.net.grpc import GRPCGateway, create_default_interceptor_chain

    # 创建 Gateway
    gateway = GRPCGateway(
        host="0.0.0.0",
        http_port=8080,
        grpc_port=50051,
        title="gRPC Gateway Service",
        description="提供 HTTP 到 gRPC 转发的网关服务",
    )

    # 添加 gRPC 拦截器
    gateway.add_grpc_interceptors(create_default_interceptor_chain())

    # 自定义 HTTP 路由
    @gateway.app.get("/api/info")
    async def info():
        return {
            "service": "gRPC Gateway",
            "http_port": 8080,
            "grpc_port": 50051,
        }

    # 注册 gRPC 服务（取消注释以使用）
    # gateway.register_grpc_service(
    #     lambda s: add_HelloServiceServicer_to_server(HelloServicer(), s),
    #     service_name="example.HelloService",
    # )

    # 注册 HTTP 到 gRPC 的代理（取消注释以使用）
    # gateway.register_http_proxy(
    #     http_method="POST",
    #     http_path="/api/v1/hello",
    #     grpc_method="SayHello",
    #     request_converter=lambda req: HelloRequest(name=req.query_params.get("name", "")),
    #     response_converter=lambda resp: {"message": resp.message},
    #     grpc_stub_class=HelloServiceStub,
    # )

    # 启动服务
    gateway.run()


# ==================== 示例 4: 独立 gRPC 服务 ====================


def example_grpc_only():
    """仅 gRPC 服务示例"""
    from peek.net.grpc import GRPCServer, create_default_interceptor_chain

    # 创建 gRPC 服务器
    server = GRPCServer(
        host="0.0.0.0",
        port=50051,
        max_workers=10,
    )

    # 添加拦截器
    server.add_interceptors(create_default_interceptor_chain())

    # 注册服务（取消注释以使用）
    # server.register_service(
    #     lambda s: add_HelloServiceServicer_to_server(HelloServicer(), s),
    #     service_name="example.HelloService",
    # )

    # 启动服务
    server.start()
    logger.info("gRPC server started on 0.0.0.0:50051")

    # 等待终止
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=5.0)


# ==================== 示例 5: 从配置文件加载 ====================


def example_from_config():
    """从配置文件加载的示例

    配置文件 (config.yaml):
    ```yaml
    web:
      bind_address:
        host: "0.0.0.0"
        port: 8080
      shutdown_delay_duration: 5
      shutdown_timeout_duration: 30
      title: "My Service"
      description: "My awesome service"
      version: "1.0.0"

    grpc:
      server:
        host: "0.0.0.0"
        port: 50051
        max_workers: 10
        enable_request_id: true
        enable_recovery: true
        enable_logging: true
        enable_timer: true
        enable_qps_limit: true
        qps_limit: 1000
    ```
    """
    from peek.net.webserver import Config, WebHandler
    from peek.net.grpc import GRPCConfig

    class MyHandler(WebHandler):
        def set_routes(self, app: FastAPI) -> None:
            @app.get("/api/hello")
            async def hello():
                return {"message": "Hello from config!"}

    # 从 YAML 加载配置
    # config = Config.from_yaml("config.yaml")
    # completed = config.complete()
    # server = completed.new_server()

    # 或者手动创建配置
    from peek.net.webserver import with_title, with_description

    config = Config(
        with_title("My Service"),
        with_description("My awesome service"),
    )
    completed = config.complete()
    server = completed.new_server()

    # 安装处理器
    server.install_web_handler(MyHandler())

    # 启动服务
    server.run()


# ==================== 示例 6: 完整的生产级服务 ====================


def example_production_service():
    """生产级服务示例

    包含完整的功能：
    - HTTP + gRPC 双协议
    - 健康检查
    - 中间件链
    - 生命周期钩子
    - 限流
    - 追踪和指标
    """
    from peek.net.webserver import (
        GenericWebServer,
        WebHandler,
        HealthzController,
        PingHealthChecker,
        create_default_handler_chain,
        QPSRateLimitMiddleware,
    )
    from peek.net.grpc import (
        create_default_interceptor_chain,
        QPSLimitInterceptor,
        ConcurrencyLimitInterceptor,
    )

    class MyHandler(WebHandler):
        def set_routes(self, app: FastAPI) -> None:
            @app.get("/api/v1/users")
            async def list_users():
                return {"users": []}

            @app.get("/api/v1/users/{user_id}")
            async def get_user(user_id: int):
                return {"id": user_id, "name": "John Doe"}

            @app.post("/api/v1/users")
            async def create_user(data: dict):
                return {"id": 1, **data}

    # 创建服务器
    server = GenericWebServer(
        host="0.0.0.0",
        port=8080,
        grpc_port=50051,
        shutdown_delay_duration=5,
        shutdown_timeout_duration=30,
        title="Production Service",
        description="生产级服务示例",
        version="1.0.0",
    )

    # 安装健康检查
    healthz = HealthzController()
    healthz.add_health_checker("self", PingHealthChecker())
    server.install_healthz_controller(healthz)

    # 安装业务处理器
    server.install_web_handler(MyHandler())

    # 添加 gRPC 拦截器
    server.add_grpc_interceptors(create_default_interceptor_chain())
    server.add_grpc_interceptor(QPSLimitInterceptor(qps=1000))
    server.add_grpc_interceptor(ConcurrencyLimitInterceptor(max_concurrent=100))

    # 添加生命周期钩子
    server.add_post_start_hook("init_db", lambda: logger.info("Database initialized"))
    server.add_post_start_hook("init_cache", lambda: logger.info("Cache initialized"))
    server.add_pre_shutdown_hook("close_db", lambda: logger.info("Database closed"))
    server.add_pre_shutdown_hook("close_cache", lambda: logger.info("Cache closed"))

    # 启动服务
    logger.info("Starting production service...")
    server.run()


# ==================== 主入口 ====================


if __name__ == "__main__":
    import sys

    examples = {
        "http": example_http_only,
        "http_grpc": example_http_and_grpc,
        "gateway": example_grpc_gateway,
        "grpc": example_grpc_only,
        "config": example_from_config,
        "production": example_production_service,
    }

    if len(sys.argv) < 2:
        print("Usage: python example_grpc.py <example>")
        print(f"Available examples: {', '.join(examples.keys())}")
        sys.exit(1)

    example_name = sys.argv[1]
    if example_name not in examples:
        print(f"Unknown example: {example_name}")
        print(f"Available examples: {', '.join(examples.keys())}")
        sys.exit(1)

    examples[example_name]()
