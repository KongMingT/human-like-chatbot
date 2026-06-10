"""行为调度器 — 控制机器人的「人类行为特征」。

包括：打字延迟、发送节奏、作息规律、随机扰动。
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import AsyncGenerator

from src.config import SchedulerConfig
from src.models.message import Message


class BehaviorScheduler:
    """行为调度器。

    模拟人类行为特征，让机器人显得更自然。
    """

    def __init__(self, config: SchedulerConfig):
        self.config = config
        self._last_active_check: datetime | None = None

    async def typing_delay(self, text_length: int) -> None:
        """模拟打字延迟。

        根据回复长度动态计算延迟（150ms-3s）。

        Args:
            text_length: 回复文本长度（字符数）
        """
        # 基础延迟 + 长度相关延迟
        base = self.config.typing_delay_min
        per_char = (self.config.typing_delay_max - self.config.typing_delay_min) / 200
        calc_delay = base + (text_length * per_char)

        # 加入随机扰动 (±30%)
        jitter = random.uniform(-0.3, 0.3)
        delay = calc_delay * (1 + jitter)

        # 限制在配置范围内
        delay = max(self.config.typing_delay_min, min(self.config.typing_delay_max, delay))

        await asyncio.sleep(delay)

    async def segment_delay(self) -> None:
        """分段发送的间隔延迟。"""
        jitter = random.uniform(-0.2, 0.2)
        delay = self.config.segment_delay * (1 + jitter)
        await asyncio.sleep(max(0.3, delay))

    def should_respond(self) -> bool:
        """根据作息时间判断是否应该回复。"""
        current_hour = datetime.now(timezone.utc).hour + 8  # UTC+8

        start = self.config.schedule.active_hours_start
        end = self.config.schedule.active_hours_end

        if start <= current_hour < end:
            # 活跃时段
            return random.random() < self.config.schedule.response_rate_active
        else:
            # 非活跃时段
            return random.random() < self.config.schedule.response_rate_inactive

    def is_active_hours(self) -> bool:
        """检查当前是否为活跃时段。"""
        current_hour = datetime.now(timezone.utc).hour + 8
        start = self.config.schedule.active_hours_start
        end = self.config.schedule.active_hours_end
        return start <= current_hour < end

    def get_inactive_message(self) -> str:
        """获取非活跃时段的自动回复。"""
        messages = [
            "唔…现在有点晚了，刚准备睡，明天再聊吧~",
            "哈欠～现在不是我活跃的时间呢，明天再回复你哦",
            "抱歉，现在不太方便聊天，明天再说！",
            "呼…好困，明天再聊啦～",
        ]
        return random.choice(messages)

    async def split_and_send(
        self,
        content: str,
        send_func,
    ) -> None:
        """将长回复按句子逐条发送。

        每条句子独立发送，模拟真人一条一条发消息的效果。
        如果单句超长，再按逗号拆分。

        Args:
            content: 完整回复内容
            send_func: 发送消息的异步函数，接收字符串参数
        """
        if not self.config.segment_enabled or len(content) <= self.config.message_max_length:
            await send_func(content)
            return

        import re

        # 1. 按强分隔符拆成独立句子（句号、感叹号、问号、换行）
        #    re.split 保留分隔符，避免丢失标点
        parts = re.split(r"([。！？\n.!?])", content)
        sentences = []
        buffer = ""

        for p in parts:
            buffer += p
            if p in "。！？\n.!?" and buffer.strip():
                sentences.append(buffer.strip())
                buffer = ""
        if buffer.strip():
            sentences.append(buffer.strip())

        # 2. 逐句处理：太长的句子再按逗号拆
        final_segments = []
        for sent in sentences:
            if len(sent) <= self.config.message_max_length:
                final_segments.append(sent)
            else:
                # 按逗号/分号进一步拆分
                sub = re.split(r"([，,；;])", sent)
                buf = ""
                for p in sub:
                    if len(buf) + len(p) < self.config.message_max_length:
                        buf += p
                    else:
                        if buf.strip():
                            final_segments.append(buf.strip())
                        buf = p
                    if p in "，,；;" and buf.strip():
                        final_segments.append(buf.strip())
                        buf = ""
                if buf.strip():
                    final_segments.append(buf.strip())

        # 3. 逐条发送
        for i, seg in enumerate(final_segments):
            if seg.strip():
                await send_func(seg.strip())
                if i < len(final_segments) - 1:
                    await self.segment_delay()

    async def simulate_streaming(
        self,
        content: str,
        chunk_size: int = 3,
    ) -> AsyncGenerator[str, None]:
        """模拟逐字输出的流式效果。

        Args:
            content: 完整回复内容
            chunk_size: 每次输出的字符数

        Yields:
            每次输出一个文本块
        """
        i = 0
        while i < len(content):
            chunk = content[i:i + chunk_size]
            yield chunk
            i += chunk_size
            # 模拟打字速度变化
            delay = random.uniform(0.03, 0.12)
            await asyncio.sleep(delay)
