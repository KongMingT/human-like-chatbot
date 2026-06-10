"""测试 LLM 接口抽象层和 DeepSeek 实现。"""

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.base import BaseLLM, LLMResponse
from src.llm.deepseek import DeepSeekLLM
from src.models.message import Message, ConversationContext


class MockLLM(BaseLLM):
    """用于测试的 Mock LLM 实现。"""

    async def chat(self, messages, **kwargs):
        return LLMResponse(
            content=f"回复: {messages[-1]['content']}",
            model="mock",
        )

    async def chat_stream(self, messages, **kwargs):
        content = f"回复: {messages[-1]['content']}"
        for char in content:
            yield char
            import asyncio
            await asyncio.sleep(0)


class TestBaseLLM:
    """测试 LLM 抽象基类。"""

    @pytest.mark.asyncio
    async def test_chat_with_context(self):
        llm = MockLLM()
        ctx = ConversationContext(
            messages=[Message(content="你好")],
            platform="qq",
            session_id="s001",
        )
        response = await llm.chat_with_context(ctx, system_prompt="你是一个助手")
        assert "你好" in response.content

    @pytest.mark.asyncio
    async def test_chat_with_context_with_history(self):
        llm = MockLLM()
        ctx = ConversationContext(
            messages=[
                Message(content="你好", role="user"),
                Message(content="你好！有什么可以帮你的？", role="assistant"),
                Message(content="今天天气如何？", role="user"),
            ],
            platform="qq",
            session_id="s001",
        )
        response = await llm.chat_with_context(ctx)
        assert "天气" in response.content

    def test_build_payload(self):
        llm = MockLLM()
        payload = llm._build_payload(
            [{"role": "user", "content": "hi"}],
            model="test-model",
            temperature=0.5,
        )
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0.5
        assert payload["messages"][0]["content"] == "hi"


class TestDeepSeekLLM:
    """测试 DeepSeek LLM 实现（使用 Mock HTTP）。"""

    @pytest.mark.asyncio
    async def test_chat_success(self, httpx_mock):
        llm = DeepSeekLLM()
        llm.api_key = "test-key"

        httpx_mock.add_response(
            url="https://api.deepseek.com/v1/chat/completions",
            json={
                "choices": [
                    {
                        "message": {"content": "你好！我是 DeepSeek。"},
                        "finish_reason": "stop",
                    }
                ],
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            },
        )

        response = await llm.chat([{"role": "user", "content": "你好"}])
        assert "你好" in response.content
        assert response.model == "deepseek-chat"
        assert response.usage["total_tokens"] == 30

        await llm.close()

    @pytest.mark.asyncio
    async def test_chat_retry_on_server_error(self, httpx_mock):
        llm = DeepSeekLLM(config={"retry_max": 2, "retry_delay": 0.1})
        llm.api_key = "test-key"

        # 第一次返回 500，第二次返回成功
        httpx_mock.add_response(status_code=500)
        httpx_mock.add_response(
            url="https://api.deepseek.com/v1/chat/completions",
            json={
                "choices": [{"message": {"content": "重试成功"}, "finish_reason": "stop"}],
                "model": "deepseek-chat",
            },
        )

        response = await llm.chat([{"role": "user", "content": "测试重试"}])
        assert response.content == "重试成功"

        await llm.close()

    @pytest.mark.asyncio
    async def test_chat_raises_on_all_failures(self, httpx_mock):
        llm = DeepSeekLLM(config={"retry_max": 2, "retry_delay": 0.1})
        llm.api_key = "test-key"

        # 全部返回 500
        httpx_mock.add_response(status_code=500)
        httpx_mock.add_response(status_code=500)

        with pytest.raises(RuntimeError, match="LLM 调用失败"):
            await llm.chat([{"role": "user", "content": "测试"}])

        await llm.close()

    @pytest.mark.asyncio
    async def test_chat_stream(self, httpx_mock):
        llm = DeepSeekLLM()
        llm.api_key = "test-key"

        # 模拟 SSE 流式响应
        stream_content = "data: {\"choices\": [{\"delta\": {\"content\": \"你好\"}}]}\n\ndata: {\"choices\": [{\"delta\": {\"content\": \"世界\"}}]}\n\ndata: [DONE]\n\n"
        httpx_mock.add_response(
            url="https://api.deepseek.com/v1/chat/completions",
            content=stream_content.encode(),
            headers={"Content-Type": "text/event-stream"},
        )

        chunks = []
        async for chunk in llm.chat_stream([{"role": "user", "content": "你好"}]):
            chunks.append(chunk)

        assert "".join(chunks) == "你好世界"

        await llm.close()

    @pytest.mark.asyncio
    async def test_chat_stream_error(self, httpx_mock):
        llm = DeepSeekLLM()
        llm.api_key = "test-key"

        httpx_mock.add_response(status_code=401)

        with pytest.raises(RuntimeError, match="流式调用失败"):
            async for _ in llm.chat_stream([{"role": "user", "content": "你好"}]):
                pass

        await llm.close()
