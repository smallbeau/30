from functools import lru_cache

import yaml

from app.config import get_settings
from app.llm.client import LLMClient
from app.skill.loader import SkillLoader
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever
from app.agent.engine import AgentEngine
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.memory.vector import VectorMemory


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
    mcfg = yaml.safe_load(s.memory_config_path.read_text(encoding="utf-8")) or {}
    st = mcfg.get("short_term", {})
    lt = mcfg.get("long_term", {})
    vm = mcfg.get("vector", {})
    short_mem = ShortTermMemory(
        db_path=st.get("db_path", "data/sessions.db"),
        max_sessions=int(st.get("max_sessions", 100)),
        session_ttl_minutes=int(st.get("session_ttl_minutes", 1440)),
    )
    long_mem = LongTermMemory(
        db_path="data/long_term.json",
        max_entries=int(lt.get("max_summaries", 100)),
    )
    vec_mem = VectorMemory(
        db_path="data/vector_memory.json",
        enabled=bool(vm.get("enabled", False)),
    )
    return AgentEngine(
        llm, retriever, skills, s.default_system_prompt,
        short_mem=short_mem, long_mem=long_mem, vec_mem=vec_mem,
    )


@lru_cache
def get_memory() -> ShortTermMemory:
    s = get_settings()
    mcfg = yaml.safe_load(s.memory_config_path.read_text(encoding="utf-8")) or {}
    st = mcfg.get("short_term", {})
    return ShortTermMemory(
        db_path=st.get("db_path", "data/sessions.db"),
        max_sessions=int(st.get("max_sessions", 100)),
        session_ttl_minutes=int(st.get("session_ttl_minutes", 1440)),
    )