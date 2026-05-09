"""
Phase 7 tests: tools/media.py
All external dependencies (keyboard, mss, subprocess, win32clipboard) are mocked.
"""

import sys
from unittest.mock import MagicMock, patch, call


def test_system_media_play_pause():
    mock_keyboard = MagicMock()
    with patch.dict("sys.modules", {"keyboard": mock_keyboard}):
        from tools.media import system_media
        result = system_media("play_pause")
    assert result.success is True
    mock_keyboard.send.assert_called_once_with("play/pause media")


def test_system_media_next():
    mock_keyboard = MagicMock()
    with patch.dict("sys.modules", {"keyboard": mock_keyboard}):
        from tools.media import system_media
        result = system_media("next")
    assert result.success is True
    mock_keyboard.send.assert_called_once_with("next track")


def test_system_media_invalid_action():
    mock_keyboard = MagicMock()
    with patch.dict("sys.modules", {"keyboard": mock_keyboard}):
        from tools.media import system_media
        result = system_media("dance")
    assert result.success is False
    mock_keyboard.send.assert_not_called()


def test_screenshot_saves_file(tmp_path):
    mock_mss_instance = MagicMock()
    mock_mss_cls = MagicMock()
    mock_mss_cls.return_value.__enter__ = MagicMock(return_value=mock_mss_instance)
    mock_mss_cls.return_value.__exit__ = MagicMock(return_value=False)

    fake_path = tmp_path / "Pictures" / "Bobby" / "test.png"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.touch()

    mock_mss_module = MagicMock()
    mock_mss_module.mss = mock_mss_cls

    with patch.dict("sys.modules", {"mss": mock_mss_module, "mss.tools": MagicMock()}):
        with patch("pathlib.Path.home", return_value=tmp_path):
            from tools.media import take_screenshot
            result = take_screenshot("test")

    assert result.success is True
    assert "path" in result.data
    assert "test.png" in result.data["path"]
    assert "test.png" in result.message


def test_get_clipboard_wsl():
    mock_result = MagicMock()
    mock_result.stdout = "hello clipboard\n"

    with patch("sys.platform", "linux"):
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Ensure win32clipboard is not present
            with patch.dict("sys.modules", {"win32clipboard": None}):
                from tools.media import get_clipboard
                result = get_clipboard()

    assert result.success is True
    assert "hello clipboard" in result.message
    assert result.data["text"] == "hello clipboard"

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "powershell.exe" in args


def test_set_clipboard_wsl():
    with patch("sys.platform", "linux"):
        with patch("subprocess.run") as mock_run:
            with patch.dict("sys.modules", {"win32clipboard": None}):
                from tools.media import set_clipboard
                result = set_clipboard("my text")

    assert result.success is True
    mock_run.assert_called_once()
    kwargs = mock_run.call_args[1]
    assert kwargs.get("input") == "my text"
    args = mock_run.call_args[0][0]
    assert "clip.exe" in args
