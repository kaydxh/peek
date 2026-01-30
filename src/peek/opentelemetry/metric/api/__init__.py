# -*- coding: utf-8 -*-
"""
Metric API 模块

提供简洁的 Metric 上报 API：
- Counter：计数器
- Histogram：直方图
- Timer：计时器
- 支持双 MeterProvider（Global + App）
"""

from peek.opentelemetry.metric.api.api import (
    # 全局 API（基础设施指标）
    global_add_counter,
    global_incr_counter,
    global_record_histogram,
    global_record_duration,
    # App API（业务指标）
    add_counter,
    incr_counter,
    record_histogram,
    record_duration,
)

from peek.opentelemetry.metric.api.instrument import (
    Counter,
    Histogram,
    Timer,
    Gauge,
)

__all__ = [
    # 全局 API
    "global_add_counter",
    "global_incr_counter",
    "global_record_histogram",
    "global_record_duration",
    # App API
    "add_counter",
    "incr_counter",
    "record_histogram",
    "record_duration",
    # Instrument 类
    "Counter",
    "Histogram",
    "Timer",
    "Gauge",
]
