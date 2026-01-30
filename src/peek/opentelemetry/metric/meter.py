# -*- coding: utf-8 -*-
"""
OpenTelemetry Meter 核心实现

提供：
- MeterProvider 创建和管理
- Push/Pull 两种导出模式
- 双 MeterProvider 架构（Global + App）
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from opentelemetry import metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)

logger = logging.getLogger(__name__)

# ========== 全局 App MeterProvider ==========
_app_meter_provider: Optional[MeterProvider] = None


def get_app_meter_provider() -> Optional[MeterProvider]:
    """
    获取 App 级别的 MeterProvider

    用于业务指标上报，独立于全局 MeterProvider。
    """
    return _app_meter_provider


def set_app_meter_provider(provider: MeterProvider) -> None:
    """设置 App 级别的 MeterProvider"""
    global _app_meter_provider
    _app_meter_provider = provider


class MeterExporterBuilder(ABC):
    """
    Meter 导出器构建器基类

    所有导出器实现都需要继承此类。
    """

    @abstractmethod
    def build(self) -> MetricReader:
        """
        构建 MetricReader

        Returns:
            MetricReader 实例
        """
        pass


class PushExporterBuilder(MeterExporterBuilder):
    """
    Push 模式导出器构建器基类

    用于 OTLP、Stdout 等主动推送的导出器。
    """
    pass


class PullExporterBuilder(MeterExporterBuilder):
    """
    Pull 模式导出器构建器基类

    用于 Prometheus 等被动拉取的导出器。
    """
    pass


class Meter:
    """
    Meter 管理器

    负责：
    - 创建和配置 MeterProvider
    - 管理导出器
    - 支持 Push/Pull 两种模式
    """

    def __init__(
        self,
        resource: Resource,
        push_exporter_builder: Optional[PushExporterBuilder] = None,
        pull_exporter_builder: Optional[PullExporterBuilder] = None,
        collect_interval_ms: int = 60000,
    ):
        """
        初始化 Meter

        Args:
            resource: OpenTelemetry Resource
            push_exporter_builder: Push 导出器构建器（OTLP/Stdout）
            pull_exporter_builder: Pull 导出器构建器（Prometheus）
            collect_interval_ms: 采集间隔（毫秒）
        """
        self._resource = resource
        self._push_exporter_builder = push_exporter_builder
        self._pull_exporter_builder = pull_exporter_builder
        self._collect_interval_ms = collect_interval_ms
        self._provider: Optional[MeterProvider] = None

    def install(self) -> MeterProvider:
        """
        安装 MeterProvider

        创建 MeterProvider 并设置为全局 Provider。

        Returns:
            MeterProvider 实例
        """
        readers = []

        # Push 导出器
        if self._push_exporter_builder:
            push_reader = self._push_exporter_builder.build()
            readers.append(push_reader)

        # Pull 导出器
        if self._pull_exporter_builder:
            pull_reader = self._pull_exporter_builder.build()
            readers.append(pull_reader)

        # 创建 MeterProvider
        self._provider = MeterProvider(
            resource=self._resource,
            metric_readers=readers,
        )

        # 设置全局 Provider
        metrics.set_meter_provider(self._provider)

        logger.info(
            "Meter installed: readers=%d, collect_interval=%dms",
            len(readers),
            self._collect_interval_ms,
        )

        return self._provider

    def install_as_app_provider(self) -> MeterProvider:
        """
        安装为 App MeterProvider

        创建独立的 MeterProvider，不设置为全局。
        用于业务指标上报。

        Returns:
            MeterProvider 实例
        """
        readers = []

        if self._push_exporter_builder:
            push_reader = self._push_exporter_builder.build()
            readers.append(push_reader)

        if self._pull_exporter_builder:
            pull_reader = self._pull_exporter_builder.build()
            readers.append(pull_reader)

        provider = MeterProvider(
            resource=self._resource,
            metric_readers=readers,
        )

        # 设置为 App Provider
        set_app_meter_provider(provider)

        logger.info(
            "App MeterProvider installed: readers=%d, collect_interval=%dms",
            len(readers),
            self._collect_interval_ms,
        )

        return provider

    def shutdown(self) -> None:
        """关闭 MeterProvider"""
        if self._provider:
            self._provider.shutdown()
            logger.info("Meter shutdown completed")

    @property
    def provider(self) -> Optional[MeterProvider]:
        """获取 MeterProvider"""
        return self._provider


def install_meter(
    resource: Resource,
    push_exporter_builder: Optional[PushExporterBuilder] = None,
    pull_exporter_builder: Optional[PullExporterBuilder] = None,
    collect_interval_ms: int = 60000,
) -> MeterProvider:
    """
    快捷函数：安装 Meter

    Args:
        resource: OpenTelemetry Resource
        push_exporter_builder: Push 导出器构建器
        pull_exporter_builder: Pull 导出器构建器
        collect_interval_ms: 采集间隔

    Returns:
        MeterProvider 实例
    """
    meter = Meter(
        resource=resource,
        push_exporter_builder=push_exporter_builder,
        pull_exporter_builder=pull_exporter_builder,
        collect_interval_ms=collect_interval_ms,
    )
    return meter.install()


def get_meter(
    name: str,
    version: str = "",
    schema_url: str = "",
    use_app_provider: bool = False,
) -> metrics.Meter:
    """
    获取 Meter 实例

    Args:
        name: Meter 名称（通常是模块名）
        version: 版本
        schema_url: Schema URL
        use_app_provider: 是否使用 App MeterProvider

    Returns:
        Meter 实例

    示例:
        ```python
        # 使用全局 MeterProvider（基础设施指标）
        meter = get_meter("my.module")

        # 使用 App MeterProvider（业务指标）
        meter = get_meter("my.business", use_app_provider=True)

        counter = meter.create_counter("requests_total")
        counter.add(1)
        ```
    """
    if use_app_provider:
        provider = get_app_meter_provider()
        if provider:
            return provider.get_meter(
                name=name,
                version=version,
                schema_url=schema_url,
            )
        logger.warning("App MeterProvider not initialized, using global provider")

    return metrics.get_meter(
        name=name,
        version=version,
        schema_url=schema_url,
    )
