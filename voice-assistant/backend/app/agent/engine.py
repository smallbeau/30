from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from app.agent.context import SessionContext
from app.skill.loader import Skill
from app.skill.matcher import SkillMatcher
from app.skill.executor import SkillExecutor


@dataclass
class AgentResult:
    text: str
    source: str


class AgentEngine:
    def __init__(self, llm, retriever, skills: list[Skill], system_prompt: str = ""):
        self.llm = llm
        self.retriever = retriever
        self.matcher = SkillMatcher(skills)
        self.executor = SkillExecutor(llm)
        self.system_prompt = system_prompt or "你是中文助手。"
        self.memory = None
        self.sessions: dict[str, SessionContext] = {}

    def get_session(self, session_id: str = "default") -> SessionContext:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionContext(session_id=session_id)
        return self.sessions[session_id]

    def handle(self, user_text: str, session_id: str = "default") -> AgentResult:
        session = self.get_session(session_id)
        session.add("user", user_text)

        decision = self.retriever.decide(user_text)
        if decision.mode == "direct":
            text = decision.context
            session.add("assistant", text)
            return AgentResult(text=text, source="knowledge")

        skill = self.matcher.match(user_text)
        if skill is not None:
            text = self.executor.run(skill, user_text)
            session.add("assistant", text)
            return AgentResult(text=text, source="skill")

        messages = [{"role": "system", "content": self.system_prompt}]
        if decision.mode == "hybrid" and decision.context:
            messages.append(
                {
                    "role": "system",
                    "content": f"参考知识库：\n{decision.context}",
                }
            )
        messages.extend(session.messages[-10:])
        text = self.llm.chat(messages)
        session.add("assistant", text)
        source = "hybrid" if decision.mode == "hybrid" else "llm"
        return AgentResult(text=text, source=source)

    def stream_handle(self, user_text: str, session_id: str = "default") -> Iterator[str]:
        session = self.get_session(session_id)
        session.add("user", user_text)

        decision = self.retriever.decide(user_text)
        if decision.mode == "direct":
            session.add("assistant", decision.context)
            yield decision.context
            return

        skill = self.matcher.match(user_text)
        if skill is not None:
            text = self.executor.run(skill, user_text)
            session.add("assistant", text)
            yield text
            return

        messages = [{"role": "system", "content": self.system_prompt}]
        if decision.mode == "hybrid" and decision.context:
            messages.append({"role": "system", "content": f"参考知识库：\n{decision.context}"})
        messages.extend(session.messages[-10:])

        parts: list[str] = []
        for token in self.llm.stream_chat(messages):
            parts.append(token)
            yield token
        session.add("assistant", "".join(parts))