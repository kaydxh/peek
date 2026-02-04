# -*- coding: utf-8 -*-
"""
OpenTelemetry Resource 模块

提供资源属性管理，包括：
- 服务信息（service.name、service.version 等）
- K8s 属性（自动从环境变量读取）
- 智研平台属性（使用平台要求的键名）
"""

from peek.opentelemetry.resource.resource import (
    create_resource,
    create_resource_from_config,
    get_k8s_attributes,
    get_zhiyan_attributes,
    # K8s 属性键
    K8S_NODE_IP_KEY,
    K8S_POD_NAMESPACE_KEY,
    K8S_POD_NAME_KEY,
    K8S_POD_IP_KEY,
    K8S_CONTAINER_NAME_KEY,
    # 平台属性键
    APM_TOKEN_KEY,
    # 智研平台属性键（平台要求的格式）
    ZHIYAN_APP_MARK_KEY,
    ZHIYAN_INSTANCE_MARK_KEY,
    ZHIYAN_ENV_KEY,
    ZHIYAN_EXPAND_KEY,
    ZHIYAN_DATA_GRAIN_KEY,
    ZHIYAN_DATA_TYPE_KEY,
    ZHIYAN_TPS_TENANT_ID_KEY,
    # 配置文件使用的简化键名
    ZHIYAN_CONFIG_APP_MARK_KEY,
    ZHIYAN_CONFIG_GLOBAL_APP_MARK_KEY,
    ZHIYAN_CONFIG_ENV_KEY,
)

__all__ = [
    "create_resource",
    "create_resource_from_config",
    "get_k8s_attributes",
    "get_zhiyan_attributes",
    # K8s 属性键
    "K8S_NODE_IP_KEY",
    "K8S_POD_NAMESPACE_KEY",
    "K8S_POD_NAME_KEY",
    "K8S_POD_IP_KEY",
    "K8S_CONTAINER_NAME_KEY",
    # 平台属性键
    "APM_TOKEN_KEY",
    # 智研平台属性键
    "ZHIYAN_APP_MARK_KEY",
    "ZHIYAN_INSTANCE_MARK_KEY",
    "ZHIYAN_ENV_KEY",
    "ZHIYAN_EXPAND_KEY",
    "ZHIYAN_DATA_GRAIN_KEY",
    "ZHIYAN_DATA_TYPE_KEY",
    "ZHIYAN_TPS_TENANT_ID_KEY",
    "ZHIYAN_CONFIG_APP_MARK_KEY",
    "ZHIYAN_CONFIG_GLOBAL_APP_MARK_KEY",
    "ZHIYAN_CONFIG_ENV_KEY",
]
