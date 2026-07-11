import tempfile
from pathlib import Path

from app.memory.short_term import ShortTermMemory


def test_add_and_get_messages():
    db = Path(tempfile.gettempdir()) / "test_stm_1.db"
    db.unlink(missing_ok=True)
    m = ShortTermMemory(db, max_sessions=10, session_ttl_minutes=60)
    try:
        m.add_message("s1", "user", "你好")
        m.add_message("s1", "assistant", "你好！")
        msgs = m.get_messages("s1")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "你好"
    finally:
        m.close()
        db.unlink(missing_ok=True)


def test_context_limit():
    db = Path(tempfile.gettempdir()) / "test_stm_2.db"
    db.unlink(missing_ok=True)
    m = ShortTermMemory(db)
    try:
        for i in range(20):
            m.add_message("s1", "user", f"msg{i}")
        ctx = m.get_context("s1", max_messages=5)
        assert len(ctx) == 5
    finally:
        m.close()
        db.unlink(missing_ok=True)


def test_delete_session():
    db = Path(tempfile.gettempdir()) / "test_stm_3.db"
    db.unlink(missing_ok=True)
    m = ShortTermMemory(db)
    try:
        m.add_message("s1", "user", "hi")
        m.delete_session("s1")
        assert m.get_messages("s1") == []
    finally:
        m.close()
        db.unlink(missing_ok=True)


def test_list_sessions():
    db = Path(tempfile.gettempdir()) / "test_stm_4.db"
    db.unlink(missing_ok=True)
    m = ShortTermMemory(db)
    try:
        m.add_message("s1", "user", "a")
        m.add_message("s2", "user", "b")
        sessions = m.list_sessions()
        assert len(sessions) == 2
    finally:
        m.close()
        db.unlink(missing_ok=True)
