from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LongTermMemoryEntry:
    summary: str
    topics: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    timestamp: float = 0.0


class LongTermMemory:
    def __init__(self, db_path: str | Path = "data/long_term.json",
                 max_entries: int = 100):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_entries = max_entries
        self._entries: dict[str, list[LongTermMemoryEntry]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for uid, entries in data.items():
                self._entries[uid] = [
                    LongTermMemoryEntry(**e) for e in entries
                ]
        except (json.JSONDecodeError, KeyError):
            self._entries = {}

    def _save(self) -> None:
        data: dict[str, list[dict[str, Any]]] = {}
        for uid, entries in self._entries.items():
            data[uid] = [
                {"summary": e.summary, "topics": e.topics,
                 "key_facts": e.key_facts, "timestamp": e.timestamp}
                for e in entries[-self._max_entries:]
            ]
        self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def add(self, user_id: str, summary: str, topics: list[str] | None = None,
            key_facts: list[str] | None = None) -> None:
        if user_id not in self._entries:
            self._entries[user_id] = []
        self._entries[user_id].append(LongTermMemoryEntry(
            summary=summary, topics=topics or [],
            key_facts=key_facts or [], timestamp=time.time(),
        ))
        self._save()

    def get(self, user_id: str) -> list[LongTermMemoryEntry]:
        return self._entries.get(user_id, [])

    def get_recent(self, user_id: str, n: int = 5) -> list[LongTermMemoryEntry]:
        entries = self._entries.get(user_id, [])
        return entries[-n:]

    def search_by_topics(self, user_id: str, topics: list[str]) -> list[LongTermMemoryEntry]:
        entries = self._entries.get(user_id, [])
        results = []
        for e in entries:
            if any(t in e.topics for t in topics):
                results.append(e)
        return results[-5:]

    def delete_user(self, user_id: str) -> None:
        self._entries.pop(user_id, None)
        self._save()
