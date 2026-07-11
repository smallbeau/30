"""MySQL 统一会话存储 — 替换 SQLite ShortTermMemory + JSON LongTermMemory + JSON VectorMemory."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.database.mysql import get_connection, close_pool


class SessionStore:
    """MySQL 版会话存储，API 与 ShortTermMemory 完全兼容。"""

    def __init__(self, max_sessions: int = 100, session_ttl_minutes: int = 1440):
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl_minutes * 60

    def get_messages(self, session_id: str) -> list[dict]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT messages FROM sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                return json.loads(row["messages"]) if row else []
        finally:
            conn.close()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        conn = get_connection()
        now = time.time()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT messages FROM sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if row is None:
                    msgs = json.dumps([{"role": role, "content": content}])
                    cur.execute(
                        "INSERT INTO sessions (session_id, messages, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s)",
                        (session_id, msgs, now, now),
                    )
                else:
                    msgs = json.loads(row["messages"])
                    msgs.append({"role": role, "content": content})
                    msgs = msgs[-100:]
                    cur.execute(
                        "UPDATE sessions SET messages = %s, updated_at = %s WHERE session_id = %s",
                        (json.dumps(msgs), now, session_id),
                    )
            conn.commit()
        finally:
            conn.close()

    def get_context(self, session_id: str, max_messages: int = 10) -> list[dict]:
        msgs = self.get_messages(session_id)
        return msgs[-max_messages:]

    def delete_session(self, session_id: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            conn.commit()
        finally:
            conn.close()

    def list_sessions(self) -> list[dict[str, Any]]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, created_at, updated_at FROM sessions "
                    "ORDER BY updated_at DESC"
                )
                return [
                    {"session_id": r["session_id"], "created_at": r["created_at"],
                     "updated_at": r["updated_at"]}
                    for r in cur.fetchall()
                ]
        finally:
            conn.close()

    def cleanup_old(self) -> int:
        conn = get_connection()
        cutoff = time.time() - self._session_ttl
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sessions WHERE updated_at < %s", (cutoff,)
                )
                deleted = cur.rowcount
                cur.execute(
                    "DELETE FROM session_summaries WHERE session_id NOT IN "
                    "(SELECT session_id FROM sessions)"
                )
                conn.commit()
                return deleted
        finally:
            conn.close()

    def add_summary(self, session_id: str, summary: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO session_summaries (session_id, summary, created_at) "
                    "VALUES (%s, %s, %s)",
                    (session_id, summary, time.time()),
                )
            conn.commit()
        finally:
            conn.close()

    def close(self) -> None:
        close_pool()


class LongTermStore:
    """MySQL 版长期记忆，API 与 LongTermMemory 兼容。"""

    def __init__(self, max_entries: int = 100):
        self._max_entries = max_entries

    def add(self, user_id: str, summary: str, topics: list[str] | None = None,
            key_facts: list[str] | None = None) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO long_term_memory (user_id, summary, topics, key_facts, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (user_id, summary, json.dumps(topics or []),
                     json.dumps(key_facts or []), time.time()),
                )
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM long_term_memory WHERE user_id = %s",
                    (user_id,),
                )
                cnt = cur.fetchone()["cnt"]
                if cnt > self._max_entries:
                    cur.execute(
                        "DELETE FROM long_term_memory WHERE user_id = %s "
                        "ORDER BY created_at ASC LIMIT %s",
                        (user_id, cnt - self._max_entries),
                    )
            conn.commit()
        finally:
            conn.close()

    def get(self, user_id: str) -> list[dict[str, Any]]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT summary, topics, key_facts, created_at "
                    "FROM long_term_memory WHERE user_id = %s ORDER BY created_at",
                    (user_id,),
                )
                return [
                    {
                        "summary": r["summary"],
                        "topics": json.loads(r["topics"]) if isinstance(r["topics"], str) else r["topics"],
                        "key_facts": json.loads(r["key_facts"]) if isinstance(r["key_facts"], str) else r["key_facts"],
                        "timestamp": r["created_at"],
                    }
                    for r in cur.fetchall()
                ]
        finally:
            conn.close()

    def get_recent(self, user_id: str, n: int = 5) -> list[dict[str, Any]]:
        entries = self.get(user_id)
        return entries[-n:]

    def search_by_topics(self, user_id: str, topics: list[str]) -> list[dict[str, Any]]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                results = []
                for t in topics:
                    cur.execute(
                        "SELECT summary, topics, key_facts, created_at "
                        "FROM long_term_memory WHERE user_id = %s AND "
                        "JSON_CONTAINS(topics, %s)",
                        (user_id, json.dumps(t)),
                    )
                    for r in cur.fetchall():
                        entry = {
                            "summary": r["summary"],
                            "topics": json.loads(r["topics"]) if isinstance(r["topics"], str) else r["topics"],
                            "key_facts": json.loads(r["key_facts"]) if isinstance(r["key_facts"], str) else r["key_facts"],
                            "timestamp": r["created_at"],
                        }
                        if entry not in results:
                            results.append(entry)
                return results[-5:]
        finally:
            conn.close()

    def delete_user(self, user_id: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM long_term_memory WHERE user_id = %s", (user_id,))
            conn.commit()
        finally:
            conn.close()


class MySQLVectorStore:
    """MySQL 版向量记忆，API 与 VectorMemory 兼容。"""

    def __init__(self, enabled: bool = False):
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def add_entry(self, text: str, metadata: dict | None = None) -> None:
        if not self._enabled:
            return
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vector_memory (text, metadata, created_at) VALUES (%s, %s, %s)",
                    (text, json.dumps(metadata or {}), time.time()),
                )
                cur.execute("SELECT COUNT(*) AS cnt FROM vector_memory")
                cnt = cur.fetchone()["cnt"]
                if cnt > 500:
                    cur.execute(
                        "DELETE FROM vector_memory ORDER BY created_at ASC LIMIT %s",
                        (cnt - 500,),
                    )
            conn.commit()
        finally:
            conn.close()

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self._enabled:
            return []
        conn = get_connection()
        q = query.lower()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT text, metadata, created_at FROM vector_memory WHERE LOWER(text) LIKE %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (f"%{q}%", top_k * 2),
                )
                scored: list[tuple[dict, float]] = []
                for row in cur.fetchall():
                    text_lower = (row["text"] or "").lower()
                    words = q.split()
                    if words:
                        matches = sum(1 for w in words if w in text_lower)
                        score = matches / len(words)
                    else:
                        score = 0.0
                    if score > 0:
                        scored.append(({**row, "metadata": json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]}, score))
                scored.sort(key=lambda x: x[1], reverse=True)
                return [entry for entry, _ in scored[:top_k]]
        finally:
            conn.close()

    def clear(self) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM vector_memory")
            conn.commit()
        finally:
            conn.close()