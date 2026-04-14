#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gRPC 参数校验拦截器

为 gRPC 请求提供统一的参数校验能力。
支持两种校验模式：
1. 全局规则注册：为指定 method 注册校验规则
2. @validated 装饰器：直接装饰 Servicer 方法

用法示例：
    from peek.validation.grpc_interceptor import ValidationInterceptor

    # 创建拦截器
    interceptor = ValidationInterceptor()

    # 注册方法级校验规则
    interceptor.register_rules(
        "/my.service.MyService/CreateUser",
        [
            FieldRule("name", required(), min_length(2), max_length(50)),
            FieldRule("email", required(), email()),
        ]
    )

    # 添加到拦截器链
    chain.add(interceptor)
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List

import grpc

from peek.net.grpc.interceptor import UnaryServerInterceptor, get_request_id

if TYPE_CHECKING:
    from peek.validation.rules import FieldRule

logger = logging.getLogger(__name__)


class ValidationInterceptor(UnaryServerInterceptor):
    """
    gRPC 参数校验拦截器

    为 gRPC 请求提供统一的参数校验。
    校验失败时返回 INVALID_ARGUMENT 状态码。

    支持两种使用方式：
    1. 通过 register_rules() 注册方法级校验规则
    2. 通过 @validated 装饰器直接装饰 Servicer 方法（两者可以叠加）
    """

    def __init__(self):
        """初始化校验拦截器"""
        # method_name -> [FieldRule, ...]
        self._rules: Dict[str, List] = {}

    def register_rules(
        self,
        method: str,
        rules: List["FieldRule"],
    ) -> "ValidationInterceptor":
        """
        注册方法级校验规则

        Args:
            method: gRPC 方法全名（如 /package.Service/Method）
            rules: 字段校验规则列表

        Returns:
            self，支持链式调用
        """
        self._rules[method] = rules
        return self

    def intercept_unary(
        self,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
        handler: Callable[[Any, grpc.ServicerContext], Any],
    ) -> Any:
        """拦截 Unary 请求并执行校验"""
        rules = self._rules.get(method_name)
        if rules:
            from peek.validation.validator import validate_fields

            errors = validate_fields(request, rules)
            if errors:
                request_id = get_request_id() or "unknown"
                error_msgs = [f"{e.field}: {e.message}" for e in errors]
                detail = "; ".join(error_msgs)
                logger.warning(
                    f"[{request_id}] gRPC validation failed for {method_name}: {detail}"
                )
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"Validation failed: {detail}",
                )

        return handler(request, context)
