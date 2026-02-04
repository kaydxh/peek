#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebServer 配置模块

参考 Go 版本 golang 库的 webserver.proto 配置结构，提供：
- Pydantic 配置模型
- YAML 配置文件加载
- 配置验证
- 默认值处理

示例 YAML 配置:
```yaml
web:
  bind_address:
    host: "0.0.0.0"
    port: 8080
  grpc:
    port: 50051
    max_receive_message_size: 104857600  # 100MB
    max_send_message_size: 104857600
    max_workers: 10
    timeout: 30s
  http:
    timeout: 30s
    max_request_body_bytes: 0
  debug:
    enable_profiling: true
  open_telemetry:
    enabled: true
    service_name: "my-service"
```
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# ======================== 时间解析工具 ========================


def parse_duration(value: Union[str, int, float, None]) -> float:
    """
    解析时间字符串为秒数

    支持格式:
    - 纯数字: 直接作为秒数
    - "30s": 30 秒
    - "5m": 5 分钟
    - "1h": 1 小时
    - "1h30m": 1 小时 30 分钟
    - "100ms": 100 毫秒
    - "1.5s": 1.5 秒

    Args:
        value: 时间字符串或数字

    Returns:
        秒数（float）
    """
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return 0.0

    value = value.strip().lower()
    if not value:
        return 0.0

    # 纯数字
    try:
        return float(value)
    except ValueError:
        pass

    # 解析时间单位
    total_seconds = 0.0
    pattern = r'(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)?'
    matches = re.findall(pattern, value)

    unit_multipliers = {
        'ms': 0.001,
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        '': 1,  # 默认秒
    }

    for num_str, unit in matches:
        num = float(num_str)
        multiplier = unit_multipliers.get(unit, 1)
        total_seconds += num * multiplier

    return total_seconds


# ======================== 配置模型定义 ========================


class NetConfig(BaseModel):
    """网络地址配置"""

    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8080, ge=1, le=65535, description="监听端口")


class GrpcConfig(BaseModel):
    """gRPC 配置"""

    port: Optional[int] = Field(
        default=None, ge=1, le=65535, description="gRPC 端口（None 表示不启用）"
    )
    max_receive_message_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        ge=0,
        description="最大接收消息大小（字节）",
    )
    max_send_message_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        ge=0,
        description="最大发送消息大小（字节）",
    )
    max_workers: int = Field(default=10, ge=1, description="gRPC 线程池大小")
    timeout: float = Field(default=0, ge=0, description="gRPC 超时时间（秒）")

    @field_validator("timeout", mode="before")
    @classmethod
    def parse_timeout(cls, v):
        """解析超时时间"""
        return parse_duration(v)


class HttpConfig(BaseModel):
    """HTTP 配置"""

    timeout: float = Field(default=0, ge=0, description="HTTP 超时时间（秒），0 表示不限制")
    max_request_body_bytes: int = Field(
        default=0, ge=0, description="最大请求体大小（字节），0 表示不限制"
    )
    docs_url: str = Field(default="/docs", description="Swagger UI 文档地址")
    redoc_url: str = Field(default="/redoc", description="ReDoc 文档地址")
    openapi_url: str = Field(default="/openapi.json", description="OpenAPI JSON 地址")

    @field_validator("timeout", mode="before")
    @classmethod
    def parse_timeout(cls, v):
        """解析超时时间"""
        return parse_duration(v)


class DebugConfig(BaseModel):
    """调试配置"""

    enable_profiling: bool = Field(default=False, description="启用性能分析")
    disable_print_inoutput_methods: List[str] = Field(
        default_factory=list, description="禁用输入输出打印的方法列表"
    )


class OtelResourceConfig(BaseModel):
    """OpenTelemetry 资源配置"""

    service_name: str = Field(default="", description="服务名称")
    attrs: Dict[str, str] = Field(default_factory=dict, description="额外属性")


class OtelPrometheusConfig(BaseModel):
    """Prometheus 配置"""

    url: str = Field(default="", description="Prometheus URL")


class OtelJaegerConfig(BaseModel):
    """Jaeger 配置"""

    url: str = Field(default="", description="Jaeger URL")


class OtelStdoutConfig(BaseModel):
    """Stdout 导出配置"""

    pretty_print: bool = Field(default=False, description="格式化输出")


class OtelMetricExporterConfig(BaseModel):
    """Metric 导出器配置"""

    prometheus: Optional[OtelPrometheusConfig] = None
    stdout: Optional[OtelStdoutConfig] = None


class OtelTraceExporterConfig(BaseModel):
    """Trace 导出器配置"""

    jaeger: Optional[OtelJaegerConfig] = None
    stdout: Optional[OtelStdoutConfig] = None


class OpenTelemetryConfig(BaseModel):
    """OpenTelemetry 配置"""

    enabled: bool = Field(default=False, description="是否启用")
    metric_collect_duration: float = Field(
        default=60, ge=0, description="指标收集间隔（秒）"
    )
    otel_trace_exporter_type: str = Field(
        default="trace_none",
        description="Trace 导出类型: trace_none, trace_stdout, trace_otlp, trace_jaeger, trace_zipkin",
    )
    otel_metric_exporter_type: str = Field(
        default="metric_none",
        description="Metric 导出类型: metric_none, metric_stdout, metric_otlp, metric_prometheus",
    )
    otel_log_exporter_type: str = Field(
        default="log_none", description="Log 导出类型: log_none, log_otlp"
    )
    otel_metric_exporter: Optional[OtelMetricExporterConfig] = None
    otel_trace_exporter: Optional[OtelTraceExporterConfig] = None
    resource: Optional[OtelResourceConfig] = None

    @field_validator("metric_collect_duration", mode="before")
    @classmethod
    def parse_duration(cls, v):
        """解析时间"""
        return parse_duration(v)


class ShutdownConfig(BaseModel):
    """关闭配置"""

    delay_duration: float = Field(default=0, ge=0, description="关闭延迟时间（秒）")
    timeout_duration: float = Field(default=5.0, ge=0, description="关闭超时时间（秒）")

    @field_validator("delay_duration", "timeout_duration", mode="before")
    @classmethod
    def parse_duration(cls, v):
        """解析时间"""
        return parse_duration(v)


class MethodQPSConfigItem(BaseModel):
    """方法/路径级 QPS 配置项"""

    method: str = Field(default="*", description="HTTP 方法（GET, POST, *）或 gRPC 方法")
    path: str = Field(default="/", description="路径，支持前缀匹配（以 * 结尾）")
    qps: float = Field(default=0, ge=0, description="QPS 限制")
    burst: int = Field(default=0, ge=0, description="突发容量")
    max_concurrency: int = Field(default=0, ge=0, description="最大并发数")


class QPSLimitConfig(BaseModel):
    """QPS 限流配置"""

    default_qps: float = Field(default=0, ge=0, description="默认 QPS（0 表示不限制）")
    default_burst: int = Field(default=0, ge=0, description="默认突发容量")
    max_concurrency: int = Field(default=0, ge=0, description="最大并发数（0 表示不限制）")
    wait_timeout: float = Field(
        default=0, ge=0, description="等待超时时间（秒），0 表示不等待"
    )
    method_qps: List[MethodQPSConfigItem] = Field(
        default_factory=list, description="方法级配置列表"
    )

    @field_validator("wait_timeout", mode="before")
    @classmethod
    def parse_wait_timeout(cls, v):
        """解析等待超时"""
        return parse_duration(v)


class WebConfig(BaseModel):
    """
    Web 服务器完整配置

    对应 Go 版本的 webserver.proto 中的 Web message
    """

    bind_address: NetConfig = Field(default_factory=NetConfig, description="绑定地址")
    grpc: GrpcConfig = Field(default_factory=GrpcConfig, description="gRPC 配置")
    http: HttpConfig = Field(default_factory=HttpConfig, description="HTTP 配置")
    debug: DebugConfig = Field(default_factory=DebugConfig, description="调试配置")
    open_telemetry: OpenTelemetryConfig = Field(
        default_factory=OpenTelemetryConfig, description="OpenTelemetry 配置"
    )
    shutdown: ShutdownConfig = Field(
        default_factory=ShutdownConfig, description="关闭配置"
    )

    # 限流配置
    http_qps_limit: Optional[QPSLimitConfig] = Field(
        default=None, description="HTTP QPS 限流配置"
    )
    grpc_qps_limit: Optional[QPSLimitConfig] = Field(
        default=None, description="gRPC QPS 限流配置"
    )

    # 额外配置（非 proto 定义）
    title: str = Field(default="Web Server", description="API 标题")
    description: str = Field(default="", description="API 描述")
    version: str = Field(default="1.0.0", description="API 版本")
    server_id: str = Field(default="", description="服务器 ID")

    @model_validator(mode="after")
    def set_defaults(self):
        """设置默认值"""
        if not self.server_id:
            self.server_id = f"webserver-{self.bind_address.port}"
        return self


class AppConfig(BaseModel):
    """
    应用配置根节点

    支持从 YAML 文件加载完整配置
    """

    web: WebConfig = Field(default_factory=WebConfig, description="Web 服务器配置")

    # 可以扩展其他配置节点
    # database: DatabaseConfig = ...
    # redis: RedisConfig = ...


# ======================== 配置加载器 ========================


class ConfigLoader:
    """
    配置加载器

    支持从 YAML 文件、字典或环境变量加载配置
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置加载器

        Args:
            config_file: YAML 配置文件路径
        """
        self.config_file = config_file
        self._raw_config: Dict[str, Any] = {}
        self._config: Optional[AppConfig] = None

    def load(self) -> "ConfigLoader":
        """
        加载配置

        Returns:
            self，支持链式调用
        """
        if self.config_file:
            self._load_from_file(self.config_file)
        return self

    def _load_from_file(self, file_path: str) -> None:
        """从文件加载配置"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            self._raw_config = yaml.safe_load(f) or {}

        logger.info(f"Loaded config from {file_path}")

    def load_from_dict(self, config_dict: Dict[str, Any]) -> "ConfigLoader":
        """
        从字典加载配置

        Args:
            config_dict: 配置字典

        Returns:
            self
        """
        self._raw_config = config_dict
        return self

    def load_from_env(self, prefix: str = "PEEK") -> "ConfigLoader":
        """
        从环境变量加载配置

        环境变量格式: {PREFIX}_WEB_BIND_ADDRESS_HOST

        Args:
            prefix: 环境变量前缀

        Returns:
            self
        """
        env_config = {}

        for key, value in os.environ.items():
            if not key.startswith(f"{prefix}_"):
                continue

            # 解析环境变量路径
            parts = key[len(prefix) + 1 :].lower().split("_")
            self._set_nested_value(env_config, parts, value)

        # 合并到现有配置
        self._deep_merge(self._raw_config, env_config)
        return self

    def _set_nested_value(
        self, config: Dict, keys: List[str], value: str
    ) -> None:
        """设置嵌套字典值"""
        for key in keys[:-1]:
            config = config.setdefault(key, {})

        # 尝试转换类型
        final_key = keys[-1]
        if value.lower() in ("true", "false"):
            config[final_key] = value.lower() == "true"
        elif value.isdigit():
            config[final_key] = int(value)
        else:
            try:
                config[final_key] = float(value)
            except ValueError:
                config[final_key] = value

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def get_config(self) -> AppConfig:
        """
        获取解析后的配置

        Returns:
            AppConfig 实例
        """
        if self._config is None:
            self._config = AppConfig(**self._raw_config)
        return self._config

    def get_web_config(self) -> WebConfig:
        """
        获取 Web 服务器配置

        Returns:
            WebConfig 实例
        """
        return self.get_config().web

    def get_raw_config(self) -> Dict[str, Any]:
        """获取原始配置字典"""
        return self._raw_config


# ======================== 便捷函数 ========================


def load_config(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    env_prefix: Optional[str] = None,
) -> WebConfig:
    """
    加载 Web 服务器配置

    优先级: config_dict > config_file > env_prefix > 默认值

    Args:
        config_file: YAML 配置文件路径
        config_dict: 配置字典
        env_prefix: 环境变量前缀

    Returns:
        WebConfig 实例

    示例:
        ```python
        # 从 YAML 文件加载
        config = load_config(config_file="config.yaml")

        # 从字典加载
        config = load_config(config_dict={
            "web": {
                "bind_address": {"host": "0.0.0.0", "port": 8080}
            }
        })

        # 从环境变量加载
        config = load_config(env_prefix="MYAPP")
        ```
    """
    loader = ConfigLoader(config_file)

    if config_file:
        loader.load()

    if config_dict:
        loader.load_from_dict(config_dict)

    if env_prefix:
        loader.load_from_env(env_prefix)

    return loader.get_web_config()


def load_config_from_file(file_path: str) -> WebConfig:
    """
    从 YAML 文件加载配置

    Args:
        file_path: YAML 文件路径

    Returns:
        WebConfig 实例
    """
    return load_config(config_file=file_path)


# ======================== 配置 Builder ========================


class WebServerConfigBuilder:
    """
    WebServer 配置构建器

    提供流式 API 构建配置

    示例:
        ```python
        config = (
            WebServerConfigBuilder()
            .with_bind_address("0.0.0.0", 8080)
            .with_grpc(port=50051, max_workers=20)
            .with_http(timeout="30s")
            .with_shutdown(delay="5s", timeout="10s")
            .build()
        )
        ```
    """

    def __init__(self):
        self._config_dict: Dict[str, Any] = {"web": {}}

    def with_bind_address(self, host: str = "0.0.0.0", port: int = 8080) -> "WebServerConfigBuilder":
        """设置绑定地址"""
        self._config_dict["web"]["bind_address"] = {"host": host, "port": port}
        return self

    def with_grpc(
        self,
        port: Optional[int] = None,
        max_receive_message_size: int = 100 * 1024 * 1024,
        max_send_message_size: int = 100 * 1024 * 1024,
        max_workers: int = 10,
        timeout: Union[str, float] = 0,
    ) -> "WebServerConfigBuilder":
        """设置 gRPC 配置"""
        self._config_dict["web"]["grpc"] = {
            "port": port,
            "max_receive_message_size": max_receive_message_size,
            "max_send_message_size": max_send_message_size,
            "max_workers": max_workers,
            "timeout": timeout,
        }
        return self

    def with_http(
        self,
        timeout: Union[str, float] = 0,
        max_request_body_bytes: int = 0,
        docs_url: str = "/docs",
        redoc_url: str = "/redoc",
    ) -> "WebServerConfigBuilder":
        """设置 HTTP 配置"""
        self._config_dict["web"]["http"] = {
            "timeout": timeout,
            "max_request_body_bytes": max_request_body_bytes,
            "docs_url": docs_url,
            "redoc_url": redoc_url,
        }
        return self

    def with_debug(
        self,
        enable_profiling: bool = False,
        disable_print_inoutput_methods: Optional[List[str]] = None,
    ) -> "WebServerConfigBuilder":
        """设置调试配置"""
        self._config_dict["web"]["debug"] = {
            "enable_profiling": enable_profiling,
            "disable_print_inoutput_methods": disable_print_inoutput_methods or [],
        }
        return self

    def with_open_telemetry(
        self,
        enabled: bool = False,
        service_name: str = "",
        trace_exporter_type: str = "trace_none",
        metric_exporter_type: str = "metric_none",
    ) -> "WebServerConfigBuilder":
        """设置 OpenTelemetry 配置"""
        self._config_dict["web"]["open_telemetry"] = {
            "enabled": enabled,
            "otel_trace_exporter_type": trace_exporter_type,
            "otel_metric_exporter_type": metric_exporter_type,
            "resource": {"service_name": service_name},
        }
        return self

    def with_shutdown(
        self,
        delay: Union[str, float] = 0,
        timeout: Union[str, float] = "5s",
    ) -> "WebServerConfigBuilder":
        """设置关闭配置"""
        self._config_dict["web"]["shutdown"] = {
            "delay_duration": delay,
            "timeout_duration": timeout,
        }
        return self

    def with_metadata(
        self,
        title: str = "Web Server",
        description: str = "",
        version: str = "1.0.0",
        server_id: str = "",
    ) -> "WebServerConfigBuilder":
        """设置元数据"""
        self._config_dict["web"]["title"] = title
        self._config_dict["web"]["description"] = description
        self._config_dict["web"]["version"] = version
        self._config_dict["web"]["server_id"] = server_id
        return self

    def build(self) -> WebConfig:
        """构建配置"""
        return load_config(config_dict=self._config_dict)
