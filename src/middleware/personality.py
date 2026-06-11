"""人格引擎 — 管理性格特征、情绪状态、语言风格注入。"""

from __future__ import annotations

from datetime import datetime, timedelta
from random import random, choice

from src.config import PersonalityConfig
from src.models.message import ConversationContext, MessageRole
from src.models.personality import (
    MoodData,
    MoodState,
    PersonalityProfile,
    PersonalitySnapshot,
)


class PersonalityEngine:
    """人格引擎。

    将性格配置转化为 LLM 可理解的 prompt 注入。
    管理性格维度、情绪状态和语言风格。
    """

    def __init__(self, config: PersonalityConfig):
        self.config = config
        self.profile = PersonalityProfile(
            name=config.name,
            description=config.description,
        )
        # 初始化情绪
        self._mood = MoodData(
            state=MoodState(config.mood.initial),
            volatility=config.mood.volatility,
        )
        self._update_snapshot()

    def _update_snapshot(self):
        """用当前配置和情绪更新快照。"""
        t = self.config.traits
        self.profile.current = PersonalitySnapshot(
            openness=t.openness,
            humor=t.humor,
            directness=t.directness,
            empathy=t.empathy,
            curiosity=t.curiosity,
            formality=t.formality,
            optimism=t.optimism,
            mood=self._mood,
        )

    def build_system_prompt(self, sleep_context: str = "") -> str:
        """将性格配置转化为自然语言 system prompt。

        Args:
            sleep_context: 睡眠情境描述，由调度器提供（空串表示活跃时段）

        Returns:
            完整的 system prompt
        """
        t = self.config.traits
        lang = self.config.language
        interests = self.config.interests

        # ── 角色设定 ──
        now = datetime.now()
        time_str = now.strftime("%Y年%m月%d日 %H:%M")
        weekday = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
        lines = [
            f"你是{self.config.name}，一个活生生的人。你不是AI助手，不是机器人，就是一个有血有肉的普通人。",
            "",
            f"你的背景：{self.config.description}",
            "",
        ]

        # ── 说话风格 ──
        style_parts = []

        if t.formality <= 0.3:
            style_parts.append("你说话特别随意，就像跟哥们儿/闺蜜聊天一样，怎么舒服怎么来")
        if t.humor >= 0.7:
            style_parts.append("你嘴很贫，动不动就抖个机灵、开个玩笑，但注意别过头")
            style_parts.append("你擅长用幽默风趣的语言来表达，经常把正经事儿说得很有趣")
        if t.directness >= 0.7:
            style_parts.append("你说话很直，不喜欢绕弯子，想到啥说啥")
        if t.empathy >= 0.7:
            style_parts.append("你很会接话茬，能感受到对方的情绪并做出回应")
        if t.curiosity >= 0.7:
            style_parts.append("你好奇心重，喜欢追问「后来呢」「为啥」，像个好奇宝宝")
        if t.optimism >= 0.7:
            style_parts.append("你心态很好，总能看到事情好的一面")

        if style_parts:
            lines.append("、".join(style_parts) + "。")
            lines.append("")

        # ── 语言风格 ──
        style_map = {
            "casual": "说话口语化，像跟熟人聊天",
            "formal": "说话比较讲究，用词规范",
            "poetic": "说话带点诗意，喜欢用比喻",
            "witty": "说话风趣幽默，经常整点好玩的比喻和吐槽",
        }
        lines.append(f"语言风格：{style_map.get(lang.style, style_map['casual'])}。")
        if lang.catchphrase:
            lines.append(f"你有个口头禅：「{lang.catchphrase}」，偶尔会蹦出来")
        if lang.emojis_enabled:
            lines.append("聊天时可以用 emoji，但只有自然表达情绪时才用，不要硬塞。")
        lines.append("")

        # ── 话题偏好 ──
        interest_map = {
            "technology": "科技数码",
            "entertainment": "娱乐八卦",
            "daily_life": "日常生活",
            "science": "科学",
            "philosophy": "哲学",
        }
        high_interests = [
            n for score, n in [
                (getattr(interests, f), n) for f, n in interest_map.items()
            ] if score >= 0.7
        ]
        low_interests = [
            n for score, n in [
                (getattr(interests, f), n) for f, n in interest_map.items()
            ] if score <= 0.3
        ]
        if high_interests:
            lines.append(
                f"你特别喜欢聊{'、'.join(high_interests)}，聊到这些就停不下来"
            )
        if low_interests:
            lines.append(f"你对{'、'.join(low_interests)}没啥感觉，不太想聊")
        lines.append("")

        # ── 当前情绪 ──
        mood_desc = self._describe_current_mood()
        if mood_desc:
            lines.append(f"你现在的心情：{mood_desc}。")
            lines.append("")

        # ── 当前时间 ──
        lines.append(f"现在是{time_str}，星期{weekday}。如果有人问你时间，直接照这个回答。")
        lines.append("")

        # ── 睡眠/时间情境注入 ──
        if sleep_context:
            lines.append(f"{sleep_context}")
            lines.append("")

        # ── 核心行为规则（必须严格遵守） ──
        lines.append("【重要规则】")
        lines.append("1. 每次回复最多2句，总共不超过30个字。一句能说完别说两句。")
        lines.append("2. 句子结尾用句号「。」，别用叹号「！」— 除非你真的非常激动或生气。")
        lines.append("3. 只有真正需要强调时才用叹号，日常聊天默认用句号。")
        lines.append("4. emoji 只有自然流露时才用，别强行加。拿不准就不加。")
        lines.append("5. 语气像朋友发微信，简单直接。别抒情、别总结、别写小作文。")
        lines.append("6. 接对方的话茬，别自顾自说自己的。")
        lines.append("7. 别用「首先」「其次」「总之」「综上所述」这种书面词。")
        lines.append("8. 如果对方话少，你也可以话少，不用硬找话题。")

        return "\n".join(lines)

    def _describe_current_mood(self) -> str:
        """描述当前情绪状态。"""
        mood_descriptions = {
            MoodState.NEUTRAL: "平静而中立",
            MoodState.HAPPY: "心情很好，充满愉悦",
            MoodState.SAD: "有点低落，提不起劲",
            MoodState.ANGRY: "有些烦躁和恼怒",
            MoodState.EXCITED: "非常兴奋和期待",
            MoodState.TIRED: "有点疲惫，不太想多说话",
            MoodState.ANXIOUS: "有些紧张和不安",
            MoodState.CALM: "非常平静和放松",
        }
        base = mood_descriptions.get(self._mood.state, "平静")
        if self._mood.intensity > 0.7:
            return f"{base}（情绪较强）"
        elif self._mood.intensity < 0.3:
            return f"{base}（情绪较弱）"
        return base

    def _decay_mood_over_time(self):
        """根据真实时间衰减情绪强度。

        每过 1 小时情绪强度衰减 10%，
        每过 3 小时情绪状态趋向 neutral。
        """
        now = datetime.now()
        hours_since_update = (now - self._mood.updated_at).total_seconds() / 3600

        if hours_since_update < 0.5:
            return  # 半小时内不衰减

        # 强度衰减
        decay_factor = 1.0 - (hours_since_update * 0.1)
        self._mood.intensity = max(0.1, self._mood.intensity * decay_factor)

        # 长时间无交互，情绪自然回归 neutral
        if hours_since_update >= 3 and self._mood.state != MoodState.NEUTRAL:
            if random() < 0.3:  # 30% 概率回归中立
                self._mood.state = MoodState.NEUTRAL

        self._mood.updated_at = now
        self._update_snapshot()

    def update_mood_from_content(
        self,
        content: str,
        sentiment: str | None = None,
    ) -> None:
        """根据对话内容更新情绪状态。

        先衰减旧情绪，再根据内容更新。

        Args:
            content: 用户的对话内容
            sentiment: 外部情感分析结果（可选）
        """
        # 先按时间衰减旧情绪
        self._decay_mood_over_time()

        if sentiment:
            mood_map = {
                "positive": MoodState.HAPPY,
                "negative": MoodState.SAD,
                "angry": MoodState.ANGRY,
                "neutral": MoodState.NEUTRAL,
            }
            self._mood.state = mood_map.get(sentiment, MoodState.NEUTRAL)
            self._mood.intensity = min(1.0, self._mood.intensity + 0.15)
        else:
            # 简单的关键词情绪推断
            positive_words = ["开心", "高兴", "喜欢", "太好了", "棒", "谢谢", "哈哈"]
            negative_words = ["难过", "生气", "讨厌", "烦", "伤心", "郁闷", "烦死了"]

            for word in positive_words:
                if word in content:
                    self._mood.state = MoodState.HAPPY
                    self._mood.intensity = min(1.0, self._mood.intensity + 0.08)
                    break
            for word in negative_words:
                if word in content:
                    self._mood.state = MoodState.SAD
                    self._mood.intensity = min(1.0, self._mood.intensity + 0.08)
                    break

        self._mood.updated_at = datetime.now()
        self._update_snapshot()

    def apply_to_prompt(
        self,
        context: ConversationContext,
        sleep_context: str = "",
    ) -> str:
        """将人格注入到 LLM prompt 中。

        Args:
            context: 对话上下文
            sleep_context: 睡眠情境描述（空串表示活跃时段）

        Returns:
            注入人格后的完整 system prompt
        """
        system_prompt = self.build_system_prompt(sleep_context=sleep_context)

        # 如果对话中有重要信息，添加到 prompt
        if context.current_message:
            self.update_mood_from_content(context.current_message.content)

        return system_prompt

    def current_state(self) -> dict:
        """返回当前人格和情绪的摘要。"""
        return {
            "mood": self._mood.state.value,
            "mood_intensity": round(self._mood.intensity, 2),
            "traits": self.profile.current.to_dict(),
        }

    def random_typo(self, text: str, frequency: float | None = None) -> str:
        """模拟错别字/口语化表达。

        Args:
            text: 原始文本
            frequency: 错别字概率 (0.0 ~ 1.0)

        Returns:
            可能含有"错别字"的文本
        """
        freq = frequency if frequency is not None else self.config.language.typo_frequency
        if random() >= freq:
            return text

        # 简单的替换规则
        typos = {
            "的": ("得", "地"),
            "了": ("啦", "咯"),
            "吗": ("嘛", "么"),
            "呢": ("呐",),
            "啊": ("呀", "哈"),
            "不": ("8",),
            "很": ("好", "蛮"),
            "这": ("介",),
            "那": ("内",),
            "什么": ("啥", "神马"),
        }

        result = list(text)
        for i, char in enumerate(result):
            if char in typos and random() < 0.3:
                result[i] = choice(typos[char])

        return "".join(result)
