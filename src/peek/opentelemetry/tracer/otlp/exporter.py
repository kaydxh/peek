# -*- coding: utf-8 -*-
"""
OTLP Trace 导出器

支持：
- HTTP 协议
- gRPC 协议
- gzip 压缩
- 自定义 Headers
"""

import logging
from typing import Dict, Optional

from opentelemetry.sdk.trace.export import SpanExporter

from peek.opentelemetry.tracer.tracer import TracerExporterBuilder
from peek.opentelemetry.config import OTLPProtocol

logger = logging.getLogger(__name__)


class OTLPTraceExporterBuilder(TracerExporterBuilder):
    """
    OTLP Trace 导出器构建器

    示例:
        ```python
        builder = OTLPTraceExporterBuilder(
            endpoint="localhost:4317",
            protocol=OTLPProtocol.GRPC,
            compression=True,
        )
        exporter = builder.build()
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
    ):
        """
        初始化 OTLP Trace 导出器构建器

        Args:
            endpoint: OTLP 端点地址
            protocol: 协议类型（grpc/http）
            headers: 请求头
            compression: 是否启用 gzip 压缩
            insecure: 是否禁用 TLS
            timeout_ms: 超时时间（毫秒）
        """
        self._endpoint = endpoint
        self._protocol = protocol
        self._headers = headers or {}
        self._compression = compression
        self._insecure = insecure
        self._timeout_ms = timeout_ms

    def build(self) -> SpanExporter:
        """构建 SpanExporter"""
        if self._protocol == OTLPProtocol.HTTP:
            return self._build_http_exporter()
        return self._build_grpc_exporter()

    def _build_http_exporter(self) -> SpanExporter:
        """构建 HTTP 导出器"""
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        # 构建端点 URL
        endpoint = self._endpoint
        if not endpoint.startswith("http"):
            scheme = "http" if self._insecure else "https"
            endpoint = f"{scheme}://{endpoint}"
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"

        # 配置压缩
        compression = None
        if self._compression:
            from opentelemetry.exporter.otlp.proto.http import Compression
            compression = Compression.Gzip

        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=self._headers,
            timeout=self._timeout_ms / 1000,
            compression=compression,
        )

        logger.info(
            "OTLP HTTP Trace exporter created: endpoint=%s, compression=%s",
            endpoint,
            self._compression,
        )

        return exporter

    def _build_grpc_exporter(self) -> SpanExporter:
        """构建 gRPC 导出器"""
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        # 配置压缩
        compression = None
        if self._compression:
            from grpc import Compression
            compression = Compression.Gzip

        exporter = OTLPSpanExporter(
            endpoint=self._endpoint,
            headers=self._headers if self._headers else None,
            timeout=self._timeout_ms / 1000,
            insecure=self._insecure,
            compression=compression,
        )

        logger.info(
            "OTLP gRPC Trace exporter created: endpoint=%s, insecure=%s, compression=%s",
            self._endpoint,
            self._insecure,
            self._compression,
        )

        return exporter
