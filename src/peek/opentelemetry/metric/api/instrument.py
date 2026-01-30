# -*- coding: utf-8 -*-
"""
Metric API 面向对象接口

提供：
- Counter 类
- Histogram 类
- Timer 类
- Gauge 类
- 链式调用支持
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from opentelemetry import metrics
from opentelemetry.metrics import Counter as OtelCounter
from opentelemetry.metrics import Histogram as OtelHistogram
from opentelemetry.metrics import UpDownCounter as OtelUpDownCounter

from peek.opentelemetry.metric.meter import get_app_meter_provider

logger = logging.getLogger(__name__)


class Instrument:
    """
    Instrument 基类

    提供公共功能：
    - 属性管理
    - 链式调用
    - 双 Provider 支持
    """

    def __init__(
        self,
        meter_name: str,
        instrument_name: str,
        unit: str = "",
        description: str = "",
        use_app_provider: bool = True,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化 Instrument

        Args:
            meter_name: Meter 名称
            instrument_name: 指标名称
            unit: 单位
            description: 描述
            use_app_provider: 是否使用 App MeterProvider
            attributes: 默认属性
        """
        self._meter_name = meter_name
        self._instrument_name = instrument_name
        self._unit = unit
        self._description = description
        self._use_app_provider = use_app_provider
        self._attributes: Dict[str, Any] = attributes.copy() if attributes else {}
        self._meter: Optional[metrics.Meter] = None

    def _get_meter(self) -> Optional[metrics.Meter]:
        """获取 Meter"""
        if self._meter:
            return self._meter

        if self._use_app_provider:
            provider = get_app_meter_provider()
            if provider:
                self._meter = provider.get_meter(self._meter_name)
                return self._meter

        self._meter = metrics.get_meter(self._meter_name)
        return self._meter

    def with_attr(self, key: str, value: Any) -> "Instrument":
        """
        添加属性（链式调用）

        返回新的 Instrument 实例，不修改原实例。

        Args:
            key: 属性键
            value: 属性值

        Returns:
            新的 Instrument 实例

        示例:
            ```python
            counter.with_attr("method", "GET").with_attr("status", 200).add(1)
            ```
        """
        new_attrs = self._attributes.copy()
        new_attrs[key] = value
        return self._clone(attributes=new_attrs)

    def with_attrs(self, **attrs: Any) -> "Instrument":
        """
        批量添加属性（链式调用）

        Args:
            **attrs: 属性键值对

        Returns:
            新的 Instrument 实例

        示例:
            ```python
            counter.with_attrs(method="GET", status=200).add(1)
            ```
        """
        new_attrs = self._attributes.copy()
        new_attrs.update(attrs)
        return self._clone(attributes=new_attrs)

    def _clone(self, attributes: Dict[str, Any]) -> "Instrument":
        """克隆实例（子类需要覆写）"""
        raise NotImplementedError

    def _to_attributes(self) -> Dict[str, Any]:
        """转换属性为 OpenTelemetry 格式"""
        return {
            k: str(v) if not isinstance(v, (str, int, float, bool)) else v
            for k, v in self._attributes.items()
        }


class Counter(Instrument):
    """
    Counter 计数器

    只增不减的计数器，适用于请求数、错误数等。

    示例:
        ```python
        # 创建 Counter
        counter = Counter("http", "requests_total", unit="1")

        # 简单使用
        counter.add(1)

        # 链式调用添加属性
        counter.with_attr("method", "GET").with_attr("status", 200).add(1)

        # 批量添加属性
        counter.with_attrs(method="POST", status=201).add(1)

        # +1 快捷方法
        counter.incr()
        ```
    """

    def __init__(
        self,
        meter_name: str,
        instrument_name: str,
        unit: str = "1",
        description: str = "",
        use_app_provider: bool = True,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            meter_name=meter_name,
            instrument_name=instrument_name,
            unit=unit,
            description=description,
            use_app_provider=use_app_provider,
            attributes=attributes,
        )
        self._counter: Optional[OtelCounter] = None

    def _get_counter(self) -> Optional[OtelCounter]:
        """获取或创建 Counter"""
        if self._counter:
            return self._counter

        meter = self._get_meter()
        if not meter:
            return None

        self._counter = meter.create_counter(
            name=self._instrument_name,
            unit=self._unit,
            description=self._description,
        )
        return self._counter

    def _clone(self, attributes: Dict[str, Any]) -> "Counter":
        """克隆实例"""
        clone = Counter(
            meter_name=self._meter_name,
            instrument_name=self._instrument_name,
            unit=self._unit,
            description=self._description,
            use_app_provider=self._use_app_provider,
            attributes=attributes,
        )
        clone._counter = self._counter
        clone._meter = self._meter
        return clone

    def add(self, value: int = 1) -> None:
        """
        增加计数

        Args:
            value: 增加值（必须 >= 0）
        """
        counter = self._get_counter()
        if counter:
            counter.add(value, attributes=self._to_attributes())

    def incr(self) -> None:
        """+1"""
        self.add(1)


class Histogram(Instrument):
    """
    Histogram 直方图

    记录值的分布，适用于延迟、大小等。

    示例:
        ```python
        # 创建 Histogram
        histogram = Histogram("http", "request_duration_ms", unit="ms")

        # 记录值
        histogram.record(123.45)

        # 链式调用添加属性
        histogram.with_attr("method", "GET").record(50.0)
        ```
    """

    def __init__(
        self,
        meter_name: str,
        instrument_name: str,
        unit: str = "ms",
        description: str = "",
        use_app_provider: bool = True,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            meter_name=meter_name,
            instrument_name=instrument_name,
            unit=unit,
            description=description,
            use_app_provider=use_app_provider,
            attributes=attributes,
        )
        self._histogram: Optional[OtelHistogram] = None

    def _get_histogram(self) -> Optional[OtelHistogram]:
        """获取或创建 Histogram"""
        if self._histogram:
            return self._histogram

        meter = self._get_meter()
        if not meter:
            return None

        self._histogram = meter.create_histogram(
            name=self._instrument_name,
            unit=self._unit,
            description=self._description,
        )
        return self._histogram

    def _clone(self, attributes: Dict[str, Any]) -> "Histogram":
        """克隆实例"""
        clone = Histogram(
            meter_name=self._meter_name,
            instrument_name=self._instrument_name,
            unit=self._unit,
            description=self._description,
            use_app_provider=self._use_app_provider,
            attributes=attributes,
        )
        clone._histogram = self._histogram
        clone._meter = self._meter
        return clone

    def record(self, value: float) -> None:
        """
        记录值

        Args:
            value: 记录值
        """
        histogram = self._get_histogram()
        if histogram:
            histogram.record(value, attributes=self._to_attributes())


class Timer(Histogram):
    """
    Timer 计时器

    基于 Histogram 的计时器封装，支持上下文管理器。

    示例:
        ```python
        # 创建 Timer
        timer = Timer("http", "request_duration_ms")

        # 手动记录
        timer.record_duration(123.45)

        # 上下文管理器
        with timer.time():
            # do something
            pass

        # 带属性的计时
        with timer.with_attr("method", "GET").time():
            # do something
            pass
        ```
    """

    def __init__(
        self,
        meter_name: str,
        instrument_name: str,
        unit: str = "ms",
        description: str = "",
        use_app_provider: bool = True,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            meter_name=meter_name,
            instrument_name=instrument_name,
            unit=unit,
            description=description,
            use_app_provider=use_app_provider,
            attributes=attributes,
        )

    def _clone(self, attributes: Dict[str, Any]) -> "Timer":
        """克隆实例"""
        clone = Timer(
            meter_name=self._meter_name,
            instrument_name=self._instrument_name,
            unit=self._unit,
            description=self._description,
            use_app_provider=self._use_app_provider,
            attributes=attributes,
        )
        clone._histogram = self._histogram
        clone._meter = self._meter
        return clone

    def record_duration(self, duration_ms: float) -> None:
        """记录耗时（毫秒）"""
        self.record(duration_ms)

    @contextmanager
    def time(self):
        """
        计时上下文管理器

        自动记录代码块执行时间。

        Yields:
            None
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.record_duration(duration_ms)


class Gauge(Instrument):
    """
    Gauge 仪表

    可增可减的值，适用于温度、内存使用等。

    示例:
        ```python
        # 创建 Gauge
        gauge = Gauge("system", "memory_usage_bytes", unit="bytes")

        # 设置值
        gauge.set(1024 * 1024 * 100)

        # 增加/减少
        gauge.add(100)
        gauge.add(-50)
        ```
    """

    def __init__(
        self,
        meter_name: str,
        instrument_name: str,
        unit: str = "1",
        description: str = "",
        use_app_provider: bool = True,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            meter_name=meter_name,
            instrument_name=instrument_name,
            unit=unit,
            description=description,
            use_app_provider=use_app_provider,
            attributes=attributes,
        )
        self._gauge: Optional[OtelUpDownCounter] = None

    def _get_gauge(self) -> Optional[OtelUpDownCounter]:
        """获取或创建 Gauge"""
        if self._gauge:
            return self._gauge

        meter = self._get_meter()
        if not meter:
            return None

        self._gauge = meter.create_up_down_counter(
            name=self._instrument_name,
            unit=self._unit,
            description=self._description,
        )
        return self._gauge

    def _clone(self, attributes: Dict[str, Any]) -> "Gauge":
        """克隆实例"""
        clone = Gauge(
            meter_name=self._meter_name,
            instrument_name=self._instrument_name,
            unit=self._unit,
            description=self._description,
            use_app_provider=self._use_app_provider,
            attributes=attributes,
        )
        clone._gauge = self._gauge
        clone._meter = self._meter
        return clone

    def add(self, value: int) -> None:
        """
        增加/减少值

        Args:
            value: 变化值（可正可负）
        """
        gauge = self._get_gauge()
        if gauge:
            gauge.add(value, attributes=self._to_attributes())

    def set(self, value: int) -> None:
        """
        设置值

        注意：OpenTelemetry 的 UpDownCounter 不支持直接设置值，
        这里通过增加差值来模拟。

        Args:
            value: 目标值
        """
        # TODO: 如果需要真正的 set 功能，需要使用 ObservableGauge
        logger.warning(
            "Gauge.set() is not fully supported in OpenTelemetry, consider using add()"
        )
        self.add(value)
