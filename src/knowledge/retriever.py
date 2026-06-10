"""检索增强生成（RAG）— 根据对话内容检索相关知识。"""

from __future__ import annotations

from src.knowledge.vector_store import VectorStore


class KnowledgeRetriever:
    """知识检索器。

    根据对话上下文检索相关知识，注入到 LLM prompt 中。
    """

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store

    def retrieve_context(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 3,
    ) -> str:
        """检索相关知识并格式化为上下文。

        Args:
            query: 查询文本（通常是用户消息或对话摘要）
            category: 限定知识类别
            top_k: 返回数量

        Returns:
            格式化后的知识上下文文本
        """
        results = self.store.search(query, category=category, n_results=top_k)

        if not results:
            return ""

        context_parts = ["【相关知识】"]
        for i, item in enumerate(results, 1):
            content = item["content"]
            source = item["metadata"].get("source", "")
            source_tag = f" (来源: {source})" if source else ""
            context_parts.append(f"{i}. {content}{source_tag}")

        return "\n".join(context_parts)

    def build_knowledge_prompt(
        self,
        query: str,
        interests: dict[str, float] | None = None,
    ) -> str:
        """构建知识增强的 prompt 片段。

        如果有兴趣偏好，优先检索偏好类别的知识。

        Args:
            query: 查询文本
            interests: 兴趣偏好字典

        Returns:
            知识 prompt 片段
        """
        if interests:
            # 按兴趣权重排序，优先检索高兴趣类别
            sorted_interests = sorted(
                interests.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for category, weight in sorted_interests:
                if weight >= 0.7:
                    context = self.retrieve_context(query, category=category, top_k=2)
                    if context:
                        return context

        return self.retrieve_context(query)
