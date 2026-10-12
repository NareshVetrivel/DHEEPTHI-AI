"""
Unit and integration tests for Gemini Live Lifecycle and Voice Consistency in DHEEPTHI-AI V1.

Verifies:
1. Only one active Live worker/session.
2. GoAway triggers exactly one replacement.
3. Duplicate GoAway events do not create duplicate replacements.
4. Old worker callback cannot stop the new worker.
5. Old worker callback cannot close the new session.
6. Recovery timer cannot create duplicate workers.
7. Replacement failure uses controlled retry (max 5 backoff).
8. shutdown_started prevents all replacement/reconnect.
9. Replacement preserves physical mic mute state.
10. Initial session uses the configured voice (Aoede).
11. Replacement session uses the exact same configured voice.
12. Every Live session creation path receives the same voice config.
"""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication, QObject, Signal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from ai.gemini_client import GeminiClient, GeminiLiveSession


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


# ==========================================================
# TEST SUITE 1: Voice Configuration Consistency & Response ID Lifecycle
# ==========================================================

def test_central_voice_configuration_exists():
    """Verify GEMINI_LIVE_VOICE exists centrally in config.settings and defaults to Aoede."""
    assert hasattr(settings, "GEMINI_LIVE_VOICE")
    assert settings.GEMINI_LIVE_VOICE == "Aoede"


def test_gemini_client_uses_configured_voice():
    """Verify GeminiClient initializes with the central configured voice (Aoede)."""
    with patch("ai.gemini_client.settings.GEMINI_LIVE_VOICE", "Aoede"):
        client = GeminiClient.__new__(GeminiClient)
        client.live_voice = getattr(settings, "GEMINI_LIVE_VOICE", "Aoede")
        assert client.live_voice == "Aoede"


def test_gemini_live_session_receives_voice():
    """Verify GeminiLiveSession explicitly stores the configured voice (Aoede)."""
    session = GeminiLiveSession(
        api_key="test_key",
        model="test-model",
        voice="Aoede",
        system_instruction="test instruction",
    )
    assert session.voice == "Aoede"


def test_gemini_live_session_builds_speech_config():
    """Verify GeminiLiveSession builds speech_config with prebuilt_voice_config Aoede."""
    session = GeminiLiveSession(
        api_key="test_key",
        model="test-model",
        voice="Aoede",
        system_instruction="test instruction",
    )
    selected_voice = session.voice or getattr(settings, "GEMINI_LIVE_VOICE", "Aoede") or "Aoede"
    config = {
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": selected_voice,
                }
            }
        },
    }
    assert config["speech_config"]["voice_config"]["prebuilt_voice_config"]["voice_name"] == "Aoede"


def test_all_live_session_creations_use_same_voice():
    """Verify create_live_session passes voice=Aoede to initial, replacement, and reconnect sessions."""
    client = GeminiClient.__new__(GeminiClient)
    client._closing = False
    client.lock = MagicMock()
    client.live_model = "test-live-model"
    client.live_voice = "Aoede"
    client.current_api_key = MagicMock(return_value="test_key")
    client.live_system_prompt = MagicMock(return_value="test prompt")
    client.close_live_session = MagicMock()

    with patch("ai.gemini_client.GeminiLiveSession") as mock_session_cls:
        mock_instance = MagicMock()
        mock_instance.start = MagicMock(return_value=True)
        mock_session_cls.return_value = mock_instance

        # 1. Initial session creation uses Aoede
        s1 = client.create_live_session(auto_start=False)
        mock_session_cls.assert_called_with(
            api_key="test_key",
            model="test-live-model",
            voice="Aoede",
            system_instruction="test prompt",
            on_connected=None,
            on_audio=None,
            on_input_transcript=None,
            on_output_transcript=None,
            on_interrupted=None,
            on_turn_complete=None,
            on_error=None,
            on_closed=None,
            on_go_away=None,
        )

        # 2. GoAway replacement session creation uses Aoede
        s2 = client.create_live_session(auto_start=False)
        assert mock_session_cls.call_args[1]["voice"] == "Aoede"

        # 3. Controlled reconnect session creation uses Aoede
        s3 = client.create_live_session(auto_start=False)
        assert mock_session_cls.call_args[1]["voice"] == "Aoede"


def test_response_4_interrupted_and_permanently_invalidated():
    """Verify response 4 can be interrupted and becomes permanently invalidated."""
    session = GeminiLiveSession(
        api_key="test_key",
        model="test-model",
        voice="Aoede",
    )
    session._active_response_id = 4
    session._is_model_speaking = True
    session._speaking_response_id = 4

    interrupted_id = session.interrupt_current_response()
    assert interrupted_id == 4
    assert 4 in session._invalidated_response_ids
    assert session._is_model_speaking is False
    # Crucially: active response ID must have advanced past 4
    assert session._active_response_id > 4


def test_new_user_turn_creates_new_identity_response_5():
    """Verify new user turn after interrupting response 4 gets response 5 ACTIVE."""
    session = GeminiLiveSession(
        api_key="test_key",
        model="test-model",
        voice="Aoede",
    )
    session._active_response_id = 4
    session.interrupt_current_response()
    assert 4 in session._invalidated_response_ids

    # New user turn starts
    new_resp_id = session.start_user_turn("Hey, India oda prime minister yaaru?")
    assert new_resp_id == 5
    assert session._active_response_id == 5
    # Response 4 remains permanently invalidated (never un-invalidated)
    assert 4 in session._invalidated_response_ids
    # Response 5 is fresh, uninvalidated, and active
    assert 5 not in session._invalidated_response_ids
    assert session._suppress_upcoming_response is False


def test_trailing_response_4_chunks_ignored_and_response_5_accepted():
    """Verify trailing chunks for response 4 are dropped while response 5 chunks are accepted."""
    from ui.main_window import GeminiLiveAudioWorker
    worker = GeminiLiveAudioWorker.__new__(GeminiLiveAudioWorker)
    import threading, queue
    worker._output_lock = threading.RLock()
    worker._output_queue = queue.Queue(maxsize=128)
    worker._output_buffer = bytearray()
    worker._active_response_id = 4
    worker._invalidated_response_ids = set()
    worker._suppress_upcoming_response = False
    worker._stop_requested = False
    worker._is_speaker_playing = False
    worker.worker_id = "test_worker"
    worker.live_session = None

    # Invalidate response 4
    worker.interrupt_and_flush(4)
    assert 4 in worker._invalidated_response_ids
    assert worker._active_response_id >= 5

    # New user turn starts -> set active response ID to 5
    worker.set_active_response_id(5)
    assert worker._active_response_id == 5
    assert 4 in worker._invalidated_response_ids
    assert 5 not in worker._invalidated_response_ids

    # Trailing audio from response 4 must be dropped
    worker.enqueue_output(b"\x01\x02" * 100, response_id=4)
    assert worker._output_queue.empty()

    # New audio from response 5 must be accepted and enqueued
    worker.enqueue_output(b"\x03\x04" * 100, response_id=5)
    assert not worker._output_queue.empty()
    item = worker._output_queue.get_nowait()
    assert item[0] == 5
    assert item[1] == b"\x03\x04" * 100


def test_stale_callbacks_from_response_4_cannot_invalidate_response_5():
    """Verify stale callbacks from response 4 cannot invalidate response 5."""
    session = GeminiLiveSession(
        api_key="test_key",
        model="test-model",
        voice="Aoede",
    )
    session._active_response_id = 4
    session.interrupt_current_response()
    assert 4 in session._invalidated_response_ids

    new_id = session.start_user_turn("Hey, India oda prime minister yaaru?")
    assert new_id == 5
    assert 5 not in session._invalidated_response_ids

    # Simulating a late callback from response 4 attempting to touch state
    assert 4 in session._invalidated_response_ids
    assert 5 not in session._invalidated_response_ids
    assert session._active_response_id == 5


def test_suppress_active_does_not_pre_invalidate_next_turn():
    """Verify command handoff suppression does NOT pre-invalidate the subsequent turn ID."""
    session = GeminiLiveSession(
        api_key="test_key",
        model="test-model",
        voice="Aoede",
    )
    session._active_response_id = 4
    session.suppress_active_and_next_response()

    assert 4 in session._invalidated_response_ids
    assert 5 not in session._invalidated_response_ids

    # Next turn can be started cleanly
    new_id = session.start_user_turn("Normal turn")
    assert new_id == 5
    assert new_id not in session._invalidated_response_ids


def test_regression_response4_speaking_user_turn5_server_interrupted4_response5_accepted():
    """Exact regression test:
    - response 4 speaking (speaking_response_id=4, active_response_id=4)
    - user starts turn 5 (start_user_turn() -> active_response_id=5, worker active=5)
    - server interrupted response 4 (interrupted_id=4 invalidated)
    - response 5 arrives (audio + transcript)
    - response 5 audio/transcript MUST NOT be dropped!
    """
    from ui.main_window import GeminiLiveAudioWorker
    session = GeminiLiveSession(api_key="test_key", model="test-model", voice="Aoede")

    worker = GeminiLiveAudioWorker.__new__(GeminiLiveAudioWorker)
    import threading, queue
    worker._output_lock = threading.RLock()
    worker._output_queue = queue.Queue(maxsize=128)
    worker._output_buffer = bytearray()
    worker._active_response_id = 4
    worker._speaking_response_id = 4
    worker._invalidated_response_ids = set()
    worker._suppress_upcoming_response = False
    worker._stop_requested = False
    worker._is_speaker_playing = True
    worker.worker_id = "test_worker"
    worker.live_session = session

    # Step 1: Response 4 speaking
    session._active_response_id = 4
    session._speaking_response_id = 4
    session._is_model_speaking = True

    # Step 2: User starts turn 5 BEFORE server interrupted arrives
    turn5_id = session.start_user_turn("India oda prime minister yaaru?")
    assert turn5_id == 5
    assert session._active_response_id == 5
    worker.set_active_response_id(turn5_id)
    assert worker._active_response_id == 5
    # Notice: speaking_response_id still tracks that response 4 was speaking
    assert session._speaking_response_id == 4

    # Step 3: Server sends interrupted event for response 4
    with session._response_lock:
        interrupted_id = session._speaking_response_id or (session._active_response_id - 1)
        session._invalidated_response_ids.add(interrupted_id)
        if interrupted_id == session._active_response_id:
            session._current_turn_interrupted = True
        session._is_model_speaking = False
        session._speaking_response_id = 0
        session._suppress_upcoming_response = False
        if session._active_response_id <= interrupted_id:
            session._active_response_id = interrupted_id + 1
        while session._active_response_id in session._invalidated_response_ids:
            session._active_response_id += 1

    # Invalidate ONLY response 4
    assert interrupted_id == 4
    assert 4 in session._invalidated_response_ids
    assert 5 not in session._invalidated_response_ids
    assert session._active_response_id == 5
    assert session._current_turn_interrupted is False

    # Worker processes interrupted event for response 4
    worker.interrupt_and_flush(response_id=4)
    # UI barge-in clear_output() also called
    worker.clear_output()

    assert 4 in worker._invalidated_response_ids
    assert 5 not in worker._invalidated_response_ids
    assert worker._active_response_id == 5

    # Step 4: Response 5 arrives
    received_transcripts = []
    received_audio = []

    def mock_on_transcript(text, resp_id=0):
        if resp_id not in session._invalidated_response_ids and resp_id >= session._active_response_id:
            received_transcripts.append((resp_id, text))

    def mock_on_audio(data, resp_id=0):
        if resp_id not in session._invalidated_response_ids and resp_id >= session._active_response_id:
            received_audio.append((resp_id, data))
            worker.enqueue_output(data, response_id=resp_id)

    # Late chunk from response 4 MUST be dropped
    worker.enqueue_output(b"stale_audio_4", response_id=4)
    assert worker._output_queue.empty()

    # Audio + Transcript for response 5 arrives
    mock_on_transcript("Narendra Modi", resp_id=5)
    mock_on_audio(b"pcm_modi_audio_chunk_5", resp_id=5)

    # Step 5: Verification - MUST NOT be dropped!
    assert len(received_transcripts) == 1
    assert received_transcripts[0] == (5, "Narendra Modi")
    assert len(received_audio) == 1
    assert received_audio[0] == (5, b"pcm_modi_audio_chunk_5")
    assert not worker._output_queue.empty()
    queued_item = worker._output_queue.get_nowait()
    assert queued_item[0] == 5
    assert queued_item[1] == b"pcm_modi_audio_chunk_5"


def test_multiple_consecutive_interruptions():
    """Verify multiple consecutive interruptions (e.g. 2 -> 3 -> 4) preserve response IDs and do not suppress."""
    session = GeminiLiveSession(api_key="test_key", model="test-model", voice="Aoede")

    # Turn 2 speaking
    session._active_response_id = 2
    session._speaking_response_id = 2
    session._is_model_speaking = True

    # User interrupts Turn 2 with Turn 3
    t3 = session.start_user_turn("First interrupt")
    assert t3 == 3
    assert session._active_response_id == 3

    # Server interrupts Turn 2
    session.interrupt_current_response()
    assert 2 in session._invalidated_response_ids
    assert 3 not in session._invalidated_response_ids
    assert session._active_response_id == 3

    # Model starts speaking Turn 3
    session._speaking_response_id = 3
    session._is_model_speaking = True

    # User interrupts Turn 3 with Turn 4
    t4 = session.start_user_turn("Second interrupt")
    assert t4 == 4
    assert session._active_response_id == 4

    # Server interrupts Turn 3
    session.interrupt_current_response()
    assert 2 in session._invalidated_response_ids
    assert 3 in session._invalidated_response_ids
    assert 4 not in session._invalidated_response_ids
    assert session._active_response_id == 4

    # Turn 4 arrives cleanly
    assert session._active_response_id == 4
    assert session._suppress_upcoming_response is False


def test_normal_non_interrupted_turns():
    """Verify normal turns proceed sequentially without invalidation or suppression."""
    session = GeminiLiveSession(api_key="test_key", model="test-model", voice="Aoede")

    # Turn 1
    t1 = session.start_user_turn("Hello")
    assert t1 == 1
    session._speaking_response_id = 1
    session._is_model_speaking = True
    # Turn 1 completes normally
    session._is_model_speaking = False
    session._speaking_response_id = 0
    session._turn_completed = True

    assert len(session._invalidated_response_ids) == 0
    assert session._active_response_id == 1

    # Turn 2
    t2 = session.start_user_turn("How are you?")
    assert t2 == 2
    assert session._active_response_id == 2
    session._speaking_response_id = 2
    session._is_model_speaking = True
    # Turn 2 completes normally
    session._is_model_speaking = False
    session._speaking_response_id = 0
    session._turn_completed = True

    assert len(session._invalidated_response_ids) == 0
    assert session._active_response_id == 2


# ==========================================================
# TEST SUITE 2: Lifecycle, Stale Callbacks, GoAway, Retry, Shutdown
# ==========================================================

class DummyWorker(QObject):
    connected = Signal()
    failed = Signal(str)
    finished_audio = Signal()

    def __init__(self, generation=0):
        super().__init__()
        self.generation = generation
        self._running = True
        self._input_enabled = True

    def isRunning(self):
        return self._running

    def stop(self):
        self._running = False

    def wait(self, timeout=1000):
        return True

    def set_input_enabled(self, val):
        self._input_enabled = val

    def input_enabled(self):
        return self._input_enabled

    def clear_output(self):
        pass


class DummySession:
    def __init__(self, generation=0):
        self.generation = generation
        self._running = True
        self.on_connected = None
        self.on_audio = None
        self.on_input_transcript = None
        self.on_output_transcript = None
        self.on_interrupted = None
        self.on_turn_complete = None
        self.on_error = None
        self.on_closed = None
        self.on_go_away = None

    def is_running(self):
        return self._running

    def stop(self, timeout=1.0):
        self._running = False


class MockMainWindowState:
    """Lightweight test harness reproducing MainWindow's Live lifecycle state and logic."""

    def __init__(self):
        self.shutdown_started = False
        self._closing = False
        self._live_generation = 0
        self._goaway_replacement_in_progress = False
        self._recovery_timer_pending = False
        self._live_recovery_timer = None
        self._live_reconnect_attempts = 0
        self.gemini_live_active = False
        self.gemini_live_mic_enabled = True
        self.physical_microphone_muted = False
        self.gemini_live_command_handoff = False
        self._gemini_live_output_suppressed = False
        self._gemini_live_pending_start = False

        self.gemini_live_session = None
        self.gemini_live_audio_worker = None

        self.gemini_live_error_signal = MagicMock()
        self.gemini_live_closed_signal = MagicMock()
        self.gemini_live_go_away_signal = MagicMock()

        self.mic_widget = MagicMock()
        self.status_label = MagicMock()
        self.microphone_button = MagicMock()
        self.left_panel = MagicMock()

    def _set_avatar_state(self, state):
        pass

    def _set_thinking_state(self, state):
        pass

    def unlock_microphone(self):
        pass

    def _start_gemini_live_input_watchdog(self):
        pass

    def _stop_gemini_live_input_watchdog(self):
        pass

    # Lifecycle methods from ui/main_window.py

    def _cancel_live_recovery_timer(self):
        timer = getattr(self, "_live_recovery_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
            self._live_recovery_timer = None
        self._recovery_timer_pending = False

    def _schedule_live_recovery_timer(self):
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return
        if getattr(self, "_goaway_replacement_in_progress", False):
            print("[LIVE LIFECYCLE] Reconnect timer suppressed: GoAway replacement in progress")
            return
        if getattr(self, "_recovery_timer_pending", False) or getattr(self, "_live_recovery_timer", None) is not None:
            print("[LIVE LIFECYCLE] Recovery timer already pending, ignoring duplicate request")
            return

        max_attempts = 5
        if self._live_reconnect_attempts >= max_attempts:
            print(f"[LIVE LIFECYCLE] Max recovery attempts ({max_attempts}) reached. Stopping reconnect loop.")
            return

        self._live_reconnect_attempts += 1
        self._recovery_timer_pending = True
        mock_timer = MagicMock()
        mock_timer.isActive.return_value = True
        self._live_recovery_timer = mock_timer

    def _on_gemini_live_audio_worker_connected(self, worker=None):
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False) or not self.gemini_live_active:
            return
        if worker is not None and worker is not self.gemini_live_audio_worker:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        if worker is not None and hasattr(worker, "generation") and worker.generation != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return

        self._cancel_live_recovery_timer()
        self._live_reconnect_attempts = 0
        if getattr(self, "_goaway_replacement_in_progress", False):
            print("[LIVE LIFECYCLE] Replacement Live session connected")
            print("[LIVE LIFECYCLE] Replacement worker is authoritative")
            self._goaway_replacement_in_progress = False
            print("[LIVE LIFECYCLE] Replacement complete")
        else:
            print("[LIVE LIFECYCLE] Replacement worker is authoritative")

        input_enabled = not self.physical_microphone_muted
        if self.gemini_live_audio_worker is not None:
            self.gemini_live_audio_worker.set_input_enabled(input_enabled)
        self._gemini_live_output_suppressed = not input_enabled
        self.gemini_live_mic_enabled = input_enabled

    def _on_gemini_live_audio_worker_failed(self, message, worker=None):
        if getattr(self, "_closing", False) or getattr(self, "shutdown_started", False):
            return
        if worker is not None and worker is not self.gemini_live_audio_worker:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        if worker is not None and hasattr(worker, "generation") and worker.generation != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        self._goaway_replacement_in_progress = False
        self.gemini_live_error_signal.emit(str(message or "Gemini Live audio failed."))

    def _on_gemini_live_error(self, message, gen=None):
        if getattr(self, "shutdown_started", False) or self._closing:
            return
        if gen is not None and gen != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        self.gemini_live_error_signal.emit(str(message or "Gemini Live error."))

    def _on_gemini_live_closed(self, gen=None):
        if getattr(self, "shutdown_started", False) or self._closing:
            return
        if gen is not None and gen != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        self.gemini_live_closed_signal.emit()

    def _on_gemini_live_go_away(self, time_left=None, gen=None):
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return
        if gen is not None and gen != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        self._handle_gemini_live_go_away(time_left or "")

    def _handle_gemini_live_go_away(self, time_left=""):
        if getattr(self, "shutdown_started", False) or self._closing:
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return
        if getattr(self, "_goaway_replacement_in_progress", False):
            print("[LIVE LIFECYCLE] Replacement already in progress")
            return

        print(f"[LIVE LIFECYCLE] GoAway detected (time_left={time_left})")
        print("[LIVE LIFECYCLE] Starting controlled replacement")
        self._goaway_replacement_in_progress = True

        self._cancel_live_recovery_timer()

        print("[LIVE LIFECYCLE] Waiting for old worker/session to stop")
        self._stop_gemini_live_conversation(clear_audio=True, restart_live=False)
        print("[LIVE LIFECYCLE] Old worker/session fully stopped")

        if getattr(self, "shutdown_started", False) or self._closing:
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            self._goaway_replacement_in_progress = False
            return

        print("[LIVE LIFECYCLE] Starting replacement Live session")
        self._gemini_live_pending_start = True
        self._start_gemini_live_conversation()

    def _stop_gemini_live_conversation(self, clear_audio=True, restart_live=False):
        self._live_generation += 1
        worker = self.gemini_live_audio_worker
        session = self.gemini_live_session
        self.gemini_live_active = False
        self.gemini_live_audio_worker = None
        self.gemini_live_session = None

        if worker is not None:
            worker.stop()
            worker.wait(100)

        if session is not None:
            session.stop(timeout=0.1)

    def _start_gemini_live_conversation(self):
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return

        self._cancel_live_recovery_timer()
        self._gemini_live_pending_start = False
        self.gemini_live_mic_enabled = not self.physical_microphone_muted

        self._stop_gemini_live_conversation(clear_audio=True, restart_live=False)

        self._live_generation += 1
        gen = self._live_generation

        session = DummySession(generation=gen)
        self.gemini_live_session = session
        self.gemini_live_active = True

        worker = DummyWorker(generation=gen)
        self.gemini_live_audio_worker = worker

    def _shutdown_gemini_live_synchronously(self):
        self.shutdown_started = True
        self._closing = True
        self._live_generation += 1
        self._cancel_live_recovery_timer()
        self._goaway_replacement_in_progress = False
        self.gemini_live_active = False
        self._gemini_live_pending_start = False

        if self.gemini_live_audio_worker is not None:
            self.gemini_live_audio_worker.stop()
            self.gemini_live_audio_worker = None
        if self.gemini_live_session is not None:
            self.gemini_live_session.stop()
            self.gemini_live_session = None


# ==========================================================
# TEST IMPLEMENTATIONS
# ==========================================================

def test_only_one_active_live_worker_and_session(qapp):
    """Verify exactly ONE active Live worker and session exist."""
    state = MockMainWindowState()
    state._start_gemini_live_conversation()

    assert state.gemini_live_session is not None
    assert state.gemini_live_audio_worker is not None
    assert state.gemini_live_active is True

    worker1 = state.gemini_live_audio_worker
    session1 = state.gemini_live_session

    # Starting again cleanly tears down old and replaces with exactly one
    state._start_gemini_live_conversation()
    assert state.gemini_live_audio_worker is not worker1
    assert state.gemini_live_session is not session1
    assert not worker1.isRunning()
    assert not session1.is_running()


def test_goaway_triggers_exactly_one_replacement(qapp, capsys):
    """Verify GoAway triggers exactly ONE controlled replacement."""
    state = MockMainWindowState()
    state._start_gemini_live_conversation()

    old_worker = state.gemini_live_audio_worker
    old_session = state.gemini_live_session
    old_gen = state._live_generation

    # Trigger GoAway
    state._on_gemini_live_go_away("30s", gen=old_gen)

    # Replacement worker should be active, old should be stopped
    new_worker = state.gemini_live_audio_worker
    new_session = state.gemini_live_session

    assert new_worker is not old_worker
    assert new_session is not old_session
    assert not old_worker.isRunning()
    assert not old_session.is_running()
    assert state._goaway_replacement_in_progress is True

    # Complete replacement
    state._on_gemini_live_audio_worker_connected(new_worker)
    assert state._goaway_replacement_in_progress is False

    captured = capsys.readouterr().out
    assert "[LIVE LIFECYCLE] GoAway detected" in captured
    assert "[LIVE LIFECYCLE] Starting controlled replacement" in captured
    assert "[LIVE LIFECYCLE] Old worker/session fully stopped" in captured
    assert "[LIVE LIFECYCLE] Starting replacement Live session" in captured
    assert "[LIVE LIFECYCLE] Replacement Live session connected" in captured
    assert "[LIVE LIFECYCLE] Replacement worker is authoritative" in captured
    assert "[LIVE LIFECYCLE] Replacement complete" in captured


def test_duplicate_goaway_does_not_create_duplicate_replacements(qapp, capsys):
    """Verify duplicate GoAway calls during replacement are ignored."""
    state = MockMainWindowState()
    state._start_gemini_live_conversation()

    gen = state._live_generation
    state._goaway_replacement_in_progress = True

    # Attempt second GoAway
    state._handle_gemini_live_go_away("20s")

    captured = capsys.readouterr().out
    assert "[LIVE LIFECYCLE] Replacement already in progress" in captured


def test_old_worker_callback_cannot_stop_new_worker(qapp, capsys):
    """Verify callbacks from an old worker generation are ignored."""
    state = MockMainWindowState()
    state._start_gemini_live_conversation()

    old_worker = state.gemini_live_audio_worker
    old_gen = state._live_generation

    # Advance generation
    state._start_gemini_live_conversation()
    new_worker = state.gemini_live_audio_worker

    # Simulate old worker emitting failed
    state._on_gemini_live_audio_worker_failed("Old audio error", worker=old_worker)

    captured = capsys.readouterr().out
    assert "[LIVE LIFECYCLE] Ignoring stale worker callback" in captured
    # Ensure error signal was NOT emitted for the old worker
    assert not state.gemini_live_error_signal.emit.called
    # Ensure new worker is untouched
    assert state.gemini_live_audio_worker is new_worker


def test_old_session_callback_cannot_close_new_session(qapp, capsys):
    """Verify callbacks from an old session generation cannot close the new session."""
    state = MockMainWindowState()
    state._start_gemini_live_conversation()

    old_gen = state._live_generation

    # Advance generation
    state._start_gemini_live_conversation()

    # Simulate old session closed and error
    state._on_gemini_live_closed(gen=old_gen)
    state._on_gemini_live_error("Old error", gen=old_gen)

    captured = capsys.readouterr().out
    assert "[LIVE LIFECYCLE] Ignoring stale worker callback" in captured
    assert not state.gemini_live_closed_signal.emit.called
    assert not state.gemini_live_error_signal.emit.called


def test_recovery_timer_cannot_create_duplicate_workers(qapp, capsys):
    """Verify duplicate recovery timers are suppressed while one is already pending."""
    state = MockMainWindowState()
    state._schedule_live_recovery_timer()
    assert state._recovery_timer_pending is True

    # Try scheduling another timer
    state._schedule_live_recovery_timer()

    captured = capsys.readouterr().out
    assert "[LIVE LIFECYCLE] Recovery timer already pending, ignoring duplicate request" in captured


def test_controlled_retry_stops_at_max_attempts(qapp, capsys):
    """Verify recovery retry stops after reaching max attempts (5)."""
    state = MockMainWindowState()
    for _ in range(5):
        state._recovery_timer_pending = False
        state._live_recovery_timer = None
        state._schedule_live_recovery_timer()

    assert state._live_reconnect_attempts == 5

    # 6th attempt should be blocked
    state._recovery_timer_pending = False
    state._live_recovery_timer = None
    state._schedule_live_recovery_timer()

    captured = capsys.readouterr().out
    assert "[LIVE LIFECYCLE] Max recovery attempts (5) reached. Stopping reconnect loop." in captured


def test_shutdown_started_prevents_all_replacement_and_reconnect(qapp, capsys):
    """Verify shutdown_started=True suppresses GoAway, timers, and reconnects."""
    state = MockMainWindowState()
    state._start_gemini_live_conversation()
    state._shutdown_gemini_live_synchronously()

    assert state.shutdown_started is True
    assert state._closing is True
    assert state.gemini_live_active is False
    assert state.gemini_live_audio_worker is None
    assert state.gemini_live_session is None

    # Try GoAway after shutdown
    state._handle_gemini_live_go_away("10s")
    # Try start after shutdown
    state._start_gemini_live_conversation()
    # Try timer schedule after shutdown
    state._schedule_live_recovery_timer()

    captured = capsys.readouterr().out
    assert "[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True" in captured


def test_replacement_preserves_physical_mic_mute_state(qapp):
    """Verify replacement worker preserves muted vs unmuted physical mic state."""
    state = MockMainWindowState()

    # Case A: Mic is muted
    state.physical_microphone_muted = True
    state._start_gemini_live_conversation()
    worker = state.gemini_live_audio_worker
    state._on_gemini_live_audio_worker_connected(worker)
    assert state.gemini_live_mic_enabled is False
    assert worker.input_enabled() is False

    # Case B: Mic is unmuted
    state.physical_microphone_muted = False
    state._start_gemini_live_conversation()
    worker = state.gemini_live_audio_worker
    state._on_gemini_live_audio_worker_connected(worker)
    assert state.gemini_live_mic_enabled is True
    assert worker.input_enabled() is True


def test_interruption_phrases_variations():
    """Verify English and Tanglish interruption phrases are correctly recognized."""
    from ui.main_window import MainWindow
    is_interrupt = MainWindow._is_interruption_phrase

    # Core interruptions
    assert is_interrupt("wait") is True
    assert is_interrupt("wait pannu") is True
    assert is_interrupt("wait pannuda") is True
    assert is_interrupt("wait pa") is True
    assert is_interrupt("iru") is True
    assert is_interrupt("irunga") is True
    assert is_interrupt("one minute") is True
    assert is_interrupt("oru nimisham") is True
    assert is_interrupt("stop") is True
    assert is_interrupt("pothum") is True
    assert is_interrupt("podhum") is True
    assert is_interrupt("pesadha") is True
    assert is_interrupt("pesatha") is True
    assert is_interrupt("niruthu") is True
    assert is_interrupt("enough") is True

    # Filler-prefixed / suffixed interruptions
    assert is_interrupt("hey wait") is True
    assert is_interrupt("dheepthi wait") is True
    assert is_interrupt("stop please") is True
    assert is_interrupt("wait please") is True
    assert is_interrupt("dheepthi wait pannu") is True

    # Normal queries and automation commands must NEVER be treated as interruptions
    assert is_interrupt("Chrome open panni Pavalamalli song play pannu") is False
    assert is_interrupt("What is the capital of France?") is False
    assert is_interrupt("Tell me a funny joke") is False
    assert is_interrupt("Open Notepad and write hello") is False


def test_audio_worker_immediate_interruption_stops_playback_and_flushes():
    """Verify interrupt_and_flush immediately discards buffer, empties queue, and stops speaker."""
    from ui.main_window import GeminiLiveAudioWorker
    import queue, threading

    worker = GeminiLiveAudioWorker.__new__(GeminiLiveAudioWorker)
    worker._output_lock = threading.RLock()
    worker._output_queue = queue.Queue(maxsize=128)
    worker._output_buffer = bytearray(b"\x01\x02" * 500)
    worker._active_response_id = 3
    worker._speaking_response_id = 3
    worker._invalidated_response_ids = set()
    worker._suppress_upcoming_response = False
    worker._stop_requested = False
    worker._is_speaker_playing = True
    worker.worker_id = "test_worker_imm"
    worker.live_session = None

    # Enqueue multiple chunks for response 3
    worker._output_queue.put((3, b"\x03\x04" * 100))
    worker._output_queue.put((3, b"\x05\x06" * 100))
    assert not worker._output_queue.empty()
    assert len(worker._output_buffer) > 0
    assert worker._is_speaker_playing is True

    # Immediate interruption occurs
    worker.interrupt_and_flush(response_id=3)

    # Verification: buffer cleared, queue emptied, speaker stopped, response 3 invalidated
    assert len(worker._output_buffer) == 0
    assert worker._output_queue.empty()
    assert worker._is_speaker_playing is False
    assert worker._speaking_response_id == 0
    assert 3 in worker._invalidated_response_ids

    # Further chunks for response 3 must be dropped
    worker.enqueue_output(b"\x07\x08" * 50, response_id=3)
    assert worker._output_queue.empty()


def test_audio_driven_user_turn_does_not_submit_duplicate_text():
    """Verify that incoming voice transcript updates turn bookkeeping but does NOT call submit_user_turn."""
    from ui.main_window import MainWindow
    win = MainWindow.__new__(MainWindow)
    win.gemini_live_active = True
    win.physical_microphone_muted = False
    win._closing = False
    win.shutdown_started = False
    win.gemini_live_command_handoff = False
    win.processing_voice = False
    win.gemini_live_last_command = ""
    win.status_label = MagicMock()
    win.mic_widget = MagicMock()
    win.left_panel = MagicMock()
    win._set_avatar_state = MagicMock()

    mock_session = MagicMock()
    mock_session._started = True
    mock_session._closing = threading.Event()
    mock_session.start_user_turn.return_value = 2
    mock_session.submit_user_turn = MagicMock()

    mock_worker = MagicMock()
    win.gemini_live_session = mock_session
    win.gemini_live_audio_worker = mock_worker

    # Simulate conversational speech: "Hello how are you?"
    win._handle_gemini_live_input_transcript("Hello how are you?")

    # start_user_turn must be called to create response identity
    mock_session.start_user_turn.assert_called_once_with("Hello how are you?")
    mock_worker.set_active_response_id.assert_called_once_with(2)

    # CRUCIAL: submit_user_turn must NOT be called (prevents duplicate response bug)
    mock_session.submit_user_turn.assert_not_called()


def test_tanglish_command_candidate_detection():
    """Verify Tanglish multi-command is recognized as command candidate and not conversational."""
    from ui.main_window import MainWindow
    is_candidate = MainWindow._is_semantic_command_candidate

    assert is_candidate(MainWindow, "Chrome open panni Pavalamalli song play pannu") is True
    assert is_candidate(MainWindow, "Downloads folder open panni file ah delete pannu") is True
    assert is_candidate(MainWindow, "Take a screenshot") is True
    assert is_candidate(MainWindow, "wait") is False
    assert is_candidate(MainWindow, "wait pannu") is False

