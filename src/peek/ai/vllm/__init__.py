# -*- coding: utf-8 -*-
"""Peek AI vLLM - vLLM 客户端和 Chat 通用模块

提供：
- VLLMClient: 文本聊天客户端
- VLLMVideoClient: 视频多模态客户端（含响应对象）
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
from peek.ai.vllm.video_client import (
    ChatCompletionResponse as VideoChatCompletionResponse,
)
from peek.ai.vllm.video_client import Choice as VideoChoice
from peek.ai.vllm.video_client import (
    Logprobs,
    LogprobToken,
)
from peek.ai.vllm.video_client import Message as VideoMessage
from peek.ai.vllm.video_client import (
    VLLMVideoClient,
)

__all__ = [
    "VLLMClient",
    "VLLMVideoClient",
    "VideoChatCompletionResponse",
    "LogprobToken",
    "Logprobs",
    "VideoMessage",
    "VideoChoice",
    "BinaryClassificationResult",
    "parse_binary_classification",
    "extract_binary_logprobs",
    "apply_threshold",
]
