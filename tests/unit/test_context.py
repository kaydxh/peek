#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
请求上下文模块测试
"""

import contextvars
import pytest

from peek.context import (
    RequestContext,
    get_extra,
    get_request_id,
    get_trace_id,
    get_user_id,
    set_extra,
    set_request_id,
    set_trace_id,
    set_user_id,
)
from peek.context.context import _extra_var, _request_id_var, _trace_id_var, _user_id_var


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_request_id_set_get_reset(self):
        """测试 request_id 的设置、获取和重置"""
        assert get_request_id() == ""
        token = set_request_id("req-123")
        assert get_request_id() == "req-123"
        _request_id_var.reset(token)
        assert get_request_id() == ""

    def test_trace_id_set_get_reset(self):
        """测试 trace_id 的设置、获取和重置"""
        assert get_trace_id() == ""
        token = set_trace_id("trace-456")
        assert get_trace_id() == "trace-456"
        _trace_id_var.reset(token)
        assert get_trace_id() == ""

    def test_user_id_set_get_reset(self):
        """测试 user_id 的设置、获取和重置"""
        assert get_user_id() == ""
        token = set_user_id("user-789")
        assert get_user_id() == "user-789"
        _user_id_var.reset(token)
        assert get_user_id() == ""

    def test_extra_set_get(self):
        """测试 extra 的设置和获取"""
        token = set_extra("key1", "value1")
        assert get_extra("key1") == "value1"
        assert get_extra("nonexistent") is None
        _extra_var.reset(token)

    def test_extra_get_all(self):
        """测试获取完整的 extra 字典"""
        token1 = set_extra("a", 1)
        token2 = set_extra("b", 2)
        all_extra = get_extra()
        assert all_extra["a"] == 1
        assert all_extra["b"] == 2
        _extra_var.reset(token2)
        _extra_var.reset(token1)

    def test_set_extra_returns_token(self):
        """测试 set_extra 返回 contextvars.Token（修复验证）"""
        token = set_extra("test_key", "test_value")
        assert isinstance(token, contextvars.Token)
        _extra_var.reset(token)

    def test_set_extra_does_not_mutate_parent(self):
        """测试 set_extra 不会修改父上下文的 extra 字典"""
        # 先设一个基础值
        token1 = set_extra("base", "original")
        old_extra = get_extra()

        # 再设一个新值
        token2 = set_extra("child", "new")

        # 新值存在
        assert get_extra("child") == "new"
        assert get_extra("base") == "original"

        # reset 回去，child 应该消失
        _extra_var.reset(token2)
        assert get_extra("child") is None
        assert get_extra("base") == "original"

        _extra_var.reset(token1)


class TestRequestContext:
    """RequestContext 类测试"""

    def test_request_id_via_class(self):
        """通过 RequestContext 类操作 request_id"""
        token = RequestContext.set_request_id("cls-req-1")
        assert RequestContext.get_request_id() == "cls-req-1"
        RequestContext.reset_request_id(token)
        assert RequestContext.get_request_id() == ""

    def test_trace_id_via_class(self):
        """通过 RequestContext 类操作 trace_id"""
        token = RequestContext.set_trace_id("cls-trace-1")
        assert RequestContext.get_trace_id() == "cls-trace-1"
        RequestContext.reset_trace_id(token)
        assert RequestContext.get_trace_id() == ""

    def test_user_id_via_class(self):
        """通过 RequestContext 类操作 user_id"""
        token = RequestContext.set_user_id("cls-user-1")
        assert RequestContext.get_user_id() == "cls-user-1"
        RequestContext.reset_user_id(token)
        assert RequestContext.get_user_id() == ""

    def test_extra_via_class(self):
        """通过 RequestContext 类操作 extra"""
        token = RequestContext.set_extra("cls_key", "cls_value")
        assert RequestContext.get_extra("cls_key") == "cls_value"
        RequestContext.reset_extra(token)
        assert RequestContext.get_extra("cls_key") is None


class TestRequestContextScope:
    """RequestContext.scope 上下文管理器测试"""

    def test_scope_sets_request_id(self):
        """scope 应正确设置和恢复 request_id"""
        assert get_request_id() == ""
        with RequestContext.scope(request_id="scope-req"):
            assert get_request_id() == "scope-req"
        assert get_request_id() == ""

    def test_scope_sets_trace_id(self):
        """scope 应正确设置和恢复 trace_id"""
        with RequestContext.scope(trace_id="scope-trace"):
            assert get_trace_id() == "scope-trace"
        assert get_trace_id() == ""

    def test_scope_sets_user_id(self):
        """scope 应正确设置和恢复 user_id"""
        with RequestContext.scope(user_id="scope-user"):
            assert get_user_id() == "scope-user"
        assert get_user_id() == ""

    def test_scope_sets_multiple_fields(self):
        """scope 可同时设置多个字段"""
        with RequestContext.scope(
            request_id="r1",
            trace_id="t1",
            user_id="u1",
        ):
            assert get_request_id() == "r1"
            assert get_trace_id() == "t1"
            assert get_user_id() == "u1"
        assert get_request_id() == ""
        assert get_trace_id() == ""
        assert get_user_id() == ""

    def test_scope_sets_extra_kwargs(self):
        """scope 的 **kwargs 应存入 extra"""
        with RequestContext.scope(custom_field="custom_val"):
            assert get_extra("custom_field") == "custom_val"
        assert get_extra("custom_field") is None

    def test_scope_nested(self):
        """嵌套 scope 应正确隔离"""
        with RequestContext.scope(request_id="outer"):
            assert get_request_id() == "outer"
            with RequestContext.scope(request_id="inner"):
                assert get_request_id() == "inner"
            assert get_request_id() == "outer"
        assert get_request_id() == ""

    def test_scope_restores_on_exception(self):
        """scope 内抛异常时应正确恢复上下文"""
        with pytest.raises(ValueError):
            with RequestContext.scope(request_id="exc-req"):
                assert get_request_id() == "exc-req"
                raise ValueError("test exception")
        assert get_request_id() == ""

    def test_scope_none_does_not_set(self):
        """scope 传入 None 时不应设置该字段"""
        token = set_request_id("pre-existing")
        with RequestContext.scope(request_id=None, trace_id="new-trace"):
            assert get_request_id() == "pre-existing"
            assert get_trace_id() == "new-trace"
        assert get_trace_id() == ""
        _request_id_var.reset(token)


class TestLogFields:
    """RequestContext.log_fields 测试"""

    def test_log_fields_empty(self):
        """无上下文时 log_fields 返回空字典"""
        fields = RequestContext.log_fields()
        assert fields == {}

    def test_log_fields_with_values(self):
        """有上下文时 log_fields 应包含对应字段"""
        with RequestContext.scope(request_id="log-req", trace_id="log-trace", user_id="log-user"):
            fields = RequestContext.log_fields()
            assert fields["request_id"] == "log-req"
            assert fields["trace_id"] == "log-trace"
            assert fields["user_id"] == "log-user"

    def test_log_fields_partial(self):
        """只设置部分字段时 log_fields 只包含已设置的字段"""
        with RequestContext.scope(request_id="only-req"):
            fields = RequestContext.log_fields()
            assert "request_id" in fields
            assert "trace_id" not in fields
            assert "user_id" not in fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])