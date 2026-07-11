from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class VectorMemory:
    def __init__(self, db_path: str | Path = "data/vector_memory.json",
                 enabled: bool = False):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._enabled = enabled
        self._entries: list[dict[str, Any]] = []
        self._embedder = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = data.get("entries", [])
        except (json.JSONDecodeError, KeyError):
            self._entries = []

    def _save(self) -> None:
        self._path.write_text(
            json.dumps({"entries": self._entries[-500:]}, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def add_entry(self, text: str, metadata: dict | None = None) -> None:
        if not self._enabled:
            return
        self._entries.append({
            "text": text,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })
        self._save()

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self._enabled or not self._entries:
            return []
        q = query.lower()
        scored: list[tuple[dict[str, Any], float]] = []
        for entry in self._entries:
            text = entry.get("text", "").lower()
            score = self._simple_score(q, text)
            scored.append((entry, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored[:top_k]]

    def _simple_score(self, query: str, text: str) -> float:
        if not query or not text:
            return 0.0
        words = query.split()
        if not words:
            return 0.0
        matches = sum(1 for w in words if w in text)
        return matches / len(words)

    def clear(self) -> None:
        self._entries.clear()
        self._save()
