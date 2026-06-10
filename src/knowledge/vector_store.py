"""向量数据库封装 — 基于 ChromaDB 的知识库存储和检索。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None


class VectorStore:
    """向量存储封装。

    提供知识的增删改查，按主题分类，带兴趣权重。
    """

    def __init__(self, persist_dir: str = "data/chroma_db"):
        self.persist_dir = persist_dir
        self._client = None
        self._collection = None

        if chromadb is not None:
            db_path = Path(persist_dir)
            db_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(db_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="knowledge_base",
                metadata={"hnsw:space": "cosine"},
            )

    @property
    def collection(self):
        if self._collection is None:
            raise RuntimeError("ChromaDB 未初始化")
        return self._collection

    def add_knowledge(
        self,
        content: str,
        category: str = "general",
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """添加知识条目。"""
        import uuid
        doc_id = str(uuid.uuid4())
        meta = {
            "category": category,
            "source": source,
            **(metadata or {}),
        }
        self.collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[meta],
        )
        return doc_id

    def search(
        self,
        query: str,
        category: str | None = None,
        n_results: int = 5,
    ) -> list[dict]:
        """搜索知识库。

        Args:
            query: 查询文本
            category: 按类别筛选
            n_results: 返回数量

        Returns:
            匹配的知识条目列表
        """
        where = None
        if category:
            where = {"category": category}

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        items = []
        if results and results["ids"]:
            for i in range(len(results["ids"][0])):
                items.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })

        return items

    def delete_knowledge(self, doc_id: str) -> None:
        """删除知识条目。"""
        self.collection.delete(ids=[doc_id])

    def get_categories(self) -> list[str]:
        """获取所有知识类别。"""
        results = self.collection.get()
        categories = set()
        if results and results["metadatas"]:
            for meta in results["metadatas"]:
                if meta and "category" in meta:
                    categories.add(meta["category"])
        return sorted(categories)

    def count(self) -> int:
        """获取知识条目总数。"""
        return self.collection.count()
