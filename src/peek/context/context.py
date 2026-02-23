#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
请求上下文核心实现

基于 Python contextvars 实现请求级别的上下文传播，
中间件/拦截器自动设置，业务代码可在任意层读取当前请求的上下文信息。

使用场景：
- HTTP 中间件设置 request_id/trace_id
- gRPC 拦截器设置 request_id/trace_id
- 日志 Formatter 自动提取 request_id
- 业务代码读取当前用户信息

用法示例：
    from peek.context import RequestContext, get_request_id

    # 在中间件中设置
    token = RequestContext.set_request_id("abc-123")
    try:
        ...
    finally:
        RequestContext.reset_request_id(token)

    # 在业务代码中读取
    rid = get_request_id()

    # 使用上下文管理器（推荐）
    with RequestContext.scope(request_id="abc-123", trace_id="trace-456"):
        print(get_request_id())  # abc-123
"""

import contextvars
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

# ============ Context Variables ============

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
_user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_id", default=""
)
_extra_var: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "context_extra", default={}
)


# ============ 便捷函数 ============

def get_request_id() -> str:
    """获取当前请求的 Request ID"""
    return _request_id_var.get()


def set_request_id(value: str) -> contextvars.Token:
    """设置当前请求的 Request ID，返回 Token 用于 reset"""
    return _request_id_var.set(value)


def get_trace_id() -> str:
    """获取当前请求的 Trace ID"""
    return _trace_id_var.get()


def set_trace_id(value: str) -> contextvars.Token:
    """设置当前请求的 Trace ID，返回 Token 用于 reset"""
    return _trace_id_var.set(value)


def get_user_id() -> str:
    """获取当前请求的 User ID"""
    return _user_id_var.get()


def set_user_id(value: str) -> contextvars.Token:
    """设置当前请求的 User ID，返回 Token 用于 reset"""
    return _user_id_var.set(value)


def get_extra(key: str = None) -> Any:
    """
    获取当前请求的额外上下文信息

    Args:
        key: 如果指定，返回对应的值；否则返回整个字典

    Returns:
        指定 key 的值，或整个字典
    """
    extra = _extra_var.get()
    if key is not None:
        return extra.get(key)
    return extra


def set_extra(key: str, value: Any) -> None:
    """
    设置当前请求的额外上下文信息

    Args:
        key: 键名
        value: 值
    """
    extra = _extra_var.get()
    # 创建新字典以避免影响父上下文
    new_extra = dict(extra)
    new_extra[key] = value
    _extra_var.set(new_extra)


# ============ RequestContext 类 ============

class RequestContext:
    """
    请求上下文管理器

    提供静态方法设置/获取/重置上下文变量，以及上下文管理器支持。
    """

    # ---- request_id ----
    @staticmethod
    def get_request_id() -> str:
        return get_request_id()

    @staticmethod
    def set_request_id(value: str) -> contextvars.Token:
        return set_request_id(value)

    @staticmethod
    def reset_request_id(token: contextvars.Token) -> None:
        _request_id_var.reset(token)

    # ---- trace_id ----
    @staticmethod
    def get_trace_id() -> str:
        return get_trace_id()

    @staticmethod
    def set_trace_id(value: str) -> contextvars.Token:
        return set_trace_id(value)

    @staticmethod
    def reset_trace_id(token: contextvars.Token) -> None:
        _trace_id_var.reset(token)

    # ---- user_id ----
    @staticmethod
    def get_user_id() -> str:
        return get_user_id()

    @staticmethod
    def set_user_id(value: str) -> contextvars.Token:
        return set_user_id(value)

    @staticmethod
    def reset_user_id(token: contextvars.Token) -> None:
        _user_id_var.reset(token)

    # ---- extra ----
    @staticmethod
    def get_extra(key: str = None) -> Any:
        return get_extra(key)

    @staticmethod
    def set_extra(key: str, value: Any) -> None:
        set_extra(key, value)

    # ---- 上下文管理器 ----
    @staticmethod
    @contextmanager
    def scope(
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Iterator[None]:
        """
        上下文管理器，自动设置和恢复上下文变量

        用法：
            with RequestContext.scope(request_id="abc-123"):
                # 在此范围内 get_request_id() 返回 "abc-123"
                do_something()
            # 退出后恢复原值

        Args:
            request_id: 请求 ID
            trace_id: 追踪 ID
            user_id: 用户 ID
            **kwargs: 额外的上下文变量（存入 extra 字典）
        """
        tokens = []

        if request_id is not None:
            tokens.append(("request_id", _request_id_var.set(request_id)))
        if trace_id is not None:
            tokens.append(("trace_id", _trace_id_var.set(trace_id)))
        if user_id is not None:
            tokens.append(("user_id", _user_id_var.set(user_id)))
        if kwargs:
            old_extra = _extra_var.get()
            new_extra = dict(old_extra)
            new_extra.update(kwargs)
            tokens.append(("extra", _extra_var.set(new_extra)))

        try:
            yield
        finally:
            # 按反序恢复
            for name, token in reversed(tokens):
                var_map = {
                    "request_id": _request_id_var,
                    "trace_id": _trace_id_var,
                    "user_id": _user_id_var,
                    "extra": _extra_var,
                }
                var_map[name].reset(token)

    # ---- 日志字段 ----
    @staticmethod
    def log_fields() -> Dict[str, str]:
        """
        获取当前上下文的日志字段

        用于日志 Formatter 自动注入上下文信息。

        Returns:
            包含 request_id, trace_id 等字段的字典
        """
        fields = {}
        rid = get_request_id()
        if rid:
            fields["request_id"] = rid
        tid = get_trace_id()
        if tid:
            fields["trace_id"] = tid
        uid = get_user_id()
        if uid:
            fields["user_id"] = uid
        return fields
