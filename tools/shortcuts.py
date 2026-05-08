"""Named app shortcuts backed by SQLite — lets Bobby learn 'the usual', 'morning setup', etc."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

_DB_PATH = Path.home() / ".bobby" / "shortcuts.db"

_DEFAULT_SHORTCUTS = {
    "the usual": {
        "apps": ["chrome", "discord", "spotify"],
        "description": "My daily apps — Chrome, Discord, Spotify",
    },
}


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shortcuts (
            name        TEXT PRIMARY KEY,
            apps        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    _seed_defaults(conn)
    return conn


def _seed_defaults(conn: sqlite3.Connection) -> None:
    for name, info in _DEFAULT_SHORTCUTS.items():
        conn.execute(
            "INSERT OR IGNORE INTO shortcuts (name, apps, description, created_at) VALUES (?,?,?,?)",
            (name, json.dumps(info["apps"]), info["description"], _now()),
        )
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_tool(
    name="open_shortcut",
    description=(
        "Open a named shortcut — a saved group of apps. "
        "Example: 'the usual' opens Chrome, Discord, and Spotify. "
        "Use list_shortcuts to see what's saved."
    ),
    parameters={
        "name": {
            "type": "string",
            "description": "Shortcut name (e.g. 'the usual', 'morning setup')",
            "required": True,
        },
    },
)
def open_shortcut(name: str) -> ToolResult:
    name = name.lower().strip()
    with _get_db() as conn:
        row = conn.execute("SELECT apps FROM shortcuts WHERE name = ?", (name,)).fetchone()

    if not row:
        return ToolResult(success=False, message=f"No shortcut named '{name}'. Try list_shortcuts.")

    apps: list[str] = json.loads(row["apps"])
    log.info(f"Opening shortcut '{name}': {apps}")

    # Dispatch each app via open_app
    from tools.os_control import open_app  # avoid circular at module load

    failed = []
    for app in apps:
        result = open_app(app)
        if not result.success:
            failed.append(app)

    if failed:
        return ToolResult(
            success=False,
            message=f"Opened most of '{name}', but failed to launch: {', '.join(failed)}.",
        )
    return ToolResult(success=True, message=f"Opened '{name}': {', '.join(apps)}.")


@register_tool(
    name="save_shortcut",
    description="Save a named shortcut for a group of apps. Replaces any existing shortcut with the same name.",
    parameters={
        "name": {
            "type": "string",
            "description": "Shortcut name (e.g. 'the usual', 'work setup')",
            "required": True,
        },
        "apps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of app names to open (e.g. ['chrome', 'discord', 'spotify'])",
            "required": True,
        },
        "description": {
            "type": "string",
            "description": "Human-readable description of what this shortcut does",
        },
    },
)
def save_shortcut(name: str, apps: list[str], description: str = "") -> ToolResult:
    name = name.lower().strip()
    if not apps:
        return ToolResult(success=False, message="Apps list cannot be empty.")

    with _get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO shortcuts (name, apps, description, created_at) VALUES (?,?,?,?)",
            (name, json.dumps(apps), description, _now()),
        )

    apps_str = ", ".join(apps)
    return ToolResult(success=True, message=f"Saved shortcut '{name}': {apps_str}.")


@register_tool(
    name="list_shortcuts",
    description="List all saved named shortcuts.",
    parameters={},
)
def list_shortcuts() -> ToolResult:
    with _get_db() as conn:
        rows = conn.execute("SELECT name, apps, description FROM shortcuts ORDER BY name").fetchall()

    if not rows:
        return ToolResult(success=True, message="No shortcuts saved yet.")

    lines = []
    for row in rows:
        apps = json.loads(row["apps"])
        desc = f" — {row['description']}" if row["description"] else ""
        lines.append(f"• {row['name']}: {', '.join(apps)}{desc}")

    return ToolResult(success=True, message="Saved shortcuts:\n" + "\n".join(lines))


@register_tool(
    name="delete_shortcut",
    description="Delete a named shortcut.",
    parameters={
        "name": {
            "type": "string",
            "description": "Shortcut name to delete",
            "required": True,
        },
    },
)
def delete_shortcut(name: str) -> ToolResult:
    name = name.lower().strip()
    with _get_db() as conn:
        cursor = conn.execute("DELETE FROM shortcuts WHERE name = ?", (name,))

    if cursor.rowcount == 0:
        return ToolResult(success=False, message=f"No shortcut named '{name}'.")

    return ToolResult(success=True, message=f"Deleted shortcut '{name}'.")
