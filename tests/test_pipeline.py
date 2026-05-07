"""
Phase 1 mandatory safety tests for the voice pipeline.
These must pass before Phase 2 ships.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from core.stt import transcribe, SAMPLE_RATE, SILENCE_THRESHOLD, MIN_AUDIO_DURATION


class TestSTTSilenceGating:
    """CRITICAL: silence and short audio must never reach Claude."""

    def test_empty_audio_returns_empty(self):
        audio = np.array([], dtype=np.float32)
        result = transcribe(audio)
        assert result == "", "Empty audio should return empty string"

    def test_short_audio_below_min_duration_returns_empty(self):
        # 0.1s clip — below MIN_AUDIO_DURATION of 0.3s
        short = np.zeros(int(SAMPLE_RATE * 0.1), dtype=np.float32)
        result = transcribe(short)
        assert result == "", "Sub-minimum audio should be rejected before transcription"

    def test_silent_audio_returns_empty(self):
        # Full-length but dead silence
        silence = np.zeros(int(SAMPLE_RATE * 1.0), dtype=np.float32)
        result = transcribe(silence)
        assert result == "", "Silent audio should return empty string without hitting Whisper"

    def test_near_silence_below_threshold_returns_empty(self):
        # RMS just under SILENCE_THRESHOLD — should be treated as silence
        rng = np.random.default_rng(42)
        near_silence = rng.normal(0, SILENCE_THRESHOLD * 0.5, int(SAMPLE_RATE * 1.0)).astype(np.float32)
        result = transcribe(near_silence)
        assert result == "", "Near-silence audio should be filtered before Whisper"


class TestBrainErrorHandling:
    """CRITICAL: Claude API failures must never crash Bobby."""

    def test_api_timeout_returns_graceful_message(self):
        import anthropic
        from core.brain import think

        with patch("core.brain._get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())
            mock_client_fn.return_value = mock_client

            text, tool_calls = think(
                user_message="open chrome",
                tools=[],
                conversation_history=[],
            )

        assert text != "", "Should return a fallback message, not empty string"
        assert tool_calls == [], "No tool calls on timeout"
        assert any(word in text.lower() for word in ["trouble", "try", "moment", "again"]), (
            f"Fallback message should indicate a problem: {text!r}"
        )

    def test_rate_limit_returns_graceful_message(self):
        import anthropic
        from core.brain import think

        with patch("core.brain._get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = anthropic.RateLimitError(
                message="rate limited", response=MagicMock(), body={}
            )
            mock_client_fn.return_value = mock_client

            text, tool_calls = think(
                user_message="open chrome",
                tools=[],
                conversation_history=[],
            )

        assert text != "", "Should return a fallback message on rate limit"
        assert tool_calls == []

    def test_generic_api_error_returns_graceful_message(self):
        import anthropic
        from core.brain import think

        with patch("core.brain._get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = anthropic.APIError(
                message="internal error", request=MagicMock(), body={}
            )
            mock_client_fn.return_value = mock_client

            text, tool_calls = think(
                user_message="open chrome",
                tools=[],
                conversation_history=[],
            )

        assert text != "", "Should return a fallback message on API error"
        assert tool_calls == []


class TestTTSFallback:
    """CRITICAL: ElevenLabs failure must not silence Bobby."""

    def test_elevenlabs_failure_falls_back_to_pyttsx3(self):
        from core.tts import speak

        # Force ElevenLabs to fail, pyttsx3 should take over
        with patch("core.tts._try_elevenlabs", return_value=False) as mock_el, \
             patch("core.tts._speak_fallback") as mock_fallback:

            speak("hello world")

            mock_el.assert_called_once_with("hello world")
            mock_fallback.assert_called_once_with("hello world")

    def test_empty_string_does_not_call_tts(self):
        from core.tts import speak

        with patch("core.tts._try_elevenlabs") as mock_el, \
             patch("core.tts._speak_fallback") as mock_fallback:

            speak("")
            speak("   ")

            mock_el.assert_not_called()
            mock_fallback.assert_not_called()
