"""Phase 11C — Personality Profile scaffold.

build_personality_profile() and update_personality_profile() synthesize a
personality profile from vault notes using Claude, then write it to BOBBY_PROFILE.md.

The profile is loaded at pipeline startup and injected as a third system block
in every think() call (~1,000 token budget).

Gated by config: personality_profile_enabled: true (default: false).
DO NOT run the profile build automatically — Kenny triggers this manually.
"""
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from core import config
from core.logging import get_logger

log = get_logger(__name__)

_GBRAIN_BIN = str(Path.home() / ".bun" / "bin" / "gbrain")
_PROFILE_CACHE: str = ""
_CACHE_LOADED = False


def _enabled() -> bool:
    return bool(config.get("personality_profile_enabled", False))


def _api_base() -> str:
    host = config.get("obsidian.api_host", "172.18.144.1")
    port = config.get("obsidian.api_port", 27123)
    return f"http://{host}:{port}"


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.get('obsidian.api_key', '')}"}


def _obsidian_enabled() -> bool:
    return bool(config.get("obsidian.enabled", False))


# ── public API ────────────────────────────────────────────────────────────────


def load_profile_context() -> str:
    """Read BOBBY_PROFILE.md from vault and return its content.

    Cached per process — call once at startup and reuse. Returns "" if
    Obsidian is unavailable, the profile doesn't exist, or the feature is
    disabled.
    """
    global _PROFILE_CACHE, _CACHE_LOADED
    if _CACHE_LOADED:
        return _PROFILE_CACHE

    _CACHE_LOADED = True
    if not _enabled() or not _obsidian_enabled():
        return ""

    profile_path = config.get("obsidian.profile_file", "BOBBY_PROFILE.md")
    try:
        r = httpx.get(f"{_api_base()}/vault/{profile_path}", headers=_headers(), timeout=5.0)
        if r.status_code == 200:
            _PROFILE_CACHE = r.text
            log.debug(f"Loaded personality profile ({len(_PROFILE_CACHE)} chars)")
        else:
            log.debug("BOBBY_PROFILE.md not found — run build_personality_profile() to create it")
    except Exception as e:
        log.debug(f"Could not load personality profile: {e}")

    return _PROFILE_CACHE


def build_personality_profile() -> None:
    """Synthesize a full personality profile from vault notes and write BOBBY_PROFILE.md.

    Runs in a background daemon thread. Silent on failure.
    Kenny triggers this manually — never called automatically.
    """
    if not _enabled():
        log.info("Personality profile feature is disabled (set personality_profile_enabled: true)")
        return
    threading.Thread(
        target=_build_profile_worker,
        kwargs={"since_days": None},
        daemon=True,
        name="profile-builder",
    ).start()


def update_personality_profile() -> None:
    """Incrementally refresh the profile using captures from the last 30 days.

    Runs in a background daemon thread. Silent on failure.
    Kenny triggers this manually — never called automatically.
    """
    if not _enabled():
        log.info("Personality profile feature is disabled (set personality_profile_enabled: true)")
        return
    threading.Thread(
        target=_build_profile_worker,
        kwargs={"since_days": 30},
        daemon=True,
        name="profile-updater",
    ).start()


# ── private workers ───────────────────────────────────────────────────────────


def _build_profile_worker(since_days: int | None) -> None:
    """Core build/update logic. Runs in a daemon thread."""
    try:
        notes = _gather_notes(since_days)
        if not notes:
            log.warning("No notes found for personality profile — aborting")
            return

        log.info(f"Building personality profile from {len(notes)} notes...")
        profile_md = _synthesize_profile(notes, since_days)
        _write_profile(profile_md)

        global _PROFILE_CACHE, _CACHE_LOADED
        _PROFILE_CACHE = profile_md
        _CACHE_LOADED = True
        log.info("Personality profile written to BOBBY_PROFILE.md")
    except Exception:
        log.exception("Personality profile build failed")


def _gather_notes(since_days: int | None) -> list[str]:
    """Return a list of note markdown strings to feed into the profile synthesis."""
    note_contents: list[str] = []

    if since_days is not None:
        note_contents.extend(_gather_recent_captures(since_days))
    else:
        note_contents.extend(_gather_via_gbrain("personal belief opinion value decision principle"))
        note_contents.extend(_gather_via_gbrain("mental model framework heuristic insight"))

    return note_contents[:50]  # cap to keep synthesis prompt manageable


def _gather_via_gbrain(query: str, limit: int = 15) -> list[str]:
    """Query gbrain and fetch the full note content for each result."""
    if not _obsidian_enabled():
        return []
    try:
        voyage_key = config.get("gbrain.voyage_api_key", "")
        env_extra = {"VOYAGE_API_KEY": voyage_key} if voyage_key else {}
        import os
        env = {**os.environ, **env_extra}
        result = subprocess.run(
            [_GBRAIN_BIN, "search", query, "--limit", str(limit)],
            capture_output=True, text=True, timeout=15, env=env,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        slugs = _parse_gbrain_slugs(result.stdout)
        return [c for c in (_fetch_note_by_slug(s) for s in slugs) if c]
    except Exception as e:
        log.debug(f"gbrain gather failed for '{query}': {e}")
        return []


def _gather_recent_captures(since_days: int) -> list[str]:
    """Fetch inbox notes captured in the last N days via Obsidian REST API."""
    if not _obsidian_enabled():
        return []
    cutoff = datetime.now() - timedelta(days=since_days)
    inbox = config.get("obsidian.inbox_folder", "Inbox")
    contents: list[str] = []
    try:
        r = httpx.get(f"{_api_base()}/vault/{inbox}/", headers=_headers(), timeout=10.0)
        if r.status_code != 200:
            return []
        files = [f for f in r.json().get("files", []) if f.endswith(".md")]
        for path in files:
            # Inbox filenames: YYYY-MM-DD_HH-MM-SS.md — parse date from stem
            stem = Path(path).stem[:10]
            try:
                note_date = datetime.strptime(stem, "%Y-%m-%d")
                if note_date < cutoff:
                    continue
            except ValueError:
                continue
            content = _fetch_note_direct(path)
            if content:
                contents.append(content)
    except Exception as e:
        log.debug(f"Recent captures gather failed: {e}")
    return contents[:30]


def _parse_gbrain_slugs(output: str) -> list[str]:
    """Extract slug or path identifiers from gbrain CLI output."""
    slugs: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("slug:") or line.startswith("- slug:"):
            slug = line.split("slug:", 1)[-1].strip()
            if slug:
                slugs.append(slug)
    return slugs


def _fetch_note_by_slug(slug: str) -> str:
    """Try to fetch a vault note by converting a gbrain slug to an Obsidian path."""
    # gbrain slugs are typically the vault-relative path without extension
    for ext in ("", ".md"):
        path = f"{slug}{ext}"
        content = _fetch_note_direct(path)
        if content:
            return content
    return ""


def _fetch_note_direct(path: str) -> str:
    """Fetch a vault note's raw markdown via Obsidian REST API."""
    try:
        r = httpx.get(f"{_api_base()}/vault/{path}", headers=_headers(), timeout=5.0)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return ""


def _synthesize_profile(notes: list[str], since_days: int | None) -> str:
    """Call Claude to synthesize a personality profile from the gathered notes."""
    from core import config as cfg
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.require("anthropic_api_key"))
    model = cfg.get("claude_complex_model", "claude-sonnet-4-6")

    notes_text = "\n\n---\n\n".join(notes[:50])
    max_note_chars = 80_000
    if len(notes_text) > max_note_chars:
        notes_text = notes_text[:max_note_chars] + "\n\n[truncated]"

    if since_days is not None:
        existing_profile = _fetch_note_direct(config.get("obsidian.profile_file", "BOBBY_PROFILE.md"))
        task_instruction = (
            f"Below is an existing personality profile and recent captures from the last {since_days} days. "
            "Update the profile to incorporate new insights from the captures. "
            "Keep the same structure. Return the complete updated profile in Markdown."
        )
        if existing_profile:
            notes_text = f"# Existing Profile\n\n{existing_profile}\n\n# New Captures\n\n{notes_text}"
    else:
        task_instruction = (
            "Based on the vault notes below, synthesize a personality profile for the owner of this vault. "
            "The profile will be used by a voice AI assistant (Bobby) to give responses that sound "
            "like the owner — their values, mental models, communication style, and opinions. "
            "Structure it as: Values, Mental Models, Communication Style, Key Opinions, and "
            "Recurring Themes. For each item, cite the source note title. "
            "Keep the total profile under 1,000 tokens. Return valid Markdown."
        )

    prompt = f"{task_instruction}\n\n<notes>\n{notes_text}\n</notes>"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    body = response.content[0].text if response.content else ""
    return (
        f"---\ngenerated: {now}\nnote_count: {len(notes)}\n---\n\n"
        f"# Bobby Personality Profile\n\n{body}\n"
    )


def _write_profile(content: str) -> None:
    """Write the profile markdown to BOBBY_PROFILE.md in the vault."""
    profile_path = config.get("obsidian.profile_file", "BOBBY_PROFILE.md")
    httpx.put(
        f"{_api_base()}/vault/{profile_path}",
        headers={**_headers(), "Content-Type": "text/markdown"},
        content=content.encode(),
        timeout=10.0,
    ).raise_for_status()
