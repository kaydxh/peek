# -*- coding: utf-8 -*-
"""
Stdout Metric 导出器

用于调试，将 Metric 输出到控制台。
"""

import logging
import sys
from typing import Optional, TextIO

from opentelemetry.sdk.metrics.export import (
    MetricReader,
    PeriodicExportingMetricReader,
    ConsoleMetricExporter,
)

from peek.opentelemetry.metric.meter import PushExporterBuilder

logger = logging.getLogger(__name__)


class StdoutMetricExporterBuilder(PushExporterBuilder):
    """
    Stdout Metric 导出器构建器

    示例:
        ```python
        builder = StdoutMetricExporterBuilder(pretty_print=True)
        reader = builder.build()
        ```
    """

    def __init__(
        self,
        pretty_print: bool = True,
        out: Optional[TextIO] = None,
        export_interval_ms: int = 60000,
    ):
        """
        初始化 Stdout 导出器构建器

        Args:
            pretty_print: 是否格式化输出
            out: 输出流（默认 stdout）
            export_interval_ms: 导出间隔（毫秒）
        """
        self._pretty_print = pretty_print
        self._out = out or sys.stdout
        self._export_interval_ms = export_interval_ms

    def build(self) -> MetricReader:
        """构建 MetricReader"""
        # 使用格式化函数
        formatter = None
        if self._pretty_print:
            import json

            def formatter(metric):
                return json.dumps(metric, indent=2, default=str)

        exporter = ConsoleMetricExporter(
            out=self._out,
            formatter=formatter if self._pretty_print else None,
        )

        logger.info("Stdout Metric exporter created: pretty_print=%s", self._pretty_print)

        return PeriodicExportingMetricReader(
            exporter=exporter,
            export_interval_millis=self._export_interval_ms,
        )
