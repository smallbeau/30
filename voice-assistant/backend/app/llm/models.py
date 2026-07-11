from __future__ import annotations

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    name: str
    base_url: str
    api_key_env: str = ""
    model: str
    priority: int = 100


class ModelsFile(BaseModel):
    models: list[ModelConfig] = Field(default_factory=list)
    default_model: str | None = None