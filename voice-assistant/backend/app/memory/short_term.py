from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class ShortTermMemory:
    def __init__(self, db_path: str | Path = "data/sessions.db",
                 max_sessions: int = 100, session_ttl_minutes: int = 1440):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl_minutes * 60
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                messages TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def get_messages(self, session_id: str) -> list[dict]:
        row = self._conn.execute(
            "SELECT messages FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return []
        return json.loads(row["messages"])

    def add_message(self, session_id: str, role: str, content: str) -> None:
        now = time.time()
        row = self._conn.execute(
            "SELECT messages FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            msgs = [{"role": role, "content": content}]
            self._conn.execute(
                "INSERT INTO sessions (session_id, messages, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, json.dumps(msgs), now, now),
            )
        else:
            msgs = json.loads(row["messages"])
            msgs.append({"role": role, "content": content})
            msgs = msgs[-100:]
            self._conn.execute(
                "UPDATE sessions SET messages = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(msgs), now, session_id),
            )
        self._conn.commit()

    def get_context(self, session_id: str, max_messages: int = 10) -> list[dict]:
        msgs = self.get_messages(session_id)
        return msgs[-max_messages:]

    def delete_session(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def list_sessions(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT session_id, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def cleanup_old(self) -> int:
        cutoff = time.time() - self._session_ttl
        deleted = self._conn.execute(
            "DELETE FROM sessions WHERE updated_at < ?", (cutoff,)
        ).rowcount
        self._conn.execute("DELETE FROM session_summaries WHERE session_id NOT IN (SELECT session_id FROM sessions)")
        self._conn.commit()
        return deleted

    def add_summary(self, session_id: str, summary: str) -> None:
        self._conn.execute(
            "INSERT INTO session_summaries (session_id, summary, created_at) VALUES (?, ?, ?)",
            (session_id, summary, time.time()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
