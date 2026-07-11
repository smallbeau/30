from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "voice-assistant"
    host: str = "0.0.0.0"
    port: int = 8000

    models_config_path: Path = ROOT / "config" / "models.yaml"
    knowledge_config_path: Path = ROOT / "config" / "knowledge.yaml"
    vad_config_path: Path = ROOT / "config" / "vad.yaml"
    skills_dir: Path = ROOT / "skills"
    knowledge_docs_dir: Path = ROOT / "knowledge" / "docs"
    voice_config_path: Path = ROOT / "config" / "voice.yaml"
    memory_config_path: Path = ROOT / "config" / "memory.yaml"
    api_key: str = ""

    default_system_prompt: str = (
        "你是中文语音助手。优先简洁口语化回答。"
        "若用户意图匹配技能则执行技能；否则结合知识库与上下文回答。"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()