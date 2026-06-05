"""
OS control tools — open apps, manage windows, system controls, terminal.

pywinauto works well for native Win32 apps.
For Electron apps (VS Code, Discord, Slack), use subprocess to launch
and rely on keyboard shortcuts rather than UI automation.
"""

import os
import shlex
import subprocess
import sys
import time
from difflib import get_close_matches

from core import config
from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

# Default app name → executable mapping.
# Extend without touching code by adding app_aliases: { name: exe } to config.yaml.
APP_MAP: dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "discord": "discord",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "riot": "riotclientservices",
    "riot client": "riotclientservices",
    "spotify": "spotify",
    "notepad": "notepad",
    "explorer": "explorer",
    "file explorer": "explorer",
    "terminal": "wt",
    "windows terminal": "wt",
    "cmd": "cmd",
    "command prompt": "cmd",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "calculator": "calc",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "slack": "slack",
    "zoom": "zoom",
    "obs": "obs64",
    "steam": "steam",
    "obsidian": "obsidian://",
    "notion": "Notion",
    "figma": "figma",
    "cursor": "cursor",
}


_start_menu_cache: dict[str, str] | None = None


def _discover_start_menu_apps() -> dict[str, str]:
    """Scan Windows Start Menu .lnk shortcuts → {lowercase-name: windows-path}.

    Covers both system-wide (ProgramData) and per-user (AppData\\Roaming) dirs.
    Result is cached for the lifetime of the process (rescan requires restart).
    """
    global _start_menu_cache
    if _start_menu_cache is not None:
        return _start_menu_cache

    import glob as _glob

    on_wsl = _is_wsl()
    on_win = sys.platform == "win32"

    if on_wsl:
        dirs = [
            "/mnt/c/ProgramData/Microsoft/Windows/Start Menu/Programs",
            "/mnt/c/Users/*/AppData/Roaming/Microsoft/Windows/Start Menu/Programs",
        ]
    elif on_win:
        dirs = [
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
    else:
        _start_menu_cache = {}
        return {}

    discovered: dict[str, str] = {}
    for pattern in dirs:
        for base in _glob.glob(pattern):
            for root, _, files in os.walk(base):
                for fname in files:
                    if not fname.lower().endswith(".lnk"):
                        continue
                    full = os.path.join(root, fname)
                    key = fname[:-4].lower()  # strip .lnk, normalize to lowercase
                    win_path = full.replace("/mnt/c", "C:").replace("/", "\\") if on_wsl else full
                    discovered[key] = win_path

    _start_menu_cache = discovered
    log.debug(f"Start Menu discovery: {len(discovered)} shortcuts indexed")
    return _start_menu_cache


def _get_app_map() -> dict[str, str]:
    """Return merged app map: Start Menu discoveries < APP_MAP < config overrides."""
    # Start Menu has lowest priority so hardcoded entries (e.g. obsidian://) win
    merged = {**_discover_start_menu_apps(), **APP_MAP}
    overrides = config.get("app_aliases", {})
    if isinstance(overrides, dict):
        merged.update({k.lower(): v for k, v in overrides.items()})
    return merged


def _resolve_app(name: str, app_map: dict[str, str]) -> str:
    """
    Resolve a natural-language app name to an executable.
    Priority: exact → substring → fuzzy (0.6 cutoff) → passthrough.
    """
    name_lower = name.lower().strip()
    if name_lower in app_map:
        return app_map[name_lower]
    # Substring: "vs" → "vs code", "google" → "google chrome"
    for key, exe in app_map.items():
        if name_lower in key or key.startswith(name_lower):
            return exe
    # Fuzzy: "chorme" → "chrome", "discrod" → "discord"
    matches = get_close_matches(name_lower, app_map.keys(), n=1, cutoff=0.6)
    if matches:
        return app_map[matches[0]]
    return name  # unknown app — try the name directly


# Commands that require explicit user confirmation before executing.
# This list is also the source of truth for the safety test.
DANGEROUS_PATTERNS = [
    "rm -rf",
    "rm -r",
    "del /f",
    "del /s",
    "format ",
    "reg delete",
    "reg del",
    "shutdown /f",
    "shutdown /r",  # restart
    "shutdown /s",  # shutdown
    "shutdown /l",  # logoff
    "shutdown -f",
    "rmdir /s",
    "rd /s",
    "mkfs",
    "dd if=",
    "taskkill /f",
    ":(){:|:&};:",  # fork bomb
]


def _is_wsl() -> bool:
    """Detect if running inside WSL (Windows Subsystem for Linux)."""
    if sys.platform == "win32":
        return False
    try:
        return "microsoft" in os.uname().release.lower()
    except AttributeError:
        return False


def _is_dangerous(command: str) -> bool:
    cmd_lower = command.lower().strip()
    return any(pattern in cmd_lower for pattern in DANGEROUS_PATTERNS)


@register_tool(
    name="open_app",
    description="Open an application by name. Use admin=true for apps that need elevated privileges.",
    parameters={
        "name": {
            "type": "string",
            "description": "App name (e.g. 'chrome', 'discord', 'vscode', 'riot client')",
            "required": True,
        },
        "admin": {
            "type": "boolean",
            "description": "Whether to launch with admin/elevated privileges",
        },
    },
)
def open_app(name: str, admin: bool = False) -> ToolResult:
    app_map = _get_app_map()
    executable = _resolve_app(name, app_map)

    try:
        on_windows = sys.platform == "win32"
        on_wsl = _is_wsl()

        if admin:
            if on_windows:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, None, None, 1)
            elif on_wsl:
                # PowerShell can elevate from WSL; ShellExecuteW is Windows-only
                subprocess.Popen(
                    f'powershell.exe -Command "Start-Process \'{executable}\' -Verb RunAs"',
                    shell=True,
                )
            else:
                subprocess.Popen(["sudo", executable])
        elif on_windows or on_wsl:
            # cmd.exe 'start' searches Windows App Paths registry — needed for apps like
            # Chrome and Spotify that aren't in PATH. Works on both native Windows and WSL.
            subprocess.Popen(f'cmd.exe /c start "" "{executable}"', shell=True)
        else:
            subprocess.Popen(executable, shell=True)

        label = f"{name} (admin)" if admin else name
        log.info(f"Opened: {label}")
        return ToolResult(success=True, message=f"Opened {label}.")
    except Exception as e:
        log.error(f"Failed to open {name}: {e}")
        return ToolResult(success=False, message=f"Couldn't open {name}: {e}")


@register_tool(
    name="confirm_destructive_command",
    description="Ask the user to confirm before running a potentially destructive terminal command.",
    parameters={
        "command": {
            "type": "string",
            "description": "The command the user wants to run",
            "required": True,
        },
        "reason": {
            "type": "string",
            "description": "Why this command is potentially destructive",
        },
    },
)
def confirm_destructive_command(command: str, reason: str = "") -> ToolResult:
    # This tool signals Bobby to ask the user — actual confirmation happens in the pipeline
    return ToolResult(
        success=True,
        message=f"Confirmation required before running: `{command}`. {reason}".strip(),
        data={"requires_confirmation": True, "command": command},
    )


@register_tool(
    name="execute_terminal",
    description="Run a terminal command. Dangerous commands (rm, del, format, etc.) will always require confirmation first.",
    parameters={
        "command": {
            "type": "string",
            "description": "Shell command to execute",
            "required": True,
        },
        "silent": {
            "type": "boolean",
            "description": "If true, run silently and return output. If false, open a visible terminal window.",
        },
    },
)
def execute_terminal(command: str, silent: bool = False, confirmed: bool = False) -> ToolResult:
    # confirmed=True is set by the pipeline after receiving explicit voice confirmation.
    # It is NOT in the tool schema — Claude never sets it; only the pipeline does.
    if _is_dangerous(command) and not confirmed:
        return ToolResult(
            success=False,
            message=(
                f"I won't run `{command}` without confirmation. "
                "This command could be destructive. Do you want me to confirm first?"
            ),
            data={"requires_confirmation": True, "command": command},
        )

    try:
        if silent:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip() or result.stderr.strip()
            return ToolResult(
                success=result.returncode == 0,
                message=output or "Command completed.",
                data={"returncode": result.returncode, "output": output},
            )
        else:
            # Open in a visible terminal window
            if sys.platform == "win32":
                subprocess.Popen(f'start cmd /k "{command}"', shell=True)
            else:
                subprocess.Popen(["bash", "-c", command])
            return ToolResult(success=True, message=f"Running: {command}")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, message="Command timed out after 30 seconds.")
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to run command: {e}")


# PowerShell C# that calls Windows Audio Session API (WASAPI) from WSL.
# Compiles inline — ~500ms first call, cached by PowerShell for the session.
_PS_AUDIO_CS = r"""Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {
    int n0();int n1();int n2();int n3();
    [PreserveSig] int SetMasterVolumeLevelScalar(float f, Guid g);
    int n5();
    [PreserveSig] int GetMasterVolumeLevelScalar(out float f);
    int n7();int n8();int n9();int n10();
    [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)] bool b, Guid g);
    [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)] out bool b);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {
    [PreserveSig] int Activate(ref Guid iid, uint ctx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object v);
}
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {
    int n0(int a, uint b, [MarshalAs(UnmanagedType.IUnknown)] out object c);
    [PreserveSig] int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice dev);
}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
public class MMDevEnum {}
public static class AudioCtrl {
    static readonly Guid AEV_IID = typeof(IAudioEndpointVolume).GUID;
    static IAudioEndpointVolume GetAEV() {
        var en = (IMMDeviceEnumerator)new MMDevEnum();
        IMMDevice dev; en.GetDefaultAudioEndpoint(0, 1, out dev);
        var iid = AEV_IID;
        object obj; dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
        return (IAudioEndpointVolume)obj;
    }
    public static int GetLevel() { var v=GetAEV(); float f; v.GetMasterVolumeLevelScalar(out f); return (int)Math.Round(f*100); }
    public static void SetLevel(float s) { GetAEV().SetMasterVolumeLevelScalar(s, Guid.Empty); }
    public static bool GetMuted() { var v=GetAEV(); bool m; v.GetMute(out m); return m; }
    public static void SetMuted(bool m) { GetAEV().SetMute(m, Guid.Empty); }
}
'@
"""


def _ps_run(cmd: str) -> tuple[int, str]:
    exe = "powershell.exe" if sys.platform != "win32" else "powershell"
    r = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode != 0:
        log.warning(f"PowerShell failed (rc={r.returncode}): {(r.stderr or r.stdout).strip()[:300]}")
    return r.returncode, r.stdout.strip()


def _pycaw_interface():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


@register_tool(
    name="get_volume",
    description="Get the current system volume (0–100) and whether it is muted.",
    parameters={},
)
def get_volume() -> ToolResult:
    try:
        if sys.platform == "win32":
            vol = _pycaw_interface()
            level = int(round(vol.GetMasterVolumeLevelScalar() * 100))
            muted = bool(vol.GetMute())
        else:
            rc, out = _ps_run(_PS_AUDIO_CS + "[AudioCtrl]::GetLevel()\n[AudioCtrl]::GetMuted()")
            if rc != 0:
                return ToolResult(success=False, message="Couldn't read volume.")
            lines = out.splitlines()
            level = int(lines[0]) if lines else -1
            muted = len(lines) > 1 and lines[1].strip().lower() == "true"

        state = "muted" if muted else f"at {level}%"
        return ToolResult(success=True, message=f"Volume is {state}.", data={"level": level, "muted": muted})
    except Exception as e:
        log.error(f"get_volume failed: {e}")
        return ToolResult(success=False, message=f"Couldn't read volume: {e}")


@register_tool(
    name="set_volume",
    description=(
        "Set system volume (0–100) and/or mute/unmute. "
        "Specify level, mute, or both. Examples: set to 50, mute it, unmute and set to 30."
    ),
    parameters={
        "level": {
            "type": "integer",
            "description": "Volume 0–100. Omit to leave the level unchanged.",
        },
        "mute": {
            "type": "boolean",
            "description": "true = mute, false = unmute. Omit to leave mute state unchanged.",
        },
    },
)
def set_volume(level: int | None = None, mute: bool | None = None) -> ToolResult:
    if level is None and mute is None:
        return ToolResult(success=False, message="Specify level (0–100) and/or mute (true/false).")
    try:
        if sys.platform == "win32":
            vol = _pycaw_interface()
            if level is not None:
                vol.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100.0)), None)
            if mute is not None:
                vol.SetMute(mute, None)
        else:
            ps_cmds = [_PS_AUDIO_CS]
            if level is not None:
                ps_cmds.append(f"[AudioCtrl]::SetLevel([float]{max(0.0, min(1.0, level / 100.0))})")
            if mute is not None:
                ps_cmds.append(f"[AudioCtrl]::SetMuted({'$true' if mute else '$false'})")
            rc, out = _ps_run("\n".join(ps_cmds))
            if rc != 0:
                return ToolResult(success=False, message=f"Volume change failed.")

        parts = []
        if level is not None:
            parts.append(f"volume set to {level}%")
        if mute is not None:
            parts.append("muted" if mute else "unmuted")
        return ToolResult(success=True, message=", ".join(parts).capitalize() + ".")
    except Exception as e:
        log.error(f"set_volume failed: {e}")
        return ToolResult(success=False, message=f"Couldn't change volume: {e}")


# Window action → keyboard shortcut mapping (Windows built-ins, no extra deps)
_WINDOW_KEYS: dict[str, str] = {
    "snap_left":    "windows+left",
    "snap_right":   "windows+right",
    "maximize":     "windows+up",
    "minimize":     "windows+down",
    "close":        "alt+f4",
    "show_desktop": "windows+d",
    "fullscreen":   "f11",
}


@register_tool(
    name="manage_window",
    description=(
        "Snap, resize, focus, minimize, or close windows. "
        "Actions: snap_left, snap_right, maximize, minimize, close, fullscreen, show_desktop, focus."
    ),
    parameters={
        "action": {
            "type": "string",
            "description": "snap_left | snap_right | maximize | minimize | close | fullscreen | show_desktop | focus",
            "required": True,
        },
        "app_name": {
            "type": "string",
            "description": "App name to bring to focus (only used with the 'focus' action)",
        },
    },
)
def manage_window(action: str, app_name: str = "") -> ToolResult:
    if action in _WINDOW_KEYS:
        try:
            import keyboard
            keyboard.send(_WINDOW_KEYS[action])
            label = action.replace("_", " ")
            return ToolResult(success=True, message=f"Window {label}.")
        except Exception as e:
            return ToolResult(success=False, message=f"Couldn't {action}: {e}")

    if action == "focus":
        if not app_name:
            return ToolResult(success=False, message="Provide an app_name to focus.")
        try:
            if sys.platform == "win32":
                import win32gui

                def _enum_cb(hwnd: int, found: list) -> None:
                    if win32gui.IsWindowVisible(hwnd) and app_name.lower() in win32gui.GetWindowText(hwnd).lower():
                        found.append(hwnd)

                found: list[int] = []
                win32gui.EnumWindows(_enum_cb, found)
                if not found:
                    return ToolResult(success=False, message=f"No visible window matching '{app_name}'.")
                win32gui.SetForegroundWindow(found[0])
                return ToolResult(success=True, message=f"Focused {app_name}.")
            else:
                # WSL / Linux: route through PowerShell wscript.shell
                ps = (
                    f"$p = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{app_name}*'}} "
                    f"| Select-Object -First 1; "
                    f"if ($p) {{ $ws = New-Object -ComObject wscript.shell; $ws.AppActivate($p.Id) }}"
                )
                subprocess.Popen(f'powershell.exe -Command "{ps}"', shell=True)
                return ToolResult(success=True, message=f"Switched to {app_name}.")
        except Exception as e:
            return ToolResult(success=False, message=f"Couldn't focus {app_name}: {e}")

    return ToolResult(success=False, message=f"Unknown window action: '{action}'.")


@register_tool(
    name="get_active_window",
    description="Get the title of the currently focused window.",
    parameters={},
)
def get_active_window() -> ToolResult:
    try:
        if sys.platform == "win32":
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            return ToolResult(success=True, message=title or "(no title)", data={"title": title})
        else:
            result = subprocess.run(
                ['powershell.exe', '-Command',
                 'Add-Type -AssemblyName System.Windows.Forms; '
                 '[System.Windows.Forms.Form]::ActiveForm.Text'],
                capture_output=True, text=True, timeout=5,
            )
            title = result.stdout.strip()
            return ToolResult(success=True, message=title or "(unknown)", data={"title": title})
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't get active window: {e}")


@register_tool(
    name="list_running_apps",
    description=(
        "List apps currently running on Windows. "
        "Use after open_app to verify a launch succeeded, or when the user asks what's open. "
        "Pass a filter to check for a specific app (e.g. 'obsidian', 'chrome')."
    ),
    parameters={
        "filter": {
            "type": "string",
            "description": "Optional partial name to filter by (case-insensitive). Leave empty to list all visible apps.",
        },
    },
)
def list_running_apps(filter: str = "") -> ToolResult:
    try:
        if filter:
            safe = filter.replace("'", "").replace('"', "")[:64]
            ps = (
                f"$p = Get-Process | Where-Object {{ $_.Name -like '*{safe}*' }}; "
                f"if ($p) {{ "
                f"  $p | Select-Object Name, Id, @{{Name='Window';Expression={{$_.MainWindowTitle}}}} "
                f"  | Format-Table -AutoSize | Out-String "
                f"}} else {{ 'not running' }}"
            )
        else:
            ps = (
                "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } "
                "| Select-Object Name, @{Name='Window';Expression={$_.MainWindowTitle}} "
                "| Sort-Object Name | Format-Table -AutoSize | Out-String"
            )
        rc, out = _ps_run(ps)
        text = out.strip()
        if not text or text.lower() == "not running":
            label = f"'{filter}' is not running." if filter else "No visible apps found."
            return ToolResult(success=True, message=label, data={"running": False})
        return ToolResult(success=True, message=text, data={"running": True})
    except Exception as e:
        log.error(f"list_running_apps failed: {e}")
        return ToolResult(success=False, message=f"Couldn't list running apps: {e}")


@register_tool(
    name="system_power",
    description="Lock, sleep, restart, or shut down the PC. Restart and shutdown require voice confirmation.",
    parameters={
        "action": {
            "type": "string",
            "description": "lock | sleep | restart | shutdown",
            "required": True,
        },
    },
)
def system_power(action: str, confirmed: bool = False) -> ToolResult:
    # confirmed is NOT in the schema — only the pipeline sets it after voice confirmation.
    if action in ("lock", "restart", "shutdown") and not confirmed:
        return ToolResult(
            success=False,
            message=f"I need you to confirm before I {action} your PC. Say yes to continue.",
            data={
                "requires_confirmation": True,
                "command": f"{action} your PC",
                "confirm_and_retry_tool": "system_power",
                "confirm_and_retry_input": {"action": action, "confirmed": True},
            },
        )

    on_windows = sys.platform == "win32"
    on_wsl = _is_wsl()

    try:
        if action == "lock":
            if on_windows:
                import ctypes
                ctypes.windll.user32.LockWorkStation()
            elif on_wsl:
                subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            else:
                return ToolResult(success=False, message="Lock is only supported on Windows.")

        elif action == "sleep":
            if on_windows:
                subprocess.run(
                    "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
                    shell=True, check=True,
                )
            elif on_wsl:
                subprocess.Popen(
                    "powershell.exe -Command \"Add-Type -Assembly System.Windows.Forms; "
                    "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)\"",
                    shell=True,
                )
            else:
                return ToolResult(success=False, message="Sleep is only supported on Windows.")

        elif action == "restart":
            cmd = "shutdown /r /t 0" if (on_windows or on_wsl) else "sudo reboot"
            subprocess.run(cmd, shell=True, check=True)

        elif action == "shutdown":
            cmd = "shutdown /s /t 0" if (on_windows or on_wsl) else "sudo poweroff"
            subprocess.run(cmd, shell=True, check=True)

        else:
            return ToolResult(success=False, message=f"Unknown action: '{action}'.")

        return ToolResult(success=True, message=f"PC {action} initiated.")
    except Exception as e:
        log.error(f"system_power {action} failed: {e}")
        return ToolResult(success=False, message=f"Couldn't {action}: {e}")


@register_tool(
    name="set_brightness",
    description="Set screen brightness (0-100). Works on laptops and monitors with WMI support.",
    parameters={
        "level": {
            "type": "integer",
            "description": "Brightness level 0-100",
            "required": True,
        },
    },
)
def set_brightness(level: int) -> ToolResult:
    level = max(0, min(100, level))
    try:
        ps = (
            f"$mon = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods; "
            f"if ($mon) {{ $mon.WmiSetBrightness(1, {level}) }} "
            f"else {{ Write-Error 'No WMI brightness support' }}"
        )
        result = subprocess.run(
            ["powershell.exe" if (sys.platform != "win32") else "powershell", "-Command", ps],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return ToolResult(success=True, message=f"Brightness set to {level}%.")
        return ToolResult(
            success=False,
            message="Brightness control not supported on this monitor (external monitors usually don't support WMI).",
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't set brightness: {e}")


@register_tool(
    name="type_text",
    description="Type text at the current cursor position, exactly as if you typed it on a keyboard.",
    parameters={
        "text": {
            "type": "string",
            "description": "Text to type",
            "required": True,
        },
        "delay_ms": {
            "type": "integer",
            "description": "Milliseconds between keystrokes (default 0, increase if the target app is slow)",
        },
    },
)
def type_text(text: str, delay_ms: int = 0) -> ToolResult:
    try:
        import keyboard
        keyboard.write(text, delay=delay_ms / 1000.0)
        preview = text[:40] + ("..." if len(text) > 40 else "")
        return ToolResult(success=True, message=f"Typed: {preview!r}")
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't type text: {e}")


@register_tool(
    name="press_keys",
    description="Press a keyboard shortcut or key combination.",
    parameters={
        "keys": {
            "type": "string",
            "description": (
                "Key combo to press. Examples: 'ctrl+c', 'alt+tab', 'windows+d', "
                "'ctrl+shift+esc', 'f5', 'enter', 'escape'"
            ),
            "required": True,
        },
    },
)
def press_keys(keys: str) -> ToolResult:
    try:
        import keyboard
        keyboard.send(keys)
        return ToolResult(success=True, message=f"Pressed {keys}.")
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't press {keys!r}: {e}")
