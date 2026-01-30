#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebServer 配置使用示例

演示如何使用 YAML 配置文件创建 WebServer
"""

import os
import sys
from pathlib import Path

# 添加项目路径
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from fastapi import FastAPI

from peek.net.webserver import (
    GenericWebServer,
    WebHandler,
    WebConfig,
    WebServerConfigBuilder,
    load_config,
    load_config_from_file,
)


# ======================== 示例 Handler ========================


class HelloHandler(WebHandler):
    """示例 Handler"""

    def set_routes(self, app: FastAPI) -> None:
        @app.get("/hello")
        async def hello():
            return {"message": "Hello, World!"}

        @app.get("/hello/{name}")
        async def hello_name(name: str):
            return {"message": f"Hello, {name}!"}


# ======================== 方式一：从 YAML 文件创建 ========================


def example_from_yaml_file():
    """从 YAML 配置文件创建服务器"""
    print("=" * 50)
    print("方式一：从 YAML 配置文件创建")
    print("=" * 50)

    # 获取配置文件路径
    config_file = Path(__file__).parent / "config.yaml"

    # 创建服务器
    server = GenericWebServer.from_config_file(str(config_file))

    # 安装 Handler
    server.install_web_handler(HelloHandler())

    # 打印配置信息
    print(f"Host: {server.host}")
    print(f"Port: {server.port}")
    print(f"gRPC Port: {server.grpc_port}")
    print(f"Server ID: {server.web_server_id}")

    # 运行服务器
    server.run()

    return server


# ======================== 方式二：从配置对象创建 ========================


def example_from_config_object():
    """从配置对象创建服务器"""
    print("=" * 50)
    print("方式二：从配置对象创建")
    print("=" * 50)

    # 加载配置
    config_file = Path(__file__).parent / "config.yaml"
    config = load_config_from_file(str(config_file))

    # 可以修改配置
    config.bind_address.port = 9090
    config.title = "Modified Server"

    # 创建服务器
    server = GenericWebServer.from_config(config)

    print(f"Host: {server.host}")
    print(f"Port: {server.port}")

    return server


# ======================== 方式三：从字典创建 ========================


def example_from_dict():
    """从配置字典创建服务器"""
    print("=" * 50)
    print("方式三：从配置字典创建")
    print("=" * 50)

    config_dict = {
        "web": {
            "bind_address": {
                "host": "0.0.0.0",
                "port": 8888,
            },
            "grpc": {
                "port": 50052,
                "max_workers": 20,
            },
            "http": {
                "timeout": "60s",
            },
            "shutdown": {
                "delay_duration": "2s",
                "timeout_duration": "10s",
            },
            "title": "Dict Config Server",
        }
    }

    server = GenericWebServer.from_config_dict(config_dict)

    print(f"Host: {server.host}")
    print(f"Port: {server.port}")
    print(f"gRPC Port: {server.grpc_port}")

    return server


# ======================== 方式四：使用 Builder 创建 ========================


def example_from_builder():
    """使用 Builder 创建服务器"""
    print("=" * 50)
    print("方式四：使用 Builder 创建")
    print("=" * 50)

    # 使用 Builder 构建配置
    config = (
        WebServerConfigBuilder()
        .with_bind_address("0.0.0.0", 8080)
        .with_grpc(port=50051, max_workers=10, timeout="30s")
        .with_http(timeout="30s", docs_url="/api/docs")
        .with_shutdown(delay="5s", timeout="10s")
        .with_open_telemetry(
            enabled=True,
            service_name="my-service",
            trace_exporter_type="trace_stdout",
        )
        .with_metadata(
            title="Builder Config Server",
            description="Created with WebServerConfigBuilder",
            version="2.0.0",
        )
        .build()
    )

    server = GenericWebServer.from_config(config)

    print(f"Host: {server.host}")
    print(f"Port: {server.port}")
    print(f"gRPC Port: {server.grpc_port}")
    print(f"Title: {config.title}")

    return server


# ======================== 方式五：从环境变量加载 ========================


def example_from_env():
    """从环境变量加载配置"""
    print("=" * 50)
    print("方式五：从环境变量加载")
    print("=" * 50)

    # 设置环境变量
    os.environ["MYAPP_WEB_BIND_ADDRESS_HOST"] = "127.0.0.1"
    os.environ["MYAPP_WEB_BIND_ADDRESS_PORT"] = "7777"
    os.environ["MYAPP_WEB_GRPC_PORT"] = "50055"

    # 从环境变量加载（会与基础配置合并）
    config = load_config(env_prefix="MYAPP")

    server = GenericWebServer.from_config(config)

    print(f"Host: {server.host}")
    print(f"Port: {server.port}")
    print(f"gRPC Port: {server.grpc_port}")

    # 清理环境变量
    del os.environ["MYAPP_WEB_BIND_ADDRESS_HOST"]
    del os.environ["MYAPP_WEB_BIND_ADDRESS_PORT"]
    del os.environ["MYAPP_WEB_GRPC_PORT"]

    return server


# ======================== 完整运行示例 ========================


def run_server():
    """完整运行示例"""
    config_file = Path(__file__).parent / "config.yaml"

    # 从配置文件创建服务器
    server = GenericWebServer.from_config_file(str(config_file))

    # 安装 Handler
    server.install_web_handler(HelloHandler())

    # 添加启动后钩子
    def on_start():
        print("🚀 Server started!")

    server.add_post_start_hook("log-start", on_start)

    # 添加关闭前钩子
    def on_shutdown():
        print("👋 Server shutting down...")

    server.add_pre_shutdown_hook("log-shutdown", on_shutdown)

    # 运行服务器
    print(f"Starting server on {server.host}:{server.port}")
    server.run()


# ======================== Main ========================


if __name__ == "__main__":
    # 运行所有示例
    example_from_yaml_file()
    print()

    example_from_config_object()
    print()

    example_from_dict()
    print()

    example_from_builder()
    print()

    example_from_env()
    print()

    # 取消注释以实际运行服务器
    # run_server()
