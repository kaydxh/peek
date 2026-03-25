import logging
import time
import threading
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class ExecutionStats:
    """执行统计信息"""
    total_calls: int = 0
    total_duration: float = 0.0
    average_call_time: float = 0.0
    target_duration: float = 0.0
    actual_duration: float = 0.0
    efficiency: float = 0.0  # 实际运行时间 / 目标时间的比例


class FunctionDurationController:
    """函数运行时长控制器"""

    def __init__(self):
        self.is_running = False
        self.stats = ExecutionStats()
        self.call_times: List[float] = []
        self.results: List[Any] = []

    def run_for_duration(self,
                         func: Callable,
                         target_duration: float,
                         *args,
                         **kwargs) -> ExecutionStats:
        """
        运行函数直到达到指定的总时长

        Args:
            func: 要执行的函数
            target_duration: 目标运行时长（秒）
            *args, **kwargs: 传递给函数的参数

        Returns:
            ExecutionStats: 执行统计信息
        """
        self._reset_stats()
        self.stats.target_duration = target_duration

        start_time = time.time()
        self.is_running = True

        logger.info("Starting function execution, target duration: %ss", target_duration)
        logger.info("Start time: %s", datetime.now().strftime('%H:%M:%S'))
        logger.info("-" * 50)

        try:
            while self.is_running:
                current_time = time.time()
                elapsed = current_time - start_time

                # 检查是否达到目标时长
                if elapsed >= target_duration:
                    break

                # 执行函数
                call_start = time.time()
                result = func(*args, **kwargs)
                call_end = time.time()

                # 记录统计信息
                call_duration = call_end - call_start
                self.call_times.append(call_duration)
                self.results.append(result)
                self.stats.total_calls += 1

                # 实时显示进度
                self._display_progress(elapsed, target_duration, call_duration)

        except KeyboardInterrupt:
            logger.info("Execution interrupted by user")
            self.is_running = False

        # 计算最终统计信息
        self._calculate_final_stats(time.time() - start_time)
        self._display_final_stats()

        return self.stats

    def run_for_duration_with_adaptive_timing(self,
                                              func: Callable,
                                              target_duration: float,
                                              estimated_call_time: float = 0.1,
                                              *args,
                                              **kwargs) -> ExecutionStats:
        """
        智能运行函数，根据实际执行时间自适应调整

        Args:
            func: 要执行的函数
            target_duration: 目标运行时长（秒）
            estimated_call_time: 预估的单次调用时间（秒）
            *args, **kwargs: 传递给函数的参数
        """
        self._reset_stats()
        self.stats.target_duration = target_duration

        start_time = time.time()
        self.is_running = True

        # 预估需要的调用次数
        estimated_calls = int(target_duration / estimated_call_time)

        logger.info("Smart execution mode")
        logger.info("Target duration: %ss", target_duration)
        logger.info("Estimated call time: %ss", estimated_call_time)
        logger.info("Estimated call count: %s", estimated_calls)
        logger.info("Start time: %s", datetime.now().strftime('%H:%M:%S'))
        logger.info("-" * 50)

        try:
            while self.is_running:
                current_time = time.time()
                elapsed = current_time - start_time
                remaining_time = target_duration - elapsed

                # 如果剩余时间不足，退出
                if remaining_time <= 0:
                    break

                # 根据历史数据调整预期
                if self.call_times:
                    avg_call_time = sum(self.call_times) / len(self.call_times)
                    # 如果剩余时间不足以完成下一次调用，退出
                    if remaining_time < avg_call_time * 1.1:  # 留10%缓冲
                        break

                # 执行函数
                call_start = time.time()
                result = func(*args, **kwargs)
                call_end = time.time()

                # 记录统计信息
                call_duration = call_end - call_start
                self.call_times.append(call_duration)
                self.results.append(result)
                self.stats.total_calls += 1

                # 实时显示进度
                self._display_adaptive_progress(elapsed, target_duration, call_duration)

        except KeyboardInterrupt:
            logger.info("Execution interrupted by user")
            self.is_running = False

        # 计算最终统计信息
        self._calculate_final_stats(time.time() - start_time)
        self._display_final_stats()

        return self.stats

    def run_with_call_count(self,
                            func: Callable,
                            call_count: int,
                            *args,
                            **kwargs) -> ExecutionStats:
        """
        执行函数指定的次数

        Args:
            func: 要执行的函数
            call_count: 调用次数
            *args, **kwargs: 传递给函数的参数
        """
        self._reset_stats()

        start_time = time.time()
        self.is_running = True

        logger.info("Executing function %d times", call_count)
        logger.info("Start time: %s", datetime.now().strftime('%H:%M:%S'))
        logger.info("-" * 50)

        try:
            for i in range(call_count):
                if not self.is_running:
                    break

                # 执行函数
                call_start = time.time()
                result = func(*args, **kwargs)
                call_end = time.time()

                # 记录统计信息
                call_duration = call_end - call_start
                self.call_times.append(call_duration)
                self.results.append(result)
                self.stats.total_calls += 1

                # 显示进度
                progress = (i + 1) / call_count * 100
                elapsed = time.time() - start_time
                eta = elapsed / (i + 1) * (call_count - i - 1) if i > 0 else 0

                logger.info(
                    "Progress: %d/%d (%.1f%%) | Call time: %.3fs | Elapsed: %.1fs | ETA: %.1fs",
                    i + 1, call_count, progress, call_duration, elapsed, eta,
                )

        except KeyboardInterrupt:
            logger.info("Execution interrupted by user")
            self.is_running = False

        # 计算最终统计信息
        self._calculate_final_stats(time.time() - start_time)
        self._display_final_stats()

        return self.stats

    def stop(self):
        """停止执行"""
        self.is_running = False

    def _reset_stats(self):
        """重置统计信息"""
        self.stats = ExecutionStats()
        self.call_times.clear()
        self.results.clear()

    def _display_progress(self, elapsed: float, target: float, call_time: float):
        """显示实时进度"""
        progress = (elapsed / target) * 100
        avg_time = sum(self.call_times) / len(self.call_times)
        estimated_total_calls = int(target / avg_time)

        logger.info("Progress: %.1f%% | Calls: %d | Elapsed: %.1fs | Call time: %.3fs | Avg: %.3fs | Est. total: %d",
            progress, self.stats.total_calls, elapsed, call_time, avg_time, estimated_total_calls,
        )

    def _display_adaptive_progress(self, elapsed: float, target: float, call_time: float):
        """显示自适应进度"""
        progress = (elapsed / target) * 100
        remaining = target - elapsed
        avg_time = sum(self.call_times) / len(self.call_times)
        estimated_remaining_calls = int(remaining / avg_time) if avg_time > 0 else 0

        logger.info("Progress: %.1f%% | Calls: %d | Elapsed: %.1fs | Remaining: %.1fs | Call time: %.3fs | Est. remaining: %d",
            progress, self.stats.total_calls, elapsed, remaining, call_time, estimated_remaining_calls,
        )

    def _calculate_final_stats(self, total_duration: float):
        """计算最终统计信息"""
        self.stats.actual_duration = total_duration
        self.stats.total_duration = sum(self.call_times)

        if self.stats.total_calls > 0:
            self.stats.average_call_time = self.stats.total_duration / self.stats.total_calls

        if self.stats.target_duration > 0:
            self.stats.efficiency = (self.stats.actual_duration / self.stats.target_duration) * 100

    def _display_final_stats(self):
        """显示最终统计信息"""
        logger.info("=" * 50)
        logger.info("Execution completed! Statistics:")
        logger.info("Total calls: %d", self.stats.total_calls)
        logger.info("Target duration: %.2fs", self.stats.target_duration)
        logger.info("Actual duration: %.2fs", self.stats.actual_duration)
        logger.info("Pure execution time: %.2fs", self.stats.total_duration)
        logger.info("Average call time: %.3fs", self.stats.average_call_time)
        logger.info("Time utilization: %.1f%%", self.stats.efficiency)

        if self.call_times:
            logger.info("Fastest call: %.3fs", min(self.call_times))
            logger.info("Slowest call: %.3fs", max(self.call_times))

        logger.info("End time: %s", datetime.now().strftime('%H:%M:%S'))
        logger.info("=" * 50)


# 示例函数
def sample_function_100ms(task_id: int = 0) -> str:
    """模拟耗时100ms的函数"""
    time.sleep(0.1)  # 模拟100ms的工作
    return f"Task {task_id} completed at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}"


def variable_time_function(base_time: float = 0.1, variance: float = 0.02) -> str:
    """模拟执行时间有变化的函数"""
    import random
    actual_time = base_time + random.uniform(-variance, variance)
    time.sleep(max(0.01, actual_time))  # 确保至少10ms
    return f"Variable task completed in {actual_time:.3f}s"


def cpu_intensive_function(iterations: int = 100000) -> int:
    """CPU密集型函数"""
    result = 0
    for i in range(iterations):
        result += i * i
    return result


def threaded_controller_demo():
    """演示多线程控制"""
    controller = FunctionDurationController()

    def run_in_thread():
        logger.info("Running in background thread...")
        return controller.run_for_duration(sample_function_100ms, 10)

    # 启动后台线程
    thread = threading.Thread(target=run_in_thread)
    thread.start()

    # 主线程可以做其他事情
    time.sleep(5)
    logger.info("Main thread: stopping background execution after 5s")
    controller.stop()

    thread.join()
    logger.info("Background thread stopped")


def main():
    """主函数 - 演示各种用法"""
    controller = FunctionDurationController()

    logger.info("=== Function Duration Controller Demo ===\n")

    # 示例1: 运行60秒（约600次调用）
    logger.info("1. Run function for 60s (expected ~600 calls):")
    stats1 = controller.run_for_duration(sample_function_100ms, 5)  # 为了演示，改为5秒
    logger.info()

    # 示例2: 智能自适应运行
    logger.info("2. Smart adaptive run (10s):")
    stats2 = controller.run_for_duration_with_adaptive_timing(
        variable_time_function, 3, 0.1  # 为了演示，改为3秒
    )
    logger.info()

    # 示例3: 指定调用次数
    logger.info("3. Run specified count (50 times):")
    stats3 = controller.run_with_call_count(sample_function_100ms, 10)  # 为了演示，改为10次
    logger.info()

    # 示例4: CPU密集型任务
    logger.info("4. CPU-intensive task (5s):")
    stats4 = controller.run_for_duration(cpu_intensive_function, 2, 50000)  # 为了演示，改为2秒
    logger.info()

    # 示例5: 多线程控制演示
    logger.info("5. Multi-thread control demo:")
    threaded_controller_demo()

    logger.info("\n=== Demo completed ===")


# 高级功能
class AdvancedDurationController(FunctionDurationController):
    """高级时长控制器"""

    def __init__(self):
        super().__init__()
        self.performance_log: List[Dict] = []

    def run_with_performance_monitoring(self,
                                        func: Callable,
                                        target_duration: float,
                                        log_interval: int = 100,
                                        *args, **kwargs) -> ExecutionStats:
        """带性能监控的运行"""
        self._reset_stats()
        self.stats.target_duration = target_duration

        start_time = time.time()
        self.is_running = True

        logger.info("Performance monitoring mode - target duration: %ss", target_duration)
        logger.info("-" * 50)

        try:
            while self.is_running:
                current_time = time.time()
                elapsed = current_time - start_time

                if elapsed >= target_duration:
                    break

                # 执行函数
                call_start = time.time()
                result = func(*args, **kwargs)
                call_end = time.time()

                call_duration = call_end - call_start
                self.call_times.append(call_duration)
                self.results.append(result)
                self.stats.total_calls += 1

                # 记录性能日志
                if self.stats.total_calls % log_interval == 0:
                    self._log_performance(elapsed, call_duration)

                # 显示进度
                if self.stats.total_calls % 50 == 0:  # 每50次显示一次
                    self._display_progress(elapsed, target_duration, call_duration)

        except KeyboardInterrupt:
            logger.info("Execution interrupted by user")
            self.is_running = False

        self._calculate_final_stats(time.time() - start_time)
        self._display_performance_summary()
        self._display_final_stats()

        return self.stats

    def _log_performance(self, elapsed: float, call_duration: float):
        """记录性能日志"""
        recent_calls = self.call_times[-100:] if len(self.call_times) >= 100 else self.call_times
        avg_recent = sum(recent_calls) / len(recent_calls)

        self.performance_log.append({
            'timestamp': elapsed,
            'total_calls': self.stats.total_calls,
            'current_call_time': call_duration,
            'recent_avg_time': avg_recent,
            'calls_per_second': self.stats.total_calls / elapsed if elapsed > 0 else 0
        })

    def _display_performance_summary(self):
        """显示性能摘要"""
        if not self.performance_log:
            return

        logger.info("Performance summary:")
        logger.info("Timestamp\t\tCalls\t\tQPS\t\tRecent avg time")
        logger.info("-" * 60)

        for log_entry in self.performance_log[-5:]:  # 显示最后5个记录点
            logger.info(
                "%.1fs\t\t%d\t\t%.1f\t\t%.3fs",
                log_entry['timestamp'], log_entry['total_calls'],
                log_entry['calls_per_second'], log_entry['recent_avg_time'],
            )


if __name__ == "__main__":
    # 基础演示
    main() 

    # 高级功能演示
    logger.info("\n\n=== Advanced features demo ===")
    advanced_controller = AdvancedDurationController()
    advanced_controller.run_with_performance_monitoring(
        sample_function_100ms, 3, log_interval=25
    )