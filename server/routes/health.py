"""Health check endpoint."""

import time
from fastapi import APIRouter

router = APIRouter()
_start_time = time.time()


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "uptime_seconds": int(time.time() - _start_time)}
