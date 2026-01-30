# -*- coding: utf-8 -*-
"""
Metric Report 模块

提供服务端/客户端指标上报功能：
- ServerDimension：服务端维度
- ClientDimension：客户端维度
- MetricReporter：指标上报器
"""

from peek.opentelemetry.metric.report.report import (
    MetricReporter,
    ServerDimension,
    ClientDimension,
    SERVER_REPORT_METER_NAME,
    CLIENT_REPORT_METER_NAME,
    REQUESTS_METRIC_NAME,
    SUCCESS_METRIC_NAME,
    FAILED_METRIC_NAME,
    DURATION_METRIC_NAME,
)

__all__ = [
    "MetricReporter",
    "ServerDimension",
    "ClientDimension",
    "SERVER_REPORT_METER_NAME",
    "CLIENT_REPORT_METER_NAME",
    "REQUESTS_METRIC_NAME",
    "SUCCESS_METRIC_NAME",
    "FAILED_METRIC_NAME",
    "DURATION_METRIC_NAME",
]
