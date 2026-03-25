#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
校验框架模块测试
"""

import pytest

from peek.validation.rules import (
    custom,
    email,
    max_length,
    max_value,
    min_length,
    min_value,
    not_empty,
    one_of,
    pattern,
    required,
    uuid_format,
)
from peek.validation.validator import (
    FieldRule,
    Validator,
    validate,
    validate_fields,
)


# ============ 校验规则测试 ============

class TestRequiredRule:
    """required 规则测试"""

    def test_none_fails(self):
        ok, msg = required()("field", None)
        assert not ok
        assert "required" in msg

    def test_value_passes(self):
        ok, _ = required()("field", "hello")
        assert ok

    def test_empty_string_passes(self):
        """空字符串应该通过 required（由 not_empty 校验非空）"""
        ok, _ = required()("field", "")
        assert ok

    def test_zero_passes(self):
        ok, _ = required()("field", 0)
        assert ok


class TestNotEmptyRule:
    """not_empty 规则测试"""

    def test_none_fails(self):
        ok, msg = not_empty()("field", None)
        assert not ok

    def test_empty_string_fails(self):
        ok, msg = not_empty()("field", "")
        assert not ok
        assert "not be empty" in msg

    def test_empty_list_fails(self):
        ok, _ = not_empty()("field", [])
        assert not ok

    def test_empty_dict_fails(self):
        ok, _ = not_empty()("field", {})
        assert not ok

    def test_empty_bytes_fails(self):
        ok, _ = not_empty()("field", b"")
        assert not ok

    def test_non_empty_passes(self):
        ok, _ = not_empty()("field", "hello")
        assert ok

    def test_non_empty_list_passes(self):
        ok, _ = not_empty()("field", [1, 2])
        assert ok


class TestMinLengthRule:
    """min_length 规则测试"""

    def test_none_passes(self):
        """None 不校验长度"""
        ok, _ = min_length(3)("field", None)
        assert ok

    def test_short_string_fails(self):
        ok, msg = min_length(3)("field", "ab")
        assert not ok
        assert "at least 3" in msg

    def test_exact_length_passes(self):
        ok, _ = min_length(3)("field", "abc")
        assert ok

    def test_long_string_passes(self):
        ok, _ = min_length(3)("field", "abcdef")
        assert ok

    def test_list_length(self):
        ok, _ = min_length(2)("field", [1])
        assert not ok
        ok, _ = min_length(2)("field", [1, 2])
        assert ok


class TestMaxLengthRule:
    """max_length 规则测试"""

    def test_none_passes(self):
        ok, _ = max_length(5)("field", None)
        assert ok

    def test_long_string_fails(self):
        ok, msg = max_length(3)("field", "abcde")
        assert not ok
        assert "at most 3" in msg

    def test_short_string_passes(self):
        ok, _ = max_length(5)("field", "abc")
        assert ok


class TestMinValueRule:
    """min_value 规则测试"""

    def test_none_passes(self):
        ok, _ = min_value(0)("field", None)
        assert ok

    def test_below_min_fails(self):
        ok, msg = min_value(10)("field", 5)
        assert not ok
        assert "at least 10" in msg

    def test_equal_passes(self):
        ok, _ = min_value(10)("field", 10)
        assert ok

    def test_above_passes(self):
        ok, _ = min_value(10)("field", 20)
        assert ok

    def test_float_value(self):
        ok, _ = min_value(1.5)("field", 1.6)
        assert ok


class TestMaxValueRule:
    """max_value 规则测试"""

    def test_none_passes(self):
        ok, _ = max_value(100)("field", None)
        assert ok

    def test_above_max_fails(self):
        ok, msg = max_value(100)("field", 150)
        assert not ok
        assert "at most 100" in msg

    def test_equal_passes(self):
        ok, _ = max_value(100)("field", 100)
        assert ok


class TestPatternRule:
    """pattern 规则测试"""

    def test_none_passes(self):
        ok, _ = pattern(r"^\d+$")("field", None)
        assert ok

    def test_match_passes(self):
        ok, _ = pattern(r"^\d+$")("field", "12345")
        assert ok

    def test_no_match_fails(self):
        ok, msg = pattern(r"^\d+$")("field", "abc")
        assert not ok

    def test_non_string_fails(self):
        ok, msg = pattern(r"^\d+$")("field", 123)
        assert not ok
        assert "string" in msg

    def test_description_in_message(self):
        ok, msg = pattern(r"^\d+$", description="digits only")("field", "abc")
        assert "digits only" in msg


class TestOneOfRule:
    """one_of 规则测试"""

    def test_none_passes(self):
        ok, _ = one_of(["a", "b"])("field", None)
        assert ok

    def test_valid_choice_passes(self):
        ok, _ = one_of(["active", "inactive"])("field", "active")
        assert ok

    def test_invalid_choice_fails(self):
        ok, msg = one_of(["active", "inactive"])("field", "deleted")
        assert not ok
        assert "one of" in msg


class TestEmailRule:
    """email 规则测试"""

    def test_none_passes(self):
        ok, _ = email()("field", None)
        assert ok

    def test_valid_email_passes(self):
        ok, _ = email()("field", "user@example.com")
        assert ok

    def test_invalid_email_fails(self):
        ok, msg = email()("field", "not-an-email")
        assert not ok
        assert "valid email" in msg

    def test_non_string_fails(self):
        ok, _ = email()("field", 123)
        assert not ok


class TestUuidFormatRule:
    """uuid_format 规则测试"""

    def test_none_passes(self):
        ok, _ = uuid_format()("field", None)
        assert ok

    def test_valid_uuid_with_dashes(self):
        ok, _ = uuid_format()("field", "550e8400-e29b-41d4-a716-446655440000")
        assert ok

    def test_valid_uuid_without_dashes(self):
        ok, _ = uuid_format()("field", "550e8400e29b41d4a716446655440000")
        assert ok

    def test_invalid_uuid_fails(self):
        ok, msg = uuid_format()("field", "not-a-uuid")
        assert not ok


class TestCustomRule:
    """custom 规则测试"""

    def test_passes(self):
        ok, _ = custom(lambda v: v > 0, "{field} must be positive")("age", 10)
        assert ok

    def test_fails(self):
        ok, msg = custom(lambda v: v > 0, "{field} must be positive")("age", -1)
        assert not ok
        assert "age must be positive" in msg

    def test_none_passes(self):
        ok, _ = custom(lambda v: v > 0, "err")("field", None)
        assert ok

    def test_exception_in_check(self):
        """校验函数异常应返回失败"""
        ok, msg = custom(lambda v: 1 / 0, "err")("field", 1)
        assert not ok
        assert "validation failed" in msg


# ============ FieldRule 和 validate_fields 测试 ============

class TestValidateFields:
    """validate_fields 集成测试"""

    def test_all_pass(self):
        """全部通过应返回空列表"""
        data = {"name": "Alice", "age": 25}
        errors = validate_fields(data, [
            FieldRule("name", required(), min_length(2)),
            FieldRule("age", required(), min_value(0)),
        ])
        assert errors == []

    def test_first_failure_stops_field(self):
        """一个字段的第一个失败规则应停止后续规则"""
        data = {"name": None}
        errors = validate_fields(data, [
            FieldRule("name", required(), min_length(2)),
        ])
        assert len(errors) == 1
        assert errors[0].field == "name"
        assert "required" in errors[0].message

    def test_multiple_field_errors(self):
        """多个字段同时失败"""
        data = {"name": None, "email": "bad"}
        errors = validate_fields(data, [
            FieldRule("name", required()),
            FieldRule("email", email()),
        ])
        assert len(errors) == 2

    def test_dict_input(self):
        """字典输入"""
        data = {"key": "value"}
        errors = validate_fields(data, [
            FieldRule("key", required(), not_empty()),
        ])
        assert errors == []

    def test_object_input(self):
        """普通对象输入"""
        class Obj:
            name = "test"
            value = 42

        errors = validate_fields(Obj(), [
            FieldRule("name", required()),
            FieldRule("value", min_value(0)),
        ])
        assert errors == []


class TestValidateFunction:
    """validate 函数测试"""

    def test_passes_no_raise(self):
        """校验通过不应抛出异常"""
        data = {"name": "Alice"}
        validate(data, [FieldRule("name", required())])

    def test_fails_raises_validation_error(self):
        """校验失败应抛出 ValidationError"""
        from peek.errors import ValidationError
        data = {"name": None}
        with pytest.raises(ValidationError) as exc_info:
            validate(data, [FieldRule("name", required())])
        assert exc_info.value.http_status == 400
        assert "errors" in exc_info.value.details


# ============ Validator 构建器测试 ============

class TestValidatorBuilder:
    """Validator 构建器测试"""

    def test_basic_usage(self):
        """基本构建器用法"""
        v = Validator()
        v.field("name").required().min_length(2)
        v.field("age").min_value(0).max_value(150)
        errors = v.validate({"name": "Al", "age": 25})
        assert errors == []

    def test_validate_or_raise(self):
        """validate_or_raise 失败时抛出异常"""
        from peek.errors import ValidationError
        v = Validator()
        v.field("name").required()
        with pytest.raises(ValidationError):
            v.validate_or_raise({"name": None})

    def test_chain_methods(self):
        """构建器链式调用"""
        v = Validator()
        builder = v.field("email")
        result = builder.required().not_empty().email()
        # 链式调用应返回同一个 builder
        assert result is builder


if __name__ == "__main__":
    pytest.main([__file__, "-v"])