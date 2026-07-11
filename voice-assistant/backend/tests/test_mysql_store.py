import pytest

from app.database import SessionStore, LongTermStore, MySQLVectorStore
from app.database.mysql import get_pool, init_tables


@pytest.fixture(autouse=True, scope="session")
def _setup_db():
    init_tables()


@pytest.fixture(autouse=True)
def _clean_tables():
    pool = get_pool()
    conn = pool.connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions")
            cur.execute("DELETE FROM session_summaries")
            cur.execute("DELETE FROM long_term_memory")
            cur.execute("DELETE FROM vector_memory")
        conn.commit()
    finally:
        conn.close()


def test_session_store_add_and_get():
    s = SessionStore(max_sessions=10, session_ttl_minutes=60)
    s.add_message("sid1", "user", "你好")
    s.add_message("sid1", "assistant", "你好！")
    msgs = s.get_messages("sid1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "你好"


def test_session_context_limit():
    s = SessionStore()
    for i in range(20):
        s.add_message("sid2", "user", f"msg{i}")
    ctx = s.get_context("sid2", max_messages=5)
    assert len(ctx) == 5
    assert ctx[-1]["content"] == "msg19"


def test_session_delete():
    s = SessionStore()
    s.add_message("sid3", "user", "hello")
    assert len(s.get_messages("sid3")) == 1
    s.delete_session("sid3")
    assert s.get_messages("sid3") == []


def test_session_list():
    s = SessionStore()
    s.add_message("a", "user", "x")
    s.add_message("b", "user", "y")
    sessions = s.list_sessions()
    ids = {row["session_id"] for row in sessions}
    assert "a" in ids
    assert "b" in ids


def test_session_cleanup_old():
    s = SessionStore(session_ttl_minutes=-1)
    s.add_message("old_sid", "user", "x")
    deleted = s.cleanup_old()
    assert deleted > 0


def test_long_term_store_add_and_get():
    lt = LongTermStore(max_entries=10)
    lt.add("user1", "喜欢打篮球", topics=["运动", "篮球"], key_facts=["爱好"])
    lt.add("user1", "在北京工作", topics=["工作"], key_facts=["城市"])
    entries = lt.get("user1")
    assert len(entries) == 2
    assert entries[0]["summary"] == "喜欢打篮球"


def test_long_term_store_recent():
    lt = LongTermStore()
    for i in range(10):
        lt.add("u1", f"summary{i}", topics=["t"], key_facts=["f"])
    recent = lt.get_recent("u1", n=3)
    assert len(recent) == 3


def test_long_term_search_by_topics():
    lt = LongTermStore()
    lt.add("u1", "篮球比赛", topics=["运动", "篮球"])
    lt.add("u1", "编程学习", topics=["技术", "Python"])
    results = lt.search_by_topics("u1", ["篮球"])
    assert len(results) >= 1
    assert results[0]["summary"] == "篮球比赛"


def test_long_term_delete_user():
    lt = LongTermStore()
    lt.add("u_del", "test", topics=["x"], key_facts=["y"])
    assert len(lt.get("u_del")) == 1
    lt.delete_user("u_del")
    assert lt.get("u_del") == []


def test_vector_store_disabled():
    vs = MySQLVectorStore()
    assert not vs.enabled
    vs.add_entry("test")
    assert vs.search("test") == []


def test_vector_store_enabled():
    vs = MySQLVectorStore(enabled=True)
    vs.add_entry("今天北京天气很好", {"intent": "weather"})
    results = vs.search("北京天气", top_k=5)
    assert len(results) >= 1
    assert results[0]["text"] == "今天北京天气很好"


def test_vector_store_clear():
    vs = MySQLVectorStore(enabled=True)
    vs.add_entry("test entry")
    vs.clear()
    assert vs.search("test") == []
