# -*- coding: utf-8 -*-
"""
Stdout Trace 导出器

用于调试，将 Span 输出到控制台。
"""

import logging
from typing import Optional, TextIO
import sys

from opentelemetry.sdk.trace.export import SpanExporter, ConsoleSpanExporter

from peek.opentelemetry.tracer.tracer import TracerExporterBuilder

logger = logging.getLogger(__name__)


class StdoutTraceExporterBuilder(TracerExporterBuilder):
    """
    Stdout Trace 导出器构建器

    示例:
        ```python
        builder = StdoutTraceExporterBuilder(pretty_print=True)
        exporter = builder.build()
        ```
    """

    def __init__(
        self,
        pretty_print: bool = True,
        out: Optional[TextIO] = None,
    ):
        """
        初始化 Stdout 导出器构建器

        Args:
            pretty_print: 是否格式化输出
            out: 输出流（默认 stdout）
        """
        self._pretty_print = pretty_print
        self._out = out or sys.stdout

    def build(self) -> SpanExporter:
        """构建 SpanExporter"""
        # 使用格式化函数
        formatter = None
        if self._pretty_print:
            import json

            def formatter(span):
                return json.dumps(
                    {
                        "name": span.name,
                        "trace_id": format(span.context.trace_id, "032x"),
                        "span_id": format(span.context.span_id, "016x"),
                        "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
                        "start_time": span.start_time,
                        "end_time": span.end_time,
                        "status": str(span.status.status_code),
                        "attributes": dict(span.attributes) if span.attributes else {},
                    },
                    indent=2,
                    default=str,
                )

        exporter = ConsoleSpanExporter(
            out=self._out,
            formatter=formatter if self._pretty_print else None,
        )

        logger.info("Stdout Trace exporter created: pretty_print=%s", self._pretty_print)

        return exporter
