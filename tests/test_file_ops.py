"""Tests for tools/file_ops.py — file search, open, and folder listing."""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    """Patch _win_home() and reset the module-level cache so each test is isolated."""
    import tools.file_ops as fo
    monkeypatch.setattr(fo, "_WIN_HOME_CACHE", None)
    monkeypatch.setattr(fo, "_win_home", lambda: tmp_path)
    yield tmp_path
    monkeypatch.setattr(fo, "_WIN_HOME_CACHE", None)


def _make_file(path: Path, content: str = "x", mtime_offset_days: int = 0) -> Path:
    """Create a file and optionally backdate its mtime."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if mtime_offset_days:
        ts = time.time() - mtime_offset_days * 86400
        os.utime(path, (ts, ts))
    return path


# ---------------------------------------------------------------------------
# _resolve_folder
# ---------------------------------------------------------------------------

def test_resolve_folder_alias_downloads(fake_home):
    from tools.file_ops import _resolve_folder
    assert _resolve_folder("downloads") == fake_home / "Downloads"


def test_resolve_folder_alias_case_insensitive(fake_home):
    from tools.file_ops import _resolve_folder
    assert _resolve_folder("Desktop") == fake_home / "Desktop"


def test_resolve_folder_absolute_path(fake_home):
    from tools.file_ops import _resolve_folder
    p = fake_home / "some" / "path"
    assert _resolve_folder(str(p)) == p


def test_resolve_folder_partial_match(fake_home):
    from tools.file_ops import _resolve_folder
    # "vid" should match "videos"
    assert _resolve_folder("vid") == fake_home / "Videos"


# ---------------------------------------------------------------------------
# _to_windows_path
# ---------------------------------------------------------------------------

def test_to_windows_path_converts_wsl():
    from tools.file_ops import _to_windows_path
    result = _to_windows_path(Path("/mnt/c/Users/keni/Downloads/file.pdf"))
    assert result == r"C:\Users\keni\Downloads\file.pdf"


def test_to_windows_path_passthrough_non_mnt():
    from tools.file_ops import _to_windows_path
    result = _to_windows_path(Path("/home/keni/file.txt"))
    assert result == "/home/keni/file.txt"


# ---------------------------------------------------------------------------
# search_files
# ---------------------------------------------------------------------------

def test_search_files_finds_match(fake_home):
    dl = fake_home / "Downloads"
    _make_file(dl / "invoice_2026.pdf")
    _make_file(dl / "photo.jpg")

    from tools.file_ops import search_files
    result = search_files("invoice", folder="downloads")
    assert result.success
    assert "invoice_2026.pdf" in result.message
    assert len(result.data["results"]) == 1


def test_search_files_no_match(fake_home):
    dl = fake_home / "Downloads"
    _make_file(dl / "readme.txt")

    from tools.file_ops import search_files
    result = search_files("zzz_does_not_exist", folder="downloads")
    assert result.success
    assert result.data["total"] == 0
    assert "No files" in result.message


def test_search_files_type_filter(fake_home):
    dl = fake_home / "Downloads"
    _make_file(dl / "clip.mp4")
    _make_file(dl / "clip.pdf")

    from tools.file_ops import search_files
    result = search_files("clip", folder="downloads", file_type="video")
    assert result.success
    names = [r["name"] for r in result.data["results"]]
    assert "clip.mp4" in names
    assert "clip.pdf" not in names


def test_search_files_newer_than_filter(fake_home):
    dl = fake_home / "Downloads"
    new_file = _make_file(dl / "new.txt", mtime_offset_days=0)
    _make_file(dl / "old.txt", mtime_offset_days=30)

    from tools.file_ops import search_files
    result = search_files(".txt", folder="downloads", newer_than_days=7)
    assert result.success
    names = [r["name"] for r in result.data["results"]]
    assert "new.txt" in names
    assert "old.txt" not in names


def test_search_files_recursive_default(fake_home):
    sub = fake_home / "Downloads" / "subdir"
    _make_file(sub / "nested.txt")

    from tools.file_ops import search_files
    result = search_files("nested", folder="downloads", recursive=True)
    assert result.success
    assert result.data["total"] == 1


def test_search_files_non_recursive(fake_home):
    sub = fake_home / "Downloads" / "subdir"
    _make_file(sub / "nested.txt")

    from tools.file_ops import search_files
    result = search_files("nested", folder="downloads", recursive=False)
    assert result.success
    assert result.data["total"] == 0


def test_search_files_folder_not_found(fake_home):
    from tools.file_ops import search_files
    result = search_files("anything", folder="/nonexistent/path/xyz")
    assert not result.success
    assert "not found" in result.message.lower()


def test_search_files_caps_at_10(fake_home):
    dl = fake_home / "Downloads"
    for i in range(15):
        _make_file(dl / f"file_{i:02d}.txt")

    from tools.file_ops import search_files
    result = search_files("file_", folder="downloads")
    assert result.success
    assert len(result.data["results"]) == 10
    assert result.data["total"] == 15
    assert "... and 5 more" in result.message


# ---------------------------------------------------------------------------
# open_file
# ---------------------------------------------------------------------------

def test_open_file_not_found(fake_home):
    from tools.file_ops import open_file
    result = open_file(str(fake_home / "nonexistent.txt"))
    assert not result.success
    assert "not found" in result.message.lower()


def test_open_file_on_directory(fake_home):
    d = fake_home / "somedir"
    d.mkdir()
    from tools.file_ops import open_file
    result = open_file(str(d))
    assert not result.success
    assert "folder" in result.message.lower()


def test_open_file_launches_process(fake_home):
    f = _make_file(fake_home / "Downloads" / "test.txt")
    with patch("subprocess.Popen") as mock_popen, \
         patch("sys.platform", "linux"):
        from tools.file_ops import open_file
        result = open_file(str(f))
    assert result.success
    mock_popen.assert_called_once()


# ---------------------------------------------------------------------------
# list_folder
# ---------------------------------------------------------------------------

def test_list_folder_returns_entries(fake_home):
    dl = fake_home / "Downloads"
    _make_file(dl / "alpha.txt")
    _make_file(dl / "beta.pdf")

    from tools.file_ops import list_folder
    result = list_folder("downloads")
    assert result.success
    assert result.data["total"] == 2
    names = [e["name"] for e in result.data["entries"]]
    assert "alpha.txt" in names
    assert "beta.pdf" in names


def test_list_folder_sort_by_name(fake_home):
    dl = fake_home / "Downloads"
    _make_file(dl / "zzz.txt")
    _make_file(dl / "aaa.txt")

    from tools.file_ops import list_folder
    result = list_folder("downloads", sort_by="name")
    assert result.success
    names = [e["name"] for e in result.data["entries"]]
    assert names == sorted(names, key=str.lower)


def test_list_folder_not_found(fake_home):
    from tools.file_ops import list_folder
    result = list_folder("/nonexistent/xyz")
    assert not result.success


def test_list_folder_empty(fake_home):
    d = fake_home / "empty_dir"
    d.mkdir()

    from tools.file_ops import list_folder
    result = list_folder(str(d))
    assert result.success
    assert result.data["total"] == 0
    assert "empty" in result.message.lower()


def test_list_folder_caps_at_20(fake_home):
    dl = fake_home / "Downloads"
    for i in range(25):
        _make_file(dl / f"item_{i:02d}.txt")

    from tools.file_ops import list_folder
    result = list_folder("downloads")
    assert result.success
    assert len(result.data["entries"]) == 20
    assert result.data["total"] == 25
    assert "... and 5 more" in result.message
