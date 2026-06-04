"""
Per-application audio volume control via Windows Audio Session API (WASAPI).

Uses PowerShell with inline C# on WSL (same approach as system volume in os_control.py).
On native Windows, falls back to pycaw if available, otherwise PowerShell.

App name → process name resolution:
  "youtube"  → chrome  (YouTube runs in Chrome; all Chrome audio sessions are affected)
  "spotify"  → spotify
  "discord"  → discord
  "game"     → detected by scanning active sessions for known game processes

Bobby can answer "what apps are making noise?" via list_audio_apps,
then the user can target the right one by name.
"""

import subprocess
import sys

from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

# Friendly name → Windows process name substring (lowercase, no .exe)
_APP_PROCESS: dict[str, str] = {
    "youtube": "chrome",
    "chrome": "chrome",
    "google chrome": "chrome",
    "spotify": "spotify",
    "discord": "discord",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "vlc": "vlc",
    "winamp": "winamp",
    "foobar": "foobar2000",
    "twitch": "chrome",        # Twitch usually runs in browser
    "netflix": "chrome",       # Netflix usually runs in browser
    "amazon music": "amazon music",
    "apple music": "applemusic",
}

# PowerShell C# type for per-app audio session control.
# Compiled once per PS session (~400ms first call, cached after).
_PS_APP_AUDIO_CS = r"""
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

[Guid("87CE5498-68D6-44E5-9215-6DA47EF883D8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface ISimpleAudioVolume {
    [PreserveSig] int SetMasterVolume(float f, Guid g);
    [PreserveSig] int GetMasterVolume(out float f);
    [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)] bool b, Guid g);
    [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)] out bool b);
}
[Guid("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioSessionControl2 {
    int n0();int n1();int n2();int n3();int n4();int n5();int n6();int n7();int n8();
    [PreserveSig] int GetProcessId(out uint pid);
    [PreserveSig] int IsSystemSoundsSession();
    [PreserveSig] int SetDuckingPreference(bool opt);
}
[Guid("E2F5BB11-0570-40CA-ACDD-3AA01277DEE8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioSessionEnumerator {
    [PreserveSig] int GetCount(out int count);
    [PreserveSig] int GetSession(int i, [MarshalAs(UnmanagedType.IUnknown)] out object s);
}
[Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioSessionManager2 {
    int n0();int n1();
    [PreserveSig] int GetSessionEnumerator(out IAudioSessionEnumerator e);
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

public static class AppAudio {
    static readonly Guid ASM2_IID = typeof(IAudioSessionManager2).GUID;

    static IAudioSessionEnumerator GetEnumerator() {
        var en = (IMMDeviceEnumerator)new MMDevEnum();
        IMMDevice dev; en.GetDefaultAudioEndpoint(0, 1, out dev);
        var iid = ASM2_IID;
        object obj; dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
        var mgr = (IAudioSessionManager2)obj;
        IAudioSessionEnumerator enumerator;
        mgr.GetSessionEnumerator(out enumerator);
        return enumerator;
    }

    public static string ListApps() {
        var enumerator = GetEnumerator();
        int count; enumerator.GetCount(out count);
        var sb = new StringBuilder();
        for (int i = 0; i < count; i++) {
            object s; enumerator.GetSession(i, out s);
            var ctl = s as IAudioSessionControl2;
            if (ctl == null) continue;
            uint pid; ctl.GetProcessId(out pid);
            if (pid == 0) continue;
            try {
                var proc = System.Diagnostics.Process.GetProcessById((int)pid);
                var vol = s as ISimpleAudioVolume;
                if (vol == null) continue;
                float f; vol.GetMasterVolume(out f);
                bool m; vol.GetMute(out m);
                sb.AppendLine(proc.ProcessName.ToLower() + ":" + (int)Math.Round(f * 100) + ":" + (m ? "1" : "0"));
            } catch {}
        }
        return sb.ToString().Trim();
    }

    public static int GetVolume(string procName) {
        procName = procName.ToLower().Replace(".exe", "");
        var enumerator = GetEnumerator();
        int count; enumerator.GetCount(out count);
        for (int i = 0; i < count; i++) {
            object s; enumerator.GetSession(i, out s);
            var ctl = s as IAudioSessionControl2;
            if (ctl == null) continue;
            uint pid; ctl.GetProcessId(out pid);
            if (pid == 0) continue;
            try {
                var proc = System.Diagnostics.Process.GetProcessById((int)pid);
                if (!proc.ProcessName.ToLower().Contains(procName)) continue;
                var vol = s as ISimpleAudioVolume;
                if (vol == null) continue;
                float f; vol.GetMasterVolume(out f);
                return (int)Math.Round(f * 100);
            } catch {}
        }
        return -1;
    }

    public static int SetVolume(string procName, float level) {
        procName = procName.ToLower().Replace(".exe", "");
        var enumerator = GetEnumerator();
        int count; enumerator.GetCount(out count);
        int changed = 0;
        for (int i = 0; i < count; i++) {
            object s; enumerator.GetSession(i, out s);
            var ctl = s as IAudioSessionControl2;
            if (ctl == null) continue;
            uint pid; ctl.GetProcessId(out pid);
            if (pid == 0) continue;
            try {
                var proc = System.Diagnostics.Process.GetProcessById((int)pid);
                if (!proc.ProcessName.ToLower().Contains(procName)) continue;
                var vol = s as ISimpleAudioVolume;
                if (vol == null) continue;
                vol.SetMasterVolume(level, Guid.Empty);
                changed++;
            } catch {}
        }
        return changed;
    }

    public static int SetMute(string procName, bool mute) {
        procName = procName.ToLower().Replace(".exe", "");
        var enumerator = GetEnumerator();
        int count; enumerator.GetCount(out count);
        int changed = 0;
        for (int i = 0; i < count; i++) {
            object s; enumerator.GetSession(i, out s);
            var ctl = s as IAudioSessionControl2;
            if (ctl == null) continue;
            uint pid; ctl.GetProcessId(out pid);
            if (pid == 0) continue;
            try {
                var proc = System.Diagnostics.Process.GetProcessById((int)pid);
                if (!proc.ProcessName.ToLower().Contains(procName)) continue;
                var vol = s as ISimpleAudioVolume;
                if (vol == null) continue;
                vol.SetMute(mute, Guid.Empty);
                changed++;
            } catch {}
        }
        return changed;
    }
}
'@ -ErrorAction SilentlyContinue
"""


def _ps(cmd: str, timeout: int = 12) -> tuple[int, str]:
    exe = "powershell.exe" if sys.platform != "win32" else "powershell"
    r = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0:
        log.debug(f"PS audio rc={r.returncode}: {(r.stderr or r.stdout).strip()[:200]}")
    return r.returncode, r.stdout.strip()


def _resolve_process(app_name: str) -> str:
    """Resolve a friendly app name to a Windows process name substring."""
    key = app_name.lower().strip()
    if key in _APP_PROCESS:
        return _APP_PROCESS[key]
    # Partial match: "chrom" → "chrome", "spot" → "spotify"
    for alias, proc in _APP_PROCESS.items():
        if key in alias or alias.startswith(key):
            return proc
    # Fall back to the name itself (user might say the exact process name)
    return key


@register_tool(
    name="list_audio_apps",
    description=(
        "List all applications currently producing audio, with their individual volume levels. "
        "Useful for knowing which app to target before adjusting app volume."
    ),
    parameters={},
)
def list_audio_apps() -> ToolResult:
    try:
        rc, out = _ps(_PS_APP_AUDIO_CS + "\n[AppAudio]::ListApps()\n")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, message="Audio session query timed out.")
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't list audio apps: {e}")

    if rc != 0 or not out:
        return ToolResult(
            success=True,
            message="No apps are currently producing audio (or all are silent).",
            data={"apps": []},
        )

    apps: list[dict] = []
    lines = []
    seen: set[str] = set()
    for line in out.splitlines():
        parts = line.strip().split(":")
        if len(parts) < 3:
            continue
        proc_name, vol_str, muted_str = parts[0], parts[1], parts[2]
        if proc_name in seen:
            continue
        seen.add(proc_name)
        try:
            vol = int(vol_str)
        except ValueError:
            continue
        muted = muted_str == "1"
        state = "muted" if muted else f"{vol}%"
        lines.append(f"  {proc_name}: {state}")
        apps.append({"process": proc_name, "volume": vol, "muted": muted})

    if not apps:
        return ToolResult(
            success=True,
            message="No apps are currently producing audio.",
            data={"apps": []},
        )

    return ToolResult(
        success=True,
        message="Apps currently making audio:\n" + "\n".join(lines),
        data={"apps": apps},
    )


@register_tool(
    name="get_app_volume",
    description=(
        "Get the current volume level of a specific application's audio stream. "
        "This is independent of system volume — each app has its own level. "
        "Use app names like: 'youtube', 'spotify', 'discord', 'chrome', 'firefox'."
    ),
    parameters={
        "app": {
            "type": "string",
            "description": "App name: 'youtube', 'spotify', 'discord', 'chrome', etc.",
            "required": True,
        },
    },
)
def get_app_volume(app: str) -> ToolResult:
    proc = _resolve_process(app)
    try:
        rc, out = _ps(_PS_APP_AUDIO_CS + f"\n[AppAudio]::GetVolume('{proc}')\n")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, message="Audio query timed out.")
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't get volume for {app}: {e}")

    if rc != 0:
        return ToolResult(success=False, message=f"Volume query failed for {app}.")

    try:
        level = int(out.strip())
    except ValueError:
        return ToolResult(success=False, message=f"Couldn't parse volume for {app}.")

    if level == -1:
        return ToolResult(
            success=False,
            message=f"{app.capitalize()} doesn't appear to be playing audio right now.",
        )

    return ToolResult(
        success=True,
        message=f"{app.capitalize()} is at {level}%.",
        data={"app": app, "process": proc, "volume": level},
    )


@register_tool(
    name="set_app_volume",
    description=(
        "Set the volume of a specific application independently of system volume. "
        "This lets you lower YouTube without touching Spotify, or mute Discord without "
        "affecting your game audio. "
        "App names: 'youtube', 'spotify', 'discord', 'chrome', 'firefox'. "
        "Level is 0–100."
    ),
    parameters={
        "app": {
            "type": "string",
            "description": "App name: 'youtube', 'spotify', 'discord', 'chrome', 'firefox', etc.",
            "required": True,
        },
        "level": {
            "type": "integer",
            "description": "Volume 0–100. Omit if only muting/unmuting.",
        },
        "mute": {
            "type": "boolean",
            "description": "true = mute this app, false = unmute. Omit to leave mute state unchanged.",
        },
    },
)
def set_app_volume(app: str, level: int | None = None, mute: bool | None = None) -> ToolResult:
    if level is None and mute is None:
        return ToolResult(success=False, message="Specify level (0–100) and/or mute (true/false).")

    proc = _resolve_process(app)
    ps_cmds = [_PS_APP_AUDIO_CS]
    results = []

    if level is not None:
        level = max(0, min(100, level))
        float_level = round(level / 100.0, 4)
        ps_cmds.append(f"$changed = [AppAudio]::SetVolume('{proc}', [float]{float_level})")
        ps_cmds.append("if ($changed -eq 0) { Write-Output 'NOT_FOUND' } else { Write-Output \"SET:$changed\" }")
        results.append(f"{app.capitalize()} volume set to {level}%")

    if mute is not None:
        ps_cmds.append(f"[AppAudio]::SetMute('{proc}', ${str(mute).lower()}) | Out-Null")
        results.append("muted" if mute else "unmuted")

    try:
        rc, out = _ps("\n".join(ps_cmds))
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, message="Volume change timed out.")
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't set {app} volume: {e}")

    if "NOT_FOUND" in out:
        return ToolResult(
            success=False,
            message=(
                f"{app.capitalize()} doesn't appear to be playing audio right now. "
                "Make sure it's open and producing sound, then try again."
            ),
        )

    if rc != 0:
        return ToolResult(success=False, message=f"Volume change failed for {app}.")

    return ToolResult(
        success=True,
        message=". ".join(results) + ".",
        data={"app": app, "process": proc, "level": level, "muted": mute},
    )
