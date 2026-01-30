# -*- coding: utf-8 -*-
"""
OpenTelemetry Tracer 核心实现

提供：
- TracerProvider 创建和管理
- 导出器接口定义
- 全局 Tracer 访问
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    BatchSpanProcessor,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import (
    Sampler,
    TraceIdRatioBased,
    ALWAYS_ON,
    ALWAYS_OFF,
)

logger = logging.getLogger(__name__)


class TracerExporterBuilder(ABC):
    """
    Tracer 导出器构建器接口

    所有导出器实现都需要实现此接口。
    """

    @abstractmethod
    def build(self) -> SpanExporter:
        """
        构建 SpanExporter

        Returns:
            SpanExporter 实例
        """
        pass


class Tracer:
    """
    Tracer 管理器

    负责：
    - 创建和配置 TracerProvider
    - 管理 SpanExporter
    - 设置全局 TracerProvider
    """

    def __init__(
        self,
        resource: Resource,
        exporter_builder: Optional[TracerExporterBuilder] = None,
        sample_ratio: float = 1.0,
        batch_timeout_ms: int = 5000,
        use_batch_processor: bool = True,
    ):
        """
        初始化 Tracer

        Args:
            resource: OpenTelemetry Resource
            exporter_builder: 导出器构建器
            sample_ratio: 采样率（0.0-1.0）
            batch_timeout_ms: 批量导出超时（毫秒）
            use_batch_processor: 是否使用批量处理器
        """
        self._resource = resource
        self._exporter_builder = exporter_builder
        self._sample_ratio = sample_ratio
        self._batch_timeout_ms = batch_timeout_ms
        self._use_batch_processor = use_batch_processor
        self._provider: Optional[TracerProvider] = None

    def _create_sampler(self) -> Sampler:
        """创建采样器"""
        if self._sample_ratio <= 0:
            return ALWAYS_OFF
        if self._sample_ratio >= 1.0:
            return ALWAYS_ON
        return TraceIdRatioBased(self._sample_ratio)

    def _create_span_processor(self, exporter: SpanExporter) -> SpanProcessor:
        """创建 Span 处理器"""
        if self._use_batch_processor:
            return BatchSpanProcessor(
                exporter,
                schedule_delay_millis=self._batch_timeout_ms,
            )
        return SimpleSpanProcessor(exporter)

    def install(self) -> TracerProvider:
        """
        安装 TracerProvider

        创建 TracerProvider 并设置为全局 Provider。

        Returns:
            TracerProvider 实例
        """
        # 创建 TracerProvider
        sampler = self._create_sampler()
        self._provider = TracerProvider(
            resource=self._resource,
            sampler=sampler,
        )

        # 添加导出器
        if self._exporter_builder:
            exporter = self._exporter_builder.build()
            processor = self._create_span_processor(exporter)
            self._provider.add_span_processor(processor)

        # 设置全局 Provider
        trace.set_tracer_provider(self._provider)

        logger.info(
            "Tracer installed: sample_ratio=%.2f, batch_timeout=%dms",
            self._sample_ratio,
            self._batch_timeout_ms,
        )

        return self._provider

    def shutdown(self) -> None:
        """关闭 TracerProvider"""
        if self._provider:
            self._provider.shutdown()
            logger.info("Tracer shutdown completed")

    @property
    def provider(self) -> Optional[TracerProvider]:
        """获取 TracerProvider"""
        return self._provider


def install_tracer(
    resource: Resource,
    exporter_builder: Optional[TracerExporterBuilder] = None,
    sample_ratio: float = 1.0,
    batch_timeout_ms: int = 5000,
) -> TracerProvider:
    """
    快捷函数：安装 Tracer

    Args:
        resource: OpenTelemetry Resource
        exporter_builder: 导出器构建器
        sample_ratio: 采样率
        batch_timeout_ms: 批量超时

    Returns:
        TracerProvider 实例
    """
    tracer = Tracer(
        resource=resource,
        exporter_builder=exporter_builder,
        sample_ratio=sample_ratio,
        batch_timeout_ms=batch_timeout_ms,
    )
    return tracer.install()


def get_tracer(
    name: str,
    version: str = "",
    schema_url: str = "",
) -> trace.Tracer:
    """
    获取 Tracer 实例

    Args:
        name: Tracer 名称（通常是模块名）
        version: 版本
        schema_url: Schema URL

    Returns:
        Tracer 实例

    示例:
        ```python
        tracer = get_tracer("my.module")
        with tracer.start_as_current_span("my-operation") as span:
            span.set_attribute("key", "value")
            # do something
        ```
    """
    return trace.get_tracer(
        instrumenting_module_name=name,
        instrumenting_library_version=version,
        schema_url=schema_url,
    )
