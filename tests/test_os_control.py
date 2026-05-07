"""
Phase 1 mandatory safety tests for OS control tools.
These must pass before Phase 2 ships.
"""

import pytest
from tools.os_control import execute_terminal, _is_dangerous, DANGEROUS_PATTERNS


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
