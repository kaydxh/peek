# -*- coding: utf-8 -*-
"""
OpenTelemetry 模块

提供 OpenTelemetry 功能：
- Tracer：分布式追踪
- Metric：指标收集（支持 Prometheus、OTLP）
- Resource：资源属性管理

示例:
    ```python
    from peek.opentelemetry import OpenTelemetryService, OpenTelemetryConfig

    # 从 YAML 配置文件创建
    service = OpenTelemetryService.from_config_file("config.yaml")
    service.install()

    # 使用 Metric API
    from peek.opentelemetry.metric.api import Counter, Histogram

    counter = Counter("my_meter", "requests_total")
    counter.with_attr("method", "GET").add(ctx, 1)
    ```
"""

from peek.opentelemetry.config import (
    OpenTelemetryConfig,
    TracerConfig,
    MetricConfig,
    ResourceConfig,
    OTLPConfig,
    PrometheusConfig,
    load_config,
    load_config_from_file,
    OpenTelemetryConfigBuilder,
)
from peek.opentelemetry.service import OpenTelemetryService
from peek.opentelemetry.resource import create_resource, get_k8s_attributes

__all__ = [
    # Config
    "OpenTelemetryConfig",
    "TracerConfig",
    "MetricConfig",
    "ResourceConfig",
    "OTLPConfig",
    "PrometheusConfig",
    "load_config",
    "load_config_from_file",
    "OpenTelemetryConfigBuilder",
    # Service
    "OpenTelemetryService",
    # Resource
    "create_resource",
    "get_k8s_attributes",
]
