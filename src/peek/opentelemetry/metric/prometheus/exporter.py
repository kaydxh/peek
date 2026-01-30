# -*- coding: utf-8 -*-
"""
Prometheus Metric 导出器

提供：
- Pull 模式导出
- 全局 Registry 管理
- /metrics 端点处理
"""

import logging
from typing import Optional

from opentelemetry.sdk.metrics.export import MetricReader

from peek.opentelemetry.metric.meter import PullExporterBuilder

logger = logging.getLogger(__name__)

# ========== 全局 Prometheus Registry ==========
_prometheus_registry = None
_prometheus_reader: Optional[MetricReader] = None


def get_prometheus_registry():
    """
    获取全局 Prometheus Registry

    Returns:
        Prometheus Registry 实例
    """
    global _prometheus_registry
    if _prometheus_registry is None:
        try:
            from prometheus_client import CollectorRegistry, REGISTRY
            from prometheus_client import multiprocess, values

            # 使用默认 Registry
            _prometheus_registry = REGISTRY
        except ImportError:
            logger.warning("prometheus_client not installed, using None registry")
            return None

    return _prometheus_registry


def get_metrics_handler():
    """
    获取 /metrics 端点处理器

    用于 FastAPI/Flask 等框架集成。

    Returns:
        WSGI 应用

    示例:
        ```python
        # FastAPI
        from starlette.responses import Response

        @app.get("/metrics")
        async def metrics():
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            return Response(
                content=generate_latest(get_prometheus_registry()),
                media_type=CONTENT_TYPE_LATEST,
            )

        # 或使用提供的处理器
        from peek.opentelemetry.metric.prometheus import get_metrics_handler
        app.mount("/metrics", get_metrics_handler())
        ```
    """
    try:
        from prometheus_client import make_wsgi_app
        return make_wsgi_app(registry=get_prometheus_registry())
    except ImportError:
        logger.warning("prometheus_client not installed")
        return None


class PrometheusExporterBuilder(PullExporterBuilder):
    """
    Prometheus 导出器构建器

    示例:
        ```python
        builder = PrometheusExporterBuilder(
            namespace="myapp",
        )
        reader = builder.build()
        ```
    """

    def __init__(
        self,
        namespace: str = "",
        enable_runtime_metrics: bool = True,
    ):
        """
        初始化 Prometheus 导出器构建器

        Args:
            namespace: 指标命名空间前缀
            enable_runtime_metrics: 是否启用运行时指标
        """
        self._namespace = namespace
        self._enable_runtime_metrics = enable_runtime_metrics

    def build(self) -> MetricReader:
        """构建 MetricReader"""
        from opentelemetry.exporter.prometheus import PrometheusMetricReader

        global _prometheus_reader

        # 创建 PrometheusMetricReader
        reader = PrometheusMetricReader(
            prefix=self._namespace if self._namespace else None,
        )

        _prometheus_reader = reader

        logger.info(
            "Prometheus Metric exporter created: namespace=%s, runtime_metrics=%s",
            self._namespace,
            self._enable_runtime_metrics,
        )

        return reader
