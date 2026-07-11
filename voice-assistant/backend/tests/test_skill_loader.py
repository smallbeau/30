from pathlib import Path
from app.skill.loader import SkillLoader


def test_load_skill_frontmatter(tmp_path: Path):
    skill = tmp_path / "translate.md"
    skill.write_text(
        """---
name: 翻译
trigger: 翻译|translate|翻成
description: 多语言翻译
version: 1.0.0
---
## steps
1. 识别目标语言
2. 翻译用户文本
3. 返回译文
## examples
- 把你好翻译成英文
""",
        encoding="utf-8",
    )
    loader = SkillLoader(tmp_path)
    skills = loader.load_all()
    assert len(skills) == 1
    assert skills[0].name == "翻译"
    assert "翻译" in skills[0].triggers
    assert "识别目标语言" in skills[0].steps[0]