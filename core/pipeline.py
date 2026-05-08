"""
Main Bobby pipeline: wake word → STT → Claude brain → TTS.
This is the entry point for running Bobby on PC.
"""

import threading

from core import config
from core.brain import think
from core.logging import get_logger
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


def _process_command(text: str) -> None:
    if not text.strip():
        return

    log.info(f"You: {text}")

    with _history_lock:
        history = list(_history)

    # Escalate to Sonnet only for genuine reasoning tasks, not simple tool calls.
    # "find chrome", "help me open discord" should stay on Haiku.
    complex_triggers = ["remember", "what did", "summarize", "explain"]
    use_complex = any(t in text.lower() for t in complex_triggers)

    response_text, tool_calls = think(
        user_message=text,
        tools=get_tools(),
        conversation_history=history,
        use_complex_model=use_complex,
    )

    # Execute tool calls, enforce hard confirmation gate, collect results
    tool_results = []
    for call in tool_calls:
        log.info(f"Tool: {call['name']}({call['input']})")
        result = dispatch_tool(call["name"], call["input"])

        # Hard confirmation gate — not delegated to Claude's judgment.
        # When a tool signals requires_confirmation, we get explicit voice input
        # before allowing execution. The pipeline then re-dispatches with confirmed=True.
        if result.data.get("requires_confirmation"):
            command = result.data.get("command", "that command")
            if _confirm_via_voice(command):
                result = dispatch_tool("execute_terminal", {"command": command, "confirmed": True})
            else:
                result = ToolResult(success=False, message="Command cancelled by user.")

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
            use_complex_model=use_complex,
        )

    if response_text:
        log.info(f"Bobby: {response_text}")
        _speaking.set()
        try:
            speak(response_text)
        finally:
            _speaking.clear()

    # Persist full history including tool_use/tool_result pairs.
    # The Anthropic API requires these to appear as matched pairs in conversation history —
    # stripping them causes API validation errors on subsequent tool-using turns.
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


def run() -> None:
    log.info("[bold green]Bobby is starting up...[/bold green]")

    detector = WakeWordDetector(on_wake=_on_wake)
    detector.start()

    log.info("[bold]Bobby is ready. Say the wake word to start.[/bold]")

    try:
        while True:
            # Wait for wake word — use timeout so Ctrl+C is delivered on Windows
            if not _listening.wait(timeout=0.5):
                continue
            _listening.clear()

            _play_chime("wake")

            # Record until silence (or speech-start timeout)
            audio = record_until_silence(on_speech_detected=lambda: _play_chime("thinking"))
            text = transcribe(audio)

            if not text:
                # If audio is very short, the mic didn't pick up anything (speech-start timeout)
                from core.stt import SAMPLE_RATE, SPEECH_START_TIMEOUT
                if len(audio) / SAMPLE_RATE < SPEECH_START_TIMEOUT + 0.5:
                    speak("I didn't catch that.")
                log.debug("No speech detected after wake word")
                continue

            # Check for stop command
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
    run()
