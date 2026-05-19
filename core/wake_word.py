"""
Always-on wake word detection via OpenWakeWord (open source, no API key required).
Fires a callback when the configured wake phrase is detected.

Audio capture uses parecord (PulseAudio) instead of sounddevice/PortAudio because
conda's libportaudio is compiled against ALSA only, which has no devices in WSL2.
WSLg exposes a PulseAudio socket at /mnt/wslg/PulseServer that parecord can reach.

Default placeholder: "hey jarvis" — same rhythm as "hey bobby".
To train a custom "hey bobby" model:
  https://github.com/dscripka/openWakeWord#custom-models
Then set wake_word_path in config.yaml to point to your .onnx file.
"""

import os
import subprocess
import threading
from typing import Callable

import numpy as np
from openwakeword.model import Model

from core import config
from core.logging import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 16_000
CHUNK_SIZE = 1280       # 80ms at 16kHz — OpenWakeWord's native frame size
DETECTION_THRESHOLD = 0.5
_BYTES_PER_CHUNK = CHUNK_SIZE * 2  # int16 = 2 bytes per sample


def _resolve_model_path(model_name: str) -> str:
    """Resolve a model name to an ONNX file path, bundled or cached."""
    cache = os.path.expanduser(f"~/.cache/openwakeword/{model_name}.onnx")
    if os.path.exists(cache):
        return cache

    bundled = os.path.join(
        os.path.dirname(__import__("openwakeword").__file__),
        "resources", "models", f"{model_name}_v0.1.onnx",
    )
    if os.path.exists(bundled):
        return bundled

    raise FileNotFoundError(
        f"Wake word model '{model_name}' not found. "
        "Set wake_word_path in config.yaml to point to your .onnx file."
    )


def _parecord_cmd() -> list[str]:
    """Build parecord command for 16kHz mono s16le raw capture."""
    cmd = ["parecord", "--rate=16000", "--channels=1", "--format=s16le", "--raw"]
    device = config.get("audio_device", "")
    if device:
        cmd.append(f"--device={device}")
    return cmd


class WakeWordDetector:
    def __init__(self, on_wake: Callable):
        self.on_wake = on_wake
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        custom_path = config.get("wake_word_path")
        wake_model = config.get("wake_word_model", "hey_jarvis")

        if custom_path:
            model_path = custom_path
            log.info(f"Custom wake word model: {custom_path}")
        else:
            model_path = _resolve_model_path(wake_model)
            log.warning(
                f"Using '{wake_model}' as wake phrase — say '{wake_model.replace('_', ' ')}' to trigger Bobby. "
                "Train a custom 'hey bobby' model and set wake_word_path in config.yaml when ready."
            )

        self._model = Model(wakeword_model_paths=[model_path])
        log.info(f"Wake word model loaded: {model_path}")

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Wake word detection started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        log.info("Wake word detection stopped")

    def _listen_loop(self) -> None:
        cmd = _parecord_cmd()
        log.debug(f"Starting audio capture: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while not self._stop.is_set():
                data = proc.stdout.read(_BYTES_PER_CHUNK)
                if len(data) < _BYTES_PER_CHUNK:
                    log.warning("parecord stream ended unexpectedly")
                    break
                audio = np.frombuffer(data, dtype=np.int16)
                predictions = self._model.predict(audio)

                for _, score in predictions.items():
                    if score >= DETECTION_THRESHOLD:
                        log.info(f"Wake word detected! (confidence: {score:.2f})")
                        self._model.reset()
                        self.on_wake()
                        break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
