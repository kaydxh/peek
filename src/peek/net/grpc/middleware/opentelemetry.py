#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC OpenTelemetry 中间件

提供 gRPC 服务端 OpenTelemetry 功能：
- 分布式追踪
- 指标收集
"""

import logging
import time
from typing import Any, Callable, Dict, Optional

import grpc

logger = logging.getLogger(__name__)

# 尝试导入 OpenTelemetry
try:
    from opentelemetry import trace, metrics
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.propagate import extract
    from opentelemetry.semconv.trace import SpanAttributes

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    metrics = None


# ======================== 拦截器基类 ========================


class UnaryServerInterceptor(grpc.ServerInterceptor):
    """Unary 服务端拦截器基类"""

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        """拦截 Unary 请求"""
        raise NotImplementedError

    def intercept_service(
        self,
        continuation: Callable[
            [grpc.HandlerCallDetails], grpc.RpcMethodHandler
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        next_handler = continuation(handler_call_details)

        if next_handler is None:
            return None

        if next_handler.unary_unary is None:
            return next_handler

        def wrapped_unary(request: Any, context: grpc.ServicerContext) -> Any:
            return self.intercept_unary(
                request,
                context,
                handler_call_details.method,
                next_handler.unary_unary,
            )

        return grpc.unary_unary_rpc_method_handler(
            wrapped_unary,
            request_deserializer=next_handler.request_deserializer,
            response_serializer=next_handler.response_serializer,
        )


# ======================== Trace 拦截器 ========================


class TraceInterceptor(UnaryServerInterceptor):
    """
    OpenTelemetry Trace 拦截器

    为每个 gRPC 请求创建 Span，记录请求信息
    """

    def __init__(
        self,
        tracer_name: str = "grpc-server",
        tracer_version: str = "1.0.0",
        record_request: bool = False,
        record_response: bool = False,
    ):
        """
        初始化 Trace 拦截器

        Args:
            tracer_name: Tracer 名称
            tracer_version: Tracer 版本
            record_request: 是否记录请求内容
            record_response: 是否记录响应内容
        """
        self.tracer_name = tracer_name
        self.tracer_version = tracer_version
        self.record_request = record_request
        self.record_response = record_response

        if OTEL_AVAILABLE:
            self._tracer = trace.get_tracer(tracer_name, tracer_version)
        else:
            self._tracer = None

    def _extract_metadata(
        self, context: grpc.ServicerContext
    ) -> Dict[str, str]:
        """从 gRPC metadata 提取信息"""
        metadata = {}
        try:
            for key, value in context.invocation_metadata() or []:
                metadata[key] = value
        except Exception:
            pass
        return metadata

    def _get_peer_info(
        self, context: grpc.ServicerContext
    ) -> Dict[str, str]:
        """获取客户端信息"""
        peer_info = {}
        try:
            peer = context.peer()
            if peer:
                # 格式: ipv4:127.0.0.1:12345 或 ipv6:[::1]:12345
                parts = peer.split(":")
                if len(parts) >= 2:
                    if parts[0] in ("ipv4", "ipv6"):
                        peer_info["peer_ip"] = parts[1]
                        if len(parts) > 2:
                            peer_info["peer_port"] = parts[-1]
        except Exception:
            pass
        return peer_info

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        if not OTEL_AVAILABLE or not self._tracer:
            return handler(request, context)

        # 从 metadata 提取上下文
        metadata = self._extract_metadata(context)
        ctx = extract(metadata)

        # 解析方法名（格式: /package.Service/Method）
        parts = method_name.split("/")
        service_name = parts[1] if len(parts) > 1 else "unknown"
        method = parts[2] if len(parts) > 2 else method_name

        span_name = f"{service_name}/{method}"

        with self._tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=SpanKind.SERVER,
        ) as span:
            # 设置 gRPC 相关属性
            span.set_attribute("rpc.system", "grpc")
            span.set_attribute("rpc.service", service_name)
            span.set_attribute("rpc.method", method)
            span.set_attribute("rpc.grpc.full_method", method_name)

            # 获取客户端信息
            peer_info = self._get_peer_info(context)
            if "peer_ip" in peer_info:
                span.set_attribute(SpanAttributes.NET_PEER_IP, peer_info["peer_ip"])
            if "peer_port" in peer_info:
                span.set_attribute(SpanAttributes.NET_PEER_PORT, peer_info["peer_port"])

            # 获取 request_id
            request_id = metadata.get("x-request-id")
            if request_id:
                span.set_attribute("request.id", request_id)

            # 记录请求内容
            if self.record_request:
                try:
                    request_str = str(request)[:1000]
                    span.set_attribute("rpc.request", request_str)
                except Exception:
                    pass

            try:
                response = handler(request, context)

                # 设置成功状态
                span.set_attribute("rpc.grpc.status_code", "OK")
                span.set_status(Status(StatusCode.OK))

                # 记录响应内容
                if self.record_response:
                    try:
                        response_str = str(response)[:1000]
                        span.set_attribute("rpc.response", response_str)
                    except Exception:
                        pass

                return response

            except grpc.RpcError as e:
                # 记录 gRPC 错误
                span.set_attribute("rpc.grpc.status_code", str(e.code().name))
                span.set_status(Status(StatusCode.ERROR, str(e.details())))
                span.record_exception(e)
                raise

            except Exception as e:
                # 记录其他异常
                span.set_attribute("rpc.grpc.status_code", "INTERNAL")
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


# ======================== Metric 拦截器 ========================


class MetricInterceptor(UnaryServerInterceptor):
    """
    OpenTelemetry Metric 拦截器

    记录 gRPC 请求指标：
    - grpc_requests_total: 请求总数
    - grpc_request_duration_seconds: 请求耗时
    - grpc_requests_in_progress: 进行中的请求数
    """

    def __init__(
        self,
        meter_name: str = "grpc-server",
        meter_version: str = "1.0.0",
    ):
        """
        初始化 Metric 拦截器

        Args:
            meter_name: Meter 名称
            meter_version: Meter 版本
        """
        self.meter_name = meter_name
        self.meter_version = meter_version

        self._counter = None
        self._histogram = None
        self._in_progress_counter = None
        self._in_progress = 0

        if OTEL_AVAILABLE:
            try:
                meter = metrics.get_meter(meter_name, meter_version)

                self._counter = meter.create_counter(
                    "grpc_requests_total",
                    description="Total number of gRPC requests",
                )

                self._histogram = meter.create_histogram(
                    "grpc_request_duration_seconds",
                    description="gRPC request duration in seconds",
                    unit="s",
                )

                self._in_progress_counter = meter.create_up_down_counter(
                    "grpc_requests_in_progress",
                    description="Number of gRPC requests in progress",
                )
            except Exception as e:
                logger.warning(f"Failed to initialize metrics: {e}")

    def _parse_method(self, method_name: str) -> Dict[str, str]:
        """解析方法名"""
        parts = method_name.split("/")
        service = parts[1] if len(parts) > 1 else "unknown"
        method = parts[2] if len(parts) > 2 else method_name
        return {"service": service, "method": method}

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        if not OTEL_AVAILABLE:
            return handler(request, context)

        method_info = self._parse_method(method_name)
        labels = {
            "grpc_service": method_info["service"],
            "grpc_method": method_info["method"],
        }

        # 增加进行中计数
        if self._in_progress_counter:
            self._in_progress_counter.add(1, labels)
            self._in_progress += 1

        start_time = time.perf_counter()
        status_code = "OK"

        try:
            response = handler(request, context)
            return response

        except grpc.RpcError as e:
            status_code = e.code().name
            raise

        except Exception:
            status_code = "INTERNAL"
            raise

        finally:
            duration = time.perf_counter() - start_time

            # 更新标签
            labels["grpc_code"] = status_code

            # 记录请求计数
            if self._counter:
                self._counter.add(1, labels)

            # 记录请求耗时
            if self._histogram:
                self._histogram.record(duration, labels)

            # 减少进行中计数
            if self._in_progress_counter:
                in_progress_labels = {
                    "grpc_service": method_info["service"],
                    "grpc_method": method_info["method"],
                }
                self._in_progress_counter.add(-1, in_progress_labels)
                self._in_progress -= 1


# ======================== 组合拦截器 ========================


class ModularInterceptor(UnaryServerInterceptor):
    """
    模块化指标上报拦截器

    提供服务级别的指标上报，包括：
    - 请求计数
    - 成功/失败计数
    - 耗时直方图
    """

    def __init__(
        self,
        app_name: str,
        server_name: str,
        meter_name: str = "grpc-server",
        meter_version: str = "1.0.0",
    ):
        """
        初始化模块化拦截器

        Args:
            app_name: 应用名称
            server_name: 服务名称
            meter_name: Meter 名称
            meter_version: Meter 版本
        """
        self.app_name = app_name
        self.server_name = server_name

        self._total_counter = None
        self._success_counter = None
        self._fail_counter = None
        self._cost_histogram = None

        if OTEL_AVAILABLE:
            try:
                meter = metrics.get_meter(meter_name, meter_version)

                self._total_counter = meter.create_counter(
                    f"{app_name}_{server_name}_total_req",
                    description=f"Total requests for {server_name}",
                )

                self._success_counter = meter.create_counter(
                    f"{app_name}_{server_name}_success_cnt",
                    description=f"Successful requests for {server_name}",
                )

                self._fail_counter = meter.create_counter(
                    f"{app_name}_{server_name}_fail_cnt",
                    description=f"Failed requests for {server_name}",
                )

                self._cost_histogram = meter.create_histogram(
                    f"{app_name}_{server_name}_cost_time",
                    description=f"Request duration for {server_name}",
                    unit="ms",
                )
            except Exception as e:
                logger.warning(f"Failed to initialize modular metrics: {e}")

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        if not OTEL_AVAILABLE:
            return handler(request, context)

        # 解析方法名
        parts = method_name.split("/")
        callee_method = parts[2] if len(parts) > 2 else method_name

        labels = {
            "callee_method": callee_method,
        }

        start_time = time.perf_counter()
        success = True

        try:
            # 记录总请求数
            if self._total_counter:
                self._total_counter.add(1, labels)

            response = handler(request, context)
            return response

        except Exception as e:
            success = False
            labels["error"] = type(e).__name__
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # 记录成功/失败计数
            if success:
                if self._success_counter:
                    self._success_counter.add(1, labels)
            else:
                if self._fail_counter:
                    self._fail_counter.add(1, labels)

            # 记录耗时
            if self._cost_histogram:
                self._cost_histogram.record(duration_ms, labels)


# ======================== 工厂函数 ========================


def create_trace_interceptor(
    tracer_name: str = "grpc-server",
    tracer_version: str = "1.0.0",
    record_request: bool = False,
    record_response: bool = False,
) -> TraceInterceptor:
    """
    创建 Trace 拦截器

    Args:
        tracer_name: Tracer 名称
        tracer_version: Tracer 版本
        record_request: 是否记录请求
        record_response: 是否记录响应

    Returns:
        TraceInterceptor 实例
    """
    return TraceInterceptor(
        tracer_name=tracer_name,
        tracer_version=tracer_version,
        record_request=record_request,
        record_response=record_response,
    )


def create_metric_interceptor(
    meter_name: str = "grpc-server",
    meter_version: str = "1.0.0",
) -> MetricInterceptor:
    """
    创建 Metric 拦截器

    Args:
        meter_name: Meter 名称
        meter_version: Meter 版本

    Returns:
        MetricInterceptor 实例
    """
    return MetricInterceptor(
        meter_name=meter_name,
        meter_version=meter_version,
    )


def create_modular_interceptor(
    app_name: str,
    server_name: str,
) -> ModularInterceptor:
    """
    创建模块化拦截器

    Args:
        app_name: 应用名称
        server_name: 服务名称

    Returns:
        ModularInterceptor 实例
    """
    return ModularInterceptor(app_name=app_name, server_name=server_name)
