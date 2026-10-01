"""SQLite: таблицы leads и feedback. База создаётся автоматически."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def db_path() -> Path:
    return Path(os.getenv("DB_PATH") or BASE_DIR / "data" / "bot.sqlite3")


SOURCES = ("bot_flow", "ai_consultant")

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('bot_flow', 'ai_consultant')),
    service TEXT,
    contact TEXT,
    problem_text TEXT,
    agent_summary TEXT,
    missing_info TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    """Безопасно вызывать сколько угодно раз: данные не теряются."""
    conn = _connect()
    try:
        with conn:
            conn.executescript(SCHEMA)
    finally:
        conn.close()


def save_lead(session_id, source, service, contact, problem_text,
              agent_summary=None, missing_info=None) -> int:
    if source not in SOURCES:
        raise ValueError("unknown lead source")
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO leads (session_id, source, service, contact, problem_text,"
                " agent_summary, missing_info, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?)",
                (session_id, source, service, contact, problem_text,
                 agent_summary, missing_info, _now()),
            )
            return cur.lastrowid
    finally:
        conn.close()


def save_feedback(session_id, message_text) -> int:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO feedback (session_id, message_text, created_at) VALUES (?, ?, ?)",
                (session_id, message_text, _now()),
            )
            return cur.lastrowid
    finally:
        conn.close()
