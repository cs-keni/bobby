"""Tests for tools/browser.py — URL opening and browser integration."""

from unittest.mock import patch


# ---------------------------------------------------------------------------
# open_url
# ---------------------------------------------------------------------------

def test_open_url_adds_https():
    from tools.browser import open_url
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_url("www.youtube.com")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "https://www.youtube.com" in call_arg


def test_open_url_preserves_https():
    from tools.browser import open_url
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_url("https://careers.tiktok.com")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "https://careers.tiktok.com" in call_arg


def test_open_url_returns_url_in_data():
    from tools.browser import open_url
    with patch("subprocess.Popen"), patch("sys.platform", "linux"):
        result = open_url("https://github.com")
    assert result.data["url"] == "https://github.com"


def test_open_url_opens_chrome():
    from tools.browser import open_url
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_url("https://www.google.com")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "chrome" in call_arg.lower()


# ---------------------------------------------------------------------------
# open_search
# ---------------------------------------------------------------------------

def test_open_search_encodes_query():
    from tools.browser import open_search
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_search("entry level software engineer jobs")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "google.com/search" in call_arg
    assert "entry+level" in call_arg or "entry%20level" in call_arg


def test_open_search_with_site_restriction():
    from tools.browser import open_search
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_search("software engineer", site="linkedin.com")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "site%3Alinkedin.com" in call_arg or "site:linkedin.com" in call_arg


def test_open_search_success_message():
    from tools.browser import open_search
    with patch("subprocess.Popen"), patch("sys.platform", "linux"):
        result = open_search("tiktok careers entry level")
    assert result.success
    assert "tiktok careers entry level" in result.message


# ---------------------------------------------------------------------------
# open_site
# ---------------------------------------------------------------------------

def test_open_site_youtube():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_site("youtube")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "youtube.com" in call_arg


def test_open_site_indeed():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_site("indeed")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "indeed.com" in call_arg


def test_open_site_tiktok_careers():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_site("tiktok careers")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "tiktok" in call_arg.lower()


def test_open_site_partial_match():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_site("glass")  # partial match for "glassdoor"
    assert result.success


def test_open_site_unknown_falls_back_to_search():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_site("some_very_obscure_startup_xyz")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    # Should fall back to Google search
    assert "google.com" in call_arg


def test_open_site_google_careers():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen, patch("sys.platform", "linux"):
        result = open_site("google careers")
    assert result.success
    call_arg = mock_popen.call_args[0][0]
    assert "careers.google.com" in call_arg or "google" in call_arg.lower()
