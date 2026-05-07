"""Speech-to-text via Whisper (local) with Deepgram cloud fallback."""

import io
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
import whisper

from core import config
from core.logging import get_logger

log = get_logger(__name__)

_model: whisper.Whisper | None = None
_model_lock = threading.Lock()

SAMPLE_RATE = 16_000
SILENCE_THRESHOLD = 0.01   # RMS below this = silence
SILENCE_DURATION = 1.2     # seconds of silence before stopping recording
MIN_AUDIO_DURATION = 0.3   # ignore clips shorter than this (avoids sending noise)


def _load_model() -> whisper.Whisper:
    global _model
    with _model_lock:
        if _model is None:
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
    text = result["text"].strip()
    log.debug(f"Transcribed: {text!r}")
    return text


def record_until_silence(on_speech_detected: Callable | None = None) -> np.ndarray:
    """
    Record audio from the microphone until silence is detected.
    Returns the recorded audio as a numpy array.
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

    def monitor():
        while not stop_event.is_set():
            if speech_started and silence_frames >= silence_limit:
                stop_event.set()
            stop_event.wait(0.05)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=512, callback=callback):
        stop_event.wait(timeout=30)  # max 30 seconds per utterance

    monitor_thread.join(timeout=1)

    if not frames:
        return np.array([], dtype=np.float32)

    return np.concatenate(frames)
