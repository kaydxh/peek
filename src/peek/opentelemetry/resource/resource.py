# -*- coding: utf-8 -*-
"""
OpenTelemetry Resource 实现

提供：
- 服务资源属性
- K8s 属性自动检测
- 平台属性（APM、智研）
"""

import os
from typing import Dict, List, Optional

from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

# ========== K8s 属性键 ==========
K8S_NODE_IP_KEY = "k8s.node.ip"
K8S_POD_NAMESPACE_KEY = "k8s.namespace.name"
K8S_POD_NAME_KEY = "k8s.pod.name"
K8S_POD_IP_KEY = "k8s.pod.ip"
K8S_CONTAINER_NAME_KEY = "k8s.container.name"

# K8s 环境变量
ENV_NODE_IP = "NODE_IP"
ENV_POD_NAMESPACE = "POD_NAMESPACE"
ENV_POD_NAME = "POD_NAME"
ENV_POD_IP = "POD_IP"
ENV_CONTAINER_NAME = "CONTAINER_NAME"

# ========== 平台属性键 ==========
APM_TOKEN_KEY = "apm.token"

# 智研（ZhiYan）平台属性键 - 必须与平台要求完全一致
# 注意：这些键名是智研平台的硬编码要求，不可修改
ZHIYAN_APP_MARK_KEY = "__zhiyan_app_mark__"  # 必填：上报应用标记
ZHIYAN_INSTANCE_MARK_KEY = "__zhiyan_instance_mark__"  # 选填：实例标识
ZHIYAN_ENV_KEY = "__zhiyan_env__"  # 必填：环境标识（prod/test/dev）
ZHIYAN_EXPAND_KEY = "__zhiyan_expand_tag_enable__"  # 选填：是否扩展属性到维度（yes/no）
ZHIYAN_DATA_GRAIN_KEY = "__zhiyan_data_grain__"  # 选填：数据粒度（10/30/60）
ZHIYAN_DATA_TYPE_KEY = "__zhiyan_data_type__"  # 选填：秒级数据填"second"
ZHIYAN_TPS_TENANT_ID_KEY = "tps.tenant.id"  # Trace 上报必填：APM Token

# 保留简化版键名用于配置文件读取
ZHIYAN_CONFIG_APP_MARK_KEY = "zhiyan.app_mark"
ZHIYAN_CONFIG_GLOBAL_APP_MARK_KEY = "zhiyan.global_app_mark"
ZHIYAN_CONFIG_ENV_KEY = "zhiyan.env"


def get_k8s_attributes() -> Dict[str, str]:
    """
    从环境变量获取 K8s 属性

    自动读取以下环境变量：
    - NODE_IP → k8s.node.ip
    - POD_NAMESPACE → k8s.namespace.name
    - POD_NAME → k8s.pod.name
    - POD_IP → k8s.pod.ip
    - CONTAINER_NAME → k8s.container.name

    Returns:
        K8s 属性字典
    """
    attrs: Dict[str, str] = {}

    env_mapping = {
        ENV_NODE_IP: K8S_NODE_IP_KEY,
        ENV_POD_NAMESPACE: K8S_POD_NAMESPACE_KEY,
        ENV_POD_NAME: K8S_POD_NAME_KEY,
        ENV_POD_IP: K8S_POD_IP_KEY,
        ENV_CONTAINER_NAME: K8S_CONTAINER_NAME_KEY,
    }

    for env_var, attr_key in env_mapping.items():
        value = os.environ.get(env_var)
        if value:
            attrs[attr_key] = value

    return attrs


def get_zhiyan_attributes(
    app_mark: str = "",
    global_app_mark: str = "",
    env: str = "",
    instance_mark: str = "",
    expand_key: str = "no",
    data_grain: int = 0,
    data_type: str = "",
    apm_token: str = "",
    meter_type: str = "global",
) -> Dict[str, str]:
    """
    获取智研平台属性

    智研平台对 Resource 属性有严格的键名要求，必须使用以下格式：
    - __zhiyan_app_mark__: 上报应用标记（必填）
    - __zhiyan_env__: 环境标识（必填）
    - __zhiyan_expand_tag_enable__: 是否扩展属性到维度
    - tps.tenant.id: APM Token（Trace 上报必填）

    Args:
        app_mark: App 级别应用标识（业务指标）
        global_app_mark: Global 级别应用标识（基础设施指标）
        env: 环境标识（prod/test/dev）
        instance_mark: 实例标识
        expand_key: 是否扩展属性到维度（yes/no）
        data_grain: 数据粒度（10/30/60）
        data_type: 数据类型（秒级填"second"）
        apm_token: APM Token（Trace 上报使用）
        meter_type: Meter 类型（global/app）

    Returns:
        智研属性字典
    """
    attrs: Dict[str, str] = {}

    # 根据 meter_type 选择使用哪个 app_mark
    selected_app_mark = ""
    if meter_type == "app" and app_mark:
        selected_app_mark = app_mark
    elif meter_type == "global" and global_app_mark:
        selected_app_mark = global_app_mark

    # 只有在有 app_mark 时才添加智研属性
    if selected_app_mark:
        # 必填属性
        attrs[ZHIYAN_APP_MARK_KEY] = selected_app_mark

        # 环境（默认为 prod）
        attrs[ZHIYAN_ENV_KEY] = env if env else "prod"

        # 可选属性：实例标识
        if instance_mark:
            attrs[ZHIYAN_INSTANCE_MARK_KEY] = instance_mark

        # 可选属性：是否扩展属性到维度（默认 no）
        attrs[ZHIYAN_EXPAND_KEY] = expand_key if expand_key in ("yes", "no") else "no"

        # 可选属性：数据粒度
        if data_grain in (10, 30, 60):
            attrs[ZHIYAN_DATA_GRAIN_KEY] = str(data_grain)

        # 可选属性：数据类型
        if data_type:
            attrs[ZHIYAN_DATA_TYPE_KEY] = data_type

    # APM Token 用于 Trace 上报（独立于 app_mark）
    if apm_token:
        attrs[ZHIYAN_TPS_TENANT_ID_KEY] = apm_token

    return attrs


def create_resource(
    service_name: str = "unknown-service",
    service_version: str = "",
    service_namespace: str = "",
    deployment_environment: str = "",
    apm_token: str = "",
    enable_k8s: bool = True,
    zhiyan_app_mark: str = "",
    zhiyan_global_app_mark: str = "",
    zhiyan_env: str = "",
    zhiyan_instance_mark: str = "",
    zhiyan_expand_key: str = "no",
    zhiyan_data_grain: int = 0,
    zhiyan_data_type: str = "",
    zhiyan_apm_token: str = "",
    meter_type: str = "global",
    attributes: Optional[Dict[str, str]] = None,
) -> Resource:
    """
    创建 OpenTelemetry Resource

    包含：
    - 服务基础信息
    - K8s 属性（可选）
    - 智研平台属性（使用平台要求的键名）

    Args:
        service_name: 服务名称
        service_version: 服务版本
        service_namespace: 服务命名空间
        deployment_environment: 部署环境
        apm_token: APM Token（腾讯云）
        enable_k8s: 是否启用 K8s 属性
        zhiyan_app_mark: 智研 App 标识（业务指标）
        zhiyan_global_app_mark: 智研 Global 标识（基础设施指标）
        zhiyan_env: 智研环境（prod/test/dev）
        zhiyan_instance_mark: 智研实例标识
        zhiyan_expand_key: 是否扩展属性到维度（yes/no）
        zhiyan_data_grain: 数据粒度（10/30/60）
        zhiyan_data_type: 数据类型（秒级填"second"）
        zhiyan_apm_token: 智研 APM Token（Trace 上报）
        meter_type: Meter 类型（global/app）
        attributes: 自定义属性

    Returns:
        OpenTelemetry Resource 实例

    示例:
        ```python
        # 创建用于智研平台的 Resource
        resource = create_resource(
            service_name="my-service",
            service_version="1.0.0",
            enable_k8s=True,
            zhiyan_global_app_mark="xxxxxx",
            zhiyan_env="test",
            zhiyan_apm_token="xxxx#apm-log-xxx#17044_xxx",
            meter_type="global",
        )
        ```
    """
    attrs: Dict[str, str] = {}

    # 1. 服务基础信息
    attrs[ResourceAttributes.SERVICE_NAME] = service_name

    if service_version:
        attrs[ResourceAttributes.SERVICE_VERSION] = service_version
    if service_namespace:
        attrs[ResourceAttributes.SERVICE_NAMESPACE] = service_namespace
    if deployment_environment:
        attrs[ResourceAttributes.DEPLOYMENT_ENVIRONMENT] = deployment_environment

    # 2. K8s 属性
    if enable_k8s:
        k8s_attrs = get_k8s_attributes()
        attrs.update(k8s_attrs)

    # 3. APM Token（腾讯云）
    if apm_token:
        attrs[APM_TOKEN_KEY] = apm_token

    # 4. 智研平台属性（使用平台要求的键名）
    zhiyan_attrs = get_zhiyan_attributes(
        app_mark=zhiyan_app_mark,
        global_app_mark=zhiyan_global_app_mark,
        env=zhiyan_env,
        instance_mark=zhiyan_instance_mark,
        expand_key=zhiyan_expand_key,
        data_grain=zhiyan_data_grain,
        data_type=zhiyan_data_type,
        apm_token=zhiyan_apm_token,
        meter_type=meter_type,
    )
    attrs.update(zhiyan_attrs)

    # 5. 自定义属性
    if attributes:
        attrs.update(attributes)

    return Resource.create(attrs)


def create_resource_from_config(config, meter_type: str = "global") -> Resource:
    """
    从配置对象创建 Resource

    Args:
        config: ResourceConfig 配置对象
        meter_type: Meter 类型（global/app）

    Returns:
        OpenTelemetry Resource 实例
    """
    return create_resource(
        service_name=config.service_name,
        service_version=config.service_version,
        service_namespace=config.service_namespace,
        deployment_environment=config.deployment_environment,
        apm_token=config.apm_token,
        enable_k8s=config.k8s.enabled,
        zhiyan_app_mark=config.zhiyan.app_mark,
        zhiyan_global_app_mark=config.zhiyan.global_app_mark,
        zhiyan_env=config.zhiyan.env,
        zhiyan_instance_mark=getattr(config.zhiyan, "instance_mark", ""),
        zhiyan_expand_key=getattr(config.zhiyan, "expand_key", "no"),
        zhiyan_data_grain=getattr(config.zhiyan, "data_grain", 0),
        zhiyan_data_type=getattr(config.zhiyan, "data_type", ""),
        zhiyan_apm_token=getattr(config.zhiyan, "apm_token", ""),
        meter_type=meter_type,
        attributes=config.attributes,
    )
