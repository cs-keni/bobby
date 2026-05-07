"""
Always-on wake word detection via Porcupine.
Fires a callback when "hey bobby" or "yo bobby" is detected.
"""

import struct
import threading
from typing import Callable

import pvporcupine
import sounddevice as sd

from core import config
from core.logging import get_logger

log = get_logger(__name__)

# Built-in Porcupine keywords closest to our wake words.
# For a custom "hey bobby" keyword, generate a .ppn at picovoice.io/console
# and set wake_word_path in config.yaml.
DEFAULT_KEYWORDS = ["hey siri", "ok google"]  # placeholder until custom ppn is generated
FRAME_LENGTH = 512


class WakeWordDetector:
    def __init__(self, on_wake: Callable):
        self.on_wake = on_wake
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        access_key = config.require("porcupine_access_key")
        ppn_path = config.get("wake_word_path")

        if ppn_path:
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=[ppn_path],
            )
            log.info(f"Wake word loaded from: {ppn_path}")
        else:
            # Fall back to built-in "porcupine" keyword until custom ppn is ready
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=["porcupine"],
            )
            log.warning(
                "No custom wake word configured — using 'porcupine' as placeholder. "
                "Generate your 'hey bobby' .ppn at picovoice.io/console"
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
        self._porcupine.delete()
        log.info("Wake word detection stopped")

    def _listen_loop(self) -> None:
        frame_length = self._porcupine.frame_length
        sample_rate = self._porcupine.sample_rate

        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=frame_length,
        ) as stream:
            while not self._stop.is_set():
                data, _ = stream.read(frame_length)
                pcm = struct.unpack_from(f"{frame_length}h", bytes(data))
                result = self._porcupine.process(pcm)
                if result >= 0:
                    log.info("Wake word detected!")
                    self.on_wake()
