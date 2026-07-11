from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.rag.store import Chunk, VectorStore, tokenize


class KnowledgeIndexer:
    def __init__(self, docs_dir: Path, chunk_size: int = 500, overlap: int = 50):
        self.docs_dir = docs_dir
        self.chunk_size = chunk_size
        self.overlap = overlap

    def build(self) -> VectorStore:
        store = VectorStore()
        for path in self.docs_dir.rglob("*"):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for i, piece in enumerate(self._chunk(text)):
                store.add(
                    Chunk(
                        id=f"{path.name}:{i}",
                        source=str(path),
                        text=piece,
                        tokens=Counter(tokenize(piece)),
                    )
                )
        return store

    def _chunk(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        out: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            out.append(text[start:end])
            start = end - self.overlap
            if start < 0:
                start = 0
            if end >= len(text):
                break
        return out