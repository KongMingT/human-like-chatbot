"""消息数据模型 — 平台无关的抽象消息结构。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型。"""

    PRIVATE = "private"
    GROUP = "group"
    SYSTEM = "system"


class MessageRole(str, Enum):
    """消息角色。"""

    USER = "user"
    BOT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """平台无关的抽象消息模型。"""

    id: str = Field(default="", description="消息唯一 ID")
    platform: str = Field(default="", description="来源平台 (qq/discord/wechat)")
    type: MessageType = Field(default=MessageType.PRIVATE, description="消息类型")
    role: MessageRole = Field(default=MessageRole.USER, description="发送者角色")
    sender_id: str = Field(default="", description="发送者 ID")
    sender_name: str = Field(default="", description="发送者昵称")
    group_id: str | None = Field(default=None, description="群组 ID（群聊时）")
    content: str = Field(default="", description="消息文本内容")
    raw: dict[str, Any] = Field(default_factory=dict, description="原始平台消息数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="消息时间")
    is_mention: bool = Field(default=False, description="是否提到了机器人")
    # 媒体相关
    has_media: bool = Field(default=False, description="是否包含媒体内容")
    images: list[dict] = Field(default_factory=list, description="消息中的图片 [{url, file, summary}]")
    # 发送时附带的媒体
    media_path: str | None = Field(default=None, description="发送时附带的媒体文件路径")
    media_url: str | None = Field(default=None, description="发送时附带的媒体 URL")


class ConversationContext(BaseModel):
    """对话上下文 — 传递给中间件和 LLM 的完整上下文。"""

    messages: list[Message] = Field(default_factory=list, description="当前对话消息列表")
    current_message: Message | None = Field(default=None, description="当前正在处理的消息")
    platform: str = Field(default="", description="平台标识")
    session_id: str = Field(default="", description="会话 ID")


class PlatformEvent(BaseModel):
    """平台事件抽象模型。"""

    type: str = Field(default="", description="事件类型")
    platform: str = Field(default="", description="来源平台")
    data: dict[str, Any] = Field(default_factory=dict, description="事件数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="事件时间")
