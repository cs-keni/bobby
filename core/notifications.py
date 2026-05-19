"""Shared notification queue — background threads post here, pipeline drains it."""
import queue

_tts_queue: queue.Queue[str] = queue.Queue()
