#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OpenTelemetry 追踪中间件

参考 Go 版本 golang 库的 trace.interceptor.go 实现
"""

import time
from typing import Any, Awaitable, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# 尝试导入 OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.propagate import extract, inject
    from opentelemetry.semconv.trace import SpanAttributes

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None


class TraceMiddleware(BaseHTTPMiddleware):
    """
    OpenTelemetry 追踪中间件

    为每个请求创建 Span，记录请求信息
    """

    def __init__(
        self,
        app: ASGIApp,
        tracer_name: str = "webserver",
        tracer_version: str = "1.0.0",
        record_request_body: bool = False,
        record_response_body: bool = False,
    ):
        """
        Args:
            app: ASGI 应用
            tracer_name: Tracer 名称
            tracer_version: Tracer 版本
            record_request_body: 是否记录请求体
            record_response_body: 是否记录响应体
        """
        super().__init__(app)
        self.tracer_name = tracer_name
        self.tracer_version = tracer_version
        self.record_request_body = record_request_body
        self.record_response_body = record_response_body

        if OTEL_AVAILABLE:
            self._tracer = trace.get_tracer(tracer_name, tracer_version)
            self._propagator = TraceContextTextMapPropagator()
        else:
            self._tracer = None
            self._propagator = None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not OTEL_AVAILABLE or not self._tracer:
            return await call_next(request)

        # 从请求头提取上下文
        carrier = dict(request.headers)
        ctx = extract(carrier)

        # 创建 Span
        span_name = f"{request.method} {request.url.path}"

        with self._tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=SpanKind.SERVER,
        ) as span:
            # 设置 Span 属性
            span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)
            span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
            span.set_attribute(SpanAttributes.HTTP_SCHEME, request.url.scheme)
            span.set_attribute(SpanAttributes.HTTP_HOST, request.url.hostname or "")
            span.set_attribute(SpanAttributes.HTTP_TARGET, request.url.path)

            # 获取 request_id（如果存在）
            request_id = getattr(request.state, "request_id", None)
            if request_id:
                span.set_attribute("request.id", request_id)

            # 客户端信息
            if request.client:
                span.set_attribute(SpanAttributes.NET_PEER_IP, request.client.host)
                span.set_attribute(SpanAttributes.NET_PEER_PORT, request.client.port)

            # User-Agent
            user_agent = request.headers.get("user-agent")
            if user_agent:
                span.set_attribute(SpanAttributes.HTTP_USER_AGENT, user_agent)

            try:
                response = await call_next(request)

                # 设置响应状态码
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)

                # 根据状态码设置 Span 状态
                if response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR))
                else:
                    span.set_status(Status(StatusCode.OK))

                return response

            except Exception as e:
                # 记录异常
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


class MetricMiddleware(BaseHTTPMiddleware):
    """
    OpenTelemetry 指标中间件

    记录请求指标：
    - http_requests_total: 请求总数
    - http_request_duration_seconds: 请求耗时
    - http_requests_in_progress: 正在处理的请求数
    """

    def __init__(
        self,
        app: ASGIApp,
        meter_name: str = "webserver",
        meter_version: str = "1.0.0",
    ):
        """
        Args:
            app: ASGI 应用
            meter_name: Meter 名称
            meter_version: Meter 版本
        """
        super().__init__(app)
        self.meter_name = meter_name
        self.meter_version = meter_version

        self._counter = None
        self._histogram = None
        self._gauge = None
        self._in_progress = 0

        if OTEL_AVAILABLE:
            try:
                from opentelemetry import metrics

                meter = metrics.get_meter(meter_name, meter_version)

                self._counter = meter.create_counter(
                    "http_requests_total",
                    description="Total number of HTTP requests",
                )

                self._histogram = meter.create_histogram(
                    "http_request_duration_seconds",
                    description="HTTP request duration in seconds",
                    unit="s",
                )

                self._gauge = meter.create_up_down_counter(
                    "http_requests_in_progress",
                    description="Number of HTTP requests in progress",
                )
            except Exception:
                pass

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not OTEL_AVAILABLE:
            return await call_next(request)

        method = request.method
        path = request.url.path

        # 增加进行中的请求计数
        if self._gauge:
            self._gauge.add(1, {"method": method, "path": path})
            self._in_progress += 1

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time

            # 记录请求计数
            if self._counter:
                self._counter.add(
                    1,
                    {
                        "method": method,
                        "path": path,
                        "status_code": str(status_code),
                    },
                )

            # 记录请求耗时
            if self._histogram:
                self._histogram.record(
                    duration,
                    {
                        "method": method,
                        "path": path,
                        "status_code": str(status_code),
                    },
                )

            # 减少进行中的请求计数
            if self._gauge:
                self._gauge.add(-1, {"method": method, "path": path})
                self._in_progress -= 1

        return response
