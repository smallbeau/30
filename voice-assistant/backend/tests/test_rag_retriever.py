from collections import Counter
from pathlib import Path

from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever
from app.rag.store import Chunk, VectorStore, tokenize


def test_index_and_retrieve(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# 公司地址\n我们公司在北京海淀区。\n", encoding="utf-8")
    indexer = KnowledgeIndexer(docs)
    store = indexer.build()
    retriever = KnowledgeRetriever(store, threshold_high=0.3, threshold_low=0.05)
    decision = retriever.decide("公司在哪里")
    assert decision.mode in {"direct", "hybrid", "llm"}
    assert decision.hits


def test_bm25_fallback():
    store = VectorStore()
    store.add(Chunk(id="1", source="a.md", text="北京天气晴朗", tokens=Counter(tokenize("北京天气晴朗"))))
    store.add(Chunk(id="2", source="b.md", text="上海天气多云", tokens=Counter(tokenize("上海天气多云"))))
    retriever = KnowledgeRetriever(store, threshold_high=0.99, threshold_low=0.98)
    decision = retriever.decide("北京天气")
    assert decision.mode in {"hybrid", "llm"}


def test_build_from_texts():
    indexer = KnowledgeIndexer(Path("/nonexistent"))
    store = indexer.build_from_texts([("test.md", "这是测试内容")])
    assert len(store.chunks) >= 1
