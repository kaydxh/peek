#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共 OpenTelemetry 安装模块（函数式接口）

提供 install_opentelemetry() 函数，将 tide/sea 配置格式转换为 peek 格式并安装 OpenTelemetry。
上层框架（如 tide）可直接调用此函数，无需重复实现 OTel 安装逻辑。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _convert_config_to_peek_format(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 tide 配置格式转换为 peek 的 OpenTelemetryConfig 格式

    tide 配置格式（兼容 sea）:
        open_telemetry:
            enabled: true
            otel_metric_exporter_type: metric_otlp
            otel_trace_exporter_type: trace_otlp
            metric_collect_duration: 60s
            otel_metric_exporter:
                otlp:
                    endpoint: "..."
                    compression: true
                    temporality_delta: true
            resource:
                service_name: "..."
                zhiyan:
                    global_app_mark: "..."

    peek 配置格式:
        enabled: true
        tracer:
            enabled: true
            exporter_type: otlp
            otlp:
                endpoint: "..."
        metric:
            enabled: true
            exporter_type: otlp
            otlp:
                endpoint: "..."
                compression: true
                temporality: delta
        resource:
            service_name: "..."
            zhiyan:
                global_app_mark: "..."
    """
    if not config:
        return {}

    # 解析 exporter 类型
    trace_exporter_type = config.get("otel_trace_exporter_type", "trace_none")
    metric_exporter_type = config.get("otel_metric_exporter_type", "metric_none")

    # 移除前缀 (trace_, metric_)
    trace_type = trace_exporter_type.replace("trace_", "")
    metric_type = metric_exporter_type.replace("metric_", "")

    # 获取原始配置
    trace_exporter_config = config.get("otel_trace_exporter", {})
    metric_exporter_config = config.get("otel_metric_exporter", {})
    resource_config = config.get("resource", {})

    # 构建 peek 格式配置
    peek_config = {
        "enabled": config.get("enabled", False),
        "resource": _convert_resource_config(resource_config),
        "tracer": _convert_tracer_config(trace_type, trace_exporter_config),
        "metric": _convert_metric_config(
            metric_type,
            metric_exporter_config,
            config.get("metric_collect_duration", "60s"),
        ),
    }

    return peek_config


def _convert_resource_config(resource_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    转换 Resource 配置

    Resource 属性要求：
    - __zhiyan_app_mark__: 上报应用标记（必填）
    - __zhiyan_env__: 环境标识（必填）
    - __zhiyan_expand_tag_enable__: 是否扩展属性到维度
    - tps.tenant.id: APM Token（Trace 上报必填）
    """
    zhiyan = resource_config.get("zhiyan", {})
    apm = resource_config.get("apm", {})
    k8s = resource_config.get("k8s", {})

    # 获取 APM Token（支持多种配置方式）
    apm_token = (
        apm.get("token", "")
        or zhiyan.get("zhiyan_apm_token", "")
        or zhiyan.get("apm_token", "")
    )

    return {
        "service_name": resource_config.get("service_name", "unknown-service"),
        "service_version": resource_config.get("service_version", ""),
        "apm_token": apm_token,
        "k8s": {
            "enabled": k8s.get("enabled", True),
        },
        "zhiyan": {
            "app_mark": zhiyan.get("app_mark", ""),
            "global_app_mark": zhiyan.get("global_app_mark", ""),
            "env": zhiyan.get("env", ""),
            "instance_mark": zhiyan.get("instance_mark", ""),
            "expand_key": zhiyan.get("expand_key", "no"),
            "data_grain": zhiyan.get("data_grain", 0),
            "data_type": zhiyan.get("data_type", ""),
            "apm_token": apm_token,  # Trace 上报需要
        },
        "attributes": resource_config.get("attrs", {}),
    }


def _convert_tracer_config(
    exporter_type: str, exporter_config: Dict[str, Any]
) -> Dict[str, Any]:
    """转换 Tracer 配置"""
    if exporter_type == "none":
        return {"enabled": False}

    otlp_config = exporter_config.get("otlp", {})
    stdout_config = exporter_config.get("stdout", {})

    tracer_config = {
        "enabled": True,
        "exporter_type": exporter_type,
    }

    if exporter_type == "otlp":
        tracer_config["otlp"] = {
            "endpoint": otlp_config.get("endpoint", "localhost:4317"),
            "protocol": otlp_config.get("protocol", "grpc"),
            "headers": otlp_config.get("headers", {}),
            "compression": otlp_config.get("compression", False),
            "insecure": otlp_config.get("insecure", True),
            "timeout": otlp_config.get("timeout", "10s"),
        }
    elif exporter_type == "stdout":
        tracer_config["stdout"] = {
            "pretty_print": stdout_config.get("pretty_print", True),
        }

    return tracer_config


def _convert_metric_config(
    exporter_type: str,
    exporter_config: Dict[str, Any],
    collect_interval: str,
) -> Dict[str, Any]:
    """转换 Metric 配置"""
    if exporter_type == "none":
        return {"enabled": False}

    otlp_config = exporter_config.get("otlp", {})
    prometheus_config = exporter_config.get("prometheus", {})
    stdout_config = exporter_config.get("stdout", {})

    metric_config = {
        "enabled": True,
        "exporter_type": exporter_type,
        "collect_interval": collect_interval,
    }

    if exporter_type == "otlp":
        # 转换 temporality_delta 为 temporality 枚举
        temporality = "delta" if otlp_config.get("temporality_delta", False) else "cumulative"

        metric_config["otlp"] = {
            "endpoint": otlp_config.get("endpoint", "localhost:4317"),
            "protocol": otlp_config.get("protocol", "grpc"),
            "headers": otlp_config.get("headers", {}),
            "compression": otlp_config.get("compression", False),
            "insecure": otlp_config.get("insecure", True),
            "timeout": otlp_config.get("timeout", "10s"),
            "temporality": temporality,
        }
    elif exporter_type == "prometheus":
        metric_config["prometheus"] = {
            "url": prometheus_config.get("url", "/metrics"),
            "namespace": prometheus_config.get("namespace", ""),
        }
    elif exporter_type == "stdout":
        metric_config["stdout"] = {
            "pretty_print": stdout_config.get("pretty_print", True),
        }

    return metric_config


async def install_opentelemetry(
    config: Dict[str, Any], web_server: Optional[Any] = None
):
    """
    安装 OpenTelemetry（使用 peek 库）。

    Args:
        config: OpenTelemetry 配置字典
        web_server: 可选的 Web 服务器实例，用于 instrument FastAPI
    """
    if not config or not config.get("enabled", False):
        logger.debug("OpenTelemetry is not enabled, skipping")
        return

    try:
        from peek.opentelemetry import OpenTelemetryService
    except ImportError:
        logger.warning(
            "peek.opentelemetry 未安装，跳过 OpenTelemetry 安装。"
            "请运行: pip install peek"
        )
        return

    try:
        # 将 tide 配置格式转换为 peek 格式
        peek_config = _convert_config_to_peek_format(config)

        logger.debug("Converted peek config: %s", peek_config)

        # 使用 peek 的 OpenTelemetryService
        service = OpenTelemetryService.from_config_dict(peek_config)
        service.install()

        # 保存 service 实例以便后续访问
        global _opentelemetry_service
        _opentelemetry_service = service

        # ========================================
        # Instrument FastAPI (禁用 http send/receive 子 Span)
        # ========================================
        if web_server is not None:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

                # 使用 exclude_spans 参数禁用 http send/receive 子 span
                # 这样每个请求只会产生一个干净的 "GET /path" span
                FastAPIInstrumentor.instrument_app(
                    web_server.app,
                    excluded_urls="health,healthz,ready,readyz,metrics",
                    exclude_spans=["receive", "send"],  # 禁用 http send/receive 子 span
                )

                logger.info("FastAPI integrated with OpenTelemetry (send/receive spans disabled)")
            except ImportError:
                logger.debug("FastAPI instrumentation not available")
            except Exception as e:
                logger.warning("FastAPI instrumentation failed: %s", e)

        logger.info(
            "OpenTelemetry installed (via peek): "
            f"tracer={peek_config.get('tracer', {}).get('exporter_type', 'none')}, "
            f"metric={peek_config.get('metric', {}).get('exporter_type', 'none')}"
        )

    except Exception as e:
        logger.error("Failed to install OpenTelemetry: %s", e)
        raise


# 全局变量保存 service 实例
_opentelemetry_service = None


def get_opentelemetry_service():
    """获取 OpenTelemetry Service 实例"""
    return _opentelemetry_service
