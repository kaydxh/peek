#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
QPS 限流中间件

参考 Go 版本 golang 库的 ratelimiter_qps.go 实现
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


@dataclass
class MethodQPSConfig:
    """方法级 QPS 配置"""

    method: str  # HTTP 方法，如 GET, POST, *
    path: str  # 路径，支持前缀匹配
    qps: float  # QPS 限制
    burst: int = 0  # 突发容量


@dataclass
class QPSLimitConfig:
    """QPS 限流配置"""

    default_qps: float = 0  # 默认 QPS（0 表示不限制）
    default_burst: int = 0  # 默认突发容量
    max_concurrency: int = 0  # 最大并发数（0 表示不限制）
    method_qps: List[MethodQPSConfig] = field(default_factory=list)


class TokenBucketLimiter:
    """
    令牌桶限流器

    实现令牌桶算法进行 QPS 限流
    """

    def __init__(self, qps: float, burst: int = 0):
        """
        Args:
            qps: 每秒请求数限制
            burst: 突发容量（令牌桶大小），默认为 qps
        """
        self.qps = qps
        self.burst = burst if burst > 0 else max(1, int(qps))
        self.tokens = float(self.burst)
        self.last_time = time.monotonic()
        self._lock = Lock()

    def allow(self) -> bool:
        """
        检查是否允许请求

        Returns:
            是否允许
        """
        if self.qps <= 0:
            return True

        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_time
            self.last_time = now

            # 添加令牌
            self.tokens = min(self.burst, self.tokens + elapsed * self.qps)

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    def wait(self) -> float:
        """
        计算需要等待的时间

        Returns:
            需要等待的秒数
        """
        if self.qps <= 0:
            return 0

        with self._lock:
            if self.tokens >= 1:
                return 0
            return (1 - self.tokens) / self.qps


class QPSLimiter:
    """
    QPS 限流器

    支持全局限流和方法级限流
    """

    def __init__(self, config: QPSLimitConfig):
        """
        Args:
            config: QPS 限流配置
        """
        self.config = config

        # 默认限流器
        self._default_limiter: Optional[TokenBucketLimiter] = None
        if config.default_qps > 0:
            self._default_limiter = TokenBucketLimiter(
                config.default_qps,
                config.default_burst,
            )

        # 方法级限流器
        self._method_limiters: Dict[str, TokenBucketLimiter] = {}
        for method_config in config.method_qps:
            key = self._make_key(method_config.method, method_config.path)
            self._method_limiters[key] = TokenBucketLimiter(
                method_config.qps,
                method_config.burst,
            )

        # 并发计数
        self._concurrency = 0
        self._concurrency_lock = Lock()

    def _make_key(self, method: str, path: str) -> str:
        """生成限流器 key"""
        return f"{method.upper()}:{path}"

    def _find_limiter(self, method: str, path: str) -> Optional[TokenBucketLimiter]:
        """
        查找匹配的限流器

        优先匹配精确路径，然后匹配前缀路径
        """
        # 精确匹配
        key = self._make_key(method, path)
        if key in self._method_limiters:
            return self._method_limiters[key]

        # 通配方法匹配
        key = self._make_key("*", path)
        if key in self._method_limiters:
            return self._method_limiters[key]

        # 前缀匹配
        for config in self.config.method_qps:
            if config.path.endswith("*"):
                prefix = config.path[:-1]
                if path.startswith(prefix):
                    if config.method == "*" or config.method.upper() == method.upper():
                        key = self._make_key(config.method, config.path)
                        return self._method_limiters.get(key)

        # 使用默认限流器
        return self._default_limiter

    def allow(self, method: str, path: str) -> bool:
        """
        检查是否允许请求

        Args:
            method: HTTP 方法
            path: 请求路径

        Returns:
            是否允许
        """
        limiter = self._find_limiter(method, path)
        if limiter:
            return limiter.allow()
        return True

    def acquire_concurrency(self) -> bool:
        """
        获取并发槽位

        Returns:
            是否成功获取
        """
        if self.config.max_concurrency <= 0:
            return True

        with self._concurrency_lock:
            if self._concurrency < self.config.max_concurrency:
                self._concurrency += 1
                return True
            return False

    def release_concurrency(self) -> None:
        """释放并发槽位"""
        if self.config.max_concurrency <= 0:
            return

        with self._concurrency_lock:
            if self._concurrency > 0:
                self._concurrency -= 1


class QPSRateLimitMiddleware(BaseHTTPMiddleware):
    """
    QPS 限流中间件

    提供 QPS 和并发数限制
    """

    def __init__(
        self,
        app: ASGIApp,
        config: QPSLimitConfig = None,
        limiter: QPSLimiter = None,
    ):
        """
        Args:
            app: ASGI 应用
            config: QPS 限流配置
            limiter: QPS 限流器实例（优先使用）
        """
        super().__init__(app)
        if limiter:
            self.limiter = limiter
        elif config:
            self.limiter = QPSLimiter(config)
        else:
            self.limiter = QPSLimiter(QPSLimitConfig())

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method
        path = request.url.path

        # 检查 QPS 限制
        if not self.limiter.allow(method, path):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"{method} {path} is rejected by rate limiter",
                },
            )

        # 检查并发限制
        if not self.limiter.acquire_concurrency():
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Max concurrency exceeded",
                },
            )

        try:
            return await call_next(request)
        finally:
            self.limiter.release_concurrency()


class ConcurrencyLimitMiddleware(BaseHTTPMiddleware):
    """
    并发限制中间件

    仅限制最大并发数
    """

    def __init__(
        self,
        app: ASGIApp,
        max_concurrency: int,
    ):
        """
        Args:
            app: ASGI 应用
            max_concurrency: 最大并发数
        """
        super().__init__(app)
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            # 尝试非阻塞获取
            if not self._semaphore.locked():
                async with self._semaphore:
                    return await call_next(request)
            else:
                # 已达到最大并发
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "message": "Max concurrency exceeded",
                    },
                )
        except Exception:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Max concurrency exceeded",
                },
            )
