"""Shared WebSocket event bus — pipeline threads post here, WS clients subscribe."""

import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional

_subscribers: list[asyncio.Queue] = []
_lock = threading.Lock()
_loop: Optional[asyncio.AbstractEventLoop] = None

_current_state: dict = {"state": "idle", "text": "", "transcript": []}


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe() -> "asyncio.Queue[dict]":
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: "asyncio.Queue[dict]") -> None:
    with _lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


def get_current_state() -> dict:
    with _lock:
        return dict(_current_state)


def broadcast_state(state: str, text: str = "", transcript: list[str] | None = None) -> None:
    if transcript is None:
        transcript = []
    payload = {
        "state": state,
        "text": text,
        "transcript": transcript,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _current_state.update({"state": state, "text": text, "transcript": transcript})
        subscribers = list(_subscribers)

    if not _loop or not subscribers:
        return

    def _put(q: asyncio.Queue) -> None:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass

    for q in subscribers:
        _loop.call_soon_threadsafe(_put, q)
