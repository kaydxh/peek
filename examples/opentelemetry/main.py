#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenTelemetry 使用示例

演示如何使用 peek 的 OpenTelemetry 模块：
1. 从 YAML 配置文件初始化
2. 使用 Builder 创建配置
3. 使用 Metric API 上报指标
4. 使用 Tracer 创建 Span
"""

import asyncio
import time
from pathlib import Path

# ========== 1. 从 YAML 配置文件初始化 ==========


def example_from_config_file():
    """从 YAML 配置文件初始化"""
    from peek.opentelemetry import OpenTelemetryService

    config_file = Path(__file__).parent / "config.yaml"
    service = OpenTelemetryService.from_config_file(str(config_file))
    service.install()

    print("OpenTelemetry initialized from config file")
    return service


# ========== 2. 使用 Builder 创建配置 ==========


def example_with_builder():
    """使用 Builder 创建配置"""
    from peek.opentelemetry import OpenTelemetryService, OpenTelemetryConfigBuilder

    config = (
        OpenTelemetryConfigBuilder()
        .with_resource(
            service_name="my-service",
            service_version="1.0.0",
            deployment_environment="dev",
        )
        .with_tracer_stdout(pretty_print=True)  # 调试用：输出到控制台
        .with_metric_stdout(pretty_print=True)  # 调试用：输出到控制台
        .build()
    )

    service = OpenTelemetryService(config)
    service.install()

    print("OpenTelemetry initialized with Builder")
    return service


def example_with_otlp():
    """使用 OTLP 导出"""
    from peek.opentelemetry import OpenTelemetryService, OpenTelemetryConfigBuilder

    config = (
        OpenTelemetryConfigBuilder()
        .with_resource(service_name="my-service", service_version="1.0.0")
        .with_tracer_otlp(
            endpoint="localhost:4317",
            protocol="grpc",
            compression=True,
        )
        .with_metric_otlp(
            endpoint="localhost:4317",
            protocol="grpc",
            temporality="cumulative",
        )
        .with_app_meter_provider(
            endpoint="prometheus.tencentcloudapi.com:4317",
            protocol="grpc",
            temporality="delta",  # 智研平台
            compression=True,
        )
        .build()
    )

    service = OpenTelemetryService(config)
    service.install()

    print("OpenTelemetry initialized with OTLP")
    return service


def example_with_prometheus():
    """使用 Prometheus 导出"""
    from peek.opentelemetry import OpenTelemetryService, OpenTelemetryConfigBuilder

    config = (
        OpenTelemetryConfigBuilder()
        .with_resource(service_name="my-service")
        .with_metric_prometheus(url="/metrics", namespace="myapp")
        .build()
    )

    service = OpenTelemetryService(config)
    service.install()

    print(f"Prometheus metrics available at: {service.get_prometheus_metrics_url()}")
    return service


# ========== 3. 使用 Metric API 上报指标 ==========


def example_metric_api():
    """使用 Metric API 上报指标"""
    from peek.opentelemetry.metric.api import (
        # 函数式 API
        global_add_counter,
        global_incr_counter,
        global_record_histogram,
        global_record_duration,
        global_timer,
        # OOP API
        Counter,
        Histogram,
        Timer,
    )

    # ===== 函数式 API =====

    # 全局计数器（基础设施指标）
    global_incr_counter(
        meter_name="http",
        instrument_name="requests_total",
        attributes={"method": "GET", "status": "200"},
    )

    # 全局直方图
    global_record_duration(
        meter_name="http",
        instrument_name="request_duration_ms",
        duration_ms=123.45,
        attributes={"method": "GET"},
    )

    # 全局计时器
    with global_timer("http", "process_duration_ms", {"handler": "index"}):
        time.sleep(0.1)

    # ===== OOP API =====

    # Counter
    counter = Counter("business", "orders_total")
    counter.incr()
    counter.with_attr("region", "us-west").with_attr("type", "premium").add(5)

    # Histogram
    histogram = Histogram("business", "order_amount", unit="USD")
    histogram.record(99.99)
    histogram.with_attrs(currency="USD", region="us-west").record(199.99)

    # Timer
    timer = Timer("business", "process_duration_ms")
    with timer.time():
        time.sleep(0.05)

    with timer.with_attr("step", "validation").time():
        time.sleep(0.02)

    print("Metric API examples completed")


# ========== 4. 使用 Tracer 创建 Span ==========


def example_tracer():
    """使用 Tracer 创建 Span"""
    from peek.opentelemetry.tracer import get_tracer

    tracer = get_tracer("my.module", version="1.0.0")

    # 简单 Span
    with tracer.start_as_current_span("my-operation") as span:
        span.set_attribute("key", "value")
        time.sleep(0.1)

    # 嵌套 Span
    with tracer.start_as_current_span("parent-operation") as parent:
        parent.set_attribute("parent_key", "parent_value")

        with tracer.start_as_current_span("child-operation") as child:
            child.set_attribute("child_key", "child_value")
            time.sleep(0.05)

    print("Tracer examples completed")


# ========== 5. 服务端/客户端指标上报 ==========


def example_metric_report():
    """服务端/客户端指标上报"""
    from peek.opentelemetry.metric.report import (
        MetricReporter,
        ServerDimension,
        ClientDimension,
    )

    reporter = MetricReporter()

    # 服务端指标上报（被调）
    server_dim = ServerDimension(
        service="my-service",
        method="/api/v1/users",
        protocol="http",
        status_code=200,
        success=True,
        caller="client-service",
    )
    reporter.report_server_metric(server_dim, cost_ms=50.0)

    # 客户端指标上报（主调）
    client_dim = ClientDimension(
        service="user-service",
        method="/api/v1/users",
        protocol="grpc",
        status_code=0,
        success=True,
        callee="user-service",
    )
    reporter.report_client_metric(client_dim, cost_ms=30.0)

    print("Metric report examples completed")


# ========== 6. 与 WebServer 集成 ==========


def example_webserver_integration():
    """与 WebServer 集成"""
    from peek.opentelemetry import OpenTelemetryService, OpenTelemetryConfigBuilder
    from peek.net.webserver import GenericWebServer, WebHandler

    # 初始化 OpenTelemetry
    config = (
        OpenTelemetryConfigBuilder()
        .with_resource(service_name="my-webserver")
        .with_metric_prometheus(url="/metrics")
        .with_tracer_stdout()
        .build()
    )
    otel_service = OpenTelemetryService(config)
    otel_service.install()

    # 创建 WebServer
    class MyHandler(WebHandler):
        def set_routes(self, app):
            @app.get("/hello")
            async def hello():
                return {"message": "Hello, World!"}

    server = GenericWebServer(host="0.0.0.0", port=8080)
    server.install_web_handler(MyHandler())

    # 注册 Prometheus /metrics 端点
    from peek.opentelemetry.metric.prometheus import get_metrics_handler

    # 注意：实际使用需要将 metrics handler 挂载到 FastAPI
    # 这里只是示例
    print(f"Prometheus metrics URL: {otel_service.get_prometheus_metrics_url()}")

    return server


# ========== Main ==========


def main():
    """主函数"""
    print("=" * 50)
    print("OpenTelemetry Examples")
    print("=" * 50)

    # 使用 stdout 导出器演示（方便查看输出）
    service = example_with_builder()

    print("\n--- Metric API Examples ---")
    example_metric_api()

    print("\n--- Tracer Examples ---")
    example_tracer()

    print("\n--- Metric Report Examples ---")
    example_metric_report()

    print("\n--- Shutdown ---")
    service.shutdown()

    print("\nAll examples completed!")


if __name__ == "__main__":
    main()
