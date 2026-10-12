"""
tests/test_user_speech_panel.py

Regression tests for UserSpeechPanel in DHEEPTHI-AI V1:
1. UserSpeechPanel can be created.
2. Transcript updates correctly.
3. Long transcript does not overflow.
4. Listening state renders.
5. User-speaking state renders.
6. Muted state renders.
7. Speaking state renders.
8. Waveform accepts real amplitude values.
9. Waveform does not create another microphone input stream.
10. Physical microphone monitor remains intact.
11. Gemini Live input path remains unchanged.
12. MainWindow incorporates UserSpeechPanel without old center microphone button.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure a single QApplication instance exists for GUI tests
_app = QApplication.instance() or QApplication(sys.argv)


def test_1_user_speech_panel_can_be_created():
    """Verify UserSpeechPanel instantiates cleanly with expected defaults."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    assert panel is not None
    assert panel.objectName() == "UserSpeechPanel"
    assert panel.get_state() == UserSpeechPanel.STATE_IDLE
    assert panel.transcript_label is not None
    assert panel.waveform_widget is not None
    assert 320 <= panel.minimumWidth() <= 380
    assert panel.maximumWidth() <= 450
    assert panel.maximumHeight() <= 95


def test_2_transcript_updates_correctly():
    """Verify transcript text updates and switches to user speaking state."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.set_transcript("Chrome open panni Pavalamalli song play pannu")
    assert "Chrome open panni Pavalamalli song play pannu" in panel.transcript_label.text()
    assert panel.get_state() == UserSpeechPanel.STATE_USER_SPEAKING


def test_3_long_transcript_does_not_overflow():
    """Verify very long speech transcripts are handled gracefully without label overflow."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.resize(380, 86)
    long_text = "This is an extremely long utterance where the user talks about opening multiple applications, editing documents, searching the web, and checking the weather while keeping DHEEPTHI active."
    panel.set_transcript(long_text)
    # The label must never exceed panel bounds
    assert panel.transcript_label.height() <= 40
    assert len(panel.transcript_label.text()) > 0


def test_4_listening_state_renders():
    """Verify transition to listening state."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.set_state("listening")
    assert panel.get_state() == UserSpeechPanel.STATE_LISTENING
    assert panel.waveform_widget._is_muted is False
    assert panel.waveform_widget._is_active is True
    assert "Listening" in panel.transcript_label.text()


def test_5_user_speaking_state_renders():
    """Verify transition to user-speaking state with active voice level."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.set_state("listening")
    panel.update_audio_level(0.45)
    assert panel.get_state() == UserSpeechPanel.STATE_USER_SPEAKING
    assert panel.waveform_widget._target_level == 0.45


def test_6_muted_state_renders():
    """Verify muted state displays muted indicator and zeroes waveform."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.set_state("muted")
    assert panel.get_state() == UserSpeechPanel.STATE_MUTED
    assert panel.waveform_widget._is_muted is True
    assert "Muted" in panel.transcript_label.text()
    # Level update while muted must remain zeroed
    panel.update_audio_level(0.8)
    assert panel.waveform_widget._target_level == 0.0


def test_7_speaking_state_renders():
    """Verify speaking state (DHEEPTHI response) deactivates user waveform."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.set_state("speaking")
    assert panel.get_state() == UserSpeechPanel.STATE_SPEAKING
    assert panel.waveform_widget._is_active is False
    assert "Speaking" in panel.transcript_label.text()


def test_8_waveform_accepts_real_amplitude_values():
    """Verify waveform widget clamps and smoothly interpolates real PCM values."""
    from ui.widgets.user_speech_panel import SpeechWaveformWidget
    wave = SpeechWaveformWidget()
    wave.set_target_level(0.72)
    assert wave._target_level == 0.72
    wave.set_target_level(1.5)  # Out of range clamped
    assert wave._target_level == 1.0
    wave.set_target_level(-0.2)
    assert wave._target_level == 0.0


def test_9_waveform_does_not_create_another_audio_stream():
    """Verify neither UserSpeechPanel nor SpeechWaveformWidget opens sounddevice or PyAudio."""
    import inspect
    from ui.widgets import user_speech_panel
    source = inspect.getsource(user_speech_panel)
    assert "sounddevice" not in source
    assert "pyaudio" not in source
    assert "InputStream" not in source


def test_10_physical_microphone_monitor_remains_intact():
    """Verify MicrophoneMuteMonitor is available, exported, and uncompromised."""
    from voice.microphone_monitor import MicrophoneMuteMonitor
    monitor = MicrophoneMuteMonitor(interval_ms=250)
    assert monitor is not None
    assert hasattr(monitor, "mute_changed")
    assert hasattr(monitor, "current_muted")


def test_11_gemini_live_input_path_remains_unchanged():
    """Verify GeminiLiveAudioWorker calculates audio level without altering packet streaming."""
    import threading
    from ui.main_window import GeminiLiveAudioWorker
    worker = GeminiLiveAudioWorker.__new__(GeminiLiveAudioWorker)
    worker._input_enabled = True
    worker._stop_requested = False
    worker._input_lock = threading.Lock()
    worker._input_byte_buffer = bytearray()
    worker.live_session = None
    worker.worker_id = "test_worker"
    worker._current_audio_level = 0.55
    assert worker.get_audio_level() == 0.55
    worker.set_input_enabled(False)
    assert worker.get_audio_level() == 0.0


def test_12_main_window_has_user_speech_panel():
    """Verify MainWindow source code configures UserSpeechPanel in center area and unhooks mic button click."""
    main_window_path = PROJECT_ROOT / "ui" / "main_window.py"
    with open(main_window_path, "r", encoding="utf-8") as f:
        code = f.read()

    assert "UserSpeechPanel" in code
    assert "self.user_speech_panel = UserSpeechPanel" in code
    assert "self._poll_live_audio_level" in code
    # Old microphone button click listener must not be hooked
    assert "self.microphone_button.clicked.connect" not in code


def test_13_english_transcript_accepted():
    """Verify pure English user transcripts are accepted verbatim."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.set_transcript("How are you?")
    assert panel.get_transcript() == "How are you?"
    assert "How are you?" in panel.transcript_label.text()


def test_14_tamil_unicode_transcript_accepted():
    """Verify authentic Tamil Unicode transcripts are accepted verbatim."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    tamil_input = "நீ எப்படி இருக்க?"
    panel.set_transcript(tamil_input)
    assert panel.get_transcript() == tamil_input
    assert tamil_input in panel.transcript_label.text()


def test_15_tanglish_latin_transcripts_accepted():
    """Verify conversational Tanglish written in Latin characters is preserved exactly."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()

    tanglish_cases = [
        "Nee epdi irukka?",
        "Chrome open panni Pavalamalli song play pannu",
        "Enakku oru doubt irukku",
        "Enna panra?",
        "Enakku coffee venum",
        "Chrome open panni YouTube la song play pannu",
        "Downloads folder open panni report.pdf Desktop ku copy pannu",
        "Wait pannu",
        "Oru nimisham iru",
        "Indha file ah open pannu",
        "dei enna da ithu naan tanglish la pesuren",
    ]

    for utterance in tanglish_cases:
        panel.set_transcript(utterance)
        assert panel.get_transcript() == utterance, f"Failed for {utterance}"
        assert utterance in panel.transcript_label.text()


def test_16_mixed_tamil_and_english_accepted():
    """Verify mixed Latin and Tamil Unicode characters are accepted verbatim."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()

    mixed_cases = [
        "Chrome ஓபன் பண்ணி Pavalamalli song play பண்ணு",
        "Chrome-ஐ open பண்ணு",
        "நான் Chrome open பண்ணணும்",
    ]

    for utterance in mixed_cases:
        panel.set_transcript(utterance)
        assert panel.get_transcript() == utterance
        assert utterance in panel.transcript_label.text()


def test_17_foreign_scripts_fallback_to_other_language_detected():
    """Verify unsupported foreign scripts trigger subtle 'Other language detected' display without crashing."""
    from ui.widgets.user_speech_panel import UserSpeechPanel, FALLBACK_OTHER_LANGUAGE
    panel = UserSpeechPanel()

    foreign_cases = [
        "आप कैसे हैं",                     # Hindi / Devanagari
        "बारे हिंदी हेप बैनो...",        # Colloquial Devanagari
        "మీరు ఎలా ఉన్నారు",               # Telugu
        "നിങ്ങൾ எങ്ങனെയുണ്ട്",            # Malayalam
        "ನೀವು ಹೇಗಿದ್ದೀರಿ",               # Kannada
        "আপনি কেমন আছেন",               # Bengali
        "元気ですか",                     # Japanese
        "你好吗",                        # Chinese
        "كيف حالك",                      # Arabic
    ]

    for foreign_text in foreign_cases:
        panel.set_transcript(foreign_text)
        assert panel.get_transcript() == FALLBACK_OTHER_LANGUAGE, f"Failed for {foreign_text}"
        assert FALLBACK_OTHER_LANGUAGE in panel.transcript_label.text()


def test_18_unsupported_language_not_translated_into_fake_text():
    """Verify unsupported scripts are deterministically mapped to the fallback and never fake-translated."""
    from ui.widgets.user_speech_panel import filter_user_speech_display_transcript, FALLBACK_OTHER_LANGUAGE

    result = filter_user_speech_display_transcript("आप कैसे हैं")
    assert result == FALLBACK_OTHER_LANGUAGE
    # Must NOT invent fake English words like "How are you"
    assert "How are you" not in result
    # Must NOT invent fake Tamil transliteration
    assert "எப்படி" not in result


def test_19_tanglish_action_command_remains_intact_and_separate():
    """Verify visual display of user speech remains separate from normalized English ACTION command."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    from planner.semantic_command_planner import extract_action_command

    panel = UserSpeechPanel()
    user_utterance = "Chrome open panni Pavalamalli song play pannu"
    panel.set_transcript(user_utterance)

    # Simulated Gemini Live model response with ACTION tag
    gemini_reply = 'Seri da, naan open panren. <ACTION>Open Chrome and play Pavalamalli song on YouTube</ACTION>'
    extracted_action = extract_action_command(gemini_reply)

    assert extracted_action == "Open Chrome and play Pavalamalli song on YouTube"
    # Panel must strictly retain the user's spoken Tanglish, NOT the internal normalized ACTION!
    assert panel.get_transcript() == user_utterance
    assert "Open Chrome and play Pavalamalli song on YouTube" not in panel.get_transcript()


def test_20_assistant_response_never_displayed_as_user_transcript():
    """Verify update_ai_message updates assistant state but never overwrites user transcript."""
    from ui.widgets.user_speech_panel import UserSpeechPanel
    panel = UserSpeechPanel()
    panel.set_transcript("How are you?")

    panel.update_ai_message("I am doing great! How can I help you today?")
    # User transcript must remain intact
    assert panel.get_transcript() == "How are you?"
    assert panel.get_state() == UserSpeechPanel.STATE_SPEAKING


def test_21_gemini_live_system_prompt_includes_transcription_fidelity():
    """Verify live_system_prompt instructs Gemini Live to preserve user script and support multilingual."""
    from ai.gemini_client import GeminiClient
    client = GeminiClient()
    prompt = client.live_system_prompt()

    assert "INPUT AUDIO TRANSCRIPTION & SCRIPT FIDELITY" in prompt
    assert "NEVER transcribe or convert Tanglish into Devanagari" in prompt
    assert "MULTILINGUAL CONVERSATION CAPABILITY" in prompt


def test_22_main_window_filter_display_transcript():
    """Verify MainWindow display filtering helper behaves correctly."""
    from ui.main_window import MainWindow
    # Test statically / unbound method
    filter_func = MainWindow._filter_user_speech_display_transcript

    assert filter_func(None, "Chrome open panni Pavalamalli song play pannu") == "Chrome open panni Pavalamalli song play pannu"
    assert filter_func(None, "நீ எப்படி இருக்க?") == "நீ எப்படி இருக்க?"
    assert filter_func(None, "आप कैसे हैं") == "Other language detected"

