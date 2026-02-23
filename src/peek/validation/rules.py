#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
内置校验规则集

提供常用的参数校验规则函数，每个函数返回一个 RuleFunc。

所有规则函数的签名为：
    rule(field_name: str, value: Any) -> Tuple[bool, str]
    返回 (是否通过, 错误信息)

用法示例：
    from peek.validation.rules import required, min_length, max_length, pattern

    rules = [
        FieldRule("name", required(), min_length(2), max_length(50)),
        FieldRule("email", required(), email()),
        FieldRule("age", required(), min_value(0), max_value(150)),
        FieldRule("status", one_of(["active", "inactive"])),
    ]
"""

import re
from typing import Any, Callable, List, Tuple, Union

# 校验规则类型
RuleFunc = Callable[[str, Any], Tuple[bool, str]]


def _make_rule(name: str, func: RuleFunc) -> RuleFunc:
    """给规则函数附加名称标记"""
    func.__rule_name__ = name
    return func


def required() -> RuleFunc:
    """
    必填校验

    验证字段值不为 None。
    对于字符串，空字符串被认为是"有值"的（使用 not_empty 来校验非空）。
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return False, f"'{field_name}' is required"
        return True, ""
    return _make_rule("required", _rule)


def not_empty() -> RuleFunc:
    """
    非空校验

    验证字段值不为 None 且不为空。
    - 字符串：不为 ""
    - 列表/集合/字典：不为空
    - bytes：不为 b""
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return False, f"'{field_name}' must not be empty"
        if isinstance(value, (str, bytes, list, tuple, set, dict)):
            if len(value) == 0:
                return False, f"'{field_name}' must not be empty"
        return True, ""
    return _make_rule("not_empty", _rule)


def min_length(length: int) -> RuleFunc:
    """
    最小长度校验

    适用于字符串、列表、bytes 等有 len() 的类型。

    Args:
        length: 最小长度
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""  # None 不校验长度，由 required 规则处理
        try:
            if len(value) < length:
                return False, f"'{field_name}' must have at least {length} characters, got {len(value)}"
        except TypeError:
            return False, f"'{field_name}' does not support length check"
        return True, ""
    return _make_rule(f"min_length({length})", _rule)


def max_length(length: int) -> RuleFunc:
    """
    最大长度校验

    适用于字符串、列表、bytes 等有 len() 的类型。

    Args:
        length: 最大长度
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        try:
            if len(value) > length:
                return False, f"'{field_name}' must have at most {length} characters, got {len(value)}"
        except TypeError:
            return False, f"'{field_name}' does not support length check"
        return True, ""
    return _make_rule(f"max_length({length})", _rule)


def min_value(minimum: Union[int, float]) -> RuleFunc:
    """
    最小值校验

    适用于数值类型。

    Args:
        minimum: 最小值
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        try:
            if value < minimum:
                return False, f"'{field_name}' must be at least {minimum}, got {value}"
        except TypeError:
            return False, f"'{field_name}' does not support value comparison"
        return True, ""
    return _make_rule(f"min_value({minimum})", _rule)


def max_value(maximum: Union[int, float]) -> RuleFunc:
    """
    最大值校验

    适用于数值类型。

    Args:
        maximum: 最大值
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        try:
            if value > maximum:
                return False, f"'{field_name}' must be at most {maximum}, got {value}"
        except TypeError:
            return False, f"'{field_name}' does not support value comparison"
        return True, ""
    return _make_rule(f"max_value({maximum})", _rule)


def pattern(regex: str, description: str = "") -> RuleFunc:
    """
    正则表达式校验

    Args:
        regex: 正则表达式
        description: 规则描述（用于错误信息）
    """
    compiled = re.compile(regex)

    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        if not isinstance(value, str):
            return False, f"'{field_name}' must be a string for pattern match"
        if not compiled.match(value):
            desc = description or f"pattern '{regex}'"
            return False, f"'{field_name}' must match {desc}"
        return True, ""
    return _make_rule(f"pattern({regex})", _rule)


def one_of(choices: list) -> RuleFunc:
    """
    枚举值校验

    Args:
        choices: 允许的值列表
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        if value not in choices:
            return False, f"'{field_name}' must be one of {choices}, got '{value}'"
        return True, ""
    return _make_rule(f"one_of({choices})", _rule)


def email() -> RuleFunc:
    """
    邮箱格式校验

    使用简单正则验证基本邮箱格式。
    """
    _pattern = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        if not isinstance(value, str):
            return False, f"'{field_name}' must be a string"
        if not _pattern.match(value):
            return False, f"'{field_name}' must be a valid email address"
        return True, ""
    return _make_rule("email", _rule)


def uuid_format() -> RuleFunc:
    """
    UUID 格式校验

    支持带/不带连字符的 UUID 格式。
    """
    _pattern = re.compile(
        r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
    )

    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        if not isinstance(value, str):
            return False, f"'{field_name}' must be a string"
        if not _pattern.match(value):
            return False, f"'{field_name}' must be a valid UUID format"
        return True, ""
    return _make_rule("uuid_format", _rule)


def custom(check: Callable[[Any], bool], message: str) -> RuleFunc:
    """
    自定义校验规则

    Args:
        check: 校验函数，接收字段值，返回是否通过
        message: 校验失败时的错误信息（可包含 {field} 占位符）

    用法：
        FieldRule("age", custom(lambda v: v >= 18, "{field} must be at least 18"))
    """
    def _rule(field_name: str, value: Any) -> Tuple[bool, str]:
        if value is None:
            return True, ""
        try:
            if not check(value):
                return False, message.format(field=field_name)
        except Exception as e:
            return False, f"'{field_name}' validation failed: {e}"
        return True, ""
    return _make_rule("custom", _rule)
