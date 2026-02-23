# -*- coding: utf-8 -*-
"""Chat Factory - 聊天工厂

负责创建聊天领域实体。
"""

from dataclasses import dataclass
from typing import Optional, List

from .entity import ChatEntity, ChatMessage, ChatRequest, ChatResponse, MessageRole
from .repository import ChatRepository


@dataclass
class FactoryConfig:
    """工厂配置"""
    chat_repository: ChatRepository


class ChatFactory:
    """聊天工厂

    负责创建和管理聊天领域实体。
    """

    def __init__(self, config: FactoryConfig):
        self._config = config
        self._repository = config.chat_repository

    @property
    def repository(self) -> ChatRepository:
        """获取聊天仓库"""
        return self._repository

    def create_entity(self, request_id: str) -> ChatEntity:
        """创建聊天实体

        Args:
            request_id: 请求ID

        Returns:
            ChatEntity: 聊天实体
        """
        return ChatEntity(request_id=request_id)

    def create_request(
        self,
        request_id: str,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> ChatRequest:
        """创建聊天请求

        Args:
            request_id: 请求ID
            messages: 消息列表
            max_tokens: 最大 token 数
            temperature: 温度参数
            top_p: top_p 参数

        Returns:
            ChatRequest: 聊天请求
        """
        return ChatRequest(
            request_id=request_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """发送聊天请求

        Args:
            request: 聊天请求

        Returns:
            ChatResponse: 聊天响应
        """
        return await self._repository.chat(request)
