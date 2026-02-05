"""
Wait/Retry 工具模块测试
"""

import asyncio
import time
import pytest

from peek.time.wait import (
    # 异常类
    TimeoutError,
    ConditionNotMetError,
    MaxRetriesExceededError,
    WaitCancelledError,
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
    # 重试
    retry,
    retry_sync,
    # 等待工具
    wait_for_condition,
    wait_for_condition_sync,
    sleep_with_jitter,
    sleep_with_jitter_sync,
    # 计时器
    Timer,
    # 装饰器
    with_timeout,
    with_timeout_sync,
    with_retry,
    with_retry_sync,
)
from peek.time.backoff import ExponentialBackOff


class TestCallWithTimeout:
    """带超时调用测试"""

    @pytest.mark.asyncio
    async def test_success_within_timeout(self):
        """测试在超时内成功完成"""

        async def quick_func():
            await asyncio.sleep(0.01)
            return "done"

        result = await call_with_timeout(quick_func, timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        """测试超时"""

        async def slow_func():
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(TimeoutError):
            await call_with_timeout(slow_func, timeout=0.05)

    @pytest.mark.asyncio
    async def test_no_timeout(self):
        """测试不设置超时"""

        async def func():
            return "done"

        # timeout=0 表示不超时
        result = await call_with_timeout(func, timeout=0)
        assert result == "done"

    def test_sync_success(self):
        """测试同步版本成功"""

        def quick_func():
            time.sleep(0.01)
            return "done"

        result = call_with_timeout_sync(quick_func, timeout=1.0)
        assert result == "done"

    def test_sync_timeout(self):
        """测试同步版本超时"""

        def slow_func():
            time.sleep(1.0)
            return "done"

        with pytest.raises(TimeoutError):
            call_with_timeout_sync(slow_func, timeout=0.05)


class TestPoll:
    """条件轮询测试"""

    @pytest.mark.asyncio
    async def test_condition_met_immediately(self):
        """测试条件立即满足"""

        async def always_true():
            return True, "result"

        result = await poll_immediate(always_true, interval=0.1, timeout=1.0)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_condition_met_after_retries(self):
        """测试重试后条件满足"""
        counter = {"value": 0}

        async def eventually_true():
            counter["value"] += 1
            if counter["value"] >= 3:
                return True, "success"
            return False, None

        result = await poll_immediate(eventually_true, interval=0.01, timeout=1.0)
        assert result == "success"
        assert counter["value"] == 3

    @pytest.mark.asyncio
    async def test_timeout(self):
        """测试轮询超时"""

        async def never_true():
            return False, None

        with pytest.raises(TimeoutError):
            await poll_immediate(never_true, interval=0.01, timeout=0.05)

    @pytest.mark.asyncio
    async def test_poll_without_immediate(self):
        """测试非立即执行的轮询"""
        start = time.monotonic()

        async def condition():
            return True, "done"

        result = await poll(condition, interval=0.05, timeout=1.0)
        elapsed = time.monotonic() - start

        assert result == "done"
        # poll 会先等待 interval 再检查
        assert elapsed >= 0.05


class TestRetry:
    """重试测试"""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """测试第一次就成功"""

        async def success():
            return "done"

        result = await retry(success, period=0.01, retry_times=3)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        """测试重试后成功"""
        counter = {"value": 0}

        async def eventually_success():
            counter["value"] += 1
            if counter["value"] < 3:
                raise ValueError("Not yet")
            return "success"

        result = await retry(eventually_success, period=0.01, retry_times=5)
        assert result == "success"
        assert counter["value"] == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """测试超过最大重试次数"""

        async def always_fail():
            raise ValueError("Always fails")

        with pytest.raises(MaxRetriesExceededError):
            await retry(always_fail, period=0.01, retry_times=2)

    def test_sync_success(self):
        """测试同步重试成功"""
        counter = {"value": 0}

        def eventually_success():
            counter["value"] += 1
            if counter["value"] < 2:
                raise ValueError("Not yet")
            return "success"

        result = retry_sync(eventually_success, period=0.01, retry_times=3)
        assert result == "success"

    def test_sync_max_retries(self):
        """测试同步重试次数限制"""

        def always_fail():
            raise ValueError("Always fails")

        with pytest.raises(MaxRetriesExceededError):
            retry_sync(always_fail, period=0.01, retry_times=2)


class TestWaitForCondition:
    """等待条件测试"""

    @pytest.mark.asyncio
    async def test_condition_met(self):
        """测试条件满足"""
        counter = {"value": 0}

        async def condition():
            counter["value"] += 1
            return counter["value"] >= 3

        await wait_for_condition(condition, timeout=1.0, interval=0.01)
        assert counter["value"] >= 3

    @pytest.mark.asyncio
    async def test_timeout_with_message(self):
        """测试超时带自定义消息"""

        async def never_true():
            return False

        with pytest.raises(TimeoutError) as exc_info:
            await wait_for_condition(
                never_true,
                timeout=0.05,
                interval=0.01,
                message="自定义超时消息",
            )

        assert "自定义超时消息" in str(exc_info.value)

    def test_sync_condition_met(self):
        """测试同步等待条件满足"""
        counter = {"value": 0}

        def condition():
            counter["value"] += 1
            return counter["value"] >= 3

        wait_for_condition_sync(condition, timeout=1.0, interval=0.01)
        assert counter["value"] >= 3


class TestSleepWithJitter:
    """带抖动睡眠测试"""

    @pytest.mark.asyncio
    async def test_jitter_range(self):
        """测试抖动范围"""
        durations = []

        for _ in range(10):
            start = time.monotonic()
            await sleep_with_jitter(0.05, jitter_factor=0.5)
            durations.append(time.monotonic() - start)

        # 检查有变化（有抖动）
        assert len(set(int(d * 1000) for d in durations)) > 1

        # 检查都在合理范围内 [0.025, 0.075]
        for d in durations:
            assert 0.02 <= d <= 0.1  # 留一些误差

    def test_sync_jitter(self):
        """测试同步版本"""
        start = time.monotonic()
        sleep_with_jitter_sync(0.05, jitter_factor=0.1)
        elapsed = time.monotonic() - start

        # 应该在 [0.045, 0.055] 范围内，但留一些误差
        assert 0.04 <= elapsed <= 0.07


class TestTimer:
    """计时器测试"""

    def test_elapsed(self):
        """测试耗时计算"""
        timer = Timer(auto_start=True)
        time.sleep(0.05)
        elapsed = timer.elapsed()

        assert 0.04 <= elapsed <= 0.1

    def test_tick(self):
        """测试时间点记录"""
        timer = Timer()

        time.sleep(0.02)
        t1 = timer.tick("step1")
        assert t1 >= 0.02

        time.sleep(0.02)
        t2 = timer.tick("step2")
        assert t2 >= t1

    def test_summary(self):
        """测试摘要"""
        timer = Timer()

        time.sleep(0.01)
        timer.tick("step1")

        time.sleep(0.01)
        timer.tick("step2")

        summary = timer.summary()
        assert "step1" in summary
        assert "step2" in summary
        assert "total" in summary

    def test_reset(self):
        """测试重置"""
        timer = Timer()
        time.sleep(0.05)
        timer.tick("before")

        timer.reset()
        elapsed = timer.elapsed()

        assert elapsed < 0.01


class TestDecorators:
    """装饰器测试"""

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """测试超时装饰器成功"""

        @with_timeout(1.0)
        async def quick_func():
            await asyncio.sleep(0.01)
            return "done"

        result = await quick_func()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_with_timeout_exceeded(self):
        """测试超时装饰器超时"""

        @with_timeout(0.05)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(TimeoutError):
            await slow_func()

    def test_with_timeout_sync(self):
        """测试同步超时装饰器"""

        @with_timeout_sync(1.0)
        def quick_func():
            time.sleep(0.01)
            return "done"

        result = quick_func()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_with_retry_success(self):
        """测试重试装饰器成功"""
        counter = {"value": 0}

        @with_retry(retry_times=3, period=0.01)
        async def eventually_success():
            counter["value"] += 1
            if counter["value"] < 2:
                raise ValueError("Not yet")
            return "done"

        result = await eventually_success()
        assert result == "done"
        assert counter["value"] == 2

    def test_with_retry_sync(self):
        """测试同步重试装饰器"""
        counter = {"value": 0}

        @with_retry_sync(retry_times=3, period=0.01)
        def eventually_success():
            counter["value"] += 1
            if counter["value"] < 2:
                raise ValueError("Not yet")
            return "done"

        result = eventually_success()
        assert result == "done"
        assert counter["value"] == 2


class TestBackoffUntil:
    """带退避策略的循环执行测试"""

    @pytest.mark.asyncio
    async def test_loop_until_timeout(self):
        """测试循环直到超时"""
        counter = {"value": 0}

        async def increment():
            counter["value"] += 1

        backoff = ExponentialBackOff(
            initial_interval=0.01,
            max_elapsed_time=0.1,
            max_elapsed_count=-1,
        )

        with pytest.raises(MaxRetriesExceededError):
            await backoff_until(increment, backoff, loop=True)

        # 应该执行了多次
        assert counter["value"] > 1

    @pytest.mark.asyncio
    async def test_loop_false_return_on_success(self):
        """测试 loop=False 成功时返回"""
        counter = {"value": 0}

        async def eventually_success():
            counter["value"] += 1
            if counter["value"] < 3:
                raise ValueError("Not yet")
            return "done"

        backoff = ExponentialBackOff(
            initial_interval=0.01,
            max_elapsed_count=5,
        )

        result = await backoff_until(eventually_success, backoff, loop=False)
        assert result == "done"
        assert counter["value"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
