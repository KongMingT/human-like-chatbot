"""LLM 抽象接口 — 定义统一的聊天和流式调用接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator

from src.models.message import ConversationContext


@dataclass
class LLMResponse:
    """LLM 响应结果。"""

    content: str
    model: str = ""
    usage: dict | None = None
    finish_reason: str = ""


@dataclass
class LLMUsage:
    """Token 用量统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class BaseLLM(ABC):
    """大模型抽象基类。

    所有 LLM 实现（DeepSeek、OpenAI、本地模型等）需继承此类。
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        **kwargs,
    ) -> LLMResponse:
        """同步聊天（非流式）。

        Args:
            messages: OpenAI 格式的消息列表
                [{"role": "user"|"assistant"|"system", "content": "..."}]
            **kwargs: 额外参数（temperature, max_tokens 等）

        Returns:
            LLMResponse: 包含回复内容和用量统计
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式聊天，逐块生成回复内容。

        Args:
            messages: OpenAI 格式的消息列表
            **kwargs: 额外参数

        Yields:
            每次生成一个文本块
        """
        ...
        yield  # pragma: no cover

    async def chat_with_context(
        self,
        context: ConversationContext,
        system_prompt: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """基于对话上下文聊天（便捷方法）。

        将 ConversationContext 转换为消息列表后调用 chat()。
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in context.messages:
            role = "assistant" if msg.role == "assistant" else "user"
            messages.append({"role": role, "content": msg.content})

        return await self.chat(messages, **kwargs)

    def _build_headers(self) -> dict:
        """构建 API 请求头。子类可覆写。"""
        return {
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict],
        **kwargs,
    ) -> dict:
        """构建请求体。"""
        payload = {
            "model": kwargs.get("model", self.config.get("model", "")),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.8)),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 2048)),
            "stream": kwargs.get("stream", self.config.get("stream", False)),
        }
        return payload
