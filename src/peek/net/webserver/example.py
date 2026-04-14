#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebServer 使用示例

展示如何使用 peek.net.webserver 模块创建 Web 服务
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

# 导入 webserver 模块
from peek.net.webserver import (
    Config,
    FuncHealthChecker,
    GenericWebServer,
    WebHandler,
    with_description,
    with_title,
    with_version,
)

# ==================== 数据模型 ====================


class TimeResponse(BaseModel):
    """时间响应模型"""

    current_time: str
    timezone: str
    timestamp: float


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    timestamp: str


# ==================== 业务处理器 ====================


class DateHandler(WebHandler):
    """
    日期服务处理器

    实现 WebHandler 接口，注册业务路由
    """

    def set_routes(self, app: FastAPI) -> None:
        """注册路由"""

        @app.get("/api/v1/time", response_model=TimeResponse, tags=["Time"])
        async def get_current_time(
            tz: str = Query(default="UTC", description="时区名称"),
        ) -> TimeResponse:
            """获取当前时间"""
            try:
                import pytz

                if tz.upper() == "UTC":
                    current_time = datetime.now(timezone.utc)
                else:
                    current_time = datetime.now(pytz.timezone(tz))

                return TimeResponse(
                    current_time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    timezone=tz,
                    timestamp=current_time.timestamp(),
                )
            except Exception as e:
                from fastapi import HTTPException

                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/v1/date", tags=["Time"])
        async def get_current_date() -> dict:
            """获取当前日期"""
            now = datetime.now(timezone.utc)
            return {
                "date": now.strftime("%Y-%m-%d"),
                "day_of_week": now.strftime("%A"),
                "week_number": now.isocalendar()[1],
            }


# ==================== 方式一：简单使用 ====================


def example_simple():
    """简单使用示例"""
    # 创建服务器
    server = GenericWebServer(
        host="0.0.0.0",
        port=8080,
        title="日期服务",
        description="提供时间和日期相关的 API",
        version="1.0.0",
    )

    # 添加启动钩子
    def on_start():
        print("🚀 服务已启动!")

    server.add_post_start_hook("startup-log", on_start)

    # 添加关闭钩子
    def on_shutdown():
        print("⏹️  服务已关闭!")

    server.add_pre_shutdown_hook("shutdown-log", on_shutdown)

    # 安装业务处理器
    handler = DateHandler()
    server.install_web_handler(handler)

    # 运行服务器
    server.run()


# ==================== 方式二：使用配置文件 ====================


def example_with_config():
    """使用配置文件示例"""
    from peek.net.webserver import BindAddress, WebConfig, WebServerConfig

    # 创建配置（也可以从 YAML 文件加载）
    proto = WebServerConfig(
        web=WebConfig(
            bind_address=BindAddress(host="0.0.0.0", port=8080),
            shutdown_delay_duration=5.0,
            shutdown_timeout_duration=10.0,
        ),
    )

    # 使用 Option 模式定制配置
    config = Config(proto).apply_options(
        with_title("日期服务"),
        with_description("提供时间和日期相关的 API"),
        with_version("2.0.0"),
    )

    # 完成配置并创建服务器
    completed = config.complete()
    server = completed.new_server()

    # 安装业务处理器
    handler = DateHandler()
    server.install_web_handler(handler)

    # 添加自定义健康检查
    def check_database() -> Optional[Exception]:
        # 模拟数据库检查
        return None

    server.healthz_controller.add_readyz_checker(
        FuncHealthChecker("database", check_database)
    )

    # 运行服务器
    server.run()


# ==================== 方式三：从 YAML 配置文件加载 ====================


EXAMPLE_CONFIG_YAML = """
web:
  bind_address:
    host: "0.0.0.0"
    port: 8080
  http:
    api_formatter: ""
    read_timeout: 30.0
    write_timeout: 30.0
  debug:
    enable_profiling: true
  shutdown_delay_duration: 5.0
  shutdown_timeout_duration: 10.0
  http_qps_limit:
    default_qps: 100
    default_burst: 200
    max_concurrency: 50
  open_telemetry:
    enabled: false
    resource:
      service_name: "date-service"
      service_version: "1.0.0"
"""


def example_with_yaml_config():
    """从 YAML 配置文件加载示例"""
    import os
    import tempfile

    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
    ) as f:
        f.write(EXAMPLE_CONFIG_YAML)
        config_file = f.name

    try:
        # 从 YAML 加载配置
        config = Config.from_yaml(
            config_file,
            with_title("日期服务"),
            with_description("从 YAML 配置加载的服务"),
        )

        # 创建服务器
        completed = config.complete()
        server = completed.new_server()

        # 安装业务处理器
        handler = DateHandler()
        server.install_web_handler(handler)

        # 运行服务器
        server.run()
    finally:
        os.unlink(config_file)


# ==================== 方式四：完全自定义 ====================


def example_advanced():
    """高级自定义示例"""
    from peek.net.webserver import (
        HandlerChain,
        LoggerMiddleware,
        QPSRateLimitMiddleware,
        RecoveryMiddleware,
        RequestIDMiddleware,
        TimerMiddleware,
    )
    from peek.net.webserver.middleware.ratelimit import (
        MethodQPSConfig,
        QPSLimitConfig,
    )

    # 创建服务器
    server = GenericWebServer(
        host="0.0.0.0",
        port=8080,
        title="高级日期服务",
        description="使用自定义中间件链的服务",
        version="3.0.0",
    )

    # 创建自定义中间件链
    chain = HandlerChain()
    chain.add_handler(LoggerMiddleware)
    chain.add_handler(TimerMiddleware)
    chain.add_handler(RecoveryMiddleware, debug=True)
    chain.add_handler(RequestIDMiddleware)

    # 添加 QPS 限流
    rate_config = QPSLimitConfig(
        default_qps=100,
        default_burst=200,
        max_concurrency=50,
        method_qps=[
            MethodQPSConfig(method="GET", path="/api/v1/time", qps=50, burst=100),
        ],
    )
    chain.add_handler(QPSRateLimitMiddleware, config=rate_config)

    # 安装中间件链
    chain.install(server.app)

    # 安装业务处理器
    handler = DateHandler()
    server.install_web_handler(handler)

    # 添加异步启动钩子
    async def async_startup():
        print("🔄 执行异步初始化...")
        await asyncio.sleep(0.1)
        print("✅ 异步初始化完成!")

    server.add_post_start_hook("async-init", async_startup)

    # 运行服务器
    server.run()


if __name__ == "__main__":
    import sys

    examples = {
        "simple": example_simple,
        "config": example_with_config,
        "yaml": example_with_yaml_config,
        "advanced": example_advanced,
    }

    if len(sys.argv) > 1 and sys.argv[1] in examples:
        examples[sys.argv[1]]()
    else:
        print("Usage: python example.py [simple|config|yaml|advanced]")
        print("Default: simple")
        example_simple()
