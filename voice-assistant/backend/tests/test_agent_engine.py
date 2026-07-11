from app.agent.engine import AgentEngine
from app.skill.loader import Skill


class FakeLLM:
    def chat(self, messages, model_name=None, temperature=0.7):
        return "LLM_ANSWER"

    def stream_chat(self, messages, model_name=None, temperature=0.7):
        yield "LLM_"
        yield "ANSWER"


class FakeRetriever:
    def decide(self, query: str):
        from app.rag.retriever import RetrievalDecision

        if "地址" in query:
            return RetrievalDecision("direct", [], "北京海淀")
        return RetrievalDecision("llm", [], "")


def test_agent_prefers_knowledge():
    engine = AgentEngine(FakeLLM(), FakeRetriever(), skills=[])
    result = engine.handle("公司地址在哪")
    assert "北京" in result.text


def test_agent_skill_then_llm():
    skills = [Skill(name="翻译", triggers=["翻译"], description="t", steps=["翻译"])]
    engine = AgentEngine(FakeLLM(), FakeRetriever(), skills=skills)
    result = engine.handle("请翻译 hello")
    assert result.source in {"skill", "llm"}