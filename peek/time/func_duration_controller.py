import time
import threading
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta

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

        print(f"开始执行函数，目标运行时长: {target_duration}秒")
        print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 50)

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
            print("\n用户中断执行")
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

        print(f"智能执行模式")
        print(f"目标运行时长: {target_duration}秒")
        print(f"预估单次调用时间: {estimated_call_time}秒")
        print(f"预估需要调用次数: {estimated_calls}次")
        print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 50)

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
            print("\n用户中断执行")
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

        print(f"执行函数 {call_count} 次")
        print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 50)

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

                print(f"进度: {i + 1}/{call_count} ({progress:.1f}%) | "
                      f"本次耗时: {call_duration:.3f}s | "
                      f"已用时: {elapsed:.1f}s | "
                      f"预计剩余: {eta:.1f}s")

        except KeyboardInterrupt:
            print("\n用户中断执行")
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

        print(f"进度: {progress:.1f}% | "
              f"已执行: {self.stats.total_calls}次 | "
              f"已用时: {elapsed:.1f}s | "
              f"本次耗时: {call_time:.3f}s | "
              f"平均耗时: {avg_time:.3f}s | "
              f"预计总次数: {estimated_total_calls}")

    def _display_adaptive_progress(self, elapsed: float, target: float, call_time: float):
        """显示自适应进度"""
        progress = (elapsed / target) * 100
        remaining = target - elapsed
        avg_time = sum(self.call_times) / len(self.call_times)
        estimated_remaining_calls = int(remaining / avg_time) if avg_time > 0 else 0

        print(f"进度: {progress:.1f}% | "
              f"已执行: {self.stats.total_calls}次 | "
              f"已用时: {elapsed:.1f}s | "
              f"剩余时间: {remaining:.1f}s | "
              f"本次耗时: {call_time:.3f}s | "
              f"预计还需: {estimated_remaining_calls}次")

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
        print("\n" + "=" * 50)
        print("执行完成！统计信息：")
        print(f"总调用次数: {self.stats.total_calls}")
        print(f"目标运行时长: {self.stats.target_duration:.2f}秒")
        print(f"实际运行时长: {self.stats.actual_duration:.2f}秒")
        print(f"纯函数执行时长: {self.stats.total_duration:.2f}秒")
        print(f"平均单次调用时间: {self.stats.average_call_time:.3f}秒")
        print(f"时间利用率: {self.stats.efficiency:.1f}%")

        if self.call_times:
            print(f"最快调用时间: {min(self.call_times):.3f}秒")
            print(f"最慢调用时间: {max(self.call_times):.3f}秒")

        print(f"结束时间: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 50)


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
        print("在后台线程中运行...")
        return controller.run_for_duration(sample_function_100ms, 10)

    # 启动后台线程
    thread = threading.Thread(target=run_in_thread)
    thread.start()

    # 主线程可以做其他事情
    time.sleep(5)
    print("主线程：5秒后停止后台执行")
    controller.stop()

    thread.join()
    print("后台线程已停止")


def main():
    """主函数 - 演示各种用法"""
    controller = FunctionDurationController()

    print("=== 函数运行时长控制器演示 ===\n")

    # 示例1: 运行60秒（约600次调用）
    print("1. 运行函数60秒（预期约600次调用）:")
    stats1 = controller.run_for_duration(sample_function_100ms, 5)  # 为了演示，改为5秒
    print()

    # 示例2: 智能自适应运行
    print("2. 智能自适应运行（10秒）:")
    stats2 = controller.run_for_duration_with_adaptive_timing(
        variable_time_function, 3, 0.1  # 为了演示，改为3秒
    )
    print()

    # 示例3: 指定调用次数
    print("3. 执行指定次数（50次）:")
    stats3 = controller.run_with_call_count(sample_function_100ms, 10)  # 为了演示，改为10次
    print()

    # 示例4: CPU密集型任务
    print("4. CPU密集型任务（5秒）:")
    stats4 = controller.run_for_duration(cpu_intensive_function, 2, 50000)  # 为了演示，改为2秒
    print()

    # 示例5: 多线程控制演示
    print("5. 多线程控制演示:")
    threaded_controller_demo()

    print("\n=== 演示完成 ===")


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

        print(f"性能监控模式 - 目标时长: {target_duration}秒")
        print("-" * 50)

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
            print("\n用户中断执行")
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

        print("\n性能摘要:")
        print("时间点\t\t调用次数\t每秒调用数\t最近平均耗时")
        print("-" * 60)

        for log in self.performance_log[-5:]:  # 显示最后5个记录点
            print(f"{log['timestamp']:.1f}s\t\t{log['total_calls']}\t\t"
                  f"{log['calls_per_second']:.1f}\t\t{log['recent_avg_time']:.3f}s")


if __name__ == "__main__":
    # 基础演示
    main() 

    # 高级功能演示
    print("\n\n=== 高级功能演示 ===")
    advanced_controller = AdvancedDurationController()
    advanced_controller.run_with_performance_monitoring(
        sample_function_100ms, 3, log_interval=25
    )
