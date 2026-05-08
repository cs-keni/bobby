"""Phase 2 feature tests: fuzzy app matching, shortcuts CRUD, system_power gate, window/keyboard tools."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fuzzy app matching (os_control._resolve_app)
# ---------------------------------------------------------------------------

def test_resolve_app_exact():
    from tools.os_control import _resolve_app
    app_map = {"chrome": "chrome.exe", "notepad": "notepad.exe"}
    assert _resolve_app("chrome", app_map) == "chrome.exe"


def test_resolve_app_substring():
    from tools.os_control import _resolve_app
    app_map = {"google chrome": "chrome.exe"}
    assert _resolve_app("chrome", app_map) == "chrome.exe"


def test_resolve_app_fuzzy():
    from tools.os_control import _resolve_app
    app_map = {"discord": "discord.exe", "notepad": "notepad.exe"}
    # "discrd" is close enough to "discord"
    result = _resolve_app("discrd", app_map)
    assert result == "discord.exe"


def test_resolve_app_passthrough():
    from tools.os_control import _resolve_app
    app_map = {"chrome": "chrome.exe"}
    # Completely unknown → return the name as-is
    assert _resolve_app("zxqwerty", app_map) == "zxqwerty"


# ---------------------------------------------------------------------------
# Shortcuts CRUD (tools/shortcuts.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Redirect the shortcuts DB to a temp directory."""
    import tools.shortcuts as sc
    monkeypatch.setattr(sc, "_DB_PATH", tmp_path / "shortcuts.db")
    yield tmp_path / "shortcuts.db"


def test_list_shortcuts_defaults(tmp_db):
    from tools.shortcuts import list_shortcuts
    result = list_shortcuts()
    assert result.success
    assert "the usual" in result.message


def test_save_and_open_shortcut(tmp_db):
    from tools.shortcuts import save_shortcut, open_shortcut

    save_result = save_shortcut("test combo", ["notepad", "calc"], "my test combo")
    assert save_result.success

    # open_app is imported lazily inside open_shortcut — patch at its source
    with patch("tools.os_control.open_app") as mock_open:
        mock_open.return_value = MagicMock(success=True, message="Opened")
        open_result = open_shortcut("test combo")

    assert open_result.success
    assert "test combo" in open_result.message
    assert mock_open.call_count == 2


def test_open_shortcut_missing(tmp_db):
    from tools.shortcuts import open_shortcut
    result = open_shortcut("does not exist")
    assert not result.success
    assert "No shortcut" in result.message


def test_delete_shortcut(tmp_db):
    from tools.shortcuts import save_shortcut, delete_shortcut, list_shortcuts
    save_shortcut("temp", ["notepad"], "temp shortcut")
    del_result = delete_shortcut("temp")
    assert del_result.success

    listed = list_shortcuts()
    assert "temp" not in listed.message


def test_delete_shortcut_missing(tmp_db):
    from tools.shortcuts import delete_shortcut
    result = delete_shortcut("ghost")
    assert not result.success


def test_save_shortcut_replaces(tmp_db):
    from tools.shortcuts import save_shortcut, open_shortcut
    save_shortcut("combo", ["notepad"], "v1")
    save_shortcut("combo", ["calc", "chrome"], "v2")

    with patch("tools.os_control.open_app") as mock_open:
        mock_open.return_value = MagicMock(success=True, message="Opened")
        open_shortcut("combo")

    assert mock_open.call_count == 2  # calc + chrome, not notepad


def test_save_shortcut_empty_apps(tmp_db):
    from tools.shortcuts import save_shortcut
    result = save_shortcut("bad", [])
    assert not result.success


# ---------------------------------------------------------------------------
# system_power — requires_confirmation gate
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform == "linux", reason="win32 API not available in WSL")
def test_system_power_requires_confirmation():
    from tools.os_control import system_power
    result = system_power("shutdown")
    assert not result.success
    assert result.data.get("requires_confirmation") is True
    assert result.data.get("confirm_and_retry_tool") == "system_power"


def test_system_power_confirmed_lock():
    """Confirmed lock runs without user prompt."""
    from tools.os_control import system_power
    with patch("tools.os_control.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = system_power("lock", confirmed=True)
    assert result.success


# ---------------------------------------------------------------------------
# type_text / press_keys — mocked keyboard module
# ---------------------------------------------------------------------------

def test_type_text():
    # keyboard is imported locally inside the function — mock via sys.modules
    mock_kb = MagicMock()
    with patch.dict("sys.modules", {"keyboard": mock_kb}):
        from tools.os_control import type_text
        result = type_text("hello world")
    assert result.success
    mock_kb.write.assert_called_once_with("hello world", delay=0.0)


def test_press_keys():
    mock_kb = MagicMock()
    with patch.dict("sys.modules", {"keyboard": mock_kb}):
        from tools.os_control import press_keys
        result = press_keys("ctrl+c")
    assert result.success
    mock_kb.send.assert_called_once_with("ctrl+c")
