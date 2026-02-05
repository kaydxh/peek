"""
指数退避重试模块测试
"""

import asyncio
import time
import pytest

from peek.time.backoff import (
    ExponentialBackOff,
    retry,
    retry_sync,
    retry_with_backoff,
    retry_with_backoff_sync,
)


class TestExponentialBackOff:
    """ExponentialBackOff 类测试"""

    def test_default_values(self):
        """测试默认值"""
        backoff = ExponentialBackOff()
        assert backoff.opts.initial_interval == 0.5
        assert backoff.opts.multiplier == 1.5
        assert backoff.opts.randomization_factor == 0.5
        assert backoff.opts.max_interval == 60.0
        assert backoff.opts.max_elapsed_time == 900.0
        assert backoff.opts.max_elapsed_count == -1

    def test_custom_values(self):
        """测试自定义值"""
        backoff = ExponentialBackOff(
            initial_interval=1.0,
            multiplier=2.0,
            max_interval=30.0,
            max_elapsed_count=5,
        )
        assert backoff.opts.initial_interval == 1.0
        assert backoff.opts.multiplier == 2.0
        assert backoff.opts.max_interval == 30.0
        assert backoff.opts.max_elapsed_count == 5

    def test_next_backoff_interval_increases(self):
        """测试间隔递增"""
        backoff = ExponentialBackOff(
            initial_interval=1.0,
            multiplier=2.0,
            randomization_factor=0,  # 关闭随机化便于测试
            max_elapsed_count=10,
        )

        # 第一次
        interval1, _ = backoff.next_backoff()
        assert interval1 == 1.0

        # 第二次应该是 2.0
        interval2, _ = backoff.next_backoff()
        assert interval2 == 2.0

        # 第三次应该是 4.0
        interval3, _ = backoff.next_backoff()
        assert interval3 == 4.0

    def test_max_interval_limit(self):
        """测试最大间隔限制"""
        backoff = ExponentialBackOff(
            initial_interval=10.0,
            multiplier=2.0,
            randomization_factor=0,
            max_interval=15.0,
            max_elapsed_count=10,
        )

        # 第一次
        interval1, _ = backoff.next_backoff()
        assert interval1 == 10.0

        # 第二次应该被限制在 15.0
        interval2, _ = backoff.next_backoff()
        assert interval2 == 15.0

    def test_max_elapsed_count(self):
        """测试最大重试次数"""
        backoff = ExponentialBackOff(
            initial_interval=0.01,
            max_elapsed_count=3,
        )

        # 应该能重试 3 次
        for i in range(3):
            _, should_continue = backoff.next_backoff()
            assert should_continue, f"第 {i+1} 次应该继续"

        # 第 4 次应该停止
        _, should_continue = backoff.next_backoff()
        assert not should_continue, "超过最大次数应该停止"

    def test_reset(self):
        """测试重置功能"""
        backoff = ExponentialBackOff(
            initial_interval=1.0,
            randomization_factor=0,
            max_elapsed_count=10,
        )

        # 执行几次
        backoff.next_backoff()
        backoff.next_backoff()

        assert backoff.elapsed_count == 2

        # 重置
        backoff.reset()

        assert backoff.elapsed_count == 0
        assert backoff.current_interval == 1.0

    def test_randomization(self):
        """测试随机化因子"""
        backoff = ExponentialBackOff(
            initial_interval=1.0,
            randomization_factor=0.5,
            max_elapsed_count=100,
        )

        intervals = [backoff.next_backoff()[0] for _ in range(10)]

        # 检查间隔不完全相同（有随机性）
        unique_intervals = set(intervals)
        assert len(unique_intervals) > 1, "应该有随机性"

        # 检查第一个间隔在合理范围内（基于 initial_interval=1.0, randomization_factor=0.5）
        # 范围应该是 [0.5, 1.5]
        # 注意：由于 next_backoff 会递增间隔，只能验证第一个
        first_interval = intervals[0]
        assert 0.5 <= first_interval <= 1.5, f"第一个间隔应在 [0.5, 1.5] 范围内，实际值: {first_interval}"


class TestRetryAsync:
    """异步重试测试"""

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        """测试第一次就成功"""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        backoff = ExponentialBackOff(max_elapsed_count=3)
        result = await backoff.retry_async(success_func)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """测试失败几次后成功"""
        call_count = 0

        async def eventually_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        backoff = ExponentialBackOff(
            initial_interval=0.01,
            max_elapsed_count=5,
        )
        result = await backoff.retry_async(eventually_success)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_all_failures(self):
        """测试所有重试都失败"""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        backoff = ExponentialBackOff(
            initial_interval=0.01,
            max_elapsed_count=3,
        )

        with pytest.raises(ValueError, match="Always fails"):
            await backoff.retry_async(always_fail)

        assert call_count == 4  # 1 次初始 + 3 次重试

    @pytest.mark.asyncio
    async def test_retry_ignore_exceptions(self):
        """测试忽略特定异常不重试"""

        async def raise_type_error():
            raise TypeError("Should not retry")

        backoff = ExponentialBackOff(
            initial_interval=0.01,
            max_elapsed_count=3,
            ignore_exceptions=(TypeError,),
        )

        with pytest.raises(TypeError):
            await backoff.retry_async(raise_type_error)

    @pytest.mark.asyncio
    async def test_retry_with_callbacks(self):
        """测试回调函数"""
        retry_calls = []
        success_calls = []

        def on_retry(exc, count, wait):
            retry_calls.append((exc, count, wait))

        def on_success(result, count):
            success_calls.append((result, count))

        call_count = 0

        async def eventually_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return "done"

        backoff = ExponentialBackOff(
            initial_interval=0.01,
            max_elapsed_count=5,
            on_retry=on_retry,
            on_success=on_success,
        )
        result = await backoff.retry_async(eventually_success)

        assert result == "done"
        assert len(retry_calls) == 1
        assert len(success_calls) == 1
        assert success_calls[0][0] == "done"


class TestRetryDecorator:
    """装饰器测试"""

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        """测试异步装饰器"""
        call_count = 0

        @retry(max_retries=3, initial_interval=0.01)
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return "decorated"

        result = await decorated_func()
        assert result == "decorated"
        assert call_count == 2

    def test_sync_decorator(self):
        """测试同步装饰器"""
        call_count = 0

        @retry_sync(max_retries=3, initial_interval=0.01)
        def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return "decorated"

        result = decorated_func()
        assert result == "decorated"
        assert call_count == 2


class TestConvenienceFunctions:
    """便捷函数测试"""

    @pytest.mark.asyncio
    async def test_retry_with_backoff(self):
        """测试异步便捷函数"""
        call_count = 0

        async def my_func(x):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return x * 2

        result = await retry_with_backoff(
            my_func,
            5,
            max_retries=3,
            initial_interval=0.01,
        )
        assert result == 10
        assert call_count == 2

    def test_retry_with_backoff_sync(self):
        """测试同步便捷函数"""
        call_count = 0

        def my_func(x):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return x * 2

        result = retry_with_backoff_sync(
            my_func,
            5,
            max_retries=3,
            initial_interval=0.01,
        )
        assert result == 10
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
