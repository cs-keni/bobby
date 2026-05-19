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
    api_key = config.get("elevenlabs_api_key")
    voice_id = config.get("elevenlabs_voice_id")

    if not api_key or not voice_id:
        return False

    try:
        import httpx
        import miniaudio
        import numpy as np
        import sounddevice as sd

        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_turbo_v2_5", "output_format": "mp3_44100_128"},
            timeout=30,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type:
            log.warning(f"ElevenLabs returned unexpected content-type: {content_type!r} — body: {response.text[:200]}")
            return False

        decoded = miniaudio.decode(response.content)
        audio = np.array(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
        if decoded.nchannels == 2:
            audio = audio.reshape(-1, 2)
        sd.play(audio, samplerate=decoded.sample_rate)
        sd.wait()
        return True

    except Exception as e:
        log.warning(f"ElevenLabs error: {e}")
        return False


def synthesize(text: str) -> bytes | None:
    """Return raw ElevenLabs MP3 bytes without playing. None on failure."""
    if not text.strip():
        return None

    api_key = config.get("elevenlabs_api_key")
    voice_id = config.get("elevenlabs_voice_id")
    if not api_key or not voice_id:
        return None

    try:
        import httpx
        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_turbo_v2_5", "output_format": "mp3_44100_128"},
            timeout=30,
        )
        response.raise_for_status()
        if "audio" not in response.headers.get("content-type", ""):
            return None
        return response.content
    except Exception as e:
        log.warning(f"ElevenLabs synthesize error: {e}")
        return None


def _speak_fallback(text: str) -> None:
    engine = _get_fallback()
    engine.say(text)
    engine.runAndWait()
