from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.rag.store import Chunk, VectorStore, tokenize


class KnowledgeIndexer:
    def __init__(self, docs_dir: Path, chunk_size: int = 500, overlap: int = 50):
        self.docs_dir = docs_dir
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._parsers = {
            ".md": self._read_text,
            ".txt": self._read_text,
            ".html": self._read_text,
            ".htm": self._read_text,
        }

    def build(self, additional_dirs: list[Path] | None = None) -> VectorStore:
        store = VectorStore()
        dirs = [self.docs_dir] + (additional_dirs or [])
        for d in dirs:
            if not d.exists():
                continue
            for path in d.rglob("*"):
                if path.suffix.lower() not in self._parsers:
                    continue
                text = self._parsers[path.suffix.lower()](path)
                if not text:
                    continue
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

    def build_from_texts(self, texts: list[tuple[str, str]]) -> VectorStore:
        store = VectorStore()
        for source, text in texts:
            for i, piece in enumerate(self._chunk(text)):
                store.add(
                    Chunk(
                        id=f"{source}:{i}",
                        source=source,
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

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore")
