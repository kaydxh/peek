#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SSE (Server-Sent Events) 工具模块

提供两个核心能力：

1. :class:`EventBus` —— 主题（topic）级的进程内发布订阅总线，
   生产者从任意线程 ``publish`` 事件，订阅者通过 ``subscribe``
   返回 ``asyncio.Queue`` 异步消费。线程安全，支持背压（队列满时丢弃最旧）。

2. :func:`sse_response` —— 把任意 ``AsyncIterator[dict]`` 转成符合 SSE
   wire format 的 ``StreamingResponse``，自动处理：
       - ``data:`` 行分包
       - 心跳保活 ``: keepalive`` 注释行
       - 客户端断开 / 任务取消的清理
       - 与 peek 现有 SSE 中间件兼容（透传 ``X-Accel-Buffering: no``、
         ``Cache-Control: no-cache``）

设计取舍：
    - 单进程使用：EventBus 持久于 web_server 生命周期，多 worker / 多实例
      场景需要外部消息中间件（Redis Pub/Sub / Kafka）替换该实现。
    - 队列上限：默认 ``maxsize=1024``，避免慢消费者把订阅者拖垮。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# EventBus —— 主题级进程内 PubSub
# ============================================================


class _Subscriber:
    """单个订阅者持有的 asyncio Queue + 所属事件循环引用。

    生产者可能在任意线程调用 publish，必须把入队动作 ``call_soon_threadsafe``
    投递到订阅者所在的事件循环；否则 Queue.put_nowait 在外部线程调用属未定义行为。
    """

    __slots__ = ("queue", "loop", "topic", "filter_fn")

    def __init__(
        self,
        queue: "asyncio.Queue[dict]",
        loop: asyncio.AbstractEventLoop,
        topic: str,
        filter_fn: Optional[Callable[[dict], bool]] = None,
    ) -> None:
        self.queue = queue
        self.loop = loop
        self.topic = topic
        self.filter_fn = filter_fn


class EventBus:
    """主题级进程内事件总线。

    Topic 命名约定：``<domain>.<resource>.<id>``，例如
    ``eval.run.42`` 表示 run_id=42 的评测进度事件流。
    """

    def __init__(self, queue_maxsize: int = 1024) -> None:
        self._subs: Dict[str, List[_Subscriber]] = defaultdict(list)
        self._lock = threading.Lock()
        self._queue_maxsize = max(1, int(queue_maxsize))

    # ------------------------------------------------------------------
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        topic: str,
        filter_fn: Optional[Callable[[dict], bool]] = None,
    ) -> "asyncio.Queue[dict]":
        """订阅指定 topic，返回该订阅者专用 ``asyncio.Queue``。

        必须在 asyncio 事件循环内调用（否则无法绑定 loop）。

        Args:
            topic: 订阅的主题
            filter_fn: 可选过滤函数，返回 False 的事件将被该订阅者丢弃

        Returns:
            该订阅者私有的 asyncio.Queue（生产者通过 publish 间接 put）
        """
        queue: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=self._queue_maxsize)
        loop = asyncio.get_event_loop()
        sub = _Subscriber(queue=queue, loop=loop, topic=topic, filter_fn=filter_fn)
        with self._lock:
            self._subs[topic].append(sub)
        logger.debug("EventBus subscribed topic=%s, total_subs=%d", topic, len(self._subs[topic]))
        return queue

    def unsubscribe(self, topic: str, queue: "asyncio.Queue[dict]") -> None:
        """根据 queue 实例反注册订阅者。生产者关闭客户端连接时调用。"""
        with self._lock:
            subs = self._subs.get(topic)
            if not subs:
                return
            self._subs[topic] = [s for s in subs if s.queue is not queue]
            if not self._subs[topic]:
                self._subs.pop(topic, None)
        logger.debug("EventBus unsubscribed topic=%s", topic)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, topic: str, event: dict) -> int:
        """向 topic 推送事件。

        - 线程安全：可在任意线程调用
        - 队列满时丢弃最旧（订阅者慢导致背压时，保证生产者不阻塞）

        Returns:
            实际投递的订阅者数量（已过滤的不计）
        """
        with self._lock:
            subs = list(self._subs.get(topic, ()))

        delivered = 0
        for sub in subs:
            if sub.filter_fn is not None:
                try:
                    if not sub.filter_fn(event):
                        continue
                except Exception as exc:
                    logger.warning("EventBus filter raised: %s", exc)
                    continue
            self._enqueue(sub, event)
            delivered += 1
        return delivered

    def topic_subscribers(self, topic: str) -> int:
        """返回订阅了某 topic 的订阅者数量（用于 metrics）。"""
        with self._lock:
            return len(self._subs.get(topic, ()))

    def _enqueue(self, sub: _Subscriber, event: dict) -> None:
        """把 event 投递到 sub 所在事件循环的 queue 里。

        若队列已满，丢弃最旧那条以保证生产侧永不阻塞（背压策略）。
        """

        def _put() -> None:
            queue = sub.queue
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # 丢弃最旧那条，再 put 新事件
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        "EventBus queue still full after eviction, dropping event topic=%s",
                        sub.topic,
                    )

        try:
            sub.loop.call_soon_threadsafe(_put)
        except RuntimeError:
            # loop 已关闭，订阅者断连未及时反注册，忽略即可
            pass


# 进程内全局 EventBus（lazy-init）
_default_event_bus: Optional[EventBus] = None
_default_event_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """获取进程级单例 EventBus。"""
    global _default_event_bus
    if _default_event_bus is None:
        with _default_event_bus_lock:
            if _default_event_bus is None:
                _default_event_bus = EventBus()
    return _default_event_bus


# ============================================================
# SSE wire format helpers
# ============================================================


def format_sse(
    data: Any,
    event: Optional[str] = None,
    event_id: Optional[str] = None,
    retry_ms: Optional[int] = None,
) -> str:
    """把一个 Python 对象序列化为符合 SSE 协议的字符串块。

    协议要点：
        - 多个 ``data:`` 行属于同一事件，最终用 ``\\n\\n`` 结束
        - ``event:`` 字段可让前端 ``addEventListener(eventName, ...)`` 监听
        - ``id:`` 字段被浏览器写入 ``Last-Event-ID`` 用于断线重连恢复进度
    """
    lines: List[str] = []
    if event:
        lines.append(f"event: {event}")
    if event_id is not None:
        lines.append(f"id: {event_id}")
    if retry_ms is not None:
        lines.append(f"retry: {retry_ms}")

    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    # 内嵌换行需要拆成多个 data: 行
    for line in payload.splitlines() or [""]:
        lines.append(f"data: {line}")
    lines.append("")  # 事件结束的空行
    lines.append("")
    return "\n".join(lines)


async def sse_event_stream(
    queue: "asyncio.Queue[dict]",
    *,
    keepalive_interval: float = 15.0,
    initial_event: Optional[dict] = None,
    event_field: str = "event",
    id_field: Optional[str] = "id",
) -> AsyncIterator[bytes]:
    """把 EventBus 订阅得到的 ``asyncio.Queue`` 转成符合 SSE 协议的 byte 流。

    协议细节由本函数统一处理；上层 handler 只管把它喂给 ``StreamingResponse``。

    Args:
        queue: :func:`EventBus.subscribe` 返回的 Queue
        keepalive_interval: 无事件时多久发送一次心跳注释行（秒）。
                            浏览器/中间代理通常 30s~60s 不收数据就断连，
                            默认 15s 比较保险。
        initial_event: 可选，连接建立时立即推送的"快照"事件（首屏数据）
        event_field: 事件 dict 中代表 event 类型的字段名（默认 ``event``）
        id_field: 事件 dict 中代表唯一 id 的字段名，None 表示不写 ``id:``

    Yields:
        bytes 形式的 SSE 事件块
    """
    if initial_event is not None:
        yield format_sse(
            initial_event,
            event=initial_event.get(event_field) if event_field else None,
            event_id=str(initial_event.get(id_field)) if id_field and id_field in initial_event else None,
        ).encode("utf-8")

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=keepalive_interval)
        except asyncio.TimeoutError:
            # 心跳：注释行（: 开头），不会被前端 onmessage 触发
            yield f": keepalive {int(time.time())}\n\n".encode("utf-8")
            continue
        except asyncio.CancelledError:
            # 客户端断开 / handler 被取消
            return

        yield format_sse(
            event,
            event=event.get(event_field) if event_field else None,
            event_id=str(event.get(id_field)) if id_field and id_field in event else None,
        ).encode("utf-8")


def sse_response(
    queue: "asyncio.Queue[dict]",
    *,
    keepalive_interval: float = 15.0,
    initial_event: Optional[dict] = None,
    event_field: str = "event",
    id_field: Optional[str] = "id",
    on_close: Optional[Callable[[], None]] = None,
):
    """把 EventBus 订阅 queue 包装成 FastAPI ``StreamingResponse``。

    与 peek webserver 中间件兼容：
        - logger / requestid 中间件已对 ``text/event-stream`` 做过透传处理
        - 自动设置 ``Cache-Control: no-cache``、``X-Accel-Buffering: no``
          以避免 nginx / 网关缓冲流式数据

    Args:
        on_close: 客户端断开后的清理回调（如反注册 EventBus 订阅）
    """
    from fastapi.responses import StreamingResponse

    async def _gen() -> AsyncIterator[bytes]:
        try:
            async for chunk in sse_event_stream(
                queue,
                keepalive_interval=keepalive_interval,
                initial_event=initial_event,
                event_field=event_field,
                id_field=id_field,
            ):
                yield chunk
        finally:
            if on_close is not None:
                try:
                    on_close()
                except Exception as exc:
                    logger.warning("SSE on_close hook raised: %s", exc)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = [
    "EventBus",
    "get_event_bus",
    "format_sse",
    "sse_event_stream",
    "sse_response",
]
