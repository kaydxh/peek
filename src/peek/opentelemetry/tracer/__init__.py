# -*- coding: utf-8 -*-
"""
OpenTelemetry Tracer 模块

提供分布式追踪功能：
- OTLP 导出器（HTTP/gRPC）
- Stdout 导出器（调试用）
- TracerProvider 管理
"""

from peek.opentelemetry.tracer.tracer import (
    Tracer,
    TracerExporterBuilder,
    install_tracer,
    get_tracer,
)

__all__ = [
    "Tracer",
    "TracerExporterBuilder",
    "install_tracer",
    "get_tracer",
]
