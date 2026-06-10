"""测试平台抽象层。"""

import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.platform.base import BaseBot
from src.models.message import Message, MessageType, PlatformEvent


class MockBot(BaseBot):
    """用于测试的 Mock Bot 实现。"""

    def __init__(self, config=None):
        super().__init__(config)
        self._connected = False
        self._sent_messages: list[Message] = []

    async def start(self):
        self._connected = True

    async def stop(self):
        self._connected = False

    async def send_message(self, message: Message) -> bool:
        self._sent_messages.append(message)
        return True

    async def listen(self) -> AsyncGenerator[Message, None]:
        yield Message(content="测试消息", sender_name="测试")

    @property
    def platform_name(self) -> str:
        return "mock"

    @property
    def is_connected(self) -> bool:
        return self._connected


class TestBaseBot:
    """测试 BaseBot 抽象基类。"""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        bot = MockBot()
        assert not bot.is_connected

        await bot.start()
        assert bot.is_connected

        await bot.stop()
        assert not bot.is_connected

    @pytest.mark.asyncio
    async def test_send_message(self):
        bot = MockBot()
        msg = Message(content="你好", sender_name="我")

        result = await bot.send_message(msg)
        assert result is True
        assert len(bot._sent_messages) == 1
        assert bot._sent_messages[0].content == "你好"

    @pytest.mark.asyncio
    async def test_on_message_handler(self):
        bot = MockBot()
        received: list[Message] = []

        @bot.on_message
        async def handler(msg: Message):
            received.append(msg)

        msg = Message(content="测试")
        await bot.dispatch_message(msg)
        assert len(received) == 1
        assert received[0].content == "测试"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        bot = MockBot()
        results: list[str] = []

        @bot.on_message
        async def handler1(msg: Message):
            results.append("h1")

        @bot.on_message
        async def handler2(msg: Message):
            results.append("h2")

        await bot.dispatch_message(Message(content="test"))
        assert "h1" in results
        assert "h2" in results

    @pytest.mark.asyncio
    async def test_on_event_handler(self):
        bot = MockBot()
        received: list[PlatformEvent] = []

        @bot.on_event("group_increase")
        async def handler(event: PlatformEvent):
            received.append(event)

        event = PlatformEvent(type="group_increase", platform="mock")
        await bot.dispatch_event(event)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_platform_name(self):
        bot = MockBot()
        assert bot.platform_name == "mock"

    def test_abstract_methods(self):
        """确认 BaseBot 不能直接实例化。"""
        with pytest.raises(TypeError):
            BaseBot()  # type: ignore
