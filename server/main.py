"""
Bobby FastAPI server — phone bridge + remote API.

Endpoints:
  GET  /api/health          — liveness check (no auth)
  POST /api/command         — text command (auth required)
  POST /api/voice           — audio upload (auth required)
  GET  /                    — React PWA (served from phone/dist/)
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.routes import health, command

app = FastAPI(title="Bobby", version="1.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(command.router, prefix="/api")

# Serve the built React PWA as the root if it exists.
# During development the Vite dev server handles this instead.
_phone_dist = os.path.join(os.path.dirname(__file__), "..", "phone", "dist")
if os.path.isdir(_phone_dist):
    app.mount("/", StaticFiles(directory=_phone_dist, html=True), name="phone")
