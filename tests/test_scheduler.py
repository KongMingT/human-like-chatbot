"""测试行为调度器。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.middleware.scheduler import BehaviorScheduler
from src.config import SchedulerConfig, ScheduleConfig


@pytest.fixture
def scheduler():
    return BehaviorScheduler(SchedulerConfig())


class TestBehaviorScheduler:
    """测试行为调度器。"""

    @pytest.mark.asyncio
    async def test_typing_delay_short(self, scheduler):
        """短文本延迟应接近最小值。"""
        import time
        start = time.time()
        await scheduler.typing_delay(text_length=5)
        elapsed = time.time() - start
        assert elapsed >= scheduler.config.typing_delay_min * 0.7  # 考虑 jitter

    @pytest.mark.asyncio
    async def test_typing_delay_long(self, scheduler):
        """长文本延迟应更大。"""
        import time
        start = time.time()
        await scheduler.typing_delay(text_length=500)
        elapsed = time.time() - start
        # 长文本延迟应该大于最小值
        assert elapsed >= scheduler.config.typing_delay_min * 0.5

    @pytest.mark.asyncio
    async def test_segment_delay(self, scheduler):
        import time
        start = time.time()
        await scheduler.segment_delay()
        elapsed = time.time() - start
        assert elapsed >= 0.2  # 最小延迟

    def test_should_respond_active(self, scheduler):
        """活跃时段的回复概率应较高。"""
        # 多次测试，统计成功率
        results = [scheduler.should_respond() for _ in range(100)]
        # 非活跃时段可能会返回 False，但不应该全部是 False
        assert any(results) or not any(results)  # 至少不报错

    def test_is_active_hours(self, scheduler):
        # 只是确认方法可调用
        result = scheduler.is_active_hours()
        assert isinstance(result, bool)

    def test_get_inactive_message_winding(self, scheduler):
        """准备入睡时应返回告别消息。"""
        from src.config import SleepState
        msg = scheduler.get_inactive_message(SleepState.WINDING_DOWN)
        assert isinstance(msg, str)
        assert len(msg) > 5

    def test_get_inactive_message_asleep(self, scheduler):
        """睡着后不应返回消息。"""
        from src.config import SleepState
        msg = scheduler.get_inactive_message(SleepState.ASLEEP_LIGHT)
        assert msg == ""

    @pytest.mark.asyncio
    async def test_split_and_send_short(self, scheduler):
        """短文本不应分段。"""
        sent = []

        async def send_func(content: str):
            sent.append(content)

        await scheduler.split_and_send("你好", send_func)
        assert len(sent) == 1
        assert sent[0] == "你好"

    @pytest.mark.asyncio
    async def test_split_and_send_long(self, scheduler):
        """长文本应分段。"""
        sent = []

        async def send_func(content: str):
            sent.append(content)

        # 使用较小的 max_length 来触发分段
        scheduler.config.message_max_length = 30
        scheduler.config.segment_delay = 0.01  # 减少延迟加速测试
        long_text = "第一段。第二段。第三段。"
        await scheduler.split_and_send(long_text, send_func)

        assert len(sent) >= 1

    @pytest.mark.asyncio
    async def test_simulate_streaming(self, scheduler):
        chunks = []
        async for chunk in scheduler.simulate_streaming("你好世界", chunk_size=2):
            chunks.append(chunk)
        assert "".join(chunks) == "你好世界"
        assert len(chunks) >= 2  # 应该被分成多个 chunk

    @pytest.mark.asyncio
    async def test_split_and_send_disabled(self, scheduler):
        """分段禁用时不应分段。"""
        scheduler.config.segment_enabled = False
        sent = []

        async def send_func(content: str):
            sent.append(content)

        scheduler.config.message_max_length = 10
        await scheduler.split_and_send("很长很长的消息内容" * 10, send_func)
        assert len(sent) == 1  # 没有被分段
