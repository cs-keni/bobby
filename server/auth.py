"""Bearer token authentication dependency for Bobby's FastAPI server."""

from fastapi import Header, HTTPException
from core import config


async def verify_token(authorization: str = Header(...)) -> None:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")

    token = authorization.removeprefix("Bearer ").strip()
    expected = config.get("server_token", "")

    if not expected:
        raise HTTPException(status_code=500, detail="server_token not configured")
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid token")
