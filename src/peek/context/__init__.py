#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
请求上下文传播模块

基于 Python contextvars 实现请求级别的上下文传播。
中间件/拦截器自动设置，业务代码通过 RequestContext 读取。

子模块：
- peek.context.context: 请求上下文核心实现
"""

from peek.context.context import (
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

__all__ = [
    "RequestContext",
    "get_request_id",
    "set_request_id",
    "get_trace_id",
    "set_trace_id",
    "get_user_id",
    "set_user_id",
    "get_extra",
    "set_extra",
]
