from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionContext:
    session_id: str
    messages: list[dict] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})