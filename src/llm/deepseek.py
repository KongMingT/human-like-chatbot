"""DeepSeek API 实现 — 使用 OpenAI 兼容接口调用 DeepSeek。"""

from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx

from src.llm.base import BaseLLM, LLMResponse


class DeepSeekLLM(BaseLLM):
    """DeepSeek API 适配器。

    通过 OpenAI 兼容接口调用 DeepSeek 模型。
    支持同步（chat）和流式（chat_stream）两种模式。
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        ).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def chat(
        self,
        messages: list[dict],
        **kwargs,
    ) -> LLMResponse:
        """非流式聊天。"""
        payload = self._build_payload(messages, **kwargs)
        payload["stream"] = False

        max_retries = kwargs.get("retry_max", self.config.get("retry_max", 3))
        retry_delay = kwargs.get("retry_delay", self.config.get("retry_delay", 2.0))

        import asyncio

        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    "/v1/chat/completions",
                    headers=self._build_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                choice = data["choices"][0]
                return LLMResponse(
                    content=choice["message"]["content"],
                    model=data.get("model", ""),
                    usage=data.get("usage"),
                    finish_reason=choice.get("finish_reason", ""),
                )

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2**attempt))
                # 最后尝试：不重新抛出，让循环结束

        raise RuntimeError(f"LLM 调用失败: {last_error}")

    async def chat_stream(
        self,
        messages: list[dict],
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式聊天，逐块生成回复。"""
        payload = self._build_payload(messages, **kwargs)
        payload["stream"] = True

        async with self.client.stream(
            "POST",
            "/v1/chat/completions",
            headers=self._build_headers(),
            json=payload,
        ) as response:
            if response.status_code >= 400:
                error_text = await response.aread()
                raise RuntimeError(
                    f"流式调用失败: {response.status_code} {error_text.decode()}"
                )

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
