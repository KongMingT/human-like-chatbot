"""人格配置模型 — 性格特征、情绪状态、语言风格。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MoodState(str, Enum):
    """情绪状态枚举。"""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    EXCITED = "excited"
    TIRED = "tired"
    ANXIOUS = "anxious"
    CALM = "calm"


class MoodData(BaseModel):
    """情绪数据。"""

    state: MoodState = Field(default=MoodState.NEUTRAL, description="当前情绪")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="情绪强度")
    volatility: float = Field(default=0.3, ge=0.0, le=1.0, description="情绪波动性")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新")


class PersonalitySnapshot(BaseModel):
    """性格快照 — 某个时间点的完整性格状态。"""

    timestamp: datetime = Field(default_factory=datetime.now, description="快照时间")
    openness: float = Field(default=0.7, ge=0.0, le=1.0)
    humor: float = Field(default=0.6, ge=0.0, le=1.0)
    directness: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.8, ge=0.0, le=1.0)
    curiosity: float = Field(default=0.7, ge=0.0, le=1.0)
    formality: float = Field(default=0.3, ge=0.0, le=1.0)
    optimism: float = Field(default=0.7, ge=0.0, le=1.0)
    mood: MoodData = Field(default_factory=MoodData)

    def to_dict(self) -> dict[str, float]:
        """转换为纯数字字典（不含时间戳和情绪）。"""
        return {
            "openness": self.openness,
            "humor": self.humor,
            "directness": self.directness,
            "empathy": self.empathy,
            "curiosity": self.curiosity,
            "formality": self.formality,
            "optimism": self.optimism,
        }

    def apply_delta(self, delta: dict[str, float]) -> PersonalitySnapshot:
        """应用增量变化，返回新的快照。"""
        data = self.to_dict()
        for key, change in delta.items():
            if key in data:
                data[key] = max(0.0, min(1.0, data[key] + change))
        return PersonalitySnapshot(
            timestamp=datetime.now(),
            mood=self.mood,
            **data,
        )


class PersonalityProfile(BaseModel):
    """完整的性格档案 — 用于持久化和分析。"""

    name: str = Field(default="", description="人格名称")
    description: str = Field(default="", description="人格描述")
    current: PersonalitySnapshot = Field(default_factory=PersonalitySnapshot, description="当前性格状态")
    history: list[PersonalitySnapshot] = Field(default_factory=list, description="性格变化历史")
    frozen: bool = Field(default=False, description="是否冻结（停止演化）")
