"""Tests for tools/discord.py — navigate, voice controls, screenshare."""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _normalize_name
# ---------------------------------------------------------------------------

def test_normalize_name_spaces():
    from tools.discord import _normalize_name
    assert _normalize_name("Bubble Butt Bottom Bois") == "bubble_butt_bottom_bois"


def test_normalize_name_dashes():
    from tools.discord import _normalize_name
    assert _normalize_name("sex-havers") == "sex_havers"


# ---------------------------------------------------------------------------
# _to_sendkeys
# ---------------------------------------------------------------------------

def test_to_sendkeys_ctrl_shift_s():
    from tools.discord import _to_sendkeys
    assert _to_sendkeys("ctrl+shift+s") == "^+s"


def test_to_sendkeys_ctrl_shift_h():
    from tools.discord import _to_sendkeys
    assert _to_sendkeys("ctrl+shift+h") == "^+h"


def test_to_sendkeys_alt_key():
    from tools.discord import _to_sendkeys
    assert _to_sendkeys("alt+f4") == "%f4"


# ---------------------------------------------------------------------------
# _resolve_server_channel
# ---------------------------------------------------------------------------

_SAMPLE_SERVERS = {
    "bubble_butt_bottom_bois": {
        "id": "111222333444555666",
        "channels": {
            "sex_havers": "999888777666555444",
            "general": "123123123123123123",
        },
    }
}


def test_resolve_server_channel_exact_match():
    from tools.discord import _resolve_server_channel
    with patch("core.config.get", side_effect=lambda k, d=None: _SAMPLE_SERVERS if k == "discord.servers" else d):
        guild_id, channel_id, err = _resolve_server_channel(
            "bubble butt bottom bois", "sex havers"
        )
    assert err == ""
    assert guild_id == "111222333444555666"
    assert channel_id == "999888777666555444"


def test_resolve_server_channel_partial_server_name():
    from tools.discord import _resolve_server_channel
    with patch("core.config.get", side_effect=lambda k, d=None: _SAMPLE_SERVERS if k == "discord.servers" else d):
        guild_id, channel_id, err = _resolve_server_channel("bubble", "general")
    assert err == ""
    assert guild_id == "111222333444555666"
    assert channel_id == "123123123123123123"


def test_resolve_server_channel_no_servers_config():
    from tools.discord import _resolve_server_channel
    with patch("core.config.get", return_value={}):
        _, _, err = _resolve_server_channel("any", "any")
    assert "No Discord servers configured" in err


def test_resolve_server_channel_unknown_server():
    from tools.discord import _resolve_server_channel
    with patch("core.config.get", side_effect=lambda k, d=None: _SAMPLE_SERVERS if k == "discord.servers" else d):
        _, _, err = _resolve_server_channel("zzz_not_a_server", "general")
    assert "not found" in err.lower()


def test_resolve_server_channel_unknown_channel():
    from tools.discord import _resolve_server_channel
    with patch("core.config.get", side_effect=lambda k, d=None: _SAMPLE_SERVERS if k == "discord.servers" else d):
        _, _, err = _resolve_server_channel("bubble butt bottom bois", "zzz_no_channel")
    assert "not found" in err.lower()


# ---------------------------------------------------------------------------
# discord_navigate
# ---------------------------------------------------------------------------

def test_discord_navigate_opens_url():
    from tools.discord import discord_navigate
    with patch("core.config.get", side_effect=lambda k, d=None: _SAMPLE_SERVERS if k == "discord.servers" else d), \
         patch("subprocess.Popen") as mock_popen, \
         patch("sys.platform", "linux"):
        result = discord_navigate(server="bubble butt bottom bois", channel="sex-havers")

    assert result.success
    assert result.data["guild_id"] == "111222333444555666"
    assert result.data["channel_id"] == "999888777666555444"
    # Array args: ["cmd.exe", "/c", "start", "", url]
    popen_args = mock_popen.call_args[0][0]
    url_arg = popen_args[-1] if isinstance(popen_args, list) else popen_args
    assert "discord://-/channels/111222333444555666/999888777666555444" in url_arg


def test_discord_navigate_uses_defaults():
    from tools.discord import discord_navigate

    def cfg_side_effect(k, d=None):
        if k == "discord.default_server":
            return "bubble butt bottom bois"
        if k == "discord.default_channel":
            return "sex-havers"
        if k == "discord.servers":
            return _SAMPLE_SERVERS
        return d

    with patch("core.config.get", side_effect=cfg_side_effect), \
         patch("subprocess.Popen"), \
         patch("sys.platform", "linux"):
        result = discord_navigate()

    assert result.success
    assert "sex-havers" in result.message


def test_discord_navigate_no_config():
    from tools.discord import discord_navigate
    with patch("core.config.get", return_value=None):
        result = discord_navigate()
    assert not result.success
    assert "No server" in result.message or "default" in result.message.lower()


# ---------------------------------------------------------------------------
# discord_voice
# ---------------------------------------------------------------------------

def _ps_ok_side_effect(cmd, timeout=6):
    return (0, "OK")


def _ps_discord_missing(cmd, timeout=6):
    return (0, "DISCORD_NOT_RUNNING")


def test_discord_voice_mute_success():
    from tools.discord import discord_voice
    with patch("tools.discord._ps", side_effect=_ps_ok_side_effect):
        result = discord_voice("mute")
    assert result.success
    assert "Muted" in result.message


def test_discord_voice_deafen_success():
    from tools.discord import discord_voice
    with patch("tools.discord._ps", side_effect=_ps_ok_side_effect):
        result = discord_voice("deafen")
    assert result.success
    assert "Deafened" in result.message


def test_discord_voice_unmute_success():
    from tools.discord import discord_voice
    with patch("tools.discord._ps", side_effect=_ps_ok_side_effect):
        result = discord_voice("unmute")
    assert result.success


def test_discord_voice_undeafen_success():
    from tools.discord import discord_voice
    with patch("tools.discord._ps", side_effect=_ps_ok_side_effect):
        result = discord_voice("undeafen")
    assert result.success


def test_discord_voice_discord_not_running():
    from tools.discord import discord_voice
    with patch("tools.discord._ps", side_effect=_ps_discord_missing):
        result = discord_voice("mute")
    assert not result.success
    assert "Discord isn't running" in result.message


def test_discord_voice_unknown_action():
    from tools.discord import discord_voice
    result = discord_voice("wave_hands")
    assert not result.success
    assert "Unknown action" in result.message


def test_discord_voice_ps_timeout():
    import subprocess
    from tools.discord import discord_voice
    with patch("tools.discord._ps", side_effect=subprocess.TimeoutExpired("ps", 6)):
        result = discord_voice("mute")
    assert not result.success
    assert "timed out" in result.message.lower()


# ---------------------------------------------------------------------------
# discord_voice — screen_share
# ---------------------------------------------------------------------------

def test_discord_screenshare_no_keybind():
    from tools.discord import discord_voice
    with patch("core.config.get", return_value=""):
        result = discord_voice("screen_share")
    assert not result.success
    assert "Keybinds" in result.message or "keybind" in result.message.lower()


def test_discord_screenshare_with_keybind():
    from tools.discord import discord_voice

    def cfg_side(k, d=None):
        if k == "discord.screenshare_keybind":
            return "ctrl+shift+s"
        return d

    with patch("core.config.get", side_effect=cfg_side), \
         patch("tools.discord._ps", side_effect=_ps_ok_side_effect):
        result = discord_voice("screen_share")
    assert result.success
    assert "toggled" in result.message.lower()


def test_discord_screenshare_discord_not_running():
    from tools.discord import discord_voice

    def cfg_side(k, d=None):
        if k == "discord.screenshare_keybind":
            return "ctrl+shift+s"
        return d

    with patch("core.config.get", side_effect=cfg_side), \
         patch("tools.discord._ps", side_effect=_ps_discord_missing):
        result = discord_voice("screen_share")
    assert not result.success
    assert "Discord isn't running" in result.message
