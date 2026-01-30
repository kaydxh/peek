#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理

参考 Go 版本 golang 库的 config.go 实现
提供 WebServer 配置和 Option 模式支持
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


class BindAddress(BaseModel):
    """绑定地址配置"""

    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8080, description="监听端口")


class HTTPConfig(BaseModel):
    """HTTP 配置"""

    api_formatter: str = Field(default="", description="API 格式化器")
    read_timeout: float = Field(default=30.0, description="读取超时（秒）")
    write_timeout: float = Field(default=30.0, description="写入超时（秒）")
    idle_timeout: float = Field(default=60.0, description="空闲超时（秒）")


class DebugConfig(BaseModel):
    """调试配置"""

    enable_profiling: bool = Field(default=False, description="是否启用 pprof")
    pprof_path: str = Field(default="/debug/pprof", description="pprof 路径")


class MethodQPSConfigItem(BaseModel):
    """方法级 QPS 配置项"""

    method: str = Field(default="*", description="HTTP 方法")
    path: str = Field(default="", description="请求路径")
    qps: float = Field(default=0, description="QPS 限制")
    burst: int = Field(default=0, description="突发容量")


class QPSLimitConfig(BaseModel):
    """QPS 限流配置"""

    default_qps: float = Field(default=0, description="默认 QPS（0 不限制）")
    default_burst: int = Field(default=0, description="默认突发容量")
    max_concurrency: int = Field(default=0, description="最大并发数（0 不限制）")
    method_qps: List[MethodQPSConfigItem] = Field(
        default_factory=list,
        description="方法级 QPS 配置",
    )


class OpenTelemetryResourceConfig(BaseModel):
    """OpenTelemetry 资源配置"""

    service_name: str = Field(default="", description="服务名称")
    service_version: str = Field(default="", description="服务版本")
    service_namespace: str = Field(default="", description="服务命名空间")
    deployment_environment: str = Field(default="", description="部署环境")


class OpenTelemetryConfig(BaseModel):
    """OpenTelemetry 配置"""

    enabled: bool = Field(default=False, description="是否启用")
    metric_collect_duration: int = Field(
        default=60,
        description="指标收集间隔（秒）",
    )
    otel_metric_exporter_type: str = Field(
        default="metric_stdout",
        description="指标导出器类型",
    )
    otel_trace_exporter_type: str = Field(
        default="trace_stdout",
        description="追踪导出器类型",
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="",
        description="OTLP 端点地址",
    )
    resource: OpenTelemetryResourceConfig = Field(
        default_factory=OpenTelemetryResourceConfig,
        description="资源配置",
    )


class WebConfig(BaseModel):
    """Web 服务配置"""

    bind_address: BindAddress = Field(
        default_factory=BindAddress,
        description="绑定地址",
    )
    http: HTTPConfig = Field(
        default_factory=HTTPConfig,
        description="HTTP 配置",
    )
    debug: DebugConfig = Field(
        default_factory=DebugConfig,
        description="调试配置",
    )
    open_telemetry: OpenTelemetryConfig = Field(
        default_factory=OpenTelemetryConfig,
        description="OpenTelemetry 配置",
    )
    grpc_qps_limit: QPSLimitConfig = Field(
        default_factory=QPSLimitConfig,
        description="gRPC QPS 限流配置",
    )
    http_qps_limit: QPSLimitConfig = Field(
        default_factory=QPSLimitConfig,
        description="HTTP QPS 限流配置",
    )
    shutdown_delay_duration: float = Field(
        default=0,
        description="关闭延迟时间（秒）",
    )
    shutdown_timeout_duration: float = Field(
        default=5.0,
        description="关闭超时时间（秒）",
    )
    max_request_body_bytes: int = Field(
        default=0,
        description="最大请求体大小（0 不限制）",
    )


class WebServerConfig(BaseModel):
    """WebServer 完整配置"""

    web: WebConfig = Field(
        default_factory=WebConfig,
        description="Web 服务配置",
    )


# Option 模式类型
ConfigOption = Callable[["Config"], None]


class Config:
    """
    WebServer 配置管理

    支持 Option 模式进行配置定制
    """

    def __init__(
        self,
        proto: WebServerConfig = None,
        **kwargs,
    ):
        """
        Args:
            proto: 配置对象
            **kwargs: 额外配置
        """
        self.proto = proto or WebServerConfig()

        # 内部选项
        self._bind_address: str = ""
        self._external_address: str = ""
        self._shutdown_delay_duration: float = 0
        self._shutdown_timeout_duration: float = 5.0
        self._title: str = "Web Server"
        self._description: str = ""
        self._version: str = "1.0.0"
        self._docs_url: str = "/docs"
        self._redoc_url: str = "/redoc"

    def apply_options(self, *options: ConfigOption) -> "Config":
        """
        应用配置选项

        Args:
            options: 配置选项列表

        Returns:
            self
        """
        for option in options:
            option(self)
        return self

    @classmethod
    def from_yaml(cls, config_file: str, *options: ConfigOption) -> "Config":
        """
        从 YAML 文件加载配置

        Args:
            config_file: 配置文件路径
            options: 配置选项列表

        Returns:
            Config 实例
        """
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        proto = WebServerConfig(**raw_config)
        config = cls(proto)
        config.apply_options(*options)

        return config

    def complete(self) -> "CompletedConfig":
        """
        完成配置初始化

        Returns:
            CompletedConfig 实例
        """
        # 应用 proto 中的配置
        web = self.proto.web

        if not self._bind_address:
            self._bind_address = f"{web.bind_address.host}:{web.bind_address.port}"

        if not self._shutdown_delay_duration:
            self._shutdown_delay_duration = web.shutdown_delay_duration

        if not self._shutdown_timeout_duration:
            self._shutdown_timeout_duration = web.shutdown_timeout_duration

        return CompletedConfig(self)


class CompletedConfig:
    """已完成初始化的配置"""

    def __init__(self, config: Config):
        self._config = config
        self.proto = config.proto

    @property
    def bind_address(self) -> str:
        return self._config._bind_address

    @property
    def host(self) -> str:
        return self.proto.web.bind_address.host

    @property
    def port(self) -> int:
        return self.proto.web.bind_address.port

    @property
    def shutdown_delay_duration(self) -> float:
        return self._config._shutdown_delay_duration

    @property
    def shutdown_timeout_duration(self) -> float:
        return self._config._shutdown_timeout_duration

    @property
    def title(self) -> str:
        return self._config._title

    @property
    def description(self) -> str:
        return self._config._description

    @property
    def version(self) -> str:
        return self._config._version

    @property
    def docs_url(self) -> str:
        return self._config._docs_url

    @property
    def redoc_url(self) -> str:
        return self._config._redoc_url

    @property
    def http_qps_limit(self) -> QPSLimitConfig:
        return self.proto.web.http_qps_limit

    @property
    def grpc_qps_limit(self) -> QPSLimitConfig:
        return self.proto.web.grpc_qps_limit

    @property
    def open_telemetry(self) -> OpenTelemetryConfig:
        return self.proto.web.open_telemetry

    @property
    def max_request_body_bytes(self) -> int:
        return self.proto.web.max_request_body_bytes

    def new_server(self) -> "GenericWebServer":
        """
        创建 WebServer 实例

        Returns:
            GenericWebServer 实例
        """
        from peek.net.webserver.server import GenericWebServer
        from peek.net.webserver.middleware import (
            HandlerChain,
            LoggerMiddleware,
            MaxBodySizeMiddleware,
            RecoveryMiddleware,
            RequestIDMiddleware,
            TimerMiddleware,
        )
        from peek.net.webserver.middleware.ratelimit import (
            QPSLimitConfig as RateLimitConfig,
            QPSRateLimitMiddleware,
            MethodQPSConfig,
        )
        from peek.net.webserver.middleware.opentelemetry import (
            MetricMiddleware,
            TraceMiddleware,
        )

        # 创建服务器
        server = GenericWebServer(
            host=self.host,
            port=self.port,
            shutdown_delay_duration=self.shutdown_delay_duration,
            shutdown_timeout_duration=self.shutdown_timeout_duration,
            max_request_body_bytes=self.max_request_body_bytes,
            title=self.title,
            description=self.description,
            version=self.version,
            docs_url=self.docs_url,
            redoc_url=self.redoc_url,
        )

        # 安装中间件链
        chain = HandlerChain()

        # 基础中间件
        chain.add_handler(LoggerMiddleware)
        chain.add_handler(TimerMiddleware)
        chain.add_handler(RecoveryMiddleware, debug=True)
        chain.add_handler(RequestIDMiddleware)

        # 请求体大小限制
        if self.max_request_body_bytes > 0:
            chain.add_handler(
                MaxBodySizeMiddleware,
                max_body_size=self.max_request_body_bytes,
            )

        # QPS 限流
        http_qps = self.http_qps_limit
        if http_qps.default_qps > 0 or http_qps.max_concurrency > 0:
            rate_config = RateLimitConfig(
                default_qps=http_qps.default_qps,
                default_burst=http_qps.default_burst,
                max_concurrency=http_qps.max_concurrency,
                method_qps=[
                    MethodQPSConfig(
                        method=m.method,
                        path=m.path,
                        qps=m.qps,
                        burst=m.burst,
                    )
                    for m in http_qps.method_qps
                ],
            )
            chain.add_handler(QPSRateLimitMiddleware, config=rate_config)

        # OpenTelemetry
        otel = self.open_telemetry
        if otel.enabled:
            service_name = otel.resource.service_name or "webserver"
            service_version = otel.resource.service_version or "1.0.0"

            chain.add_handler(
                TraceMiddleware,
                tracer_name=service_name,
                tracer_version=service_version,
            )
            chain.add_handler(
                MetricMiddleware,
                meter_name=service_name,
                meter_version=service_version,
            )

        # 安装中间件链
        chain.install(server.app)

        return server


# ==================== Option 函数 ====================


def with_bind_address(address: str) -> ConfigOption:
    """设置绑定地址"""

    def apply(config: Config):
        config._bind_address = address

    return apply


def with_external_address(address: str) -> ConfigOption:
    """设置外部地址"""

    def apply(config: Config):
        config._external_address = address

    return apply


def with_shutdown_delay_duration(duration: float) -> ConfigOption:
    """设置关闭延迟时间"""

    def apply(config: Config):
        config._shutdown_delay_duration = duration

    return apply


def with_shutdown_timeout_duration(duration: float) -> ConfigOption:
    """设置关闭超时时间"""

    def apply(config: Config):
        config._shutdown_timeout_duration = duration

    return apply


def with_title(title: str) -> ConfigOption:
    """设置 API 标题"""

    def apply(config: Config):
        config._title = title

    return apply


def with_description(description: str) -> ConfigOption:
    """设置 API 描述"""

    def apply(config: Config):
        config._description = description

    return apply


def with_version(version: str) -> ConfigOption:
    """设置 API 版本"""

    def apply(config: Config):
        config._version = version

    return apply


def with_docs_url(url: str) -> ConfigOption:
    """设置 Swagger UI 文档地址"""

    def apply(config: Config):
        config._docs_url = url

    return apply


def with_redoc_url(url: str) -> ConfigOption:
    """设置 ReDoc 文档地址"""

    def apply(config: Config):
        config._redoc_url = url

    return apply
