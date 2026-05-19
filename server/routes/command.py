"""
Command endpoints:
  POST /api/command  — text command → response + optional audio
  POST /api/voice    — audio upload → transcribe → respond
"""

import asyncio
import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from server.auth import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])


class CommandRequest(BaseModel):
    text: str
    return_audio: bool = True


@router.post("/command")
async def command(req: CommandRequest) -> dict:
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="text cannot be empty")

    from core.pipeline import process_text_command
    result = await asyncio.to_thread(process_text_command, req.text, req.return_audio)

    audio_b64 = (
        base64.b64encode(result["audio_bytes"]).decode()
        if result["audio_bytes"]
        else None
    )
    return {"ok": True, "response": result["response"], "audio_b64": audio_b64}


@router.post("/voice")
async def voice(audio: UploadFile = File(...)) -> dict:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Audio file is empty")

    # Determine the file extension from the content type for Whisper/ffmpeg
    content_type = audio.content_type or "audio/webm"
    ext = _ext_from_content_type(content_type)

    from core.stt import transcribe_from_bytes
    text = await asyncio.to_thread(transcribe_from_bytes, audio_bytes, ext)

    if not text:
        return {"ok": False, "error": "Could not transcribe audio — speak clearly and try again"}

    from core.pipeline import process_text_command
    result = await asyncio.to_thread(process_text_command, text, True)

    audio_b64 = (
        base64.b64encode(result["audio_bytes"]).decode()
        if result["audio_bytes"]
        else None
    )
    return {
        "ok": True,
        "transcription": text,
        "response": result["response"],
        "audio_b64": audio_b64,
    }


def _ext_from_content_type(content_type: str) -> str:
    mapping = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/wave": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".mp4",
        "audio/aac": ".aac",
        "audio/flac": ".flac",
    }
    for mime, ext in mapping.items():
        if mime in content_type:
            return ext
    return ".webm"
