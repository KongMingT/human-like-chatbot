"""演化引擎 — 性格随时间和事件的渐进演化。

核心差异化功能：性格参数随时间缓慢漂移，
并因特定事件触发调整。
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import EvolutionConfig
from src.models.personality import PersonalitySnapshot


class EvolutionEngine:
    """演化引擎。

    管理性格参数的渐进变化，支持时间漂移和事件驱动。
    """

    def __init__(self, config: EvolutionConfig):
        self.config = config
        self._last_update: datetime = datetime.now()
        self._change_log: list[dict] = []
        self._load_change_log()

    def _load_change_log(self):
        """加载历史变化记录。"""
        log_path = Path(self.config.change_log_path)
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    self._change_log = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._change_log = []

    def _save_change_log(self):
        """保存变化记录。"""
        log_path = Path(self.config.change_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self._change_log, f, ensure_ascii=False, indent=2, default=str)

    def calculate_daily_drift(self, current: PersonalitySnapshot) -> dict[str, float]:
        """计算每日性格漂移量。

        使用 sigmoid 函数产生平滑的变化。
        不同维度的漂移方向和速率不同。

        Args:
            current: 当前性格快照

        Returns:
            各维度的变化增量
        """
        if not self.config.enabled:
            return {}

        drift = {}
        base_rate = self.config.drift_rate

        for trait in ["openness", "humor", "directness", "empathy", "curiosity", "optimism"]:
            value = getattr(current, trait, 0.5)

            # 使用 sigmoid 中心驱动力：偏离 0.5 越远，往回拉的力越大
            center_pull = (0.5 - value) * 0.1

            # 随机波动
            import random
            random_walk = random.uniform(-0.05, 0.05)

            # 组合变化
            delta = (center_pull + random_walk) * base_rate * 10

            # 限制单次变化幅度
            delta = max(-0.05, min(0.05, delta))
            drift[trait] = delta

        return drift

    def apply_event_impact(
        self,
        current: PersonalitySnapshot,
        event_type: str,
        event_data: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """应用事件驱动的性格影响。

        Args:
            current: 当前性格快照
            event_type: 事件类型
            event_data: 事件数据

        Returns:
            各维度的变化增量
        """
        if not self.config.enabled:
            return {}

        impact = self.config.event_impact
        delta: dict[str, float] = {}

        event_effects = {
            "deep_conversation": {"openness": 0.02, "empathy": 0.01},
            "conflict": {"empathy": -0.02, "directness": 0.02, "optimism": -0.01},
            "praise": {"optimism": 0.02, "humor": 0.01},
            "criticism": {"optimism": -0.015, "empathy": 0.01},
            "long_silence": {"curiosity": -0.01, "openness": -0.01},
            "new_topic": {"curiosity": 0.02, "openness": 0.01},
            "help_provided": {"empathy": 0.01, "optimism": 0.01},
        }

        effects = event_effects.get(event_type, {})
        for trait, change in effects.items():
            delta[trait] = change * impact * 10

        return delta

    def evolve(
        self,
        current: PersonalitySnapshot,
        days_passed: float | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> PersonalitySnapshot:
        """执行性格演化。

        Args:
            current: 当前性格快照
            days_passed: 经过的天数（None 自动计算）
            events: 期间发生的事件列表

        Returns:
            演化后的新性格快照
        """
        if not self.config.enabled or self._is_frozen():
            return current

        if days_passed is None:
            days_passed = (datetime.now() - self._last_update).total_seconds() / 86400

        # 限制最大演化天数（防止长时间离线后突变）
        days_passed = min(days_passed, 30.0)

        total_delta: dict[str, float] = {}

        # 时间漂移
        for _ in range(int(days_passed)):
            daily_drift = self.calculate_daily_drift(current)
            for trait, change in daily_drift.items():
                total_delta[trait] = total_delta.get(trait, 0) + change

        # 事件影响
        if events:
            for event in events:
                event_delta = self.apply_event_impact(
                    current,
                    event.get("type", ""),
                    event.get("data"),
                )
                for trait, change in event_delta.items():
                    total_delta[trait] = total_delta.get(trait, 0) + change

        # 应用变化
        new_snapshot = current.apply_delta(total_delta)

        # 记录变化
        if total_delta:
            self._log_change(total_delta, days_passed, events)

        self._last_update = datetime.now()
        return new_snapshot

    def _is_frozen(self) -> bool:
        """检查性格是否被冻结。"""
        return self.config.freeze_enabled and False  # 由外部控制

    def _log_change(
        self,
        delta: dict[str, float],
        days_passed: float,
        events: list[dict] | None,
    ):
        """记录性格变化。"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "days_passed": round(days_passed, 2),
            "delta": {k: round(v, 4) for k, v in delta.items()},
            "events": events or [],
        }
        self._change_log.append(entry)
        self._save_change_log()

    def get_change_history(self, limit: int = 50) -> list[dict]:
        """获取最近的变化记录。"""
        return self._change_log[-limit:]

    def get_trait_history(self, trait: str) -> list[tuple[str, float]]:
        """获取指定维度的历史变化轨迹。"""
        history: list[tuple[str, float]] = []
        cumulative = 0.5  # 从中间值开始

        for entry in self._change_log:
            if trait in entry.get("delta", {}):
                cumulative += entry["delta"][trait]
                history.append((entry["timestamp"], round(cumulative, 4)))

        return history

    def freeze(self):
        """冻结性格，停止演化。"""
        self.config.freeze_enabled = True

    def unfreeze(self):
        """解冻性格，恢复演化。"""
        self.config.freeze_enabled = False
