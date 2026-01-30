#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC 服务器模块

提供 gRPC 服务器的核心实现。
"""

import asyncio
import logging
from concurrent import futures
from typing import Any, Callable, List, Optional, Tuple, Union

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

logger = logging.getLogger(__name__)


class GRPCServer:
    """gRPC 服务器

    提供 gRPC 服务注册、拦截器链、健康检查等功能。

    示例:
        ```python
        server = GRPCServer(port=50051)

        # 注册服务
        server.register_service(
            lambda s: my_pb2_grpc.add_MyServiceServicer_to_server(MyServicer(), s)
        )

        # 添加拦截器
        server.add_interceptor(RequestIDInterceptor())

        # 启动服务
        server.start()
        server.wait_for_termination()
        ```
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 50051,
        max_workers: int = 10,
        max_message_length: int = 100 * 1024 * 1024,  # 100MB
        options: Optional[List[Tuple[str, Any]]] = None,
    ):
        """初始化 gRPC 服务器

        Args:
            host: 绑定地址
            port: 端口号
            max_workers: 线程池最大工作线程数
            max_message_length: 最大消息大小（字节）
            options: gRPC 服务器选项
        """
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.max_message_length = max_message_length

        self._interceptors: List[grpc.ServerInterceptor] = []
        self._service_handlers: List[Callable[[grpc.Server], None]] = []
        self._service_names: List[str] = []
        self._server: Optional[grpc.Server] = None
        self._health_servicer: Optional[health.HealthServicer] = None
        self._started = False

        # gRPC 选项
        self._options = options or []
        self._options.extend([
            ("grpc.max_send_message_length", max_message_length),
            ("grpc.max_receive_message_length", max_message_length),
        ])

    @property
    def address(self) -> str:
        """获取服务器地址"""
        return f"{self.host}:{self.port}"

    def add_interceptor(self, interceptor: grpc.ServerInterceptor) -> "GRPCServer":
        """添加拦截器

        Args:
            interceptor: gRPC 服务端拦截器

        Returns:
            self，支持链式调用
        """
        if self._started:
            raise RuntimeError("Cannot add interceptor after server started")
        self._interceptors.append(interceptor)
        return self

    def add_interceptors(
        self, interceptors: List[grpc.ServerInterceptor]
    ) -> "GRPCServer":
        """批量添加拦截器

        Args:
            interceptors: 拦截器列表

        Returns:
            self，支持链式调用
        """
        for interceptor in interceptors:
            self.add_interceptor(interceptor)
        return self

    def register_service(
        self,
        add_servicer_func: Callable[[grpc.Server], None],
        service_name: Optional[str] = None,
    ) -> "GRPCServer":
        """注册 gRPC 服务

        Args:
            add_servicer_func: 注册函数，接收 grpc.Server 参数
            service_name: 服务名称（用于健康检查和反射）

        Returns:
            self，支持链式调用

        示例:
            ```python
            server.register_service(
                lambda s: my_pb2_grpc.add_MyServiceServicer_to_server(MyServicer(), s),
                service_name="my.service.MyService"
            )
            ```
        """
        self._service_handlers.append(add_servicer_func)
        if service_name:
            self._service_names.append(service_name)
        return self

    def _create_server(self) -> grpc.Server:
        """创建 gRPC 服务器"""
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            interceptors=self._interceptors,
            options=self._options,
        )

        # 注册所有服务
        for handler in self._service_handlers:
            handler(server)

        # 注册健康检查服务
        self._health_servicer = health.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(self._health_servicer, server)

        # 设置所有服务为 SERVING
        for service_name in self._service_names:
            self._health_servicer.set(
                service_name, health_pb2.HealthCheckResponse.SERVING
            )

        # 注册反射服务（用于 grpcurl 等工具）
        service_names_for_reflection = list(self._service_names)
        service_names_for_reflection.append(health.SERVICE_NAME)
        service_names_for_reflection.append(reflection.SERVICE_NAME)
        reflection.enable_server_reflection(service_names_for_reflection, server)

        return server

    def start(self) -> "GRPCServer":
        """启动服务器

        Returns:
            self，支持链式调用
        """
        if self._started:
            logger.warning("Server already started")
            return self

        self._server = self._create_server()
        self._server.add_insecure_port(self.address)
        self._server.start()
        self._started = True

        logger.info(f"gRPC server started on {self.address}")
        return self

    def stop(self, grace: Optional[float] = None) -> None:
        """停止服务器

        Args:
            grace: 优雅关闭等待时间（秒）
        """
        if self._server is not None:
            # 标记所有服务为 NOT_SERVING
            if self._health_servicer is not None:
                for service_name in self._service_names:
                    self._health_servicer.set(
                        service_name, health_pb2.HealthCheckResponse.NOT_SERVING
                    )

            self._server.stop(grace)
            logger.info("gRPC server stopped")

    def wait_for_termination(self, timeout: Optional[float] = None) -> bool:
        """等待服务器终止

        Args:
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            是否正常终止
        """
        if self._server is None:
            return True
        return self._server.wait_for_termination(timeout)

    def set_service_status(
        self, service_name: str, serving: bool
    ) -> None:
        """设置服务健康状态

        Args:
            service_name: 服务名称
            serving: 是否可用
        """
        if self._health_servicer is not None:
            status = (
                health_pb2.HealthCheckResponse.SERVING
                if serving
                else health_pb2.HealthCheckResponse.NOT_SERVING
            )
            self._health_servicer.set(service_name, status)


class AsyncGRPCServer:
    """异步 gRPC 服务器

    基于 grpcio 的异步实现。

    示例:
        ```python
        server = AsyncGRPCServer(port=50051)

        server.register_service(
            lambda s: my_pb2_grpc.add_MyServiceServicer_to_server(MyServicer(), s)
        )

        await server.start()
        await server.wait_for_termination()
        ```
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 50051,
        max_message_length: int = 100 * 1024 * 1024,
        options: Optional[List[Tuple[str, Any]]] = None,
    ):
        """初始化异步 gRPC 服务器

        Args:
            host: 绑定地址
            port: 端口号
            max_message_length: 最大消息大小（字节）
            options: gRPC 服务器选项
        """
        self.host = host
        self.port = port
        self.max_message_length = max_message_length

        self._interceptors: List[grpc.aio.ServerInterceptor] = []
        self._service_handlers: List[Callable[[grpc.aio.Server], None]] = []
        self._service_names: List[str] = []
        self._server: Optional[grpc.aio.Server] = None
        self._started = False

        # gRPC 选项
        self._options = options or []
        self._options.extend([
            ("grpc.max_send_message_length", max_message_length),
            ("grpc.max_receive_message_length", max_message_length),
        ])

    @property
    def address(self) -> str:
        """获取服务器地址"""
        return f"{self.host}:{self.port}"

    def add_interceptor(
        self, interceptor: grpc.aio.ServerInterceptor
    ) -> "AsyncGRPCServer":
        """添加拦截器"""
        if self._started:
            raise RuntimeError("Cannot add interceptor after server started")
        self._interceptors.append(interceptor)
        return self

    def register_service(
        self,
        add_servicer_func: Callable[[grpc.aio.Server], None],
        service_name: Optional[str] = None,
    ) -> "AsyncGRPCServer":
        """注册 gRPC 服务"""
        self._service_handlers.append(add_servicer_func)
        if service_name:
            self._service_names.append(service_name)
        return self

    async def start(self) -> "AsyncGRPCServer":
        """启动异步服务器"""
        if self._started:
            logger.warning("Server already started")
            return self

        self._server = grpc.aio.server(
            interceptors=self._interceptors,
            options=self._options,
        )

        # 注册所有服务
        for handler in self._service_handlers:
            handler(self._server)

        self._server.add_insecure_port(self.address)
        await self._server.start()
        self._started = True

        logger.info(f"Async gRPC server started on {self.address}")
        return self

    async def stop(self, grace: Optional[float] = None) -> None:
        """停止服务器"""
        if self._server is not None:
            await self._server.stop(grace)
            logger.info("Async gRPC server stopped")

    async def wait_for_termination(self) -> None:
        """等待服务器终止"""
        if self._server is not None:
            await self._server.wait_for_termination()
