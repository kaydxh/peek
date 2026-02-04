#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
限流中间件

提供多种限流策略：
- QPS 限流：基于令牌桶算法的 QPS 限制
- 并发限流：限制同时处理的请求数
- 路径级限流：支持不同路径设置不同限流规则
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock, RLock
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


# ======================== 配置类 ========================


@dataclass
class MethodQPSConfig:
    """
    方法/路径级 QPS 配置

    Attributes:
        method: HTTP 方法（GET, POST, * 表示全部）
        path: 路径（支持前缀匹配，以 * 结尾）
        qps: QPS 限制
        burst: 突发容量，0 表示使用 qps 值
        max_concurrency: 最大并发数，0 表示不限制
    """

    method: str = "*"
    path: str = "/"
    qps: float = 0
    burst: int = 0
    max_concurrency: int = 0


@dataclass
class QPSLimitConfig:
    """
    QPS 限流配置

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


@dataclass
class QPSStats:
    """
    QPS 统计信息

    Attributes:
        path: 路径
        qps: 配置的 QPS
        burst: 配置的突发容量
        current_tokens: 当前令牌数
        total_requests: 总请求数
        allowed_requests: 允许的请求数
        rejected_requests: 拒绝的请求数
    """

    path: str = ""
    qps: float = 0
    burst: int = 0
    current_tokens: float = 0
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0


# ======================== 令牌桶限流器 ========================


class TokenBucketLimiter:
    """
    令牌桶限流器

    基于令牌桶算法实现 QPS 限流：
    - 以固定速率向桶中添加令牌
    - 每个请求消耗一个令牌
    - 桶满时不再添加令牌
    """

    def __init__(self, qps: float, burst: int = 0):
        """
        初始化令牌桶限流器

        Args:
            qps: 每秒请求数限制
            burst: 突发容量（令牌桶大小），默认为 max(1, qps)
        """
        self.qps = qps
        self.burst = burst if burst > 0 else max(1, int(qps)) if qps > 0 else 1
        self.tokens = float(self.burst)
        self.last_time = time.monotonic()
        self._lock = RLock()

        # 统计信息
        self.total_requests = 0
        self.allowed_requests = 0
        self.rejected_requests = 0

    def allow(self) -> bool:
        """
        检查是否允许请求（非阻塞）

        Returns:
            是否允许请求
        """
        if self.qps <= 0:
            return True

        with self._lock:
            self.total_requests += 1
            now = time.monotonic()
            elapsed = now - self.last_time
            self.last_time = now

            # 按时间添加令牌
            self.tokens = min(self.burst, self.tokens + elapsed * self.qps)

            if self.tokens >= 1:
                self.tokens -= 1
                self.allowed_requests += 1
                return True

            self.rejected_requests += 1
            return False

    def allow_for(self, timeout: float) -> bool:
        """
        等待获取令牌（阻塞，带超时）

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            是否成功获取令牌
        """
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

                # 按时间添加令牌
                self.tokens = min(self.burst, self.tokens + elapsed * self.qps)

                if self.tokens >= 1:
                    self.tokens -= 1
                    self.allowed_requests += 1
                    return True

                # 计算需要等待的时间
                wait_time = (1 - self.tokens) / self.qps
                remaining = deadline - now

                if wait_time > remaining:
                    self.rejected_requests += 1
                    return False

            # 等待
            time.sleep(min(wait_time, 0.01))

    async def allow_for_async(self, timeout: float) -> bool:
        """
        异步等待获取令牌

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            是否成功获取令牌
        """
        if self.qps <= 0:
            return True

        deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                now = time.monotonic()

                if now >= deadline:
                    self.total_requests += 1
                    self.rejected_requests += 1
                    return False

                elapsed = now - self.last_time
                self.last_time = now

                # 按时间添加令牌
                self.tokens = min(self.burst, self.tokens + elapsed * self.qps)

                if self.tokens >= 1:
                    self.tokens -= 1
                    self.total_requests += 1
                    self.allowed_requests += 1
                    return True

                # 计算需要等待的时间
                wait_time = (1 - self.tokens) / self.qps
                remaining = deadline - now

                if wait_time > remaining:
                    self.total_requests += 1
                    self.rejected_requests += 1
                    return False

            # 异步等待
            await asyncio.sleep(min(wait_time, 0.01))

    def wait_time(self) -> float:
        """
        获取需要等待的时间

        Returns:
            需要等待的秒数，0 表示立即可用
        """
        if self.qps <= 0:
            return 0

        with self._lock:
            if self.tokens >= 1:
                return 0
            return (1 - self.tokens) / self.qps

    def set_qps(self, qps: float, burst: int = 0) -> None:
        """
        动态更新 QPS 限制

        Args:
            qps: 新的 QPS 值
            burst: 新的突发容量
        """
        with self._lock:
            self.qps = qps
            self.burst = burst if burst > 0 else max(1, int(qps)) if qps > 0 else 1
            # 重置令牌数（不超过新的突发容量）
            self.tokens = min(self.tokens, self.burst)

    def stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            return {
                "qps": self.qps,
                "burst": self.burst,
                "current_tokens": round(self.tokens, 2),
                "total_requests": self.total_requests,
                "allowed_requests": self.allowed_requests,
                "rejected_requests": self.rejected_requests,
            }


# ======================== 并发限流器 ========================


class ConcurrencyLimiter:
    """
    并发限流器

    限制同时处理的请求数量
    """

    def __init__(self, max_concurrency: int):
        """
        初始化并发限流器

        Args:
            max_concurrency: 最大并发数
        """
        self.max_concurrency = max_concurrency
        self._current = 0
        self._lock = Lock()

        # 统计信息
        self.total_requests = 0
        self.allowed_requests = 0
        self.rejected_requests = 0

    def allow(self) -> bool:
        """
        尝试获取并发槽位

        Returns:
            是否成功获取
        """
        if self.max_concurrency <= 0:
            return True

        with self._lock:
            self.total_requests += 1
            if self._current < self.max_concurrency:
                self._current += 1
                self.allowed_requests += 1
                return True
            self.rejected_requests += 1
            return False

    def put(self) -> None:
        """释放并发槽位"""
        if self.max_concurrency <= 0:
            return

        with self._lock:
            if self._current > 0:
                self._current -= 1

    def current(self) -> int:
        """获取当前并发数"""
        with self._lock:
            return self._current

    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "max_concurrency": self.max_concurrency,
                "current_concurrency": self._current,
                "total_requests": self.total_requests,
                "allowed_requests": self.allowed_requests,
                "rejected_requests": self.rejected_requests,
            }


# ======================== 方法级限流器 ========================


class MethodLimiter:
    """
    方法级限流器

    支持按路径配置不同的限流规则
    """

    def __init__(self, default_concurrency: int = 0):
        """
        初始化方法级限流器

        Args:
            default_concurrency: 默认并发限制
        """
        self.default_concurrency = default_concurrency
        self._limiters: Dict[str, ConcurrencyLimiter] = {}
        self._default_limiter: Optional[ConcurrencyLimiter] = None
        self._lock = Lock()

        if default_concurrency > 0:
            self._default_limiter = ConcurrencyLimiter(default_concurrency)

    def add_limiter(self, path: str, max_concurrency: int) -> None:
        """
        添加路径级并发限制

        Args:
            path: 路径
            max_concurrency: 最大并发数
        """
        with self._lock:
            self._limiters[path] = ConcurrencyLimiter(max_concurrency)

    def allow(self, path: str) -> bool:
        """
        检查是否允许请求

        Args:
            path: 请求路径

        Returns:
            是否允许
        """
        limiter = self._find_limiter(path)
        if limiter:
            return limiter.allow()
        return True

    def put(self, path: str) -> None:
        """
        释放并发槽位

        Args:
            path: 请求路径
        """
        limiter = self._find_limiter(path)
        if limiter:
            limiter.put()

    def _find_limiter(self, path: str) -> Optional[ConcurrencyLimiter]:
        """查找匹配的限流器"""
        with self._lock:
            # 精确匹配
            if path in self._limiters:
                return self._limiters[path]

            # 前缀匹配
            for key, limiter in self._limiters.items():
                if key.endswith("*"):
                    prefix = key[:-1]
                    if path.startswith(prefix):
                        return limiter

            return self._default_limiter


class MethodQPSLimiter:
    """
    方法级 QPS 限流器

    支持按路径配置不同的 QPS 限制
    """

    def __init__(self, default_qps: float = 0, default_burst: int = 0):
        """
        初始化方法级 QPS 限流器

        Args:
            default_qps: 默认 QPS 限制
            default_burst: 默认突发容量
        """
        self.default_qps = default_qps
        self.default_burst = default_burst
        self._limiters: Dict[str, TokenBucketLimiter] = {}
        self._default_limiter: Optional[TokenBucketLimiter] = None
        self._lock = Lock()

        if default_qps > 0:
            self._default_limiter = TokenBucketLimiter(default_qps, default_burst)

    def add_method(self, path: str, qps: float, burst: int = 0) -> None:
        """
        添加路径级 QPS 限制

        Args:
            path: 路径
            qps: QPS 限制
            burst: 突发容量
        """
        with self._lock:
            self._limiters[path] = TokenBucketLimiter(qps, burst)

    def set_method_qps(self, path: str, qps: float, burst: int = 0) -> None:
        """
        动态更新路径的 QPS 限制

        Args:
            path: 路径
            qps: 新的 QPS 值
            burst: 新的突发容量
        """
        with self._lock:
            if path in self._limiters:
                self._limiters[path].set_qps(qps, burst)
            else:
                self._limiters[path] = TokenBucketLimiter(qps, burst)

    def remove_method(self, path: str) -> None:
        """
        移除路径的 QPS 限制

        Args:
            path: 路径
        """
        with self._lock:
            self._limiters.pop(path, None)

    def allow(self, path: str) -> bool:
        """
        检查是否允许请求

        Args:
            path: 请求路径

        Returns:
            是否允许
        """
        limiter = self._find_limiter(path)
        if limiter:
            return limiter.allow()
        return True

    def allow_for(self, path: str, timeout: float) -> bool:
        """
        等待获取令牌

        Args:
            path: 请求路径
            timeout: 最大等待时间

        Returns:
            是否成功获取
        """
        limiter = self._find_limiter(path)
        if limiter:
            return limiter.allow_for(timeout)
        return True

    async def allow_for_async(self, path: str, timeout: float) -> bool:
        """
        异步等待获取令牌

        Args:
            path: 请求路径
            timeout: 最大等待时间

        Returns:
            是否成功获取
        """
        limiter = self._find_limiter(path)
        if limiter:
            return await limiter.allow_for_async(timeout)
        return True

    def _find_limiter(self, path: str) -> Optional[TokenBucketLimiter]:
        """查找匹配的限流器"""
        with self._lock:
            # 精确匹配
            if path in self._limiters:
                return self._limiters[path]

            # 前缀匹配
            for key, limiter in self._limiters.items():
                if key.endswith("*"):
                    prefix = key[:-1]
                    if path.startswith(prefix):
                        return limiter

            return self._default_limiter

    def stats(self) -> List[Dict[str, Any]]:
        """
        获取所有限流器的统计信息

        Returns:
            统计信息列表
        """
        result = []
        with self._lock:
            if self._default_limiter:
                stats = self._default_limiter.stats()
                stats["path"] = "*"
                result.append(stats)

            for path, limiter in self._limiters.items():
                stats = limiter.stats()
                stats["path"] = path
                result.append(stats)

        return result


# ======================== QPS 限流器 ========================


class QPSLimiter:
    """
    综合 QPS 限流器

    整合 QPS 限流和并发控制
    """

    def __init__(self, config: QPSLimitConfig):
        """
        初始化 QPS 限流器

        Args:
            config: 限流配置
        """
        self.config = config

        # 默认 QPS 限流器
        self._qps_limiter = MethodQPSLimiter(
            config.default_qps,
            config.default_burst,
        )

        # 默认并发限流器
        self._concurrency_limiter: Optional[ConcurrencyLimiter] = None
        if config.max_concurrency > 0:
            self._concurrency_limiter = ConcurrencyLimiter(config.max_concurrency)

        # 路径级并发限流器
        self._path_concurrency: Dict[str, ConcurrencyLimiter] = {}

        # 注册方法级配置
        for method_config in config.method_qps:
            key = self._make_key(method_config.method, method_config.path)
            if method_config.qps > 0:
                self._qps_limiter.add_method(key, method_config.qps, method_config.burst)
            if method_config.max_concurrency > 0:
                self._path_concurrency[key] = ConcurrencyLimiter(
                    method_config.max_concurrency
                )

    def _make_key(self, method: str, path: str) -> str:
        """生成限流 key"""
        if method == "*":
            return path
        return f"{method.upper()}:{path}"

    def _find_concurrency_limiter(
        self, method: str, path: str
    ) -> Optional[ConcurrencyLimiter]:
        """查找并发限流器"""
        # 精确匹配
        key = self._make_key(method, path)
        if key in self._path_concurrency:
            return self._path_concurrency[key]

        # 通配方法
        if path in self._path_concurrency:
            return self._path_concurrency[path]

        # 前缀匹配
        for k, limiter in self._path_concurrency.items():
            if k.endswith("*"):
                prefix = k[:-1]
                if path.startswith(prefix):
                    return limiter

        return self._concurrency_limiter

    def allow(self, method: str, path: str) -> bool:
        """
        检查是否允许请求

        Args:
            method: HTTP 方法
            path: 请求路径

        Returns:
            是否允许
        """
        # 检查 QPS
        key = self._make_key(method, path)
        if not self._qps_limiter.allow(key):
            # 尝试通配方法
            if not self._qps_limiter.allow(path):
                return False

        return True

    def allow_for(self, method: str, path: str, timeout: float) -> bool:
        """
        等待获取令牌

        Args:
            method: HTTP 方法
            path: 请求路径
            timeout: 最大等待时间

        Returns:
            是否成功获取
        """
        key = self._make_key(method, path)
        if not self._qps_limiter.allow_for(key, timeout):
            if not self._qps_limiter.allow_for(path, timeout):
                return False
        return True

    async def allow_for_async(self, method: str, path: str, timeout: float) -> bool:
        """
        异步等待获取令牌

        Args:
            method: HTTP 方法
            path: 请求路径
            timeout: 最大等待时间

        Returns:
            是否成功获取
        """
        key = self._make_key(method, path)
        if not await self._qps_limiter.allow_for_async(key, timeout):
            if not await self._qps_limiter.allow_for_async(path, timeout):
                return False
        return True

    def acquire_concurrency(self, method: str, path: str) -> bool:
        """
        获取并发槽位

        Args:
            method: HTTP 方法
            path: 请求路径

        Returns:
            是否成功获取
        """
        limiter = self._find_concurrency_limiter(method, path)
        if limiter:
            return limiter.allow()
        return True

    def release_concurrency(self, method: str, path: str) -> None:
        """
        释放并发槽位

        Args:
            method: HTTP 方法
            path: 请求路径
        """
        limiter = self._find_concurrency_limiter(method, path)
        if limiter:
            limiter.put()

    def stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        result = {
            "qps_stats": self._qps_limiter.stats(),
            "concurrency_stats": {},
        }

        if self._concurrency_limiter:
            result["concurrency_stats"]["default"] = self._concurrency_limiter.stats()

        for path, limiter in self._path_concurrency.items():
            result["concurrency_stats"][path] = limiter.stats()

        return result


# ======================== HTTP 中间件 ========================


class QPSRateLimitMiddleware(BaseHTTPMiddleware):
    """
    QPS 限流中间件

    提供 QPS 和并发数限制
    """

    def __init__(
        self,
        app: ASGIApp,
        config: Optional[QPSLimitConfig] = None,
        limiter: Optional[QPSLimiter] = None,
        wait_timeout: float = 0,
    ):
        """
        初始化限流中间件

        Args:
            app: ASGI 应用
            config: 限流配置
            limiter: 限流器实例（优先使用）
            wait_timeout: 等待超时时间（0 表示不等待，直接拒绝）
        """
        super().__init__(app)
        if limiter:
            self.limiter = limiter
        elif config:
            self.limiter = QPSLimiter(config)
        else:
            self.limiter = QPSLimiter(QPSLimitConfig())
        self.wait_timeout = wait_timeout

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method
        path = request.url.path

        # 检查 QPS 限制
        if self.wait_timeout > 0:
            allowed = await self.limiter.allow_for_async(method, path, self.wait_timeout)
        else:
            allowed = self.limiter.allow(method, path)

        if not allowed:
            logger.warning(
                f"Request rejected by QPS rate limiter: {method} {path}"
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "1"},
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"{method} {path} is rejected by rate limiter, QPS limit exceeded",
                    "code": 429,
                },
            )

        # 检查并发限制
        if not self.limiter.acquire_concurrency(method, path):
            logger.warning(
                f"Request rejected by concurrency limiter: {method} {path}"
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "1"},
                content={
                    "error": "concurrency_limit_exceeded",
                    "message": f"{method} {path} is rejected, max concurrency exceeded",
                    "code": 429,
                },
            )

        try:
            return await call_next(request)
        finally:
            self.limiter.release_concurrency(method, path)


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
        初始化并发限制中间件

        Args:
            app: ASGI 应用
            max_concurrency: 最大并发数
        """
        super().__init__(app)
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._current = 0
        self._lock = Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 尝试获取信号量（非阻塞）
        acquired = self._semaphore.locked() is False

        if not acquired:
            try:
                # 尝试立即获取
                await asyncio.wait_for(self._semaphore.acquire(), timeout=0)
                acquired = True
            except asyncio.TimeoutError:
                pass

        if not acquired:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "1"},
                content={
                    "error": "concurrency_limit_exceeded",
                    "message": "Max concurrency exceeded",
                    "code": 429,
                },
            )

        try:
            with self._lock:
                self._current += 1
            return await call_next(request)
        finally:
            self._semaphore.release()
            with self._lock:
                self._current -= 1


# ======================== 工厂函数 ========================


def create_qps_limiter(
    default_qps: float = 0,
    default_burst: int = 0,
    max_concurrency: int = 0,
    method_configs: Optional[List[Dict[str, Any]]] = None,
) -> QPSLimiter:
    """
    创建 QPS 限流器

    Args:
        default_qps: 默认 QPS 限制
        default_burst: 默认突发容量
        max_concurrency: 最大并发数
        method_configs: 方法级配置列表

    Returns:
        QPSLimiter 实例

    示例:
        ```python
        limiter = create_qps_limiter(
            default_qps=100,
            default_burst=10,
            max_concurrency=50,
            method_configs=[
                {"path": "/api/v1/upload", "qps": 10, "burst": 5},
                {"path": "/api/v1/*", "qps": 50},
            ]
        )
        ```
    """
    method_qps = []
    if method_configs:
        for cfg in method_configs:
            method_qps.append(
                MethodQPSConfig(
                    method=cfg.get("method", "*"),
                    path=cfg.get("path", "/"),
                    qps=cfg.get("qps", 0),
                    burst=cfg.get("burst", 0),
                    max_concurrency=cfg.get("max_concurrency", 0),
                )
            )

    config = QPSLimitConfig(
        default_qps=default_qps,
        default_burst=default_burst,
        max_concurrency=max_concurrency,
        method_qps=method_qps,
    )
    return QPSLimiter(config)


def limit_all_qps(qps: float, burst: int = 0) -> QPSLimiter:
    """
    创建简单的全局 QPS 限流器

    Args:
        qps: QPS 限制
        burst: 突发容量

    Returns:
        QPSLimiter 实例
    """
    return create_qps_limiter(default_qps=qps, default_burst=burst)


def limit_all_concurrency(max_concurrency: int) -> QPSLimiter:
    """
    创建简单的全局并发限流器

    Args:
        max_concurrency: 最大并发数

    Returns:
        QPSLimiter 实例
    """
    return create_qps_limiter(max_concurrency=max_concurrency)


# ======================== 统计端点处理器 ========================


class RateLimitStatsHandler:
    """
    限流统计信息处理器

    提供 HTTP 端点暴露限流统计信息
    """

    def __init__(self, limiter: QPSLimiter):
        """
        初始化统计处理器

        Args:
            limiter: 限流器实例
        """
        self.limiter = limiter

    async def __call__(self, request: Request) -> Response:
        """
        处理统计请求

        Args:
            request: HTTP 请求

        Returns:
            JSON 响应
        """
        return JSONResponse(content=self.limiter.stats())
