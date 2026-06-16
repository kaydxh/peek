#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 任务装饰器：trace_id / request_id 自动注入

提供 @traceable_task 装饰器，让 Celery worker 进程内的所有日志自动带上
caller 端的 trace_id（与 HTTP 请求链路保持一致），无需业务代码侵入。

使用方式：

    from peek.plugins.celery import create_celery_app, traceable_task

    celery_app = create_celery_app("eduprobe", celery_config, redis_config)

    @traceable_task(celery_app, bind=True, max_retries=1)
    def run_evaluation(self, run_id, config_override=None, _trace_id=None):
        ...

调用方（HTTP handler 等）：

    from peek.context import RequestContext

    trace_id = RequestContext.get_trace_id()
    run_evaluation.delay(run_id, config_override, _trace_id=trace_id)

worker 端会自动从 kwargs 中弹出 _trace_id 并用 RequestContext.scope() 包住整个 task，
peek 的 GlogFormatter 会自动把 trace_id 追加到所有日志末尾。
"""

import functools
import logging
import uuid
from typing import Any, Callable

logger = logging.getLogger(__name__)

_TRACE_ID_KEY = "_trace_id"
_REQUEST_ID_KEY = "_request_id"


def traceable_task(celery_app: Any, **task_kwargs) -> Callable:
    """Celery 任务装饰器：自动注入 trace_id / request_id 到 RequestContext。

    包装顺序：先用 functools.wraps 保留元数据，再交给 celery_app.task。

    Args:
        celery_app: Celery 实例
        **task_kwargs: 透传给 celery_app.task 的参数（bind / max_retries / queue 等）

    Returns:
        装饰器，被装饰的函数会变成 Celery task。

    被装饰函数的约定：
        - 可在 kwargs 中接收 _trace_id / _request_id 两个保留参数
        - 这两个参数会在 worker 端被弹出，不会传给业务函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 弹出保留参数（业务函数不感知）
            trace_id = kwargs.pop(_TRACE_ID_KEY, None) or ""
            request_id = kwargs.pop(_REQUEST_ID_KEY, None) or ""

            # worker 端如果都没收到，自己生成一个，至少保证当前 task 内日志可串联
            if not trace_id and not request_id:
                request_id = f"celery-{uuid.uuid4().hex[:16]}"

            try:
                from peek.context import RequestContext
            except ImportError:
                # peek.context 不可用：直接执行，不做注入
                return func(*args, **kwargs)

            scope_kwargs = {}
            if trace_id:
                scope_kwargs["trace_id"] = trace_id
            if request_id:
                scope_kwargs["request_id"] = request_id

            with RequestContext.scope(**scope_kwargs):
                return func(*args, **kwargs)

        # 关键：先 wraps 再交给 celery，task 装饰器会读取 wrapper.__name__
        return celery_app.task(**task_kwargs)(wrapper)

    return decorator


def inject_trace_kwargs(kwargs: dict) -> dict:
    """工具函数：从当前 RequestContext 读取 trace_id / request_id 并塞进 kwargs。

    适合在 HTTP handler 中调用 task.delay() 之前使用：

        kwargs = inject_trace_kwargs({"config_override": cfg})
        run_evaluation.delay(run_id, **kwargs)

    Args:
        kwargs: 原始关键字参数 dict

    Returns:
        新的 dict（不修改原 dict），追加 _trace_id / _request_id（如有）
    """
    new_kwargs = dict(kwargs)
    try:
        from peek.context import RequestContext

        trace_id = RequestContext.get_trace_id()
        request_id = RequestContext.get_request_id()
        if trace_id:
            new_kwargs[_TRACE_ID_KEY] = trace_id
        if request_id:
            new_kwargs[_REQUEST_ID_KEY] = request_id
    except ImportError:
        pass
    return new_kwargs
