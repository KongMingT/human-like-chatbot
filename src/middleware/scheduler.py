"""行为调度器 — 控制机器人的「人类行为特征」。

包括：打字延迟、发送节奏、睡眠状态机、作息规律、随机扰动。
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import AsyncGenerator

from src.config import SchedulerConfig, SleepState
from src.models.message import Message


class BehaviorScheduler:
    """行为调度器。

    管理睡眠状态机，模拟人类作息和行为特征。
    """

    # ── 睡眠状态机 ──────────────────────────────────

    def get_sleep_state(self) -> SleepState:
        """根据当前时间判断睡眠状态。

        状态转换：
        AWAKE  (08:00-22:00)  活跃
        WINDING_DOWN (回22:00-23:00)  准备入睡
        ASLEEP_LIGHT (23:00-00:00)  浅睡
        ASLEEP_DEEP (00:00-06:00)  深睡
        WAKING_UP (06:00-08:00)  刚醒

        周末会偏移作息。
        """
        now = datetime.now(timezone.utc)
        hour = now.hour + 8  # UTC+8

        # 周末偏移
        is_weekend = now.weekday() >= 5  # 周六=5, 周日=6
        offset = self.config.schedule.weekend_offset if is_weekend else 0

        s = self.config.schedule

        if s.deep_sleep_end + offset <= hour < s.waking_up_end + offset:
            return SleepState.WAKING_UP
        elif s.waking_up_end + offset <= hour < s.wind_down_start:
            return SleepState.AWAKE
        elif s.wind_down_start <= hour < s.light_sleep_start:
            return SleepState.WINDING_DOWN
        elif s.light_sleep_start <= hour < 24 or hour < s.deep_sleep_start:
            return SleepState.ASLEEP_LIGHT
        else:
            return SleepState.ASLEEP_DEEP

    def get_sleep_state_name(self) -> str:
        """获取睡眠状态的中文描述。"""
        return {
            SleepState.AWAKE: "活跃",
            SleepState.WINDING_DOWN: "犯困",
            SleepState.ASLEEP_LIGHT: "浅睡",
            SleepState.ASLEEP_DEEP: "深睡",
            SleepState.WAKING_UP: "刚醒",
        }.get(self.get_sleep_state(), "活跃")

    def is_active_hours(self) -> bool:
        """兼容旧接口：检查当前是否为活跃时段。"""
        return self.get_sleep_state() == SleepState.AWAKE

    def should_respond(self, sleep_state: SleepState | None = None) -> bool:
        """根据睡眠状态判断是否应该回复。

        Args:
            sleep_state: 指定的睡眠状态，为 None 时自动获取

        Returns:
            是否应回复
        """
        state = sleep_state or self.get_sleep_state()
        s = self.config.schedule

        rate_map = {
            SleepState.AWAKE: s.response_rate_active,
            SleepState.WINDING_DOWN: s.response_rate_winding,
            SleepState.ASLEEP_LIGHT: s.response_rate_light,
            SleepState.ASLEEP_DEEP: s.response_rate_deep,
            SleepState.WAKING_UP: s.response_rate_waking,
        }
        rate = rate_map.get(state, s.response_rate_active)
        return random.random() < rate

    async def typing_delay(self, text_length: int, sleep_state: SleepState | None = None) -> None:
        """模拟打字延迟（受睡眠状态影响）。

        睡眠越深，打字越慢。

        Args:
            text_length: 回复文本长度（字符数）
            sleep_state: 当前睡眠状态
        """
        state = sleep_state or self.get_sleep_state()

        # 基础延迟 + 长度相关延迟
        base = self.config.typing_delay_min
        per_char = (self.config.typing_delay_max - self.config.typing_delay_min) / 200
        calc_delay = base + (text_length * per_char)

        # 睡眠状态打字速度倍率
        speed_map = {
            SleepState.AWAKE: 1.0,
            SleepState.WINDING_DOWN: self.config.schedule.typing_speed_mult_winding,
            SleepState.ASLEEP_LIGHT: self.config.schedule.typing_speed_mult_light,
            SleepState.ASLEEP_DEEP: 3.0,  # 深睡时基本不会打字
            SleepState.WAKING_UP: self.config.schedule.typing_speed_mult_waking,
        }
        multiplier = speed_map.get(state, 1.0)

        delay = calc_delay * multiplier

        # 加入随机扰动 (±40%)，睡眠时扰动更大
        jitter_range = 0.4 if state == SleepState.AWAKE else 0.6
        jitter = random.uniform(-jitter_range, jitter_range)
        delay = delay * (1 + jitter)

        # 限制在配置范围内（睡眠时上限放宽）
        max_delay = self.config.typing_delay_max * multiplier
        delay = max(self.config.typing_delay_min * 0.5, min(max_delay, delay))

        await asyncio.sleep(delay)

    # ── 睡眠唤醒追踪 ──────────────────────────────

    def __init__(self, config: SchedulerConfig):
        self.config = config
        self._last_active_check: datetime | None = None
        # 记录每个用户在睡眠时段最后一次被回复的时间
        self._woke_up: dict[str, datetime] = {}

        # ── 对话疲劳追踪 ──
        # 每个用户的连续对话轮次（短时间内）
        self._conversation_streak: dict[str, int] = {}
        # 上次对话时间
        self._last_conversation_time: dict[str, datetime] = {}

    # ── 对话疲劳 ──────────────────────────────────

    def record_interaction(self, session_id: str):
        """记录一次对话交互，用于计算疲劳度。"""
        now = datetime.now()
        last = self._last_conversation_time.get(session_id)

        # 如果超过 5 分钟没说话，重置连续计数
        if last and (now - last).total_seconds() > 300:
            self._conversation_streak[session_id] = 0

        self._conversation_streak[session_id] = self._conversation_streak.get(session_id, 0) + 1
        self._last_conversation_time[session_id] = now

    def get_fatigue_level(self, session_id: str) -> float:
        """获取当前疲劳度 (0~1)。

        连续对话越多越疲劳。
        超过 10 轮后达到最高疲劳。
        """
        streak = self._conversation_streak.get(session_id, 0)
        now = datetime.now()
        last = self._last_conversation_time.get(session_id)

        # 长时间没说话，疲劳清零
        if last and (now - last).total_seconds() > 300:
            self._conversation_streak[session_id] = 0
            return 0.0

        # 10 轮对话达到最大疲劳
        fatigue = min(streak / 10, 1.0)
        return round(fatigue, 2)

    def get_fatigue_behavior(self, session_id: str) -> dict:
        """根据疲劳度返回行为调整参数。"""
        fatigue = self.get_fatigue_level(session_id)

        if fatigue < 0.3:
            return {"reply_multiplier": 1.0, "ending_chance": 0.0}
        elif fatigue < 0.6:
            return {"reply_multiplier": 0.7, "ending_chance": 0.15}
        elif fatigue < 0.8:
            return {"reply_multiplier": 0.5, "ending_chance": 0.3}
        else:
            return {"reply_multiplier": 0.3, "ending_chance": 0.5}

    def get_fatigue_context(self, session_id: str) -> str:
        """生成疲劳相关的 prompt 上下文。"""
        fatigue = self.get_fatigue_level(session_id)

        if fatigue < 0.3:
            return ""
        elif fatigue < 0.6:
            return "你们已经聊了一会儿了，你稍微有点累，回复可以短一点。"
        elif fatigue < 0.8:
            return "你们聊了好一阵了，你有点累了，不太想继续长篇大论。"
        else:
            return "你已经聊了很久了，很累了，想结束对话了。回复尽量简短，甚至可以暗示想休息。"

    def mark_woke_up(self, session_id: str):
        """标记某个用户的消息把机器人「吵醒」了。"""
        self._woke_up[session_id] = datetime.now()

    def was_just_woken(self, session_id: str, cooldown_minutes: int = 3) -> bool:
        """检查该用户是否刚把机器人吵醒（冷却期内不再重复吵醒）。

        Args:
            session_id: 用户标识
            cooldown_minutes: 冷却分钟数

        Returns:
            True 表示还在冷却期内（刚醒过，不应再回）
        """
        last = self._woke_up.get(session_id)
        if last is None:
            return False
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed < cooldown_minutes * 60

    def get_inactive_message(self, sleep_state: SleepState | None = None) -> str:
        """根据睡眠状态判断是否返回一条「告别消息」。

        注意：只有准备入睡（WINDING_DOWN）时会返回告别消息。
        已经睡着后（ASLEEP_LIGHT/DEEP）不返回任何消息 — 没反应就是最好的反应。

        Args:
            sleep_state: 当前睡眠状态

        Returns:
            回复文本，空字符串表示不回复
        """
        state = sleep_state or self.get_sleep_state()

        # 已经睡着了 → 完全不回复（没看到消息）
        if state in (SleepState.ASLEEP_LIGHT, SleepState.ASLEEP_DEEP):
            return ""

        messages = {
            SleepState.WINDING_DOWN: [
                "哈欠～好困了，明天再聊吧...",
                "眼睛快睁不开了，先睡了晚安~",
                "唔…今天先到这儿吧，明天见~",
            ],
            SleepState.WAKING_UP: [
                "嗯…早啊…刚醒，脑子还有点懵…",
                "哈欠～早…让我先清醒一下…",
                "唔…现在几点了…等我缓一缓…",
            ],
            SleepState.AWAKE: [
                "嗯？刚没看到消息，怎么了？",
                "啊，不好意思刚才走神了，你说~",
            ],
        }
        choices = messages.get(state, messages[SleepState.AWAKE])
        return random.choice(choices)

    def get_sleep_context(self, sleep_state: SleepState | None = None) -> str:
        """获取用于注入 prompt 的睡眠情境描述。"""
        state = sleep_state or self.get_sleep_state()
        now = datetime.now(timezone.utc)
        hour = now.hour + 8

        contexts = {
            SleepState.WINDING_DOWN: (
                f"现在是深夜{hour}点，你还没睡着，但已经在床上了，"
                "眼皮很重，脑子转不动。对方这时候发消息过来，"
                "你迷迷糊糊地摸到手机回复。语气要含糊简短，像半睡半醒的人。"
                "回完这条你可能就直接睡着了。"
            ),
            SleepState.ASLEEP_LIGHT: (
                f"现在是深夜{hour}点，你本来已经睡着了，"
                "被手机消息提示音吵醒了。你迷迷糊糊地摸到手机，"
                "眼睛都睁不开，打字也不利索。"
                "回完这条大概率又直接睡着了，对方再发消息你可能就看不到了。"
                "说话要简短含糊，像被吵醒的人。"
            ),
            SleepState.ASLEEP_DEEP: "",
            SleepState.WAKING_UP: (
                f"现在是早晨{hour}点，你刚刚被闹钟叫醒，"
                "眼睛还没完全睁开，脑子也还没开始转。"
                "摸到手机看到有消息，迷迷糊糊地回一下。"
                "说话要简简短短，带点刚醒的含糊感。"
            ),
            SleepState.AWAKE: "",
        }
        return contexts.get(state, "")

    async def segment_delay(self) -> None:
        """分段发送的间隔延迟。"""
        jitter = random.uniform(-0.2, 0.2)
        delay = self.config.segment_delay * (1 + jitter)
        await asyncio.sleep(max(0.3, delay))

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
