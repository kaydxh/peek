"""
时间相关工具模块

包含：
- ExponentialBackOff: 指数退避重试器
- retry: 异步重试装饰器
- retry_sync: 同步重试装饰器
- retry_with_backoff: 异步重试便捷函数
- retry_with_backoff_sync: 同步重试便捷函数
"""

from peek.time.backoff import (
    DEFAULT_INITIAL_INTERVAL,
    DEFAULT_MAX_ELAPSED_COUNT,
    DEFAULT_MAX_ELAPSED_TIME,
    DEFAULT_MAX_INTERVAL,
    DEFAULT_MIN_INTERVAL,
    DEFAULT_MULTIPLIER,
    DEFAULT_RANDOMIZATION_FACTOR,
    BackOffOptions,
    ExponentialBackOff,
    retry,
    retry_sync,
    retry_with_backoff,
    retry_with_backoff_sync,
)
from peek.time.func_duration_controller import FunctionDurationController

__all__ = [
    # 类
    "ExponentialBackOff",
    "BackOffOptions",
    "FunctionDurationController",
    # 装饰器
    "retry",
    "retry_sync",
    # 便捷函数
    "retry_with_backoff",
    "retry_with_backoff_sync",
    # 常量
    "DEFAULT_INITIAL_INTERVAL",
    "DEFAULT_RANDOMIZATION_FACTOR",
    "DEFAULT_MULTIPLIER",
    "DEFAULT_MAX_INTERVAL",
    "DEFAULT_MIN_INTERVAL",
    "DEFAULT_MAX_ELAPSED_TIME",
    "DEFAULT_MAX_ELAPSED_COUNT",
]