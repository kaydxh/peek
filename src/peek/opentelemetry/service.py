# -*- coding: utf-8 -*-
"""
OpenTelemetry Service 服务类

提供：
- 统一的初始化入口
- 配置驱动的组件安装
- 支持 YAML 配置文件
"""

import logging
from typing import Optional

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider

from peek.opentelemetry.config import (
    OpenTelemetryConfig,
    ExporterType,
    MetricExporterType,
    OTLPProtocol,
    TemporalityType,
    load_config,
    load_config_from_file,
)
from peek.opentelemetry.resource.resource import create_resource_from_config
from peek.opentelemetry.tracer.tracer import Tracer, TracerExporterBuilder
from peek.opentelemetry.tracer.otlp.exporter import OTLPTraceExporterBuilder
from peek.opentelemetry.tracer.stdout.exporter import StdoutTraceExporterBuilder
from peek.opentelemetry.metric.meter import (
    Meter,
    PushExporterBuilder,
    PullExporterBuilder,
    set_app_meter_provider,
)
from peek.opentelemetry.metric.otlp.exporter import OTLPMetricExporterBuilder
from peek.opentelemetry.metric.prometheus.exporter import PrometheusExporterBuilder
from peek.opentelemetry.metric.stdout.exporter import StdoutMetricExporterBuilder

logger = logging.getLogger(__name__)


class OpenTelemetryService:
    """
    OpenTelemetry 服务

    统一管理：
    - Tracer
    - Meter（Global + App）
    - Resource

    示例:
        ```python
        # 从 YAML 配置文件创建
        service = OpenTelemetryService.from_config_file("config.yaml")
        service.install()

        # 从配置对象创建
        config = OpenTelemetryConfig(
            enabled=True,
            tracer=TracerConfig(enabled=True, exporter_type="otlp"),
            metric=MetricConfig(enabled=True, exporter_type="prometheus"),
        )
        service = OpenTelemetryService(config)
        service.install()

        # 使用 Builder
        config = (
            OpenTelemetryConfigBuilder()
            .with_resource(service_name="my-service")
            .with_tracer_otlp("localhost:4317")
            .with_metric_prometheus()
            .build()
        )
        service = OpenTelemetryService(config)
        service.install()
        ```
    """

    def __init__(self, config: OpenTelemetryConfig):
        """
        初始化 OpenTelemetry 服务

        Args:
            config: OpenTelemetryConfig 配置对象
        """
        self._config = config
        self._resource: Optional[Resource] = None
        self._tracer: Optional[Tracer] = None
        self._meter: Optional[Meter] = None
        self._app_meter: Optional[Meter] = None
        self._tracer_provider: Optional[TracerProvider] = None
        self._meter_provider: Optional[MeterProvider] = None
        self._app_meter_provider: Optional[MeterProvider] = None

    @classmethod
    def from_config_file(cls, config_file: str) -> "OpenTelemetryService":
        """从 YAML 配置文件创建"""
        config = load_config_from_file(config_file)
        return cls(config)

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "OpenTelemetryService":
        """从配置字典创建"""
        config = load_config(config_dict=config_dict)
        return cls(config)

    def _create_resource(self, meter_type: str = "global") -> Resource:
        """
        创建 Resource

        Args:
            meter_type: Meter 类型（global/app），用于选择使用哪个 zhiyan app_mark
        """
        # 注意：每种 meter_type 需要独立的 Resource（因为 zhiyan app_mark 不同）
        return create_resource_from_config(self._config.resource, meter_type=meter_type)

    def _create_tracer_exporter_builder(self) -> Optional[TracerExporterBuilder]:
        """创建 Tracer 导出器构建器"""
        tracer_config = self._config.tracer

        if tracer_config.exporter_type == ExporterType.OTLP:
            return OTLPTraceExporterBuilder(
                endpoint=tracer_config.otlp.endpoint,
                protocol=tracer_config.otlp.protocol,
                headers=tracer_config.otlp.headers,
                compression=tracer_config.otlp.compression,
                insecure=tracer_config.otlp.insecure,
                timeout_ms=int(tracer_config.otlp.timeout_seconds * 1000),
            )
        elif tracer_config.exporter_type == ExporterType.STDOUT:
            return StdoutTraceExporterBuilder(
                pretty_print=tracer_config.stdout.pretty_print,
            )

        return None

    def _create_metric_push_exporter_builder(self) -> Optional[PushExporterBuilder]:
        """创建 Metric Push 导出器构建器"""
        metric_config = self._config.metric

        if metric_config.exporter_type == MetricExporterType.OTLP:
            return OTLPMetricExporterBuilder(
                endpoint=metric_config.otlp.endpoint,
                protocol=metric_config.otlp.protocol,
                headers=metric_config.otlp.headers,
                compression=metric_config.otlp.compression,
                insecure=metric_config.otlp.insecure,
                timeout_ms=int(metric_config.otlp.timeout_seconds * 1000),
                temporality=metric_config.otlp.temporality,
                export_interval_ms=int(metric_config.collect_interval_seconds * 1000),
            )
        elif metric_config.exporter_type == MetricExporterType.STDOUT:
            return StdoutMetricExporterBuilder(
                pretty_print=metric_config.stdout.pretty_print,
                export_interval_ms=int(metric_config.collect_interval_seconds * 1000),
            )

        return None

    def _create_metric_pull_exporter_builder(self) -> Optional[PullExporterBuilder]:
        """创建 Metric Pull 导出器构建器"""
        metric_config = self._config.metric

        if metric_config.exporter_type == MetricExporterType.PROMETHEUS:
            return PrometheusExporterBuilder(
                namespace=metric_config.prometheus.namespace,
            )

        return None

    def _create_app_meter_push_exporter_builder(self) -> Optional[PushExporterBuilder]:
        """创建 App Meter Push 导出器构建器"""
        app_config = self._config.app_meter_provider

        if not app_config.enabled:
            return None

        if app_config.exporter_type == MetricExporterType.OTLP:
            return OTLPMetricExporterBuilder(
                endpoint=app_config.otlp.endpoint,
                protocol=app_config.otlp.protocol,
                headers=app_config.otlp.headers,
                compression=app_config.otlp.compression,
                insecure=app_config.otlp.insecure,
                timeout_ms=int(app_config.otlp.timeout_seconds * 1000),
                temporality=app_config.otlp.temporality,
                export_interval_ms=int(app_config.collect_interval_seconds * 1000),
            )

        return None

    def install_tracer(self) -> Optional[TracerProvider]:
        """
        安装 Tracer

        Returns:
            TracerProvider 实例（如果启用）
        """
        if not self._config.enabled or not self._config.tracer.enabled:
            logger.info("Tracer is disabled")
            return None

        # Tracer 使用 global resource（包含 zhiyan apm_token）
        resource = self._create_resource(meter_type="global")
        exporter_builder = self._create_tracer_exporter_builder()

        self._tracer = Tracer(
            resource=resource,
            exporter_builder=exporter_builder,
            sample_ratio=self._config.tracer.sample_ratio,
            batch_timeout_ms=int(self._config.tracer.batch_timeout_seconds * 1000),
        )

        self._tracer_provider = self._tracer.install()

        logger.info(
            "Tracer installed: exporter_type=%s, sample_ratio=%.2f",
            self._config.tracer.exporter_type.value,
            self._config.tracer.sample_ratio,
        )

        return self._tracer_provider

    def install_meter(self) -> Optional[MeterProvider]:
        """
        安装 Meter（Global MeterProvider）

        使用 zhiyan.global_app_mark 作为应用标识。

        Returns:
            MeterProvider 实例（如果启用）
        """
        if not self._config.enabled or not self._config.metric.enabled:
            logger.info("Meter is disabled")
            return None

        # Global Meter 使用 global_app_mark
        resource = self._create_resource(meter_type="global")
        push_builder = self._create_metric_push_exporter_builder()
        pull_builder = self._create_metric_pull_exporter_builder()

        self._meter = Meter(
            resource=resource,
            push_exporter_builder=push_builder,
            pull_exporter_builder=pull_builder,
            collect_interval_ms=int(self._config.metric.collect_interval_seconds * 1000),
        )

        self._meter_provider = self._meter.install()

        logger.info(
            "Meter installed: exporter_type=%s, collect_interval=%ds",
            self._config.metric.exporter_type.value,
            self._config.metric.collect_interval_seconds,
        )

        return self._meter_provider

    def install_app_meter(self) -> Optional[MeterProvider]:
        """
        安装 App Meter（业务指标）

        使用 zhiyan.app_mark 作为应用标识。
        独立于全局 Meter，用于业务指标上报。

        Returns:
            MeterProvider 实例（如果启用）
        """
        if not self._config.enabled or not self._config.app_meter_provider.enabled:
            logger.info("App Meter is disabled")
            return None

        # App Meter 使用 app_mark
        resource = self._create_resource(meter_type="app")
        push_builder = self._create_app_meter_push_exporter_builder()

        self._app_meter = Meter(
            resource=resource,
            push_exporter_builder=push_builder,
            collect_interval_ms=int(self._config.app_meter_provider.collect_interval_seconds * 1000),
        )

        self._app_meter_provider = self._app_meter.install_as_app_provider()

        logger.info(
            "App Meter installed: exporter_type=%s, collect_interval=%ds",
            self._config.app_meter_provider.exporter_type.value,
            self._config.app_meter_provider.collect_interval_seconds,
        )

        return self._app_meter_provider

    def install(self) -> "OpenTelemetryService":
        """
        安装所有组件

        按顺序安装：
        1. Tracer
        2. Meter
        3. App Meter

        Returns:
            self（支持链式调用）
        """
        if not self._config.enabled:
            logger.info("OpenTelemetry is disabled")
            return self

        self.install_tracer()
        self.install_meter()
        self.install_app_meter()

        logger.info("OpenTelemetry service installed")

        return self

    def shutdown(self) -> None:
        """关闭所有组件"""
        if self._tracer:
            self._tracer.shutdown()
        if self._meter:
            self._meter.shutdown()
        if self._app_meter:
            self._app_meter.shutdown()

        logger.info("OpenTelemetry service shutdown completed")

    @property
    def config(self) -> OpenTelemetryConfig:
        """获取配置"""
        return self._config

    @property
    def resource(self) -> Optional[Resource]:
        """获取 Resource"""
        return self._resource

    @property
    def tracer_provider(self) -> Optional[TracerProvider]:
        """获取 TracerProvider"""
        return self._tracer_provider

    @property
    def meter_provider(self) -> Optional[MeterProvider]:
        """获取 MeterProvider"""
        return self._meter_provider

    @property
    def app_meter_provider(self) -> Optional[MeterProvider]:
        """获取 App MeterProvider"""
        return self._app_meter_provider

    def get_prometheus_metrics_url(self) -> Optional[str]:
        """获取 Prometheus /metrics URL"""
        if self._config.metric.exporter_type == MetricExporterType.PROMETHEUS:
            return self._config.metric.prometheus.url
        return None
