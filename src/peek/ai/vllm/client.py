# -*- coding: utf-8 -*-
"""vLLM Client - vLLM 通用文本聊天客户端

实现与 vLLM 服务器的 HTTP 通信，使用 OpenAI 兼容的 API 格式。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class VLLMClient:
    """vLLM 文本聊天客户端

    通过 HTTP 与 vLLM 服务器通信，使用 OpenAI 兼容的 API 格式。
    内部复用 httpx.AsyncClient 连接池以提升性能。
    """

    host: str = "localhost"
    port: int = 8000
    api_key: str = ""
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    timeout: int = 60

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
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """发送聊天补全请求

        使用 OpenAI 兼容的 /v1/chat/completions 端点

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            model: 模型名称，默认使用配置的模型
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            top_p: top_p 参数
            stream: 是否流式输出

        Returns:
            Dict: API 响应
        """
        url = f"{self._base_url}/v1/chat/completions"

        payload = {
            "model": model or self.model_name,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "top_p": top_p if top_p is not None else self.top_p,
            "stream": stream,
        }

        logger.debug("Sending request to vLLM: %s", url)
        logger.debug("Request payload: %s", payload)

        client = await self._get_client()
        response = await client.post(
            url,
            json=payload,
            headers=self._headers,
        )
        response.raise_for_status()
        result = response.json()

        logger.debug("vLLM response: %s", result)
        return result

    async def health_check(self) -> bool:
        """健康检查

        检查 vLLM 服务器是否可用并且模型已就绪

        Returns:
            bool: 服务是否健康
        """
        try:
            url = f"{self._base_url}/v1/models"
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
            url = f"{self._base_url}/v1/models"
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

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接池资源"""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
