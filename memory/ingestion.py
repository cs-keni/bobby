"""Markdown chunker for Obsidian vault notes.

Splits notes by H2/H3 section headers with frontmatter stripping.
For flat notes (no H2/H3), returns the whole note as one chunk.

Used by:
- tools/obsidian.py: push new captures to gbrain immediately
- (future) core/pipeline.py: full vault-file retrieval instead of CLI snippets
"""
from dataclasses import dataclass, field


@dataclass
class Chunk:
    title: str          # section heading, or note title for flat notes
    content: str        # section body (no headers, no frontmatter)
    section_level: int  # 0 = whole note, 2 = H2, 3 = H3
    metadata: dict = field(default_factory=dict)  # frontmatter key-value pairs


def chunk_markdown(content: str, note_title: str = "") -> list[Chunk]:
    """Split markdown content into chunks by H2/H3 section headers.

    Strips YAML frontmatter first; metadata fields are attached to every
    chunk. Returns a single whole-note chunk for flat notes (no headers).
    Empty or whitespace-only notes return [].
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines()
    body_lines, metadata = _strip_frontmatter(lines)
    chunks = _split_on_headers(body_lines, note_title)

    # Attach frontmatter metadata to every chunk
    if metadata:
        for chunk in chunks:
            chunk.metadata = dict(metadata)

    return chunks


def _strip_frontmatter(lines: list[str]) -> tuple[list[str], dict]:
    """Remove YAML frontmatter (opening --- block) and parse key-value pairs.

    Returns (body_lines, metadata_dict). Handles missing or malformed frontmatter
    gracefully — always returns a valid body.
    """
    if not lines or lines[0].strip() != "---":
        return lines, {}

    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        # Opening --- with no closing --- — treat as body
        return lines, {}

    fm_lines = lines[1:end]
    body_lines = lines[end + 1:]

    metadata: dict = {}
    for line in fm_lines:
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, val = line.partition(":")
            metadata[key.strip()] = val.strip()

    return body_lines, metadata


def _split_on_headers(lines: list[str], note_title: str) -> list[Chunk]:
    """Split body lines into Chunk objects at H2/H3 boundaries.

    The first block of lines before any header is attached to section_level=0
    with note_title as title. If there are no H2/H3 headers, the whole body
    is returned as one flat chunk.
    """
    chunks: list[Chunk] = []
    current_title = note_title
    current_level = 0
    current_body: list[str] = []

    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            body = "\n".join(current_body).strip()
            if body:
                chunks.append(Chunk(title=current_title, content=body, section_level=current_level))
            level = 2 if line.startswith("## ") else 3
            current_title = line.lstrip("#").strip()
            current_level = level
            current_body = []
        else:
            current_body.append(line)

    body = "\n".join(current_body).strip()
    if body:
        chunks.append(Chunk(title=current_title, content=body, section_level=current_level))

    return chunks
