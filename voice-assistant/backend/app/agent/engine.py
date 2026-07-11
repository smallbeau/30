from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from app.agent.context import SessionContext
from app.agent.intent import classify_intent
from app.database import SessionStore, LongTermStore, MySQLVectorStore
from app.skill.loader import Skill
from app.skill.matcher import SkillMatcher
from app.skill.executor import SkillExecutor


@dataclass
class AgentResult:
    text: str
    source: str


class AgentEngine:
    def __init__(self, llm, retriever, skills: list[Skill], system_prompt: str = "",
                 short_mem: SessionStore | None = None,
                 long_mem: LongTermStore | None = None,
                 vec_mem: MySQLVectorStore | None = None):
        self.llm = llm
        self.retriever = retriever
        self.matcher = SkillMatcher(skills)
        self.executor = SkillExecutor(llm)
        self.system_prompt = system_prompt or "你是中文助手。"
        self.short_mem = short_mem or SessionStore()
        self.long_mem = long_mem or LongTermStore()
        self.vec_mem = vec_mem or MySQLVectorStore()
        self.sessions: dict[str, SessionContext] = {}

    def get_session(self, session_id: str = "default") -> SessionContext:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionContext(session_id=session_id)
        return self.sessions[session_id]

    def handle(self, user_text: str, session_id: str = "default") -> AgentResult:
        self.short_mem.add_message(session_id, "user", user_text)
        intent = classify_intent(user_text)

        if intent.intent == "greeting":
            reply = f"你好！有什么可以帮你的？"
            self.short_mem.add_message(session_id, "assistant", reply)
            return AgentResult(text=reply, source="intent")

        if intent.intent == "goodbye":
            reply = "再见！有需要随时找我。"
            self.short_mem.add_message(session_id, "assistant", reply)
            return AgentResult(text=reply, source="intent")

        if intent.intent == "help":
            reply = (
                "我可以帮你：查天气、翻译、设闹钟、搜索、记备忘录。"
                "直接说出你的需求即可。"
            )
            self.short_mem.add_message(session_id, "assistant", reply)
            return AgentResult(text=reply, source="intent")

        decision = self.retriever.decide(user_text)
        if decision.mode == "direct":
            self.short_mem.add_message(session_id, "assistant", decision.context)
            return AgentResult(text=decision.context, source="knowledge")

        skill = self.matcher.match(user_text)
        if skill is not None:
            text = self.executor.run(skill, user_text)
            self.short_mem.add_message(session_id, "assistant", text)
            self.vec_mem.add_entry(text, {"source": "skill"})
            return AgentResult(text=text, source="skill")

        messages = [{"role": "system", "content": self.system_prompt}]
        if decision.mode == "hybrid" and decision.context:
            messages.append(
                {"role": "system", "content": f"参考知识库：\n{decision.context}"}
            )
        ctx = self.short_mem.get_context(session_id, max_messages=10)
        messages.extend(ctx)
        text = self.llm.chat(messages)
        self.short_mem.add_message(session_id, "assistant", text)
        self.vec_mem.add_entry(text, {"source": "llm"})
        source = "hybrid" if decision.mode == "hybrid" else "llm"
        return AgentResult(text=text, source=source)

    def stream_handle(self, user_text: str, session_id: str = "default") -> Iterator[str]:
        self.short_mem.add_message(session_id, "user", user_text)
        intent = classify_intent(user_text)

        if intent.intent == "greeting":
            reply = "你好！有什么可以帮你的？"
            self.short_mem.add_message(session_id, "assistant", reply)
            yield reply
            return

        if intent.intent == "goodbye":
            reply = "再见！有需要随时找我。"
            self.short_mem.add_message(session_id, "assistant", reply)
            yield reply
            return

        if intent.intent == "help":
            reply = "我可以帮你：查天气、翻译、设闹钟、搜索、记备忘录。直接说出你的需求即可。"
            self.short_mem.add_message(session_id, "assistant", reply)
            yield reply
            return

        decision = self.retriever.decide(user_text)
        if decision.mode == "direct":
            self.short_mem.add_message(session_id, "assistant", decision.context)
            yield decision.context
            return

        skill = self.matcher.match(user_text)
        if skill is not None:
            text = self.executor.run(skill, user_text)
            self.short_mem.add_message(session_id, "assistant", text)
            yield text
            return

        messages = [{"role": "system", "content": self.system_prompt}]
        if decision.mode == "hybrid" and decision.context:
            messages.append({"role": "system", "content": f"参考知识库：\n{decision.context}"})
        ctx = self.short_mem.get_context(session_id, max_messages=10)
        messages.extend(ctx)

        parts: list[str] = []
        for token in self.llm.stream_chat(messages):
            parts.append(token)
            yield token
        full = "".join(parts)
        self.short_mem.add_message(session_id, "assistant", full)
        self.vec_mem.add_entry(full, {"source": "llm"})
