# -*- coding: utf-8 -*-
"""
OTLP Metric 导出器

支持：
- HTTP 协议
- gRPC 协议
- gzip 压缩
- Delta Temporality（智研平台要求）
"""

import logging
from typing import Dict, Optional

from opentelemetry.sdk.metrics.export import (
    MetricReader,
    PeriodicExportingMetricReader,
    AggregationTemporality,
)

from peek.opentelemetry.metric.meter import PushExporterBuilder
from peek.opentelemetry.config import OTLPProtocol, TemporalityType

logger = logging.getLogger(__name__)


def _get_delta_temporality_selector(instrument_type):
    """Delta Temporality 选择器（智研平台要求）"""
    return AggregationTemporality.DELTA


def _get_cumulative_temporality_selector(instrument_type):
    """Cumulative Temporality 选择器（默认）"""
    return AggregationTemporality.CUMULATIVE


class OTLPMetricExporterBuilder(PushExporterBuilder):
    """
    OTLP Metric 导出器构建器

    示例:
        ```python
        builder = OTLPMetricExporterBuilder(
            endpoint="localhost:4317",
            protocol=OTLPProtocol.GRPC,
            compression=True,
            temporality=TemporalityType.DELTA,  # 智研平台
        )
        reader = builder.build()
        ```
    """

    def __init__(
        self,
        endpoint: str = "localhost:4317",
        protocol: OTLPProtocol = OTLPProtocol.GRPC,
        headers: Optional[Dict[str, str]] = None,
        compression: bool = False,
        insecure: bool = True,
        timeout_ms: int = 10000,
        temporality: TemporalityType = TemporalityType.CUMULATIVE,
        export_interval_ms: int = 60000,
    ):
        """
        初始化 OTLP Metric 导出器构建器

        Args:
            endpoint: OTLP 端点地址
            protocol: 协议类型（grpc/http）
            headers: 请求头
            compression: 是否启用 gzip 压缩
            insecure: 是否禁用 TLS
            timeout_ms: 超时时间（毫秒）
            temporality: Temporality 类型（cumulative/delta）
            export_interval_ms: 导出间隔（毫秒）
        """
        self._endpoint = endpoint
        self._protocol = protocol
        self._headers = headers or {}
        self._compression = compression
        self._insecure = insecure
        self._timeout_ms = timeout_ms
        self._temporality = temporality
        self._export_interval_ms = export_interval_ms

    def build(self) -> MetricReader:
        """构建 MetricReader"""
        if self._protocol == OTLPProtocol.HTTP:
            return self._build_http_exporter()
        return self._build_grpc_exporter()

    def _get_temporality_selector(self):
        """获取 Temporality 选择器"""
        if self._temporality == TemporalityType.DELTA:
            return _get_delta_temporality_selector
        return _get_cumulative_temporality_selector

    def _build_http_exporter(self) -> MetricReader:
        """构建 HTTP 导出器"""
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )

        # 构建端点 URL
        endpoint = self._endpoint
        if not endpoint.startswith("http"):
            scheme = "http" if self._insecure else "https"
            endpoint = f"{scheme}://{endpoint}"
        if not endpoint.endswith("/v1/metrics"):
            endpoint = f"{endpoint}/v1/metrics"

        # 配置压缩
        compression = None
        if self._compression:
            from opentelemetry.exporter.otlp.proto.http import Compression
            compression = Compression.Gzip

        exporter = OTLPMetricExporter(
            endpoint=endpoint,
            headers=self._headers,
            timeout=self._timeout_ms / 1000,
            compression=compression,
            preferred_temporality=self._get_temporality_selector(),
        )

        logger.info(
            "OTLP HTTP Metric exporter created: endpoint=%s, temporality=%s, compression=%s",
            endpoint,
            self._temporality.value,
            self._compression,
        )

        return PeriodicExportingMetricReader(
            exporter=exporter,
            export_interval_millis=self._export_interval_ms,
        )

    def _build_grpc_exporter(self) -> MetricReader:
        """构建 gRPC 导出器"""
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )

        # 配置压缩
        compression = None
        if self._compression:
            from grpc import Compression
            compression = Compression.Gzip

        exporter = OTLPMetricExporter(
            endpoint=self._endpoint,
            headers=self._headers if self._headers else None,
            timeout=self._timeout_ms / 1000,
            insecure=self._insecure,
            compression=compression,
            preferred_temporality=self._get_temporality_selector(),
        )

        logger.info(
            "OTLP gRPC Metric exporter created: endpoint=%s, temporality=%s, insecure=%s, compression=%s",
            self._endpoint,
            self._temporality.value,
            self._insecure,
            self._compression,
        )

        return PeriodicExportingMetricReader(
            exporter=exporter,
            export_interval_millis=self._export_interval_ms,
        )
