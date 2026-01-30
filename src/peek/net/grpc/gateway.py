#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC Gateway 模块

提供 HTTP/gRPC 同端口复用能力，类似 Go 版本的 grpc-gateway。
"""

import asyncio
import logging
import signal
import threading
from concurrent import futures
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

try:
    from fastapi import FastAPI, Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware
    import uvicorn

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

logger = logging.getLogger(__name__)


class GRPCGateway:
    """gRPC Gateway

    支持在同一端口同时提供 HTTP 和 gRPC 服务。

    实现方式：
    - gRPC 服务运行在独立端口（或与 HTTP 相同端口但通过不同协议区分）
    - HTTP 服务（FastAPI）可以作为 gRPC 的 HTTP/JSON 代理
    - 支持 gRPC-Gateway 风格的 HTTP 到 gRPC 转发

    注意：Python 不像 Go 那样方便地实现真正的同端口 HTTP/gRPC 复用，
    但可以通过以下方式近似实现：
    1. 分离端口：HTTP 和 gRPC 使用不同端口
    2. 协议判断：使用 h2c 或反向代理
    3. HTTP 代理：HTTP 请求转发到 gRPC 服务

    示例:
        ```python
        gateway = GRPCGateway(
            http_port=8080,
            grpc_port=50051,
        )

        # 注册 gRPC 服务
        gateway.register_grpc_service(
            lambda s: my_pb2_grpc.add_MyServiceServicer_to_server(MyServicer(), s),
            service_name="my.service.MyService"
        )

        # 注册 HTTP 路由（可选，用于自定义 HTTP 端点）
        @gateway.app.get("/api/hello")
        async def hello():
            return {"message": "Hello"}

        # 启动服务
        gateway.run()
        ```
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        http_port: int = 8080,
        grpc_port: int = 50051,
        title: str = "gRPC Gateway",
        description: str = "",
        version: str = "1.0.0",
        max_workers: int = 10,
        max_message_length: int = 100 * 1024 * 1024,
        grpc_options: Optional[List[Tuple[str, Any]]] = None,
    ):
        """初始化 gRPC Gateway

        Args:
            host: 绑定地址
            http_port: HTTP 端口
            grpc_port: gRPC 端口（如果与 http_port 相同则尝试端口复用）
            title: API 标题
            description: API 描述
            version: API 版本
            max_workers: gRPC 线程池大小
            max_message_length: 最大消息大小
            grpc_options: gRPC 服务器选项
        """
        if not HAS_FASTAPI:
            raise ImportError(
                "FastAPI is required for GRPCGateway. "
                "Install with: pip install fastapi uvicorn"
            )

        self.host = host
        self.http_port = http_port
        self.grpc_port = grpc_port
        self.max_workers = max_workers
        self.max_message_length = max_message_length

        # FastAPI 应用
        self.app = FastAPI(
            title=title,
            description=description,
            version=version,
        )

        # gRPC 服务器组件
        self._grpc_interceptors: List[grpc.ServerInterceptor] = []
        self._grpc_service_handlers: List[Callable[[grpc.Server], None]] = []
        self._service_names: List[str] = []
        self._grpc_server: Optional[grpc.Server] = None
        self._health_servicer: Optional[health.HealthServicer] = None

        # gRPC 选项
        self._grpc_options = grpc_options or []
        self._grpc_options.extend([
            ("grpc.max_send_message_length", max_message_length),
            ("grpc.max_receive_message_length", max_message_length),
        ])

        # HTTP 到 gRPC 的代理路由
        self._grpc_proxies: Dict[str, Callable] = {}

        # 运行状态
        self._running = False
        self._grpc_thread: Optional[threading.Thread] = None

        # 设置健康检查端点
        self._setup_health_endpoints()

    def _setup_health_endpoints(self) -> None:
        """设置健康检查 HTTP 端点"""

        @self.app.get("/healthz")
        async def healthz():
            return {"status": "ok"}

        @self.app.get("/livez")
        async def livez():
            return {"status": "ok"}

        @self.app.get("/readyz")
        async def readyz():
            if self._running:
                return {"status": "ok"}
            return Response(
                content='{"status": "not ready"}',
                status_code=503,
                media_type="application/json",
            )

    def add_grpc_interceptor(
        self, interceptor: grpc.ServerInterceptor
    ) -> "GRPCGateway":
        """添加 gRPC 拦截器

        Args:
            interceptor: gRPC 服务端拦截器

        Returns:
            self，支持链式调用
        """
        self._grpc_interceptors.append(interceptor)
        return self

    def add_grpc_interceptors(
        self, interceptors: List[grpc.ServerInterceptor]
    ) -> "GRPCGateway":
        """批量添加 gRPC 拦截器"""
        for interceptor in interceptors:
            self.add_grpc_interceptor(interceptor)
        return self

    def register_grpc_service(
        self,
        add_servicer_func: Callable[[grpc.Server], None],
        service_name: Optional[str] = None,
    ) -> "GRPCGateway":
        """注册 gRPC 服务

        Args:
            add_servicer_func: 注册函数
            service_name: 服务名称

        Returns:
            self，支持链式调用
        """
        self._grpc_service_handlers.append(add_servicer_func)
        if service_name:
            self._service_names.append(service_name)
        return self

    def register_http_proxy(
        self,
        http_method: str,
        http_path: str,
        grpc_method: str,
        request_converter: Callable[[Request], Any],
        response_converter: Callable[[Any], dict],
        grpc_stub_class: type,
    ) -> "GRPCGateway":
        """注册 HTTP 到 gRPC 的代理路由

        这实现了类似 grpc-gateway 的功能，将 HTTP 请求转发到 gRPC 服务。

        Args:
            http_method: HTTP 方法 (GET, POST, etc.)
            http_path: HTTP 路径
            grpc_method: gRPC 方法名
            request_converter: 将 HTTP Request 转换为 gRPC 请求
            response_converter: 将 gRPC 响应转换为 HTTP 响应
            grpc_stub_class: gRPC Stub 类

        Returns:
            self，支持链式调用

        示例:
            ```python
            gateway.register_http_proxy(
                http_method="POST",
                http_path="/api/v1/date",
                grpc_method="GetDate",
                request_converter=lambda req: date_pb2.DateRequest(format=req.query_params.get("format", "")),
                response_converter=lambda resp: {"date": resp.date},
                grpc_stub_class=date_pb2_grpc.DateServiceStub,
            )
            ```
        """
        async def proxy_handler(request: Request):
            try:
                # 创建 gRPC channel 和 stub
                async with grpc.aio.insecure_channel(
                    f"{self.host}:{self.grpc_port}"
                ) as channel:
                    stub = grpc_stub_class(channel)

                    # 转换请求
                    grpc_request = request_converter(request)

                    # 调用 gRPC 方法
                    method = getattr(stub, grpc_method)
                    grpc_response = await method(grpc_request)

                    # 转换响应
                    return response_converter(grpc_response)

            except grpc.RpcError as e:
                return Response(
                    content=f'{{"error": "{e.details()}"}}',
                    status_code=_grpc_status_to_http(e.code()),
                    media_type="application/json",
                )

        # 注册路由
        self.app.add_api_route(
            http_path,
            proxy_handler,
            methods=[http_method.upper()],
        )

        return self

    def _create_grpc_server(self) -> grpc.Server:
        """创建 gRPC 服务器"""
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            interceptors=self._grpc_interceptors,
            options=self._grpc_options,
        )

        # 注册所有服务
        for handler in self._grpc_service_handlers:
            handler(server)

        # 注册健康检查服务
        self._health_servicer = health.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(self._health_servicer, server)

        # 设置所有服务为 SERVING
        for service_name in self._service_names:
            self._health_servicer.set(
                service_name, health_pb2.HealthCheckResponse.SERVING
            )

        # 注册反射服务
        service_names_for_reflection = list(self._service_names)
        service_names_for_reflection.append(health.SERVICE_NAME)
        service_names_for_reflection.append(reflection.SERVICE_NAME)
        reflection.enable_server_reflection(service_names_for_reflection, server)

        return server

    def _run_grpc_server(self) -> None:
        """运行 gRPC 服务器（在单独线程中）"""
        self._grpc_server = self._create_grpc_server()
        self._grpc_server.add_insecure_port(f"{self.host}:{self.grpc_port}")
        self._grpc_server.start()
        logger.info(f"gRPC server started on {self.host}:{self.grpc_port}")
        self._grpc_server.wait_for_termination()

    def run(
        self,
        reload: bool = False,
        log_level: str = "info",
    ) -> None:
        """启动 HTTP 和 gRPC 服务

        Args:
            reload: 是否启用热重载
            log_level: 日志级别
        """
        self._running = True

        # 启动 gRPC 服务器线程
        if self._grpc_service_handlers:
            self._grpc_thread = threading.Thread(
                target=self._run_grpc_server,
                daemon=True,
            )
            self._grpc_thread.start()

        # 启动 HTTP 服务器
        logger.info(f"HTTP server starting on {self.host}:{self.http_port}")

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.http_port,
            reload=reload,
            log_level=log_level,
        )
        server = uvicorn.Server(config)

        # 处理信号
        def signal_handler(signum, frame):
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            server.run()
        finally:
            self.shutdown()

    async def run_async(
        self,
        reload: bool = False,
        log_level: str = "info",
    ) -> None:
        """异步启动服务"""
        self._running = True

        # 启动 gRPC 服务器线程
        if self._grpc_service_handlers:
            self._grpc_thread = threading.Thread(
                target=self._run_grpc_server,
                daemon=True,
            )
            self._grpc_thread.start()

        # 启动 HTTP 服务器
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.http_port,
            reload=reload,
            log_level=log_level,
        )
        server = uvicorn.Server(config)
        await server.serve()

    def shutdown(self, grace: Optional[float] = 5.0) -> None:
        """关闭服务

        Args:
            grace: 优雅关闭等待时间
        """
        self._running = False

        # 标记服务为 NOT_SERVING
        if self._health_servicer is not None:
            for service_name in self._service_names:
                self._health_servicer.set(
                    service_name, health_pb2.HealthCheckResponse.NOT_SERVING
                )

        # 停止 gRPC 服务器
        if self._grpc_server is not None:
            self._grpc_server.stop(grace)
            logger.info("gRPC server stopped")


def _grpc_status_to_http(code: grpc.StatusCode) -> int:
    """将 gRPC 状态码转换为 HTTP 状态码"""
    mapping = {
        grpc.StatusCode.OK: 200,
        grpc.StatusCode.CANCELLED: 499,
        grpc.StatusCode.UNKNOWN: 500,
        grpc.StatusCode.INVALID_ARGUMENT: 400,
        grpc.StatusCode.DEADLINE_EXCEEDED: 504,
        grpc.StatusCode.NOT_FOUND: 404,
        grpc.StatusCode.ALREADY_EXISTS: 409,
        grpc.StatusCode.PERMISSION_DENIED: 403,
        grpc.StatusCode.RESOURCE_EXHAUSTED: 429,
        grpc.StatusCode.FAILED_PRECONDITION: 400,
        grpc.StatusCode.ABORTED: 409,
        grpc.StatusCode.OUT_OF_RANGE: 400,
        grpc.StatusCode.UNIMPLEMENTED: 501,
        grpc.StatusCode.INTERNAL: 500,
        grpc.StatusCode.UNAVAILABLE: 503,
        grpc.StatusCode.DATA_LOSS: 500,
        grpc.StatusCode.UNAUTHENTICATED: 401,
    }
    return mapping.get(code, 500)
