from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


@dataclass
class Skill:
    name: str
    triggers: list[str]
    description: str
    version: str = "0.0.0"
    steps: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    tools: dict = field(default_factory=dict)
    raw_path: Path | None = None


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir

    def load_all(self) -> list[Skill]:
        skills: list[Skill] = []
        for path in sorted(self.skills_dir.glob("*.md")):
            skills.append(self._parse(path))
        return skills

    def _parse(self, path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            raise ValueError(f"invalid skill frontmatter: {path}")
        meta_raw, body = m.group(1), m.group(2)
        meta: dict[str, str] = {}
        for line in meta_raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        triggers = [t.strip() for t in meta.get("trigger", "").split("|") if t.strip()]
        steps = self._section_lines(body, "steps")
        examples = self._section_lines(body, "examples")
        tools = self._section_kv(body, "tools")
        return Skill(
            name=meta.get("name", path.stem),
            triggers=triggers,
            description=meta.get("description", ""),
            version=meta.get("version", "0.0.0"),
            steps=steps,
            examples=examples,
            tools=tools,
            raw_path=path,
        )

    def _section_lines(self, body: str, header: str) -> list[str]:
        pattern = re.compile(rf"^##\s+{header}\s*$", re.I | re.M)
        m = pattern.search(body)
        if not m:
            return []
        rest = body[m.end():]
        next_h = re.search(r"^##\s+", rest, re.M)
        block = rest[: next_h.start()] if next_h else rest
        lines: list[str] = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*\d.]+\s*", "", line)
            lines.append(line)
        return lines

    def _section_kv(self, body: str, header: str) -> dict:
        pattern = re.compile(rf"^##\s+{header}\s*$", re.I | re.M)
        m = pattern.search(body)
        if not m:
            return {}
        rest = body[m.end():]
        next_h = re.search(r"^##\s+", rest, re.M)
        block = rest[: next_h.start()] if next_h else rest
        result: dict[str, dict] = {}
        current_key: str | None = None
        for line in block.splitlines():
            if not line.strip():
                continue
            if not line.startswith(" ") and ":" in line:
                # top-level key: value
                k, v = line.split(":", 1)
                current_key = k.strip()
                result[current_key] = {"type": v.strip()}
            elif line.strip().startswith("- "):
                # nested list item
                pass
            elif ":" in line and current_key:
                k, v = line.split(":", 1)
                result[current_key][k.strip()] = v.strip()
        return result