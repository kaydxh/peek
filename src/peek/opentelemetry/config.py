# -*- coding: utf-8 -*-
"""
OpenTelemetry 配置模块

提供配置定义，支持 YAML 文件加载。
"""

import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


def parse_duration(value: Union[str, int, float]) -> float:
    """
    解析时间字符串为秒数

    支持格式：
    - 纯数字：直接作为秒数
    - "30s"：30 秒
    - "5m"：5 分钟
    - "1h"：1 小时
    - "1h30m"：1 小时 30 分钟
    - "100ms"：100 毫秒

    Args:
        value: 时间值

    Returns:
        秒数（float）
    """
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return 0.0

    value = value.strip()
    if not value:
        return 0.0

    # 纯数字
    if value.isdigit() or value.replace(".", "", 1).isdigit():
        return float(value)

    total_seconds = 0.0

    # 解析时间单位
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*h", 3600),    # 小时
        (r"(\d+(?:\.\d+)?)\s*m(?!s)", 60),  # 分钟（不匹配 ms）
        (r"(\d+(?:\.\d+)?)\s*s(?!$)", 1),   # 秒
        (r"(\d+(?:\.\d+)?)\s*ms", 0.001),   # 毫秒
        (r"(\d+(?:\.\d+)?)\s*us", 0.000001),  # 微秒
        (r"(\d+(?:\.\d+)?)\s*$", 1),         # 末尾的 s
    ]

    for pattern, multiplier in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            total_seconds += float(match.group(1)) * multiplier

    # 如果没有匹配到任何单位，尝试直接解析
    if total_seconds == 0.0:
        try:
            return float(value.rstrip("s"))
        except ValueError:
            return 0.0

    return total_seconds


class ExporterType(str, Enum):
    """导出器类型"""
    NONE = "none"
    STDOUT = "stdout"
    OTLP = "otlp"


class MetricExporterType(str, Enum):
    """Metric 导出器类型"""
    NONE = "none"
    STDOUT = "stdout"
    OTLP = "otlp"
    PROMETHEUS = "prometheus"


class OTLPProtocol(str, Enum):
    """OTLP 协议类型"""
    HTTP = "http"
    GRPC = "grpc"


class TemporalityType(str, Enum):
    """Metric Temporality 类型"""
    CUMULATIVE = "cumulative"
    DELTA = "delta"


class OTLPConfig(BaseModel):
    """OTLP 导出器配置"""
    endpoint: str = Field(default="localhost:4317", description="OTLP 端点地址")
    protocol: OTLPProtocol = Field(default=OTLPProtocol.GRPC, description="协议类型")
    headers: Dict[str, str] = Field(default_factory=dict, description="请求头")
    compression: bool = Field(default=False, description="是否启用 gzip 压缩")
    insecure: bool = Field(default=True, description="是否禁用 TLS")
    timeout: str = Field(default="10s", description="超时时间")
    temporality: TemporalityType = Field(
        default=TemporalityType.CUMULATIVE,
        description="Metric Temporality 类型（cumulative/delta）"
    )

    @property
    def timeout_seconds(self) -> float:
        """获取超时秒数"""
        return parse_duration(self.timeout)


class PrometheusConfig(BaseModel):
    """Prometheus 导出器配置"""
    url: str = Field(default="/metrics", description="Metrics 端点路径")
    namespace: str = Field(default="", description="指标命名空间前缀")
    enable_go_collector: bool = Field(default=True, description="启用 Go Runtime 采集")
    enable_process_collector: bool = Field(default=True, description="启用进程指标采集")


class StdoutConfig(BaseModel):
    """Stdout 导出器配置"""
    pretty_print: bool = Field(default=True, description="是否格式化输出")


class TracerConfig(BaseModel):
    """Tracer 配置"""
    enabled: bool = Field(default=False, description="是否启用 Tracer")
    exporter_type: ExporterType = Field(default=ExporterType.NONE, description="导出器类型")
    otlp: OTLPConfig = Field(default_factory=OTLPConfig, description="OTLP 配置")
    stdout: StdoutConfig = Field(default_factory=StdoutConfig, description="Stdout 配置")
    sample_ratio: float = Field(default=1.0, description="采样率（0.0-1.0）")
    batch_timeout: str = Field(default="5s", description="批量导出超时时间")

    @property
    def batch_timeout_seconds(self) -> float:
        """获取批量超时秒数"""
        return parse_duration(self.batch_timeout)


class MetricConfig(BaseModel):
    """Metric 配置"""
    enabled: bool = Field(default=False, description="是否启用 Metric")
    exporter_type: MetricExporterType = Field(
        default=MetricExporterType.NONE,
        description="导出器类型"
    )
    otlp: OTLPConfig = Field(default_factory=OTLPConfig, description="OTLP 配置")
    prometheus: PrometheusConfig = Field(
        default_factory=PrometheusConfig,
        description="Prometheus 配置"
    )
    stdout: StdoutConfig = Field(default_factory=StdoutConfig, description="Stdout 配置")
    collect_interval: str = Field(default="60s", description="采集间隔")

    @property
    def collect_interval_seconds(self) -> float:
        """获取采集间隔秒数"""
        return parse_duration(self.collect_interval)


class AppMeterProviderConfig(BaseModel):
    """
    App 级别的 MeterProvider 配置

    用于业务指标上报，独立于全局 MeterProvider。
    """
    enabled: bool = Field(default=False, description="是否启用 App MeterProvider")
    exporter_type: MetricExporterType = Field(
        default=MetricExporterType.OTLP,
        description="导出器类型"
    )
    otlp: OTLPConfig = Field(default_factory=OTLPConfig, description="OTLP 配置")
    collect_interval: str = Field(default="30s", description="采集间隔")

    @property
    def collect_interval_seconds(self) -> float:
        """获取采集间隔秒数"""
        return parse_duration(self.collect_interval)


class K8sConfig(BaseModel):
    """K8s 资源配置"""
    enabled: bool = Field(default=True, description="是否启用 K8s 属性")


class ZhiYanConfig(BaseModel):
    """智研平台配置"""
    app_mark: str = Field(default="", description="App 级别应用标识（业务指标）")
    global_app_mark: str = Field(default="", description="Global 级别应用标识（基础设施指标）")
    env: str = Field(default="", description="环境标识（prod/test/dev）")
    instance_mark: str = Field(default="", description="实例标识")
    expand_key: str = Field(default="no", description="是否扩展属性到维度（yes/no）")
    data_grain: int = Field(default=0, description="数据粒度（10/30/60）")
    data_type: str = Field(default="", description="数据类型（秒级填 second）")
    apm_token: str = Field(default="", description="APM Token（Trace 上报）")


class ResourceConfig(BaseModel):
    """Resource 资源配置"""
    service_name: str = Field(default="unknown-service", description="服务名称")
    service_version: str = Field(default="", description="服务版本")
    service_namespace: str = Field(default="", description="服务命名空间")
    deployment_environment: str = Field(default="", description="部署环境")
    apm_token: str = Field(default="", description="APM Token（腾讯云）")
    k8s: K8sConfig = Field(default_factory=K8sConfig, description="K8s 配置")
    zhiyan: ZhiYanConfig = Field(default_factory=ZhiYanConfig, description="智研平台配置")
    attributes: Dict[str, str] = Field(default_factory=dict, description="自定义属性")


class OpenTelemetryConfig(BaseModel):
    """OpenTelemetry 完整配置"""
    enabled: bool = Field(default=False, description="是否启用 OpenTelemetry")
    tracer: TracerConfig = Field(default_factory=TracerConfig, description="Tracer 配置")
    metric: MetricConfig = Field(default_factory=MetricConfig, description="Metric 配置")
    app_meter_provider: AppMeterProviderConfig = Field(
        default_factory=AppMeterProviderConfig,
        description="App MeterProvider 配置"
    )
    resource: ResourceConfig = Field(default_factory=ResourceConfig, description="Resource 配置")


def load_config(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    env_prefix: str = "",
) -> OpenTelemetryConfig:
    """
    加载 OpenTelemetry 配置

    优先级：环境变量 > config_dict > config_file > 默认值

    Args:
        config_file: YAML 配置文件路径
        config_dict: 配置字典
        env_prefix: 环境变量前缀

    Returns:
        OpenTelemetryConfig 实例
    """
    data: Dict[str, Any] = {}

    # 1. 从文件加载
    if config_file and os.path.exists(config_file):
        try:
            import yaml
            with open(config_file, "r", encoding="utf-8") as f:
                file_data = yaml.safe_load(f) or {}
                # 支持 open_telemetry 或 opentelemetry 作为根键
                data = file_data.get("open_telemetry") or file_data.get("opentelemetry") or file_data
        except ImportError:
            raise ImportError("PyYAML is required for loading config files. Install with: pip install pyyaml")

    # 2. 合并字典配置
    if config_dict:
        dict_data = config_dict.get("open_telemetry") or config_dict.get("opentelemetry") or config_dict
        _deep_merge(data, dict_data)

    # 3. 从环境变量覆盖（如果指定了前缀）
    if env_prefix:
        _override_from_env(data, env_prefix)

    return OpenTelemetryConfig(**data)


def load_config_from_file(config_file: str) -> OpenTelemetryConfig:
    """从 YAML 文件加载配置"""
    return load_config(config_file=config_file)


def _deep_merge(base: Dict, override: Dict) -> None:
    """深度合并字典"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _override_from_env(data: Dict, prefix: str) -> None:
    """从环境变量覆盖配置"""
    prefix = prefix.upper()

    # 定义环境变量到配置路径的映射
    env_mappings = {
        f"{prefix}_ENABLED": ("enabled",),
        f"{prefix}_TRACER_ENABLED": ("tracer", "enabled"),
        f"{prefix}_TRACER_EXPORTER_TYPE": ("tracer", "exporter_type"),
        f"{prefix}_TRACER_OTLP_ENDPOINT": ("tracer", "otlp", "endpoint"),
        f"{prefix}_METRIC_ENABLED": ("metric", "enabled"),
        f"{prefix}_METRIC_EXPORTER_TYPE": ("metric", "exporter_type"),
        f"{prefix}_METRIC_OTLP_ENDPOINT": ("metric", "otlp", "endpoint"),
        f"{prefix}_RESOURCE_SERVICE_NAME": ("resource", "service_name"),
    }

    for env_var, path in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            _set_nested(data, path, _parse_env_value(value))


def _set_nested(data: Dict, path: tuple, value: Any) -> None:
    """设置嵌套字典的值"""
    for key in path[:-1]:
        data = data.setdefault(key, {})
    data[path[-1]] = value


def _parse_env_value(value: str) -> Any:
    """解析环境变量值"""
    lower = value.lower()
    if lower in ("true", "1", "yes"):
        return True
    if lower in ("false", "0", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


class OpenTelemetryConfigBuilder:
    """OpenTelemetry 配置构建器"""

    def __init__(self):
        self._config: Dict[str, Any] = {
            "enabled": True,
            "tracer": {},
            "metric": {},
            "app_meter_provider": {},
            "resource": {},
        }

    def with_enabled(self, enabled: bool = True) -> "OpenTelemetryConfigBuilder":
        """设置是否启用"""
        self._config["enabled"] = enabled
        return self

    def with_resource(
        self,
        service_name: str,
        service_version: str = "",
        service_namespace: str = "",
        deployment_environment: str = "",
        apm_token: str = "",
        enable_k8s: bool = True,
        **attributes: str,
    ) -> "OpenTelemetryConfigBuilder":
        """设置 Resource 配置"""
        self._config["resource"] = {
            "service_name": service_name,
            "service_version": service_version,
            "service_namespace": service_namespace,
            "deployment_environment": deployment_environment,
            "apm_token": apm_token,
            "k8s": {"enabled": enable_k8s},
            "attributes": attributes,
        }
        return self

    def with_tracer_otlp(
        self,
        endpoint: str,
        protocol: str = "grpc",
        headers: Optional[Dict[str, str]] = None,
        compression: bool = False,
        insecure: bool = True,
        timeout: str = "10s",
        sample_ratio: float = 1.0,
    ) -> "OpenTelemetryConfigBuilder":
        """配置 OTLP Tracer"""
        self._config["tracer"] = {
            "enabled": True,
            "exporter_type": "otlp",
            "otlp": {
                "endpoint": endpoint,
                "protocol": protocol,
                "headers": headers or {},
                "compression": compression,
                "insecure": insecure,
                "timeout": timeout,
            },
            "sample_ratio": sample_ratio,
        }
        return self

    def with_tracer_stdout(self, pretty_print: bool = True) -> "OpenTelemetryConfigBuilder":
        """配置 Stdout Tracer"""
        self._config["tracer"] = {
            "enabled": True,
            "exporter_type": "stdout",
            "stdout": {"pretty_print": pretty_print},
        }
        return self

    def with_metric_otlp(
        self,
        endpoint: str,
        protocol: str = "grpc",
        headers: Optional[Dict[str, str]] = None,
        compression: bool = False,
        insecure: bool = True,
        timeout: str = "10s",
        temporality: str = "cumulative",
        collect_interval: str = "60s",
    ) -> "OpenTelemetryConfigBuilder":
        """配置 OTLP Metric"""
        self._config["metric"] = {
            "enabled": True,
            "exporter_type": "otlp",
            "otlp": {
                "endpoint": endpoint,
                "protocol": protocol,
                "headers": headers or {},
                "compression": compression,
                "insecure": insecure,
                "timeout": timeout,
                "temporality": temporality,
            },
            "collect_interval": collect_interval,
        }
        return self

    def with_metric_prometheus(
        self,
        url: str = "/metrics",
        namespace: str = "",
    ) -> "OpenTelemetryConfigBuilder":
        """配置 Prometheus Metric"""
        self._config["metric"] = {
            "enabled": True,
            "exporter_type": "prometheus",
            "prometheus": {
                "url": url,
                "namespace": namespace,
            },
        }
        return self

    def with_metric_stdout(self, pretty_print: bool = True) -> "OpenTelemetryConfigBuilder":
        """配置 Stdout Metric"""
        self._config["metric"] = {
            "enabled": True,
            "exporter_type": "stdout",
            "stdout": {"pretty_print": pretty_print},
        }
        return self

    def with_app_meter_provider(
        self,
        endpoint: str,
        protocol: str = "grpc",
        headers: Optional[Dict[str, str]] = None,
        compression: bool = True,
        temporality: str = "delta",
        collect_interval: str = "30s",
    ) -> "OpenTelemetryConfigBuilder":
        """
        配置 App MeterProvider（业务指标）

        Args:
            endpoint: OTLP 端点
            protocol: 协议类型（grpc/http）
            headers: 请求头
            compression: 是否压缩
            temporality: Temporality 类型（delta 用于智研平台）
            collect_interval: 采集间隔
        """
        self._config["app_meter_provider"] = {
            "enabled": True,
            "exporter_type": "otlp",
            "otlp": {
                "endpoint": endpoint,
                "protocol": protocol,
                "headers": headers or {},
                "compression": compression,
                "temporality": temporality,
            },
            "collect_interval": collect_interval,
        }
        return self

    def with_zhiyan(
        self,
        app_mark: str = "",
        global_app_mark: str = "",
        env: str = "",
        instance_mark: str = "",
        expand_key: str = "no",
        data_grain: int = 0,
        data_type: str = "",
        apm_token: str = "",
    ) -> "OpenTelemetryConfigBuilder":
        """
        配置智研平台属性

        Args:
            app_mark: App 级别应用标识（业务指标）
            global_app_mark: Global 级别应用标识（基础设施指标）
            env: 环境标识（prod/test/dev）
            instance_mark: 实例标识
            expand_key: 是否扩展属性到维度（yes/no）
            data_grain: 数据粒度（10/30/60）
            data_type: 数据类型（秒级填 second）
            apm_token: APM Token（Trace 上报）
        """
        if "resource" not in self._config:
            self._config["resource"] = {}
        self._config["resource"]["zhiyan"] = {
            "app_mark": app_mark,
            "global_app_mark": global_app_mark,
            "env": env,
            "instance_mark": instance_mark,
            "expand_key": expand_key,
            "data_grain": data_grain,
            "data_type": data_type,
            "apm_token": apm_token,
        }
        return self

    def build(self) -> OpenTelemetryConfig:
        """构建配置对象"""
        return OpenTelemetryConfig(**self._config)
