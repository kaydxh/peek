#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web 服务器工厂

提供 GenericWebServer 的工厂函数，封装常见的服务器创建流程：
- create_web_server: 创建并配置 Web 服务器
- install_grpc_interceptors: 安装 gRPC 默认拦截器链
- install_qps_limit_middleware: 安装 QPS 限流中间件
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def create_web_server(web_config: Any, **kwargs) -> Any:
    """创建并配置 Web 服务器。

    工厂函数，根据配置创建 GenericWebServer 并安装默认的
    gRPC 拦截器链和 QPS 限流中间件。

    Args:
        web_config: Web 配置对象或字典，需包含 bind_address、grpc、shutdown 等字段
        **kwargs: 传递给 GenericWebServer 构造函数的额外参数
            - title: API 标题（默认 "Web Server"）
            - description: API 描述
            - version: API 版本（默认 "1.0.0"）

    Returns:
        GenericWebServer 实例
    """
    try:
        from peek.net.webserver import GenericWebServer
    except ImportError:
        logger.error("peek.net.webserver not available, using fallback FastAPI server")
        return await _create_fallback_server(web_config)

    # 获取配置值，处理 dict 和 dataclass 两种情况
    bind_address = getattr(web_config, 'bind_address', {}) or {}
    if isinstance(bind_address, dict):
        host = bind_address.get('host', '0.0.0.0')
        port = bind_address.get('port', 10001)
    else:
        host = getattr(bind_address, 'host', '0.0.0.0')
        port = getattr(bind_address, 'port', 10001)

    grpc_config = getattr(web_config, 'grpc', {}) or {}
    shutdown_config = getattr(web_config, 'shutdown', {}) or {}

    # 获取 gRPC 端口
    if isinstance(grpc_config, dict):
        grpc_enabled = grpc_config.get('enabled', False)
        grpc_port = grpc_config.get('port', None) if grpc_enabled else None
    else:
        grpc_enabled = getattr(grpc_config, 'enabled', False)
        grpc_port = getattr(grpc_config, 'port', None) if grpc_enabled else None

    # 获取 shutdown 配置
    if isinstance(shutdown_config, dict):
        shutdown_delay = shutdown_config.get('delay_duration', 0)
        shutdown_timeout = shutdown_config.get('timeout_duration', 5.0)
    else:
        shutdown_delay = getattr(shutdown_config, 'delay_duration', 0)
        shutdown_timeout = getattr(shutdown_config, 'timeout_duration', 5.0)

    # 创建服务器
    server = GenericWebServer(
        host=host,
        port=port,
        grpc_port=grpc_port,
        shutdown_delay_duration=shutdown_delay,
        shutdown_timeout_duration=shutdown_timeout,
        title=kwargs.get("title", "Web Server"),
        description=kwargs.get("description", ""),
        version=kwargs.get("version", "1.0.0"),
    )

    # 安装 gRPC 默认拦截器链
    install_grpc_interceptors(server)

    # 安装限流中间件
    install_qps_limit_middleware(server, web_config)

    logger.info(f"WebServer created: http://{host}:{port}")
    return server


def install_grpc_interceptors(server: Any) -> None:
    """安装 gRPC 默认拦截器链。

    为 gRPC 请求添加以下拦截器：
    - RequestID: 请求ID生成/传递
    - Recovery: 异常捕获恢复
    - Timer: 请求耗时计时（含慢请求告警）
    - Logging: 请求/响应日志
    - Trace: 链路追踪

    Args:
        server: GenericWebServer 实例
    """
    try:
        from peek.net.grpc import create_default_interceptor_chain
    except ImportError:
        logger.warning("peek.net.grpc not available, skipping gRPC interceptors")
        return

    try:
        interceptors = create_default_interceptor_chain(
            enable_request_id=True,
            enable_recovery=True,
            enable_logging=True,
            enable_timer=True,
            enable_trace=True,
            log_request=True,
            log_response=True,
            slow_threshold_ms=1000,
        )
        server.add_grpc_interceptors(interceptors)
        logger.info(
            f"gRPC default interceptor chain installed: "
            f"{len(interceptors)} interceptors "
            f"(RequestID, Trace, Recovery, Timer, Logging)"
        )
    except Exception as e:
        logger.warning(f"Failed to install gRPC interceptors: {e}")


def install_qps_limit_middleware(server: Any, web_config: Any) -> None:
    """安装 QPS 限流中间件。

    Args:
        server: GenericWebServer 实例
        web_config: Web 配置对象
    """
    try:
        from peek.net.webserver.middleware import (
            QPSLimitConfig,
            MethodQPSConfig,
            QPSRateLimitMiddleware,
        )
    except ImportError:
        logger.warning("peek.net.webserver.middleware not available, skipping QPS limit middleware")
        return

    # 获取 qps_limit 配置
    qps_limit_config = getattr(web_config, 'qps_limit', {}) or {}
    if isinstance(qps_limit_config, dict):
        http_qps_config = qps_limit_config.get('http', {})
    else:
        http_qps_config = getattr(qps_limit_config, 'http', {}) or {}

    if not http_qps_config:
        logger.debug("No HTTP QPS limit config found, skipping QPS limit middleware")
        return

    # 解析配置
    if isinstance(http_qps_config, dict):
        default_qps = http_qps_config.get('default_qps', 0)
        default_burst = http_qps_config.get('default_burst', 0)
        max_concurrency = http_qps_config.get('max_concurrency', 0)
        method_qps_list = http_qps_config.get('method_qps', [])
    else:
        default_qps = getattr(http_qps_config, 'default_qps', 0)
        default_burst = getattr(http_qps_config, 'default_burst', 0)
        max_concurrency = getattr(http_qps_config, 'max_concurrency', 0)
        method_qps_list = getattr(http_qps_config, 'method_qps', [])

    # 如果没有配置任何限流参数，跳过
    if default_qps <= 0 and max_concurrency <= 0 and not method_qps_list:
        logger.debug("QPS limit config has no effective limits, skipping middleware")
        return

    # 构建方法级配置
    method_configs = []
    for item in method_qps_list:
        if isinstance(item, dict):
            method_configs.append(MethodQPSConfig(
                method=item.get('method', '*'),
                path=item.get('path', '/'),
                qps=item.get('qps', 0),
                burst=item.get('burst', 0),
                max_concurrency=item.get('max_concurrency', 0),
            ))
        else:
            method_configs.append(MethodQPSConfig(
                method=getattr(item, 'method', '*'),
                path=getattr(item, 'path', '/'),
                qps=getattr(item, 'qps', 0),
                burst=getattr(item, 'burst', 0),
                max_concurrency=getattr(item, 'max_concurrency', 0),
            ))

    # 创建限流配置
    config = QPSLimitConfig(
        default_qps=default_qps,
        default_burst=default_burst if default_burst > 0 else max(1, int(default_qps)),
        max_concurrency=max_concurrency,
        method_qps=method_configs,
    )

    # 添加限流中间件到服务器
    server.app.add_middleware(QPSRateLimitMiddleware, config=config)

    logger.info(
        f"QPS limit middleware installed: "
        f"default_qps={default_qps}, default_burst={default_burst}, "
        f"max_concurrency={max_concurrency}"
    )


async def _create_fallback_server(web_config: Any) -> Any:
    """创建回退 FastAPI 服务器（当 peek.net.webserver 不可用时）。

    Args:
        web_config: Web 配置对象
    
    Returns:
        FallbackWebServer 实例
    """
    from fastapi import FastAPI, APIRouter
    import uvicorn

    # 获取配置值
    bind_address = getattr(web_config, 'bind_address', {}) or {}
    if isinstance(bind_address, dict):
        host = bind_address.get('host', '0.0.0.0')
        port = bind_address.get('port', 10001)
    else:
        host = getattr(bind_address, 'host', '0.0.0.0')
        port = getattr(bind_address, 'port', 10001)

    class FallbackWebServer:
        """回退 Web 服务器，使用 FastAPI 直接实现。"""

        def __init__(self):
            self.app = FastAPI(title="Web Server")
            self.router = APIRouter()
            self.host = host
            self.port = port

        def get_router(self):
            """获取 API 路由器。"""
            return self.router

        async def run(self):
            """运行服务器。"""
            self.app.include_router(self.router)
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()

    server = FallbackWebServer()
    logger.info(f"Fallback WebServer created: http://{host}:{port}")
    return server
