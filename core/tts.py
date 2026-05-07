"""
Text-to-speech via ElevenLabs (streaming) with pyttsx3 local fallback.
Streams audio chunks as they arrive so Bobby starts speaking before the
full response is ready.
"""

import threading
from typing import Iterator

from core import config
from core.logging import get_logger

log = get_logger(__name__)

_fallback_engine = None
_fallback_lock = threading.Lock()


def _get_fallback():
    global _fallback_engine
    with _fallback_lock:
        if _fallback_engine is None:
            import pyttsx3
            _fallback_engine = pyttsx3.init()
            _fallback_engine.setProperty("rate", 175)
    return _fallback_engine


def speak(text: str) -> None:
    """Speak text aloud. Streams ElevenLabs chunks; falls back to pyttsx3."""
    if not text.strip():
        return

    if _try_elevenlabs(text):
        return

    log.warning("ElevenLabs unavailable, using pyttsx3 fallback")
    _speak_fallback(text)


def _try_elevenlabs(text: str) -> bool:
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import play, stream

        api_key = config.get("elevenlabs_api_key")
        voice_id = config.get("elevenlabs_voice_id")

        if not api_key or not voice_id:
            return False

        client = ElevenLabs(api_key=api_key)
        audio_stream = client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=voice_id,
            model_id="eleven_turbo_v2_5",
            output_format="mp3_44100_128",
        )
        stream(audio_stream)
        return True

    except Exception as e:
        log.warning(f"ElevenLabs error: {e}")
        return False


def _speak_fallback(text: str) -> None:
    engine = _get_fallback()
    engine.say(text)
    engine.runAndWait()
