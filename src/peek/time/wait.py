"""
Wait/Retry 等待工具模块

移植自 golang/go/time/wait.go

功能特性：
- 支持带超时的函数调用
- 支持定时轮询执行（Until/JitterUntil）
- 支持条件等待（Poll/PollImmediate/PollUntil）
- 支持带退避策略的重试（BackOffUntil）
- 支持同步和异步两种模式

使用示例：
    # 带超时调用
    result = await call_with_timeout(async_func, timeout=5.0)
    
    # 定时轮询（直到上下文取消）
    await until(check_status, period=1.0, timeout=60.0)
    
    # 条件等待
    await poll(condition_func, interval=0.5, timeout=30.0)
    
    # 带退避策略的重试
    await backoff_until(task_func, backoff, loop=False)
"""

import asyncio
import functools
import logging
import time
import traceback
from dataclasses import dataclass
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from peek.time.backoff import ExponentialBackOff

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimeoutError(Exception):
    """超时错误"""

    pass


class ConditionNotMetError(Exception):
    """条件未满足错误"""

    pass


class MaxRetriesExceededError(Exception):
    """超过最大重试次数错误"""

    pass


class WaitCancelledError(Exception):
    """等待被取消错误"""

    pass


@dataclass
class WaitResult:
    """等待结果"""

    success: bool  # 是否成功
    result: Any = None  # 返回值
    error: Optional[Exception] = None  # 异常
    elapsed_time: float = 0.0  # 耗时（秒）
    retry_count: int = 0  # 重试次数


# ============================================================================
# 带超时的函数调用
# ============================================================================


async def call_with_timeout(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    timeout: float = 0,
    **kwargs: Any,
) -> T:
    """
    带超时的异步函数调用

    Args:
        func: 要执行的异步函数
        *args: 位置参数
        timeout: 超时时间（秒），0 或负数表示不超时
        **kwargs: 关键字参数

    Returns:
        函数执行结果

    Raises:
        TimeoutError: 执行超时
        Exception: 函数执行异常

    使用示例：
        result = await call_with_timeout(
            fetch_data,
            "https://api.example.com",
            timeout=5.0,
        )
    """
    start_time = time.monotonic()

    # 不设置超时
    if timeout <= 0:
        result = await func(*args, **kwargs)
        elapsed = time.monotonic() - start_time
        logger.debug(f"call_with_timeout: 执行完成, elapsed={elapsed:.3f}s")
        return result

    try:
        result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        elapsed = time.monotonic() - start_time
        logger.debug(f"call_with_timeout: 执行完成, elapsed={elapsed:.3f}s")
        return result
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start_time
        logger.warning(f"call_with_timeout: 执行超时, timeout={timeout}s, elapsed={elapsed:.3f}s")
        raise TimeoutError(f"执行超时: timeout={timeout}s")


def call_with_timeout_sync(
    func: Callable[..., T],
    *args: Any,
    timeout: float = 0,
    **kwargs: Any,
) -> T:
    """
    带超时的同步函数调用（通过线程实现）

    注意：如果函数在超时后仍在执行，它会继续运行直到完成，
    但调用者会立即收到 TimeoutError

    Args:
        func: 要执行的同步函数
        *args: 位置参数
        timeout: 超时时间（秒），0 或负数表示不超时
        **kwargs: 关键字参数

    Returns:
        函数执行结果

    Raises:
        TimeoutError: 执行超时
        Exception: 函数执行异常
    """
    import concurrent.futures

    start_time = time.monotonic()

    # 不设置超时
    if timeout <= 0:
        result = func(*args, **kwargs)
        elapsed = time.monotonic() - start_time
        logger.debug(f"call_with_timeout_sync: 执行完成, elapsed={elapsed:.3f}s")
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=timeout)
            elapsed = time.monotonic() - start_time
            logger.debug(f"call_with_timeout_sync: 执行完成, elapsed={elapsed:.3f}s")
            return result
        except concurrent.futures.TimeoutError:
            elapsed = time.monotonic() - start_time
            logger.warning(f"call_with_timeout_sync: 执行超时, timeout={timeout}s, elapsed={elapsed:.3f}s")
            raise TimeoutError(f"执行超时: timeout={timeout}s")


# ============================================================================
# 定时轮询执行（Until）
# ============================================================================


async def until(
    func: Callable[..., Awaitable[Any]],
    period: float,
    timeout: float = 0,
    stop_on_error: bool = False,
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    定时轮询执行函数，直到超时或被取消

    函数会在每个周期执行一次，执行间隔从上一次执行完成后开始计算（sliding=True）

    Args:
        func: 要定时执行的异步函数
        period: 执行周期（秒）
        timeout: 总超时时间（秒），0 表示永不超时
        stop_on_error: 是否在遇到错误时停止
        *args: 传递给函数的位置参数
        **kwargs: 传递给函数的关键字参数

    Raises:
        TimeoutError: 达到超时时间
        Exception: 当 stop_on_error=True 时，函数执行异常

    使用示例：
        # 每秒检查一次状态，最多 60 秒
        await until(check_status, period=1.0, timeout=60.0)

        # 永久轮询（直到外部取消）
        await until(heartbeat, period=5.0)
    """
    await jitter_until(
        func,
        period,
        jitter_factor=0,
        timeout=timeout,
        stop_on_error=stop_on_error,
        *args,
        **kwargs,
    )


async def jitter_until(
    func: Callable[..., Awaitable[Any]],
    period: float,
    jitter_factor: float = 0.5,
    timeout: float = 0,
    stop_on_error: bool = False,
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    带抖动的定时轮询执行函数

    Args:
        func: 要定时执行的异步函数
        period: 基础执行周期（秒）
        jitter_factor: 抖动因子（0-1），实际间隔在 [period*(1-jitter), period*(1+jitter)] 之间
        timeout: 总超时时间（秒），0 表示永不超时
        stop_on_error: 是否在遇到错误时停止
        *args: 传递给函数的位置参数
        **kwargs: 传递给函数的关键字参数

    使用示例：
        # 每 5 秒左右执行一次（带抖动），防止惊群
        await jitter_until(sync_data, period=5.0, jitter_factor=0.3, timeout=300.0)
    """
    backoff = ExponentialBackOff(
        initial_interval=period,
        multiplier=1.0,  # 保持固定间隔
        randomization_factor=jitter_factor,
        max_elapsed_time=timeout,
        max_elapsed_count=-1,  # 不限制次数
    )

    await backoff_until(
        func,
        backoff,
        sliding=True,
        loop=True,
        stop_on_error=stop_on_error,
        *args,
        **kwargs,
    )


# ============================================================================
# 带退避策略的重试（BackOffUntil）
# ============================================================================


async def backoff_until(
    func: Callable[..., Awaitable[Any]],
    backoff: ExponentialBackOff,
    sliding: bool = True,
    loop: bool = False,
    stop_on_error: bool = False,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    带退避策略的循环执行函数

    Args:
        func: 要执行的异步函数
        backoff: 退避策略对象
        sliding: 是否在函数执行完成后才开始计算等待时间
                 True: 等待时间从函数执行完成后开始
                 False: 等待时间包含函数执行时间
        loop: 是否持续循环
              True: 持续执行直到超时/取消
              False: 函数返回成功（不抛异常）时停止
        stop_on_error: 是否在遇到错误时停止（仅在 loop=True 时有效）
        *args: 传递给函数的位置参数
        **kwargs: 传递给函数的关键字参数

    Returns:
        函数执行结果（当 loop=False 时）

    Raises:
        MaxRetriesExceededError: 达到最大重试次数或时间
        Exception: 当 stop_on_error=True 时，函数执行异常

    使用示例：
        # 重试直到成功或达到限制
        backoff = ExponentialBackOff(max_elapsed_count=5)
        result = await backoff_until(fetch_data, backoff, loop=False)

        # 持续轮询
        backoff = ExponentialBackOff(max_elapsed_time=300)
        await backoff_until(check_status, backoff, loop=True)
    """
    backoff.reset()
    last_error: Optional[Exception] = None

    while True:
        start_time = time.monotonic()

        if not sliding:
            # 提前获取下一次等待时间
            wait_time, should_continue = backoff.next_backoff()
            if not should_continue:
                msg = f"达到最大等待时间或次数限制: count={backoff.elapsed_count}, elapsed={backoff.elapsed_time:.2f}s"
                logger.warning(f"backoff_until: {msg}")
                if last_error:
                    raise MaxRetriesExceededError(msg) from last_error
                raise MaxRetriesExceededError(msg)

        # 执行函数
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"backoff_until: 函数执行成功, count={backoff.elapsed_count}")

            if not loop:
                return result

        except Exception as e:
            last_error = e
            logger.debug(f"backoff_until: 函数执行异常, count={backoff.elapsed_count}, error={e}")

            if stop_on_error:
                raise

        if sliding:
            # 函数执行完成后才获取等待时间
            wait_time, should_continue = backoff.next_backoff()
            if not should_continue:
                msg = f"达到最大等待时间或次数限制: count={backoff.elapsed_count}, elapsed={backoff.elapsed_time:.2f}s"
                logger.warning(f"backoff_until: {msg}")
                if last_error:
                    raise MaxRetriesExceededError(msg) from last_error
                raise MaxRetriesExceededError(msg)

        # 计算实际需要等待的时间
        elapsed = time.monotonic() - start_time
        remain = wait_time - elapsed

        if remain > 0:
            await asyncio.sleep(remain)


# ============================================================================
# 条件等待（Poll）
# ============================================================================

# 条件函数类型：返回 (done, result) 或抛出异常
ConditionFunc = Callable[..., Awaitable[Tuple[bool, Any]]]
ConditionFuncSync = Callable[..., Tuple[bool, Any]]


async def poll(
    condition: ConditionFunc,
    interval: float,
    timeout: float,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    轮询等待条件满足

    持续检查条件函数，直到条件满足或超时

    Args:
        condition: 条件函数，返回 (done, result)
                  done=True 表示条件满足，result 为返回值
        interval: 检查间隔（秒）
        timeout: 超时时间（秒）
        *args: 传递给条件函数的位置参数
        **kwargs: 传递给条件函数的关键字参数

    Returns:
        条件满足时的返回值

    Raises:
        TimeoutError: 等待超时
        ConditionNotMetError: 条件一直未满足

    使用示例：
        async def check_ready() -> Tuple[bool, str]:
            status = await get_status()
            if status == "ready":
                return True, status
            return False, None

        result = await poll(check_ready, interval=1.0, timeout=30.0)
    """
    return await poll_immediate(
        condition,
        interval,
        timeout,
        immediate=False,
        *args,
        **kwargs,
    )


async def poll_immediate(
    condition: ConditionFunc,
    interval: float,
    timeout: float,
    immediate: bool = True,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    轮询等待条件满足（可选立即执行首次检查）

    Args:
        condition: 条件函数，返回 (done, result)
        interval: 检查间隔（秒）
        timeout: 超时时间（秒）
        immediate: 是否立即执行首次检查（不等待 interval）
        *args: 传递给条件函数的位置参数
        **kwargs: 传递给条件函数的关键字参数

    Returns:
        条件满足时的返回值

    Raises:
        TimeoutError: 等待超时
        ConditionNotMetError: 条件一直未满足

    使用示例：
        # 立即检查一次，然后每秒检查
        result = await poll_immediate(check_ready, interval=1.0, timeout=30.0)
    """
    start_time = time.monotonic()

    first_check = True
    while True:
        # 检查是否超时
        elapsed = time.monotonic() - start_time
        if timeout > 0 and elapsed >= timeout:
            raise TimeoutError(f"等待条件超时: timeout={timeout}s, elapsed={elapsed:.2f}s")

        # 首次检查或等待间隔
        if first_check and immediate:
            first_check = False
        else:
            if first_check:
                first_check = False
            await asyncio.sleep(interval)

        # 检查条件
        try:
            done, result = await condition(*args, **kwargs)
            if done:
                logger.debug(f"poll_immediate: 条件满足, elapsed={time.monotonic() - start_time:.2f}s")
                return result
        except Exception as e:
            logger.debug(f"poll_immediate: 条件检查异常, error={e}")
            # 继续轮询，除非超时


async def poll_until_context_done(
    condition: ConditionFunc,
    interval: float,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    轮询等待条件满足，直到当前任务被取消

    Args:
        condition: 条件函数，返回 (done, result)
        interval: 检查间隔（秒）
        *args: 传递给条件函数的位置参数
        **kwargs: 传递给条件函数的关键字参数

    Returns:
        条件满足时的返回值

    Raises:
        WaitCancelledError: 任务被取消
        ConditionNotMetError: 条件一直未满足
    """
    while True:
        try:
            # 检查条件
            done, result = await condition(*args, **kwargs)
            if done:
                return result

            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise WaitCancelledError("等待被取消")


# ============================================================================
# 重试工具（Retry）
# ============================================================================


async def retry(
    func: Callable[..., Awaitable[T]],
    period: float,
    retry_times: int,
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    简单重试函数

    Args:
        func: 要重试的异步函数
        period: 重试间隔（秒）
        retry_times: 重试次数（不包括首次调用）
        *args: 传递给函数的位置参数
        **kwargs: 传递给函数的关键字参数

    Returns:
        函数执行结果

    Raises:
        MaxRetriesExceededError: 超过最大重试次数

    使用示例：
        result = await retry(fetch_data, period=1.0, retry_times=3, url="...")
    """
    backoff = ExponentialBackOff(
        initial_interval=period,
        multiplier=1.0,  # 固定间隔
        randomization_factor=0,
        max_elapsed_time=0,  # 不限制时间
        max_elapsed_count=retry_times,
    )

    return await backoff_until(
        func,
        backoff,
        sliding=True,
        loop=False,
        *args,
        **kwargs,
    )


def retry_sync(
    func: Callable[..., T],
    period: float,
    retry_times: int,
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    简单同步重试函数

    Args:
        func: 要重试的同步函数
        period: 重试间隔（秒）
        retry_times: 重试次数（不包括首次调用）
        *args: 传递给函数的位置参数
        **kwargs: 传递给函数的关键字参数

    Returns:
        函数执行结果

    Raises:
        MaxRetriesExceededError: 超过最大重试次数
    """
    last_error: Optional[Exception] = None
    total_attempts = retry_times + 1  # 首次调用 + 重试次数

    for attempt in range(total_attempts):
        try:
            result = func(*args, **kwargs)
            logger.debug(f"retry_sync: 执行成功, attempt={attempt + 1}")
            return result
        except Exception as e:
            last_error = e
            logger.debug(f"retry_sync: 执行异常, attempt={attempt + 1}, error={e}")

            if attempt < total_attempts - 1:
                time.sleep(period)

    msg = f"超过最大重试次数: retry_times={retry_times}"
    raise MaxRetriesExceededError(msg) from last_error


# ============================================================================
# 等待工具函数
# ============================================================================


async def wait_for_condition(
    condition: Callable[[], Awaitable[bool]],
    timeout: float,
    interval: float = 0.1,
    message: str = "",
) -> None:
    """
    等待条件满足

    Args:
        condition: 条件函数，返回 True 表示条件满足
        timeout: 超时时间（秒）
        interval: 检查间隔（秒）
        message: 超时时的错误信息

    Raises:
        TimeoutError: 等待超时

    使用示例：
        await wait_for_condition(
            lambda: server.is_ready(),
            timeout=30.0,
            message="等待服务器就绪超时"
        )
    """

    async def wrapper() -> Tuple[bool, None]:
        result = await condition()
        return result, None

    try:
        await poll_immediate(wrapper, interval=interval, timeout=timeout)
    except TimeoutError:
        if message:
            raise TimeoutError(message)
        raise


def wait_for_condition_sync(
    condition: Callable[[], bool],
    timeout: float,
    interval: float = 0.1,
    message: str = "",
) -> None:
    """
    同步等待条件满足

    Args:
        condition: 条件函数，返回 True 表示条件满足
        timeout: 超时时间（秒）
        interval: 检查间隔（秒）
        message: 超时时的错误信息

    Raises:
        TimeoutError: 等待超时
    """
    start_time = time.monotonic()

    while True:
        elapsed = time.monotonic() - start_time
        if timeout > 0 and elapsed >= timeout:
            if message:
                raise TimeoutError(message)
            raise TimeoutError(f"等待条件超时: timeout={timeout}s, elapsed={elapsed:.2f}s")

        if condition():
            return

        time.sleep(interval)


async def sleep_with_jitter(
    base_duration: float,
    jitter_factor: float = 0.1,
) -> None:
    """
    带抖动的异步睡眠

    实际睡眠时间在 [base * (1 - jitter), base * (1 + jitter)] 范围内

    Args:
        base_duration: 基础睡眠时间（秒）
        jitter_factor: 抖动因子（0-1）

    使用示例：
        # 睡眠约 5 秒（带 10% 抖动）
        await sleep_with_jitter(5.0, jitter_factor=0.1)
    """
    import random

    min_duration = base_duration * (1 - jitter_factor)
    max_duration = base_duration * (1 + jitter_factor)
    actual_duration = random.uniform(min_duration, max_duration)
    await asyncio.sleep(actual_duration)


def sleep_with_jitter_sync(
    base_duration: float,
    jitter_factor: float = 0.1,
) -> None:
    """
    带抖动的同步睡眠

    Args:
        base_duration: 基础睡眠时间（秒）
        jitter_factor: 抖动因子（0-1）
    """
    import random

    min_duration = base_duration * (1 - jitter_factor)
    max_duration = base_duration * (1 + jitter_factor)
    actual_duration = random.uniform(min_duration, max_duration)
    time.sleep(actual_duration)


# ============================================================================
# 上下文管理器
# ============================================================================


class Timeout:
    """
    超时上下文管理器

    使用示例：
        async with Timeout(5.0):
            await long_running_task()
    """

    def __init__(self, timeout: float):
        """
        Args:
            timeout: 超时时间（秒），0 或负数表示不超时
        """
        self.timeout = timeout
        self._task: Optional[asyncio.Task] = None

    async def __aenter__(self) -> "Timeout":
        if self.timeout > 0:
            self._task = asyncio.current_task()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class TimeoutSync:
    """
    同步超时上下文管理器（基于信号，仅 Unix）

    注意：此实现仅适用于主线程

    使用示例：
        with TimeoutSync(5.0):
            long_running_task()
    """

    def __init__(self, timeout: float):
        """
        Args:
            timeout: 超时时间（秒），0 或负数表示不超时
        """
        self.timeout = timeout
        self._old_handler = None

    def __enter__(self) -> "TimeoutSync":
        if self.timeout > 0:
            import signal

            def handler(signum, frame):
                raise TimeoutError(f"执行超时: timeout={self.timeout}s")

            self._old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(int(self.timeout))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.timeout > 0:
            import signal

            signal.alarm(0)
            if self._old_handler is not None:
                signal.signal(signal.SIGALRM, self._old_handler)
        return False


# ============================================================================
# 定时器工具
# ============================================================================


class Timer:
    """
    简单计时器

    使用示例：
        timer = Timer(auto_start=True)
        # ... do something ...
        print(f"耗时: {timer.elapsed():.3f}s")

        timer.reset()
        # ... do something else ...
        timer.tick("step1")
        # ... do more ...
        timer.tick("step2")
        print(timer.summary())
    """

    def __init__(self, auto_start: bool = True):
        """
        Args:
            auto_start: 是否自动开始计时
        """
        self._start_time: float = 0
        self._ticks: list[Tuple[str, float]] = []

        if auto_start:
            self.start()

    def start(self) -> None:
        """开始计时"""
        self._start_time = time.monotonic()
        self._ticks = []

    def reset(self) -> None:
        """重置计时器"""
        self.start()

    def elapsed(self) -> float:
        """获取已经过的时间（秒）"""
        if self._start_time == 0:
            return 0
        return time.monotonic() - self._start_time

    def tick(self, name: str = "") -> float:
        """
        记录一个时间点

        Args:
            name: 时间点名称

        Returns:
            从开始到现在的耗时（秒）
        """
        elapsed = self.elapsed()
        self._ticks.append((name or f"tick_{len(self._ticks)}", elapsed))
        return elapsed

    def summary(self) -> str:
        """获取计时摘要"""
        if not self._ticks:
            return f"total: {self.elapsed():.3f}s"

        parts = []
        prev_time = 0
        for name, elapsed in self._ticks:
            delta = elapsed - prev_time
            parts.append(f"{name}: {delta:.3f}s")
            prev_time = elapsed

        parts.append(f"total: {self.elapsed():.3f}s")
        return ", ".join(parts)

    def __str__(self) -> str:
        return self.summary()


# ============================================================================
# 装饰器
# ============================================================================


def with_timeout(timeout: float):
    """
    带超时的异步函数装饰器

    Args:
        timeout: 超时时间（秒）

    使用示例：
        @with_timeout(5.0)
        async def fetch_data(url: str):
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await call_with_timeout(func, *args, timeout=timeout, **kwargs)

        return wrapper

    return decorator


def with_timeout_sync(timeout: float):
    """
    带超时的同步函数装饰器

    Args:
        timeout: 超时时间（秒）

    使用示例：
        @with_timeout_sync(5.0)
        def process_data(data):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return call_with_timeout_sync(func, *args, timeout=timeout, **kwargs)

        return wrapper

    return decorator


def with_retry(
    retry_times: int = 3,
    period: float = 1.0,
):
    """
    简单重试装饰器

    Args:
        retry_times: 重试次数（不包括首次调用）
        period: 重试间隔（秒）

    使用示例：
        @with_retry(retry_times=3, period=1.0)
        async def fetch_data(url: str):
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry(func, period=period, retry_times=retry_times, *args, **kwargs)

        return wrapper

    return decorator


def with_retry_sync(
    retry_times: int = 3,
    period: float = 1.0,
):
    """
    简单同步重试装饰器

    Args:
        retry_times: 重试次数（不包括首次调用）
        period: 重试间隔（秒）

    使用示例：
        @with_retry_sync(retry_times=3, period=1.0)
        def fetch_data(url: str):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return retry_sync(func, period=period, retry_times=retry_times, *args, **kwargs)

        return wrapper

    return decorator
