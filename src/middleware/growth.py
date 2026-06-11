"""成长引擎 — 从对话中持续学习，实现语气、性格、知识三个维度的成长。

核心能力：
1. 语气适应 — 学习对方的常用词、句式，对话越多越像「了解你的人」
2. 性格漂移 — 基于长期对话模式微调性格参数
3. 知识积累 — 从对话中提取事实并存入长期记忆
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import EvolutionConfig
from src.models.personality import PersonalitySnapshot

logger = logging.getLogger("human-like-chatbot.growth")


class GrowthEngine:
    """成长引擎。

    管理三个维度的成长，数据持久化到本地文件。
    """

    def __init__(self, config: EvolutionConfig):
        self.config = config

        # 成长数据根目录
        self._data_dir = Path("data/profiles")
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # ── 语气词库 ──
        self._tone_lexicon: dict[str, int] = self._load_json("tone_lexicon.json")
        # { "哈哈": 5, "绝了": 3, "确实": 2, ... }

        # ── 句式模式 ──
        self._sentence_patterns: dict[str, int] = self._load_json("sentence_patterns.json")
        # { "X 也太 Y 了吧": 3, "不会吧不会吧": 2, ... }

        # ── 性格漂移记录 ──
        self._drift_log: list[dict] = self._load_json("drift_log.json", [])

        # ── 对话统计 ──
        self._stats: dict[str, Any] = self._load_json("growth_stats.json", {
            "total_turns": 0,
            "unique_users": set(),
            "last_update": datetime.now().isoformat(),
            "tone_adaptation_rate": 0.3,    # 语气适应速度 (0~1)
        })

    # ── 持久化 ──────────────────────────────────────

    def _load_json(self, name: str, default: Any = None) -> Any:
        path = self._data_dir / name
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return default if default is not None else {}

    def _save_json(self, name: str, data: Any):
        path = self._data_dir / name
        # set 不能 JSON 序列化
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if isinstance(v, set):
                    clean[k] = list(v)
                else:
                    clean[k] = v
            data = clean
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def save_state(self):
        """持久化所有成长数据。"""
        self._save_json("tone_lexicon.json", self._tone_lexicon)
        self._save_json("sentence_patterns.json", self._sentence_patterns)
        self._save_json("drift_log.json", self._drift_log)
        self._save_json("growth_stats.json", self._stats)
        logger.info("成长数据已保存")

    # ── 1. 语气适应 ────────────────────────────────

    def learn_from_message(self, content: str, sender: str):
        """从一条消息中学习语气和用词。

        Args:
            content: 消息内容
            sender: 发送者标识
        """
        # 更新统计
        self._stats["total_turns"] += 1
        if isinstance(self._stats.get("unique_users"), list):
            self._stats["unique_users"] = set(self._stats["unique_users"])
        self._stats.setdefault("unique_users", set()).add(sender)
        self._stats["last_update"] = datetime.now().isoformat()

        # 提取词汇特征（2-4 字短语）
        self._extract_phrases(content)

        # 提取句式模式
        self._extract_patterns(content)

    def _extract_phrases(self, content: str):
        """提取有特征的短语。"""
        # 排除纯标点/数字/英文的消息
        if not re.search(r"[\u4e00-\u9fff]", content):
            return

        chars = list(content)

        # 2-gram
        for i in range(len(chars) - 1):
            bigram = "".join(chars[i:i+2]).strip()
            if len(bigram) == 2 and re.search(r"[\u4e00-\u9fff]", bigram):
                self._tone_lexicon[bigram] = self._tone_lexicon.get(bigram, 0) + 1

        # 3-gram (仅抽取有意义的三字组合)
        for i in range(len(chars) - 2):
            trigram = "".join(chars[i:i+3]).strip()
            if len(trigram) == 3 and re.search(r"[\u4e00-\u9fff]", trigram):
                # 过滤常见停用 trigram
                if trigram not in ("这是一个", "是不是", "什么的", "的时候", "还可以"):
                    self._tone_lexicon[trigram] = self._tone_lexicon.get(trigram, 0) + 1

        # 限制词库大小，避免膨胀
        if len(self._tone_lexicon) > 2000:
            # 只保留频率最高的 1500 个
            self._tone_lexicon = dict(
                Counter(self._tone_lexicon).most_common(1500)
            )

    def _extract_patterns(self, content: str):
        """提取句式模式，如「也太 X 了吧」「X 死我了」。"""
        patterns = [
            (r"太(.+)了", "太X了"),
            (r"也太(.+)了吧", "也太X了吧"),
            (r"好(.+)啊", "好X啊"),
            (r"真(.+)啊", "真X啊"),
            (r"什么(.+)玩意", "什么X玩意"),
            (r"不会(.+)吧", "不会X吧"),
            (r"有(.+)吗", "有X吗"),
            (r"是不是(.+)", "是不是X"),
            (r"怎么(.+)了", "怎么X了"),
            (r"(.+)死我了", "X死我了"),
        ]
        for regex, template in patterns:
            if re.search(regex, content):
                self._sentence_patterns[template] = self._sentence_patterns.get(template, 0) + 1

    def get_adapted_tone_prompt(self) -> str:
        """生成语气适应后的 prompt 片段。"""
        if not self._tone_lexicon:
            return ""

        # 取最高频的 8 个特色短语
        top_phrases = Counter(self._tone_lexicon).most_common(8)
        phrases = [p for p, _ in top_phrases if len(p) >= 2]

        if not phrases:
            return ""

        return f"你最近跟对方聊天时学会了用这些词：{'、'.join(phrases)}。在合适的场合可以自然地用上。"

    # ── 2. 性格漂移 ────────────────────────────────

    def calculate_drift(
        self,
        current: PersonalitySnapshot,
        recent_interactions: list[dict],
    ) -> dict[str, float]:
        """基于近期对话模式计算性格漂移。

        Args:
            current: 当前性格快照
            recent_interactions: 近期对话列表

        Returns:
            各维度的漂移增量
        """
        if not self.config.enabled or not recent_interactions:
            return {}

        drift: dict[str, float] = {}

        # 分析近期对话的情感倾向
        positive = sum(1 for m in recent_interactions
                       if any(w in m.get("content", "")
                              for w in ["开心", "哈哈", "喜欢", "棒", "谢谢", "不错"]))
        negative = sum(1 for m in recent_interactions
                       if any(w in m.get("content", "")
                              for w in ["难过", "生气", "讨厌", "烦", "伤心", "无语"]))
        total = len(recent_interactions)

        # 乐观程度受对话氛围影响
        if total > 5:
            pos_ratio = positive / max(total, 1)
            neg_ratio = negative / max(total, 1)
            optimism_drift = (pos_ratio - neg_ratio) * self.config.event_impact
            drift["optimism"] = optimism_drift

        # 好奇心受提问频率影响
        question_count = sum(
            1 for m in recent_interactions
            if "?" in m.get("content", "") or "?" in m.get("content", "")
        )
        q_ratio = question_count / max(total, 1)
        if q_ratio > 0.3:
            drift["curiosity"] = q_ratio * self.config.event_impact * 0.5

        # 记录漂移
        if drift:
            self._drift_log.append({
                "timestamp": datetime.now().isoformat(),
                "drift": drift,
                "context": {
                    "total_interactions": total,
                    "positive_ratio": round(positive / max(total, 1), 2),
                    "question_ratio": round(q_ratio, 2),
                },
            })
            # 限制日志长度
            if len(self._drift_log) > 200:
                self._drift_log = self._drift_log[-200:]

        return drift

    # ── 3. 知识提取 ────────────────────────────────

    def extract_facts(self, content: str) -> list[dict]:
        """从内容中提取事实性知识。

        Args:
            content: 对话内容

        Returns:
            事实列表 [{"subject": "...", "fact": "...", "confidence": 0.8}, ...]
        """
        facts = []

        # 规则：X 是/叫/在/有/喜欢 Y
        patterns = [
            (r"(我|他|她|我们)(?:叫|是|在|有|喜欢|爱|讨厌|住在|想去)(.+?)(?:[。！？\n]|$)", "属性"),
            (r"(.+?)(?:是|叫)(.+?)(?:[。，]|$)", "定义"),
        ]

        for regex, fact_type in patterns:
            for m in re.finditer(regex, content):
                subj = m.group(1).strip()
                obj = m.group(2).strip()

                # 过滤低质量提取
                if len(obj) < 2 or len(obj) > 50:
                    continue
                if subj in ("我", "他", "她"):
                    continue  # 代词的属性暂不提取，后面关联

                facts.append({
                    "subject": subj,
                    "fact": obj,
                    "type": fact_type,
                    "confidence": 0.5,
                    "source": content[:80],
                })

        return facts

    # ── 报告 ────────────────────────────────────────

    def summary(self) -> dict:
        """返回成长摘要。"""
        top_words = Counter(self._tone_lexicon).most_common(10)
        top_patterns = Counter(self._sentence_patterns).most_common(5)
        return {
            "total_turns": self._stats.get("total_turns", 0),
            "unique_users": len(self._stats.get("unique_users", [])),
            "vocabulary_size": len(self._tone_lexicon),
            "patterns_learned": len(self._sentence_patterns),
            "top_phrases": [w for w, _ in top_words],
            "top_patterns": [p for p, _ in top_patterns],
            "drift_events": len(self._drift_log),
        }
