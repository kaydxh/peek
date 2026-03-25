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

        logger.debug(f"Sending request to vLLM: {url}")
        logger.debug(f"Request payload: {payload}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            result = response.json()

        logger.debug(f"vLLM response: {result}")
        return result

    async def health_check(self) -> bool:
        """健康检查

        检查 vLLM 服务器是否可用并且模型已就绪

        Returns:
            bool: 服务是否健康
        """
        try:
            url = f"{self._base_url}/v1/models"
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url, headers=self._headers)
                if response.status_code == 200:
                    data = response.json()
                    model_names = [model["id"] for model in data.get("data", [])]
                    is_ready = self.model_name in model_names
                    if not is_ready:
                        logger.debug(
                            f"Model {self.model_name} not ready yet, "
                            f"available models: {model_names}"
                        )
                    return is_ready
                else:
                    logger.debug(f"vLLM server returned status code: {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"vLLM health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """获取可用模型列表

        Returns:
            List[str]: 模型名称列表
        """
        try:
            url = f"{self._base_url}/v1/models"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
                result = response.json()
                return [model["id"] for model in result.get("data", [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
