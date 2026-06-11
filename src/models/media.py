"""媒体资源模型 — 图片、表情包的表示。"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class MediaType(str, Enum):
    """媒体类型。"""
    IMAGE = "image"
    MEME = "meme"


class MediaItem(BaseModel):
    """媒体资源项。"""
    id: str = Field(default="", description="资源标识")
    type: MediaType = Field(default=MediaType.IMAGE)
    path: str = Field(default="", description="本地文件路径")
    url: str = Field(default="", description="远程 URL")
    category: str = Field(default="general", description="分类（开心/生气/惊讶等）")
    tags: list[str] = Field(default_factory=list, description="标签")
    description: str = Field(default="", description="内容描述")


class IncomingMedia(BaseModel):
    """收到的媒体内容。"""
    type: MediaType
    url: str = ""
    file: str = ""
    summary: str = ""           # OneBot summary 字段
    raw: dict[str, Any] = Field(default_factory=dict)
