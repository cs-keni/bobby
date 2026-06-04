"""Tests for tools/browser.py — URL opening and browser integration."""

from unittest.mock import patch


def _popen_url(mock_popen) -> str:
    """Extract the URL argument from a Popen call (last element of the list)."""
    return mock_popen.call_args[0][0][-1]


# ---------------------------------------------------------------------------
# open_url
# ---------------------------------------------------------------------------

def test_open_url_adds_https():
    from tools.browser import open_url
    with patch("subprocess.Popen") as mock_popen:
        result = open_url("www.youtube.com")
    assert result.success
    assert "https://www.youtube.com" in _popen_url(mock_popen)


def test_open_url_preserves_https():
    from tools.browser import open_url
    with patch("subprocess.Popen") as mock_popen:
        result = open_url("https://careers.tiktok.com")
    assert result.success
    assert "https://careers.tiktok.com" in _popen_url(mock_popen)


def test_open_url_returns_url_in_data():
    from tools.browser import open_url
    with patch("subprocess.Popen"):
        result = open_url("https://github.com")
    assert result.data["url"] == "https://github.com"


def test_open_url_opens_chrome():
    from tools.browser import open_url
    with patch("subprocess.Popen") as mock_popen:
        result = open_url("https://www.google.com")
    assert result.success
    # Array args: ["cmd.exe", "/c", "start", "chrome", url]
    args = mock_popen.call_args[0][0]
    assert "chrome" in args


def test_open_url_blocks_file_scheme():
    from tools.browser import open_url
    result = open_url("file:///C:/Windows/System32/cmd.exe")
    assert not result.success
    assert "Unsafe" in result.message


def test_open_url_blocks_javascript_scheme():
    from tools.browser import open_url
    result = open_url("javascript:alert(1)")
    assert not result.success


def test_open_url_uses_array_args_not_shell():
    """Confirm Popen is called with a list (not a shell string) to prevent injection."""
    from tools.browser import open_url
    with patch("subprocess.Popen") as mock_popen:
        open_url("https://example.com")
    args = mock_popen.call_args[0][0]
    assert isinstance(args, list), "Popen must be called with list args, not a shell string"
    assert "cmd.exe" in args[0]


# ---------------------------------------------------------------------------
# open_search
# ---------------------------------------------------------------------------

def test_open_search_encodes_query():
    from tools.browser import open_search
    with patch("subprocess.Popen") as mock_popen:
        result = open_search("entry level software engineer jobs")
    assert result.success
    url = _popen_url(mock_popen)
    assert "google.com/search" in url
    assert "entry+level" in url or "entry%20level" in url


def test_open_search_with_site_restriction():
    from tools.browser import open_search
    with patch("subprocess.Popen") as mock_popen:
        result = open_search("software engineer", site="linkedin.com")
    assert result.success
    url = _popen_url(mock_popen)
    assert "linkedin" in url


def test_open_search_success_message():
    from tools.browser import open_search
    with patch("subprocess.Popen"):
        result = open_search("tiktok careers entry level")
    assert result.success
    assert "tiktok careers entry level" in result.message


# ---------------------------------------------------------------------------
# open_site
# ---------------------------------------------------------------------------

def test_open_site_youtube():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen:
        result = open_site("youtube")
    assert result.success
    assert "youtube.com" in _popen_url(mock_popen)


def test_open_site_indeed():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen:
        result = open_site("indeed")
    assert result.success
    assert "indeed.com" in _popen_url(mock_popen)


def test_open_site_tiktok_careers():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen:
        result = open_site("tiktok careers")
    assert result.success
    assert "tiktok" in _popen_url(mock_popen).lower()


def test_open_site_partial_match():
    from tools.browser import open_site
    with patch("subprocess.Popen"):
        result = open_site("glass")  # partial match for "glassdoor"
    assert result.success


def test_open_site_unknown_falls_back_to_search():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen:
        result = open_site("some_very_obscure_startup_xyz")
    assert result.success
    assert "google.com" in _popen_url(mock_popen)


def test_open_site_google_careers():
    from tools.browser import open_site
    with patch("subprocess.Popen") as mock_popen:
        result = open_site("google careers")
    assert result.success
    url = _popen_url(mock_popen)
    assert "google" in url.lower()
