"""
Main Bobby pipeline: wake word → STT → Claude brain → TTS.
This is the entry point for running Bobby on PC.
"""

import re
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core import config
from core.brain import think
from core.logging import get_logger
from core.notifications import _tts_queue
from core.stt import record_until_silence, transcribe
from core.tool_result import ToolResult
from core.tts import speak
from core.wake_word import WakeWordDetector
from tools.registry import get_tools, dispatch_tool

log = get_logger(__name__)

# Conversation history for the current session
_history: list[dict] = []
_history_lock = threading.Lock()
_listening = threading.Event()
_speaking = threading.Event()

# Serializes command execution — prevents voice + API from running simultaneously
_processing_lock = threading.Lock()

_session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + str(uuid.uuid4())[:6]

HISTORY_MAX_TURNS = 20  # keep last N turns to avoid runaway context growth


def _on_wake() -> None:
    """Called by the wake word detector when the wake phrase is heard."""
    if _speaking.is_set():
        log.debug("Wake word during speech — ignoring (Bobby is talking)")
        return
    _listening.set()


def _play_chime(kind: str = "wake") -> None:
    """Play a subtle audio cue. kind: 'wake' | 'thinking' | 'done'"""
    # TODO Phase 1 polish: implement short audio cues
    pass


def _confirm_via_voice(command: str) -> bool:
    """Ask the user to verbally confirm a dangerous command. Returns True if confirmed."""
    speak(f"I need confirmation before running that. Say yes to proceed or no to cancel.")
    log.info(f"Awaiting voice confirmation for: {command}")
    confirm_audio = record_until_silence()
    confirm_text = transcribe(confirm_audio).lower().strip()
    confirmed = any(w in confirm_text for w in ["yes", "yeah", "yep", "confirm", "do it", "go ahead", "proceed", "sure"])
    if not confirmed:
        speak("Got it, cancelling.")
        log.info("User cancelled dangerous command")
    return confirmed


def _trim_history(history: list[dict]) -> list[dict]:
    """Trim history to HISTORY_MAX_TURNS, never cutting mid-tool-exchange."""
    if len(history) <= HISTORY_MAX_TURNS * 2:
        return history
    trimmed = list(history[-(HISTORY_MAX_TURNS * 2):])
    # Walk forward until we find a clean user-text message (not a tool_result list)
    while trimmed and not (
        trimmed[0]["role"] == "user"
        and isinstance(trimmed[0].get("content"), str)
    ):
        trimmed.pop(0)
    return trimmed


_GBRAIN_BIN = str(Path.home() / ".bun" / "bin" / "gbrain")


def _query_gbrain(user_text: str) -> str:
    """Query gbrain for vault context semantically relevant to user_text.

    Returns a formatted context string for injection into Bobby's system prompt,
    or "" on any failure (silent fallback — gbrain outage must never break Bobby).

    Skips the query for action-only commands (open, close, volume, etc.) where
    vault context adds no value and would only add latency.
    """
    if not config.get("gbrain.enabled", False):
        return ""

    text_lower = user_text.lower().strip()
    skip_patterns = config.get("gbrain.intent_skip_patterns", [])
    if any(text_lower.startswith(p.lower()) for p in skip_patterns):
        log.debug("gbrain skip: matched intent_skip_pattern")
        return ""

    try:
        top_k = config.get("gbrain.query_top_k", 5)
        max_chars = config.get("gbrain.max_context_tokens", 4000) * 4

        proc = subprocess.run(
            [_GBRAIN_BIN, "query", user_text, "--limit", str(top_k), "--source-id", "__all__"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if proc.returncode != 0 or not proc.stdout.strip():
            if proc.returncode != 0:
                log.debug(f"gbrain query exit {proc.returncode}: {proc.stderr[:100]}")
            return ""

        # CLI format: "[score] slug -- chunk_text\n[next result...]"
        # Chunk text may span multiple lines — split on lines that start a new result.
        blocks = re.split(r"\n(?=\[[\d.]+\])", proc.stdout.strip())
        parts: list[str] = []
        total_chars = 0

        for block in blocks:
            if " -- " not in block:
                continue
            header, chunk_text = block.split(" -- ", 1)
            # header: "[0.9999] resources/category/slug-name"
            slug = header.split("] ", 1)[-1].strip() if "] " in header else ""
            title = slug.split("/")[-1].replace("-", " ").title() if slug else ""
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            entry = f"[{title}]\n{chunk_text}" if title else chunk_text
            if total_chars + len(entry) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 200:
                    parts.append(entry[:remaining])
                break
            parts.append(entry)
            total_chars += len(entry)

        return "\n\n---\n\n".join(parts) if parts else ""

    except subprocess.TimeoutExpired:
        log.warning("gbrain query timed out (5s)")
        return ""
    except Exception as e:
        log.warning(f"gbrain unavailable: {e}")
        return ""


def _run_command(text: str, via_api: bool = False) -> str:
    """
    Core command processing: think + execute tools + return response text.
    No audio side effects — callers decide how to deliver the response.

    via_api=True: dangerous commands that require voice confirmation are blocked
    with a message instead of prompting the microphone.
    """
    if not text.strip():
        return ""

    log.info(f"You: {text}")

    with _history_lock:
        history = list(_history)

    complex_triggers = ["remember", "what did", "summarize", "explain"]
    use_complex = any(t in text.lower() for t in complex_triggers)

    from memory.db import get_memory_context, save_turn
    memory_context = get_memory_context()
    vault_context = _query_gbrain(text)

    response_text, tool_calls = think(
        user_message=text,
        tools=get_tools(),
        conversation_history=history,
        memory_context=memory_context,
        vault_context=vault_context,
        use_complex_model=use_complex,
    )

    tool_results = []
    for call in tool_calls:
        log.info(f"Tool: {call['name']}({call['input']})")
        result = dispatch_tool(call["name"], call["input"])

        if result.data.get("requires_confirmation"):
            command = result.data.get("command", "that action")
            if via_api:
                # Can't prompt the microphone from an API call — block it.
                result = ToolResult(
                    success=False,
                    message=f"Action requires voice confirmation. Please use Bobby's microphone interface to run: {command}",
                )
            elif _confirm_via_voice(command):
                retry_tool = result.data.get("confirm_and_retry_tool", "execute_terminal")
                retry_input = result.data.get(
                    "confirm_and_retry_input",
                    {"command": command, "confirmed": True},
                )
                result = dispatch_tool(retry_tool, retry_input)
            else:
                result = ToolResult(success=False, message="Action cancelled by user.")

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": call["id"],
            "content": result.to_claude_content(),
        })

    # If tools were called, get Bobby's final spoken response
    if tool_calls and not response_text:
        with _history_lock:
            history = list(_history)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"]}
            for c in tool_calls
        ]})
        history.append({"role": "user", "content": tool_results})

        response_text, _ = think(
            user_message="",
            tools=get_tools(),
            conversation_history=history,
            memory_context="",  # already injected in first turn; don't repeat
            vault_context=vault_context,
            use_complex_model=use_complex,
        )

    if response_text:
        log.info(f"Bobby: {response_text}")

    # Persist full history including tool_use/tool_result pairs.
    with _history_lock:
        _history.append({"role": "user", "content": text})
        if tool_calls:
            _history.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"]}
                for c in tool_calls
            ]})
            _history.append({"role": "user", "content": tool_results})
            if response_text:
                _history.append({"role": "assistant", "content": response_text})
        else:
            _history.append({"role": "assistant", "content": response_text or ""})

        _history[:] = _trim_history(_history)

    save_turn(_session_id, "user", text)
    if response_text:
        save_turn(_session_id, "assistant", response_text)

    return response_text or ""


def _process_command(text: str) -> None:
    """Voice pipeline handler: run command and speak the response locally."""
    with _processing_lock:
        response_text = _run_command(text, via_api=False)
    if response_text:
        _speaking.set()
        try:
            speak(response_text)
        finally:
            _speaking.clear()


def process_text_command(text: str, return_audio: bool = True) -> dict:
    """
    Public entry point for the server. Process a text command and return
    the response text + optionally synthesized MP3 audio bytes.

    Returns: {"response": str, "audio_bytes": bytes | None}
    """
    if not text.strip():
        return {"response": "", "audio_bytes": None}

    if not _processing_lock.acquire(timeout=10):
        return {"response": "I'm busy right now, try again in a moment.", "audio_bytes": None}

    try:
        response_text = _run_command(text, via_api=True)
    finally:
        _processing_lock.release()

    audio_bytes = None
    if return_audio and response_text:
        from core.tts import synthesize
        audio_bytes = synthesize(response_text)

    return {"response": response_text, "audio_bytes": audio_bytes}


def run() -> None:
    log.info("[bold green]Bobby is starting up...[/bold green]")

    detector = WakeWordDetector(on_wake=_on_wake)
    detector.start()

    log.info("[bold]Bobby is ready. Say the wake word to start.[/bold]")

    try:
        while True:
            # Wait for wake word — use timeout so Ctrl+C is delivered on Windows
            if not _listening.wait(timeout=0.5):
                while not _tts_queue.empty() and not _speaking.is_set():
                    msg = _tts_queue.get_nowait()
                    _speaking.set()
                    try:
                        speak(msg)
                    finally:
                        _speaking.clear()
                continue
            _listening.clear()

            _play_chime("wake")

            audio = record_until_silence(on_speech_detected=lambda: _play_chime("thinking"))
            text = transcribe(audio)

            if not text:
                from core.stt import SAMPLE_RATE, SPEECH_START_TIMEOUT
                if len(audio) / SAMPLE_RATE < SPEECH_START_TIMEOUT + 0.5:
                    speak("I didn't catch that.")
                log.debug("No speech detected after wake word")
                continue

            if any(word in text.lower() for word in ["stop", "never mind", "cancel"]):
                speak("Got it.")
                continue

            _process_command(text)
            _play_chime("done")

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        detector.stop()


def main() -> None:
    if config.get("server_enabled", False):
        _start_server_thread()
    run()


def _start_server_thread() -> None:
    """Start the FastAPI server in a daemon thread alongside the voice loop."""
    import socket
    import threading

    host = config.get("server_host", "0.0.0.0")
    port = int(config.get("server_port", 8765))

    def _run():
        try:
            import uvicorn
            from server.main import app
        except ImportError as e:
            log.error(f"Server dependencies not installed (pip install fastapi uvicorn): {e}")
            return
        uvicorn.run(app, host=host, port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True, name="bobby-server")
    t.start()

    # Log the reachable local IP for easy phone setup
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "localhost"

    log.info(f"[bold cyan]Server started → http://{local_ip}:{port}[/bold cyan]")
    log.info(f"[dim]Phone PWA: http://{local_ip}:{port}/  |  API: http://{local_ip}:{port}/api/[/dim]")
