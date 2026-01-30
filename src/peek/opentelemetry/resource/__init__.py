# -*- coding: utf-8 -*-
"""
OpenTelemetry Resource 模块

提供资源属性管理，包括：
- 服务信息（service.name、service.version 等）
- K8s 属性（自动从环境变量读取）
- 平台属性（APM Token、智研平台等）
"""

from peek.opentelemetry.resource.resource import (
    create_resource,
    get_k8s_attributes,
    get_zhiyan_attributes,
    K8S_NODE_IP_KEY,
    K8S_POD_NAMESPACE_KEY,
    K8S_POD_NAME_KEY,
    K8S_POD_IP_KEY,
    K8S_CONTAINER_NAME_KEY,
    APM_TOKEN_KEY,
    ZHIYAN_APP_MARK_KEY,
    ZHIYAN_GLOBAL_APP_MARK_KEY,
    ZHIYAN_ENV_KEY,
)

__all__ = [
    "create_resource",
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
    "ZHIYAN_APP_MARK_KEY",
    "ZHIYAN_GLOBAL_APP_MARK_KEY",
    "ZHIYAN_ENV_KEY",
]
