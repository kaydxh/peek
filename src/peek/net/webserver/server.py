#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GenericWebServer - 通用 Web 服务器

参考 Go 版本 golang 库的 GenericWebServer 实现，提供：
- HTTP 服务器 (FastAPI + Uvicorn)
- gRPC 服务器 (grpcio)
- 生命周期钩子管理
- 中间件链
- 健康检查
- 优雅关闭
"""

import asyncio
import logging
import signal
import sys
import threading
import traceback
from concurrent import futures
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from peek.net.webserver.hooks import (
    HookEntry,
    PostStartHookFunc,
    PreShutdownHookFunc,
)
from peek.net.webserver.healthz import HealthzController
from peek.net.webserver.config import (
    WebConfig,
    load_config,
    load_config_from_file,
    WebServerConfigBuilder,
)

# 尝试导入 gRPC 相关模块
try:
    import grpc
    from grpc_health.v1 import health, health_pb2, health_pb2_grpc
    from grpc_reflection.v1alpha import reflection

    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False

logger = logging.getLogger(__name__)


class WebHandler:
    """
    WebHandler 接口

    所有业务处理器都需要继承此类来注册路由
    类似 Go 版本的 WebHandler interface
    """

    def set_routes(self, app: FastAPI) -> None:
        """
        设置路由

        Args:
            app: FastAPI 应用实例
        """
        raise NotImplementedError("Subclass must implement set_routes method")


class GenericWebServer:
    """
    通用 Web 服务器

    提供类似 Go 版本 GenericWebServer 的能力：
    - HTTP/gRPC 双协议支持
    - 生命周期钩子 (PostStartHook, PreShutdownHook)
    - 健康检查控制器
    - 优雅关闭
    - YAML 配置文件支持

    示例:
        ```python
        # 方式一：直接参数创建
        server = GenericWebServer(host="0.0.0.0", port=8080)

        # 方式二：从 YAML 配置文件创建
        server = GenericWebServer.from_config_file("config.yaml")

        # 方式三：从配置对象创建
        config = load_config_from_file("config.yaml")
        server = GenericWebServer.from_config(config)

        # 方式四：使用 Builder 创建配置
        config = (
            WebServerConfigBuilder()
            .with_bind_address("0.0.0.0", 8080)
            .with_grpc(port=50051)
            .build()
        )
        server = GenericWebServer.from_config(config)
        ```
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        grpc_port: Optional[int] = None,
        shutdown_delay_duration: float = 0,
        shutdown_timeout_duration: float = 5.0,
        max_request_body_bytes: int = 0,
        max_grpc_message_size: int = 100 * 1024 * 1024,  # 100MB
        grpc_max_workers: int = 10,
        web_server_id: str = "",
        title: str = "Web Server",
        description: str = "",
        version: str = "1.0.0",
        docs_url: str = "/docs",
        redoc_url: str = "/redoc",
        openapi_url: str = "/openapi.json",
    ):
        """
        初始化 GenericWebServer

        Args:
            host: 监听地址
            port: HTTP 监听端口
            grpc_port: gRPC 监听端口（None 表示不启用 gRPC）
            shutdown_delay_duration: 关闭延迟时间（秒）
            shutdown_timeout_duration: 关闭超时时间（秒）
            max_request_body_bytes: 最大 HTTP 请求体大小（0 表示不限制）
            max_grpc_message_size: 最大 gRPC 消息大小
            grpc_max_workers: gRPC 线程池大小
            web_server_id: 服务器 ID
            title: API 标题
            description: API 描述
            version: API 版本
            docs_url: Swagger UI 文档地址
            redoc_url: ReDoc 文档地址
            openapi_url: OpenAPI JSON 地址
        """
        self.host = host
        self.port = port
        self.grpc_port = grpc_port
        self.shutdown_delay_duration = shutdown_delay_duration
        self.shutdown_timeout_duration = shutdown_timeout_duration
        self.max_request_body_bytes = max_request_body_bytes
        self.max_grpc_message_size = max_grpc_message_size
        self.grpc_max_workers = grpc_max_workers
        self.web_server_id = web_server_id or f"webserver-{port}"

        # 生命周期钩子
        self._post_start_hooks: Dict[str, HookEntry[PostStartHookFunc]] = {}
        self._pre_shutdown_hooks: Dict[str, HookEntry[PreShutdownHookFunc]] = {}
        self._post_start_hooks_called: bool = False
        self._pre_shutdown_hooks_called: bool = False
        self._hooks_lock = threading.Lock()

        # 健康检查控制器
        self.healthz_controller: Optional[HealthzController] = None

        # 就绪状态通道
        self._readiness_stop_event: asyncio.Event = asyncio.Event()

        # 创建 FastAPI 应用
        self.app = FastAPI(
            title=title,
            description=description,
            version=version,
            docs_url=docs_url,
            redoc_url=redoc_url,
            openapi_url=openapi_url,
            lifespan=self._lifespan,
        )

        # Uvicorn 服务器实例
        self._server: Optional[uvicorn.Server] = None

        # gRPC 相关
        self._grpc_server: Optional["grpc.Server"] = None
        self._grpc_interceptors: List["grpc.ServerInterceptor"] = []
        self._grpc_service_handlers: List[Callable] = []
        self._grpc_service_names: List[str] = []
        self._grpc_health_servicer = None
        self._grpc_thread: Optional[threading.Thread] = None

        # gRPC 选项
        self._grpc_options: List[Tuple[str, Any]] = [
            ("grpc.max_send_message_length", max_grpc_message_size),
            ("grpc.max_receive_message_length", max_grpc_message_size),
        ]

        # 安装默认中间件
        self._install_default_middleware()

    @classmethod
    def from_config(cls, config: WebConfig) -> "GenericWebServer":
        """
        从配置对象创建 GenericWebServer

        Args:
            config: WebConfig 配置对象

        Returns:
            GenericWebServer 实例

        示例:
            ```python
            config = load_config_from_file("config.yaml")
            server = GenericWebServer.from_config(config)
            ```
        """
        return cls(
            host=config.bind_address.host,
            port=config.bind_address.port,
            grpc_port=config.grpc.port,
            shutdown_delay_duration=config.shutdown.delay_duration,
            shutdown_timeout_duration=config.shutdown.timeout_duration,
            max_request_body_bytes=config.http.max_request_body_bytes,
            max_grpc_message_size=max(
                config.grpc.max_receive_message_size,
                config.grpc.max_send_message_size,
            ),
            grpc_max_workers=config.grpc.max_workers,
            web_server_id=config.server_id,
            title=config.title,
            description=config.description,
            version=config.version,
            docs_url=config.http.docs_url,
            redoc_url=config.http.redoc_url,
            openapi_url=config.http.openapi_url,
        )

    @classmethod
    def from_config_file(cls, config_file: str) -> "GenericWebServer":
        """
        从 YAML 配置文件创建 GenericWebServer

        Args:
            config_file: YAML 配置文件路径

        Returns:
            GenericWebServer 实例

        示例:
            ```python
            server = GenericWebServer.from_config_file("config.yaml")
            server.run()
            ```
        """
        config = load_config_from_file(config_file)
        return cls.from_config(config)

    @classmethod
    def from_config_dict(cls, config_dict: dict) -> "GenericWebServer":
        """
        从配置字典创建 GenericWebServer

        Args:
            config_dict: 配置字典

        Returns:
            GenericWebServer 实例

        示例:
            ```python
            server = GenericWebServer.from_config_dict({
                "web": {
                    "bind_address": {"host": "0.0.0.0", "port": 8080},
                    "grpc": {"port": 50051},
                }
            })
            ```
        """
        config = load_config(config_dict=config_dict)
        return cls.from_config(config)

    def _install_default_middleware(self) -> None:
        """安装默认中间件
        
        默认安装以下中间件（按执行顺序）：
        1. CORS - 跨域支持
        2. RequestID - 请求ID生成/传递
        3. Recovery - 异常捕获恢复
        4. Timer - 请求耗时计时
        5. Logger - 请求/响应日志
        
        注意：中间件按添加顺序的逆序执行，即最后添加的最先执行
        """
        from peek.net.webserver.middleware import (
            RequestIDMiddleware,
            RecoveryMiddleware,
            TimerMiddleware,
            LoggerMiddleware,
        )
        
        # CORS 中间件（最先执行）
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Logger 中间件 - 记录请求/响应日志（含请求体、响应体、请求头、响应头）
        # 注意：Logger 要在 Timer 之后添加，这样才能获取到耗时信息
        # log_request_headers/log_response_headers: 类似 Go 版 InOutputHeaderPrinter
        self.app.add_middleware(
            LoggerMiddleware,
            logger=logger,
            log_request_body=True,
            log_response_body=True,
            log_request_headers=True,
            log_response_headers=True,
            max_string_length=64,  # 大字符串只打印前64字节
            skip_paths=["/health", "/healthz", "/ready", "/readyz", "/live", "/livez", "/metrics"],
        )
        
        # Timer 中间件 - 计算请求耗时
        self.app.add_middleware(TimerMiddleware)
        
        # Recovery 中间件 - 异常捕获恢复
        self.app.add_middleware(RecoveryMiddleware)
        
        # RequestID 中间件 - 生成/传递请求ID（最后添加，最先执行）
        self.app.add_middleware(RequestIDMiddleware)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """
        生命周期管理

        实现 FastAPI 的 lifespan context manager
        """
        # Startup
        await self._run_post_start_hooks()
        if self.healthz_controller:
            self.healthz_controller.set_ready(True)
        yield
        # Shutdown
        if self.healthz_controller:
            self.healthz_controller.set_ready(False)
        if self.shutdown_delay_duration > 0:
            await asyncio.sleep(self.shutdown_delay_duration)
        await self._run_pre_shutdown_hooks()

    def add_post_start_hook(
        self,
        name: str,
        hook: PostStartHookFunc,
    ) -> None:
        """
        添加启动后钩子

        Args:
            name: 钩子名称（必须唯一）
            hook: 钩子函数

        Raises:
            ValueError: 钩子名称重复
        """
        with self._hooks_lock:
            if self._post_start_hooks_called:
                raise RuntimeError(
                    f"Unable to add post start hook {name} after server has started"
                )
            if name in self._post_start_hooks:
                # 获取之前注册的堆栈信息
                prev_entry = self._post_start_hooks[name]
                raise ValueError(
                    f"Post start hook {name} already registered "
                    f"(previously registered at: {prev_entry.originating_stack})"
                )

            # 记录当前堆栈
            stack = "".join(traceback.format_stack())
            self._post_start_hooks[name] = HookEntry(
                hook=hook,
                originating_stack=stack,
            )

    def add_post_start_hook_or_die(
        self,
        name: str,
        hook: PostStartHookFunc,
    ) -> None:
        """
        添加启动后钩子，失败则终止进程

        Args:
            name: 钩子名称
            hook: 钩子函数
        """
        try:
            self.add_post_start_hook(name, hook)
        except Exception as e:
            print(f"Failed to add post start hook {name}: {e}", file=sys.stderr)
            sys.exit(1)

    def add_pre_shutdown_hook(
        self,
        name: str,
        hook: PreShutdownHookFunc,
    ) -> None:
        """
        添加关闭前钩子

        Args:
            name: 钩子名称（必须唯一）
            hook: 钩子函数

        Raises:
            ValueError: 钩子名称重复
        """
        with self._hooks_lock:
            if self._pre_shutdown_hooks_called:
                raise RuntimeError(
                    f"Unable to add pre shutdown hook {name} after server has started shutdown"
                )
            if name in self._pre_shutdown_hooks:
                prev_entry = self._pre_shutdown_hooks[name]
                raise ValueError(
                    f"Pre shutdown hook {name} already registered "
                    f"(previously registered at: {prev_entry.originating_stack})"
                )

            stack = "".join(traceback.format_stack())
            self._pre_shutdown_hooks[name] = HookEntry(
                hook=hook,
                originating_stack=stack,
            )

    def add_pre_shutdown_hook_or_die(
        self,
        name: str,
        hook: PreShutdownHookFunc,
    ) -> None:
        """
        添加关闭前钩子，失败则终止进程

        Args:
            name: 钩子名称
            hook: 钩子函数
        """
        try:
            self.add_pre_shutdown_hook(name, hook)
        except Exception as e:
            print(f"Failed to add pre shutdown hook {name}: {e}", file=sys.stderr)
            sys.exit(1)

    async def _run_post_start_hooks(self) -> None:
        """运行所有启动后钩子（并行执行）"""
        with self._hooks_lock:
            self._post_start_hooks_called = True
            hooks = dict(self._post_start_hooks)

        if not hooks:
            return

        # 并行执行所有钩子
        async def run_hook(name: str, entry: HookEntry[PostStartHookFunc]):
            try:
                if asyncio.iscoroutinefunction(entry.hook):
                    await entry.hook()
                else:
                    entry.hook()
                entry.done.set()
                print(f"Post start hook {name} completed")
            except Exception as e:
                print(f"Post start hook {name} failed: {e}", file=sys.stderr)

        tasks = [run_hook(name, entry) for name, entry in hooks.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_pre_shutdown_hooks(self) -> None:
        """运行所有关闭前钩子（顺序执行）"""
        with self._hooks_lock:
            self._pre_shutdown_hooks_called = True
            hooks = dict(self._pre_shutdown_hooks)

        if not hooks:
            return

        # 顺序执行所有钩子
        for name, entry in hooks.items():
            try:
                if asyncio.iscoroutinefunction(entry.hook):
                    await entry.hook()
                else:
                    entry.hook()
                entry.done.set()
                print(f"Pre shutdown hook {name} completed")
            except Exception as e:
                print(f"Pre shutdown hook {name} failed: {e}", file=sys.stderr)

    def install_healthz_controller(
        self,
        controller: Optional[HealthzController] = None,
    ) -> None:
        """
        安装健康检查控制器

        Args:
            controller: 健康检查控制器实例，None 则创建默认控制器
        """
        if controller is None:
            controller = HealthzController()

        self.healthz_controller = controller
        controller.install_routes(self.app)

    def install_web_handler(self, handler: WebHandler) -> None:
        """
        安装 Web 处理器

        Args:
            handler: WebHandler 实例
        """
        handler.set_routes(self.app)

    # ======================== gRPC 相关方法 ========================

    def add_grpc_interceptor(
        self, interceptor: "grpc.ServerInterceptor"
    ) -> "GenericWebServer":
        """
        添加 gRPC 拦截器

        Args:
            interceptor: gRPC 服务端拦截器

        Returns:
            self，支持链式调用
        """
        if not HAS_GRPC:
            raise ImportError(
                "grpcio is required for gRPC support. "
                "Install with: pip install grpcio grpcio-tools grpcio-health-checking grpcio-reflection"
            )
        self._grpc_interceptors.append(interceptor)
        return self

    def add_grpc_interceptors(
        self, interceptors: List["grpc.ServerInterceptor"]
    ) -> "GenericWebServer":
        """批量添加 gRPC 拦截器"""
        for interceptor in interceptors:
            self.add_grpc_interceptor(interceptor)
        return self

    def register_grpc_service(
        self,
        add_servicer_func: Callable,
        service_name: Optional[str] = None,
    ) -> "GenericWebServer":
        """
        注册 gRPC 服务

        Args:
            add_servicer_func: 注册函数，接收 grpc.Server 参数
            service_name: 服务名称（用于健康检查和反射）

        Returns:
            self，支持链式调用

        示例:
            ```python
            server.register_grpc_service(
                lambda s: my_pb2_grpc.add_MyServiceServicer_to_server(MyServicer(), s),
                service_name="my.service.MyService"
            )
            ```
        """
        if not HAS_GRPC:
            raise ImportError(
                "grpcio is required for gRPC support. "
                "Install with: pip install grpcio grpcio-tools grpcio-health-checking grpcio-reflection"
            )

        self._grpc_service_handlers.append(add_servicer_func)
        if service_name:
            self._grpc_service_names.append(service_name)
        return self

    def _create_grpc_server(self) -> "grpc.Server":
        """创建 gRPC 服务器"""
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.grpc_max_workers),
            interceptors=self._grpc_interceptors,
            options=self._grpc_options,
        )

        # 注册所有服务
        for handler in self._grpc_service_handlers:
            handler(server)

        # 注册健康检查服务
        self._grpc_health_servicer = health.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(
            self._grpc_health_servicer, server
        )

        # 设置所有服务为 SERVING
        for service_name in self._grpc_service_names:
            self._grpc_health_servicer.set(
                service_name, health_pb2.HealthCheckResponse.SERVING
            )

        # 注册反射服务
        service_names_for_reflection = list(self._grpc_service_names)
        service_names_for_reflection.append(health.SERVICE_NAME)
        service_names_for_reflection.append(reflection.SERVICE_NAME)
        reflection.enable_server_reflection(service_names_for_reflection, server)

        return server

    def _run_grpc_server(self) -> None:
        """运行 gRPC 服务器（在单独线程中）"""
        if not self._grpc_service_handlers:
            return

        self._grpc_server = self._create_grpc_server()
        grpc_address = f"{self.host}:{self.grpc_port}"
        self._grpc_server.add_insecure_port(grpc_address)
        self._grpc_server.start()
        logger.info(f"gRPC server started on {grpc_address}")
        self._grpc_server.wait_for_termination()

    def _stop_grpc_server(self, grace: Optional[float] = None) -> None:
        """停止 gRPC 服务器"""
        if self._grpc_server is not None:
            # 标记所有服务为 NOT_SERVING
            if self._grpc_health_servicer is not None:
                for service_name in self._grpc_service_names:
                    self._grpc_health_servicer.set(
                        service_name, health_pb2.HealthCheckResponse.NOT_SERVING
                    )

            self._grpc_server.stop(grace)
            logger.info("gRPC server stopped")

    def set_grpc_service_status(self, service_name: str, serving: bool) -> None:
        """
        设置 gRPC 服务健康状态

        Args:
            service_name: 服务名称
            serving: 是否可用
        """
        if self._grpc_health_servicer is not None:
            status = (
                health_pb2.HealthCheckResponse.SERVING
                if serving
                else health_pb2.HealthCheckResponse.NOT_SERVING
            )
            self._grpc_health_servicer.set(service_name, status)

    # ======================== 运行相关方法 ========================


    def prepare_run(self) -> "GenericWebServer":
        """
        准备运行

        安装默认路由和处理器

        Returns:
            self
        """
        # 安装默认的健康检查控制器
        if self.healthz_controller is None:
            self.install_healthz_controller()

        return self

    async def run_async(self) -> None:
        """异步运行服务器（HTTP + gRPC）"""
        # 启动 gRPC 服务器（如果配置了）
        if self.grpc_port is not None and HAS_GRPC and self._grpc_service_handlers:
            self._grpc_thread = threading.Thread(
                target=self._run_grpc_server,
                daemon=True,
            )
            self._grpc_thread.start()

        # 启动 HTTP 服务器
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)

        # 设置信号处理
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_shutdown(s)),
            )

        await self._server.serve()

    async def _handle_shutdown(self, sig: signal.Signals) -> None:
        """处理关闭信号"""
        logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")

        # 停止 gRPC 服务器
        if self._grpc_server is not None:
            self._stop_grpc_server(grace=self.shutdown_timeout_duration)

        # 停止 HTTP 服务器
        if self._server:
            self._server.should_exit = True

    def run(self) -> None:
        """
        运行服务器（阻塞）

        使用 uvicorn 运行 FastAPI 应用，同时启动 gRPC 服务器（如果配置了）
        """
        self.prepare_run()

        # 启动 gRPC 服务器（如果配置了）
        if self.grpc_port is not None and HAS_GRPC and self._grpc_service_handlers:
            self._grpc_thread = threading.Thread(
                target=self._run_grpc_server,
                daemon=True,
            )
            self._grpc_thread.start()

        # 启动 HTTP 服务器
        logger.info(f"HTTP server starting on {self.host}:{self.port}")
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )

    async def shutdown(self) -> None:
        """关闭服务器"""
        # 停止 gRPC 服务器
        if self._grpc_server is not None:
            self._stop_grpc_server(grace=self.shutdown_timeout_duration)

        # 停止 HTTP 服务器
        if self._server:
            self._server.should_exit = True

    def set_ready(self, ready: bool) -> None:
        """
        设置服务就绪状态

        Args:
            ready: 是否就绪
        """
        if self.healthz_controller:
            self.healthz_controller.set_ready(ready)

    @property
    def is_ready(self) -> bool:
        """获取服务就绪状态"""
        if self.healthz_controller:
            return self.healthz_controller.is_ready
        return True
