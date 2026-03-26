# -*- coding: utf-8 -*-
"""vLLM Chat Repository - vLLM 聊天仓库实现

实现 ChatRepository 接口，使用 VLLMClient 与服务交互。

注意：此实现通过 get_client / get_server_manager 回调获取依赖，
而非直接依赖特定的 Provider，因此可被任意上层框架复用。
"""

import logging
from typing import Any, Callable, Optional

from .entity import ChatRequest, ChatResponse
from .repository import ChatRepository

logger = logging.getLogger(__name__)


class VLLMChatRepository(ChatRepository):
    """vLLM 聊天仓库实现

    使用 vLLM 客户端实现聊天功能。
    通过回调函数获取 client 和 server_manager，避免绑定到特定的 Provider。
    """

    def __init__(
        self,
        get_client: Callable[[], Any],
        get_server_manager: Optional[Callable[[], Optional[Any]]] = None,
    ):
        """初始化仓库

        Args:
            get_client: 回调，返回 VLLMClient 实例
            get_server_manager: 可选回调，返回 VLLMServerManager 实例
        """
        self._get_client = get_client
        self._get_server_manager = get_server_manager

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """发送聊天请求

        Args:
            request: 聊天请求

        Returns:
            ChatResponse: 聊天响应
        """
        client = self._get_client()

        # 转换消息格式
        messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in request.messages
        ]

        logger.info("Processing chat request: request_id=%s", request.request_id)

        try:
            # 调用 vLLM API
            result = await client.chat_completion(
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
            )

            # 解析响应
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            finish_reason = choice.get("finish_reason", "")

            usage = result.get("usage", {})
            model = result.get("model", "")

            response = ChatResponse(
                request_id=request.request_id,
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
            )

            logger.info(
                "Chat request completed: request_id=%s, tokens=%s",
                request.request_id, usage.get('total_tokens', 0),
            )

            return response

        except Exception as e:
            logger.error("Chat request failed: request_id=%s, error=%s", request.request_id, e)
            raise

    async def health_check(self) -> bool:
        """健康检查

        检查 vLLM 服务是否健康。
        如果有 server_manager（auto_start 模式），还会检查进程状态。

        Returns:
            bool: 服务是否健康
        """
        try:
            # 如果有 vLLM server manager（auto_start 模式），检查其状态
            if self._get_server_manager:
                server_manager = self._get_server_manager()
                if server_manager:
                    server_healthy = await server_manager.health_check()
                    if not server_healthy:
                        logger.warning("vLLM server process health check failed")
                        return False

            # 检查客户端连接
            client = self._get_client()
            return await client.health_check()
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            return False
