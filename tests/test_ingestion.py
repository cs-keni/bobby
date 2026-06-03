"""Tests for memory/ingestion.py — Markdown chunker."""
import pytest

from memory.ingestion import chunk_markdown, Chunk


# ---------------------------------------------------------------------------
# Flat notes (no H2/H3 headers) — whole-note fallback
# ---------------------------------------------------------------------------

def test_flat_note_returns_one_chunk():
    content = "This is a flat note with no headers.\n\nJust some text."
    chunks = chunk_markdown(content, note_title="My Note")
    assert len(chunks) == 1
    assert chunks[0].section_level == 0
    assert chunks[0].title == "My Note"
    assert "flat note" in chunks[0].content


def test_flat_note_uses_note_title():
    chunks = chunk_markdown("Some content.", note_title="The Title")
    assert chunks[0].title == "The Title"


def test_flat_note_empty_title_ok():
    chunks = chunk_markdown("Some content.")
    assert chunks[0].title == ""
    assert chunks[0].section_level == 0


def test_empty_content_returns_empty():
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n\n  ") == []


# ---------------------------------------------------------------------------
# H2 sections
# ---------------------------------------------------------------------------

def test_h2_sections_split_correctly():
    content = "## Overview\nThis is overview.\n\n## Details\nThis is details."
    chunks = chunk_markdown(content)
    assert len(chunks) == 2
    assert chunks[0].title == "Overview"
    assert chunks[0].section_level == 2
    assert "overview" in chunks[0].content.lower()
    assert chunks[1].title == "Details"
    assert chunks[1].section_level == 2


def test_h2_preamble_before_first_header_captured():
    content = "Intro paragraph before any header.\n\n## Section One\nBody of section one."
    chunks = chunk_markdown(content, note_title="My Note")
    assert len(chunks) == 2
    assert chunks[0].section_level == 0
    assert "Intro" in chunks[0].content
    assert chunks[1].title == "Section One"


def test_h2_empty_section_body_skipped():
    content = "## Section A\n\n## Section B\nHas content."
    chunks = chunk_markdown(content)
    assert len(chunks) == 1
    assert chunks[0].title == "Section B"


# ---------------------------------------------------------------------------
# H3 sections
# ---------------------------------------------------------------------------

def test_h3_sections_split_correctly():
    content = "### Sub One\nContent one.\n\n### Sub Two\nContent two."
    chunks = chunk_markdown(content)
    assert len(chunks) == 2
    assert chunks[0].section_level == 3
    assert chunks[1].section_level == 3


def test_mixed_h2_h3():
    content = (
        "## Big Section\nBig body.\n"
        "### Sub Section\nSub body.\n"
        "## Another Big\nAnother body."
    )
    chunks = chunk_markdown(content)
    assert len(chunks) == 3
    assert chunks[0].section_level == 2
    assert chunks[1].section_level == 3
    assert chunks[2].section_level == 2


# ---------------------------------------------------------------------------
# Frontmatter stripping
# ---------------------------------------------------------------------------

def test_frontmatter_stripped_from_body():
    content = "---\ncreated: 2026-06-03\ntags:\n  - idea\n---\n\nActual body text."
    chunks = chunk_markdown(content)
    assert len(chunks) == 1
    assert "created" not in chunks[0].content
    assert "Actual body text" in chunks[0].content


def test_frontmatter_metadata_attached_to_chunks():
    content = "---\ncreated: 2026-06-03\nauthor: Kenny\n---\n\n## Section\nBody."
    chunks = chunk_markdown(content)
    assert chunks[0].metadata["created"] == "2026-06-03"
    assert chunks[0].metadata["author"] == "Kenny"


def test_frontmatter_metadata_on_all_chunks():
    content = "---\ncreated: 2026-01-01\n---\n\n## A\nBody A.\n\n## B\nBody B."
    chunks = chunk_markdown(content)
    assert len(chunks) == 2
    for chunk in chunks:
        assert chunk.metadata.get("created") == "2026-01-01"


def test_note_with_only_frontmatter_returns_empty():
    content = "---\ncreated: 2026-06-03\n---\n"
    assert chunk_markdown(content) == []


def test_unclosed_frontmatter_treated_as_body():
    content = "---\ncreated: 2026-06-03\nno closing marker\nSome text."
    chunks = chunk_markdown(content)
    assert len(chunks) == 1
    assert "---" in chunks[0].content  # opening --- is in body


def test_no_frontmatter_returns_no_metadata():
    chunks = chunk_markdown("Just text with no frontmatter.", note_title="Note")
    assert chunks[0].metadata == {}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_h1_not_treated_as_section_boundary():
    content = "# Title\n\nSome content.\n\n## Real Section\nSection body."
    chunks = chunk_markdown(content)
    # H1 is NOT a split boundary — only H2/H3 are
    assert len(chunks) == 2
    assert "# Title" in chunks[0].content or "Title" in chunks[0].content
    assert chunks[1].title == "Real Section"


def test_h4_not_treated_as_section_boundary():
    content = "## Section\nBody with\n#### H4 subsection\nstill part of Section."
    chunks = chunk_markdown(content)
    assert len(chunks) == 1
    assert "H4 subsection" in chunks[0].content


def test_multiline_section_body_preserved():
    content = "## Section\nLine one.\nLine two.\n\nLine three after blank."
    chunks = chunk_markdown(content)
    assert "Line one" in chunks[0].content
    assert "Line two" in chunks[0].content
    assert "Line three" in chunks[0].content


def test_whitespace_only_note_returns_empty():
    assert chunk_markdown("\n\n\n") == []


def test_chunk_dataclass_defaults():
    chunk = Chunk(title="T", content="C", section_level=2)
    assert chunk.metadata == {}
