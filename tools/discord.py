"""
Discord integration — navigate to servers/channels and control voice state.

Navigation: uses the discord:// URL scheme. Discord must be running.
Voice controls: atomic PowerShell script saves foreground window handle,
  focuses Discord, sends the keyboard shortcut, then restores the original
  window — all in ~250ms and invisible to the user.

One-time setup required in config.yaml:
  1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
  2. Right-click your server icon → Copy Server ID → paste as discord.servers.<name>.id
  3. Right-click the channel → Copy Channel ID → paste under .channels.<name>

Example config.yaml block:
  discord:
    default_server: "bubble butt bottom bois"
    default_channel: "sex-havers"
    servers:
      bubble_butt_bottom_bois:
        id: "123456789012345678"
        channels:
          sex_havers: "987654321098765432"
          general: "111222333444555666"

For screen share: Discord has no built-in keyboard shortcut for this.
Set a custom global keybind in Discord Settings → Keybinds → "Toggle Screenshare",
then add it to config.yaml as discord.screenshare_keybind (e.g. "ctrl+shift+s").
Bobby will trigger it via the same focus-switch mechanism.
"""

import subprocess
import sys

from core import config
from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

# WScript.Shell SendKeys notation for Discord keyboard shortcuts
_VOICE_HOTKEYS: dict[str, str] = {
    "mute":     "^+m",   # Ctrl+Shift+M
    "unmute":   "^+m",   # same key — it's a toggle
    "deafen":   "^+d",   # Ctrl+Shift+D
    "undeafen": "^+d",   # same key — it's a toggle
}

# Inline C# type definition for GetForegroundWindow / SetForegroundWindow.
# Compiled by PowerShell on first use; subsequent calls in the same PS session
# hit the Add-Type cache. Using -ErrorAction SilentlyContinue so re-runs in
# tests don't fail on "type already defined".
_PS_WIN32_FOCUS = r"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class BobbyWin32 {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
"@ -ErrorAction SilentlyContinue
"""


def _ps(cmd: str, timeout: int = 6) -> tuple[int, str]:
    """Run a PowerShell command, return (returncode, stdout)."""
    exe = "powershell.exe" if sys.platform != "win32" else "powershell"
    r = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0:
        log.debug(f"PowerShell rc={r.returncode}: {(r.stderr or r.stdout).strip()[:200]}")
    return r.returncode, r.stdout.strip()


def _normalize_name(name: str) -> str:
    """Lowercase + underscores — matches config.yaml key convention."""
    return name.lower().strip().replace(" ", "_").replace("-", "_")


def _resolve_server_channel(
    server: str, channel: str
) -> tuple[str | None, str | None, str]:
    """
    Resolve friendly server+channel names → Discord snowflake IDs from config.
    Returns (guild_id, channel_id, error_message). error_message is "" on success.
    """
    servers_cfg = config.get("discord.servers", {})
    if not servers_cfg:
        return None, None, (
            "No Discord servers configured. Add server and channel IDs to config.yaml "
            "under discord.servers. Enable Developer Mode in Discord to copy IDs "
            "(Settings → Advanced → Developer Mode, then right-click server/channel)."
        )

    server_key = _normalize_name(server)

    # Exact match first, then substring
    matched_key: str | None = None
    if server_key in servers_cfg:
        matched_key = server_key
    else:
        for key in servers_cfg:
            if server_key in key or key in server_key:
                matched_key = key
                break

    if not matched_key:
        available = ", ".join(servers_cfg.keys())
        return None, None, (
            f"Server '{server}' not found in config. "
            f"Known servers: {available}."
        )

    server_cfg = servers_cfg[matched_key]
    guild_id: str | None = str(server_cfg.get("id", "")) or None
    if not guild_id:
        return None, None, f"Server '{matched_key}' is missing an 'id' in config.yaml."

    channels: dict = server_cfg.get("channels", {})
    channel_key = _normalize_name(channel)
    channel_id: str | None = None

    if channel_key in channels:
        channel_id = str(channels[channel_key])
    else:
        for key, cid in channels.items():
            if channel_key in key or key in channel_key:
                channel_id = str(cid)
                break

    if not channel_id:
        available_ch = ", ".join(channels.keys()) if channels else "(none configured)"
        return guild_id, None, (
            f"Channel '{channel}' not found in '{matched_key}'. "
            f"Known channels: {available_ch}."
        )

    return guild_id, channel_id, ""


@register_tool(
    name="discord_navigate",
    description=(
        "Open a specific Discord server and channel in the Discord app. "
        "Call with no arguments to jump to your default server and channel (set in config). "
        "Use friendly names you've configured — e.g. 'bubble butt bottom bois' and 'sex-havers'."
    ),
    parameters={
        "server": {
            "type": "string",
            "description": "Server name as configured in config.yaml. Defaults to discord.default_server.",
        },
        "channel": {
            "type": "string",
            "description": "Channel name as configured in config.yaml. Defaults to discord.default_channel.",
        },
    },
)
def discord_navigate(server: str = "", channel: str = "") -> ToolResult:
    if not server:
        server = config.get("discord.default_server", "")
    if not channel:
        channel = config.get("discord.default_channel", "")

    if not server or not channel:
        return ToolResult(
            success=False,
            message=(
                "No server or channel specified and no defaults set. "
                "Say which server and channel to join, or add discord.default_server and "
                "discord.default_channel to config.yaml."
            ),
        )

    guild_id, channel_id, err = _resolve_server_channel(server, channel)
    if err:
        return ToolResult(success=False, message=err)

    # Snowflake IDs must be 17-20 digit integers. Guards against malformed config.
    if not (guild_id and guild_id.isdigit() and channel_id and channel_id.isdigit()):
        return ToolResult(success=False, message="Discord server/channel IDs in config must be numeric snowflake IDs.")

    url = f"discord://-/channels/{guild_id}/{channel_id}"

    try:
        subprocess.Popen(["cmd.exe", "/c", "start", "", url])
        log.info(f"Discord navigate → {server}/{channel} ({guild_id}/{channel_id})")
        return ToolResult(
            success=True,
            message=f"Opening #{channel} in {server}.",
            data={"guild_id": guild_id, "channel_id": channel_id},
        )
    except Exception as e:
        log.error(f"discord_navigate failed: {e}")
        return ToolResult(success=False, message=f"Couldn't open Discord: {e}")


@register_tool(
    name="discord_voice",
    description=(
        "Control Discord voice while gaming — mute, unmute, deafen, undeafen, "
        "share screen, or stop sharing. "
        "Works without you needing to alt-tab: Bobby briefly switches focus to Discord, "
        "sends the shortcut, and returns focus to your game in under 300ms. "
        "For screen share, set a custom keybind in Discord Settings → Keybinds → "
        "'Toggle Screenshare', then add it to config.yaml as discord.screenshare_keybind."
    ),
    parameters={
        "action": {
            "type": "string",
            "enum": ["mute", "unmute", "deafen", "undeafen", "screen_share"],
            "description": "mute | unmute | deafen | undeafen | screen_share",
            "required": True,
        },
    },
)
def discord_voice(action: str) -> ToolResult:
    action_lower = action.lower().strip()

    if action_lower == "screen_share":
        return _discord_screenshare()

    if action_lower not in _VOICE_HOTKEYS:
        return ToolResult(
            success=False,
            message=f"Unknown action '{action}'. Options: mute, unmute, deafen, undeafen, screen_share.",
        )

    keys = _VOICE_HOTKEYS[action_lower]
    _labels = {"mute": "Muted", "unmute": "Unmuted", "deafen": "Deafened", "undeafen": "Undeafened"}
    label = _labels[action_lower]

    # Single PowerShell call: save handle → focus Discord → send keys → restore.
    # All steps are atomic within one PS invocation (~250ms total).
    ps_cmd = (
        _PS_WIN32_FOCUS
        + "\n$prev = [BobbyWin32]::GetForegroundWindow()\n"
        "$disc = Get-Process discord -ErrorAction SilentlyContinue "
        "| Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1\n"
        "if (-not $disc) { Write-Output 'DISCORD_NOT_RUNNING'; exit }\n"
        "$ws = New-Object -ComObject wscript.shell\n"
        "$ws.AppActivate($disc.Id) | Out-Null\n"
        "Start-Sleep -Milliseconds 150\n"
        f"$ws.SendKeys('{keys}')\n"
        "Start-Sleep -Milliseconds 100\n"
        "[BobbyWin32]::SetForegroundWindow($prev) | Out-Null\n"
        "Write-Output 'OK'\n"
    )

    try:
        rc, out = _ps(ps_cmd, timeout=6)
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, message="Discord voice control timed out.")
    except Exception as e:
        return ToolResult(success=False, message=f"Voice control failed: {e}")

    if "DISCORD_NOT_RUNNING" in out:
        return ToolResult(success=False, message="Discord isn't running — open it first.")

    if rc != 0 or "OK" not in out:
        return ToolResult(
            success=False,
            message="Discord voice control failed. Make sure Discord is open and you're in a voice channel.",
        )

    log.info(f"Discord voice: {action}")
    return ToolResult(success=True, message=f"{label}.")


def _discord_screenshare() -> ToolResult:
    """
    Trigger the user's custom Discord screen share keybind.
    Requires discord.screenshare_keybind set in config.yaml.
    """
    keybind = config.get("discord.screenshare_keybind", "")
    if not keybind:
        return ToolResult(
            success=False,
            message=(
                "Screen share keybind not configured. "
                "In Discord: Settings → Keybinds → Add Keybind → 'Toggle Screenshare'. "
                "Then add 'discord.screenshare_keybind: ctrl+shift+s' (or your chosen key) to config.yaml."
            ),
        )

    # Convert human-readable format to WScript SendKeys notation
    # e.g. "ctrl+shift+s" → "^+s", "ctrl+shift+h" → "^+h"
    sendkeys = _to_sendkeys(keybind)

    ps_cmd = (
        _PS_WIN32_FOCUS
        + "\n$prev = [BobbyWin32]::GetForegroundWindow()\n"
        "$disc = Get-Process discord -ErrorAction SilentlyContinue "
        "| Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1\n"
        "if (-not $disc) { Write-Output 'DISCORD_NOT_RUNNING'; exit }\n"
        "$ws = New-Object -ComObject wscript.shell\n"
        "$ws.AppActivate($disc.Id) | Out-Null\n"
        "Start-Sleep -Milliseconds 150\n"
        f"$ws.SendKeys('{sendkeys}')\n"
        "Start-Sleep -Milliseconds 100\n"
        "[BobbyWin32]::SetForegroundWindow($prev) | Out-Null\n"
        "Write-Output 'OK'\n"
    )

    try:
        rc, out = _ps(ps_cmd, timeout=6)
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, message="Screen share toggle timed out.")
    except Exception as e:
        return ToolResult(success=False, message=f"Screen share toggle failed: {e}")

    if "DISCORD_NOT_RUNNING" in out:
        return ToolResult(success=False, message="Discord isn't running — open it first.")

    if rc != 0 or "OK" not in out:
        return ToolResult(success=False, message="Screen share toggle failed. Is Discord open?")

    log.info("Discord screenshare toggled")
    return ToolResult(success=True, message="Screen share toggled.")


def _to_sendkeys(keybind: str) -> str:
    """
    Convert a human-readable keybind like 'ctrl+shift+s' to WScript.Shell
    SendKeys notation like '^+s'.
    """
    parts = [p.strip().lower() for p in keybind.split("+")]
    result = ""
    for part in parts:
        if part == "ctrl":
            result += "^"
        elif part == "shift":
            result += "+"
        elif part == "alt":
            result += "%"
        else:
            result += part  # literal key character
    return result
