# -*- coding: utf-8 -*-
"""vLLM 响应类型定义

定义 vLLM Chat Completion API 的响应数据结构，
供 VLLMClient 和 logprobs 工具使用。
"""

from typing import Any, Dict, List, Optional


class LogprobToken:
    """Logprob token 数据结构"""

    __slots__ = ("token", "logprob", "top_logprobs")

    def __init__(self, data: Dict[str, Any]):
        self.token: str = data.get("token", "")
        self.logprob: float = data.get("logprob", 0.0)
        self.top_logprobs: Optional[List["LogprobToken"]] = (
            [LogprobToken(t) for t in data.get("top_logprobs", [])]
            if "top_logprobs" in data
            else None
        )


class Logprobs:
    """Logprobs 数据结构"""

    __slots__ = ("content",)

    def __init__(self, data: Optional[Dict[str, Any]]):
        self.content: Optional[List[LogprobToken]] = (
            [LogprobToken(item) for item in data.get("content", [])] if data else None
        )


class Message:
    """消息数据结构"""

    __slots__ = ("content", "role")

    def __init__(self, data: Dict[str, Any]):
        self.content: str = data.get("content", "")
        self.role: str = data.get("role", "assistant")


class Choice:
    """Choice 数据结构"""

    __slots__ = ("message", "logprobs")

    def __init__(self, data: Dict[str, Any]):
        self.message: Message = Message(data.get("message", {}))
        self.logprobs: Optional[Logprobs] = (
            Logprobs(data.get("logprobs", {})) if data.get("logprobs") else None
        )


class ChatCompletionResponse:
    """Chat completion 响应数据结构

    同时支持属性访问和字典访问（向后兼容）。
    """

    __slots__ = ("choices", "model", "usage", "_raw")

    def __init__(self, data: Dict[str, Any]):
        self._raw: Dict[str, Any] = data
        self.choices: List[Choice] = [Choice(c) for c in data.get("choices", [])]
        self.model: str = data.get("model", "")
        self.usage: Dict[str, Any] = data.get("usage", {})

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问 result["choices"] 等（向后兼容）。"""
        return self._raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        """支持 result.get("usage", {}) 式访问（向后兼容）。"""
        return self._raw.get(key, default)
