"""Bobby WebSocket endpoint — streams pipeline state to connected clients."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from core import config, events

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    expected = config.get("server_token", "")
    if not expected or token != expected:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    events.set_event_loop(asyncio.get_event_loop())
    q = events.subscribe()

    try:
        # Send state snapshot immediately so a late-joining client isn't blank
        snapshot = events.get_current_state()
        snapshot["timestamp"] = datetime.now(timezone.utc).isoformat()
        await websocket.send_json(snapshot)

        while True:
            payload = await q.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        events.unsubscribe(q)
