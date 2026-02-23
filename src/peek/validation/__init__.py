#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一参数校验模块

提供框架级别的请求参数校验能力，覆盖 HTTP 和 gRPC 两种协议。

子模块：
- peek.validation.validator: 通用校验器（支持 Pydantic 模型和 protobuf 消息）
- peek.validation.rules: 内置校验规则集
- peek.validation.decorators: 校验装饰器
"""

from peek.validation.validator import (
    Validator,
    FieldRule,
    validate,
    validate_fields,
)
from peek.validation.rules import (
    required,
    min_length,
    max_length,
    min_value,
    max_value,
    pattern,
    one_of,
    not_empty,
    email,
    uuid_format,
)
from peek.validation.decorators import (
    validated,
)

__all__ = [
    # 校验器
    "Validator",
    "FieldRule",
    "validate",
    "validate_fields",
    # 内置规则
    "required",
    "min_length",
    "max_length",
    "min_value",
    "max_value",
    "pattern",
    "one_of",
    "not_empty",
    "email",
    "uuid_format",
    # 装饰器
    "validated",
]
