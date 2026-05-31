# -*- coding: utf-8 -*-
"""vLLM Client - vLLM 统一客户端

实现与 vLLM 服务器的 HTTP 通信，使用 OpenAI 兼容的 API 格式。
支持文本聊天、多模态输入（图片/视频）、logprobs 返回等全部能力。
"""

import logging
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from peek.ai.vllm.types import ChatCompletionResponse

logger = logging.getLogger(__name__)


@dataclass
class VLLMClient:
    """vLLM 统一客户端

    通过 HTTP 与 vLLM 服务器通信，使用 OpenAI 兼容的 API 格式。
    支持文本聊天、多模态输入（图片/视频）、logprobs 返回。
    内部复用 httpx.AsyncClient 连接池以提升性能。

    支持两种初始化方式：
    1. host + port: 适用于本地 vLLM 服务
    2. base_url: 适用于远程 OpenAI 兼容 API（如 Hunyuan、DeepSeek 等）
    """

    host: str = "localhost"
    port: int = 8000
    base_url: str = ""
    api_key: str = ""
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    timeout: int = 60

    def __post_init__(self):
        """初始化客户端"""
        # 优先使用 base_url，否则用 host:port 拼接
        if self.base_url:
            self._base_url = self.base_url.rstrip("/")
        else:
            self._base_url = f"http://{self.host}:{self.port}"
        self._headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"
        # 复用 httpx 连接池，避免每次请求创建新连接
        self._http_client: Optional[httpx.AsyncClient] = None
        logger.info(
            "VLLMClient initialized: model=%s, base_url=%s",
            self.model_name, self._base_url,
        )

    def get_base_url(self) -> str:
        """获取处理后的基础 URL"""
        return self._base_url

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        seed: Optional[int] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        skip_special_tokens: Optional[bool] = None,
        repetition_penalty: Optional[float] = None,
        stream: bool = False,
    ) -> ChatCompletionResponse:
        """发送聊天补全请求

        使用 OpenAI 兼容的 /v1/chat/completions 端点。
        支持文本聊天、多模态输入（图片/视频）、logprobs 返回。

        Args:
            messages: 消息列表，支持纯文本和多模态格式
            model: 模型名称，默认使用配置的模型
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            top_p: top_p 参数
            seed: 随机种子
            logprobs: 是否返回 logprobs
            top_logprobs: 返回 top-k 个 logprobs
            skip_special_tokens: 是否跳过特殊 token
            repetition_penalty: 重复惩罚系数
            stream: 是否流式输出

        Returns:
            ChatCompletionResponse: 完整响应对象
        """
        # 将 0.0.0.0 替换为 127.0.0.1 以便客户端连接
        base_url = self._base_url.replace("0.0.0.0", "127.0.0.1")
        # 如果 base_url 已包含版本路径（如 /v1、/v2 等），则直接拼接 /chat/completions
        import re
        if re.search(r"/v\d+", base_url):
            url = f"{base_url}/chat/completions"
        else:
            url = f"{base_url}/v1/chat/completions"

        payload = {
            "model": model or self.model_name,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": stream,
        }

        # 可选参数：仅在显式传入时添加
        if top_p is not None:
            payload["top_p"] = top_p
        if seed is not None:
            payload["seed"] = seed
        if logprobs is not None:
            payload["logprobs"] = logprobs
        if top_logprobs is not None:
            payload["top_logprobs"] = top_logprobs
        if skip_special_tokens is not None:
            payload["skip_special_tokens"] = skip_special_tokens
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty

        logger.debug("Sending request to vLLM: %s", url)

        client = await self._get_client()
        response = await client.post(
            url,
            json=payload,
            headers=self._headers,
        )
        if response.status_code != 200:
            error_detail = response.text
            logger.error(
                "vLLM request failed: status=%s, detail=%s",
                response.status_code,
                error_detail,
            )
        response.raise_for_status()
        result = response.json()

        logger.debug("vLLM response: model=%s", result.get("model", ""))
        return ChatCompletionResponse(result)

    async def health_check(self) -> bool:
        """健康检查

        检查 vLLM 服务器是否可用并且模型已就绪。

        Returns:
            bool: 服务是否健康
        """
        try:
            base_url = self._base_url.replace("0.0.0.0", "127.0.0.1")
            url = f"{base_url}/v1/models"
            client = await self._get_client(timeout=5)
            response = await client.get(url, headers=self._headers)
            if response.status_code == 200:
                data = response.json()
                model_names = [model["id"] for model in data.get("data", [])]
                is_ready = self.model_name in model_names
                if not is_ready:
                    logger.debug(
                        "Model %s not ready yet, available models: %s",
                        self.model_name,
                        model_names,
                    )
                return is_ready
            else:
                logger.debug(
                    "vLLM server returned status code: %s", response.status_code
                )
                return False
        except Exception as e:
            logger.warning("vLLM health check failed: %s", e)
            return False

    async def list_models(self) -> List[str]:
        """获取可用模型列表

        Returns:
            List[str]: 模型名称列表
        """
        try:
            base_url = self._base_url.replace("0.0.0.0", "127.0.0.1")
            url = f"{base_url}/v1/models"
            client = await self._get_client(timeout=10)
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            result = response.json()
            return [model["id"] for model in result.get("data", [])]
        except Exception as e:
            logger.error("Failed to list models: %s", e)
            return []

    async def _get_client(self, timeout: Optional[int] = None) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端（复用连接池）

        Args:
            timeout: 可选的超时覆盖，None 时使用默认 timeout

        Returns:
            httpx.AsyncClient 实例
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        if timeout is not None and timeout != self.timeout:
            # 对于不同超时的请求，创建临时客户端
            return httpx.AsyncClient(timeout=timeout)
        return self._http_client

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        context: str = "",
        image_base64: Optional[str] = None,
    ) -> tuple:
        """高层便捷聊天接口，支持 system_prompt 和多模态输入。

        自动组装 messages 并调用 chat_completion，返回回复文本和 token 用量。

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            context: 附加上下文（对话历史摘要等）
            image_base64: 可选的 base64 编码图片（用于多模态识别）

        Returns:
            (reply, usage) 元组:
            - reply: LLM 回答文本
            - usage: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        """
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append(
                {"role": "assistant", "content": "Got it. What would you like to practice?"}
            )

        # 构建用户消息：纯文本或多模态（文字 + 图片）
        if image_base64:
            user_content: List[Dict[str, Any]] = [
                {"type": "text", "text": user_message},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                    },
                },
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": user_message})

        # 打印请求日志
        logger.info(
            "[LLM] request model=%s, temperature=%.2f, max_tokens=%d",
            self.model_name, self.temperature, self.max_tokens,
        )
        for i, msg in enumerate(messages):
            content_preview = msg.get("content", "")
            if isinstance(content_preview, list):
                text_parts = [
                    p.get("text", "[image]")
                    for p in content_preview
                    if isinstance(p, dict)
                ]
                content_preview = " | ".join(text_parts)
            content_preview = str(content_preview)[:200]
            logger.info("[LLM] messages[%d] role=%s: %s", i, msg.get("role"), content_preview)

        try:
            result = await self.chat_completion(messages=messages)

            message = result["choices"][0]["message"]
            # 兼容深度思考模型：content 为空时回退到 reasoning_content
            reply = message.get("content") or message.get("reasoning_content") or ""
            logger.info("[LLM] reply (first 300 chars): %s", reply[:300])

            # 提取 token 用量
            usage = result.get("usage", {})
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

            logger.info(
                "LLM API token usage: prompt=%d, completion=%d, total=%d",
                token_usage["prompt_tokens"],
                token_usage["completion_tokens"],
                token_usage["total_tokens"],
            )
            return (reply, token_usage)

        except Exception as e:
            logger.error("LLM API call failed: %s", e)
            return (
                "I'm sorry, I encountered an error. Please try again.",
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )

    async def chat_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str = "",
        image_base64: Optional[str] = None,
    ):
        """高层流式聊天接口，逐 chunk 返回生成内容。

        与 chat() 接口参数一致，但返回 AsyncGenerator，
        每次 yield 一个 dict：
        - {"type": "chunk", "content": "..."} — 增量文本
        - {"type": "done", "usage": {...}} — 结束标记 + token 用量

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            context: 附加上下文
            image_base64: 可选的 base64 编码图片

        Yields:
            dict: chunk 或 done 事件
        """
        import re

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append(
                {"role": "assistant", "content": "Got it. What would you like to practice?"}
            )

        # 构建用户消息：纯文本或多模态
        if image_base64:
            user_content: List[Dict[str, Any]] = [
                {"type": "text", "text": user_message},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                    },
                },
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": user_message})

        logger.info(
            "[LLM-Stream] request model=%s, temperature=%.2f, max_tokens=%d",
            self.model_name, self.temperature, self.max_tokens,
        )

        # 构建请求
        if re.search(r"/v\d+", self._base_url):
            url = f"{self._base_url}/chat/completions"
        else:
            url = f"{self._base_url}/v1/chat/completions"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": True,
        }

        try:
            client = await self._get_client()
            async with client.stream(
                "POST", url, json=payload, headers=self._headers
            ) as response:
                response.raise_for_status()
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                full_content = ""

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        # 提取增量内容
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        # 兼容深度思考模型：content 为空时回退到 reasoning_content
                        content = delta.get("content") or delta.get("reasoning_content") or ""
                        if content:
                            full_content += content
                            yield {"type": "chunk", "content": content}

                        # 部分 API 在最后一个 chunk 中返回 usage
                        if "usage" in chunk and chunk["usage"]:
                            usage = {
                                "prompt_tokens": chunk["usage"].get("prompt_tokens", 0),
                                "completion_tokens": chunk["usage"].get("completion_tokens", 0),
                                "total_tokens": chunk["usage"].get("total_tokens", 0),
                            }
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue

                # 如果 API 没有在 stream 中返回 usage，估算 completion tokens
                if usage["total_tokens"] == 0 and full_content:
                    estimated_completion = len(full_content) // 4
                    usage["completion_tokens"] = estimated_completion
                    usage["total_tokens"] = usage["prompt_tokens"] + estimated_completion

                logger.info(
                    "[LLM-Stream] stream completed, total_length=%d, tokens: prompt=%d, completion=%d, total=%d",
                    len(full_content),
                    usage["prompt_tokens"],
                    usage["completion_tokens"],
                    usage["total_tokens"],
                )
                yield {"type": "done", "usage": usage}

        except Exception as e:
            logger.error("[LLM-Stream] stream call failed: %s", e)
            yield {"type": "error", "message": str(e)}

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接池资源"""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
