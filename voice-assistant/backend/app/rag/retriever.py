from __future__ import annotations

from dataclasses import dataclass

from app.rag.store import Chunk, VectorStore


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
            return RetrievalDecision("llm", [], "")
        best = hits[0][1]
        context = "\n\n".join(f"[{c.source}] {c.text}" for c, _ in hits)
        if best >= self.threshold_high:
            return RetrievalDecision("direct", hits, hits[0][0].text)
        if best >= self.threshold_low:
            return RetrievalDecision("hybrid", hits, context)
        return RetrievalDecision("llm", hits, "")