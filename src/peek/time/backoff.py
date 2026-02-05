"""
指数退避重试模块

移植自 golang/go/time/exponential_backoff.go

功能特性：
- 支持指数退避算法
- 支持随机化因子（jitter）防止惊群效应
- 支持最大重试次数和最大等待时间限制
- 支持同步和异步两种重试模式
- 支持装饰器模式
- 支持自定义重试条件

使用示例：
    # 基础使用
    backoff = ExponentialBackOff()
    result = await backoff.retry_async(async_function, arg1, arg2)
    
    # 使用装饰器
    @retry(max_retries=3, initial_interval=0.5)
    async def my_async_func():
        ...
    
    @retry_sync(max_retries=3)
    def my_sync_func():
        ...
"""

import asyncio
import functools
import logging
import random
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 默认配置常量
DEFAULT_INITIAL_INTERVAL = 0.5  # 500ms
DEFAULT_RANDOMIZATION_FACTOR = 0.5
DEFAULT_MULTIPLIER = 1.5
DEFAULT_MAX_INTERVAL = 60.0  # 60s
DEFAULT_MIN_INTERVAL = 0.5  # 500ms
DEFAULT_MAX_ELAPSED_TIME = 900.0  # 15 minutes
DEFAULT_MAX_ELAPSED_COUNT = -1  # 无限制


@dataclass
class BackOffOptions:
    """指数退避配置选项"""

    # 初始重试间隔（秒）
    initial_interval: float = DEFAULT_INITIAL_INTERVAL
    # 随机化因子，用于计算随机化的重试间隔 [interval - delta, interval + delta]
    # 其中 delta = randomization_factor * interval
    randomization_factor: float = DEFAULT_RANDOMIZATION_FACTOR
    # 倍数，每次重试后间隔乘以此倍数
    multiplier: float = DEFAULT_MULTIPLIER
    # 最大重试间隔（秒）
    max_interval: float = DEFAULT_MAX_INTERVAL
    # 最小重试间隔（秒）
    min_interval: float = DEFAULT_MIN_INTERVAL
    # 最大总等待时间（秒），0 表示不限制
    max_elapsed_time: float = DEFAULT_MAX_ELAPSED_TIME
    # 最大重试次数，-1 表示不限制
    max_elapsed_count: int = DEFAULT_MAX_ELAPSED_COUNT
    # 需要重试的异常类型列表，为空则重试所有异常
    retry_exceptions: Tuple[Type[Exception], ...] = field(default_factory=lambda: (Exception,))
    # 不需要重试的异常类型列表
    ignore_exceptions: Tuple[Type[Exception], ...] = field(default_factory=tuple)
    # 自定义重试条件函数，返回 True 则重试
    retry_condition: Optional[Callable[[Exception], bool]] = None
    # 重试前的回调函数
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
    # 重试成功后的回调函数
    on_success: Optional[Callable[[Any, int], None]] = None
    # 重试失败后的回调函数
    on_failure: Optional[Callable[[Exception, int], None]] = None


class ExponentialBackOff:
    """
    指数退避重试器

    实现了带有随机化因子的指数退避算法，用于网络请求重试等场景。

    算法说明：
    - 每次重试的间隔 = current_interval * multiplier
    - 实际等待时间会添加随机化因子：[interval - delta, interval + delta]
    - 其中 delta = randomization_factor * interval

    使用示例：
        # 创建重试器
        backoff = ExponentialBackOff(
            initial_interval=0.5,
            max_interval=30.0,
            max_elapsed_count=5,
        )

        # 异步重试
        result = await backoff.retry_async(async_request, url, data=payload)

        # 同步重试
        result = backoff.retry_sync(sync_request, url)

        # 手动使用
        while True:
            interval, should_continue = backoff.next_backoff()
            if not should_continue:
                break
            await asyncio.sleep(interval)
            try:
                result = await async_request()
                break
            except Exception:
                pass
    """

    def __init__(
        self,
        initial_interval: float = DEFAULT_INITIAL_INTERVAL,
        randomization_factor: float = DEFAULT_RANDOMIZATION_FACTOR,
        multiplier: float = DEFAULT_MULTIPLIER,
        max_interval: float = DEFAULT_MAX_INTERVAL,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        max_elapsed_time: float = DEFAULT_MAX_ELAPSED_TIME,
        max_elapsed_count: int = DEFAULT_MAX_ELAPSED_COUNT,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        ignore_exceptions: Tuple[Type[Exception], ...] = (),
        retry_condition: Optional[Callable[[Exception], bool]] = None,
        on_retry: Optional[Callable[[Exception, int, float], None]] = None,
        on_success: Optional[Callable[[Any, int], None]] = None,
        on_failure: Optional[Callable[[Exception, int], None]] = None,
    ):
        """
        初始化指数退避重试器

        Args:
            initial_interval: 初始重试间隔（秒），默认 0.5
            randomization_factor: 随机化因子（0-1），默认 0.5
            multiplier: 间隔倍增因子，默认 1.5
            max_interval: 最大重试间隔（秒），默认 60
            min_interval: 最小重试间隔（秒），默认 0.5
            max_elapsed_time: 最大总等待时间（秒），0 表示不限制，默认 900
            max_elapsed_count: 最大重试次数，-1 表示不限制，默认 -1
            retry_exceptions: 需要重试的异常类型元组
            ignore_exceptions: 不需要重试的异常类型元组
            retry_condition: 自定义重试条件函数
            on_retry: 重试前回调函数 (exception, retry_count, wait_time)
            on_success: 成功回调函数 (result, retry_count)
            on_failure: 失败回调函数 (exception, retry_count)
        """
        self.opts = BackOffOptions(
            initial_interval=initial_interval,
            randomization_factor=randomization_factor,
            multiplier=multiplier,
            max_interval=max_interval,
            min_interval=min_interval,
            max_elapsed_time=max_elapsed_time,
            max_elapsed_count=max_elapsed_count,
            retry_exceptions=retry_exceptions,
            ignore_exceptions=ignore_exceptions,
            retry_condition=retry_condition,
            on_retry=on_retry,
            on_success=on_success,
            on_failure=on_failure,
        )

        self._current_interval: float = initial_interval
        self._start_time: float = time.monotonic()
        self._elapsed_count: int = 0

    def reset(self) -> None:
        """重置退避状态，恢复到初始状态"""
        self._current_interval = self.opts.initial_interval
        self._start_time = time.monotonic()
        self._elapsed_count = 0

    def reset_with_interval(self, initial_interval: float) -> None:
        """使用指定的初始间隔重置退避状态"""
        self._current_interval = initial_interval
        self._start_time = time.monotonic()
        self._elapsed_count = 0

    @property
    def current_interval(self) -> float:
        """获取当前重试间隔"""
        return self._current_interval

    @property
    def elapsed_time(self) -> float:
        """获取已经过的总时间（秒）"""
        return time.monotonic() - self._start_time

    @property
    def elapsed_count(self) -> int:
        """获取已重试次数"""
        return self._elapsed_count

    def _get_random_interval(self) -> float:
        """
        获取添加了随机化因子的间隔时间

        返回值在 [interval - delta, interval + delta] 范围内
        其中 delta = randomization_factor * interval
        """
        delta = self.opts.randomization_factor * self._current_interval
        min_interval = self._current_interval - delta
        max_interval = self._current_interval + delta
        return min_interval + random.random() * (max_interval - min_interval)

    def _validate_and_get_next_interval(self) -> Tuple[float, bool]:
        """
        验证是否应该继续重试，并返回下一个间隔

        Returns:
            (interval, should_continue): 间隔时间和是否应该继续重试
        """
        elapsed = self.elapsed_time
        next_interval = self._get_random_interval()

        # 检查是否超过最大等待时间
        if self.opts.max_elapsed_time > 0 and elapsed > self.opts.max_elapsed_time:
            return next_interval, False

        # 检查是否超过最大重试次数
        if self.opts.max_elapsed_count > -1 and self._elapsed_count > self.opts.max_elapsed_count:
            return next_interval, False

        return next_interval, True

    def _increment_current_interval(self) -> None:
        """递增当前间隔（乘以 multiplier）"""
        new_interval = self._current_interval * self.opts.multiplier

        if self.opts.max_interval > 0 and new_interval > self.opts.max_interval:
            self._current_interval = self.opts.max_interval
        elif self.opts.min_interval > 0 and new_interval < self.opts.min_interval:
            self._current_interval = self.opts.min_interval
        else:
            self._current_interval = new_interval

    def _decrement_current_interval(self) -> None:
        """递减当前间隔（除以 multiplier）"""
        new_interval = self._current_interval / self.opts.multiplier

        if self.opts.max_interval > 0 and new_interval > self.opts.max_interval:
            self._current_interval = self.opts.max_interval
        elif self.opts.min_interval > 0 and new_interval < self.opts.min_interval:
            self._current_interval = self.opts.min_interval
        else:
            self._current_interval = new_interval

    def next_backoff(self) -> Tuple[float, bool]:
        """
        获取下一次退避的等待时间（递增模式）

        Returns:
            (wait_time, should_continue): 等待时间（秒）和是否应该继续
        """
        self._elapsed_count += 1
        interval, should_continue = self._validate_and_get_next_interval()

        if should_continue:
            self._increment_current_interval()

        return interval, should_continue

    def pre_backoff(self) -> Tuple[float, bool]:
        """
        获取前一次退避的等待时间（递减模式）

        Returns:
            (wait_time, should_continue): 等待时间（秒）和是否应该继续
        """
        interval, should_continue = self._validate_and_get_next_interval()

        if not should_continue:
            return interval, False

        self._elapsed_count += 1
        self._decrement_current_interval()

        return interval, True

    def _should_retry(self, exc: Exception) -> bool:
        """
        判断是否应该重试

        Args:
            exc: 捕获到的异常

        Returns:
            是否应该重试
        """
        # 检查是否在忽略列表中
        if self.opts.ignore_exceptions and isinstance(exc, self.opts.ignore_exceptions):
            return False

        # 检查自定义重试条件
        if self.opts.retry_condition is not None:
            return self.opts.retry_condition(exc)

        # 检查是否在重试列表中
        if self.opts.retry_exceptions:
            return isinstance(exc, self.opts.retry_exceptions)

        return True

    async def retry_async(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        异步重试执行函数

        Args:
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            最后一次执行的异常
        """
        self.reset()
        last_exception: Optional[Exception] = None

        while True:
            try:
                result = await func(*args, **kwargs)
                # 执行成功回调
                if self.opts.on_success:
                    self.opts.on_success(result, self._elapsed_count)
                return result

            except Exception as e:
                last_exception = e

                # 检查是否应该重试
                if not self._should_retry(e):
                    if self.opts.on_failure:
                        self.opts.on_failure(e, self._elapsed_count)
                    raise

                # 获取下一次退避时间
                wait_time, should_continue = self.next_backoff()

                if not should_continue:
                    logger.warning(
                        f"重试失败，已达到限制: elapsed_count={self._elapsed_count}, "
                        f"elapsed_time={self.elapsed_time:.2f}s, error={e}"
                    )
                    if self.opts.on_failure:
                        self.opts.on_failure(e, self._elapsed_count)
                    raise

                # 执行重试回调
                if self.opts.on_retry:
                    self.opts.on_retry(e, self._elapsed_count, wait_time)

                logger.debug(
                    f"重试中: attempt={self._elapsed_count}, "
                    f"wait={wait_time:.3f}s, error={e}"
                )

                await asyncio.sleep(wait_time)

    def retry_sync(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        同步重试执行函数

        Args:
            func: 要执行的同步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            最后一次执行的异常
        """
        self.reset()
        last_exception: Optional[Exception] = None

        while True:
            try:
                result = func(*args, **kwargs)
                # 执行成功回调
                if self.opts.on_success:
                    self.opts.on_success(result, self._elapsed_count)
                return result

            except Exception as e:
                last_exception = e

                # 检查是否应该重试
                if not self._should_retry(e):
                    if self.opts.on_failure:
                        self.opts.on_failure(e, self._elapsed_count)
                    raise

                # 获取下一次退避时间
                wait_time, should_continue = self.next_backoff()

                if not should_continue:
                    logger.warning(
                        f"重试失败，已达到限制: elapsed_count={self._elapsed_count}, "
                        f"elapsed_time={self.elapsed_time:.2f}s, error={e}"
                    )
                    if self.opts.on_failure:
                        self.opts.on_failure(e, self._elapsed_count)
                    raise

                # 执行重试回调
                if self.opts.on_retry:
                    self.opts.on_retry(e, self._elapsed_count, wait_time)

                logger.debug(
                    f"重试中: attempt={self._elapsed_count}, "
                    f"wait={wait_time:.3f}s, error={e}"
                )

                time.sleep(wait_time)


def retry(
    max_retries: int = 3,
    initial_interval: float = DEFAULT_INITIAL_INTERVAL,
    max_interval: float = DEFAULT_MAX_INTERVAL,
    multiplier: float = DEFAULT_MULTIPLIER,
    randomization_factor: float = DEFAULT_RANDOMIZATION_FACTOR,
    max_elapsed_time: float = DEFAULT_MAX_ELAPSED_TIME,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ignore_exceptions: Tuple[Type[Exception], ...] = (),
    retry_condition: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    on_success: Optional[Callable[[Any, int], None]] = None,
    on_failure: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    异步重试装饰器

    Args:
        max_retries: 最大重试次数
        initial_interval: 初始重试间隔（秒）
        max_interval: 最大重试间隔（秒）
        multiplier: 间隔倍增因子
        randomization_factor: 随机化因子
        max_elapsed_time: 最大总等待时间（秒）
        retry_exceptions: 需要重试的异常类型
        ignore_exceptions: 不需要重试的异常类型
        retry_condition: 自定义重试条件
        on_retry: 重试前回调
        on_success: 成功回调
        on_failure: 失败回调

    Returns:
        装饰后的函数

    使用示例：
        @retry(max_retries=3, initial_interval=0.5)
        async def fetch_data(url: str) -> dict:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return await resp.json()
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            backoff = ExponentialBackOff(
                initial_interval=initial_interval,
                max_interval=max_interval,
                multiplier=multiplier,
                randomization_factor=randomization_factor,
                max_elapsed_time=max_elapsed_time,
                max_elapsed_count=max_retries,
                retry_exceptions=retry_exceptions,
                ignore_exceptions=ignore_exceptions,
                retry_condition=retry_condition,
                on_retry=on_retry,
                on_success=on_success,
                on_failure=on_failure,
            )
            return await backoff.retry_async(func, *args, **kwargs)

        return wrapper

    return decorator


def retry_sync(
    max_retries: int = 3,
    initial_interval: float = DEFAULT_INITIAL_INTERVAL,
    max_interval: float = DEFAULT_MAX_INTERVAL,
    multiplier: float = DEFAULT_MULTIPLIER,
    randomization_factor: float = DEFAULT_RANDOMIZATION_FACTOR,
    max_elapsed_time: float = DEFAULT_MAX_ELAPSED_TIME,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ignore_exceptions: Tuple[Type[Exception], ...] = (),
    retry_condition: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    on_success: Optional[Callable[[Any, int], None]] = None,
    on_failure: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    同步重试装饰器

    Args:
        max_retries: 最大重试次数
        initial_interval: 初始重试间隔（秒）
        max_interval: 最大重试间隔（秒）
        multiplier: 间隔倍增因子
        randomization_factor: 随机化因子
        max_elapsed_time: 最大总等待时间（秒）
        retry_exceptions: 需要重试的异常类型
        ignore_exceptions: 不需要重试的异常类型
        retry_condition: 自定义重试条件
        on_retry: 重试前回调
        on_success: 成功回调
        on_failure: 失败回调

    Returns:
        装饰后的函数

    使用示例：
        @retry_sync(max_retries=3, initial_interval=0.5)
        def fetch_data(url: str) -> dict:
            response = requests.get(url)
            return response.json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            backoff = ExponentialBackOff(
                initial_interval=initial_interval,
                max_interval=max_interval,
                multiplier=multiplier,
                randomization_factor=randomization_factor,
                max_elapsed_time=max_elapsed_time,
                max_elapsed_count=max_retries,
                retry_exceptions=retry_exceptions,
                ignore_exceptions=ignore_exceptions,
                retry_condition=retry_condition,
                on_retry=on_retry,
                on_success=on_success,
                on_failure=on_failure,
            )
            return backoff.retry_sync(func, *args, **kwargs)

        return wrapper

    return decorator


# 便捷函数
async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    initial_interval: float = DEFAULT_INITIAL_INTERVAL,
    max_interval: float = DEFAULT_MAX_INTERVAL,
    **kwargs: Any,
) -> T:
    """
    使用指数退避重试异步函数的便捷函数

    Args:
        func: 要重试的异步函数
        *args: 传递给函数的位置参数
        max_retries: 最大重试次数
        initial_interval: 初始重试间隔
        max_interval: 最大重试间隔
        **kwargs: 传递给函数的关键字参数

    Returns:
        函数执行结果

    使用示例：
        result = await retry_with_backoff(
            fetch_data,
            "https://api.example.com",
            max_retries=5,
            initial_interval=1.0,
        )
    """
    backoff = ExponentialBackOff(
        initial_interval=initial_interval,
        max_interval=max_interval,
        max_elapsed_count=max_retries,
    )
    return await backoff.retry_async(func, *args, **kwargs)


def retry_with_backoff_sync(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    initial_interval: float = DEFAULT_INITIAL_INTERVAL,
    max_interval: float = DEFAULT_MAX_INTERVAL,
    **kwargs: Any,
) -> T:
    """
    使用指数退避重试同步函数的便捷函数

    Args:
        func: 要重试的同步函数
        *args: 传递给函数的位置参数
        max_retries: 最大重试次数
        initial_interval: 初始重试间隔
        max_interval: 最大重试间隔
        **kwargs: 传递给函数的关键字参数

    Returns:
        函数执行结果

    使用示例：
        result = retry_with_backoff_sync(
            requests.get,
            "https://api.example.com",
            max_retries=5,
            initial_interval=1.0,
        )
    """
    backoff = ExponentialBackOff(
        initial_interval=initial_interval,
        max_interval=max_interval,
        max_elapsed_count=max_retries,
    )
    return backoff.retry_sync(func, *args, **kwargs)
