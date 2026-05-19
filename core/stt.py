"""Speech-to-text via Whisper (local) with Deepgram cloud fallback."""

import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

from core import config
from core.logging import get_logger

log = get_logger(__name__)

_model = None  # whisper.Whisper, lazy-loaded on first transcription call
_model_lock = threading.Lock()

SAMPLE_RATE = 16_000
SILENCE_THRESHOLD = 0.01   # RMS below this = silence
SILENCE_DURATION = 1.2     # seconds of silence before stopping recording
MIN_AUDIO_DURATION = 0.3   # ignore clips shorter than this (avoids sending noise)
SPEECH_START_TIMEOUT = 3.0  # give up if no speech begins within this many seconds


def _load_model():
    """Load Whisper on first call. Heavy import deferred so tests can import stt without whisper."""
    global _model
    with _model_lock:
        if _model is None:
            import whisper
            model_name = config.get("whisper_model", "small")
            log.info(f"Loading Whisper model: {model_name}")
            _model = whisper.load_model(model_name)
    return _model


def transcribe(audio: np.ndarray) -> str:
    """Transcribe a numpy audio array. Returns empty string for silence/noise."""
    if len(audio) < SAMPLE_RATE * MIN_AUDIO_DURATION:
        return ""

    rms = float(np.sqrt(np.mean(audio**2)))
    if rms < SILENCE_THRESHOLD:
        log.debug("Audio is silence, skipping transcription")
        return ""

    model = _load_model()
    result = model.transcribe(audio.astype(np.float32), fp16=False, language="en")
    text = result.get("text", "").strip()
    log.debug(f"Transcribed: {text!r}")
    return text


def transcribe_from_bytes(audio_bytes: bytes, suffix: str = ".webm") -> str:
    """
    Transcribe audio from raw bytes (WebM/Opus from browser MediaRecorder, or any
    format ffmpeg can decode). Writes to a temp file then calls Whisper.
    Requires ffmpeg to be installed (already required by openai-whisper).
    """
    import os
    import tempfile

    if not audio_bytes:
        return ""

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        model = _load_model()
        result = model.transcribe(tmp_path, fp16=False, language="en")
        text = result.get("text", "").strip()
        log.debug(f"Transcribed from bytes: {text!r}")
        return text
    except Exception as e:
        log.warning(f"Whisper transcription from bytes failed: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def record_until_silence(on_speech_detected: Callable | None = None) -> np.ndarray:
    """
    Record audio from the microphone until silence is detected.

    Two independent timeouts:
    - SPEECH_START_TIMEOUT: give up if the user hasn't started speaking yet
    - 30s hard cap: stop even if the user is still talking (runaway guard)
    """
    frames: list[np.ndarray] = []
    silence_frames = 0
    silence_limit = int(SILENCE_DURATION * SAMPLE_RATE / 512)
    speech_started = False

    def callback(indata: np.ndarray, frame_count: int, time_info, status):
        nonlocal silence_frames, speech_started
        chunk = indata[:, 0].copy()
        frames.append(chunk)

        rms = float(np.sqrt(np.mean(chunk**2)))
        if rms > SILENCE_THRESHOLD:
            silence_frames = 0
            if not speech_started:
                speech_started = True
                if on_speech_detected:
                    on_speech_detected()
        else:
            silence_frames += 1

    stop_event = threading.Event()
    start_time = time.monotonic()

    def monitor():
        while not stop_event.is_set():
            if speech_started and silence_frames >= silence_limit:
                stop_event.set()
            elif not speech_started and (time.monotonic() - start_time) >= SPEECH_START_TIMEOUT:
                # Mic never triggered — give up rather than waiting 30s
                stop_event.set()
            stop_event.wait(0.05)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=512, callback=callback):
        stop_event.wait(timeout=30)  # hard cap: never record more than 30s

    monitor_thread.join(timeout=1)

    if not frames:
        return np.array([], dtype=np.float32)

    return np.concatenate(frames)
