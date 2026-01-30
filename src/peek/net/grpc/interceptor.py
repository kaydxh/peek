#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC 拦截器模块

提供各类 gRPC 服务端拦截器，类似 Go 版本的 grpc-middleware。
"""

import logging
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import Any, Callable, List, Optional, Tuple

import grpc

logger = logging.getLogger(__name__)

# Context variables for request-scoped data
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
start_time_var: ContextVar[Optional[float]] = ContextVar("start_time", default=None)


def get_request_id() -> Optional[str]:
    """获取当前请求的 Request ID"""
    return request_id_var.get()


def get_start_time() -> Optional[float]:
    """获取当前请求的开始时间"""
    return start_time_var.get()


class UnaryServerInterceptor(grpc.ServerInterceptor, ABC):
    """Unary 服务端拦截器基类"""

    @abstractmethod
    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        """拦截 Unary 请求

        Args:
            request: 请求对象
            context: gRPC 上下文
            method_name: 方法全名（如 /package.Service/Method）
            handler: 下一个处理器

        Returns:
            响应对象
        """
        pass

    def intercept_service(
        self,
        continuation: Callable[
            [grpc.HandlerCallDetails], grpc.RpcMethodHandler
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        """实现 grpc.ServerInterceptor 接口"""
        next_handler = continuation(handler_call_details)

        if next_handler is None:
            return None

        if next_handler.unary_unary is None:
            # 非 Unary 方法，直接返回
            return next_handler

        def wrapped_unary(
            request: Any, context: grpc.ServicerContext
        ) -> Any:
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


class StreamServerInterceptor(grpc.ServerInterceptor, ABC):
    """Stream 服务端拦截器基类"""

    @abstractmethod
    def intercept_stream(
        self,
        request_or_iterator: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable,
        is_client_stream: bool,
        is_server_stream: bool,
    ) -> Any:
        """拦截 Stream 请求"""
        pass

    def intercept_service(
        self,
        continuation: Callable[
            [grpc.HandlerCallDetails], grpc.RpcMethodHandler
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        """实现 grpc.ServerInterceptor 接口"""
        next_handler = continuation(handler_call_details)

        if next_handler is None:
            return None

        # 根据方法类型包装不同的处理器
        if next_handler.unary_stream is not None:
            def wrapped_unary_stream(request, context):
                return self.intercept_stream(
                    request,
                    context,
                    handler_call_details.method,
                    next_handler.unary_stream,
                    is_client_stream=False,
                    is_server_stream=True,
                )

            return grpc.unary_stream_rpc_method_handler(
                wrapped_unary_stream,
                request_deserializer=next_handler.request_deserializer,
                response_serializer=next_handler.response_serializer,
            )

        elif next_handler.stream_unary is not None:
            def wrapped_stream_unary(request_iterator, context):
                return self.intercept_stream(
                    request_iterator,
                    context,
                    handler_call_details.method,
                    next_handler.stream_unary,
                    is_client_stream=True,
                    is_server_stream=False,
                )

            return grpc.stream_unary_rpc_method_handler(
                wrapped_stream_unary,
                request_deserializer=next_handler.request_deserializer,
                response_serializer=next_handler.response_serializer,
            )

        elif next_handler.stream_stream is not None:
            def wrapped_stream_stream(request_iterator, context):
                return self.intercept_stream(
                    request_iterator,
                    context,
                    handler_call_details.method,
                    next_handler.stream_stream,
                    is_client_stream=True,
                    is_server_stream=True,
                )

            return grpc.stream_stream_rpc_method_handler(
                wrapped_stream_stream,
                request_deserializer=next_handler.request_deserializer,
                response_serializer=next_handler.response_serializer,
            )

        return next_handler


class RequestIDInterceptor(UnaryServerInterceptor):
    """Request ID 拦截器

    为每个请求生成唯一的 Request ID，并设置到 context 和响应 metadata 中。
    """

    REQUEST_ID_METADATA_KEY = "x-request-id"

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        # 尝试从 metadata 获取 request_id
        metadata = dict(context.invocation_metadata() or [])
        request_id = metadata.get(self.REQUEST_ID_METADATA_KEY)

        # 如果请求对象有 request_id 字段，优先使用
        if hasattr(request, "request_id") and request.request_id:
            request_id = request.request_id
        elif not request_id:
            # 生成新的 request_id
            request_id = str(uuid.uuid4())

        # 设置到 context variable
        token = request_id_var.set(request_id)

        try:
            # 设置响应 metadata
            context.set_trailing_metadata([
                (self.REQUEST_ID_METADATA_KEY, request_id)
            ])

            response = handler(request, context)

            # 如果响应对象有 request_id 字段，设置它
            if hasattr(response, "request_id"):
                try:
                    response.request_id = request_id
                except AttributeError:
                    pass  # 只读字段

            return response
        finally:
            request_id_var.reset(token)


class RecoveryInterceptor(UnaryServerInterceptor):
    """异常恢复拦截器

    捕获未处理的异常，记录日志并返回 gRPC 错误。
    """

    def __init__(self, log_stacktrace: bool = True):
        """初始化

        Args:
            log_stacktrace: 是否记录堆栈信息
        """
        self.log_stacktrace = log_stacktrace

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        try:
            return handler(request, context)
        except grpc.RpcError:
            # gRPC 错误直接抛出
            raise
        except Exception as e:
            request_id = get_request_id() or "unknown"

            if self.log_stacktrace:
                logger.exception(
                    f"[{request_id}] Unhandled exception in {method_name}: {e}"
                )
            else:
                logger.error(
                    f"[{request_id}] Unhandled exception in {method_name}: {e}"
                )

            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Internal server error: {type(e).__name__}",
            )


class LoggingInterceptor(UnaryServerInterceptor):
    """日志拦截器

    记录请求和响应日志。
    """

    def __init__(
        self,
        log_request: bool = True,
        log_response: bool = False,
        max_log_length: int = 1000,
    ):
        """初始化

        Args:
            log_request: 是否记录请求内容
            log_response: 是否记录响应内容
            max_log_length: 日志最大长度
        """
        self.log_request = log_request
        self.log_response = log_response
        self.max_log_length = max_log_length

    def _truncate(self, text: str) -> str:
        """截断过长的文本"""
        if len(text) > self.max_log_length:
            return text[:self.max_log_length] + "..."
        return text

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        request_id = get_request_id() or "unknown"

        if self.log_request:
            request_str = self._truncate(str(request))
            logger.info(f"[{request_id}] gRPC Request {method_name}: {request_str}")

        response = handler(request, context)

        if self.log_response:
            response_str = self._truncate(str(response))
            logger.info(f"[{request_id}] gRPC Response {method_name}: {response_str}")

        return response


class TimerInterceptor(UnaryServerInterceptor):
    """计时拦截器

    记录请求处理耗时。
    """

    def __init__(
        self,
        slow_threshold_ms: float = 1000,
        log_all: bool = False,
    ):
        """初始化

        Args:
            slow_threshold_ms: 慢请求阈值（毫秒），超过则记录警告
            log_all: 是否记录所有请求的耗时
        """
        self.slow_threshold_ms = slow_threshold_ms
        self.log_all = log_all

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        start_time = time.time()
        token = start_time_var.set(start_time)

        try:
            response = handler(request, context)

            elapsed_ms = (time.time() - start_time) * 1000
            request_id = get_request_id() or "unknown"

            if elapsed_ms > self.slow_threshold_ms:
                logger.warning(
                    f"[{request_id}] Slow gRPC request {method_name}: {elapsed_ms:.2f}ms"
                )
            elif self.log_all:
                logger.info(
                    f"[{request_id}] gRPC request {method_name}: {elapsed_ms:.2f}ms"
                )

            return response
        finally:
            start_time_var.reset(token)


class QPSLimitInterceptor(UnaryServerInterceptor):
    """QPS 限流拦截器

    基于令牌桶算法的 QPS 限流。
    """

    def __init__(
        self,
        qps: float,
        burst: Optional[int] = None,
        per_method: bool = False,
    ):
        """初始化

        Args:
            qps: 每秒最大请求数
            burst: 突发容量，默认等于 qps
            per_method: 是否按方法分别限流
        """
        from peek.net.webserver.middleware.ratelimit import TokenBucketLimiter

        self.qps = qps
        self.burst = burst or int(qps)
        self.per_method = per_method

        if per_method:
            self._limiters: dict = {}
        else:
            self._limiter = TokenBucketLimiter(qps, self.burst)

    def _get_limiter(self, method_name: str):
        """获取限流器"""
        from peek.net.webserver.middleware.ratelimit import TokenBucketLimiter

        if not self.per_method:
            return self._limiter

        if method_name not in self._limiters:
            self._limiters[method_name] = TokenBucketLimiter(self.qps, self.burst)
        return self._limiters[method_name]

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        limiter = self._get_limiter(method_name)

        if not limiter.allow():
            request_id = get_request_id() or "unknown"
            logger.warning(
                f"[{request_id}] Rate limit exceeded for {method_name}"
            )
            context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                f"Rate limit exceeded for {method_name}",
            )

        return handler(request, context)


class ConcurrencyLimitInterceptor(UnaryServerInterceptor):
    """并发限制拦截器

    限制同时处理的请求数量。
    """

    def __init__(
        self,
        max_concurrent: int,
        per_method: bool = False,
    ):
        """初始化

        Args:
            max_concurrent: 最大并发数
            per_method: 是否按方法分别限流
        """
        import threading

        self.max_concurrent = max_concurrent
        self.per_method = per_method

        if per_method:
            self._semaphores: dict = {}
            self._lock = threading.Lock()
        else:
            self._semaphore = threading.Semaphore(max_concurrent)

    def _get_semaphore(self, method_name: str):
        """获取信号量"""
        import threading

        if not self.per_method:
            return self._semaphore

        with self._lock:
            if method_name not in self._semaphores:
                self._semaphores[method_name] = threading.Semaphore(
                    self.max_concurrent
                )
            return self._semaphores[method_name]

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        semaphore = self._get_semaphore(method_name)

        acquired = semaphore.acquire(blocking=False)
        if not acquired:
            request_id = get_request_id() or "unknown"
            logger.warning(
                f"[{request_id}] Concurrency limit exceeded for {method_name}"
            )
            context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                f"Concurrency limit exceeded for {method_name}",
            )

        try:
            return handler(request, context)
        finally:
            semaphore.release()


class InterceptorChain:
    """拦截器链构建器

    简化拦截器链的创建和管理。

    示例:
        ```python
        chain = InterceptorChain()
        chain.add(RequestIDInterceptor())
        chain.add(RecoveryInterceptor())
        chain.add(LoggingInterceptor())

        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=10),
            interceptors=chain.build(),
        )
        ```
    """

    def __init__(self):
        self._interceptors: List[grpc.ServerInterceptor] = []

    def add(self, interceptor: grpc.ServerInterceptor) -> "InterceptorChain":
        """添加拦截器

        Args:
            interceptor: gRPC 服务端拦截器

        Returns:
            self，支持链式调用
        """
        self._interceptors.append(interceptor)
        return self

    def build(self) -> List[grpc.ServerInterceptor]:
        """构建拦截器列表

        Returns:
            拦截器列表，用于传给 grpc.server()
        """
        return list(self._interceptors)

    def __len__(self) -> int:
        return len(self._interceptors)


def create_default_interceptor_chain(
    enable_request_id: bool = True,
    enable_recovery: bool = True,
    enable_logging: bool = True,
    enable_timer: bool = True,
    log_request: bool = True,
    log_response: bool = False,
    slow_threshold_ms: float = 1000,
) -> List[grpc.ServerInterceptor]:
    """创建默认拦截器链

    Args:
        enable_request_id: 是否启用 RequestID 拦截器
        enable_recovery: 是否启用异常恢复拦截器
        enable_logging: 是否启用日志拦截器
        enable_timer: 是否启用计时拦截器
        log_request: 是否记录请求内容
        log_response: 是否记录响应内容
        slow_threshold_ms: 慢请求阈值

    Returns:
        拦截器列表
    """
    chain = InterceptorChain()

    if enable_request_id:
        chain.add(RequestIDInterceptor())

    if enable_recovery:
        chain.add(RecoveryInterceptor())

    if enable_timer:
        chain.add(TimerInterceptor(slow_threshold_ms=slow_threshold_ms))

    if enable_logging:
        chain.add(LoggingInterceptor(
            log_request=log_request,
            log_response=log_response,
        ))

    return chain.build()
