# -*- coding: utf-8 -*-
"""Chat - vLLM 聊天领域通用模块

提供 vLLM 文本聊天的完整 DDD 分层：
- entity: 领域实体（ChatMessage, ChatRequest, ChatResponse, ChatEntity, MessageRole）
- repository: 仓库接口（ChatRepository）
- factory: 聊天工厂（ChatFactory, FactoryConfig）
- vllm_repository: vLLM 仓库实现（VLLMChatRepository）
- handler: 应用层处理器（ChatHandler, Application, Commands）
"""

from .entity import (
    MessageRole,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatEntity,
)
from .repository import ChatRepository
from .factory import ChatFactory, FactoryConfig
from .vllm_repository import VLLMChatRepository
from .handler import (
    ChatHandler,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Application,
    Commands,
)

__all__ = [
    # Entity
    "MessageRole",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatEntity",
    # Repository
    "ChatRepository",
    # Factory
    "ChatFactory",
    "FactoryConfig",
    # Infrastructure
    "VLLMChatRepository",
    # Handler / Application
    "ChatHandler",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "Application",
    "Commands",
]
