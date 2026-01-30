# -*- coding: utf-8 -*-
"""
Metric API 函数式接口

提供：
- 双 MeterProvider 支持（Global + App）
- 函数式调用风格
- 自动 Instrument 缓存
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from opentelemetry import metrics
from opentelemetry.metrics import Counter as OtelCounter
from opentelemetry.metrics import Histogram as OtelHistogram
from opentelemetry.metrics import UpDownCounter as OtelGauge

from peek.opentelemetry.metric.meter import get_app_meter_provider

logger = logging.getLogger(__name__)

# ========== Instrument 缓存 ==========
_global_counters: Dict[Tuple[str, str], OtelCounter] = {}
_global_histograms: Dict[Tuple[str, str], OtelHistogram] = {}
_app_counters: Dict[Tuple[str, str], OtelCounter] = {}
_app_histograms: Dict[Tuple[str, str], OtelHistogram] = {}


def _get_global_meter(meter_name: str) -> metrics.Meter:
    """获取全局 Meter"""
    return metrics.get_meter(meter_name)


def _get_app_meter(meter_name: str) -> Optional[metrics.Meter]:
    """获取 App Meter"""
    provider = get_app_meter_provider()
    if provider:
        return provider.get_meter(meter_name)
    return None


def _get_global_counter(meter_name: str, instrument_name: str, unit: str = "") -> OtelCounter:
    """获取或创建全局 Counter"""
    key = (meter_name, instrument_name)
    if key not in _global_counters:
        meter = _get_global_meter(meter_name)
        _global_counters[key] = meter.create_counter(
            name=instrument_name,
            unit=unit,
        )
    return _global_counters[key]


def _get_global_histogram(
    meter_name: str,
    instrument_name: str,
    unit: str = "",
) -> OtelHistogram:
    """获取或创建全局 Histogram"""
    key = (meter_name, instrument_name)
    if key not in _global_histograms:
        meter = _get_global_meter(meter_name)
        _global_histograms[key] = meter.create_histogram(
            name=instrument_name,
            unit=unit,
        )
    return _global_histograms[key]


def _get_app_counter(meter_name: str, instrument_name: str, unit: str = "") -> Optional[OtelCounter]:
    """获取或创建 App Counter"""
    meter = _get_app_meter(meter_name)
    if not meter:
        return None

    key = (meter_name, instrument_name)
    if key not in _app_counters:
        _app_counters[key] = meter.create_counter(
            name=instrument_name,
            unit=unit,
        )
    return _app_counters[key]


def _get_app_histogram(
    meter_name: str,
    instrument_name: str,
    unit: str = "",
) -> Optional[OtelHistogram]:
    """获取或创建 App Histogram"""
    meter = _get_app_meter(meter_name)
    if not meter:
        return None

    key = (meter_name, instrument_name)
    if key not in _app_histograms:
        _app_histograms[key] = meter.create_histogram(
            name=instrument_name,
            unit=unit,
        )
    return _app_histograms[key]


def _to_attributes(attrs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """转换属性字典"""
    if not attrs:
        return {}
    return {k: str(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in attrs.items()}


# ========== 全局 API（基础设施指标）==========


def global_add_counter(
    meter_name: str,
    instrument_name: str,
    value: int = 1,
    attributes: Optional[Dict[str, Any]] = None,
    unit: str = "",
) -> None:
    """
    全局 Counter 增加（基础设施指标）

    Args:
        meter_name: Meter 名称
        instrument_name: 指标名称
        value: 增加值
        attributes: 属性字典
        unit: 单位

    示例:
        ```python
        global_add_counter(
            "http",
            "requests_total",
            value=1,
            attributes={"method": "GET", "status": "200"},
        )
        ```
    """
    counter = _get_global_counter(meter_name, instrument_name, unit)
    counter.add(value, attributes=_to_attributes(attributes))


def global_incr_counter(
    meter_name: str,
    instrument_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    unit: str = "",
) -> None:
    """全局 Counter +1"""
    global_add_counter(meter_name, instrument_name, 1, attributes, unit)


def global_record_histogram(
    meter_name: str,
    instrument_name: str,
    value: float,
    attributes: Optional[Dict[str, Any]] = None,
    unit: str = "",
) -> None:
    """
    全局 Histogram 记录（基础设施指标）

    Args:
        meter_name: Meter 名称
        instrument_name: 指标名称
        value: 记录值
        attributes: 属性字典
        unit: 单位

    示例:
        ```python
        global_record_histogram(
            "http",
            "request_duration_ms",
            value=123.45,
            attributes={"method": "GET"},
            unit="ms",
        )
        ```
    """
    histogram = _get_global_histogram(meter_name, instrument_name, unit)
    histogram.record(value, attributes=_to_attributes(attributes))


def global_record_duration(
    meter_name: str,
    instrument_name: str,
    duration_ms: float,
    attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """全局记录耗时（毫秒）"""
    global_record_histogram(meter_name, instrument_name, duration_ms, attributes, unit="ms")


@contextmanager
def global_timer(
    meter_name: str,
    instrument_name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    全局计时器上下文管理器

    示例:
        ```python
        with global_timer("http", "request_duration_ms", {"method": "GET"}):
            # do something
            pass
        ```
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        global_record_duration(meter_name, instrument_name, duration_ms, attributes)


# ========== App API（业务指标）==========


def add_counter(
    meter_name: str,
    instrument_name: str,
    value: int = 1,
    attributes: Optional[Dict[str, Any]] = None,
    unit: str = "",
) -> None:
    """
    App Counter 增加（业务指标）

    使用 App MeterProvider，如果未配置则不上报。

    Args:
        meter_name: Meter 名称
        instrument_name: 指标名称
        value: 增加值
        attributes: 属性字典
        unit: 单位

    示例:
        ```python
        add_counter(
            "business",
            "orders_total",
            value=1,
            attributes={"region": "us-west", "type": "premium"},
        )
        ```
    """
    counter = _get_app_counter(meter_name, instrument_name, unit)
    if counter:
        counter.add(value, attributes=_to_attributes(attributes))


def incr_counter(
    meter_name: str,
    instrument_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    unit: str = "",
) -> None:
    """App Counter +1"""
    add_counter(meter_name, instrument_name, 1, attributes, unit)


def record_histogram(
    meter_name: str,
    instrument_name: str,
    value: float,
    attributes: Optional[Dict[str, Any]] = None,
    unit: str = "",
) -> None:
    """
    App Histogram 记录（业务指标）

    使用 App MeterProvider，如果未配置则不上报。

    Args:
        meter_name: Meter 名称
        instrument_name: 指标名称
        value: 记录值
        attributes: 属性字典
        unit: 单位

    示例:
        ```python
        record_histogram(
            "business",
            "order_amount",
            value=99.99,
            attributes={"currency": "USD"},
            unit="USD",
        )
        ```
    """
    histogram = _get_app_histogram(meter_name, instrument_name, unit)
    if histogram:
        histogram.record(value, attributes=_to_attributes(attributes))


def record_duration(
    meter_name: str,
    instrument_name: str,
    duration_ms: float,
    attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """App 记录耗时（毫秒）"""
    record_histogram(meter_name, instrument_name, duration_ms, attributes, unit="ms")


@contextmanager
def timer(
    meter_name: str,
    instrument_name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    App 计时器上下文管理器

    示例:
        ```python
        with timer("business", "process_duration_ms", {"type": "async"}):
            # do something
            pass
        ```
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        record_duration(meter_name, instrument_name, duration_ms, attributes)
