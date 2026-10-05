"""
tools/test_runtime_language_scenarios.py

Simulates runtime speech transcript events for:
1. "How are you?"
2. "Nee epdi irukka?"
3. "Chrome open panni Pavalamalli song play pannu"
4. Tamil Unicode
5. Mixed Latin + Tamil
6. Foreign script (Hindi -> Other language detected)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def test_runtime_scenarios():
    print("=" * 60)
    print("TESTING RUNTIME LANGUAGE SCENARIOS IN MAINWINDOW")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    if hasattr(win, "loading_overlay") and win.loading_overlay:
        win.loading_overlay.hide()

    win.gemini_live_active = True
    win.gemini_live_mic_enabled = True

    # 1. "How are you?"
    print("\n[SCENARIO 1] English utterance: 'How are you?'")
    win._handle_gemini_live_input_transcript("How are you?")
    transcript_ui = win.user_speech_panel.get_transcript()
    assert transcript_ui == "How are you?", f"Expected 'How are you?', got '{transcript_ui}'"
    print(f"      [PASSED] Panel displays: '{transcript_ui}'")

    # 2. "Nee epdi irukka?"
    print("\n[SCENARIO 2] Tanglish utterance: 'Nee epdi irukka?'")
    win._handle_gemini_live_input_transcript("Nee epdi irukka?")
    transcript_ui = win.user_speech_panel.get_transcript()
    assert transcript_ui == "Nee epdi irukka?", f"Expected 'Nee epdi irukka?', got '{transcript_ui}'"
    print(f"      [PASSED] Panel displays: '{transcript_ui}'")

    # 3. "Chrome open panni Pavalamalli song play pannu"
    print("\n[SCENARIO 3] Tanglish command: 'Chrome open panni Pavalamalli song play pannu'")
    win._handle_gemini_live_input_transcript("Chrome open panni Pavalamalli song play pannu")
    transcript_ui = win.user_speech_panel.get_transcript()
    assert transcript_ui == "Chrome open panni Pavalamalli song play pannu"
    print(f"      [PASSED] Panel displays: '{transcript_ui}' (Tanglish in Roman script preserved)")

    # 4. Tamil Unicode
    tamil_input = "\u0ba8\u0bc0 \u0b8e\u0baa\u0bcd\u0baa\u0b9f\u0bbf \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95?"
    print(f"\n[SCENARIO 4] Tamil Unicode utterance: '{tamil_input}'")
    win._handle_gemini_live_input_transcript(tamil_input)
    transcript_ui = win.user_speech_panel.get_transcript()
    assert transcript_ui == tamil_input
    print(f"      [PASSED] Panel displays: '{transcript_ui}' (Tamil Unicode preserved)")

    # 5. Mixed Latin + Tamil command
    mixed_cmd = "Chrome open \u0baa\u0ba3\u0bcd\u0ba3\u0bbf YouTube open \u0baa\u0ba3\u0bcd\u0ba3\u0bc1"
    print(f"\n[SCENARIO 5] Mixed Latin + Tamil command: '{mixed_cmd}'")
    win._handle_gemini_live_input_transcript(mixed_cmd)
    transcript_ui = win.user_speech_panel.get_transcript()
    assert transcript_ui == mixed_cmd
    print(f"      [PASSED] Panel displays: '{transcript_ui}' (Mixed script preserved)")

    # 6. Foreign script (Hindi / Devanagari)
    hindi_input = "\u092c\u093e\u0930\u0947 \u0939\u093f\u0902\u0926\u0940 \u0939\u0947\u092a \u092c\u0948\u0928\u094b..."
    print(f"\n[SCENARIO 6] Foreign script (Hindi/Devanagari): '{hindi_input}'")
    win._handle_gemini_live_input_transcript(hindi_input)
    transcript_ui = win.user_speech_panel.get_transcript()
    assert transcript_ui == "Other language detected"
    print(f"      [PASSED] Panel displays safe fallback: '{transcript_ui}'")
    assert win.gemini_live_user_transcript == hindi_input
    print("      [PASSED] Raw user transcript tracked internally for Live session without corruption.")

    win._closing = True
    win.close()
    app.processEvents()

    print("\n" + "=" * 60)
    print("ALL RUNTIME LANGUAGE SCENARIOS VERIFIED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_runtime_scenarios()
