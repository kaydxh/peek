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
ZHIYAN_APP_MARK_KEY = "zhiyan.app_mark"
ZHIYAN_GLOBAL_APP_MARK_KEY = "zhiyan.global_app_mark"
ZHIYAN_ENV_KEY = "zhiyan.env"


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
) -> Dict[str, str]:
    """
    获取智研平台属性

    Args:
        app_mark: App 级别应用标识
        global_app_mark: Global 级别应用标识
        env: 环境标识

    Returns:
        智研属性字典
    """
    attrs: Dict[str, str] = {}

    if app_mark:
        attrs[ZHIYAN_APP_MARK_KEY] = app_mark
    if global_app_mark:
        attrs[ZHIYAN_GLOBAL_APP_MARK_KEY] = global_app_mark
    if env:
        attrs[ZHIYAN_ENV_KEY] = env

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
    attributes: Optional[Dict[str, str]] = None,
) -> Resource:
    """
    创建 OpenTelemetry Resource

    包含：
    - 服务基础信息
    - K8s 属性（可选）
    - 平台属性

    Args:
        service_name: 服务名称
        service_version: 服务版本
        service_namespace: 服务命名空间
        deployment_environment: 部署环境
        apm_token: APM Token（腾讯云）
        enable_k8s: 是否启用 K8s 属性
        zhiyan_app_mark: 智研 App 标识
        zhiyan_global_app_mark: 智研 Global 标识
        zhiyan_env: 智研环境
        attributes: 自定义属性

    Returns:
        OpenTelemetry Resource 实例

    示例:
        ```python
        resource = create_resource(
            service_name="my-service",
            service_version="1.0.0",
            enable_k8s=True,
            apm_token="xxx",
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

    # 3. APM Token
    if apm_token:
        attrs[APM_TOKEN_KEY] = apm_token

    # 4. 智研属性
    zhiyan_attrs = get_zhiyan_attributes(
        app_mark=zhiyan_app_mark,
        global_app_mark=zhiyan_global_app_mark,
        env=zhiyan_env,
    )
    attrs.update(zhiyan_attrs)

    # 5. 自定义属性
    if attributes:
        attrs.update(attributes)

    return Resource.create(attrs)


def create_resource_from_config(config) -> Resource:
    """
    从配置对象创建 Resource

    Args:
        config: ResourceConfig 配置对象

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
        attributes=config.attributes,
    )
