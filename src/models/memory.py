"""记忆数据模型 — 短期记忆、长期记忆、向量存储。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """记忆类型。"""

    FACT = "fact"           # 事实性信息（用户名、偏好等）
    EVENT = "event"         # 事件（发生过的事）
    SUMMARY = "summary"     # 对话摘要
    EMOTION = "emotion"     # 情感记忆
    PATTERN = "pattern"     # 行为模式


class MemoryImportance(str, Enum):
    """记忆重要性等级。"""

    CRITICAL = "critical"   # 非常重要，不会遗忘
    HIGH = "high"           # 重要
    MEDIUM = "medium"       # 一般
    LOW = "low"             # 不重要，可能被遗忘


class MemoryItem(BaseModel):
    """单条记忆。"""

    id: str = Field(default="", description="记忆唯一 ID")
    type: MemoryType = Field(default=MemoryType.FACT, description="记忆类型")
    content: str = Field(default="", description="记忆内容")
    importance: MemoryImportance = Field(default=MemoryImportance.MEDIUM, description="重要性")
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性数值 (0-1)")
    user_id: str = Field(default="", description="关联用户 ID")
    tags: list[str] = Field(default_factory=list, description="标签")
    embedding: list[float] | None = Field(default=None, description="向量嵌入")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    accessed_at: datetime = Field(default_factory=datetime.now, description="最后访问时间")
    access_count: int = Field(default=0, description="访问次数")
    decay_factor: float = Field(default=1.0, ge=0.0, le=1.0, description="衰减因子（1=未衰减）")


class ShortTermMemory(BaseModel):
    """短期记忆 — 当前对话窗口。"""

    session_id: str = Field(default="", description="会话 ID")
    messages: list[dict] = Field(default_factory=list, description="消息历史")
    max_window: int = Field(default=20, description="最大消息数")
    summary: str = Field(default="", description="当前对话摘要")


class MemoryQuery(BaseModel):
    """记忆查询参数。"""

    query: str = Field(default="", description="查询文本")
    user_id: str | None = Field(default=None, description="按用户筛选")
    memory_type: MemoryType | None = Field(default=None, description="按类型筛选")
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0, description="最低重要性")
    limit: int = Field(default=10, description="返回数量上限")
    include_decayed: bool = Field(default=False, description="是否包含已衰减的记忆")
