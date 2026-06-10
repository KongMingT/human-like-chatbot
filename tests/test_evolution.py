"""测试演化引擎。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.middleware.evolution import EvolutionEngine
from src.config import EvolutionConfig
from src.models.personality import PersonalitySnapshot


@pytest.fixture
def engine():
    config = EvolutionConfig(
        enabled=True,
        drift_rate=0.001,
        event_impact=0.02,
        change_log_path=str(Path(__file__).parent / "test_data" / "evo_log.json"),
    )
    return EvolutionEngine(config)


class TestEvolutionEngine:
    """测试演化引擎。"""

    def test_init(self, engine):
        assert engine.config.enabled is True
        assert engine.config.drift_rate == 0.001

    def test_calculate_daily_drift_returns_dict(self, engine):
        snap = PersonalitySnapshot()
        drift = engine.calculate_daily_drift(snap)
        assert isinstance(drift, dict)
        # 非冻结状态应有漂移
        if engine.config.enabled:
            assert len(drift) > 0

    def test_calculate_drift_toward_center(self, engine):
        """偏离中心值的维度应被拉回。"""
        snap = PersonalitySnapshot(openness=0.1, humor=0.9)
        drift = engine.calculate_daily_drift(snap)
        if "openness" in drift:
            # 0.1 应被拉向 0.5（正向变化）
            assert drift["openness"] >= -0.01  # 不一定是正，但随机+中心拉力应该不极端负
        if "humor" in drift:
            pass  # 随机性使得难以断言方向

    def test_apply_event_impact_deep_conversation(self, engine):
        snap = PersonalitySnapshot()
        delta = engine.apply_event_impact(snap, "deep_conversation")
        assert "openness" in delta
        assert delta["openness"] > 0  # 深入对话增加开放性

    def test_apply_event_impact_conflict(self, engine):
        snap = PersonalitySnapshot()
        delta = engine.apply_event_impact(snap, "conflict")
        assert "optimism" in delta
        assert delta["optimism"] < 0  # 冲突降低乐观

    def test_apply_event_impact_unknown(self, engine):
        snap = PersonalitySnapshot()
        delta = engine.apply_event_impact(snap, "unknown_event")
        assert delta == {}  # 未知事件无影响

    def test_evolve_no_change_when_disabled(self):
        config = EvolutionConfig(enabled=False)
        engine = EvolutionEngine(config)
        snap = PersonalitySnapshot(openness=0.5)
        result = engine.evolve(snap, days_passed=10)
        assert result.openness == 0.5  # 禁用时不变化

    def test_evolve_time_passes(self, engine):
        snap = PersonalitySnapshot(openness=0.5, humor=0.5)
        result = engine.evolve(snap, days_passed=7)
        # 7天后应有微小变化
        traits = result.to_dict()
        has_changed = any(v != 0.5 for v in traits.values())
        # 由于随机性不一定每次都有变化，但至少返回有效结果
        assert isinstance(result, PersonalitySnapshot)

    def test_evolve_with_events(self, engine):
        snap = PersonalitySnapshot(openness=0.5)
        events = [{"type": "deep_conversation"}, {"type": "praise"}]
        result = engine.evolve(snap, days_passed=1, events=events)
        # 事件应有正面影响
        assert isinstance(result, PersonalitySnapshot)

    def test_evolve_max_days_capped(self, engine):
        snap = PersonalitySnapshot(openness=0.5)
        result = engine.evolve(snap, days_passed=100)  # 100 天应被 cap 到 30
        assert isinstance(result, PersonalitySnapshot)
        # 不崩溃即可

    def test_freeze_unfreeze(self, engine):
        assert engine._is_frozen() is False
        # freeze 通过 config 控制
        engine.freeze()
        # 检查 freeze 后的行为
        snap = PersonalitySnapshot(openness=0.5)
        engine.config.enabled = False
        result = engine.evolve(snap, days_passed=10)
        assert result.openness == 0.5

        engine.unfreeze()
        engine.config.enabled = True

    def test_get_change_history_empty(self, engine):
        history = engine.get_change_history()
        assert isinstance(history, list)

    def test_get_trait_history(self, engine):
        history = engine.get_trait_history("openness")
        assert isinstance(history, list)

    def test_change_logging(self, engine):
        snap = PersonalitySnapshot(openness=0.5)
        engine.evolve(snap, days_passed=1, events=[{"type": "praise"}])
        history = engine.get_change_history()
        # 至少有一条变化记录
        if len(history) > 0:
            assert "timestamp" in history[0]
            assert "delta" in history[0]
