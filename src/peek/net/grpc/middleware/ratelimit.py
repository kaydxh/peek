#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC 限流拦截器

提供 gRPC 服务端限流功能：
- QPS 限流
- 并发限流
- 方法级限流
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import grpc

logger = logging.getLogger(__name__)


# ======================== 配置类 ========================


@dataclass
class MethodQPSConfig:
    """
    方法级 QPS 配置

    Attributes:
        method: gRPC 方法名（如 /package.Service/Method）
        qps: QPS 限制
        burst: 突发容量
        max_concurrency: 最大并发数
    """

    method: str
    qps: float = 0
    burst: int = 0
    max_concurrency: int = 0


@dataclass
class GrpcQPSLimitConfig:
    """
    gRPC QPS 限流配置

    Attributes:
        default_qps: 默认 QPS（0 表示不限制）
        default_burst: 默认突发容量
        max_concurrency: 最大并发数（0 表示不限制）
        method_qps: 方法级配置列表
    """

    default_qps: float = 0
    default_burst: int = 0
    max_concurrency: int = 0
    method_qps: List[MethodQPSConfig] = field(default_factory=list)


# ======================== 令牌桶限流器 ========================


class TokenBucketLimiter:
    """令牌桶限流器"""

    def __init__(self, qps: float, burst: int = 0):
        self.qps = qps
        self.burst = burst if burst > 0 else max(1, int(qps)) if qps > 0 else 1
        self.tokens = float(self.burst)
        self.last_time = time.monotonic()
        self._lock = threading.RLock()

        # 统计信息
        self.total_requests = 0
        self.allowed_requests = 0
        self.rejected_requests = 0

    def allow(self) -> bool:
        """检查是否允许请求"""
        if self.qps <= 0:
            return True

        with self._lock:
            self.total_requests += 1
            now = time.monotonic()
            elapsed = now - self.last_time
            self.last_time = now

            self.tokens = min(self.burst, self.tokens + elapsed * self.qps)

            if self.tokens >= 1:
                self.tokens -= 1
                self.allowed_requests += 1
                return True

            self.rejected_requests += 1
            return False

    def allow_for(self, timeout: float) -> bool:
        """等待获取令牌"""
        if self.qps <= 0:
            return True

        deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self.total_requests += 1
                now = time.monotonic()

                if now >= deadline:
                    self.rejected_requests += 1
                    return False

                elapsed = now - self.last_time
                self.last_time = now

                self.tokens = min(self.burst, self.tokens + elapsed * self.qps)

                if self.tokens >= 1:
                    self.tokens -= 1
                    self.allowed_requests += 1
                    return True

                wait_time = (1 - self.tokens) / self.qps
                remaining = deadline - now

                if wait_time > remaining:
                    self.rejected_requests += 1
                    return False

            time.sleep(min(wait_time, 0.01))

    def set_qps(self, qps: float, burst: int = 0) -> None:
        """动态更新 QPS"""
        with self._lock:
            self.qps = qps
            self.burst = burst if burst > 0 else max(1, int(qps)) if qps > 0 else 1
            self.tokens = min(self.tokens, self.burst)


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


# ======================== 限流拦截器 ========================


class QPSLimitInterceptor(UnaryServerInterceptor):
    """
    QPS 限流拦截器

    基于令牌桶算法的 QPS 限流
    """

    def __init__(
        self,
        qps: float,
        burst: int = 0,
        wait_timeout: float = 0,
    ):
        """
        初始化 QPS 限流拦截器

        Args:
            qps: 每秒最大请求数
            burst: 突发容量，默认等于 qps
            wait_timeout: 等待超时时间（秒），0 表示不等待
        """
        self.qps = qps
        self.burst = burst if burst > 0 else int(qps)
        self.wait_timeout = wait_timeout
        self._limiter = TokenBucketLimiter(qps, self.burst)

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        if self.wait_timeout > 0:
            allowed = self._limiter.allow_for(self.wait_timeout)
        else:
            allowed = self._limiter.allow()

        if not allowed:
            logger.warning(f"Rate limit exceeded for {method_name}")
            context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                f"{method_name} is rejected by rate limiter, QPS limit exceeded",
            )

        return handler(request, context)


class ConcurrencyLimitInterceptor(UnaryServerInterceptor):
    """
    并发限制拦截器

    限制同时处理的请求数量
    """

    def __init__(self, max_concurrency: int):
        """
        初始化并发限制拦截器

        Args:
            max_concurrency: 最大并发数
        """
        self.max_concurrency = max_concurrency
        self._semaphore = threading.Semaphore(max_concurrency)
        self._current = 0
        self._lock = threading.Lock()

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            logger.warning(f"Concurrency limit exceeded for {method_name}")
            context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                f"{method_name} is rejected, max concurrency exceeded",
            )

        try:
            with self._lock:
                self._current += 1
            return handler(request, context)
        finally:
            self._semaphore.release()
            with self._lock:
                self._current -= 1


class MethodQPSLimitInterceptor(UnaryServerInterceptor):
    """
    方法级 QPS 限流拦截器

    支持为不同方法设置不同的 QPS 限制
    """

    def __init__(self, config: GrpcQPSLimitConfig):
        """
        初始化方法级 QPS 限流拦截器

        Args:
            config: 限流配置
        """
        self.config = config
        self._lock = threading.Lock()

        # 默认限流器
        self._default_qps_limiter: Optional[TokenBucketLimiter] = None
        if config.default_qps > 0:
            self._default_qps_limiter = TokenBucketLimiter(
                config.default_qps, config.default_burst
            )

        # 默认并发限流器
        self._default_concurrency_semaphore: Optional[threading.Semaphore] = None
        if config.max_concurrency > 0:
            self._default_concurrency_semaphore = threading.Semaphore(
                config.max_concurrency
            )

        # 方法级限流器
        self._method_qps_limiters: Dict[str, TokenBucketLimiter] = {}
        self._method_concurrency_semaphores: Dict[str, threading.Semaphore] = {}

        for method_config in config.method_qps:
            if method_config.qps > 0:
                self._method_qps_limiters[method_config.method] = TokenBucketLimiter(
                    method_config.qps, method_config.burst
                )
            if method_config.max_concurrency > 0:
                self._method_concurrency_semaphores[
                    method_config.method
                ] = threading.Semaphore(method_config.max_concurrency)

    def _get_qps_limiter(self, method_name: str) -> Optional[TokenBucketLimiter]:
        """获取 QPS 限流器"""
        # 精确匹配
        if method_name in self._method_qps_limiters:
            return self._method_qps_limiters[method_name]

        # 前缀匹配
        for key, limiter in self._method_qps_limiters.items():
            if key.endswith("*"):
                prefix = key[:-1]
                if method_name.startswith(prefix):
                    return limiter

        return self._default_qps_limiter

    def _get_concurrency_semaphore(
        self, method_name: str
    ) -> Optional[threading.Semaphore]:
        """获取并发限流器"""
        # 精确匹配
        if method_name in self._method_concurrency_semaphores:
            return self._method_concurrency_semaphores[method_name]

        # 前缀匹配
        for key, semaphore in self._method_concurrency_semaphores.items():
            if key.endswith("*"):
                prefix = key[:-1]
                if method_name.startswith(prefix):
                    return semaphore

        return self._default_concurrency_semaphore

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        # 检查 QPS 限制
        qps_limiter = self._get_qps_limiter(method_name)
        if qps_limiter and not qps_limiter.allow():
            logger.warning(f"QPS limit exceeded for {method_name}")
            context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                f"{method_name} is rejected, QPS limit exceeded",
            )

        # 检查并发限制
        concurrency_semaphore = self._get_concurrency_semaphore(method_name)
        if concurrency_semaphore:
            acquired = concurrency_semaphore.acquire(blocking=False)
            if not acquired:
                logger.warning(f"Concurrency limit exceeded for {method_name}")
                context.abort(
                    grpc.StatusCode.RESOURCE_EXHAUSTED,
                    f"{method_name} is rejected, max concurrency exceeded",
                )
        else:
            acquired = False

        try:
            return handler(request, context)
        finally:
            if acquired and concurrency_semaphore:
                concurrency_semaphore.release()

    def add_method_limit(
        self,
        method: str,
        qps: float = 0,
        burst: int = 0,
        max_concurrency: int = 0,
    ) -> None:
        """
        动态添加方法级限流配置

        Args:
            method: 方法名
            qps: QPS 限制
            burst: 突发容量
            max_concurrency: 最大并发数
        """
        with self._lock:
            if qps > 0:
                self._method_qps_limiters[method] = TokenBucketLimiter(qps, burst)
            if max_concurrency > 0:
                self._method_concurrency_semaphores[method] = threading.Semaphore(
                    max_concurrency
                )

    def remove_method_limit(self, method: str) -> None:
        """
        移除方法级限流配置

        Args:
            method: 方法名
        """
        with self._lock:
            self._method_qps_limiters.pop(method, None)
            self._method_concurrency_semaphores.pop(method, None)


# ======================== 工厂函数 ========================


def create_qps_limit_interceptor(
    qps: float,
    burst: int = 0,
    wait_timeout: float = 0,
) -> QPSLimitInterceptor:
    """
    创建 QPS 限流拦截器

    Args:
        qps: QPS 限制
        burst: 突发容量
        wait_timeout: 等待超时时间

    Returns:
        QPSLimitInterceptor 实例
    """
    return QPSLimitInterceptor(qps, burst, wait_timeout)


def create_concurrency_limit_interceptor(
    max_concurrency: int,
) -> ConcurrencyLimitInterceptor:
    """
    创建并发限制拦截器

    Args:
        max_concurrency: 最大并发数

    Returns:
        ConcurrencyLimitInterceptor 实例
    """
    return ConcurrencyLimitInterceptor(max_concurrency)


def create_method_qps_limit_interceptor(
    default_qps: float = 0,
    default_burst: int = 0,
    max_concurrency: int = 0,
    method_configs: Optional[List[Dict[str, Any]]] = None,
) -> MethodQPSLimitInterceptor:
    """
    创建方法级 QPS 限流拦截器

    Args:
        default_qps: 默认 QPS
        default_burst: 默认突发容量
        max_concurrency: 默认最大并发数
        method_configs: 方法级配置列表

    Returns:
        MethodQPSLimitInterceptor 实例
    """
    method_qps = []
    if method_configs:
        for cfg in method_configs:
            method_qps.append(
                MethodQPSConfig(
                    method=cfg.get("method", ""),
                    qps=cfg.get("qps", 0),
                    burst=cfg.get("burst", 0),
                    max_concurrency=cfg.get("max_concurrency", 0),
                )
            )

    config = GrpcQPSLimitConfig(
        default_qps=default_qps,
        default_burst=default_burst,
        max_concurrency=max_concurrency,
        method_qps=method_qps,
    )
    return MethodQPSLimitInterceptor(config)
