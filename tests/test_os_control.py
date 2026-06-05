"""
Phase 1 mandatory safety tests for OS control tools.
These must pass before Phase 2 ships.
"""

import pytest
from unittest.mock import patch
from tools.os_control import execute_terminal, _is_dangerous, DANGEROUS_PATTERNS, list_running_apps, APP_MAP


class TestDangerousCommandDetection:
    """CRITICAL: dangerous commands must NEVER auto-execute."""

    @pytest.mark.parametrize("command", [
        "rm -rf /",
        "rm -rf /home/user",
        "rm -r /important",
        "del /f /s /q C:\\",
        "del /f C:\\Windows",
        "format c:",
        "FORMAT C: /FS:NTFS",
        "reg delete HKLM\\System",
        "reg del HKCU\\Software",
        "shutdown /f /r",
        "shutdown -f",
        "rmdir /s /q C:\\Users",
        "rd /s C:\\",
        "mkfs.ext4 /dev/sda",
        "dd if=/dev/zero of=/dev/sda",
    ])
    def test_detects_dangerous_command(self, command: str):
        assert _is_dangerous(command), f"Should have detected '{command}' as dangerous"

    @pytest.mark.parametrize("command", [
        "echo hello",
        "ls -la",
        "dir",
        "python --version",
        "git status",
        "npm install",
        "pip list",
        "cat README.md",
    ])
    def test_safe_commands_not_flagged(self, command: str):
        assert not _is_dangerous(command), f"Safe command '{command}' was incorrectly flagged"

    def test_execute_terminal_blocks_rm_rf(self):
        result = execute_terminal("rm -rf /")
        assert not result.success
        assert result.data.get("requires_confirmation") is True
        assert "rm -rf" in result.message.lower() or "confirmation" in result.message.lower()

    def test_execute_terminal_blocks_format(self):
        result = execute_terminal("format c:")
        assert not result.success
        assert result.data.get("requires_confirmation") is True

    def test_execute_terminal_blocks_del_force(self):
        result = execute_terminal("del /f /s /q C:\\important")
        assert not result.success
        assert result.data.get("requires_confirmation") is True

    def test_execute_terminal_allows_safe_command(self, tmp_path):
        result = execute_terminal("echo hello", silent=True)
        assert result.success
        assert "hello" in result.message.lower() or result.data.get("returncode") == 0

    def test_execute_terminal_case_insensitive(self):
        """Dangerous command detection must be case-insensitive."""
        result = execute_terminal("RM -RF /tmp/test")
        assert not result.success
        assert result.data.get("requires_confirmation") is True


class TestListRunningApps:
    """list_running_apps calls PowerShell — mock _ps_run to avoid Windows dependency."""

    def test_returns_running_true_when_app_found(self):
        output = "Name        Id  Window\n----        --  ------\nObsidian  1234  Obsidian\n"
        with patch("tools.os_control._ps_run", return_value=(0, output)):
            result = list_running_apps(filter="obsidian")
        assert result.success
        assert result.data["running"] is True
        assert "Obsidian" in result.message

    def test_returns_running_false_when_not_found(self):
        with patch("tools.os_control._ps_run", return_value=(0, "not running")):
            result = list_running_apps(filter="obsidian")
        assert result.success
        assert result.data["running"] is False
        assert "not running" in result.message

    def test_empty_output_reports_not_running(self):
        with patch("tools.os_control._ps_run", return_value=(0, "")):
            result = list_running_apps(filter="obsidian")
        assert result.success
        assert result.data["running"] is False

    def test_no_filter_lists_all_visible_apps(self):
        output = "Name    Window\n----    ------\nChrome  Google\n"
        with patch("tools.os_control._ps_run", return_value=(0, output)):
            result = list_running_apps()
        assert result.success
        assert result.data["running"] is True

    def test_sanitizes_filter_input(self):
        captured = []
        def fake_ps_run(cmd):
            captured.append(cmd)
            return (0, "not running")
        with patch("tools.os_control._ps_run", fake_ps_run):
            list_running_apps(filter="evil'; DROP TABLE--")
        # The raw injection payload (quote + semicolon) should not survive into the filter
        assert "'; DROP" not in captured[0]


class TestAppMap:
    def test_obsidian_in_app_map(self):
        assert "obsidian" in APP_MAP
        assert APP_MAP["obsidian"] == "Obsidian"
