"""
Discord local IPC/RPC — join voice channels via Discord's Windows named pipe.

One-time setup:
1. discord.com/developers/applications → New Application (name it anything, e.g. "Bobby")
2. OAuth2 → copy Client ID and Client Secret
3. OAuth2 → Redirects → Add Redirect → type: http://127.0.0.1
4. Add to config.yaml:
     discord:
       app_id: "YOUR_CLIENT_ID"
       app_secret: "YOUR_CLIENT_SECRET"

First "join the call": Discord shows a one-time "Bobby wants access" popup.
Click Authorize. Token is cached at ~/.bobby/discord_token.json and auto-refreshed.
"""

import json
import sys
import subprocess
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

from core import config
from core.logging import get_logger
from core.tool_result import ToolResult

log = get_logger(__name__)

TOKEN_CACHE = Path.home() / ".bobby" / "discord_token.json"

# PowerShell helpers shared by both scripts: Write-Frame, Read-Frame, Connect-Pipe.
# Uses System.IO.Pipes.NamedPipeClientStream — available in PS 5.1+ (Windows 10+).
_PS_HELPERS = r"""
function Write-Frame($pipe, [int]$op, $obj) {
    $json  = $obj | ConvertTo-Json -Compress -Depth 10
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $hdr   = New-Object byte[] 8
    [BitConverter]::GetBytes([uint32]$op).CopyTo($hdr, 0)
    [BitConverter]::GetBytes([uint32]$bytes.Length).CopyTo($hdr, 4)
    $pipe.Write($hdr,  0, 8)
    $pipe.Write($bytes, 0, $bytes.Length)
    $pipe.Flush()
}
function Read-Frame($pipe) {
    $hdr = New-Object byte[] 8; $r = 0
    while ($r -lt 8)   { $n = $pipe.Read($hdr, $r, 8 - $r);   if ($n -eq 0) { throw "EOF" }; $r += $n }
    $op  = [BitConverter]::ToUInt32($hdr, 0)
    $len = [BitConverter]::ToUInt32($hdr, 4)
    $dat = New-Object byte[] $len; $r = 0
    while ($r -lt $len) { $n = $pipe.Read($dat, $r, $len - $r); if ($n -eq 0) { throw "EOF" }; $r += $n }
    return @{ op = [int]$op; json = [System.Text.Encoding]::UTF8.GetString($dat) }
}
function Connect-Pipe {
    for ($i = 0; $i -lt 10; $i++) {
        $p = New-Object System.IO.Pipes.NamedPipeClientStream(".", "discord-ipc-$i",
            [System.IO.Pipes.PipeDirection]::InOut)
        try { $p.Connect(500); return $p } catch { }
    }
    return $null
}
"""

_PS_JOIN_BODY = r"""
$pipe = Connect-Pipe
if (-not $pipe) { Write-Output "PIPE_NOT_FOUND"; exit 1 }
try {
    Write-Frame $pipe 0 @{ v = 1; client_id = $cid }
    $r = Read-Frame $pipe
    if (($r.json | ConvertFrom-Json).evt -ne "READY") { Write-Output "HANDSHAKE_FAILED"; exit 1 }

    Write-Frame $pipe 1 @{ cmd = "AUTHENTICATE"; args = @{ access_token = $tok }; nonce = ([guid]::NewGuid().ToString()) }
    $r = Read-Frame $pipe
    $obj = $r.json | ConvertFrom-Json
    if ($obj.evt -eq "ERROR") { Write-Output "AUTH_FAILED:$($obj.data.message)"; exit 1 }

    Write-Frame $pipe 1 @{ cmd = "VOICE_CHANNEL_SELECT"; args = @{ channel_id = $chan }; nonce = ([guid]::NewGuid().ToString()) }
    $r = Read-Frame $pipe
    Write-Output "OK:$($r.json)"
} catch {
    Write-Output "ERROR:$($_.Exception.Message)"
} finally { $pipe.Dispose() }
"""

_PS_AUTH_BODY = r"""
$pipe = Connect-Pipe
if (-not $pipe) { Write-Output "PIPE_NOT_FOUND"; exit 1 }
try {
    Write-Frame $pipe 0 @{ v = 1; client_id = $cid }
    $r = Read-Frame $pipe
    if (($r.json | ConvertFrom-Json).evt -ne "READY") { Write-Output "HANDSHAKE_FAILED"; exit 1 }

    Write-Frame $pipe 1 @{
        cmd   = "AUTHORIZE"
        args  = @{
            client_id = $cid
            scopes    = @("rpc")
        }
        nonce = [guid]::NewGuid().ToString()
    }
    $r   = Read-Frame $pipe
    $obj = $r.json | ConvertFrom-Json
    if ($obj.evt -eq "ERROR") { Write-Output "AUTH_ERROR:$($obj.data.message)"; exit 1 }
    Write-Output "CODE:$($obj.data.code)"
} catch {
    Write-Output "ERROR:$($_.Exception.Message)"
} finally { $pipe.Dispose() }
"""


def _ps(script: str, timeout: int = 15) -> tuple[int, str]:
    exe = "powershell.exe" if sys.platform != "win32" else "powershell"
    r = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def _sq(s: str) -> str:
    """Escape a string for embedding in PowerShell single-quoted literals."""
    return s.replace("'", "''")


def _make_join_script(client_id: str, access_token: str, channel_id: str) -> str:
    return (
        _PS_HELPERS
        + "\n$cid  = '" + _sq(client_id) + "'\n"
        + "$tok  = '" + _sq(access_token) + "'\n"
        + "$chan = '" + _sq(channel_id) + "'\n"
        + _PS_JOIN_BODY
    )


def _make_auth_script(client_id: str) -> str:
    return (
        _PS_HELPERS
        + "\n$cid = '" + _sq(client_id) + "'\n"
        + _PS_AUTH_BODY
    )


def _load_token() -> dict | None:
    try:
        return json.loads(TOKEN_CACHE.read_text())
    except Exception:
        return None


def _save_token(data: dict) -> None:
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE.write_text(json.dumps(data))


def _token_post(params: dict) -> dict | None:
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://discord.com/api/oauth2/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        log.error(f"Discord token HTTP {e.code}: {detail}")
        return None
    except Exception as e:
        log.error(f"Discord token exchange error: {e}")
        return None


def _exchange_code(client_id: str, client_secret: str, code: str) -> dict | None:
    return _token_post({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "http://127.0.0.1",
    })


def _refresh_token(client_id: str, client_secret: str, refresh_token: str) -> dict | None:
    return _token_post({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    })


def _try_join(client_id: str, access_token: str, channel_id: str) -> str:
    """Returns the raw PowerShell output string."""
    _, out = _ps(_make_join_script(client_id, access_token, channel_id), timeout=15)
    return out


def join_voice(channel_id: str, channel_name: str) -> ToolResult:
    """
    Join a Discord voice channel via the local IPC protocol.
    Handles first-time OAuth2 authorization and automatic token refresh.
    """
    client_id = config.get("discord.app_id", "")
    client_secret = config.get("discord.app_secret", "")

    if not client_id or not client_secret:
        return ToolResult(
            success=False,
            message=(
                "Discord auto-join needs a one-time setup — takes about 2 minutes:\n"
                "1. discord.com/developers/applications → New Application\n"
                "2. OAuth2 → copy Client ID and Client Secret\n"
                "3. OAuth2 → Redirects → Add http://127.0.0.1\n"
                "4. Add to config.yaml:\n"
                "     discord:\n"
                "       app_id: \"YOUR_CLIENT_ID\"\n"
                "       app_secret: \"YOUR_CLIENT_SECRET\"\n"
                "Then say 'join the call' — Bobby will ask Discord to authorize once."
            ),
        )

    # Attempt with cached token
    token = _load_token()
    if token and token.get("access_token"):
        out = _try_join(client_id, token["access_token"], channel_id)
        if "OK:" in out:
            log.info(f"Discord RPC: joined #{channel_name}")
            return ToolResult(success=True, message=f"Joined #{channel_name}.")
        if "AUTH_FAILED" in out and token.get("refresh_token"):
            log.info("Discord RPC: token expired, refreshing")
            new_tok = _refresh_token(client_id, client_secret, token["refresh_token"])
            if new_tok and new_tok.get("access_token"):
                _save_token(new_tok)
                out = _try_join(client_id, new_tok["access_token"], channel_id)
                if "OK:" in out:
                    log.info(f"Discord RPC: joined #{channel_name} (refreshed)")
                    return ToolResult(success=True, message=f"Joined #{channel_name}.")

    # First-time: launch AUTHORIZE — Discord shows a one-time popup
    log.info("Discord RPC: starting first-time OAuth2 authorization")
    try:
        _, out = _ps(_make_auth_script(client_id), timeout=70)
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            message="Discord authorization timed out. Look for a Discord popup asking for permission and click Authorize.",
        )

    if "PIPE_NOT_FOUND" in out:
        return ToolResult(success=False, message="Discord isn't running — open it first.")
    if "CODE:" not in out:
        log.warning(f"Discord authorize PS output: {out[:500]!r}")
        return ToolResult(success=False, message=f"Discord authorization failed: {out[:300]}")

    code = out.split("CODE:", 1)[1].strip().splitlines()[0]
    token = _exchange_code(client_id, client_secret, code)
    if not token or not token.get("access_token"):
        return ToolResult(
            success=False,
            message="Got auth code but token exchange failed. Check discord.app_id and discord.app_secret in config.yaml.",
        )

    _save_token(token)
    out = _try_join(client_id, token["access_token"], channel_id)
    if "OK:" in out:
        log.info(f"Discord RPC: joined #{channel_name} (first auth complete)")
        return ToolResult(success=True, message=f"Joined #{channel_name}.")

    return ToolResult(
        success=False,
        message=f"Authorized but voice join failed: {out[:200]}",
    )
