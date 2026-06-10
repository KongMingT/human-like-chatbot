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

    def build_system_prompt(self) -> str:
        """将性格配置转化为自然语言 system prompt。"""
        t = self.config.traits
        lang = self.config.language
        interests = self.config.interests

        # ── 角色设定 ──
        lines = [
            f"你是{self.config.name}，一个活生生的人。你不是AI助手，不是机器人，就是一个有血有肉的普通人。",
            "",
            f"你的背景：{self.config.description}",
            "",
        ]

        # ── 说话风格（用第一人称，有画面感） ──
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
            lines.append("聊天的时候可以用点 emoji 表达情绪，别太多。")
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

        # ── 核心行为规则（必须严格遵守） ──
        lines.append("【重要规则】")
        lines.append("1. 一句话只表达一个意思，别把好几件事揉在一句话里说")
        lines.append("2. 每次回复最多2-3句，每句话控制在15字以内，像发微信一样简短")
        lines.append("3. 一句说完就停，让对方有接话的空间，别连珠炮似的说一堆")
        lines.append("4. 语气要自然，像朋友之间发微信那样，别像客服")
        lines.append("5. 接对方的话茬，别自顾自说自己的")
        lines.append("6. 别用「首先」「其次」「总之」「综上所述」这种书面词")
        lines.append("7. 别动不动就总结概括，你不是在做报告")
        lines.append("8. 如果对方话少，你也可以话少，不用硬找话题")

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

    def update_mood_from_content(
        self,
        content: str,
        sentiment: str | None = None,
    ) -> None:
        """根据对话内容更新情绪状态。

        Args:
            content: 用户的对话内容
            sentiment: 外部情感分析结果（可选）
        """
        if sentiment:
            mood_map = {
                "positive": MoodState.HAPPY,
                "negative": MoodState.SAD,
                "angry": MoodState.ANGRY,
                "neutral": MoodState.NEUTRAL,
            }
            self._mood.state = mood_map.get(sentiment, MoodState.NEUTRAL)
            self._mood.intensity = min(1.0, self._mood.intensity + 0.1)
        else:
            # 简单的关键词情绪推断
            positive_words = ["开心", "高兴", "喜欢", "太好了", "棒", "谢谢", "哈哈"]
            negative_words = ["难过", "生气", "讨厌", "烦", "伤心", "郁闷", "烦死了"]

            for word in positive_words:
                if word in content:
                    self._mood.state = MoodState.HAPPY
                    self._mood.intensity = min(1.0, self._mood.intensity + 0.05)
                    break
            for word in negative_words:
                if word in content:
                    self._mood.state = MoodState.SAD
                    self._mood.intensity = min(1.0, self._mood.intensity + 0.05)
                    break

        # 情绪自然衰减
        self._mood.intensity = max(0.1, self._mood.intensity - 0.02)
        self._mood.updated_at = datetime.now()
        self._update_snapshot()

    def apply_to_prompt(
        self,
        context: ConversationContext,
    ) -> str:
        """将人格注入到 LLM prompt 中。

        Args:
            context: 对话上下文

        Returns:
            注入人格后的完整 system prompt
        """
        system_prompt = self.build_system_prompt()

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
