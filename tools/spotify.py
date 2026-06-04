"""
Spotify integration via Spotify Web API (spotipy).

Setup (one-time, ~5 minutes):
  1. Go to https://developer.spotify.com/dashboard
  2. Log in → Create App
     - App name: Bobby (or anything)
     - Redirect URI: http://127.0.0.1:8888/callback  ← exact match required
  3. Copy Client ID and Client Secret
  4. In config.yaml set:
       spotify:
         enabled: true
         client_id: "your_client_id"
         client_secret: "your_client_secret"
  5. Run any Spotify command → Bobby will open the auth URL in Chrome.
     Approve in browser. Token saved to ~/.bobby/spotify_cache automatically.
     All future commands work silently.

Scopes requested:
  user-modify-playback-state  — play, pause, skip, volume
  user-read-playback-state    — read current track/device
  playlist-read-private       — search your private playlists
  playlist-read-collaborative — search collaborative playlists
"""

import subprocess
import sys
from pathlib import Path

from core import config
from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

_SCOPES = " ".join([
    "user-modify-playback-state",
    "user-read-playback-state",
    "playlist-read-private",
    "playlist-read-collaborative",
])


def _get_sp():
    """Return an authenticated Spotify client, or None if not configured."""
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    client_id = config.get("spotify.client_id", "")
    client_secret = config.get("spotify.client_secret", "")
    redirect_uri = config.get("spotify.redirect_uri", "http://127.0.0.1:8888/callback")
    cache_path = Path(config.get("spotify.cache_path", "~/.bobby/spotify_cache")).expanduser()
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if not client_id or not client_secret:
        return None

    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=_SCOPES,
        cache_path=str(cache_path),
        open_browser=False,  # We open Chrome ourselves
    )

    # Check if we already have a valid (or refreshable) token
    token_info = auth.get_cached_token()
    if not token_info:
        # First-time auth: open the auth URL in Chrome and wait for callback
        auth_url = auth.get_authorize_url()
        log.info(f"Spotify auth URL: {auth_url}")
        _open_chrome(auth_url)
        # spotipy's get_access_token will start a local server and wait
        token_info = auth.get_access_token()
        if not token_info:
            return None
    elif auth.is_token_expired(token_info):
        try:
            token_info = auth.refresh_access_token(token_info["refresh_token"])
        except Exception:
            # Refresh token revoked (user removed app access, or 90-day inactivity).
            # Delete the stale cache so the next call triggers a clean first-time auth.
            cache_path.unlink(missing_ok=True)
            log.warning("Spotify refresh token revoked — cache cleared, re-auth required.")
            return None

    return spotipy.Spotify(auth=token_info["access_token"])


def _open_chrome(url: str) -> None:
    """Open a URL in Chrome (WSL-aware). Array args prevent shell injection."""
    try:
        subprocess.Popen(["cmd.exe", "/c", "start", "chrome", url])
    except Exception as e:
        log.error(f"_open_chrome failed: {e}")


def _enabled() -> bool:
    return bool(config.get("spotify.enabled", False))


def _active_device_id(sp) -> str | None:
    """Return the ID of the currently active Spotify device, or None."""
    try:
        devices = sp.devices()
        for d in devices.get("devices", []):
            if d.get("is_active"):
                return d["id"]
        # No active device — return first available
        devs = devices.get("devices", [])
        if devs:
            return devs[0]["id"]
    except Exception:
        pass
    return None


def _search_playlist(sp, query: str) -> tuple[str | None, str | None]:
    """
    Search user's saved playlists by name. Returns (playlist_uri, playlist_name)
    or (None, None) if not found.
    """
    query_lower = query.lower()
    try:
        results = sp.current_user_playlists(limit=50)
        while results:
            for item in results.get("items", []):
                if not item:
                    continue
                name = item.get("name", "")
                if query_lower in name.lower():
                    return item["uri"], name
            if results.get("next"):
                results = sp.next(results)
            else:
                break
    except Exception as e:
        log.debug(f"_search_playlist error: {e}")
    return None, None


@register_tool(
    name="spotify_play",
    description=(
        "Play a Spotify playlist, album, or artist by name. "
        "Examples: 'play my Vietnamese playlist', 'play lo-fi hip hop', 'play Drake'. "
        "Searches your saved playlists first, then Spotify's catalog."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "Playlist, album, or artist name to search for and play.",
            "required": True,
        },
        "type": {
            "type": "string",
            "description": "'playlist' (default) | 'album' | 'artist' | 'track'",
        },
    },
)
def spotify_play(query: str, type: str = "playlist") -> ToolResult:
    if not _enabled():
        return ToolResult(
            success=False,
            message=(
                "Spotify isn't set up yet. Add your credentials to config.yaml: "
                "spotify.client_id, spotify.client_secret, and set spotify.enabled: true. "
                "Get them at developer.spotify.com/dashboard."
            ),
        )

    sp = _get_sp()
    if not sp:
        return ToolResult(
            success=False,
            message="Spotify credentials missing or auth failed. Check config.yaml.",
        )

    device_id = _active_device_id(sp)

    # Try user's own playlists first (they know their playlist names)
    if type in ("playlist", ""):
        uri, name = _search_playlist(sp, query)
        if uri:
            try:
                sp.start_playback(device_id=device_id, context_uri=uri)
                return ToolResult(
                    success=True,
                    message=f"Playing your playlist: {name}.",
                    data={"uri": uri, "name": name},
                )
            except Exception as e:
                log.debug(f"start_playback failed: {e}")

    # Fall back to Spotify catalog search
    search_type = type if type in ("playlist", "album", "artist", "track") else "playlist"
    try:
        results = sp.search(q=query, type=search_type, limit=5)
        items_key = f"{search_type}s"
        items = results.get(items_key, {}).get("items", [])
        if not items:
            return ToolResult(
                success=False,
                message=f"No {search_type} found for '{query}' on Spotify.",
            )
        best = items[0]
        uri = best["uri"]
        name = best.get("name", query)

        if search_type == "track":
            sp.start_playback(device_id=device_id, uris=[uri])
        else:
            sp.start_playback(device_id=device_id, context_uri=uri)

        return ToolResult(
            success=True,
            message=f"Playing {search_type}: {name}.",
            data={"uri": uri, "name": name},
        )
    except Exception as e:
        log.error(f"spotify_play failed: {e}")
        return ToolResult(
            success=False,
            message=f"Couldn't play '{query}' on Spotify: {e}",
        )


@register_tool(
    name="spotify_control",
    description=(
        "Control Spotify playback: pause, resume, skip to next track, go back, or shuffle. "
        "Works while you're in a game — no need to alt-tab."
    ),
    parameters={
        "action": {
            "type": "string",
            "enum": ["pause", "resume", "next", "previous", "shuffle_on", "shuffle_off"],
            "description": "pause | resume | next | previous | shuffle_on | shuffle_off",
            "required": True,
        },
    },
)
def spotify_control(action: str) -> ToolResult:
    if not _enabled():
        return ToolResult(success=False, message="Spotify isn't set up. See spotify.enabled in config.yaml.")

    sp = _get_sp()
    if not sp:
        return ToolResult(success=False, message="Spotify auth failed. Check config.yaml.")

    device_id = _active_device_id(sp)

    try:
        if action == "pause":
            sp.pause_playback(device_id=device_id)
            return ToolResult(success=True, message="Spotify paused.")
        elif action == "resume":
            sp.start_playback(device_id=device_id)
            return ToolResult(success=True, message="Spotify resumed.")
        elif action == "next":
            sp.next_track(device_id=device_id)
            return ToolResult(success=True, message="Skipped to next track.")
        elif action == "previous":
            sp.previous_track(device_id=device_id)
            return ToolResult(success=True, message="Went back to previous track.")
        elif action == "shuffle_on":
            sp.shuffle(True, device_id=device_id)
            return ToolResult(success=True, message="Shuffle on.")
        elif action == "shuffle_off":
            sp.shuffle(False, device_id=device_id)
            return ToolResult(success=True, message="Shuffle off.")
        else:
            return ToolResult(success=False, message=f"Unknown action: {action}")
    except Exception as e:
        log.error(f"spotify_control {action} failed: {e}")
        return ToolResult(success=False, message=f"Spotify {action} failed: {e}")


@register_tool(
    name="spotify_volume",
    description=(
        "Set Spotify's own playback volume (0–100). "
        "This controls the Spotify app volume, independent of system volume."
    ),
    parameters={
        "level": {
            "type": "integer",
            "description": "Volume level 0–100.",
            "required": True,
        },
    },
)
def spotify_volume(level: int) -> ToolResult:
    if not _enabled():
        return ToolResult(success=False, message="Spotify isn't set up. See config.yaml.")

    sp = _get_sp()
    if not sp:
        return ToolResult(success=False, message="Spotify auth failed.")

    level = max(0, min(100, level))
    device_id = _active_device_id(sp)

    try:
        sp.volume(level, device_id=device_id)
        return ToolResult(success=True, message=f"Spotify volume set to {level}%.")
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't set Spotify volume: {e}")


@register_tool(
    name="spotify_current_track",
    description=(
        "Read what's currently playing on Spotify — track name, artist, and album."
    ),
    parameters={},
)
def spotify_current_track() -> ToolResult:
    if not _enabled():
        return ToolResult(success=False, message="Spotify isn't set up. See config.yaml.")

    sp = _get_sp()
    if not sp:
        return ToolResult(success=False, message="Spotify auth failed.")

    try:
        current = sp.current_playback()
        if not current or not current.get("is_playing"):
            return ToolResult(
                success=True,
                message="Spotify isn't playing anything right now.",
                data={"is_playing": False},
            )

        item = current.get("item")
        if not item:
            return ToolResult(success=True, message="Spotify is playing something but track info isn't available.")

        track = item.get("name", "Unknown track")
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        album = item.get("album", {}).get("name", "")
        msg = f"Now playing: {track} by {artists}"
        if album:
            msg += f" (from {album})"

        return ToolResult(
            success=True,
            message=msg,
            data={"track": track, "artists": artists, "album": album},
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Couldn't get current track: {e}")
