#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC 配置模块

提供 gRPC 服务器和客户端的配置管理。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class GRPCServerConfig:
    """gRPC 服务器配置"""

    host: str = "0.0.0.0"
    port: int = 50051
    max_workers: int = 10
    max_send_message_length: int = 100 * 1024 * 1024  # 100MB
    max_receive_message_length: int = 100 * 1024 * 1024  # 100MB

    # 拦截器配置
    enable_request_id: bool = True
    enable_recovery: bool = True
    enable_logging: bool = True
    enable_timer: bool = True

    # 日志配置
    log_request: bool = True
    log_response: bool = False
    slow_threshold_ms: float = 1000

    # 限流配置
    enable_qps_limit: bool = False
    qps_limit: float = 1000
    qps_burst: Optional[int] = None
    enable_concurrency_limit: bool = False
    max_concurrent: int = 100

    def to_grpc_options(self) -> List[Tuple[str, Any]]:
        """转换为 gRPC 选项"""
        return [
            ("grpc.max_send_message_length", self.max_send_message_length),
            ("grpc.max_receive_message_length", self.max_receive_message_length),
        ]


@dataclass
class GRPCClientConfig:
    """gRPC 客户端配置"""

    target: str = "localhost:50051"
    max_send_message_length: int = 100 * 1024 * 1024
    max_receive_message_length: int = 100 * 1024 * 1024
    timeout_seconds: float = 30.0

    # 重试配置
    enable_retry: bool = True
    max_retries: int = 3
    retry_backoff_ms: int = 100

    # 负载均衡
    load_balancing_policy: str = "round_robin"

    def to_grpc_options(self) -> List[Tuple[str, Any]]:
        """转换为 gRPC 选项"""
        options = [
            ("grpc.max_send_message_length", self.max_send_message_length),
            ("grpc.max_receive_message_length", self.max_receive_message_length),
        ]

        if self.load_balancing_policy:
            options.append((
                "grpc.lb_policy_name",
                self.load_balancing_policy,
            ))

        return options


@dataclass
class GRPCGatewayConfig:
    """gRPC Gateway 配置"""

    host: str = "0.0.0.0"
    http_port: int = 8080
    grpc_port: int = 50051

    # API 文档
    title: str = "gRPC Gateway"
    description: str = ""
    version: str = "1.0.0"

    # gRPC 配置
    grpc: GRPCServerConfig = field(default_factory=GRPCServerConfig)

    # 健康检查
    enable_health_check: bool = True

    # 优雅关闭
    shutdown_delay_seconds: float = 0
    shutdown_timeout_seconds: float = 30


@dataclass
class GRPCConfig:
    """gRPC 完整配置"""

    server: GRPCServerConfig = field(default_factory=GRPCServerConfig)
    client: GRPCClientConfig = field(default_factory=GRPCClientConfig)
    gateway: GRPCGatewayConfig = field(default_factory=GRPCGatewayConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GRPCConfig":
        """从字典创建配置"""
        config = cls()

        if "server" in data:
            server_data = data["server"]
            config.server = GRPCServerConfig(
                host=server_data.get("host", config.server.host),
                port=server_data.get("port", config.server.port),
                max_workers=server_data.get("max_workers", config.server.max_workers),
                max_send_message_length=server_data.get(
                    "max_send_message_length", config.server.max_send_message_length
                ),
                max_receive_message_length=server_data.get(
                    "max_receive_message_length", config.server.max_receive_message_length
                ),
                enable_request_id=server_data.get(
                    "enable_request_id", config.server.enable_request_id
                ),
                enable_recovery=server_data.get(
                    "enable_recovery", config.server.enable_recovery
                ),
                enable_logging=server_data.get(
                    "enable_logging", config.server.enable_logging
                ),
                enable_timer=server_data.get("enable_timer", config.server.enable_timer),
                log_request=server_data.get("log_request", config.server.log_request),
                log_response=server_data.get("log_response", config.server.log_response),
                slow_threshold_ms=server_data.get(
                    "slow_threshold_ms", config.server.slow_threshold_ms
                ),
                enable_qps_limit=server_data.get(
                    "enable_qps_limit", config.server.enable_qps_limit
                ),
                qps_limit=server_data.get("qps_limit", config.server.qps_limit),
                qps_burst=server_data.get("qps_burst", config.server.qps_burst),
                enable_concurrency_limit=server_data.get(
                    "enable_concurrency_limit", config.server.enable_concurrency_limit
                ),
                max_concurrent=server_data.get(
                    "max_concurrent", config.server.max_concurrent
                ),
            )

        if "client" in data:
            client_data = data["client"]
            config.client = GRPCClientConfig(
                target=client_data.get("target", config.client.target),
                max_send_message_length=client_data.get(
                    "max_send_message_length", config.client.max_send_message_length
                ),
                max_receive_message_length=client_data.get(
                    "max_receive_message_length", config.client.max_receive_message_length
                ),
                timeout_seconds=client_data.get(
                    "timeout_seconds", config.client.timeout_seconds
                ),
                enable_retry=client_data.get("enable_retry", config.client.enable_retry),
                max_retries=client_data.get("max_retries", config.client.max_retries),
                retry_backoff_ms=client_data.get(
                    "retry_backoff_ms", config.client.retry_backoff_ms
                ),
                load_balancing_policy=client_data.get(
                    "load_balancing_policy", config.client.load_balancing_policy
                ),
            )

        if "gateway" in data:
            gateway_data = data["gateway"]
            config.gateway = GRPCGatewayConfig(
                host=gateway_data.get("host", config.gateway.host),
                http_port=gateway_data.get("http_port", config.gateway.http_port),
                grpc_port=gateway_data.get("grpc_port", config.gateway.grpc_port),
                title=gateway_data.get("title", config.gateway.title),
                description=gateway_data.get("description", config.gateway.description),
                version=gateway_data.get("version", config.gateway.version),
                enable_health_check=gateway_data.get(
                    "enable_health_check", config.gateway.enable_health_check
                ),
                shutdown_delay_seconds=gateway_data.get(
                    "shutdown_delay_seconds", config.gateway.shutdown_delay_seconds
                ),
                shutdown_timeout_seconds=gateway_data.get(
                    "shutdown_timeout_seconds", config.gateway.shutdown_timeout_seconds
                ),
            )

        return config

    @classmethod
    def from_yaml(cls, path: str) -> "GRPCConfig":
        """从 YAML 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data.get("grpc", {}))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "max_workers": self.server.max_workers,
                "max_send_message_length": self.server.max_send_message_length,
                "max_receive_message_length": self.server.max_receive_message_length,
                "enable_request_id": self.server.enable_request_id,
                "enable_recovery": self.server.enable_recovery,
                "enable_logging": self.server.enable_logging,
                "enable_timer": self.server.enable_timer,
                "log_request": self.server.log_request,
                "log_response": self.server.log_response,
                "slow_threshold_ms": self.server.slow_threshold_ms,
                "enable_qps_limit": self.server.enable_qps_limit,
                "qps_limit": self.server.qps_limit,
                "qps_burst": self.server.qps_burst,
                "enable_concurrency_limit": self.server.enable_concurrency_limit,
                "max_concurrent": self.server.max_concurrent,
            },
            "client": {
                "target": self.client.target,
                "max_send_message_length": self.client.max_send_message_length,
                "max_receive_message_length": self.client.max_receive_message_length,
                "timeout_seconds": self.client.timeout_seconds,
                "enable_retry": self.client.enable_retry,
                "max_retries": self.client.max_retries,
                "retry_backoff_ms": self.client.retry_backoff_ms,
                "load_balancing_policy": self.client.load_balancing_policy,
            },
            "gateway": {
                "host": self.gateway.host,
                "http_port": self.gateway.http_port,
                "grpc_port": self.gateway.grpc_port,
                "title": self.gateway.title,
                "description": self.gateway.description,
                "version": self.gateway.version,
                "enable_health_check": self.gateway.enable_health_check,
                "shutdown_delay_seconds": self.gateway.shutdown_delay_seconds,
                "shutdown_timeout_seconds": self.gateway.shutdown_timeout_seconds,
            },
        }
