"""
Main Bobby pipeline: wake word → STT → Claude brain → TTS.
This is the entry point for running Bobby on PC.
"""

import threading

from core import config
from core.brain import think
from core.logging import get_logger
from core.stt import record_until_silence, transcribe
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


def _process_command(text: str) -> None:
    global _history

    if not text.strip():
        return

    log.info(f"You: {text}")

    with _history_lock:
        history = list(_history)

    # Determine model complexity from heuristics
    complex_triggers = ["remember", "what did", "summarize", "explain", "find", "search", "help"]
    use_complex = any(t in text.lower() for t in complex_triggers)

    response_text, tool_calls = think(
        user_message=text,
        tools=get_tools(),
        conversation_history=history,
        use_complex_model=use_complex,
    )

    # Execute tool calls and collect results
    tool_results = []
    for call in tool_calls:
        log.info(f"Tool: {call['name']}({call['input']})")
        result = dispatch_tool(call["name"], call["input"])
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

    # Update history
    with _history_lock:
        _history.append({"role": "user", "content": text})
        _history.append({"role": "assistant", "content": response_text or "(tool action)"})

        # Keep history bounded
        if len(_history) > HISTORY_MAX_TURNS * 2:
            _history = _history[-(HISTORY_MAX_TURNS * 2):]


def run() -> None:
    log.info("[bold green]Bobby is starting up...[/bold green]")

    detector = WakeWordDetector(on_wake=_on_wake)
    detector.start()

    log.info("[bold]Bobby is ready. Say the wake word to start.[/bold]")

    try:
        while True:
            # Wait for wake word
            _listening.wait()
            _listening.clear()

            _play_chime("wake")

            # Record until silence
            audio = record_until_silence(on_speech_detected=lambda: _play_chime("thinking"))
            text = transcribe(audio)

            if not text:
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
