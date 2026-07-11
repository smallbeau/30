import tempfile
from pathlib import Path

from app.memory.long_term import LongTermMemory


def test_add_and_get():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "ltm.json"
        m = LongTermMemory(db, max_entries=10)
        m.add("user1", "关于天气的对话", topics=["天气", "北京"])
        entries = m.get("user1")
        assert len(entries) == 1
        assert entries[0].summary == "关于天气的对话"


def test_search_by_topics():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "ltm.json"
        m = LongTermMemory(db)
        m.add("u1", "讨论编程", topics=["编程", "Python"])
        m.add("u1", "讨论天气", topics=["天气", "北京"])
        results = m.search_by_topics("u1", ["天气"])
        assert len(results) == 1
        assert "天气" in results[0].topics


def test_recent():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "ltm.json"
        m = LongTermMemory(db)
        for i in range(10):
            m.add("u1", f"对话{i}", topics=["test"])
        recent = m.get_recent("u1", 3)
        assert len(recent) == 3


def test_delete_user():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "ltm.json"
        m = LongTermMemory(db)
        m.add("u1", "test")
        m.delete_user("u1")
        assert m.get("u1") == []
