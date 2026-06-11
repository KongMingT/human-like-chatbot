"""媒体处理器 — 管理图片/表情包的收发。"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from src.models.media import IncomingMedia, MediaItem, MediaType

logger = logging.getLogger("human-like-chatbot.media")


class MediaHandler:
    """媒体处理器。

    管理表情包库，处理收到的图片，决定何时发送表情包。
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._memes: dict[str, list[MediaItem]] = {}  # category → items
        self._load_meme_library()

    # ── 表情包库管理 ──────────────────────────────

    def _load_meme_library(self):
        """从 data/memes 加载表情包库。"""
        meme_dir = Path("data/memes")
        if not meme_dir.exists():
            logger.info("表情包目录不存在: data/memes，跳过加载")
            return

        # 加载分类配置文件
        config_path = meme_dir / "memes.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                category = item.get("category", "general")
                if category not in self._memes:
                    self._memes[category] = []
                self._memes[category].append(MediaItem(**item))

        # 按目录扫描图片文件
        for cat_dir in meme_dir.iterdir():
            if cat_dir.is_dir() and cat_dir.name != "__pycache__":
                category = cat_dir.name
                if category not in self._memes:
                    self._memes[category] = []
                for img_file in cat_dir.glob("*.*"):
                    if img_file.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                        self._memes[category].append(MediaItem(
                            id=img_file.stem,
                            path=str(img_file),
                            category=category,
                        ))

        total = sum(len(v) for v in self._memes.values())
        logger.info(f"加载 {total} 个表情包 ({len(self._memes)} 类)")

    def pick_meme(self, mood: str | None = None, text: str = "") -> MediaItem | None:
        """根据当前情绪和上下文挑选一个表情包。

        Args:
            mood: 当前情绪状态
            text: 对话文本（用于关键词匹配）

        Returns:
            选中的表情包，或 None 如果库为空
        """
        if not self._memes:
            return None

        # 按情绪匹配
        candidates: list[MediaItem] = []
        mood_map = {
            "happy": ["开心", "高兴", "happy", "joy", "lol"],
            "sad": ["难过", "伤心", "sad", "cry"],
            "angry": ["生气", "angry", "mad"],
            "excited": ["兴奋", "excited", "wow"],
            "tired": ["累", "tired", "sleepy"],
            "neutral": ["general", "neutral"],
        }

        # 优先匹配情绪
        if mood:
            categories = mood_map.get(mood, ["general"])
            for cat in categories:
                if cat in self._memes:
                    candidates.extend(self._memes[cat])

        # 回退到 general
        if not candidates and "general" in self._memes:
            candidates = self._memes["general"]

        # 随机选一个
        if candidates:
            return random.choice(candidates)
        return None

    # ── 图片接收 ──────────────────────────────────

    def parse_image_segments(self, segments: list[dict]) -> list[IncomingMedia]:
        """从 OneBot 消息段中提取图片信息。"""
        images = []
        for seg in segments:
            if seg.get("type") == "image":
                data = seg.get("data", {})
                images.append(IncomingMedia(
                    type=MediaType.IMAGE,
                    url=data.get("url", ""),
                    file=data.get("file", ""),
                    summary=data.get("summary", "[图片]"),
                    raw=data,
                ))
        return images

    def summarize_images(self, images: list[IncomingMedia]) -> str:
        """将收到的图片转为文字描述，供 LLM 理解。"""
        if not images:
            return ""
        descs = []
        for i, img in enumerate(images):
            if img.summary and img.summary != "[图片]":
                descs.append(f"[图片{i+1}: {img.summary}]")
            else:
                descs.append(f"[图片{i+1}]")
        return " ".join(descs)

    # ── 表情包发送决策 ────────────────────────────

    def should_send_meme(self, mood_intensity: float, reply_length: int) -> bool:
        """判断当前是否适合发送表情包。

        Args:
            mood_intensity: 当前情绪强度 (0~1)
            reply_length: 回复文字长度

        Returns:
            是否应该附带表情包
        """
        if not self._memes:
            return False
        # 情绪强或回复短时更容易发表情包
        prob = mood_intensity * 0.4 + max(0, 1 - reply_length / 60) * 0.2
        return random.random() < prob

    def has_memes(self) -> bool:
        """是否有可用的表情包。"""
        return bool(self._memes)
