"""Tests for tools/audio.py — per-app audio session volume control."""

import subprocess
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# _resolve_process
# ---------------------------------------------------------------------------

def test_resolve_process_youtube_maps_to_chrome():
    from tools.audio import _resolve_process
    assert _resolve_process("youtube") == "chrome"


def test_resolve_process_spotify():
    from tools.audio import _resolve_process
    assert _resolve_process("spotify") == "spotify"


def test_resolve_process_discord():
    from tools.audio import _resolve_process
    assert _resolve_process("discord") == "discord"


def test_resolve_process_partial_match():
    from tools.audio import _resolve_process
    # "chrom" should match "chrome" alias
    assert _resolve_process("chrom") == "chrome"


def test_resolve_process_unknown_passthrough():
    from tools.audio import _resolve_process
    assert _resolve_process("somegame") == "somegame"


def test_resolve_process_rejects_injection():
    from tools.audio import _resolve_process
    assert _resolve_process("'; Invoke-Expression 'calc.exe'") == ""


def test_resolve_process_rejects_special_chars():
    from tools.audio import _resolve_process
    assert _resolve_process("app; rm -rf /") == ""


# ---------------------------------------------------------------------------
# list_audio_apps
# ---------------------------------------------------------------------------

def _ps_list_apps(cmd, timeout=12):
    return (0, "chrome:80:0\nspotify:60:0\ndiscord:100:1")


def _ps_empty(cmd, timeout=12):
    return (0, "")


def _ps_error(cmd, timeout=12):
    return (1, "error")


def test_list_audio_apps_parses_output():
    from tools.audio import list_audio_apps
    with patch("tools.audio._ps", side_effect=_ps_list_apps):
        result = list_audio_apps()
    assert result.success
    names = [a["process"] for a in result.data["apps"]]
    assert "chrome" in names
    assert "spotify" in names
    assert "discord" in names


def test_list_audio_apps_discord_muted():
    from tools.audio import list_audio_apps
    with patch("tools.audio._ps", side_effect=_ps_list_apps):
        result = list_audio_apps()
    discord = next(a for a in result.data["apps"] if a["process"] == "discord")
    assert discord["muted"] is True


def test_list_audio_apps_empty():
    from tools.audio import list_audio_apps
    with patch("tools.audio._ps", side_effect=_ps_empty):
        result = list_audio_apps()
    assert result.success
    assert result.data["apps"] == []


def test_list_audio_apps_timeout():
    from tools.audio import list_audio_apps
    with patch("tools.audio._ps", side_effect=subprocess.TimeoutExpired("ps", 12)):
        result = list_audio_apps()
    assert not result.success
    assert "timed out" in result.message.lower()


# ---------------------------------------------------------------------------
# get_app_volume
# ---------------------------------------------------------------------------

def _ps_get_80(cmd, timeout=12):
    return (0, "80")


def _ps_get_not_found(cmd, timeout=12):
    return (0, "-1")


def test_get_app_volume_success():
    from tools.audio import get_app_volume
    with patch("tools.audio._ps", side_effect=_ps_get_80):
        result = get_app_volume("youtube")
    assert result.success
    assert "80%" in result.message
    assert result.data["volume"] == 80


def test_get_app_volume_not_playing():
    from tools.audio import get_app_volume
    with patch("tools.audio._ps", side_effect=_ps_get_not_found):
        result = get_app_volume("spotify")
    assert not result.success
    assert "playing" in result.message.lower()


def test_get_app_volume_timeout():
    from tools.audio import get_app_volume
    with patch("tools.audio._ps", side_effect=subprocess.TimeoutExpired("ps", 12)):
        result = get_app_volume("youtube")
    assert not result.success
    assert "timed out" in result.message.lower()


# ---------------------------------------------------------------------------
# set_app_volume
# ---------------------------------------------------------------------------

def _ps_set_ok(cmd, timeout=12):
    return (0, "SET:2")


def _ps_set_not_found(cmd, timeout=12):
    return (0, "NOT_FOUND")


def _ps_set_error(cmd, timeout=12):
    return (1, "error")


def test_set_app_volume_by_level():
    from tools.audio import set_app_volume
    with patch("tools.audio._ps", side_effect=_ps_set_ok):
        result = set_app_volume("youtube", level=30)
    assert result.success
    assert "30%" in result.message


def test_set_app_volume_clamps_level():
    from tools.audio import set_app_volume
    with patch("tools.audio._ps", side_effect=_ps_set_ok):
        result = set_app_volume("youtube", level=150)
    assert result.success
    assert result.data["level"] == 100


def test_set_app_volume_mute():
    from tools.audio import set_app_volume
    with patch("tools.audio._ps", side_effect=_ps_set_ok):
        result = set_app_volume("discord", mute=True)
    assert result.success
    assert "muted" in result.message.lower()


def test_set_app_volume_not_found():
    from tools.audio import set_app_volume
    with patch("tools.audio._ps", side_effect=_ps_set_not_found):
        result = set_app_volume("youtube", level=30)
    assert not result.success
    assert "playing" in result.message.lower()


def test_set_app_volume_no_params():
    from tools.audio import set_app_volume
    result = set_app_volume("youtube")
    assert not result.success


def test_set_app_volume_invalid_app_name():
    from tools.audio import set_app_volume
    result = set_app_volume("'; calc.exe", level=50)
    assert not result.success
    assert "Invalid app name" in result.message


def test_get_app_volume_invalid_app_name():
    from tools.audio import get_app_volume
    result = get_app_volume("'; calc.exe")
    assert not result.success
    assert "Invalid app name" in result.message


def test_set_app_volume_timeout():
    from tools.audio import set_app_volume
    with patch("tools.audio._ps", side_effect=subprocess.TimeoutExpired("ps", 12)):
        result = set_app_volume("spotify", level=50)
    assert not result.success
    assert "timed out" in result.message.lower()
