"""全局配置加载系统。

支持从 TOML 文件加载配置，并通过环境变量覆盖（环境变量优先级更高）。
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

import tomllib

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    """大模型接口配置。"""

    provider: str = "deepseek"
    model: str = "deepseek-chat"
    temperature: float = 0.8
    max_tokens: int = 2048
    stream: bool = True
    retry_max: int = 3
    retry_delay: float = 2.0


class PersonalityTraits(BaseModel):
    """性格维度配置 (0.0 ~ 1.0)。"""

    openness: float = 0.7
    humor: float = 0.6
    directness: float = 0.5
    empathy: float = 0.8
    curiosity: float = 0.7
    formality: float = 0.3
    optimism: float = 0.7


class MoodConfig(BaseModel):
    """情绪模型配置。"""

    initial: str = "neutral"
    volatility: float = 0.3


class InterestConfig(BaseModel):
    """话题偏好配置。"""

    technology: float = 0.8
    entertainment: float = 0.6
    daily_life: float = 0.7
    science: float = 0.5
    philosophy: float = 0.4


class LanguageConfig(BaseModel):
    """语言风格配置。"""

    style: str = "casual"
    catchphrase: str = ""
    dialect: str = "standard"
    emojis_enabled: bool = True
    typo_frequency: float = 0.05


class PersonalityConfig(BaseModel):
    """人格配置。"""

    name: str = "小助手"
    description: str = "一个友善、幽默的聊天助手"
    traits: PersonalityTraits = PersonalityTraits()
    mood: MoodConfig = MoodConfig()
    interests: InterestConfig = InterestConfig()
    language: LanguageConfig = LanguageConfig()


class SleepState(str, Enum):
    """睡眠状态枚举。"""
    AWAKE = "awake"
    WINDING_DOWN = "winding_down"  # 准备入睡
    ASLEEP_LIGHT = "asleep_light"  # 浅睡
    ASLEEP_DEEP = "asleep_deep"    # 深睡
    WAKING_UP = "waking_up"        # 刚醒


class ScheduleConfig(BaseModel):
    """作息时间配置。"""

    active_hours_start: int = 8
    active_hours_end: int = 23
    response_rate_active: float = 1.0
    response_rate_inactive: float = 0.3
    response_delay_inactive: int = 300

    # 睡眠阶段时间划分
    wind_down_start: int = 22        # 开始犯困
    light_sleep_start: int = 23      # 浅睡
    deep_sleep_start: int = 0        # 深睡（凌晨0点）
    deep_sleep_end: int = 6          # 深睡结束
    waking_up_end: int = 8           # 完全清醒

    # 各睡眠阶段的行为参数
    response_rate_winding: float = 0.5    # 准备入睡时回复概率
    response_rate_light: float = 0.2      # 浅睡时回复概率
    response_rate_deep: float = 0.0       # 深睡时不回复
    response_rate_waking: float = 0.6     # 刚醒时回复概率

    typing_speed_mult_winding: float = 1.5   # 准备入睡时打字慢 1.5倍
    typing_speed_mult_light: float = 2.5     # 浅睡时打字极慢
    typing_speed_mult_waking: float = 1.3    # 刚醒时打字稍慢

    # 周末特殊作息偏移（小时）
    weekend_offset: int = 1                  # 周末晚起1小时


class SchedulerConfig(BaseModel):
    """行为调度器配置。"""

    typing_delay_min: float = 0.5
    typing_delay_max: float = 3.0
    segment_delay: float = 1.0
    message_max_length: int = 500
    segment_enabled: bool = True
    schedule: ScheduleConfig = ScheduleConfig()


class MemoryConfig(BaseModel):
    """记忆系统配置。"""

    short_term_window: int = 20
    long_term_enabled: bool = True
    vector_db_path: str = "data/chroma_db"
    summary_interval: int = 50
    importance_threshold: float = 0.6
    forget_decay: float = 0.9


class EvolutionConfig(BaseModel):
    """演化引擎配置。"""

    enabled: bool = True
    drift_rate: float = 0.001
    event_impact: float = 0.02
    freeze_enabled: bool = True
    change_log_path: str = "data/profiles/evolution_log.json"


class BotConfig(BaseModel):
    """机器人基础配置。"""

    name: str = "小助手"
    version: str = "0.1.0"
    platform: str = "qq"


class AppConfig(BaseSettings):
    """应用全局配置。

    从 TOML 文件加载，支持环境变量覆盖。
    环境变量优先级：环境变量 > TOML 文件 > 默认值。
    """

    bot: BotConfig = BotConfig()
    llm: LLMConfig = LLMConfig()
    personality: PersonalityConfig = PersonalityConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    memory: MemoryConfig = MemoryConfig()
    evolution: EvolutionConfig = EvolutionConfig()

    # 环境变量覆盖（pydantic-settings 自动处理）
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL"
    )
    qq_host: str = Field(default="127.0.0.1", validation_alias="QQ_HOST")
    qq_port: int = Field(default=6099, validation_alias="QQ_PORT")
    qq_access_token: str = Field(default="", validation_alias="QQ_ACCESS_TOKEN")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    model_config = {"extra": "ignore"}


def load_config(path: str | Path | None = None) -> AppConfig:
    """加载配置。

    从 TOML 文件加载基础配置，然后通过环境变量覆盖。

    Args:
        path: TOML 配置文件路径。为 None 时使用默认路径。

    Returns:
        合并后的应用配置。
    """
    if path is None:
        # 尝试多个默认路径
        candidates = [
            Path("configs/default.toml"),
            Path("config.toml"),
            Path.home() / ".human-like-chatbot" / "config.toml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
        else:
            path = None

    toml_data: dict[str, Any] = {}
    if path is not None and Path(path).exists():
        with open(path, "rb") as f:
            toml_data = tomllib.load(f)

    return AppConfig(**toml_data)
