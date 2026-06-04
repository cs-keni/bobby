"""WebSocket event bus and endpoint tests — T5 of Phase 12 UI."""

import asyncio
import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

import core.events as events
from server.main import app

TEST_TOKEN = "test-token-ws"


# ─── Event bus unit tests ─────────────────────────────────────────────────────

class TestEventBus:
    def setup_method(self):
        # Reset event bus state before each test
        with events._lock:
            events._subscribers.clear()
            events._current_state.update({"state": "idle", "text": "", "transcript": []})
            events._loop = None

    def test_get_current_state_returns_snapshot(self):
        state = events.get_current_state()
        assert state["state"] == "idle"
        assert state["text"] == ""
        # Mutating the returned dict does not affect internal state
        state["state"] = "hacked"
        assert events.get_current_state()["state"] == "idle"

    def test_subscribe_adds_queue(self):
        loop = asyncio.new_event_loop()
        events.set_event_loop(loop)
        q = asyncio.Queue.__new__(asyncio.Queue)
        # Use real subscribe
        q = events.subscribe()
        assert q in events._subscribers
        events.unsubscribe(q)
        loop.close()

    def test_unsubscribe_removes_queue(self):
        q = events.subscribe()
        events.unsubscribe(q)
        assert q not in events._subscribers

    def test_unsubscribe_nonexistent_does_not_raise(self):
        q = asyncio.Queue()
        events.unsubscribe(q)  # should not raise

    def test_broadcast_updates_current_state(self):
        events.broadcast_state("thinking", text="running a tool")
        state = events.get_current_state()
        assert state["state"] == "thinking"
        assert state["text"] == "running a tool"

    def test_broadcast_without_loop_does_not_crash(self):
        # _loop is None — broadcast should silently skip delivery
        events.broadcast_state("listening")
        assert events.get_current_state()["state"] == "listening"

    def test_broadcast_with_no_subscribers_does_not_crash(self):
        loop = asyncio.new_event_loop()
        events.set_event_loop(loop)
        events.broadcast_state("speaking", text="hello")  # no subscribers
        loop.close()

    def test_broadcast_delivers_to_subscriber(self):
        loop = asyncio.new_event_loop()
        events.set_event_loop(loop)

        async def _run():
            q = events.subscribe()
            events.broadcast_state("speaking", text="hi there")
            # Give call_soon_threadsafe a tick to execute
            await asyncio.sleep(0)
            payload = q.get_nowait()
            events.unsubscribe(q)
            return payload

        payload = loop.run_until_complete(_run())
        loop.close()
        assert payload["state"] == "speaking"
        assert payload["text"] == "hi there"
        assert "timestamp" in payload

    def test_broadcast_delivers_to_multiple_subscribers(self):
        loop = asyncio.new_event_loop()
        events.set_event_loop(loop)

        async def _run():
            q1 = events.subscribe()
            q2 = events.subscribe()
            events.broadcast_state("thinking")
            await asyncio.sleep(0)
            p1 = q1.get_nowait()
            p2 = q2.get_nowait()
            events.unsubscribe(q1)
            events.unsubscribe(q2)
            return p1, p2

        p1, p2 = loop.run_until_complete(_run())
        loop.close()
        assert p1["state"] == "thinking"
        assert p2["state"] == "thinking"

    def test_broadcast_full_queue_does_not_crash(self):
        """QueueFull on a maxed-out queue should be swallowed, not raised."""
        loop = asyncio.new_event_loop()
        events.set_event_loop(loop)

        async def _run():
            q = events.subscribe()
            # Fill the queue to capacity
            for _ in range(100):
                q.put_nowait({"state": "idle", "text": "", "transcript": [], "timestamp": "x"})
            # This should not raise even though queue is full
            events.broadcast_state("thinking")
            await asyncio.sleep(0)
            events.unsubscribe(q)

        loop.run_until_complete(_run())
        loop.close()


# ─── WebSocket endpoint tests ─────────────────────────────────────────────────

class TestWebSocketEndpoint:
    def setup_method(self):
        with events._lock:
            events._subscribers.clear()
            events._current_state.update({"state": "idle", "text": "", "transcript": []})

    def test_ws_invalid_token_closes_connection(self):
        with patch("core.config.get", side_effect=lambda k, d=None: TEST_TOKEN if k == "server_token" else d):
            with TestClient(app) as client:
                with pytest.raises(Exception):
                    with client.websocket_connect("/ws?token=wrong-token") as ws:
                        ws.receive_json()

    def test_ws_valid_token_receives_snapshot(self):
        with patch("core.config.get", side_effect=lambda k, d=None: TEST_TOKEN if k == "server_token" else d):
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws?token={TEST_TOKEN}") as ws:
                    snapshot = ws.receive_json()
                    assert snapshot["state"] == "idle"
                    assert "timestamp" in snapshot

    def test_ws_disconnect_cleans_up_subscription(self):
        with patch("core.config.get", side_effect=lambda k, d=None: TEST_TOKEN if k == "server_token" else d):
            initial_count = len(events._subscribers)
            with TestClient(app) as client:
                with client.websocket_connect(f"/ws?token={TEST_TOKEN}") as ws:
                    ws.receive_json()  # consume snapshot
                    mid_count = len(events._subscribers)
            # After disconnect, subscriber should be removed
            assert len(events._subscribers) == initial_count
            assert mid_count == initial_count + 1

    def test_ws_reconnect_works(self):
        with patch("core.config.get", side_effect=lambda k, d=None: TEST_TOKEN if k == "server_token" else d):
            with TestClient(app) as client:
                for _ in range(2):
                    with client.websocket_connect(f"/ws?token={TEST_TOKEN}") as ws:
                        snapshot = ws.receive_json()
                        assert snapshot["state"] == "idle"
