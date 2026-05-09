import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config
from core.logging import get_logger

log = get_logger(__name__)


def _db_path() -> Path:
    raw = config.get("memory_db_path", "~/.bobby/memory.db")
    p = Path(raw).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            timestamp  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_fact(key: str, value: str, description: str = "") -> None:
    with _connect() as conn:
        existing = conn.execute("SELECT created_at FROM facts WHERE key = ?", (key,)).fetchone()
        created_at = existing[0] if existing else _now()
        conn.execute(
            """
            INSERT INTO facts (key, value, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value       = excluded.value,
                description = excluded.description,
                updated_at  = excluded.updated_at
            """,
            (key, value, description, created_at, _now()),
        )


def get_fact(key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM facts WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None


def delete_fact(key: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM facts WHERE key = ?", (key,))
        return cur.rowcount > 0


def list_facts(search: str = "") -> list[dict[str, Any]]:
    with _connect() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT key, value, description, created_at, updated_at FROM facts "
                "WHERE key LIKE ? OR value LIKE ?",
                (pattern, pattern),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT key, value, description, created_at, updated_at FROM facts"
            ).fetchall()
    return [
        {"key": r[0], "value": r[1], "description": r[2], "created_at": r[3], "updated_at": r[4]}
        for r in rows
    ]


def get_memory_context(query: str = "") -> str:
    facts = list_facts(query)
    if not facts:
        return ""

    max_chars = config.get("max_memory_tokens", 4000) * 4
    header = "Bobby's memory about the user:\n"
    lines = [f"[{f['key']}]: {f['value']}" for f in facts]
    body = "\n".join(lines)
    full = header + body

    if len(full) <= max_chars:
        return full

    truncated = full[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > len(header):
        truncated = truncated[:last_newline]
    return truncated


def save_turn(session_id: str, role: str, content: str | list | dict) -> None:
    if not isinstance(content, str):
        content = json.dumps(content)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )


def get_recent_history(session_id: str, max_turns: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, max_turns),
        ).fetchall()

    result = []
    for role, content in reversed(rows):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed = content
        result.append({"role": role, "content": parsed})
    return result
