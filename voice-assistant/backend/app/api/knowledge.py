from fastapi import APIRouter

import yaml

from app.config import get_settings
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever
from app.api.deps import get_engine

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/reindex")
def reindex():
    s = get_settings()
    kcfg = yaml.safe_load(s.knowledge_config_path.read_text(encoding="utf-8")) or {}
    ret = kcfg.get("retrieval", {})
    store = KnowledgeIndexer(s.knowledge_docs_dir).build()
    get_engine.cache_clear()
    return {"chunks": len(store.chunks), "ok": True}