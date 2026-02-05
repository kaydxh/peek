"""
时间相关工具模块

包含：
- ExponentialBackOff: 指数退避重试器
- retry/retry_sync: 重试装饰器
- retry_with_backoff: 重试便捷函数
- Wait/Poll: 等待和轮询工具
- Timer: 计时器工具
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
from peek.time.wait import (
    # 异常类
    ConditionNotMetError,
    MaxRetriesExceededError,
    TimeoutError,
    WaitCancelledError,
    WaitResult,
    # 带超时调用
    call_with_timeout,
    call_with_timeout_sync,
    # 定时轮询
    until,
    jitter_until,
    backoff_until,
    # 条件等待
    poll,
    poll_immediate,
    poll_until_context_done,
    # 等待工具
    wait_for_condition,
    wait_for_condition_sync,
    sleep_with_jitter,
    sleep_with_jitter_sync,
    # 计时器
    Timer,
    Timeout,
    TimeoutSync,
    # 装饰器
    with_timeout,
    with_timeout_sync,
    with_retry,
    with_retry_sync,
)

__all__ = [
    # ===== backoff 模块 =====
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
    # ===== wait 模块 =====
    # 异常类
    "TimeoutError",
    "ConditionNotMetError",
    "MaxRetriesExceededError",
    "WaitCancelledError",
    "WaitResult",
    # 带超时调用
    "call_with_timeout",
    "call_with_timeout_sync",
    # 定时轮询
    "until",
    "jitter_until",
    "backoff_until",
    # 条件等待
    "poll",
    "poll_immediate",
    "poll_until_context_done",
    # 等待工具
    "wait_for_condition",
    "wait_for_condition_sync",
    "sleep_with_jitter",
    "sleep_with_jitter_sync",
    # 计时器
    "Timer",
    "Timeout",
    "TimeoutSync",
    # 装饰器
    "with_timeout",
    "with_timeout_sync",
    "with_retry",
    "with_retry_sync",
]