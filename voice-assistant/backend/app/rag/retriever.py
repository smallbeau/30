from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from app.rag.store import Chunk, VectorStore, tokenize


@dataclass
class RetrievalDecision:
    mode: str
    hits: list[tuple[Chunk, float]]
    context: str


class KnowledgeRetriever:
    def __init__(
        self,
        store: VectorStore,
        top_k: int = 5,
        threshold_high: float = 0.75,
        threshold_low: float = 0.40,
    ):
        self.store = store
        self.top_k = top_k
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low

    def decide(self, query: str) -> RetrievalDecision:
        hits = self.store.search(query, self.top_k)
        if not hits:
            bm25_hits = self._bm25_search(query)
            if bm25_hits:
                return RetrievalDecision("hybrid", bm25_hits, self._format_context(bm25_hits))
            return RetrievalDecision("llm", [], "")
        best = hits[0][1]
        context = self._format_context(hits)
        if best >= self.threshold_high:
            return RetrievalDecision("direct", hits, hits[0][0].text)
        if best >= self.threshold_low:
            return RetrievalDecision("hybrid", hits, context)
        bm25_hits = self._bm25_search(query)
        if bm25_hits:
            return RetrievalDecision("hybrid", bm25_hits, self._format_context(bm25_hits))
        return RetrievalDecision("llm", hits, "")

    def _format_context(self, hits: list[tuple[Chunk, float]]) -> str:
        return "\n\n".join(f"[{c.source}] {c.text}" for c, _ in hits)

    def _bm25_search(self, query: str, top_k: int = 3) -> list[tuple[Chunk, float]]:
        q_tokens = tokenize(query)
        if not q_tokens or not self.store.chunks:
            return []
        n = len(self.store.chunks)
        idf: dict[str, float] = {}
        for token in set(q_tokens):
            df = sum(1 for c in self.store.chunks if c.tokens.get(token, 0) > 0)
            idf[token] = math.log((n - df + 0.5) / (df + 0.5) + 1)
        scored: list[tuple[Chunk, float]] = []
        for c in self.store.chunks:
            score = 0.0
            for t in q_tokens:
                tf = c.tokens.get(t, 0)
                if tf > 0:
                    score += idf.get(t, 0) * (tf * 1.5) / (tf + 1.5)
            if score > 0:
                scored.append((c, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
