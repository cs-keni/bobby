"""
OS control tools — open apps, manage windows, system controls, terminal.

pywinauto works well for native Win32 apps.
For Electron apps (VS Code, Discord, Slack), use subprocess to launch
and rely on keyboard shortcuts rather than UI automation.
"""

import shlex
import subprocess
import sys

from core import config
from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

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
    "shutdown -f",
    "rmdir /s",
    "rd /s",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",  # fork bomb
]


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
    APP_MAP = {
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
        "terminal": "wt",
        "windows terminal": "wt",
    }

    executable = APP_MAP.get(name.lower(), name)

    try:
        if admin and sys.platform == "win32":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, None, None, 1)
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
def execute_terminal(command: str, silent: bool = False) -> ToolResult:
    if _is_dangerous(command):
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


@register_tool(
    name="set_volume",
    description="Set system volume level or mute/unmute.",
    parameters={
        "level": {
            "type": "integer",
            "description": "Volume level 0-100, or -1 to toggle mute",
        },
    },
)
def set_volume(level: int) -> ToolResult:
    try:
        if sys.platform == "win32":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            if level == -1:
                muted = volume.GetMute()
                volume.SetMute(not muted, None)
                return ToolResult(success=True, message="Muted." if not muted else "Unmuted.")

            scalar = max(0.0, min(1.0, level / 100.0))
            volume.SetMasterVolumeLevelScalar(scalar, None)
            return ToolResult(success=True, message=f"Volume set to {level}%.")
        else:
            return ToolResult(success=False, message="Volume control not yet supported on this platform.")
    except Exception as e:
        log.error(f"Volume control failed: {e}")
        return ToolResult(success=False, message=f"Couldn't change volume: {e}")
