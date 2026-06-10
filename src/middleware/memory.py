"""记忆系统 — 短期记忆 + 长期记忆（向量数据库）。

短期记忆维护对话窗口上下文。
长期记忆使用 ChromaDB 持久化重要信息。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import MemoryConfig
from src.models.memory import (
    MemoryImportance,
    MemoryItem,
    MemoryQuery,
    MemoryType,
    ShortTermMemory,
)

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None  # type: ignore


class MemorySystem:
    """记忆系统。

    管理短期对话记忆和长期持久化记忆。
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.short_term: dict[str, ShortTermMemory] = {}

        # 初始化 ChromaDB
        self._chroma_client = None
        self._collection = None
        if chromadb is not None and config.long_term_enabled:
            db_path = Path(config.vector_db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(
                path=str(db_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name="long_term_memory",
                metadata={"hnsw:space": "cosine"},
            )

    @property
    def _mem_collection(self):
        if self._collection is None:
            raise RuntimeError("ChromaDB 未初始化（long_term_enabled=False 或 chromadb 未安装）")
        return self._collection

    # ==================== 短期记忆 ====================

    def get_short_term(self, session_id: str) -> ShortTermMemory:
        """获取或创建短期记忆。"""
        if session_id not in self.short_term:
            self.short_term[session_id] = ShortTermMemory(
                session_id=session_id,
                max_window=self.config.short_term_window,
            )
        return self.short_term[session_id]

    def add_to_short_term(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """添加消息到短期记忆。"""
        stm = self.get_short_term(session_id)
        stm.messages.append({"role": role, "content": content})

        # 超出窗口时移除最早的消息
        if len(stm.messages) > stm.max_window:
            stm.messages = stm.messages[-stm.max_window:]

        # 定期生成对话摘要
        if len(stm.messages) % self.config.summary_interval == 0:
            self._summarize_short_term(session_id, stm)

    def _summarize_short_term(
        self,
        session_id: str,
        stm: ShortTermMemory,
    ) -> None:
        """生成短期记忆摘要。"""
        # 简化的摘要：记录消息数量和最后几条消息的主题
        recent = stm.messages[-5:] if len(stm.messages) >= 5 else stm.messages
        topics = set()
        for msg in recent:
            if len(msg["content"]) > 5:
                topics.add(msg["content"][:20] + "...")
        stm.summary = f"共 {len(stm.messages)} 条消息。最近话题: {'; '.join(topics)}"

    # ==================== 长期记忆 ====================

    async def add_long_term(
        self,
        content: str,
        user_id: str,
        memory_type: MemoryType = MemoryType.FACT,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        tags: list[str] | None = None,
    ) -> str:
        """添加长期记忆。"""
        mem_id = str(uuid.uuid4())

        importance_scores = {
            MemoryImportance.CRITICAL: 0.95,
            MemoryImportance.HIGH: 0.75,
            MemoryImportance.MEDIUM: 0.50,
            MemoryImportance.LOW: 0.25,
        }

        item = MemoryItem(
            id=mem_id,
            type=memory_type,
            content=content,
            importance=importance,
            importance_score=importance_scores[importance],
            user_id=user_id,
            tags=tags or [],
        )

        if self._collection is not None:
            # 提取关键词作为简单"嵌入"占位（实际应使用 embedding 模型）
            self._collection.add(
                ids=[mem_id],
                documents=[content],
                metadatas=[{
                    "type": memory_type.value,
                    "user_id": user_id,
                    "importance": item.importance_score,
                    "tags": json.dumps(tags or []),
                    "created_at": item.created_at.isoformat(),
                }],
            )

        return mem_id

    async def search_memory(
        self,
        query: MemoryQuery,
    ) -> list[MemoryItem]:
        """搜索长期记忆。

        Args:
            query: 查询参数

        Returns:
            匹配的记忆列表
        """
        if self._collection is None:
            return []

        # 构建查询条件
        where: dict[str, Any] = {}
        if query.user_id:
            where["user_id"] = query.user_id
        if query.memory_type:
            where["type"] = query.memory_type.value

        where_document: dict[str, Any] = {}
        if query.query:
            where_document["$contains"] = query.query

        results = self._collection.query(
            query_texts=[query.query] if query.query else None,
            n_results=query.limit,
            where=where or None,
            where_document=where_document or None,
        )

        items = []
        if results and results["ids"]:
            for i, mem_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                items.append(MemoryItem(
                    id=mem_id,
                    content=results["documents"][0][i],
                    type=MemoryType(metadata.get("type", "fact")),
                    user_id=metadata.get("user_id", ""),
                    importance_score=metadata.get("importance", 0.5),
                ))

        return items

    async def get_relevant_memories(
        self,
        context: str,
        user_id: str,
        limit: int = 5,
    ) -> list[MemoryItem]:
        """获取与当前上下文相关的记忆。"""
        query = MemoryQuery(
            query=context,
            user_id=user_id,
            limit=limit,
        )
        return await self.search_memory(query)

    async def extract_and_store_facts(
        self,
        content: str,
        user_id: str,
    ) -> list[str]:
        """从对话中提取重要事实并存储。

        Args:
            content: 对话内容
            user_id: 用户 ID

        Returns:
            存储的记忆 ID 列表
        """
        # 简单的关键词提取（后续可用 LLM 提取）
        facts = []
        patterns = [
            ("喜欢", MemoryType.FACT, MemoryImportance.MEDIUM),
            ("讨厌", MemoryType.FACT, MemoryImportance.MEDIUM),
            ("名字", MemoryType.FACT, MemoryImportance.HIGH),
            ("住在", MemoryType.FACT, MemoryImportance.MEDIUM),
            ("工作", MemoryType.FACT, MemoryImportance.MEDIUM),
            ("生日", MemoryType.FACT, MemoryImportance.HIGH),
        ]

        ids = []
        for keyword, mem_type, importance in patterns:
            if keyword in content:
                # 提取包含关键词的句子
                import re
                sentences = re.split(r"[。！？\n.!?]", content)
                for sentence in sentences:
                    if keyword in sentence and len(sentence) > 5:
                        mem_id = await self.add_long_term(
                            content=sentence.strip(),
                            user_id=user_id,
                            memory_type=mem_type,
                            importance=importance,
                            tags=[keyword],
                        )
                        ids.append(mem_id)

        return ids

    # ==================== 持久化 ====================

    def save_state(self, path: str | Path | None = None) -> None:
        """保存记忆状态到磁盘。"""
        # 短期记忆保存为 JSON
        save_path = Path(path or "data/profiles/memory_state.json")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "short_term": {
                sid: stm.model_dump()
                for sid, stm in self.short_term.items()
            },
        }
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)

    def load_state(self, path: str | Path | None = None) -> None:
        """从磁盘加载记忆状态。"""
        load_path = Path(path or "data/profiles/memory_state.json")
        if not load_path.exists():
            return

        with open(load_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        for sid, data in state.get("short_term", {}).items():
            stm = ShortTermMemory(**data)
            self.short_term[sid] = stm
