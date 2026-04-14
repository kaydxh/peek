#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通用参数校验器

支持对 Pydantic 模型和 protobuf 消息进行统一的业务规则校验。
与 Pydantic 自身的类型校验互补——Pydantic 负责类型检查，本模块负责业务规则检查。

用法示例：
    from peek.validation import validate, validate_fields, FieldRule, required, min_length

    # 方式一：基于规则列表校验
    errors = validate_fields(request, [
        FieldRule("request_id", required(), min_length(1)),
        FieldRule("name", required(), min_length(2), max_length(50)),
        FieldRule("email", required(), email()),
    ])
    if errors:
        raise ValidationError("参数校验失败", details={"errors": errors})

    # 方式二：快速校验（自动抛出 ValidationError）
    validate(request, [
        FieldRule("request_id", required()),
    ])

    # 方式三：使用 Validator 构建器
    validator = Validator()
    validator.field("request_id").required().min_length(1)
    validator.field("name").required().min_length(2).max_length(50)
    validator.validate_or_raise(request)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple, Union

logger = logging.getLogger(__name__)

# 校验规则类型：接收 (field_name, field_value) 返回 (是否通过, 错误信息)
RuleFunc = Callable[[str, Any], Tuple[bool, str]]


@dataclass
class FieldError:
    """单个字段的校验错误"""

    field: str
    message: str
    value: Any = None
    rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "field": self.field,
            "message": self.message,
        }
        if self.rule:
            result["rule"] = self.rule
        return result


@dataclass
class FieldRule:
    """
    字段校验规则

    将字段名和多个校验规则函数绑定在一起。

    Args:
        field_name: 字段名称
        *rules: 校验规则函数列表
    """

    field_name: str
    rules: List[RuleFunc] = field(default_factory=list)

    def __init__(self, field_name: str, *rules: RuleFunc):
        self.field_name = field_name
        self.rules = list(rules)


def _get_field_value(obj: Any, field_name: str) -> Any:
    """
    从对象中获取字段值

    支持 Pydantic 模型、protobuf 消息、dict 和普通对象。

    Args:
        obj: 对象实例
        field_name: 字段名称

    Returns:
        字段值
    """
    # dict
    if isinstance(obj, dict):
        return obj.get(field_name)

    # Pydantic BaseModel
    try:
        from pydantic import BaseModel

        if isinstance(obj, BaseModel):
            return getattr(obj, field_name, None)
    except ImportError:
        pass

    # protobuf Message
    try:
        from google.protobuf.message import Message

        if isinstance(obj, Message):
            if obj.HasField(field_name):
                return getattr(obj, field_name)
            # 对于标量字段，HasField 不适用，直接获取
            return getattr(obj, field_name, None)
    except (ImportError, ValueError):
        # ValueError: HasField 对标量字段会抛异常
        return getattr(obj, field_name, None)

    # 普通对象
    return getattr(obj, field_name, None)


def validate_fields(
    obj: Any,
    field_rules: List[FieldRule],
) -> List[FieldError]:
    """
    校验对象的多个字段

    Args:
        obj: 待校验的对象（Pydantic 模型、protobuf 消息、dict 等）
        field_rules: 字段校验规则列表

    Returns:
        校验错误列表，空列表表示全部通过
    """
    errors: List[FieldError] = []

    for field_rule in field_rules:
        value = _get_field_value(obj, field_rule.field_name)

        for rule in field_rule.rules:
            ok, msg = rule(field_rule.field_name, value)
            if not ok:
                errors.append(
                    FieldError(
                        field=field_rule.field_name,
                        message=msg,
                        value=value,
                        rule=getattr(rule, "__rule_name__", ""),
                    )
                )
                break  # 一个字段的第一个失败规则就停止

    return errors


def validate(
    obj: Any,
    field_rules: List[FieldRule],
    message: str = "Validation failed",
) -> None:
    """
    校验对象，不通过时自动抛出 ValidationError

    Args:
        obj: 待校验的对象
        field_rules: 字段校验规则列表
        message: 错误消息

    Raises:
        peek.errors.ValidationError: 校验不通过时抛出
    """
    errors = validate_fields(obj, field_rules)
    if errors:
        from peek.errors import ValidationError

        raise ValidationError(
            message=message,
            details={
                "errors": [e.to_dict() for e in errors],
            },
        )


class _FieldBuilder:
    """字段校验构建器（Validator 内部使用）"""

    def __init__(self, field_name: str):
        self._field_name = field_name
        self._rules: List[RuleFunc] = []

    def add_rule(self, rule: RuleFunc) -> "_FieldBuilder":
        self._rules.append(rule)
        return self

    def required(self) -> "_FieldBuilder":
        from peek.validation.rules import required as _required

        return self.add_rule(_required())

    def not_empty(self) -> "_FieldBuilder":
        from peek.validation.rules import not_empty as _not_empty

        return self.add_rule(_not_empty())

    def min_length(self, length: int) -> "_FieldBuilder":
        from peek.validation.rules import min_length as _min_length

        return self.add_rule(_min_length(length))

    def max_length(self, length: int) -> "_FieldBuilder":
        from peek.validation.rules import max_length as _max_length

        return self.add_rule(_max_length(length))

    def min_value(self, value: Union[int, float]) -> "_FieldBuilder":
        from peek.validation.rules import min_value as _min_value

        return self.add_rule(_min_value(value))

    def max_value(self, value: Union[int, float]) -> "_FieldBuilder":
        from peek.validation.rules import max_value as _max_value

        return self.add_rule(_max_value(value))

    def pattern(self, regex: str, description: str = "") -> "_FieldBuilder":
        from peek.validation.rules import pattern as _pattern

        return self.add_rule(_pattern(regex, description))

    def one_of(self, choices: list) -> "_FieldBuilder":
        from peek.validation.rules import one_of as _one_of

        return self.add_rule(_one_of(choices))

    def email(self) -> "_FieldBuilder":
        from peek.validation.rules import email as _email

        return self.add_rule(_email())

    def uuid_format(self) -> "_FieldBuilder":
        from peek.validation.rules import uuid_format as _uuid_format

        return self.add_rule(_uuid_format())

    def custom(self, rule: RuleFunc) -> "_FieldBuilder":
        """添加自定义校验规则"""
        return self.add_rule(rule)

    def build(self) -> FieldRule:
        return FieldRule(self._field_name, *self._rules)


class Validator:
    """
    链式校验器构建器

    用法：
        validator = Validator()
        validator.field("request_id").required().min_length(1)
        validator.field("name").required().min_length(2).max_length(50)

        # 校验并返回错误列表
        errors = validator.validate(request)

        # 或自动抛出 ValidationError
        validator.validate_or_raise(request)
    """

    def __init__(self, message: str = "Validation failed"):
        self._fields: List[_FieldBuilder] = []
        self._message = message

    def field(self, field_name: str) -> _FieldBuilder:
        """定义字段校验规则"""
        builder = _FieldBuilder(field_name)
        self._fields.append(builder)
        return builder

    def validate(self, obj: Any) -> List[FieldError]:
        """校验对象，返回错误列表"""
        field_rules = [fb.build() for fb in self._fields]
        return validate_fields(obj, field_rules)

    def validate_or_raise(self, obj: Any, message: str = None) -> None:
        """校验对象，不通过时抛出 ValidationError"""
        field_rules = [fb.build() for fb in self._fields]
        validate(obj, field_rules, message=message or self._message)
