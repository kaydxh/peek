#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP 中间件模块

提供 HTTP 中间件链支持：
- 基础中间件：RequestID、Timer、Recovery、Logger
- 限流中间件：QPS 限流、并发限流
- 超时中间件：请求超时控制
- OpenTelemetry 中间件：追踪、指标
"""

from typing import Any, Awaitable, Callable, List, Optional

from fastapi import Request, Response

# 导出中间件链
from peek.net.webserver.middleware.handler_chain import (
    HandlerChain,
    HandlerChainMiddleware,
    MiddlewareFunc,
    PreHandlerFunc,
    PostHandlerFunc,
)

# 导出基础中间件
from peek.net.webserver.middleware.requestid import RequestIDMiddleware
from peek.net.webserver.middleware.base_timer import TimerMiddleware
from peek.net.webserver.middleware.recovery import RecoveryMiddleware
from peek.net.webserver.middleware.logger import LoggerMiddleware
from peek.net.webserver.middleware.body_size import MaxBodySizeMiddleware

# 导出限流中间件
from peek.net.webserver.middleware.ratelimit import (
    # 配置
    MethodQPSConfig,
    QPSLimitConfig,
    QPSStats,
    # 限流器
    TokenBucketLimiter,
    ConcurrencyLimiter,
    MethodLimiter,
    MethodQPSLimiter,
    QPSLimiter,
    # 中间件
    QPSRateLimitMiddleware,
    ConcurrencyLimitMiddleware,
    # 工厂函数
    create_qps_limiter,
    limit_all_qps,
    limit_all_concurrency,
    # 统计处理器
    RateLimitStatsHandler,
)

# 导出超时中间件
from peek.net.webserver.middleware.timeout import (
    TimeoutMiddleware,
    PathTimeoutMiddleware,
    timeout,
)

# 导出请求耗时中间件
from peek.net.webserver.middleware.timer import (
    HttpTimerMiddleware,
)

# 导出 OpenTelemetry 中间件
from peek.net.webserver.middleware.opentelemetry import (
    TraceMiddleware,
    MetricMiddleware,
)

__all__ = [
    # 中间件链
    "HandlerChain",
    "HandlerChainMiddleware",
    # 基础中间件
    "RequestIDMiddleware",
    "TimerMiddleware",
    "RecoveryMiddleware",
    "LoggerMiddleware",
    "MaxBodySizeMiddleware",
    "create_default_handler_chain",
    # 限流
    "MethodQPSConfig",
    "QPSLimitConfig",
    "QPSStats",
    "TokenBucketLimiter",
    "ConcurrencyLimiter",
    "MethodLimiter",
    "MethodQPSLimiter",
    "QPSLimiter",
    "QPSRateLimitMiddleware",
    "ConcurrencyLimitMiddleware",
    "create_qps_limiter",
    "limit_all_qps",
    "limit_all_concurrency",
    "RateLimitStatsHandler",
    # 超时
    "TimeoutMiddleware",
    "PathTimeoutMiddleware",
    "timeout",
    # 请求耗时
    "HttpTimerMiddleware",
    # OpenTelemetry
    "TraceMiddleware",
    "MetricMiddleware",
    # 类型
    "MiddlewareFunc",
    "PreHandlerFunc",
    "PostHandlerFunc",
]


def create_default_handler_chain(
    debug: bool = False,
    max_body_size: int = 0,
    logger: Any = None,
    log_request_body: bool = True,
    log_response_body: bool = True,
    log_request_headers: bool = False,
    log_response_headers: bool = False,
    max_string_length: int = LoggerMiddleware.DEFAULT_MAX_STRING_LENGTH,
    skip_log_paths: List[str] = None,
) -> HandlerChain:
    """
    创建默认的中间件链

    包含：
    - RequestIDMiddleware: Request ID 生成
    - RecoveryMiddleware: 异常恢复
    - TimerMiddleware: 计时器
    - LoggerMiddleware: 日志记录（支持请求/响应的 body 和 headers）
    - MaxBodySizeMiddleware: 请求体大小限制（如果设置）

    Args:
        debug: 是否开启调试模式
        max_body_size: 最大请求体大小（0 表示不限制）
        logger: 日志记录器
        log_request_body: 是否记录请求体
        log_response_body: 是否记录响应体
        log_request_headers: 是否记录请求头
        log_response_headers: 是否记录响应头
        max_string_length: 字符串字段的最大打印长度，超过则截断
        skip_log_paths: 跳过记录的路径列表

    Returns:
        HandlerChain 实例
    """
    chain = HandlerChain()

    # 注意：中间件按添加顺序的反序执行
    # 所以先添加的最后执行
    chain.add_handler(
        LoggerMiddleware,
        logger=logger,
        log_request_body=log_request_body,
        log_response_body=log_response_body,
        log_request_headers=log_request_headers,
        log_response_headers=log_response_headers,
        max_string_length=max_string_length,
        skip_paths=skip_log_paths,
    )
    chain.add_handler(TimerMiddleware)
    chain.add_handler(RecoveryMiddleware, debug=debug)
    chain.add_handler(RequestIDMiddleware)

    if max_body_size > 0:
        chain.add_handler(MaxBodySizeMiddleware, max_body_size=max_body_size)

    return chain