"""
Always-on wake word detection via OpenWakeWord (open source, no API key required).
Fires a callback when the configured wake phrase is detected.

Default placeholder: "hey jarvis" — same rhythm as "hey bobby".
To train a custom "hey bobby" model:
  https://github.com/dscripka/openWakeWord#custom-models
Then set wake_word_path in config.yaml to point to your .onnx file.
"""

import threading
from typing import Callable

import numpy as np
import sounddevice as sd
import openwakeword.utils
from openwakeword.model import Model

from core import config
from core.logging import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 16_000
CHUNK_SIZE = 1280       # 80ms at 16kHz — OpenWakeWord's native frame size
DETECTION_THRESHOLD = 0.5


class WakeWordDetector:
    def __init__(self, on_wake: Callable):
        self.on_wake = on_wake
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        custom_path = config.get("wake_word_path")
        wake_model = config.get("wake_word_model", "hey_jarvis")

        # Download pre-trained models on first run (~10MB total, cached after)
        log.info("Checking wake word models...")
        openwakeword.utils.download_models()

        if custom_path:
            self._model = Model(wakeword_models=[custom_path], inference_framework="onnx")
            log.info(f"Custom wake word model loaded: {custom_path}")
        else:
            # Downloads ~2MB model file on first run (cached at ~/.cache/openwakeword/)
            self._model = Model(wakeword_models=[wake_model], inference_framework="onnx")
            log.warning(
                f"Using '{wake_model}' as wake phrase placeholder — say '{wake_model.replace('_', ' ')}' to trigger Bobby. "
                "Train a custom 'hey bobby' model and set wake_word_path in config.yaml when ready."
            )

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
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        ) as stream:
            while not self._stop.is_set():
                data, _ = stream.read(CHUNK_SIZE)
                audio = data[:, 0]
                predictions = self._model.predict(audio)

                for _, score in predictions.items():
                    if score >= DETECTION_THRESHOLD:
                        log.info(f"Wake word detected! (confidence: {score:.2f})")
                        self._model.reset()  # reset buffer so it doesn't re-trigger immediately
                        self.on_wake()
                        break
