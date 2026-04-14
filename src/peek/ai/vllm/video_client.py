# -*- coding: utf-8 -*-
"""vLLM Video Client - vLLM 视频多模态客户端

实现与 vLLM 服务器的 HTTP 通信，支持视频输入和 logprobs 返回。
使用 OpenAI 兼容的 API 格式。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ========== Response 对象类定义 ==========


class LogprobToken:
    """Logprob token 数据结构"""

    __slots__ = ("token", "logprob", "top_logprobs")

    def __init__(self, data: Dict):
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

    def __init__(self, data: Optional[Dict]):
        self.content: Optional[List[LogprobToken]] = (
            [LogprobToken(item) for item in data.get("content", [])] if data else None
        )


class Message:
    """消息数据结构"""

    __slots__ = ("content", "role")

    def __init__(self, data: Dict):
        self.content: str = data.get("content", "")
        self.role: str = data.get("role", "assistant")


class Choice:
    """Choice 数据结构"""

    __slots__ = ("message", "logprobs")

    def __init__(self, data: Dict):
        self.message: Message = Message(data.get("message", {}))
        self.logprobs: Optional[Logprobs] = (
            Logprobs(data.get("logprobs", {})) if data.get("logprobs") else None
        )


class ChatCompletionResponse:
    """Chat completion 响应数据结构"""

    __slots__ = ("choices", "model", "usage")

    def __init__(self, data: Dict):
        self.choices: List[Choice] = [Choice(c) for c in data.get("choices", [])]
        self.model: str = data.get("model", "")
        self.usage: Dict = data.get("usage", {})


# ========== 客户端 ==========


@dataclass
class VLLMVideoClient:
    """vLLM 视频多模态客户端

    通过 HTTP 与 vLLM 服务器通信，支持视频输入和 logprobs 返回。
    内部复用 httpx.AsyncClient 连接池以提升性能。
    """

    host: str = "localhost"
    port: int = 8000
    api_key: str = ""
    model_name: str = "Qwen/Qwen2.5-VL-72B-Instruct"
    max_tokens: int = 512
    temperature: float = 0.0
    top_p: float = 0.9
    timeout: int = 120

    def __post_init__(self):
        """初始化客户端"""
        self._base_url = f"http://{self.host}:{self.port}"
        self._headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"
        # 复用 httpx 连接池，避免每次请求创建新连接
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def base_url(self) -> str:
        """获取基础 URL"""
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
        """发送聊天补全请求（支持视频输入和 logprobs）

        Args:
            messages: 消息列表
            model: 模型名称
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
        url = f"{base_url}/v1/chat/completions"

        payload = {
            "model": model or self.model_name,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": stream,
        }

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
        """获取可用模型列表"""
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
            return httpx.AsyncClient(timeout=timeout)
        return self._http_client

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接池资源"""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
