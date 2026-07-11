from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import yaml
from openai import OpenAI

from app.llm.models import ModelConfig, ModelsFile


class LLMClient:
    def __init__(self, models: list[ModelConfig], default_model: str | None = None):
        if not models:
            raise ValueError("at least one model is required")
        self._models = {m.name: m for m in sorted(models, key=lambda x: x.priority)}
        self.default_model_name = default_model or models[0].name
        if self.default_model_name not in self._models:
            raise ValueError(f"default model not found: {self.default_model_name}")

    @classmethod
    def from_yaml(cls, path: Path) -> "LLMClient":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        mf = ModelsFile.model_validate(data)
        return cls(mf.models, mf.default_model)

    def get_model(self, name: str | None = None) -> ModelConfig:
        key = name or self.default_model_name
        if key not in self._models:
            raise KeyError(f"unknown model: {key}")
        return self._models[key]

    def _client(self, model: ModelConfig) -> OpenAI:
        api_key = os.getenv(model.api_key_env, "") if model.api_key_env else "EMPTY"
        return OpenAI(base_url=model.base_url, api_key=api_key or "EMPTY")

    def stream_chat(
        self,
        messages: list[dict],
        model_name: str | None = None,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        cfg = self.get_model(model_name)
        client = self._client(cfg)
        stream = client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def chat(
        self,
        messages: list[dict],
        model_name: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        return "".join(self.stream_chat(messages, model_name, temperature))