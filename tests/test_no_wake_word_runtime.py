"""
Regression tests for no-wake-word runtime architecture in DHEEPTHI-AI V1.
Verifies that:
1. No wake-word detector is loaded or imported in main components.
2. Faster-Whisper wake detector is completely absent from initialization.
3. Gemini Live is configured as the realtime voice session.
4. Physical laptop microphone mute state is authoritative.
5. CommandDispatcher and ACTION routing remain intact.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_1_no_wake_word_imports_in_main_window():
    """Verify MainWindow does not import legacy wake-word detectors."""
    with open(PROJECT_ROOT / "ui" / "main_window.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "WakeWordDetector" not in content
    assert "load_wake_word_model" not in content
    assert "openwakeword" not in content.lower()


def test_2_no_wake_word_in_initialization_worker():
    """Verify InitializationWorker does not load or initialize wake-word models."""
    with open(PROJECT_ROOT / "workers" / "initialization_worker.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "wake_word" not in content.lower()
    assert "openwakeword" not in content.lower()


def test_3_gemini_live_session_is_available():
    """Verify GeminiLiveSession class is exported by ai.gemini_client."""
    from ai.gemini_client import GeminiLiveSession, GeminiClient
    assert GeminiLiveSession is not None
    assert GeminiClient is not None


def test_4_physical_microphone_monitor_is_available():
    """Verify MicrophoneMuteMonitor is available and functional."""
    from voice.microphone_monitor import MicrophoneMuteMonitor
    monitor = MicrophoneMuteMonitor(interval_ms=250)
    assert monitor is not None
    assert hasattr(monitor, "mute_changed")
    assert hasattr(monitor, "current_muted")
    assert hasattr(monitor, "start_monitoring")


def test_5_action_extractor_intact():
    """Verify ACTION extraction logic is intact."""
    from planner.semantic_command_planner import extract_action_command
    raw = "<ACTION>open chrome</ACTION>"
    cmd = extract_action_command(raw)
    assert cmd == "open chrome"


def test_6_command_dispatcher_intact():
    """Verify CommandDispatcher class is intact."""
    from planner.command_dispatcher import CommandDispatcher
    assert CommandDispatcher is not None
    assert hasattr(CommandDispatcher, "dispatch")


def test_7_gemini_live_vad_settings_configured():
    """Verify server-side VAD settings exist in config.settings."""
    from config import settings
    assert hasattr(settings, "GEMINI_LIVE_START_SENSITIVITY")
    assert hasattr(settings, "GEMINI_LIVE_END_SENSITIVITY")
    assert hasattr(settings, "GEMINI_LIVE_SILENCE_DURATION_MS")
    assert settings.GEMINI_LIVE_START_SENSITIVITY == "START_SENSITIVITY_HIGH"
    assert settings.GEMINI_LIVE_END_SENSITIVITY == "END_SENSITIVITY_HIGH"
    assert settings.GEMINI_LIVE_SILENCE_DURATION_MS == 600


def test_8_groq_recognizer_intact():
    """Verify GroqRecognizer class is available."""
    from voice.groq_recognizer import GroqRecognizer
    assert GroqRecognizer is not None
