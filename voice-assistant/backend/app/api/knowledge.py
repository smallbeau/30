from __future__ import annotations

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import get_engine
from app.config import get_settings
from app.rag.crawler import crawl_url
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever

router = APIRouter(tags=["knowledge"])


class CrawlRequest(BaseModel):
    url: str


@router.post("/knowledge/reindex")
def reindex():
    s = get_settings()
    kcfg = yaml.safe_load(s.knowledge_config_path.read_text(encoding="utf-8")) or {}
    ret = kcfg.get("retrieval", {})
    store = KnowledgeIndexer(s.knowledge_docs_dir).build()
    get_engine.cache_clear()
    return {"chunks": len(store.chunks), "ok": True}


@router.post("/knowledge/crawl")
def crawl(req: CrawlRequest):
    s = get_settings()
    page = crawl_url(req.url, s.knowledge_docs_dir.parent / "crawled")
    if page is None:
        return {"ok": False, "error": "crawl failed"}
    kcfg = yaml.safe_load(s.knowledge_config_path.read_text(encoding="utf-8")) or {}
    ret = kcfg.get("retrieval", {})
    store = KnowledgeIndexer(s.knowledge_docs_dir).build(
        additional_dirs=[s.knowledge_docs_dir.parent / "crawled"]
    )
    get_engine.cache_clear()
    return {"ok": True, "title": page.title, "chunks": len(store.chunks)}


@router.get("/knowledge/search")
def search_knowledge(q: str, top_k: int = 3):
    engine = get_engine()
    decision = engine.retriever.decide(q)
    return {
        "mode": decision.mode,
        "results": [
            {"source": c.source, "text": c.text[:200], "score": round(s, 3)}
            for c, s in decision.hits[:top_k]
        ],
    }
