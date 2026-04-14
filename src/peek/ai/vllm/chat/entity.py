# -*- coding: utf-8 -*-
"""Chat Entity - 聊天领域实体

定义聊天相关的领域实体和值对象。
通用于任何基于 vLLM 的文本聊天场景。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class MessageRole(str, Enum):
    """消息角色枚举"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    """聊天消息值对象"""

    role: MessageRole
    content: str


@dataclass
class ChatRequest:
    """聊天请求值对象"""

    request_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None


@dataclass
class ChatResponse:
    """聊天响应值对象"""

    request_id: str
    content: str
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""


@dataclass
class ChatEntity:
    """聊天领域实体

    代表一次聊天会话
    """

    request_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    response: Optional[ChatResponse] = None

    def add_message(self, role: MessageRole, content: str) -> None:
        """添加消息到会话"""
        self.messages.append(ChatMessage(role=role, content=content))

    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.add_message(MessageRole.SYSTEM, content)

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add_message(MessageRole.USER, content)

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self.add_message(MessageRole.ASSISTANT, content)
