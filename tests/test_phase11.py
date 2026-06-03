"""Phase 11 tests: tools/obsidian.py and core/brain.py vault_context."""

import pytest
from unittest.mock import patch, MagicMock


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def obsidian_enabled(monkeypatch):
    """Enable Obsidian for all tests in this module."""
    import core.config as cfg
    original_get = cfg.get

    def patched_get(key, default=None):
        if key == "obsidian.enabled":
            return True
        if key == "obsidian.api_key":
            return "test-key"
        if key == "obsidian.api_host":
            return "127.0.0.1"
        if key == "obsidian.api_port":
            return 27123
        if key == "obsidian.inbox_folder":
            return "Inbox"
        if key == "obsidian.index_file":
            return "VAULT_INDEX.md"
        if key == "obsidian.max_index_tokens":
            return 3000
        return original_get(key, default)

    monkeypatch.setattr(cfg, "get", patched_get)


def _mock_response(status_code=200, json_data=None, text=""):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.text = text
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock
        )
    return mock


# ── capture_to_obsidian ──────────────────────────────────────────────────────


def test_capture_disabled_returns_error(monkeypatch):
    import core.config as cfg
    monkeypatch.setattr(cfg, "get", lambda key, default=None: False if key == "obsidian.enabled" else default)
    from tools.obsidian import capture_to_obsidian
    result = capture_to_obsidian(text="test note")
    assert not result.success
    assert "enabled" in result.message.lower()


def test_capture_happy_path():
    with patch("httpx.put", return_value=_mock_response(200)) as mock_put, \
         patch("httpx.get", return_value=_mock_response(404)):  # no index yet
        from tools.obsidian import capture_to_obsidian
        result = capture_to_obsidian(text="look into WebRTC")
    assert result.success
    assert "Inbox/" in result.data["path"]
    mock_put.assert_called_once()
    body = mock_put.call_args.kwargs.get("content", b"").decode()
    assert "look into WebRTC" in body


def test_capture_with_tags():
    with patch("httpx.put", return_value=_mock_response(200)), \
         patch("httpx.get", return_value=_mock_response(404)):
        from tools.obsidian import capture_to_obsidian
        result = capture_to_obsidian(text="tagged note", tags=["project", "idea"])
    assert result.success


def test_capture_unreachable():
    import httpx
    with patch("httpx.put", side_effect=httpx.ConnectError("refused")):
        from tools.obsidian import capture_to_obsidian
        result = capture_to_obsidian(text="test")
    assert not result.success
    assert "open it" in result.message.lower() or "obsidian" in result.message.lower()


def test_capture_appends_to_index_when_exists():
    existing_index = "# Bobby's Vault Index\n\n## Recent Captures\n"
    with patch("httpx.put", return_value=_mock_response(200)) as mock_put, \
         patch("httpx.get", return_value=_mock_response(200, text=existing_index)):
        from tools.obsidian import capture_to_obsidian
        capture_to_obsidian(text="my captured thought")
    # put called twice: once for the note, once for the index update
    assert mock_put.call_count == 2
    index_put = mock_put.call_args_list[1]
    updated = index_put.kwargs.get("content", b"").decode()
    assert "my captured thought" in updated


def test_capture_skips_index_when_missing():
    with patch("httpx.put", return_value=_mock_response(200)) as mock_put, \
         patch("httpx.get", return_value=_mock_response(404)):
        from tools.obsidian import capture_to_obsidian
        result = capture_to_obsidian(text="no index yet")
    assert result.success
    assert mock_put.call_count == 1  # only the note, no index update


# ── read_obsidian_note ───────────────────────────────────────────────────────


def test_read_happy_path():
    with patch("httpx.get", return_value=_mock_response(200, text="# My Note\n\nContent here.")):
        from tools.obsidian import read_obsidian_note
        result = read_obsidian_note(path="Inbox/my-note.md")
    assert result.success
    assert "<data>" in result.message
    assert "Content here." in result.message


def test_read_not_found():
    with patch("httpx.get", return_value=_mock_response(404)):
        from tools.obsidian import read_obsidian_note
        result = read_obsidian_note(path="Inbox/missing.md")
    assert not result.success
    assert "not found" in result.message.lower()


@pytest.mark.parametrize("bad_path", [
    "../etc/passwd",
    "/absolute/path.md",
    "some/%2e%2e/escape.md",
    "notes/%2f/traversal.md",
])
def test_read_path_traversal_rejected(bad_path):
    from tools.obsidian import read_obsidian_note
    result = read_obsidian_note(path=bad_path)
    assert not result.success
    assert "invalid" in result.message.lower()


# ── search_obsidian ──────────────────────────────────────────────────────────


def test_search_happy_path():
    hits = [{"filename": "notes/animation.md"}, {"filename": "notes/spring.md"}]
    with patch("httpx.post", return_value=_mock_response(200, json_data=hits)):
        from tools.obsidian import search_obsidian
        result = search_obsidian(query="animation")
    assert result.success
    assert len(result.data["results"]) == 2
    assert "animation.md" in result.message


def test_search_no_results():
    with patch("httpx.post", return_value=_mock_response(200, json_data=[])):
        from tools.obsidian import search_obsidian
        result = search_obsidian(query="nonexistent topic")
    assert result.success
    assert result.data["results"] == []
    assert "no notes" in result.message.lower()


def test_search_unreachable():
    import httpx
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        from tools.obsidian import search_obsidian
        result = search_obsidian(query="anything")
    assert not result.success


# ── brain.py vault_context ───────────────────────────────────────────────────


def test_think_without_vault_context_uses_list_system():
    # system is always list[dict] — allows safe append in Phase C personality injection
    from core.brain import think
    with patch("core.brain._get_client") as mock_client_fn:
        mock_response = MagicMock()
        mock_response.content = []
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_client_fn.return_value = mock_client

        think(user_message="hello", tools=[], conversation_history=[])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert isinstance(call_kwargs["system"], list)
        assert len(call_kwargs["system"]) == 1
        assert call_kwargs["system"][0]["type"] == "text"


def test_think_with_vault_context_uses_block_system():
    from core.brain import think
    with patch("core.brain._get_client") as mock_client_fn:
        mock_response = MagicMock()
        mock_response.content = []
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_client_fn.return_value = mock_client

        think(
            user_message="hello",
            tools=[],
            conversation_history=[],
            vault_context="## Topics\n- animation\n",
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert isinstance(call_kwargs["system"], list)
        assert len(call_kwargs["system"]) == 2
        assert call_kwargs["system"][1]["type"] == "text"
        assert "VAULT CONTEXT" in call_kwargs["system"][1]["text"]


# ── _do_build_index (full implementation) ───────────────────────────────────


def test_build_index_includes_section_titles():
    """Notes with H2/H3 sections get per-section preview lines in the index."""
    sectioned = "# Concept Note\n\n## Section A\nContent A here.\n\n## Section B\nContent B here."
    flat = "# Flat Note\n\nJust plain text with no headers."

    def _fake_get(url, **kwargs):
        if url.endswith("/vault/"):
            return _mock_response(200, json_data={"files": ["notes/concept.md", "notes/flat.md"]})
        if "concept.md" in url:
            return _mock_response(200, text=sectioned)
        if "flat.md" in url:
            return _mock_response(200, text=flat)
        return _mock_response(404)

    with patch("httpx.get", side_effect=_fake_get), \
         patch("httpx.put", return_value=_mock_response(200)) as mock_put:
        from tools.obsidian import _do_build_index
        _do_build_index()

    mock_put.assert_called_once()
    written = mock_put.call_args.kwargs["content"].decode()
    assert "notes/concept.md" in written
    assert "Section A" in written
    assert "Section B" in written
    assert "notes/flat.md" in written
    assert "Just plain text" in written


def test_build_index_empty_vault_writes_gracefully():
    with patch("httpx.get", return_value=_mock_response(200, json_data={"files": []})), \
         patch("httpx.put", return_value=_mock_response(200)) as mock_put:
        from tools.obsidian import _do_build_index
        _do_build_index()

    mock_put.assert_called_once()
    written = mock_put.call_args.kwargs["content"].decode()
    assert "Notes: 0" in written
    assert "Sections: 0" in written
    assert "## Recent Captures" in written


def test_build_index_h3_sections_appear():
    """H3 sub-sections are indented with ### prefix in the index."""
    deep = "# Deep Note\n\n## Top Section\nIntro.\n\n### Sub A\nDetail A.\n\n### Sub B\nDetail B."

    def _fake_get(url, **kwargs):
        if url.endswith("/vault/"):
            return _mock_response(200, json_data={"files": ["notes/deep.md"]})
        return _mock_response(200, text=deep)

    with patch("httpx.get", side_effect=_fake_get), \
         patch("httpx.put", return_value=_mock_response(200)) as mock_put:
        from tools.obsidian import _do_build_index
        _do_build_index()

    written = mock_put.call_args.kwargs["content"].decode()
    assert "Top Section" in written
    assert "Sub A" in written
    assert "Sub B" in written


# ── core/config.py dotted-path accessor ─────────────────────────────────────


def test_config_dotted_path():
    from core.config import get
    assert get("obsidian.enabled") is True  # set by fixture
    assert get("obsidian.api_key") == "test-key"


def test_config_missing_dotted_path_returns_default():
    from core.config import get
    assert get("obsidian.nonexistent.key", "fallback") == "fallback"
