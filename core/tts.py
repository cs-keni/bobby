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


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting so TTS reads clean prose instead of symbols."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)            # **bold**
    text = re.sub(r'\*(.+?)\*', r'\1', text)                 # *italic*
    text = re.sub(r'__(.+?)__', r'\1', text)                 # __bold__
    text = re.sub(r'_(.+?)_', r'\1', text)                   # _italic_
    text = re.sub(r'`(.+?)`', r'\1', text)                   # `code`
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # ## headers
    text = re.sub(r'\[(.+?)\]\([^)]*\)', r'\1', text)        # [link](url)
    text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)   # bullet points
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)   # numbered lists
    text = re.sub(r'-{3,}', '', text)                         # --- horizontal rules
    text = re.sub(r'\n{2,}', '. ', text)                      # blank lines → sentence break
    text = re.sub(r'\n', ' ', text)                           # single newlines → space
    return text.strip()


def speak(text: str) -> None:
    """Speak text aloud. Strips markdown, then streams ElevenLabs; falls back to pyttsx3."""
    if not text.strip():
        return

    text = _strip_markdown(text)
    if _try_elevenlabs(text):
        return

    log.warning("ElevenLabs unavailable, using pyttsx3 fallback")
    _speak_fallback(text)


def _play_mp3(mp3_bytes: bytes) -> None:
    """Play MP3 bytes via ffplay → PulseAudio (WSL2-safe, no PortAudio needed)."""
    import subprocess
    volume = int(config.get("tts_volume", 50))
    proc = subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-f", "mp3", "-i", "pipe:0",
         "-volume", str(volume), "-loglevel", "quiet"],
        stdin=subprocess.PIPE,
    )
    try:
        proc.communicate(input=mp3_bytes, timeout=20)
    except subprocess.TimeoutExpired:
        log.warning("ffplay timed out — killing (PulseAudio may have dropped)")
        proc.kill()
        proc.communicate()


def _try_elevenlabs(text: str) -> bool:
    api_key = config.get("elevenlabs_api_key")
    voice_id = config.get("elevenlabs_voice_id")

    if not api_key or not voice_id:
        return False

    try:
        import httpx

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

        _play_mp3(response.content)
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
    import sys
    if sys.platform != "win32":
        # pyttsx3 has no audio output in WSL2 and hangs on runAndWait()
        log.warning("pyttsx3 fallback skipped (WSL2 — no audio backend)")
        return
    engine = _get_fallback()
    engine.say(text)
    engine.runAndWait()
