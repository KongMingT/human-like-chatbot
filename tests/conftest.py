"""全局测试配置和 fixtures。"""

import pytest


@pytest.fixture
def sample_config_dict() -> dict:
    """提供一个示例配置字典供测试使用。"""
    return {
        "personality": {
            "name": "测试助手",
            "traits": {
                "openness": 0.7,
                "humor": 0.5,
                "directness": 0.6,
                "empathy": 0.8,
                "curiosity": 0.7,
            },
            "mood": {
                "initial": "neutral",
                "volatility": 0.3,
            },
        },
        "scheduler": {
            "typing_delay_min": 0.5,
            "typing_delay_max": 3.0,
            "active_hours_start": 8,
            "active_hours_end": 23,
        },
        "memory": {
            "short_term_window": 20,
            "long_term_enabled": True,
        },
    }
