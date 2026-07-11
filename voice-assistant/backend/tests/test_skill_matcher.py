from app.skill.loader import Skill
from app.skill.matcher import SkillMatcher
from app.skill.executor import SkillExecutor


def test_match_by_trigger():
    skills = [
        Skill(name="翻译", triggers=["翻译", "translate"], description="t", steps=["翻译文本"])
    ]
    matcher = SkillMatcher(skills)
    hit = matcher.match("请把你好翻译成英文")
    assert hit is not None
    assert hit.name == "翻译"


def test_executor_uses_llm(monkeypatch):
    class FakeLLM:
        def chat(self, messages, model_name=None, temperature=0.7):
            return "Hello"

    skill = Skill(name="翻译", triggers=["翻译"], description="t", steps=["翻译文本"])
    ex = SkillExecutor(FakeLLM())
    out = ex.run(skill, "把你好翻译成英文")
    assert "Hello" in out