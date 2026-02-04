#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
中间件示例

演示如何使用 peek 中的各种中间件功能：
- QPS 限流
- 并发限流
- 超时控制
- OpenTelemetry 追踪和指标
"""

import asyncio
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app_with_ratelimit() -> FastAPI:
    """
    创建带限流中间件的应用

    示例配置：
    - 默认 QPS: 100
    - /api/v1/upload 路径: QPS 10
    - /api/v1/slow 路径: 最大并发 5
    """
    from peek.net.webserver.middleware import (
        QPSLimitConfig,
        MethodQPSConfig,
        QPSRateLimitMiddleware,
        RequestIDMiddleware,
        TimerMiddleware,
        RecoveryMiddleware,
        create_qps_limiter,
    )

    app = FastAPI(title="Rate Limit Demo")

    # 创建限流配置
    config = QPSLimitConfig(
        default_qps=100,
        default_burst=10,
        max_concurrency=50,
        method_qps=[
            MethodQPSConfig(
                method="*",
                path="/api/v1/upload",
                qps=10,
                burst=5,
            ),
            MethodQPSConfig(
                method="*",
                path="/api/v1/slow",
                qps=0,  # 不限制 QPS
                max_concurrency=5,  # 但限制并发
            ),
            MethodQPSConfig(
                method="GET",
                path="/api/v1/*",  # 前缀匹配
                qps=50,
            ),
        ],
    )

    # 添加中间件（注意顺序：后添加的先执行）
    app.add_middleware(QPSRateLimitMiddleware, config=config)
    app.add_middleware(TimerMiddleware)
    app.add_middleware(RecoveryMiddleware, debug=True)
    app.add_middleware(RequestIDMiddleware)

    # 路由定义
    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/v1/upload")
    async def upload(request: Request):
        """模拟上传接口（有 QPS 限制）"""
        await asyncio.sleep(0.1)  # 模拟处理时间
        return {"message": "upload success"}

    @app.get("/api/v1/slow")
    async def slow():
        """模拟慢接口（有并发限制）"""
        await asyncio.sleep(2)  # 模拟长时间处理
        return {"message": "slow response"}

    @app.get("/api/v1/users")
    async def list_users():
        """用户列表（受前缀匹配限流）"""
        return {"users": ["user1", "user2"]}

    return app


def create_app_with_timeout() -> FastAPI:
    """
    创建带超时中间件的应用
    """
    from peek.net.webserver.middleware import (
        TimeoutMiddleware,
        PathTimeoutMiddleware,
        RequestIDMiddleware,
    )

    app = FastAPI(title="Timeout Demo")

    # 路径级超时配置
    app.add_middleware(
        PathTimeoutMiddleware,
        default_timeout=30.0,
        path_timeouts={
            "/api/v1/quick": 1.0,  # 快速接口 1 秒超时
            "/api/v1/slow/*": 60.0,  # 慢接口 60 秒超时
        },
    )
    app.add_middleware(RequestIDMiddleware)

    @app.get("/api/v1/quick")
    async def quick():
        """快速接口"""
        return {"message": "quick response"}

    @app.get("/api/v1/slow/process")
    async def slow_process():
        """慢接口"""
        await asyncio.sleep(5)
        return {"message": "slow process done"}

    @app.get("/api/v1/timeout-test")
    async def timeout_test():
        """测试超时"""
        await asyncio.sleep(35)  # 超过默认 30 秒
        return {"message": "should timeout"}

    return app


def create_app_with_opentelemetry() -> FastAPI:
    """
    创建带 OpenTelemetry 中间件的应用
    """
    from peek.net.webserver.middleware import (
        TraceMiddleware,
        MetricMiddleware,
        RequestIDMiddleware,
        TimerMiddleware,
    )

    app = FastAPI(title="OpenTelemetry Demo")

    # 添加 OpenTelemetry 中间件
    app.add_middleware(MetricMiddleware)
    app.add_middleware(TraceMiddleware)
    app.add_middleware(TimerMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/api/v1/trace")
    async def trace_demo():
        """追踪示例"""
        await asyncio.sleep(0.1)
        return {"message": "traced"}

    return app


def create_full_app() -> FastAPI:
    """
    创建完整功能的应用

    包含所有中间件：
    - RequestID
    - Recovery
    - Timer
    - Rate Limit
    - Timeout
    - OpenTelemetry (如果可用)
    """
    from peek.net.webserver.middleware import (
        QPSLimitConfig,
        MethodQPSConfig,
        QPSRateLimitMiddleware,
        TimeoutMiddleware,
        RequestIDMiddleware,
        TimerMiddleware,
        RecoveryMiddleware,
        LoggerMiddleware,
        RateLimitStatsHandler,
        create_qps_limiter,
    )

    app = FastAPI(
        title="Full Middleware Demo",
        description="演示所有中间件功能",
        version="1.0.0",
    )

    # 创建限流器
    limiter = create_qps_limiter(
        default_qps=100,
        default_burst=10,
        max_concurrency=100,
        method_configs=[
            {"path": "/api/v1/upload", "qps": 10, "burst": 5},
            {"path": "/api/v1/heavy/*", "max_concurrency": 10},
        ],
    )

    # 添加中间件（从下到上执行）
    app.add_middleware(LoggerMiddleware)
    app.add_middleware(QPSRateLimitMiddleware, limiter=limiter)
    app.add_middleware(TimeoutMiddleware, timeout=30.0)
    app.add_middleware(TimerMiddleware)
    app.add_middleware(RecoveryMiddleware, debug=True)
    app.add_middleware(RequestIDMiddleware)

    # 尝试添加 OpenTelemetry 中间件
    try:
        from peek.net.webserver.middleware import TraceMiddleware, MetricMiddleware

        app.add_middleware(MetricMiddleware)
        app.add_middleware(TraceMiddleware)
        logger.info("OpenTelemetry middlewares enabled")
    except Exception as e:
        logger.warning(f"OpenTelemetry not available: {e}")

    # 路由定义
    @app.get("/")
    async def root():
        return {"message": "Welcome to Full Middleware Demo"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/users")
    async def list_users():
        return {"users": ["user1", "user2", "user3"]}

    @app.post("/api/v1/upload")
    async def upload():
        await asyncio.sleep(0.1)
        return {"message": "uploaded"}

    @app.get("/api/v1/heavy/compute")
    async def heavy_compute():
        """重计算接口"""
        await asyncio.sleep(1)
        return {"result": "computed"}

    @app.get("/api/v1/error")
    async def error():
        """测试错误处理"""
        raise ValueError("Test error")

    # 限流统计端点
    stats_handler = RateLimitStatsHandler(limiter)
    app.add_api_route(
        "/debug/ratelimit/stats",
        stats_handler,
        methods=["GET"],
        tags=["Debug"],
    )

    return app


# ===================== gRPC 中间件示例 =====================


def create_grpc_server_with_interceptors():
    """
    创建带拦截器的 gRPC 服务器

    示例代码，需要实际的 proto 定义才能运行
    """
    from concurrent import futures

    import grpc

    from peek.net.grpc.interceptor import (
        InterceptorChain,
        RequestIDInterceptor,
        RecoveryInterceptor,
        TimerInterceptor,
        LoggingInterceptor,
    )
    from peek.net.grpc.middleware import (
        QPSLimitInterceptor,
        ConcurrencyLimitInterceptor,
        MethodQPSLimitInterceptor,
    )

    # 构建拦截器链
    chain = InterceptorChain()
    chain.add(RequestIDInterceptor())
    chain.add(RecoveryInterceptor())
    chain.add(TimerInterceptor(slow_threshold_ms=1000))
    chain.add(LoggingInterceptor(log_request=True, log_response=False))
    chain.add(QPSLimitInterceptor(qps=100, burst=10))
    chain.add(ConcurrencyLimitInterceptor(max_concurrency=50))

    # 创建 gRPC 服务器
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=chain.build(),
    )

    return server


def create_grpc_server_with_method_limit():
    """
    创建带方法级限流的 gRPC 服务器
    """
    from concurrent import futures

    import grpc

    from peek.net.grpc.interceptor import (
        InterceptorChain,
        RequestIDInterceptor,
        RecoveryInterceptor,
    )
    from peek.net.grpc.middleware import (
        MethodQPSLimitInterceptor,
        GrpcQPSLimitConfig,
        MethodQPSConfig,
    )

    # 方法级限流配置
    config = GrpcQPSLimitConfig(
        default_qps=100,
        default_burst=10,
        max_concurrency=50,
        method_qps=[
            MethodQPSConfig(
                method="/myservice.v1.MyService/Upload",
                qps=10,
                burst=5,
            ),
            MethodQPSConfig(
                method="/myservice.v1.MyService/*",  # 前缀匹配
                qps=50,
            ),
        ],
    )

    # 构建拦截器链
    chain = InterceptorChain()
    chain.add(RequestIDInterceptor())
    chain.add(RecoveryInterceptor())
    chain.add(MethodQPSLimitInterceptor(config))

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=chain.build(),
    )

    return server


# ===================== 测试函数 =====================


async def test_ratelimit():
    """测试限流功能"""
    from peek.net.webserver.middleware import (
        TokenBucketLimiter,
        create_qps_limiter,
    )

    print("\n=== Testing Token Bucket Limiter ===")

    limiter = TokenBucketLimiter(qps=10, burst=5)

    # 快速发送 10 个请求
    allowed = 0
    rejected = 0

    for i in range(10):
        if limiter.allow():
            allowed += 1
        else:
            rejected += 1

    print(f"Allowed: {allowed}, Rejected: {rejected}")
    print(f"Stats: {limiter.stats()}")

    # 等待令牌恢复
    print("\nWaiting 1 second for tokens to recover...")
    await asyncio.sleep(1)

    # 再次测试
    allowed_after = 0
    for i in range(10):
        if limiter.allow():
            allowed_after += 1

    print(f"Allowed after wait: {allowed_after}")


async def test_qps_limiter():
    """测试 QPS 限流器"""
    from peek.net.webserver.middleware import create_qps_limiter

    print("\n=== Testing QPS Limiter ===")

    limiter = create_qps_limiter(
        default_qps=10,
        default_burst=5,
        method_configs=[
            {"path": "/api/upload", "qps": 2, "burst": 1},
        ],
    )

    # 测试默认限流
    allowed = sum(1 for _ in range(10) if limiter.allow("GET", "/api/users"))
    print(f"Default path - Allowed: {allowed}/10")

    # 测试特定路径限流
    allowed = sum(1 for _ in range(10) if limiter.allow("POST", "/api/upload"))
    print(f"Upload path - Allowed: {allowed}/10")

    print(f"\nStats: {limiter.stats()}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]

        if mode == "test":
            # 运行测试
            asyncio.run(test_ratelimit())
            asyncio.run(test_qps_limiter())

        elif mode == "server":
            # 启动完整服务器
            import uvicorn

            app = create_full_app()
            uvicorn.run(app, host="0.0.0.0", port=8080)

        elif mode == "ratelimit":
            # 启动限流演示服务器
            import uvicorn

            app = create_app_with_ratelimit()
            uvicorn.run(app, host="0.0.0.0", port=8080)

        elif mode == "timeout":
            # 启动超时演示服务器
            import uvicorn

            app = create_app_with_timeout()
            uvicorn.run(app, host="0.0.0.0", port=8080)

    else:
        print("Usage:")
        print("  python main.py test      - Run tests")
        print("  python main.py server    - Run full demo server")
        print("  python main.py ratelimit - Run rate limit demo")
        print("  python main.py timeout   - Run timeout demo")
