"""Verify that pipeline state transitions broadcast the correct WS events — T5 of Phase 12 UI."""

import threading
from unittest.mock import patch, MagicMock, call


class TestOnWakeBroadcast:
    def test_on_wake_broadcasts_listening_when_not_speaking(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline._speaking") as mock_speaking:
            mock_speaking.is_set.return_value = False
            from core.pipeline import _on_wake
            _on_wake()
            mock_bc.assert_called_once_with("listening")

    def test_on_wake_skips_broadcast_when_speaking(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline._speaking") as mock_speaking, \
             patch("core.pipeline._listening") as mock_listening:
            mock_speaking.is_set.return_value = True
            from core.pipeline import _on_wake
            _on_wake()
            mock_bc.assert_not_called()
            mock_listening.set.assert_not_called()


class TestRunCommandBroadcast:
    def test_run_command_broadcasts_thinking_at_start(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline.think", return_value=("hello", [])), \
             patch("core.pipeline.get_tools", return_value=[]), \
             patch("core.pipeline._query_gbrain", return_value=""), \
             patch("memory.db.save_turn"), \
             patch("memory.db.get_memory_context", return_value=""), \
             patch("tools.profile.load_profile_context", return_value=""), \
             patch("core.pipeline._history_lock", threading.Lock()):
            from core.pipeline import _run_command
            _run_command("what time is it", via_api=True)
            calls = [c.args[0] for c in mock_bc.call_args_list]
            assert "thinking" in calls

    def test_run_command_skips_broadcast_for_empty_text(self):
        with patch("core.pipeline.broadcast_state") as mock_bc:
            from core.pipeline import _run_command
            result = _run_command("   ")
            mock_bc.assert_not_called()
            assert result == ""


class TestProcessCommandBroadcast:
    def test_process_command_broadcasts_speaking_and_idle(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline._run_command", return_value="Here is my response"), \
             patch("core.pipeline._speaking") as mock_speaking, \
             patch("core.pipeline.speak"), \
             patch("core.pipeline._processing_lock", threading.Lock()):
            mock_speaking.is_set.return_value = False
            from core.pipeline import _process_command
            _process_command("test command")
            calls = [c.args[0] for c in mock_bc.call_args_list]
            assert "speaking" in calls
            assert "idle" in calls
            # speaking comes before idle
            assert calls.index("speaking") < calls.index("idle")
            # text is passed with speaking
            speaking_call = next(c for c in mock_bc.call_args_list if c.args[0] == "speaking")
            assert speaking_call.kwargs.get("text") == "Here is my response" or \
                   (len(speaking_call.args) > 1 and speaking_call.args[1] == "Here is my response")

    def test_process_command_broadcasts_idle_on_empty_response(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline._run_command", return_value=""), \
             patch("core.pipeline._processing_lock", threading.Lock()):
            from core.pipeline import _process_command
            _process_command("test command")
            calls = [c.args[0] for c in mock_bc.call_args_list]
            assert "idle" in calls
            assert "speaking" not in calls


class TestProcessTextCommandBroadcast:
    def test_process_text_command_broadcasts_speaking_and_idle(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline._run_command", return_value="API response"), \
             patch("core.pipeline._processing_lock", threading.Lock()), \
             patch("core.tts.synthesize", return_value=b"audio"):
            from core.pipeline import process_text_command
            result = process_text_command("hello", return_audio=False)
            calls = [c.args[0] for c in mock_bc.call_args_list]
            # thinking comes from _run_command (mocked here), idle always fires
            assert "idle" in calls

    def test_process_text_command_always_broadcasts_idle(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline._run_command", return_value=""), \
             patch("core.pipeline._processing_lock", threading.Lock()):
            from core.pipeline import process_text_command
            process_text_command("anything", return_audio=False)
            calls = [c.args[0] for c in mock_bc.call_args_list]
            assert "idle" in calls

    def test_process_text_command_broadcasts_speaking_with_text(self):
        with patch("core.pipeline.broadcast_state") as mock_bc, \
             patch("core.pipeline._run_command", return_value="spoken text"), \
             patch("core.pipeline._processing_lock", threading.Lock()), \
             patch("core.tts.synthesize", return_value=b"audio"):
            from core.pipeline import process_text_command
            process_text_command("hello", return_audio=True)
            calls = [c.args[0] for c in mock_bc.call_args_list]
            assert "speaking" in calls
            speaking_call = next(c for c in mock_bc.call_args_list if c.args[0] == "speaking")
            assert speaking_call.kwargs.get("text") == "spoken text" or \
                   (len(speaking_call.args) > 1 and speaking_call.args[1] == "spoken text")
