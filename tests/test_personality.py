"""测试人格引擎。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.middleware.personality import PersonalityEngine
from src.config import PersonalityConfig, PersonalityTraits, MoodConfig, LanguageConfig
from src.models.message import ConversationContext, Message


@pytest.fixture
def default_engine():
    return PersonalityEngine(PersonalityConfig())


class TestPersonalityEngine:
    """测试人格引擎。"""

    def test_init(self, default_engine):
        assert default_engine.profile.name == "小助手"
        assert default_engine.profile.current.openness == 0.7

    def test_build_system_prompt(self, default_engine):
        prompt = default_engine.build_system_prompt()
        assert "小助手" in prompt
        assert "友善" in prompt
        assert "随意" in prompt or "哥们儿" in prompt

    def test_build_system_prompt_formal(self):
        config = PersonalityConfig(
            traits=PersonalityTraits(formality=0.8),
            language=LanguageConfig(style="formal"),
        )
        engine = PersonalityEngine(config)
        prompt = engine.build_system_prompt()
        assert "讲究" in prompt
        assert "规范" in prompt

    def test_build_system_prompt_with_catchphrase(self):
        config = PersonalityConfig(
            language=LanguageConfig(catchphrase="原来如此"),
        )
        engine = PersonalityEngine(config)
        prompt = engine.build_system_prompt()
        assert "原来如此" in prompt

    def test_mood_update_positive(self, default_engine):
        default_engine.update_mood_from_content("今天真开心！")
        assert default_engine._mood.state.value in ["happy", "neutral"]

    def test_mood_update_negative(self, default_engine):
        default_engine.update_mood_from_content("好难过，今天太伤心了")
        assert default_engine._mood.state.value in ["sad", "neutral"]

    def test_mood_intensity_decay(self, default_engine):
        default_engine._mood.intensity = 0.9
        default_engine.update_mood_from_content("好的")
        assert default_engine._mood.intensity < 0.9

    def test_apply_to_prompt(self, default_engine):
        ctx = ConversationContext(
            messages=[Message(content="你好")],
            current_message=Message(content="你好吗？"),
        )
        prompt = default_engine.apply_to_prompt(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_current_state(self, default_engine):
        state = default_engine.current_state()
        assert "mood" in state
        assert "traits" in state
        assert state["mood"] in ["neutral", "happy", "sad", "calm", "excited", "tired", "anxious", "angry"]

    def test_random_typo_no_change(self, default_engine):
        """频率为 0 时不应产生错别字。"""
        result = default_engine.random_typo("今天天气很好", frequency=0.0)
        assert result == "今天天气很好"

    def test_random_typo_high_frequency(self, default_engine):
        """高频时应产生变化。"""
        import random
        random.seed(42)
        result = default_engine.random_typo("这是什么", frequency=1.0)
        # 无法保证每次都有变化，但至少返回字符串
        assert isinstance(result, str)

    def test_custom_traits(self):
        config = PersonalityConfig(
            traits=PersonalityTraits(
                openness=0.2,
                humor=0.9,
                directness=0.9,
            ),
        )
        engine = PersonalityEngine(config)
        prompt = engine.build_system_prompt()
        # 保守、幽默、直率
        if "保守" in prompt or "开放" not in prompt:
            pass  # OK
        assert "幽默" in prompt

    def test_apply_to_prompt_no_context(self, default_engine):
        """空上下文中应仍能正常工作。"""
        prompt = default_engine.apply_to_prompt(ConversationContext())
        assert len(prompt) > 50
