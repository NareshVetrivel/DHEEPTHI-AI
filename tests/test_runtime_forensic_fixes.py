"""
Unit and regression tests for DHEEPTHI-AI V1 forensic runtime fixes.

Covers:
1. Folder false positive prevention (conversational questions, Chrome Remote Desktop)
2. Folder valid command detection (English, Tamil, Tanglish)
3. Interim transcript gating (never executes, never suppresses Gemini Live)
4. Final transcript execution exactly once
5. Chrome Remote Desktop remains conversation
6. Desktop/computer conversational mentions remain conversation
7. Deterministic local time query in English
8. Deterministic local time query in Tamil / Tanglish / Mixed
9. Command execution off GUI thread via CommandExecutionWorker
10. Action deduplication (never executes twice)
11. Audio packet logging throttled by default
"""

import datetime
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.intent_detector import IntentDetector
from planner.command_dispatcher import CommandDispatcher
from ui.main_window import CommandExecutionWorker
from config import settings


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    return app


@pytest.fixture
def detector():
    return IntentDetector()


@pytest.fixture
def mock_dispatcher():
    mocks = {k: MagicMock() for k in [
        'tts', 'app_launcher', 'app_closer', 'keyboard_controller',
        'mouse_controller', 'window_controller', 'system_controller',
        'file_finder', 'folder_manager', 'file_manager',
        'browser_controller', 'whisper', 'gemini_client'
    ]}
    mocks['tts'].speak.side_effect = lambda t: t
    return CommandDispatcher(**mocks)


# ==========================================================
# FIX 1: STRICT FOLDER INTENT TESTS
# ==========================================================

def test_1_folder_conversational_negatives(detector):
    """Conversational phrases mentioning folders/desktop must NOT be open_folder."""
    negatives = [
        "Chrome Remote Desktop",
        "What is Chrome Remote Desktop?",
        "Explain desktop computers",
        "Why should I use desktop mode?",
        "Tell me about Downloads",
        "What is the Music folder?",
        "Chrome Remote Desktop pathi sollu",
    ]
    for text in negatives:
        intent = detector.detect_local_intent_only(text)
        assert intent != "open_folder", f"Expected '{text}' to NOT be open_folder, got {intent}"


def test_2_folder_valid_commands(detector):
    """Legitimate natural English and Tanglish folder commands must resolve to open_folder."""
    positives = [
        "Open Desktop",
        "Open the Desktop folder",
        "Desktop folder open pannu",
        "Downloads open pannu",
        "Open Downloads",
        "Go to Downloads",
        "Open Music folder",
        "Documents folder open pannu",
    ]
    for text in positives:
        intent = detector.detect_local_intent_only(text)
        assert intent == "open_folder", f"Expected '{text}' to be open_folder, got {intent}"


# ==========================================================
# FIX 4: DETERMINISTIC LOCAL TIME QUERY TESTS
# ==========================================================

def test_3_time_query_detection_english(detector):
    """English time queries must resolve to deterministic current_time intent."""
    english_time_queries = [
        "What is the time?",
        "What time is it?",
        "Current time?",
        "what's the time",
        "tell me the time",
    ]
    for text in english_time_queries:
        intent = detector.detect_local_intent_only(text)
        assert intent == "current_time", f"Expected '{text}' -> current_time, got {intent}"


def test_4_time_query_detection_tamil_tanglish(detector):
    """Tamil and Tanglish time queries must resolve to deterministic current_time intent."""
    tanglish_time_queries = [
        "Indian time enna?",
        "Ippa time enna?",
        "Ippo current time sollu",
        "India-la ippo enna time?",
        "current time sollu",
        "time enna",
    ]
    for text in tanglish_time_queries:
        intent = detector.detect_local_intent_only(text)
        assert intent == "current_time", f"Expected '{text}' -> current_time, got {intent}"


def test_5_time_query_deterministic_execution(mock_dispatcher):
    """Time query must read actual IST time, never hardcoded."""
    try:
        import zoneinfo
        ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    except Exception:
        ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")
    now = datetime.datetime.now(tz=ist)
    expected_hour = now.strftime("%I").lstrip("0")
    expected_ampm = now.strftime("%p")

    # English query
    res_en = mock_dispatcher.dispatch(intent="current_time", user_text="What is the time?")
    assert res_en["success"] is True
    assert "Current Time" in res_en["status"]
    assert expected_hour in res_en["message"]
    assert expected_ampm in res_en["message"]
    assert "India time" in res_en["message"]
    assert "IST" in res_en["message"]

    # Tamil/Tanglish query
    res_ta = mock_dispatcher.dispatch(intent="current_time", user_text="Indian time enna?")
    assert res_ta["success"] is True
    assert "Ippo India time" in res_ta["message"]
    assert expected_hour in res_ta["message"]
    assert "IST" in res_ta["message"]


# ==========================================================
# FIX 2: NEVER EXECUTE INTERIM TRANSCRIPTS
# ==========================================================

def test_6_interim_transcript_simulation(qapp):
    """
    Simulate streaming interim transcripts followed by final turn completion:
        interim: 'Chrome Remote'
        interim: 'Chrome Remote Desktop'
        final:   'Chrome Remote Desktop pathi sollu'
    Verifies:
        - no command during interim
        - Gemini response is NOT suppressed
        - final routes to conversation
    """
    from ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self: None):
        win = MainWindow()
        win._closing = False
        win.shutdown_started = False
        win._live_generation = 1
        win.gemini_live_active = True
        win.gemini_live_audio_worker = None
        win.gemini_live_session = None
        win.intent_detector = IntentDetector()
        win.semantic_command_planner = None
        win._gemini_live_output_suppressed = False
        win._is_interruption_phrase = lambda t: False
        win._filter_user_speech_display_transcript = lambda t: t

        # Mock Qt signals
        win.gemini_live_interim_signal = MagicMock()
        win.gemini_live_input_signal = MagicMock()
        win.gemini_live_interrupted_signal = MagicMock()

        # Step 1: interim "Chrome Remote"
        win._on_gemini_live_input_transcript("Chrome Remote", gen=1, is_interim=True)
        assert win._gemini_live_output_suppressed is False
        win.gemini_live_interim_signal.emit.assert_called_with("Chrome Remote")
        win.gemini_live_input_signal.emit.assert_not_called()

        # Step 2: interim "Chrome Remote Desktop"
        win._on_gemini_live_input_transcript("Chrome Remote Desktop", gen=1, is_interim=True)
        assert win._gemini_live_output_suppressed is False
        win.gemini_live_input_signal.emit.assert_not_called()

        # Step 3: final "Chrome Remote Desktop pathi sollu"
        win._on_gemini_live_input_transcript("Chrome Remote Desktop pathi sollu", gen=1, is_interim=False)
        # Conversational query must NOT suppress Gemini Live
        assert win._gemini_live_output_suppressed is False
        win.gemini_live_input_signal.emit.assert_called_with("Chrome Remote Desktop pathi sollu")


def test_7_interim_and_final_open_downloads_executes_once(qapp):
    """
    Simulate:
        interim: 'Open Down'
        final:   'Open Downloads'
    Expected:
        - no folder opening on interim
        - exactly one folder command after final transcript
    """
    from ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self: None):
        win = MainWindow()
        win._closing = False
        win.shutdown_started = False
        win._live_generation = 1
        win.gemini_live_active = True
        win.gemini_live_audio_worker = None
        win.gemini_live_session = None
        win.intent_detector = IntentDetector()
        win.semantic_command_planner = None
        win._gemini_live_output_suppressed = False
        win._is_interruption_phrase = lambda t: False

        win.gemini_live_interim_signal = MagicMock()
        win.gemini_live_input_signal = MagicMock()

        # Interim
        win._on_gemini_live_input_transcript("Open Down", gen=1, is_interim=True)
        assert win._gemini_live_output_suppressed is False
        win.gemini_live_input_signal.emit.assert_not_called()

        # Final
        win._on_gemini_live_input_transcript("Open Downloads", gen=1, is_interim=False)
        # Fast local deterministic command is detected on final transcript
        assert win._gemini_live_output_suppressed is True
        win.gemini_live_input_signal.emit.assert_called_once_with("Open Downloads")


# ==========================================================
# FIX 3: REMOVE GUI THREAD BLOCKING TESTS
# ==========================================================

def test_8_command_execution_off_gui_thread(qapp, mock_dispatcher):
    """CommandExecutionWorker must execute target function in background thread, not GUI thread."""
    thread_ids = []

    def mock_target(intent=None, user_text=None, **kwargs):
        is_main = threading.current_thread() is threading.main_thread()
        thread_ids.append(is_main)
        time.sleep(0.05)
        return {"success": True, "status": "Done"}

    worker = CommandExecutionWorker(
        target_fn=mock_target,
        text="Open Downloads",
        intent="open_folder",
        entity="Downloads",
    )

    results = []
    worker.result_ready.connect(lambda res, text, intent, entity: results.append((res, text, intent, entity)))

    worker.start()
    worker.wait(2000)
    qapp.processEvents()

    assert len(thread_ids) == 1
    assert thread_ids[0] is False, "Command execution MUST NOT run on GUI / main thread!"
    assert len(results) == 1
    assert results[0][0]["success"] is True
    assert results[0][2] == "open_folder"


# ==========================================================
# ACTION DEDUPLICATION TESTS
# ==========================================================

def test_9_action_deduplication(qapp):
    """An extracted action cannot be executed twice within the same turn window."""
    from ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self: None):
        win = MainWindow()
        win._last_routed_action_cmd = ""
        win._last_routed_action_time = 0.0
        win.gemini_live_last_command = ""
        win._last_command_time = 0.0
        win.semantic_command_planner = None
        win.process_command = MagicMock()

        # First call: executes
        win._route_action_command_to_semantic_pipeline("open chrome")
        assert win.process_command.call_count == 1

        # Second call immediately after: blocked by dedup
        win._route_action_command_to_semantic_pipeline("open chrome")
        assert win.process_command.call_count == 1, "Duplicate action execution should have been blocked!"


# ==========================================================
# FIX 5: AUDIO LOGGING THROTTLED BY DEFAULT
# ==========================================================

def test_10_audio_logging_throttled_by_default():
    """Verify that verbose audio debugging is disabled by default."""
    assert hasattr(settings, "DEBUG_AUDIO_VERBOSE")
    assert settings.DEBUG_AUDIO_VERBOSE is False
