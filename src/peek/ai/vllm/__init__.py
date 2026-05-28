# -*- coding: utf-8 -*-
"""Peek AI vLLM - vLLM 统一客户端和工具模块

提供：
- VLLMClient: 统一客户端（支持文本/多模态/logprobs）
- types: 响应类型定义（ChatCompletionResponse, Choice, Message, Logprobs, LogprobToken）
- chat: 聊天领域通用模块（entity, repository, factory, handler）
- logprobs: 二分类 logprobs 解析工具
"""

from peek.ai.vllm.client import VLLMClient
from peek.ai.vllm.logprobs import (
    BinaryClassificationResult,
    apply_threshold,
    extract_binary_logprobs,
    parse_binary_classification,
)
from peek.ai.vllm.types import (
    ChatCompletionResponse,
    Choice,
    Logprobs,
    LogprobToken,
    Message,
)

__all__ = [
    # 主要接口
    "VLLMClient",
    # 响应类型
    "ChatCompletionResponse",
    "Choice",
    "Message",
    "Logprobs",
    "LogprobToken",
    # logprobs 工具
    "BinaryClassificationResult",
    "parse_binary_classification",
    "extract_binary_logprobs",
    "apply_threshold",
]
