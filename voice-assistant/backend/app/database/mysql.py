"""MySQL connection pool — singleton, thread-safe via DBUtils."""

from __future__ import annotations

import atexit

from dbutils.pooled_db import PooledDB
import pymysql

from app.config import get_settings


_pool: PooledDB | None = None


def _ensure_database() -> None:
    s = get_settings()
    conn = pymysql.connect(
        host=s.mysql_host,
        port=s.mysql_port,
        user=s.mysql_user,
        password=s.mysql_password,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{s.mysql_database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


def get_pool() -> PooledDB:
    global _pool
    if _pool is not None:
        return _pool
    _ensure_database()
    s = get_settings()
    _pool = PooledDB(
        creator=pymysql,
        maxconnections=10,
        mincached=2,
        maxcached=5,
        blocking=True,
        host=s.mysql_host,
        port=s.mysql_port,
        user=s.mysql_user,
        password=s.mysql_password,
        database=s.mysql_database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    return _pool


def get_connection() -> pymysql.connections.Connection:
    return get_pool().connection()


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


atexit.register(close_pool)


def init_tables() -> None:
    conn = get_pool().connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    messages JSON NOT NULL,
                    created_at DOUBLE NOT NULL,
                    updated_at DOUBLE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_summaries (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    summary TEXT NOT NULL,
                    created_at DOUBLE NOT NULL,
                    INDEX idx_session (session_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vector_memory (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    text TEXT NOT NULL,
                    metadata JSON NOT NULL,
                    created_at DOUBLE NOT NULL,
                    INDEX idx_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    user_id VARCHAR(64) NOT NULL,
                    summary TEXT NOT NULL,
                    topics JSON NOT NULL,
                    key_facts JSON NOT NULL,
                    created_at DOUBLE NOT NULL,
                    INDEX idx_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
    finally:
        conn.close()