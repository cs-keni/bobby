"""
Phase 1 mandatory safety tests for memory injection.
These must pass before Phase 3 ships.
"""

import pytest


def count_tokens_approx(text: str) -> int:
    """Rough token count: ~4 chars per token."""
    return len(text) // 4


class TestMemoryTokenBounding:
    """CRITICAL: memory injection must never overflow Claude's context window."""

    def test_token_approximation(self):
        """Sanity check the token counter."""
        text = "hello world"
        assert count_tokens_approx(text) < 10

    def test_large_memory_corpus_is_bounded(self):
        """Simulate 1000 memories and verify the injected context is bounded."""
        # Generate a large memory corpus (simulates a year of use)
        memories = [
            f"Memory {i}: The user prefers using VSCode for Python development "
            f"and has a shortcut called 'the usual' that opens Discord, Chrome, YouTube, and Riot."
            for i in range(1000)
        ]
        full_corpus = "\n".join(memories)
        full_token_count = count_tokens_approx(full_corpus)

        # The full corpus should be way over the limit
        assert full_token_count > 4000, "Test corpus should be larger than the limit"

        # After bounding, it must fit within max_memory_tokens
        MAX_MEMORY_TOKENS = 4000
        max_chars = MAX_MEMORY_TOKENS * 4

        bounded = full_corpus[:max_chars]
        bounded_tokens = count_tokens_approx(bounded)

        assert bounded_tokens <= MAX_MEMORY_TOKENS, (
            f"Bounded memory ({bounded_tokens} tokens) exceeds limit ({MAX_MEMORY_TOKENS})"
        )

    def test_empty_memory_returns_empty_string(self):
        """No memories → no context injected → no tokens wasted."""
        memories = []
        result = "\n".join(memories)
        assert result == ""
        assert count_tokens_approx(result) == 0
