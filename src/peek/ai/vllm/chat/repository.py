# -*- coding: utf-8 -*-
"""Chat Repository - 聊天仓库接口

定义聊天仓库的抽象接口。
"""

from abc import ABC, abstractmethod

from .entity import ChatRequest, ChatResponse


class ChatRepository(ABC):
    """聊天仓库抽象基类

    定义与 LLM 服务交互的接口。
    """

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """发送聊天请求

        Args:
            request: 聊天请求

        Returns:
            ChatResponse: 聊天响应
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查

        Returns:
            bool: 服务是否健康
        """
