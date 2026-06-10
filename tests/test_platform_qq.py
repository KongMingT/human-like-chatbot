"""测试 QQ 平台适配器（原生 WebSocket 版本）。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.platform.qq import QQBot
from src.models.message import Message, MessageType


class TestQQBot:
    """测试 QQ 机器人适配器。"""

    @pytest.mark.asyncio
    async def test_import_error(self):
        """当 websockets 未安装时应有清晰提示。"""
        with patch.object(sys.modules.get("src.platform.qq"), "websockets", None):
            bot = QQBot()
            with pytest.raises(RuntimeError, match="websockets 未安装"):
                await bot.start()

    def test_platform_name(self):
        bot = QQBot()
        assert bot.platform_name == "qq"

    def test_not_connected_initially(self):
        bot = QQBot()
        assert not bot.is_connected

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """未启动时停止不应报错。"""
        bot = QQBot()
        await bot.stop()
        assert not bot.is_connected

    @pytest.mark.asyncio
    async def test_send_message_without_connection(self):
        bot = QQBot()
        msg = Message(content="测试")
        result = await bot.send_message(msg)
        assert result is False

    def test_ws_url_default(self):
        bot = QQBot()
        assert bot.ws_url == "ws://127.0.0.1:6700"

    def test_ws_url_custom(self):
        bot = QQBot({"host": "192.168.1.100", "port": 9090})
        assert bot.ws_url == "ws://192.168.1.100:9090"

    # --- 消息解析测试 ---

    def test_extract_text_from_string(self):
        bot = QQBot()
        assert bot._extract_text_from_segments("你好世界") == "你好世界"
        assert bot._extract_text_from_segments("") == ""

    def test_extract_text_from_segments_list(self):
        bot = QQBot()
        segments = [
            {"type": "text", "data": {"text": "前面"}},
            {"type": "face", "data": {"id": "123"}},
            {"type": "text", "data": {"text": "后面"}},
        ]
        assert bot._extract_text_from_segments(segments) == "前面后面"

    def test_extract_text_empty_list(self):
        bot = QQBot()
        assert bot._extract_text_from_segments([]) == ""

    def test_extract_text_non_text_segments(self):
        bot = QQBot()
        segments = [{"type": "face", "data": {"id": "1"}}]
        assert bot._extract_text_from_segments(segments) == ""

    def test_parse_private_message_string(self):
        bot = QQBot()
        data = {
            "message_id": 12345,
            "message_type": "private",
            "user_id": 10001,
            "message": "你好",
            "sender": {"nickname": "小明"},
        }
        msg = bot._parse_message(data)
        assert msg is not None
        assert msg.content == "你好"
        assert msg.type == MessageType.PRIVATE
        assert msg.sender_name == "小明"
        assert msg.sender_id == "10001"

    def test_parse_group_message(self):
        bot = QQBot()
        data = {
            "message_id": 67890,
            "message_type": "group",
            "user_id": 20002,
            "group_id": 999888,
            "message": "大家好",
            "sender": {"card": "群友A"},
        }
        msg = bot._parse_message(data)
        assert msg is not None
        assert msg.content == "大家好"
        assert msg.type == MessageType.GROUP
        assert msg.group_id == "999888"
        assert msg.sender_name == "群友A"

    def test_parse_message_with_segments(self):
        bot = QQBot()
        data = {
            "message_id": 1,
            "message_type": "private",
            "user_id": 10001,
            "message": [
                {"type": "text", "data": {"text": "第一段"}},
                {"type": "face", "data": {"id": "123"}},
                {"type": "text", "data": {"text": "第二段"}},
            ],
            "sender": {"nickname": "测试"},
        }
        msg = bot._parse_message(data)
        assert msg is not None
        assert msg.content == "第一段第二段"

    # --- @ 提及检测测试 ---

    def test_check_mention_at_bot(self):
        bot = QQBot()
        bot._bot_self_id = "12345"
        segments = [
            {"type": "at", "data": {"qq": "12345"}},
            {"type": "text", "data": {"text": "你好"}},
        ]
        assert bot._check_mention(segments) is True

    def test_check_mention_at_all(self):
        bot = QQBot()
        segments = [{"type": "at", "data": {"qq": "all"}}]
        assert bot._check_mention(segments) is True

    def test_check_mention_false(self):
        bot = QQBot()
        bot._bot_self_id = "12345"
        segments = [{"type": "text", "data": {"text": "你好"}}]
        assert bot._check_mention(segments) is False

    def test_check_mention_string_not_list(self):
        bot = QQBot()
        assert bot._check_mention("你好") is False
        assert bot._check_mention("") is False

    # --- listen / stop ---

    @pytest.mark.asyncio
    async def test_listen_stops_when_not_running(self):
        bot = QQBot()
        bot._running = False
        count = 0
        async for _ in bot.listen():
            count += 1
        assert count == 0

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        bot = QQBot()
        bot._running = True
        await bot.stop()
        assert not bot._running
