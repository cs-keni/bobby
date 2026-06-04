"""
File system search and navigation tools.

Searches Windows user folders from WSL or native Windows.
Paths returned are WSL-native (/mnt/c/...). open_file converts to
Windows paths automatically before launching the default application.
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

# Friendly folder name → subdirectory relative to Windows home
_FOLDER_ALIASES: dict[str, str] = {
    "downloads": "Downloads",
    "download": "Downloads",
    "desktop": "Desktop",
    "documents": "Documents",
    "docs": "Documents",
    "pictures": "Pictures",
    "photos": "Pictures",
    "images": "Pictures",
    "videos": "Videos",
    "video": "Videos",
    "music": "Music",
    "home": "",
    "appdata": "AppData",
}

# Friendly type name → set of extensions (lowercase, dot-prefixed)
_TYPE_EXTENSIONS: dict[str, set[str]] = {
    "pdf": {".pdf"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg", ".heic"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "audio": {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma"},
    "document": {".doc", ".docx", ".txt", ".rtf", ".odt", ".pages"},
    "spreadsheet": {".xls", ".xlsx", ".csv", ".ods", ".numbers"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".sh"},
    "exe": {".exe", ".msi", ".bat", ".cmd"},
}


@lru_cache(maxsize=1)
def _win_home() -> Path:
    """
    Return the Windows user home directory as a WSL-compatible Path.
    Cached after first call (subprocess only runs once per process).
    """
    if sys.platform == "win32":
        return Path.home()
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "echo", "%USERPROFILE%"],
            capture_output=True, text=True, timeout=3,
        )
        win_path = result.stdout.strip()  # e.g. C:\Users\keni
        if win_path and "\\" in win_path:
            drive = win_path[0].lower()
            rest = win_path[2:].replace("\\", "/")
            return Path(f"/mnt/{drive}{rest}")
    except Exception as e:
        log.debug(f"_win_home WSL detection failed: {e}")
    return Path.home()


def _resolve_folder(folder: str) -> Path:
    """Resolve a friendly name, alias, or path string to an absolute Path."""
    folder = folder.strip()

    if folder.startswith("~"):
        return Path(str(_win_home()) + folder[1:])

    p = Path(folder)
    if p.is_absolute():
        return p

    key = folder.lower()
    if key in _FOLDER_ALIASES:
        rel = _FOLDER_ALIASES[key]
        return _win_home() / rel if rel else _win_home()

    # Partial match (e.g. "vid" → "videos")
    for alias, rel in _FOLDER_ALIASES.items():
        if key in alias or alias.startswith(key):
            return _win_home() / rel if rel else _win_home()

    # Fall back: treat as subdirectory of Windows home
    return _win_home() / folder


def _to_windows_path(p: Path) -> str:
    """Convert a WSL path to a Windows path string (for cmd.exe start)."""
    s = str(p)
    if s.startswith("/mnt/") and len(s) > 6:
        drive = s[5].upper()
        rest = s[6:].replace("/", "\\")
        return f"{drive}:{rest}"
    return s


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.0f} TB"


def _human_date(ts: float) -> str:
    dt = datetime.fromtimestamp(ts)
    diff = datetime.now() - dt
    if diff.days == 0:
        return "today"
    if diff.days == 1:
        return "yesterday"
    if diff.days < 7:
        return f"{diff.days} days ago"
    return dt.strftime("%b %d, %Y")


@register_tool(
    name="search_files",
    description=(
        "Search for files by name in a folder. "
        "Use friendly folder names: 'downloads', 'desktop', 'documents', 'pictures', 'videos'. "
        "Optionally filter by type (pdf, image, video, audio, document, etc.) or recency. "
        "Returns the top 10 matches with path, size, and last-modified date."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "Filename or partial name to search for (case-insensitive).",
            "required": True,
        },
        "folder": {
            "type": "string",
            "description": (
                "Where to search. Friendly names: 'downloads', 'desktop', 'documents', "
                "'pictures', 'videos'. Defaults to 'downloads'."
            ),
        },
        "file_type": {
            "type": "string",
            "description": (
                "Filter by type: pdf, image, video, audio, document, spreadsheet, "
                "archive, code, exe. Omit to match all types."
            ),
        },
        "newer_than_days": {
            "type": "integer",
            "description": "Only return files modified within this many days (e.g. 7 = last week).",
        },
        "recursive": {
            "type": "boolean",
            "description": "Search subfolders recursively. Defaults to true.",
        },
    },
)
def search_files(
    query: str,
    folder: str = "downloads",
    file_type: str = "",
    newer_than_days: int | None = None,
    recursive: bool = True,
) -> ToolResult:
    search_root = _resolve_folder(folder)

    if not search_root.exists():
        return ToolResult(
            success=False,
            message=f"Folder not found: {search_root}. Check the path or try a different folder name.",
        )

    allowed_exts = _TYPE_EXTENSIONS.get(file_type.lower(), set()) if file_type else set()
    cutoff_ts = (datetime.now() - timedelta(days=newer_than_days)).timestamp() if newer_than_days else None

    query_lower = query.lower()
    matches: list[tuple[float, Path, int]] = []

    try:
        pattern = "**/*" if recursive else "*"
        for p in search_root.glob(pattern):
            if not p.is_file():
                continue
            if query_lower not in p.name.lower():
                continue
            if allowed_exts and p.suffix.lower() not in allowed_exts:
                continue
            try:
                stat = p.stat()
            except OSError:
                continue
            if cutoff_ts and stat.st_mtime < cutoff_ts:
                continue
            matches.append((stat.st_mtime, p, stat.st_size))
    except PermissionError as e:
        return ToolResult(success=False, message=f"Permission denied searching {search_root}: {e}")

    if not matches:
        type_hint = f" ({file_type} files)" if file_type else ""
        age_hint = f" from the last {newer_than_days} days" if newer_than_days else ""
        return ToolResult(
            success=True,
            message=f"No files matching '{query}'{type_hint}{age_hint} found in {folder}.",
            data={"results": [], "total": 0},
        )

    matches.sort(reverse=True)  # newest first
    top = matches[:10]

    lines = [f"Found {len(matches)} file(s) matching '{query}':", ""]
    result_data = []
    for mtime, p, size in top:
        date_str = _human_date(mtime)
        size_str = _human_size(size)
        lines.append(f"  {p.name}  ({size_str}, {date_str})")
        lines.append(f"    {p}")
        result_data.append({
            "name": p.name,
            "path": str(p),
            "size": size,
            "modified": mtime,
        })

    if len(matches) > 10:
        lines.append(f"\n  ... and {len(matches) - 10} more. Try a more specific query to narrow results.")

    return ToolResult(
        success=True,
        message="\n".join(lines),
        data={"results": result_data, "total": len(matches)},
    )


@register_tool(
    name="open_file",
    description=(
        "Open a file with its default application. "
        "Pass the full path returned by search_files or list_folder. "
        "PDFs open in the PDF viewer, images in Photos, videos in the media player, etc."
    ),
    parameters={
        "path": {
            "type": "string",
            "description": "Absolute path to the file (WSL-style /mnt/c/... or Windows C:\\... both accepted).",
            "required": True,
        },
    },
)
def open_file(path: str) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, message=f"File not found: {path}")
    if not p.is_file():
        return ToolResult(success=False, message=f"'{p.name}' is a folder, not a file. Use list_folder to browse it.")

    try:
        if sys.platform == "win32":
            os.startfile(str(p))
        else:
            win_path = _to_windows_path(p)
            subprocess.Popen(f'cmd.exe /c start "" "{win_path}"', shell=True)
        log.info(f"Opened file: {p.name}")
        return ToolResult(success=True, message=f"Opening {p.name}.")
    except Exception as e:
        log.error(f"open_file failed for {p}: {e}")
        return ToolResult(success=False, message=f"Couldn't open {p.name}: {e}")


@register_tool(
    name="list_folder",
    description=(
        "List the contents of a folder — up to 20 items. "
        "Friendly names: 'downloads', 'desktop', 'documents', 'pictures', 'videos'. "
        "Sorted by most recently modified by default."
    ),
    parameters={
        "folder": {
            "type": "string",
            "description": "Folder to list: 'downloads', 'desktop', 'documents', or an absolute path.",
            "required": True,
        },
        "sort_by": {
            "type": "string",
            "description": "'date' (newest first, default) | 'name' (A-Z) | 'size' (largest first).",
        },
    },
)
def list_folder(folder: str, sort_by: str = "date") -> ToolResult:
    target = _resolve_folder(folder)

    if not target.exists():
        return ToolResult(success=False, message=f"Folder not found: {target}.")
    if not target.is_dir():
        return ToolResult(success=False, message=f"'{target.name}' is a file, not a folder.")

    try:
        entries: list[tuple[Path, os.stat_result]] = []
        for p in target.iterdir():
            try:
                entries.append((p, p.stat()))
            except OSError:
                continue
    except PermissionError as e:
        return ToolResult(success=False, message=f"Permission denied: {e}")

    if not entries:
        return ToolResult(success=True, message=f"'{folder}' is empty.", data={"entries": [], "total": 0})

    sort_key = sort_by.lower()
    if sort_key == "name":
        entries.sort(key=lambda x: x[0].name.lower())
    elif sort_key == "size":
        entries.sort(key=lambda x: x[1].st_size, reverse=True)
    else:
        entries.sort(key=lambda x: x[1].st_mtime, reverse=True)

    shown = entries[:20]
    lines = [f"{folder}/ — {len(entries)} item(s)", ""]
    entry_data = []
    for p, stat in shown:
        if p.is_dir():
            lines.append(f"  [{p.name}/]  ({_human_date(stat.st_mtime)})")
        else:
            lines.append(f"  {p.name}  ({_human_size(stat.st_size)}, {_human_date(stat.st_mtime)})")
        entry_data.append({
            "name": p.name,
            "path": str(p),
            "is_dir": p.is_dir(),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        })

    if len(entries) > 20:
        lines.append(f"\n  ... and {len(entries) - 20} more.")

    return ToolResult(
        success=True,
        message="\n".join(lines),
        data={"entries": entry_data, "total": len(entries), "folder": str(target)},
    )
