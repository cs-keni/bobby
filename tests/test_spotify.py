"""Tests for tools/spotify.py — Spotify Web API integration."""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_sp(playlists=None, search_results=None, current=None, devices=None):
    """Build a mock Spotify client with configurable responses."""
    sp = MagicMock()

    # Devices
    sp.devices.return_value = {"devices": devices or [{"id": "dev1", "is_active": True}]}

    # User playlists
    if playlists is not None:
        sp.current_user_playlists.return_value = {"items": playlists, "next": None}
    else:
        sp.current_user_playlists.return_value = {"items": [], "next": None}

    # Search
    if search_results is not None:
        sp.search.return_value = search_results
    else:
        sp.search.return_value = {"playlists": {"items": []}}

    # Playback
    sp.current_playback.return_value = current

    return sp


def _playlist_item(name: str, uri: str) -> dict:
    return {"name": name, "uri": uri}


def _track_item(name: str, artists: list[str], album: str) -> dict:
    return {
        "name": name,
        "artists": [{"name": a} for a in artists],
        "album": {"name": album},
    }


# ---------------------------------------------------------------------------
# _enabled / not configured
# ---------------------------------------------------------------------------

def test_spotify_play_not_enabled():
    from tools.spotify import spotify_play
    with patch("core.config.get", return_value=False):
        result = spotify_play("lo-fi")
    assert not result.success
    assert "set up" in result.message.lower() or "enabled" in result.message.lower()


def test_spotify_control_not_enabled():
    from tools.spotify import spotify_control
    with patch("core.config.get", return_value=False):
        result = spotify_control("pause")
    assert not result.success


def test_spotify_volume_not_enabled():
    from tools.spotify import spotify_volume
    with patch("core.config.get", return_value=False):
        result = spotify_volume(50)
    assert not result.success


def test_spotify_current_track_not_enabled():
    from tools.spotify import spotify_current_track
    with patch("core.config.get", return_value=False):
        result = spotify_current_track()
    assert not result.success


# ---------------------------------------------------------------------------
# spotify_play
# ---------------------------------------------------------------------------

def test_spotify_play_finds_user_playlist():
    from tools.spotify import spotify_play
    playlists = [_playlist_item("Vietnamese Mix", "spotify:playlist:abc123")]
    sp = _mock_sp(playlists=playlists)

    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_play("vietnamese")

    assert result.success
    assert "Vietnamese Mix" in result.message
    sp.start_playback.assert_called_once()


def test_spotify_play_user_playlist_partial_match():
    from tools.spotify import spotify_play
    playlists = [_playlist_item("Chill EDM Vibes", "spotify:playlist:edm1")]
    sp = _mock_sp(playlists=playlists)

    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_play("chill edm")

    assert result.success
    assert "Chill EDM Vibes" in result.message


def test_spotify_play_falls_back_to_catalog():
    from tools.spotify import spotify_play
    sp = _mock_sp(
        playlists=[],
        search_results={
            "playlists": {
                "items": [{"uri": "spotify:playlist:catalog1", "name": "Lo-Fi Beats"}]
            }
        }
    )

    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_play("lo-fi beats")

    assert result.success
    assert "Lo-Fi Beats" in result.message


def test_spotify_play_not_found():
    from tools.spotify import spotify_play
    sp = _mock_sp(playlists=[], search_results={"playlists": {"items": []}})

    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_play("zzz_this_does_not_exist_xyz")

    assert not result.success


def test_spotify_play_no_sp():
    from tools.spotify import spotify_play
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=None):
        result = spotify_play("lo-fi")
    assert not result.success
    assert "auth" in result.message.lower() or "credential" in result.message.lower()


# ---------------------------------------------------------------------------
# spotify_control
# ---------------------------------------------------------------------------

def test_spotify_control_pause():
    from tools.spotify import spotify_control
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_control("pause")
    assert result.success
    assert "paused" in result.message.lower()
    sp.pause_playback.assert_called_once()


def test_spotify_control_resume():
    from tools.spotify import spotify_control
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_control("resume")
    assert result.success
    sp.start_playback.assert_called_once()


def test_spotify_control_next():
    from tools.spotify import spotify_control
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_control("next")
    assert result.success
    sp.next_track.assert_called_once()


def test_spotify_control_previous():
    from tools.spotify import spotify_control
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_control("previous")
    assert result.success
    sp.previous_track.assert_called_once()


def test_spotify_control_shuffle_on():
    from tools.spotify import spotify_control
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_control("shuffle_on")
    assert result.success
    sp.shuffle.assert_called_once_with(True, device_id="dev1")


def test_spotify_control_unknown_action():
    from tools.spotify import spotify_control
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_control("dance")
    assert not result.success


# ---------------------------------------------------------------------------
# spotify_volume
# ---------------------------------------------------------------------------

def test_spotify_volume_sets_level():
    from tools.spotify import spotify_volume
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_volume(70)
    assert result.success
    assert "70%" in result.message
    sp.volume.assert_called_once_with(70, device_id="dev1")


def test_spotify_volume_clamps_to_100():
    from tools.spotify import spotify_volume
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_volume(150)
    assert result.success
    sp.volume.assert_called_once_with(100, device_id="dev1")


def test_spotify_volume_clamps_to_0():
    from tools.spotify import spotify_volume
    sp = _mock_sp()
    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_volume(-10)
    assert result.success
    sp.volume.assert_called_once_with(0, device_id="dev1")


# ---------------------------------------------------------------------------
# spotify_current_track
# ---------------------------------------------------------------------------

def test_spotify_current_track_playing():
    from tools.spotify import spotify_current_track
    track = _track_item("Blinding Lights", ["The Weeknd"], "After Hours")
    sp = _mock_sp(current={"is_playing": True, "item": track})

    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_current_track()

    assert result.success
    assert "Blinding Lights" in result.message
    assert "The Weeknd" in result.message


def test_spotify_current_track_not_playing():
    from tools.spotify import spotify_current_track
    sp = _mock_sp(current={"is_playing": False, "item": None})

    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_current_track()

    assert result.success
    assert "isn't playing" in result.message.lower() or "nothing" in result.message.lower()


def test_spotify_current_track_none_playback():
    from tools.spotify import spotify_current_track
    sp = _mock_sp(current=None)

    with patch("tools.spotify._enabled", return_value=True), \
         patch("tools.spotify._get_sp", return_value=sp):
        result = spotify_current_track()

    assert result.success
