"""测试记忆系统。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.middleware.memory import MemorySystem
from src.config import MemoryConfig
from src.models.memory import MemoryQuery, MemoryType, MemoryImportance


@pytest.fixture
def memory():
    config = MemoryConfig(
        long_term_enabled=False,  # 跳过 ChromaDB
    )
    return MemorySystem(config)


class TestMemorySystem:
    """测试记忆系统。"""

    def test_short_term_create(self, memory):
        stm = memory.get_short_term("session_1")
        assert stm.session_id == "session_1"
        assert len(stm.messages) == 0

    def test_short_term_add(self, memory):
        memory.add_to_short_term("session_1", "user", "你好")
        stm = memory.get_short_term("session_1")
        assert len(stm.messages) == 1
        assert stm.messages[0]["content"] == "你好"

    def test_short_term_window(self, memory):
        """超出窗口应自动截断。"""
        memory.config.short_term_window = 3
        for i in range(10):
            memory.add_to_short_term("session_2", "user", f"消息{i}")
        stm = memory.get_short_term("session_2")
        assert len(stm.messages) == 3
        assert stm.messages[-1]["content"] == "消息9"

    def test_short_term_multiple_sessions(self, memory):
        memory.add_to_short_term("s1", "user", "会话1")
        memory.add_to_short_term("s2", "user", "会话2")

        assert len(memory.get_short_term("s1").messages) == 1
        assert len(memory.get_short_term("s2").messages) == 1

    @pytest.mark.asyncio
    async def test_add_long_term_without_chroma(self, memory):
        """ChromaDB 禁用时应能正常添加。"""
        mem_id = await memory.add_long_term(
            content="测试记忆",
            user_id="u001",
        )
        assert mem_id is not None
        assert len(mem_id) > 0

    @pytest.mark.asyncio
    async def test_search_memory_without_chroma(self, memory):
        """ChromaDB 禁用时搜索应返回空列表。"""
        results = await memory.search_memory(MemoryQuery(query="测试"))
        assert results == []

    @pytest.mark.asyncio
    async def test_extract_and_store_facts(self, memory):
        ids = await memory.extract_and_store_facts(
            "我喜欢编程和音乐", "u001"
        )
        assert isinstance(ids, list)

    def test_save_and_load_state(self, memory, tmp_path):
        memory.add_to_short_term("s1", "user", "测试消息")
        save_path = tmp_path / "memory_state.json"
        memory.save_state(save_path)

        # 新建一个 memory 实例并加载
        memory2 = MemorySystem(MemoryConfig(long_term_enabled=False))
        memory2.load_state(save_path)
        stm = memory2.get_short_term("s1")
        assert len(stm.messages) == 1
        assert stm.messages[0]["content"] == "测试消息"

    def test_load_state_nonexistent(self, memory):
        """加载不存在的文件不应报错。"""
        memory.load_state(Path("nonexistent.json"))
        # 不应抛出异常

    def test_summary_generation(self, memory):
        """消息达到摘要间隔时应生成摘要。"""
        memory.config.summary_interval = 5
        for i in range(5):
            memory.add_to_short_term("s1", "user", f"这是一条测试消息{i}")

        stm = memory.get_short_term("s1")
        # 摘要应该非空
        assert len(stm.summary) > 0
