#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通用配置模型

提供框架级通用的配置数据类，可被上层框架（如 tide）直接复用或继承。
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from peek.time.parse import parse_duration


class NetConfig(BaseModel):
    """网络绑定配置"""

    host: str = Field(default="0.0.0.0", description="绑定地址")
    port: int = Field(default=8080, ge=1, le=65535, description="绑定端口")


class GrpcConfig(BaseModel):
    """gRPC 配置"""

    enabled: bool = Field(default=True, description="是否启用")
    port: int = Field(default=50051, ge=1, le=65535, description="gRPC 端口")
    timeout: float = Field(default=0, ge=0, description="超时时间（秒）")
    max_recv_msg_size: int = Field(
        default=4 * 1024 * 1024, ge=0, description="最大接收消息大小"
    )
    max_send_msg_size: int = Field(
        default=4 * 1024 * 1024, ge=0, description="最大发送消息大小"
    )

    @field_validator("timeout", mode="before")
    @classmethod
    def parse_timeout(cls, v):
        return parse_duration(v)


class HttpConfig(BaseModel):
    """HTTP 配置"""

    enabled: bool = Field(default=True, description="是否启用")
    read_timeout: float = Field(default=0, ge=0, description="读取超时时间（秒）")
    write_timeout: float = Field(default=0, ge=0, description="写入超时时间（秒）")
    max_request_body_size: int = Field(
        default=4 * 1024 * 1024, ge=0, description="最大请求体大小"
    )
    api_formatter: str = Field(default="trivial_api_v20", description="API 格式化器")

    @field_validator("read_timeout", "write_timeout", mode="before")
    @classmethod
    def parse_timeout(cls, v):
        return parse_duration(v)


class MethodQPSConfig(BaseModel):
    """方法级 QPS 配置"""

    method: str = Field(default="*", description="HTTP 方法或 gRPC 方法")
    path: str = Field(default="/", description="路径，支持前缀匹配")
    qps: float = Field(default=0, ge=0, description="QPS 限制")
    burst: int = Field(default=0, ge=0, description="突发容量")
    max_concurrency: int = Field(default=0, ge=0, description="最大并发数")


class QPSLimitConfig(BaseModel):
    """QPS 限流配置"""

    default_qps: float = Field(default=0, ge=0, description="默认 QPS")
    default_burst: int = Field(default=0, ge=0, description="默认突发容量")
    max_concurrency: int = Field(default=0, ge=0, description="最大并发数")
    wait_timeout: float = Field(default=0, ge=0, description="等待超时时间（秒）")
    method_qps: List[MethodQPSConfig] = Field(
        default_factory=list, description="方法级配置"
    )

    @field_validator("wait_timeout", mode="before")
    @classmethod
    def parse_wait_timeout(cls, v):
        return parse_duration(v)


class DebugConfig(BaseModel):
    """调试配置"""

    enabled: bool = Field(default=False, description="是否启用调试")
    enable_profiling: bool = Field(default=False, description="是否启用性能分析")
    profiling_path: str = Field(default="/debug/pprof", description="性能分析路径")


class ShutdownConfig(BaseModel):
    """关闭配置"""

    delay_duration: float = Field(default=0, ge=0, description="关闭延迟时间（秒）")
    timeout_duration: float = Field(default=5.0, ge=0, description="关闭超时时间（秒）")

    @field_validator("delay_duration", "timeout_duration", mode="before")
    @classmethod
    def parse_duration_field(cls, v):
        return parse_duration(v)


class WebConfig(BaseModel):
    """Web 服务器配置"""

    bind_address: NetConfig = Field(default_factory=NetConfig, description="绑定地址")
    grpc: GrpcConfig = Field(default_factory=GrpcConfig, description="gRPC 配置")
    http: HttpConfig = Field(default_factory=HttpConfig, description="HTTP 配置")
    debug: DebugConfig = Field(default_factory=DebugConfig, description="调试配置")
    shutdown: ShutdownConfig = Field(
        default_factory=ShutdownConfig, description="关闭配置"
    )
    http_qps_limit: Optional[QPSLimitConfig] = Field(
        default=None, description="HTTP QPS 限流配置"
    )
    grpc_qps_limit: Optional[QPSLimitConfig] = Field(
        default=None, description="gRPC QPS 限流配置"
    )


class LogConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="info", description="日志级别")
    format: str = Field(default="text", description="日志格式 (text/json)")
    filepath: str = Field(default="./log", description="日志文件路径")
    max_age: float = Field(default=604800, ge=0, description="最大保留时间（秒）")
    rotate_interval: float = Field(default=3600, ge=0, description="轮转间隔（秒）")
    rotate_size: int = Field(default=100 * 1024 * 1024, ge=0, description="轮转大小")
    report_caller: bool = Field(default=False, description="是否报告调用者")

    @field_validator("max_age", "rotate_interval", mode="before")
    @classmethod
    def parse_duration_field(cls, v):
        return parse_duration(v)


class OpenTelemetryConfig(BaseModel):
    """OpenTelemetry 配置"""

    enabled: bool = Field(default=False, description="是否启用")
    service_name: str = Field(default="app-service", description="服务名称")
    service_version: str = Field(default="1.0.0", description="服务版本")

    # Trace 配置
    trace_enabled: bool = Field(default=True, description="是否启用 Trace")
    trace_exporter_type: str = Field(
        default="otlp", description="Trace 导出器类型 (otlp/jaeger/stdout)"
    )
    trace_endpoint: str = Field(
        default="http://localhost:4317", description="Trace 导出端点"
    )
    trace_sample_ratio: float = Field(
        default=1.0, ge=0, le=1, description="Trace 采样率"
    )

    # Metric 配置
    metric_enabled: bool = Field(default=True, description="是否启用 Metric")
    metric_exporter_type: str = Field(
        default="otlp", description="Metric 导出器类型 (otlp/prometheus/stdout)"
    )
    metric_endpoint: str = Field(
        default="http://localhost:4317", description="Metric 导出端点"
    )
    metric_collect_duration: float = Field(
        default=60, ge=0, description="Metric 收集间隔（秒）"
    )

    @field_validator("metric_collect_duration", mode="before")
    @classmethod
    def parse_duration_field(cls, v):
        return parse_duration(v)


class MonitorConfig(BaseModel):
    """进程监控配置"""

    enabled: bool = Field(default=False, description="是否启用监控")
    auto_start: bool = Field(default=False, description="是否自动启动持续采集")
    interval: float = Field(default=5.0, ge=0, description="采集间隔（秒）")
    enable_gpu: bool = Field(default=True, description="是否启用 GPU 监控")
    include_children: bool = Field(default=True, description="是否监控子进程")
    history_size: int = Field(default=3600, ge=0, description="历史记录最大条数")


class DatabaseConfig(BaseModel):
    """
    数据库配置

    对应 Go 版本 database 配置，聚合 MySQL 和 Redis 配置。
    """

    mysql: "MySQLConfig" = Field(default=None, description="MySQL 配置")
    redis: "RedisConfig" = Field(default=None, description="Redis 配置")

    @field_validator("mysql", mode="before")
    @classmethod
    def parse_mysql(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            from peek.database.mysql.config import MySQLConfig
            return MySQLConfig.model_validate(v)
        return v

    @field_validator("redis", mode="before")
    @classmethod
    def parse_redis(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            from peek.database.redis.config import RedisConfig
            return RedisConfig.model_validate(v)
        return v
