"""Speech-to-text via Whisper (local) with Deepgram cloud fallback.

Audio capture uses parecord (PulseAudio) rather than sounddevice/PortAudio
because conda's libportaudio only has ALSA support, which has no devices in WSL2.
"""

import subprocess
import threading
import time
from typing import Callable

import numpy as np

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

_CHUNK_SAMPLES = 512
_BYTES_PER_CHUNK = _CHUNK_SAMPLES * 2  # int16


def _parecord_cmd() -> list[str]:
    cmd = ["parecord", "--rate=16000", "--channels=1", "--format=s16le", "--raw"]
    device = config.get("audio_device", "")
    if device:
        cmd.append(f"--device={device}")
    return cmd


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
    silence_limit = int(SILENCE_DURATION * SAMPLE_RATE / _CHUNK_SAMPLES)
    speech_started = False
    stop_event = threading.Event()
    start_time = time.monotonic()

    def _record():
        nonlocal silence_frames, speech_started
        cmd = _parecord_cmd()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while not stop_event.is_set():
                data = proc.stdout.read(_BYTES_PER_CHUNK)
                if len(data) < _BYTES_PER_CHUNK:
                    break
                # Normalize int16 → float32 in [-1, 1]
                chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
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

                if speech_started and silence_frames >= silence_limit:
                    stop_event.set()
                elif not speech_started and (time.monotonic() - start_time) >= SPEECH_START_TIMEOUT:
                    stop_event.set()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    record_thread = threading.Thread(target=_record, daemon=True)
    record_thread.start()
    stop_event.wait(timeout=30)
    stop_event.set()
    record_thread.join(timeout=3)

    if not frames:
        return np.array([], dtype=np.float32)

    return np.concatenate(frames)
