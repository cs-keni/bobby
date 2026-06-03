"""Obsidian vault tools — Phase 11A: capture, read, search."""
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import httpx

from core import config
from core.brain import wrap_external
from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)


def _api_base() -> str:
    host = config.get("obsidian.api_host", "172.18.144.1")
    port = config.get("obsidian.api_port", 27123)
    return f"http://{host}:{port}"


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.get('obsidian.api_key', '')}"}


def _enabled() -> bool:
    return bool(config.get("obsidian.enabled", False))


def _not_enabled() -> ToolResult:
    return ToolResult(
        success=False,
        message="Obsidian isn't enabled — set obsidian.enabled: true in config.yaml first.",
    )


def _unreachable(e: Exception) -> ToolResult:
    log.warning(f"Obsidian API error: {e}")
    return ToolResult(
        success=False,
        message="Obsidian isn't running — open it and try again.",
    )


@register_tool(
    name="capture_to_obsidian",
    description="Create a timestamped note in the Obsidian inbox. Use this when the user says 'note this', 'remember this', 'save this to Obsidian', or wants to capture a thought.",
    parameters={
        "text": {"type": "string", "description": "The content to capture as a note", "required": True},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional list of tags to add to the note"},
        "folder": {"type": "string", "description": "Target folder in the vault, defaults to the inbox folder"},
    },
)
def capture_to_obsidian(text: str, tags: list[str] | None = None, folder: str | None = None) -> ToolResult:
    if not _enabled():
        return _not_enabled()

    inbox = folder or config.get("obsidian.inbox_folder", "Inbox")
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".md"
    path = f"{inbox}/{filename}"

    tag_block = ""
    if tags:
        tag_str = "\n".join(f"  - {t}" for t in tags)
        tag_block = f"tags:\n{tag_str}\n"

    content = f"---\ncreated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n{tag_block}---\n\n{text}\n"

    try:
        response = httpx.put(
            f"{_api_base()}/vault/{path}",
            headers={**_headers(), "Content-Type": "text/markdown"},
            content=content.encode(),
            timeout=5.0,
        )
        response.raise_for_status()
    except Exception as e:
        return _unreachable(e)

    _append_to_index(text, path)
    _push_to_gbrain_async(content, f"inbox/{filename.replace('.md', '')}")

    return ToolResult(
        success=True,
        message=f"Captured to Obsidian: {path}",
        data={"path": path},
    )


@register_tool(
    name="read_obsidian_note",
    description="Read the contents of a specific note from the Obsidian vault by its path.",
    parameters={
        "path": {"type": "string", "description": "Vault-relative path to the note, e.g. 'Inbox/my-note.md'", "required": True},
    },
)
def read_obsidian_note(path: str) -> ToolResult:
    if not _enabled():
        return _not_enabled()

    # Path traversal guard
    if ".." in path or path.startswith("/") or "%2e" in path.lower() or "%2f" in path.lower():
        return ToolResult(success=False, message=f"Invalid note path: {path!r}")

    try:
        response = httpx.get(
            f"{_api_base()}/vault/{path}",
            headers=_headers(),
            timeout=5.0,
        )
        if response.status_code == 404:
            return ToolResult(success=False, message=f"Note not found: {path}")
        response.raise_for_status()
    except Exception as e:
        return _unreachable(e)

    content = wrap_external(response.text)
    return ToolResult(
        success=True,
        message=content,
        data={"path": path},
    )


@register_tool(
    name="search_obsidian",
    description="Search the Obsidian vault for notes matching a query string.",
    parameters={
        "query": {"type": "string", "description": "The search query", "required": True},
    },
)
def search_obsidian(query: str) -> ToolResult:
    if not _enabled():
        return _not_enabled()

    try:
        response = httpx.post(
            f"{_api_base()}/search/simple/",
            headers=_headers(),
            params={"query": query},
            timeout=5.0,
        )
        response.raise_for_status()
        results = response.json()
    except Exception as e:
        return _unreachable(e)

    if not results:
        return ToolResult(success=True, message=f"No notes found matching '{query}'.", data={"results": []})

    filenames = [r.get("filename", r) for r in results]
    summary = "\n".join(f"- {f}" for f in filenames[:10])
    return ToolResult(
        success=True,
        message=f"Found {len(results)} note(s) matching '{query}':\n{summary}",
        data={"results": filenames},
    )


@register_tool(
    name="build_vault_index",
    description="Build or rebuild Bobby's vault index (VAULT_INDEX.md). Runs in the background — Bobby will say when it's done.",
    parameters={},
)
def build_vault_index() -> ToolResult:
    if not _enabled():
        return _not_enabled()

    thread = threading.Thread(target=_build_index_worker, daemon=True, name="vault-indexer")
    thread.start()
    return ToolResult(success=True, message="Building your vault index — I'll let you know when it's done.")


def _build_index_worker() -> None:
    from core.notifications import _tts_queue
    try:
        _do_build_index()
        _tts_queue.put("Your vault index is ready.")
    except Exception as e:
        log.error(f"Vault index build failed: {e}", exc_info=True)
        _tts_queue.put("I ran into a problem building your vault index. Check the logs.")


def _do_build_index() -> None:
    """Fetch all vault notes concurrently, extract sections, write VAULT_INDEX.md."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from memory.ingestion import chunk_markdown

    response = httpx.get(f"{_api_base()}/vault/", headers=_headers(), timeout=10.0)
    response.raise_for_status()
    files = sorted(
        f for f in response.json().get("files", [])
        if f.endswith(".md") and "VAULT_INDEX" not in f
    )

    def _fetch(path: str) -> tuple[str, list]:
        try:
            r = httpx.get(f"{_api_base()}/vault/{path}", headers=_headers(), timeout=5.0)
            if r.status_code == 200:
                return path, chunk_markdown(r.text, Path(path).stem)
        except Exception:
            pass
        return path, []

    fetched: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        for path, chunks in pool.map(_fetch, files):
            fetched[path] = chunks

    preview_lines: list[str] = []
    for path in sorted(fetched):
        chunks = fetched[path]
        if not chunks:
            preview_lines.append(f"- `{path}`")
            continue
        intro = chunks[0].content[:120].replace("\n", " ")
        preview_lines.append(f"- `{path}` — {intro}")
        for chunk in chunks[1:]:
            section_preview = chunk.content[:80].replace("\n", " ")
            prefix = "  ##" if chunk.section_level == 2 else "   ###"
            preview_lines.append(f"{prefix} {chunk.title} — {section_preview}")

    total_sections = sum(len(c) for c in fetched.values())
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    index_content = (
        f"# Bobby's Vault Index\n"
        f"Last updated: {now} | Notes: {len(files)} | Sections: {total_sections}\n\n"
        f"## Notes\n\n"
        + "\n".join(preview_lines)
        + "\n\n## Recent Captures\n"
    )

    index_path = config.get("obsidian.index_file", "VAULT_INDEX.md")
    httpx.put(
        f"{_api_base()}/vault/{index_path}",
        headers={**_headers(), "Content-Type": "text/markdown"},
        content=index_content.encode(),
        timeout=10.0,
    ).raise_for_status()


def ensure_daily_note() -> None:
    """Create today's daily note if it doesn't already exist. Non-blocking daemon thread."""
    if not _enabled():
        return
    threading.Thread(target=_ensure_daily_note_worker, daemon=True, name="daily-note").start()


def _ensure_daily_note_worker() -> None:
    try:
        daily_folder = config.get("obsidian.daily_folder", "Areas/Daily")
        today = datetime.now().strftime("%Y-%m-%d")
        path = f"{daily_folder}/{today}.md"

        r = httpx.get(f"{_api_base()}/vault/{path}", headers=_headers(), timeout=5.0)
        if r.status_code == 200:
            log.debug(f"Daily note already exists: {path}")
            return

        content = (
            f"---\ncreated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"type: daily\ntags:\n  - daily\n---\n\n"
            f"# {today}\n\n## Morning\n\n## Notes\n\n## Evening\n"
        )
        httpx.put(
            f"{_api_base()}/vault/{path}",
            headers={**_headers(), "Content-Type": "text/markdown"},
            content=content.encode(),
            timeout=5.0,
        ).raise_for_status()
        log.info(f"Created daily note: {path}")
    except Exception as e:
        log.debug(f"Could not create daily note: {e}")


_GBRAIN_BIN = str(Path.home() / ".bun" / "bin" / "gbrain")


def _push_to_gbrain_async(content: str, slug: str) -> None:
    """Push a captured note to gbrain in a background thread. Non-blocking.

    Failures are logged at DEBUG level and never surfaced to the user —
    gbrain availability must not affect capture reliability.
    """
    if not config.get("gbrain.enabled", False):
        return
    threading.Thread(
        target=_do_push_to_gbrain,
        args=(content, slug),
        daemon=True,
        name="gbrain-push",
    ).start()


def _do_push_to_gbrain(content: str, slug: str) -> None:
    try:
        result = subprocess.run(
            [_GBRAIN_BIN, "capture", "--stdin", "--slug", slug, "--type", "concept", "--quiet"],
            input=content,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            log.debug(f"gbrain capture exit {result.returncode}: {result.stderr[:100]}")
    except Exception as e:
        log.debug(f"gbrain push skipped: {e}")


def _append_to_index(text: str, path: str) -> None:
    """Append one line to ## Recent Captures in VAULT_INDEX.md, if it exists."""
    index_path = config.get("obsidian.index_file", "VAULT_INDEX.md")
    try:
        r = httpx.get(f"{_api_base()}/vault/{index_path}", headers=_headers(), timeout=5.0)
        if r.status_code != 200:
            return  # index doesn't exist yet — skip silently
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        snippet = text[:80].replace("\n", " ")
        new_line = f"- {now} | \"{snippet}\" | {path}\n"
        updated = r.text + new_line
        httpx.put(
            f"{_api_base()}/vault/{index_path}",
            headers={**_headers(), "Content-Type": "text/markdown"},
            content=updated.encode(),
            timeout=5.0,
        ).raise_for_status()
    except Exception as e:
        log.debug(f"Could not update vault index: {e}")
