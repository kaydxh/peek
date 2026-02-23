# -*- coding: utf-8 -*-
"""Peek AI vLLM - vLLM 客户端和 Chat 通用模块

提供：
- VLLMClient: 文本聊天客户端
- VLLMVideoClient: 视频多模态客户端（含响应对象）
- chat: 聊天领域通用模块（entity, repository, factory, handler）
"""

from peek.ai.vllm.client import VLLMClient
from peek.ai.vllm.video_client import (
    VLLMVideoClient,
    ChatCompletionResponse as VideoChatCompletionResponse,
    LogprobToken,
    Logprobs,
    Message as VideoMessage,
    Choice as VideoChoice,
)

__all__ = [
    "VLLMClient",
    "VLLMVideoClient",
    "VideoChatCompletionResponse",
    "LogprobToken",
    "Logprobs",
    "VideoMessage",
    "VideoChoice",
]
