from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import jieba


def tokenize(text: str) -> list[str]:
    words = jieba.lcut(text.lower())
    return [w for w in words if w.strip() and not w.isspace()]


@dataclass
class Chunk:
    id: str
    source: str
    text: str
    tokens: Counter


class VectorStore:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks or []

    def add(self, chunk: Chunk) -> None:
        self.chunks.append(chunk)

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        q = Counter(tokenize(query))
        scored: list[tuple[Chunk, float]] = []
        for c in self.chunks:
            scored.append((c, self._cosine(q, c.tokens)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _cosine(self, a: Counter, b: Counter) -> float:
        if not a or not b:
            return 0.0
        keys = set(a) | set(b)
        dot = sum(a[k] * b[k] for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)