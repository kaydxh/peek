#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
校验装饰器

提供 @validated 装饰器，为 HTTP handler 和 gRPC servicer 方法自动添加参数校验。

用法示例：
    from peek.validation import validated, FieldRule, required, min_length

    # HTTP Controller 方法
    class MyController:
        @validated([
            FieldRule("request_id", required(), min_length(1)),
            FieldRule("name", required(), min_length(2), max_length(50)),
        ])
        async def create_user(self, req):
            ...

    # gRPC Servicer 方法
    class MyServicer(my_pb2_grpc.MyServiceServicer):
        @validated([
            FieldRule("request_id", required()),
            FieldRule("name", required(), min_length(2)),
        ])
        def CreateUser(self, request, context):
            ...
"""

import asyncio
import functools
import logging
from typing import Any, Callable, List, Optional

from peek.validation.validator import FieldRule, validate

logger = logging.getLogger(__name__)


def validated(
    rules: List[FieldRule],
    message: str = "Validation failed",
) -> Callable:
    """
    参数校验装饰器

    自动对方法的第一个请求参数进行校验。
    校验失败时：
    - HTTP 场景：抛出 peek.errors.ValidationError（由 RecoveryMiddleware 自动转为 400 响应）
    - gRPC 场景：抛出 peek.errors.ValidationError（由 RecoveryInterceptor 自动转为 INVALID_ARGUMENT）

    Args:
        rules: 字段校验规则列表
        message: 校验失败时的错误消息

    Returns:
        装饰器函数

    用法：
        @validated([
            FieldRule("request_id", required()),
            FieldRule("name", required(), min_length(2)),
        ])
        async def my_handler(self, request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 提取请求参数：支持 (self, request) 和 (self, request, context) 两种签名
            request_obj = _extract_request(args, kwargs)
            if request_obj is not None:
                validate(request_obj, rules, message=message)
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            request_obj = _extract_request(args, kwargs)
            if request_obj is not None:
                validate(request_obj, rules, message=message)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _extract_request(args: tuple, kwargs: dict) -> Optional[Any]:
    """
    从函数参数中提取请求对象

    支持的签名：
    - handler(request)                    → args[0]
    - handler(self, request)              → args[1]
    - handler(self, request, context)     → args[1]（gRPC servicer）
    - handler(request=req)                → kwargs["request"]
    """
    # 先检查 kwargs
    if "request" in kwargs:
        return kwargs["request"]
    if "req" in kwargs:
        return kwargs["req"]

    # 检查 args
    if len(args) >= 2:
        # (self, request, ...) 或 (self, request, context)
        return args[1]
    elif len(args) == 1:
        # (request,)
        return args[0]

    return None
