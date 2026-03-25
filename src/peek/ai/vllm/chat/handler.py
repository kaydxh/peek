# -*- coding: utf-8 -*-
"""Chat Handler - 聊天处理器

处理聊天相关的应用用例。通用于任何基于 vLLM 的文本聊天场景。
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from .entity import ChatMessage, MessageRole
from .factory import ChatFactory

logger = logging.getLogger(__name__)


@dataclass
class ChatCompletionRequest:
    """聊天补全请求"""
    request_id: str
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None


@dataclass
class ChatCompletionResponse:
    """聊天补全响应"""
    request_id: str
    content: str
    model: str = ""
    usage: dict = None
    finish_reason: str = ""


@dataclass
class Commands:
    """命令集合"""
    chat_handler: "ChatHandler"


@dataclass
class Application:
    """应用层

    包含所有命令处理器
    """
    commands: Commands


class ChatHandler:
    """聊天处理器

    处理聊天相关的应用用例
    """

    def __init__(self, factory: ChatFactory):
        """初始化处理器

        Args:
            factory: 聊天工厂
        """
        self._factory = factory

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """处理聊天补全请求

        Args:
            request: 聊天补全请求

        Returns:
            ChatCompletionResponse: 聊天补全响应
        """
        logger.info(f"Processing chat completion: request_id={request.request_id}")

        # 构建消息列表
        messages: List[ChatMessage] = []

        # 添加系统提示词
        if request.system_prompt:
            messages.append(ChatMessage(
                role=MessageRole.SYSTEM,
                content=request.system_prompt,
            ))

        # 添加用户消息
        messages.append(ChatMessage(
            role=MessageRole.USER,
            content=request.prompt,
        ))

        # 创建领域请求
        domain_request = self._factory.create_request(
            request_id=request.request_id,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
        )

        # 调用领域服务
        domain_response = await self._factory.chat(domain_request)

        # 转换为应用响应
        return ChatCompletionResponse(
            request_id=domain_response.request_id,
            content=domain_response.content,
            model=domain_response.model,
            usage=domain_response.usage,
            finish_reason=domain_response.finish_reason,
        )

    async def health_check(self) -> bool:
        """健康检查

        Returns:
            bool: 服务是否健康
        """
        return await self._factory.repository.health_check()
