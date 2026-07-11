from functools import lru_cache

import yaml

from app.config import get_settings
from app.llm.client import LLMClient
from app.skill.loader import SkillLoader
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever
from app.agent.engine import AgentEngine


@lru_cache
def get_engine() -> AgentEngine:
    s = get_settings()
    llm = LLMClient.from_yaml(s.models_config_path)
    skills = SkillLoader(s.skills_dir).load_all()
    kcfg = yaml.safe_load(s.knowledge_config_path.read_text(encoding="utf-8")) or {}
    ret = kcfg.get("retrieval", {})
    store = KnowledgeIndexer(s.knowledge_docs_dir).build()
    retriever = KnowledgeRetriever(
        store,
        top_k=int(ret.get("top_k", 5)),
        threshold_high=float(ret.get("threshold_high", 0.75)),
        threshold_low=float(ret.get("threshold_low", 0.4)),
    )
    return AgentEngine(llm, retriever, skills, s.default_system_prompt)