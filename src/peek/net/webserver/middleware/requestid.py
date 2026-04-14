#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Request ID 中间件

参考 golang HandleReuestId 拦截器，在中间件层统一处理 request_id：
1. 从请求 header 中提取 request_id
2. 如果为空，生成新的 UUID
3. handler 执行后，自动将 request_id 注入到响应 body 的 RequestId 字段（如果为空）
4. 设置 X-Request-ID 响应头

使用纯 ASGI 实现（不依赖 BaseHTTPMiddleware），确保与 OpenTelemetry
FastAPIInstrumentor 等工具兼容。
"""

import json
import logging
import uuid
from typing import List, Optional, Tuple

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from peek.context import RequestContext

logger = logging.getLogger(__name__)

# response body 中 request_id 的候选字段名
_RESPONSE_REQUEST_ID_KEYS = ("RequestId", "request_id")


class RequestIDMiddleware:
    """
    Request ID 中间件（纯 ASGI 实现）

    参考 golang 的 HandleReuestId 拦截器，统一在中间件层完成：
    - 提取 / 生成 request_id
    - 自动回写到 response body 的 RequestId 字段（如果为空）
    - 设置 X-Request-ID 响应头

    使用纯 ASGI 实现而非 BaseHTTPMiddleware，与 OTel instrumentation 完全兼容。
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
    ):
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ===== Step 1: 解析 request_id =====
        # 从 scope["headers"] 中提取
        headers = dict(
            (k.decode("latin-1").lower(), v.decode("latin-1"))
            for k, v in scope.get("headers", [])
        )
        request_id = headers.get(self.header_name.lower(), "")

        # 尝试从 OTel 获取 trace_id
        trace_id = ""
        try:
            from opentelemetry import trace as otel_trace

            span = otel_trace.get_current_span()
            if span and span.get_span_context().trace_id:
                trace_id = format(span.get_span_context().trace_id, "032x")
        except (ImportError, Exception):
            pass

        # 如果请求没有传 request_id，优先使用 OTel trace_id，否则生成 UUID
        # 保证日志和回包使用同一个 ID
        if not request_id:
            request_id = trace_id if trace_id else str(uuid.uuid4())

        # 将 request_id 存储到 ASGI scope["state"] 中
        # 这样后续 BaseHTTPMiddleware 子类可以通过 request.state.request_id 获取
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        # 设置到 contextvars（跨层传播）
        with RequestContext.scope(request_id=request_id):
            # 同步设置 trace_id 到 contextvars
            if trace_id:
                RequestContext.set_trace_id(trace_id)

            # ===== Step 2 & 3: 拦截 response，注入 request_id =====
            # 收集 response body 和 headers，在发送前修改
            response_started = False
            initial_message: Optional[Message] = None
            body_parts: List[bytes] = []
            content_type = ""

            async def send_wrapper(message: Message) -> None:
                nonlocal response_started, initial_message, content_type

                if message["type"] == "http.response.start":
                    # 暂存 response start 消息，稍后可能修改 headers
                    response_started = True
                    initial_message = message

                    # 提取 content-type
                    raw_headers: List[Tuple[bytes, bytes]] = message.get("headers", [])
                    for k, v in raw_headers:
                        if k.decode("latin-1").lower() == "content-type":
                            content_type = v.decode("latin-1")
                            break

                elif message["type"] == "http.response.body":
                    body = message.get("body", b"")
                    more_body = message.get("more_body", False)

                    body_parts.append(body)

                    if not more_body:
                        # 最后一个 body chunk，执行注入逻辑
                        full_body = b"".join(body_parts)
                        modified_body = _try_inject_request_id(
                            full_body, content_type, request_id, trace_id
                        )

                        # 添加/更新 X-Request-ID header
                        new_headers = _update_headers(
                            initial_message.get("headers", []),
                            self.header_name,
                            request_id,
                            len(modified_body),
                        )
                        initial_message["headers"] = new_headers

                        # 发送 response start
                        await send(initial_message)
                        # 发送修改后的 body
                        await send(
                            {
                                "type": "http.response.body",
                                "body": modified_body,
                                "more_body": False,
                            }
                        )
                    # 如果还有更多 body chunk，继续收集
                else:
                    await send(message)

            await self.app(scope, receive, send_wrapper)


def _try_inject_request_id(
    body: bytes,
    content_type: str,
    request_id: str,
    trace_id: str,
) -> bytes:
    """
    尝试将 request_id 注入到 response body 的 RequestId 字段

    参考 golang HandleReuestId:
      reflect_.TrySetId(resp, reflect_.FieldNameRequestId, id)

    规则：
    - 仅处理 JSON 响应
    - 如果 RequestId 字段存在且为空，自动填充
    - 如果 RequestId 字段不为空（业务层已设置），保持不变
    - 使用 request_id（已统一：请求传了用请求的，没传优先用 trace_id）

    Args:
        body: 原始 response body
        content_type: Content-Type 头
        request_id: 中间件确定的 request_id（日志和回包统一使用）
        trace_id: OTel trace_id（仅保留参数兼容性）

    Returns:
        可能修改过的 response body
    """
    if "application/json" not in content_type:
        return body

    if not body:
        return body

    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            return body

        # 查找 RequestId 字段
        for key in _RESPONSE_REQUEST_ID_KEYS:
            if key in data:
                if not data[key]:
                    # 字段存在但为空 → 自动填充
                    # 使用 request_id，保证回包和日志中的 ID 一致
                    data[key] = request_id
                    return json.dumps(data, ensure_ascii=False).encode("utf-8")
                # 字段不为空，保持不变
                return body

        return body

    except (json.JSONDecodeError, UnicodeDecodeError, Exception):
        return body


def _update_headers(
    raw_headers: List[Tuple[bytes, bytes]],
    request_id_header: str,
    request_id: str,
    new_content_length: int,
) -> List[Tuple[bytes, bytes]]:
    """
    更新 response headers：
    - 添加/更新 X-Request-ID
    - 更新 content-length

    Args:
        raw_headers: 原始 headers
        request_id_header: X-Request-ID header 名
        request_id: request_id 值
        new_content_length: 新的 body 长度

    Returns:
        更新后的 headers
    """
    new_headers: List[Tuple[bytes, bytes]] = []
    header_lower = request_id_header.lower()
    found_request_id = False

    for k, v in raw_headers:
        key_str = k.decode("latin-1").lower()
        if key_str == header_lower:
            # 更新已有的 X-Request-ID
            new_headers.append((k, request_id.encode("latin-1")))
            found_request_id = True
        elif key_str == "content-length":
            # 更新 content-length
            new_headers.append((k, str(new_content_length).encode("latin-1")))
        else:
            new_headers.append((k, v))

    if not found_request_id:
        new_headers.append(
            (
                request_id_header.encode("latin-1"),
                request_id.encode("latin-1"),
            )
        )

    return new_headers
