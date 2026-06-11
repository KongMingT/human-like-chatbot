"""测试数据模型和配置系统。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.message import Message, MessageType, MessageRole, ConversationContext
from src.models.personality import PersonalitySnapshot, PersonalityProfile, MoodState
from src.models.memory import MemoryItem, MemoryType, MemoryImportance, ShortTermMemory
from src.config import load_config, PersonalityConfig, LLMConfig


class TestMessageModels:
    """测试消息模型。"""

    def test_message_create(self):
        msg = Message(content="你好", sender_name="测试用户")
        assert msg.content == "你好"
        assert msg.sender_name == "测试用户"
        assert msg.type == MessageType.PRIVATE
        assert msg.role == MessageRole.USER

    def test_message_group(self):
        msg = Message(
            content="大家好",
            sender_name="群友",
            type=MessageType.GROUP,
            group_id="g12345",
        )
        assert msg.type == MessageType.GROUP
        assert msg.group_id == "g12345"

    def test_conversation_context(self):
        ctx = ConversationContext(
            messages=[Message(content="hi")],
            platform="qq",
            session_id="s001",
        )
        assert len(ctx.messages) == 1
        assert ctx.platform == "qq"


class TestPersonalityModels:
    """测试人格模型。"""

    def test_snapshot_defaults(self):
        snap = PersonalitySnapshot()
        assert snap.openness == 0.7
        assert snap.humor == 0.6
        assert snap.curiosity == 0.7
        assert snap.mood.state == MoodState.NEUTRAL

    def test_snapshot_to_dict(self):
        snap = PersonalitySnapshot()
        d = snap.to_dict()
        assert "openness" in d
        assert "humor" in d
        assert len(d) == 7

    def test_snapshot_apply_delta(self):
        snap = PersonalitySnapshot(openness=0.5, humor=0.5)
        new_snap = snap.apply_delta({"openness": 0.2, "humor": -0.1})
        assert new_snap.openness == pytest.approx(0.7)
        assert new_snap.humor == pytest.approx(0.4)

    def test_snapshot_clamp_values(self):
        snap = PersonalitySnapshot(openness=0.5)
        new_snap = snap.apply_delta({"openness": 10.0})
        assert new_snap.openness == 1.0  # 不应超过 1.0

        new_snap2 = snap.apply_delta({"openness": -10.0})
        assert new_snap2.openness == 0.0  # 不应低于 0.0

    def test_profile_create(self):
        profile = PersonalityProfile(name="测试人格")
        assert profile.name == "测试人格"
        assert not profile.frozen
        assert len(profile.history) == 0


class TestMemoryModels:
    """测试记忆模型。"""

    def test_memory_item_create(self):
        mem = MemoryItem(content="用户喜欢编程", user_id="u001")
        assert mem.type == MemoryType.FACT
        assert mem.importance == MemoryImportance.MEDIUM
        assert mem.decay_factor == 1.0

    def test_memory_importance_scores(self):
        mem = MemoryItem(
            content="重要信息",
            user_id="u001",
            importance=MemoryImportance.CRITICAL,
            importance_score=0.95,
        )
        assert mem.importance_score == 0.95
        assert mem.importance == MemoryImportance.CRITICAL

    def test_short_term_memory(self):
        stm = ShortTermMemory(session_id="s001", max_window=20)
        stm.messages.append({"role": "user", "content": "你好"})
        assert len(stm.messages) == 1


class TestConfigSystem:
    """测试配置系统。"""

    def test_load_default_config(self):
        cfg_path = Path(__file__).parent.parent / "configs" / "default.toml"
        assert cfg_path.exists(), "默认配置文件不存在"
        cfg = load_config(cfg_path)
        assert cfg.bot.name == "小夜"
        assert cfg.bot.platform == "qq"

    def test_llm_config(self):
        cfg_path = Path(__file__).parent.parent / "configs" / "default.toml"
        cfg = load_config(cfg_path)
        assert cfg.llm.provider == "deepseek"
        assert cfg.llm.temperature == 0.9
        assert cfg.llm.stream is True

    def test_personality_config(self):
        cfg_path = Path(__file__).parent.parent / "configs" / "default.toml"
        cfg = load_config(cfg_path)
        assert cfg.personality.traits.openness == 0.8
        assert cfg.personality.traits.humor == 0.85
        assert cfg.personality.language.emojis_enabled is False

    def test_scheduler_config(self):
        cfg_path = Path(__file__).parent.parent / "configs" / "default.toml"
        cfg = load_config(cfg_path)
        assert cfg.scheduler.typing_delay_min == 0.5
        assert cfg.scheduler.typing_delay_max == 3.0
        assert cfg.scheduler.schedule.active_hours_start == 8

    def test_memory_config(self):
        cfg_path = Path(__file__).parent.parent / "configs" / "default.toml"
        cfg = load_config(cfg_path)
        assert cfg.memory.short_term_window == 20
        assert cfg.memory.long_term_enabled is True

    def test_evolution_config(self):
        cfg_path = Path(__file__).parent.parent / "configs" / "default.toml"
        cfg = load_config(cfg_path)
        assert cfg.evolution.enabled is True
        assert cfg.evolution.drift_rate == 0.001
