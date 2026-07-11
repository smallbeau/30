from pathlib import Path
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever


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