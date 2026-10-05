"""
Comprehensive system verification test for DHEEPTHI-AI V1.
Tests core subsystems:
1. Settings configuration
2. GeminiClient & Live session configuration
3. Microphone monitor availability
4. ACTION extractor and Semantic Command Planner
5. CommandDispatcher and automation components
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_system_test():
    print("=" * 60)
    print("DHEEPTHI-AI V1 SYSTEM VERIFICATION TEST")
    print("=" * 60)

    # 1. Settings
    print("[1/5] Verifying Settings...")
    from config import settings
    assert settings.GEMINI_LIVE_MODEL == "gemini-3.1-flash-live-preview"
    assert settings.GEMINI_LIVE_START_SENSITIVITY == "START_SENSITIVITY_HIGH"
    assert settings.GEMINI_LIVE_END_SENSITIVITY == "END_SENSITIVITY_HIGH"
    assert settings.GEMINI_LIVE_SILENCE_DURATION_MS == 600
    assert getattr(settings, "GEMINI_LIVE_VOICE", "") == "Aoede"
    print("      Settings: OK")

    # 2. Gemini Client & Live Session
    print("[2/5] Verifying Gemini Client & Live Configuration...")
    from ai.gemini_client import GeminiClient, GeminiLiveSession
    client = GeminiClient()
    assert client.live_model == "gemini-3.1-flash-live-preview"
    assert client.live_voice == "Aoede"
    assert GeminiLiveSession is not None
    print("      Gemini Client: OK")

    # 3. Microphone Monitor
    print("[3/5] Verifying Physical Microphone Monitor...")
    from voice.microphone_monitor import MicrophoneMuteMonitor
    monitor = MicrophoneMuteMonitor(interval_ms=250)
    assert monitor is not None
    assert hasattr(monitor, "mute_changed")
    print("      Microphone Monitor: OK")

    # 4. ACTION Extractor & Semantic Planner
    print("[4/5] Verifying ACTION Extractor & Semantic Planner...")
    from planner.semantic_command_planner import extract_action_command, SemanticCommandPlanner
    assert extract_action_command("<ACTION>open chrome</ACTION>") == "open chrome"
    planner = SemanticCommandPlanner()
    assert planner is not None
    print("      ACTION Extractor & Planner: OK")

    # 5. Command Dispatcher
    print("[5/5] Verifying Command Dispatcher...")
    from planner.command_dispatcher import CommandDispatcher
    assert CommandDispatcher is not None
    assert hasattr(CommandDispatcher, "dispatch")
    print("      Command Dispatcher: OK")

    print("\n" + "=" * 60)
    print("ALL SYSTEM SUBSYSTEMS VERIFIED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    run_system_test()
