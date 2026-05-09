import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.tool_result import ToolResult
from tools.registry import register_tool

_MEDIA_KEYS = {
    "play_pause": "play/pause media",
    "next": "next track",
    "previous": "previous track",
    "stop": "stop media",
}


@register_tool(
    name="system_media",
    description=(
        "Control system-level media playback using hardware media keys. "
        "Works with any media player (Spotify, YouTube, VLC, etc.). "
        "Use for play/pause, skip, go back, or stop."
    ),
    parameters={
        "action": {
            "type": "string",
            "enum": ["play_pause", "next", "previous", "stop"],
            "description": "Media action: play_pause, next, previous, or stop",
            "required": True,
        },
    },
)
def system_media(action: str) -> ToolResult:
    key = _MEDIA_KEYS.get(action)
    if not key:
        return ToolResult(success=False, message=f"Unknown media action: {action}")
    import keyboard
    keyboard.send(key)
    return ToolResult(success=True, message=f"Sent {action} media key.")


@register_tool(
    name="get_clipboard",
    description=(
        "Read the current contents of the Windows clipboard. "
        "Use when the user asks 'what's in my clipboard?' or "
        "'read what I just copied'."
    ),
    parameters={},
)
def get_clipboard() -> ToolResult:
    try:
        if sys.platform == "win32":
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        else:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            text = result.stdout.rstrip("\n")
    except Exception as e:
        return ToolResult(success=False, message=f"Could not read clipboard: {e}")

    preview = text[:200]
    suffix = "..." if len(text) > 200 else ""
    return ToolResult(
        success=True,
        message=f"Clipboard contains: {preview}{suffix}",
        data={"text": text},
    )


@register_tool(
    name="set_clipboard",
    description=(
        "Write text to the Windows clipboard. "
        "Use when the user says 'copy X to clipboard' or "
        "'put X in my clipboard'."
    ),
    parameters={
        "text": {
            "type": "string",
            "description": "Text to place on the clipboard",
            "required": True,
        },
    },
)
def set_clipboard(text: str) -> ToolResult:
    try:
        if sys.platform == "win32":
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
        else:
            subprocess.run(
                ["clip.exe"],
                input=text,
                text=True,
                timeout=5,
                check=True,
            )
    except Exception as e:
        return ToolResult(success=False, message=f"Could not set clipboard: {e}")

    return ToolResult(success=True, message="Clipboard updated.")


@register_tool(
    name="take_screenshot",
    description=(
        "Capture a screenshot of the full desktop (all monitors). "
        "Saves to ~/Pictures/Bobby/. "
        "Use when the user says 'take a screenshot', 'capture my screen', or 'screenshot this'."
    ),
    parameters={
        "filename": {
            "type": "string",
            "description": "Optional filename (without extension). Defaults to a timestamp.",
            "required": False,
        },
    },
)
def take_screenshot(filename: str = "") -> ToolResult:
    try:
        import mss
        import mss.tools

        save_dir = Path.home() / "Pictures" / "Bobby"
        save_dir.mkdir(parents=True, exist_ok=True)

        name = filename.strip() or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if not name.endswith(".png"):
            name += ".png"
        out_path = save_dir / name

        with mss.mss() as sct:
            sct.shot(mon=0, output=str(out_path))

    except Exception as e:
        return ToolResult(success=False, message=f"Screenshot failed: {e}")

    return ToolResult(
        success=True,
        message=f"Screenshot saved to {out_path}",
        data={"path": str(out_path)},
    )
