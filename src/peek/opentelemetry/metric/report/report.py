# -*- coding: utf-8 -*-
"""
Metric Report 指标上报

提供：
- 服务端指标上报（被调）
- 客户端指标上报（主调）
- 维度定义
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from peek.opentelemetry.metric.api.instrument import Counter, Histogram

logger = logging.getLogger(__name__)

# ========== 常量定义 ==========
SERVER_REPORT_METER_NAME = "server_report"
CLIENT_REPORT_METER_NAME = "client_report"

REQUESTS_METRIC_NAME = "requests_total"
SUCCESS_METRIC_NAME = "success_total"
FAILED_METRIC_NAME = "failed_total"
DURATION_METRIC_NAME = "duration_ms"


@dataclass
class ServerDimension:
    """
    服务端维度（被调）

    用于描述被调请求的维度信息。
    """
    service: str = ""           # 服务名
    method: str = ""            # 方法名
    protocol: str = ""          # 协议（http/grpc）
    status_code: int = 0        # 状态码
    caller: str = ""            # 调用方
    caller_ip: str = ""         # 调用方 IP
    success: bool = True        # 是否成功

    def to_attributes(self) -> Dict[str, Any]:
        """转换为属性字典"""
        attrs = {
            "service": self.service,
            "method": self.method,
            "protocol": self.protocol,
            "status_code": self.status_code,
            "success": str(self.success).lower(),
        }
        if self.caller:
            attrs["caller"] = self.caller
        if self.caller_ip:
            attrs["caller_ip"] = self.caller_ip
        return attrs


@dataclass
class ClientDimension:
    """
    客户端维度（主调）

    用于描述主调请求的维度信息。
    """
    service: str = ""           # 目标服务名
    method: str = ""            # 方法名
    protocol: str = ""          # 协议（http/grpc）
    status_code: int = 0        # 状态码
    callee: str = ""            # 被调方
    callee_ip: str = ""         # 被调方 IP
    success: bool = True        # 是否成功

    def to_attributes(self) -> Dict[str, Any]:
        """转换为属性字典"""
        attrs = {
            "service": self.service,
            "method": self.method,
            "protocol": self.protocol,
            "status_code": self.status_code,
            "success": str(self.success).lower(),
        }
        if self.callee:
            attrs["callee"] = self.callee
        if self.callee_ip:
            attrs["callee_ip"] = self.callee_ip
        return attrs


class MetricReporter:
    """
    指标上报器

    提供：
    - 服务端指标上报
    - 客户端指标上报
    - 自动管理 Instrument

    示例:
        ```python
        reporter = MetricReporter()

        # 服务端指标上报
        dim = ServerDimension(
            service="my-service",
            method="/api/v1/users",
            protocol="http",
            status_code=200,
            success=True,
        )
        reporter.report_server_metric(dim, cost_ms=123.45)

        # 客户端指标上报
        dim = ClientDimension(
            service="user-service",
            method="/api/v1/users",
            protocol="grpc",
            status_code=0,
            success=True,
        )
        reporter.report_client_metric(dim, cost_ms=50.0)
        ```
    """

    def __init__(self, use_app_provider: bool = False):
        """
        初始化指标上报器

        Args:
            use_app_provider: 是否使用 App MeterProvider
        """
        self._use_app_provider = use_app_provider

        # 服务端指标
        self._server_requests_counter: Optional[Counter] = None
        self._server_success_counter: Optional[Counter] = None
        self._server_failed_counter: Optional[Counter] = None
        self._server_duration_histogram: Optional[Histogram] = None

        # 客户端指标
        self._client_requests_counter: Optional[Counter] = None
        self._client_success_counter: Optional[Counter] = None
        self._client_failed_counter: Optional[Counter] = None
        self._client_duration_histogram: Optional[Histogram] = None

    def _get_server_requests_counter(self) -> Counter:
        """获取服务端请求计数器"""
        if not self._server_requests_counter:
            self._server_requests_counter = Counter(
                meter_name=SERVER_REPORT_METER_NAME,
                instrument_name=REQUESTS_METRIC_NAME,
                description="Total number of server requests",
                use_app_provider=self._use_app_provider,
            )
        return self._server_requests_counter

    def _get_server_success_counter(self) -> Counter:
        """获取服务端成功计数器"""
        if not self._server_success_counter:
            self._server_success_counter = Counter(
                meter_name=SERVER_REPORT_METER_NAME,
                instrument_name=SUCCESS_METRIC_NAME,
                description="Total number of successful server requests",
                use_app_provider=self._use_app_provider,
            )
        return self._server_success_counter

    def _get_server_failed_counter(self) -> Counter:
        """获取服务端失败计数器"""
        if not self._server_failed_counter:
            self._server_failed_counter = Counter(
                meter_name=SERVER_REPORT_METER_NAME,
                instrument_name=FAILED_METRIC_NAME,
                description="Total number of failed server requests",
                use_app_provider=self._use_app_provider,
            )
        return self._server_failed_counter

    def _get_server_duration_histogram(self) -> Histogram:
        """获取服务端耗时直方图"""
        if not self._server_duration_histogram:
            self._server_duration_histogram = Histogram(
                meter_name=SERVER_REPORT_METER_NAME,
                instrument_name=DURATION_METRIC_NAME,
                unit="ms",
                description="Server request duration in milliseconds",
                use_app_provider=self._use_app_provider,
            )
        return self._server_duration_histogram

    def _get_client_requests_counter(self) -> Counter:
        """获取客户端请求计数器"""
        if not self._client_requests_counter:
            self._client_requests_counter = Counter(
                meter_name=CLIENT_REPORT_METER_NAME,
                instrument_name=REQUESTS_METRIC_NAME,
                description="Total number of client requests",
                use_app_provider=self._use_app_provider,
            )
        return self._client_requests_counter

    def _get_client_success_counter(self) -> Counter:
        """获取客户端成功计数器"""
        if not self._client_success_counter:
            self._client_success_counter = Counter(
                meter_name=CLIENT_REPORT_METER_NAME,
                instrument_name=SUCCESS_METRIC_NAME,
                description="Total number of successful client requests",
                use_app_provider=self._use_app_provider,
            )
        return self._client_success_counter

    def _get_client_failed_counter(self) -> Counter:
        """获取客户端失败计数器"""
        if not self._client_failed_counter:
            self._client_failed_counter = Counter(
                meter_name=CLIENT_REPORT_METER_NAME,
                instrument_name=FAILED_METRIC_NAME,
                description="Total number of failed client requests",
                use_app_provider=self._use_app_provider,
            )
        return self._client_failed_counter

    def _get_client_duration_histogram(self) -> Histogram:
        """获取客户端耗时直方图"""
        if not self._client_duration_histogram:
            self._client_duration_histogram = Histogram(
                meter_name=CLIENT_REPORT_METER_NAME,
                instrument_name=DURATION_METRIC_NAME,
                unit="ms",
                description="Client request duration in milliseconds",
                use_app_provider=self._use_app_provider,
            )
        return self._client_duration_histogram

    def report_server_metric(
        self,
        dimension: ServerDimension,
        cost_ms: float,
    ) -> None:
        """
        上报服务端指标

        Args:
            dimension: 服务端维度
            cost_ms: 耗时（毫秒）
        """
        attrs = dimension.to_attributes()

        # 请求数
        self._get_server_requests_counter().with_attrs(**attrs).incr()

        # 成功/失败数
        if dimension.success:
            self._get_server_success_counter().with_attrs(**attrs).incr()
        else:
            self._get_server_failed_counter().with_attrs(**attrs).incr()

        # 耗时
        self._get_server_duration_histogram().with_attrs(**attrs).record(cost_ms)

    def report_client_metric(
        self,
        dimension: ClientDimension,
        cost_ms: float,
    ) -> None:
        """
        上报客户端指标

        Args:
            dimension: 客户端维度
            cost_ms: 耗时（毫秒）
        """
        attrs = dimension.to_attributes()

        # 请求数
        self._get_client_requests_counter().with_attrs(**attrs).incr()

        # 成功/失败数
        if dimension.success:
            self._get_client_success_counter().with_attrs(**attrs).incr()
        else:
            self._get_client_failed_counter().with_attrs(**attrs).incr()

        # 耗时
        self._get_client_duration_histogram().with_attrs(**attrs).record(cost_ms)


# 全局 Reporter 实例
_global_reporter: Optional[MetricReporter] = None


def get_global_reporter() -> MetricReporter:
    """获取全局 Reporter"""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = MetricReporter(use_app_provider=False)
    return _global_reporter


def report_server_metric(dimension: ServerDimension, cost_ms: float) -> None:
    """全局服务端指标上报"""
    get_global_reporter().report_server_metric(dimension, cost_ms)


def report_client_metric(dimension: ClientDimension, cost_ms: float) -> None:
    """全局客户端指标上报"""
    get_global_reporter().report_client_metric(dimension, cost_ms)
