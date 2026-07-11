from __future__ import annotations

from app.skill.loader import Skill


class SkillMatcher:
    def __init__(self, skills: list[Skill]):
        self.skills = skills

    def match(self, user_text: str) -> Skill | None:
        text = user_text.lower()
        for skill in self.skills:
            for t in skill.triggers:
                if t.lower() in text:
                    return skill
        return None