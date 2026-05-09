"""
Phase 3 tests: memory/db.py and tools/memory.py
"""

import pytest


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    import memory.db as db
    monkeypatch.setattr(db, "_db_path", lambda: tmp_path / "memory.db")
    yield tmp_path / "memory.db"


# ── memory/db.py tests ──────────────────────────────────────────────────────


def test_save_and_get_fact(tmp_db):
    from memory.db import save_fact, get_fact
    save_fact("name", "Alice")
    assert get_fact("name") == "Alice"


def test_save_fact_upsert(tmp_db):
    from memory.db import save_fact, get_fact
    save_fact("name", "Alice")
    save_fact("name", "Bob")
    assert get_fact("name") == "Bob"


def test_delete_fact(tmp_db):
    from memory.db import save_fact, get_fact, delete_fact
    save_fact("color", "blue")
    assert delete_fact("color") is True
    assert get_fact("color") is None


def test_delete_missing_fact(tmp_db):
    from memory.db import delete_fact
    assert delete_fact("nonexistent") is False


def test_list_facts_all(tmp_db):
    from memory.db import save_fact, list_facts
    save_fact("a", "1")
    save_fact("b", "2")
    save_fact("c", "3")
    facts = list_facts()
    assert len(facts) == 3


def test_list_facts_filtered(tmp_db):
    from memory.db import save_fact, list_facts
    save_fact("browser", "chrome")
    save_fact("editor", "vscode")
    save_fact("hobby", "gaming")
    results = list_facts("chrome")
    assert len(results) == 1
    assert results[0]["key"] == "browser"


def test_get_memory_context_empty(tmp_db):
    from memory.db import get_memory_context
    assert get_memory_context() == ""


def test_get_memory_context_format(tmp_db):
    from memory.db import save_fact, get_memory_context
    save_fact("name", "Alice")
    ctx = get_memory_context()
    assert ctx.startswith("Bobby's memory about the user:")
    assert "[name]: Alice" in ctx


def test_get_memory_context_token_bounded(tmp_db, monkeypatch):
    import memory.db as db
    from memory.db import save_fact, get_memory_context

    monkeypatch.setattr(db, "_db_path", lambda: tmp_db.parent / "memory.db")

    # Each fact is ~80 chars; 600 facts ≈ 48000 chars >> 4000*4=16000 cap
    for i in range(600):
        save_fact(f"key_{i:04d}", f"value_that_is_moderately_long_to_fill_space_{i}")

    ctx = get_memory_context()
    assert len(ctx) <= 4000 * 4


def test_get_memory_context_no_mid_key_cut(tmp_db, monkeypatch):
    import memory.db as db
    from memory.db import save_fact, get_memory_context

    monkeypatch.setattr(db, "_db_path", lambda: tmp_db.parent / "memory.db")

    for i in range(600):
        save_fact(f"key_{i:04d}", f"value_that_is_moderately_long_to_fill_space_{i}")

    ctx = get_memory_context()
    # If there was a mid-line cut, the last char of a line would be a dangling `[`
    # Verify no line ends with just `[`
    lines = ctx.splitlines()
    assert not any(line.rstrip() == "[" for line in lines)
    # Also verify no line contains an orphaned `[` at end (incomplete key)
    last_line = lines[-1] if lines else ""
    assert not last_line.endswith("[")


def test_save_turn_and_get_history(tmp_db):
    from memory.db import save_turn, get_recent_history
    sid = "test_session"
    save_turn(sid, "user", "hello")
    save_turn(sid, "assistant", "hi there")
    save_turn(sid, "user", "how are you")
    history = get_recent_history(sid)
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"
    assert history[1]["role"] == "assistant"
    assert history[2]["content"] == "how are you"


# ── tools/memory.py tests ───────────────────────────────────────────────────


def test_remember_fact_tool(tmp_db):
    import memory.db as db
    from tools.memory import remember_fact
    result = remember_fact("pet", "dog")
    assert result.success is True
    assert "dog" in result.message


def test_recall_facts_tool_empty(tmp_db):
    from tools.memory import recall_facts
    result = recall_facts()
    assert result.success is True
    assert result.message == "Nothing stored yet."


def test_recall_facts_tool_with_results(tmp_db):
    from memory.db import save_fact
    from tools.memory import recall_facts
    save_fact("drink", "coffee")
    save_fact("food", "pizza")
    result = recall_facts()
    assert result.success is True
    assert "drink" in result.message
    assert "coffee" in result.message


def test_forget_fact_tool_success(tmp_db):
    from memory.db import save_fact
    from tools.memory import forget_fact
    save_fact("temp", "value")
    result = forget_fact("temp")
    assert result.success is True
    assert "temp" in result.message


def test_forget_fact_tool_missing(tmp_db):
    from tools.memory import forget_fact
    result = forget_fact("ghost")
    assert result.success is False
    assert "ghost" in result.message
