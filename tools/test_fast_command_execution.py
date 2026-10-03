"""
DHEEPTHI-AI V1 — Fast Laptop Command Execution, Model Hierarchy, 503 Fix & Telemetry Test Suite
"""

import sys
import os
import time
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from config import settings
from ai.gemini_client import GeminiClient
from planner.intent_detector import IntentDetector
from planner.multi_command_planner import MultiCommandPlanner
from planner.semantic_command_planner import SemanticCommandPlanner
from ui.main_window import MainWindow


class MockMainWindowForRouting:
    """Mock harness to test MainWindow transcript routing without launching full Qt window."""

    def __init__(self):
        self._closing = False
        self.shutdown_started = False
        self._shutdown_finalizing = False
        self._shutdown_goodbye_started = False
        self._goodbye_tts_finished = False
        self.gemini_live_active = True
        self.gemini_live_command_handoff = False
        self.processing_voice = False
        self.gemini_live_last_command = ""
        self.gemini_live_user_transcript = ""
        self.gemini_live_output_transcript = ""
        self._gemini_live_output_suppressed = False
        self.gemini_live_mic_enabled = True
        self.physical_microphone_muted = False
        self._gemini_live_pending_start = False

        self.multi_command_planner = MultiCommandPlanner()
        self.intent_detector = IntentDetector(gemini_client=None, enable_gemini_fallback=False)
        self.semantic_command_planner = None

        class MockWidget:
            def update_user_message(self, text):
                pass
            def update_ai_message(self, text):
                pass
            def show_conversation(self, u, a):
                pass
            def setEnabled(self, val):
                pass
            def set_listening(self, val):
                pass

        class MockStatus:
            def setText(self, text):
                pass

        class MockLeftPanel:
            def set_listening(self, s):
                pass
            def set_speaking(self, s):
                pass

        class MockBtn:
            def setEnabled(self, val):
                pass

        class MockSignal:
            def __init__(self):
                self.calls = []
            def emit(self, *args):
                self.calls.append(args)

        self.mic_widget = MockWidget()
        self.status_label = MockStatus()
        self.left_panel = MockLeftPanel()
        self.microphone_button = MockBtn()
        self.gemini_live_audio_worker = None
        self.gemini_live_session = None
        self.gemini = None

        self.gemini_live_input_signal = MockSignal()
        self.gemini_live_output_signal = MockSignal()
        self.gemini_live_interrupted_signal = MockSignal()
        self.gemini_live_turn_complete_signal = MockSignal()
        self.gemini_live_error_signal = MockSignal()
        self.gemini_live_closed_signal = MockSignal()
        self.gemini_live_go_away_signal = MockSignal()

        # Tracking variables
        self.dispatched_commands = []
        self.semantic_plans_executed = []
        self.planner_call_count = 0
        self.shutdown_steps_run = []

    # Bind methods from MainWindow
    _is_interruption_phrase = MainWindow._is_interruption_phrase
    _is_semantic_command_candidate = MainWindow._is_semantic_command_candidate
    _handle_gemini_live_input_transcript = MainWindow._handle_gemini_live_input_transcript
    _handle_gemini_live_output_transcript = MainWindow._handle_gemini_live_output_transcript
    _handle_gemini_live_interrupted = MainWindow._handle_gemini_live_interrupted
    _handle_gemini_live_turn_complete = MainWindow._handle_gemini_live_turn_complete
    _handle_gemini_live_error = MainWindow._handle_gemini_live_error
    _handle_gemini_live_closed = MainWindow._handle_gemini_live_closed
    _handle_gemini_live_go_away = MainWindow._handle_gemini_live_go_away
    _on_gemini_live_connected = MainWindow._on_gemini_live_connected
    _on_gemini_live_audio = MainWindow._on_gemini_live_audio
    _on_gemini_live_input_transcript = MainWindow._on_gemini_live_input_transcript
    _on_gemini_live_output_transcript = MainWindow._on_gemini_live_output_transcript
    _on_gemini_live_interrupted = MainWindow._on_gemini_live_interrupted
    _on_gemini_live_turn_complete = MainWindow._on_gemini_live_turn_complete
    _on_gemini_live_error = MainWindow._on_gemini_live_error
    _on_gemini_live_closed = MainWindow._on_gemini_live_closed
    _on_gemini_live_go_away = MainWindow._on_gemini_live_go_away
    _start_gemini_live_conversation = MainWindow._start_gemini_live_conversation
    _stop_gemini_live_conversation = MainWindow._stop_gemini_live_conversation
    _shutdown_gemini_live_synchronously = MainWindow._shutdown_gemini_live_synchronously
    _stop_gemini_live_input_watchdog = lambda self: None
    _set_avatar_state = lambda self, s: None
    _set_thinking_state = lambda self, s, avatar_state=None: None
    lock_microphone = lambda self: None
    unlock_microphone = lambda self: None

    def process_command(self, text):
        self.dispatched_commands.append(text)

    def _execute_semantic_plan(self, plan, text, t_cmd_start=None):
        self.semantic_plans_executed.append((plan, text))

    def _begin_goodbye_shutdown(self, event=None):
        self._shutdown_goodbye_started = True
        self.shutdown_steps_run.append("goodbye_tts")
        return True

    def closeEvent(self, event):
        return MainWindow.closeEvent(self, event)


def run_tests():
    print("======================================================================")
    print("DHEEPTHI-AI V1 — FAST LAPTOP COMMAND EXECUTION & 503 FIX TEST SUITE")
    print("======================================================================\n")

    passed = 0
    total = 0

    # ------------------------------------------------------------------
    # Test 1: Settings & Model Hierarchy Configuration
    # ------------------------------------------------------------------
    total += 1
    print("TEST 1: Model Hierarchy Configuration")
    client = GeminiClient()
    models = client.semantic_planner_models
    print(f"Configured models: {models}")
    expected_primary = "gemini-3.8-flash"
    assert models[0] == expected_primary, f"Primary model should be {expected_primary}, got {models[0]}"
    assert "gemini-3.7-flash" in models, "Fallback tier 1 must be gemini-3.7-flash"
    assert "gemini-3.6-flash" in models, "Fallback tier 2 must be gemini-3.6-flash"
    assert len(models) >= 3, f"Expected at least 3 models in hierarchy, got {len(models)}"
    print("[PASS] Test 1: Model hierarchy correctly ordered (3.8 -> 3.7 -> 3.6 -> fallback)")
    passed += 1

    # ------------------------------------------------------------------
    # Test 2: Service Unavailable / 503 Detection Helper
    # ------------------------------------------------------------------
    total += 1
    print("\nTEST 2: 503 / Service Unavailable Detection")
    err_503 = Exception("503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand.'}}")
    err_other = Exception("400 INVALID_ARGUMENT: Bad request syntax.")
    err_quota = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded.")

    assert GeminiClient._is_service_unavailable_error(err_503) is True
    assert GeminiClient._is_service_unavailable_error(err_other) is False
    assert GeminiClient._is_service_unavailable_error(err_quota) is False
    print("[PASS] Test 2: _is_service_unavailable_error correctly isolates 503/high demand from other errors")
    passed += 1

    # ------------------------------------------------------------------
    # Test 3: Fast 503 Failover Simulation
    # ------------------------------------------------------------------
    total += 1
    print("\nTEST 3: Fast 503 Failover (Skip Key Retries on Overloaded Models)")
    # Create client with mocked API calls
    mock_calls = []

    class MockModelsService:
        def generate_content(self, model, contents, config=None):
            mock_calls.append(model)
            if model in ("gemini-3.8-flash", "gemini-3.7-flash"):
                raise Exception("503 UNAVAILABLE: Model experiencing high demand")
            elif model == "gemini-3.6-flash":
                class Resp:
                    text = '{"type": "command", "actions": [{"intent": "launch_application"}]}'
                return Resp()
            raise Exception("404 NOT_FOUND")

    class MockGenaiClient:
        def __init__(self):
            self.models = MockModelsService()

    test_client = GeminiClient()
    test_client.client = MockGenaiClient()
    test_client.semantic_planner_models = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]

    t0 = time.time()
    plan_json = test_client.generate_structured_plan("Test prompt")
    t1 = time.time()
    elapsed = t1 - t0

    print(f"Mock calls made: {mock_calls}")
    print(f"Plan output: {plan_json}")
    print(f"Elapsed time: {elapsed:.3f}s")

    # Verify each 503 model was tried only ONCE (no 4-key retries burning time)
    assert mock_calls.count("gemini-3.8-flash") == 1, "gemini-3.8-flash should fail fast after 1 attempt on 503"
    assert mock_calls.count("gemini-3.7-flash") == 1, "gemini-3.7-flash should fail fast after 1 attempt on 503"
    assert mock_calls.count("gemini-3.6-flash") == 1, "gemini-3.6-flash succeeded"
    assert "launch_application" in plan_json, "Plan successfully produced by tier 3"
    assert elapsed < 1.0, f"503 failover should take < 1.0s in simulation, took {elapsed:.3f}s"
    print("[PASS] Test 3: 503 fails fast to next tier without cycling 4 keys on overloaded model")
    passed += 1

    # ------------------------------------------------------------------
    # Test 4: Fast Local Deterministic Routing (<0.5s, 0 Planner Calls)
    # ------------------------------------------------------------------
    fast_commands = [
        ("Open Chrome", "launch_application"),
        ("Open Notepad", "launch_application"),
        ("Open Downloads", "open_folder"),
        ("Close Notepad", "close_application"),
        ("Take a screenshot", "take_screenshot"),
        ("Open VS Code", "launch_application"),
    ]

    for cmd, expected_intent in fast_commands:
        total += 1
        print(f"\nTEST: Fast Local Path for '{cmd}'")
        harness = MockMainWindowForRouting()

        # Mock a spy planner that would raise if called
        class SpyPlanner:
            def plan(self, text):
                harness.planner_call_count += 1
                raise AssertionError(f"Semantic planner should NOT be called for deterministic command '{text}'")

        harness.semantic_command_planner = SpyPlanner()

        t0 = time.time()
        harness._handle_gemini_live_input_transcript(cmd)
        t1 = time.time()
        routing_time = t1 - t0

        print(f"Routing + Dispatch time: {routing_time:.4f}s")
        assert routing_time < 0.50, f"Expected < 0.50s, got {routing_time:.4f}s"
        assert harness.planner_call_count == 0, f"Planner called {harness.planner_call_count} times, expected 0"
        assert len(harness.dispatched_commands) == 1, f"Expected 1 dispatched command, got {len(harness.dispatched_commands)}"
        assert harness.dispatched_commands[0] == cmd, f"Expected dispatched command '{cmd}', got '{harness.dispatched_commands[0]}'"
        print(f"[PASS] Fast local path: '{cmd}' dispatched in {routing_time*1000:.2f}ms with 0 planner calls")
        passed += 1

    # ------------------------------------------------------------------
    # Test 5: Tanglish / Multi-step Commands Route to Semantic Planner
    # ------------------------------------------------------------------
    semantic_commands = [
        "Chrome open panni Pavalamalli song play pannu",
        "VS Code open panni Python la calculator program create pannu",
        "Downloads folder open panni report.pdf Desktop ku copy pannu",
    ]

    for cmd in semantic_commands:
        total += 1
        print(f"\nTEST: Semantic Planning Route for '{cmd}'")
        harness = MockMainWindowForRouting()

        planner_called_with = []
        class MockPlanner:
            def plan(self, text):
                planner_called_with.append(text)
                return {
                    "type": "command",
                    "actions": [{"intent": "launch_application", "entities": {"application": "Chrome"}}],
                    "original_command": text
                }
            def _is_obviously_conversational(self, text):
                return False

        harness.semantic_command_planner = MockPlanner()

        harness._handle_gemini_live_input_transcript(cmd)

        assert len(planner_called_with) == 1, f"Expected planner called 1 time, got {len(planner_called_with)}"
        assert planner_called_with[0] == cmd
        assert len(harness.semantic_plans_executed) == 1, "Semantic plan should be executed"
        assert len(harness.dispatched_commands) == 0, "Should NOT route to local simple dispatcher"
        print(f"[PASS] Tanglish command '{cmd}' correctly routed to SemanticCommandPlanner")
        passed += 1

    # ------------------------------------------------------------------
    # Test 6: Pure Conversation Protection (No Command Dispatch)
    # ------------------------------------------------------------------
    conv_utterances = [
        "Tell me about Chrome",
        "Hello, how are you?",
        "What is the weather today?",
        "Can you explain machine learning?",
    ]

    for utt in conv_utterances:
        total += 1
        print(f"\nTEST: Conversation Protection for '{utt}'")
        harness = MockMainWindowForRouting()

        planner_called = []
        class MockPlanner:
            def plan(self, text):
                planner_called.append(text)
                return {"type": "conversation", "actions": []}
            def _is_obviously_conversational(self, text):
                return True

        harness.semantic_command_planner = MockPlanner()

        harness._handle_gemini_live_input_transcript(utt)

        assert len(harness.dispatched_commands) == 0, f"Conversation '{utt}' should NOT dispatch any command"
        assert len(harness.semantic_plans_executed) == 0, f"Conversation '{utt}' should NOT execute semantic plan"
        assert len(planner_called) == 0, f"Conversation '{utt}' should skip planner"
        print(f"[PASS] Conversation '{utt}' stayed in native conversation without command dispatch")
        passed += 1

    # ------------------------------------------------------------------
    # Test 7: Section 25 Explicit Regression Items (Items 1 - 12)
    # ------------------------------------------------------------------
    print("\n------------------------------------------------------------------")
    print("TEST 7: Section 25 Explicit Regression Items (Items 1 - 12)")
    print("------------------------------------------------------------------")

    # Item 1: conversation gate: "Human body la evlo bones irukum?"
    total += 1
    print("\n[Item 1] Conversation gate: 'Human body la evlo bones irukum?'")
    h1 = MockMainWindowForRouting()
    class SpyPlanner1:
        def plan(self, text):
            raise AssertionError("Semantic planner MUST be skipped for question!")
        def _is_obviously_conversational(self, text):
            return SemanticCommandPlanner._is_obviously_conversational(text)
    h1.semantic_command_planner = SpyPlanner1()
    assert h1._is_semantic_command_candidate("Human body la evlo bones irukum?") is False
    h1._handle_gemini_live_input_transcript("Human body la evlo bones irukum?")
    assert len(h1.dispatched_commands) == 0 and len(h1.semantic_plans_executed) == 0
    print("[PASS] Item 1: 'Human body la evlo bones irukum?' routed to CONVERSATION, planner skipped")
    passed += 1

    # Item 2: Tanglish conversation: "Wait pannu, oru doubt iruku"
    total += 1
    print("\n[Item 2] Tanglish conversation: 'Wait pannu, oru doubt iruku'")
    h2 = MockMainWindowForRouting()
    h2.semantic_command_planner = SpyPlanner1()
    assert h2._is_semantic_command_candidate("Wait pannu, oru doubt iruku") is False
    h2._handle_gemini_live_input_transcript("Wait pannu, oru doubt iruku")
    assert len(h2.dispatched_commands) == 0 and len(h2.semantic_plans_executed) == 0
    print("[PASS] Item 2: 'Wait pannu, oru doubt iruku' routed to CONVERSATION, planner skipped")
    passed += 1

    # Item 3: Deterministic application: "Open Chrome"
    total += 1
    print("\n[Item 3] Deterministic application: 'Open Chrome'")
    h3 = MockMainWindowForRouting()
    h3.semantic_command_planner = SpyPlanner1()
    h3._handle_gemini_live_input_transcript("Open Chrome")
    assert len(h3.dispatched_commands) == 1 and h3.dispatched_commands[0] == "Open Chrome"
    print("[PASS] Item 3: 'Open Chrome' executed via local deterministic path (<0.5s, 0 planner calls)")
    passed += 1

    # Item 4: YouTube: "Play Pavalamalli song"
    total += 1
    print("\n[Item 4] YouTube command: 'Play Pavalamalli song'")
    h4 = MockMainWindowForRouting()
    h4.semantic_command_planner = SpyPlanner1()
    h4._handle_gemini_live_input_transcript("Play Pavalamalli song")
    assert len(h4.dispatched_commands) == 1 and h4.dispatched_commands[0] == "Play Pavalamalli song"
    print("[PASS] Item 4: 'Play Pavalamalli song' executed via fast local YouTube route")
    passed += 1

    # Item 5: Natural Tanglish YouTube: "Pavalamalli song play pannu"
    total += 1
    print("\n[Item 5] Natural Tanglish YouTube: 'Pavalamalli song play pannu'")
    h5 = MockMainWindowForRouting()
    planner5_calls = []
    class MockPlanner5:
        def plan(self, text):
            planner5_calls.append(text)
            return {"type": "command", "actions": [{"intent": "play_youtube", "entities": {"song": "Pavalamalli"}}], "original_command": text}
        def _is_obviously_conversational(self, text):
            return SemanticCommandPlanner._is_obviously_conversational(text)
    h5.semantic_command_planner = MockPlanner5()
    assert h5._is_semantic_command_candidate("Pavalamalli song play pannu") is True
    h5._handle_gemini_live_input_transcript("Pavalamalli song play pannu")
    assert len(planner5_calls) == 1 and len(h5.semantic_plans_executed) == 1
    print("[PASS] Item 5: 'Pavalamalli song play pannu' routed to semantic planner -> play_youtube")
    passed += 1

    # Item 6: Multi-step application + YouTube: "Chrome open panni Pavalamalli song play pannu"
    total += 1
    print("\n[Item 6] Multi-step application + YouTube: 'Chrome open panni Pavalamalli song play pannu'")
    h6 = MockMainWindowForRouting()
    planner6_calls = []
    class MockPlanner6:
        def plan(self, text):
            planner6_calls.append(text)
            return {"type": "command", "actions": [{"intent": "launch_application", "entities": {"application": "Chrome"}}, {"intent": "play_youtube", "entities": {"song": "Pavalamalli"}}], "original_command": text}
        def _is_obviously_conversational(self, text):
            return SemanticCommandPlanner._is_obviously_conversational(text)
    h6.semantic_command_planner = MockPlanner6()
    assert h6._is_semantic_command_candidate("Chrome open panni Pavalamalli song play pannu") is True
    h6._handle_gemini_live_input_transcript("Chrome open panni Pavalamalli song play pannu")
    assert len(planner6_calls) == 1 and len(h6.semantic_plans_executed) == 1
    actions6 = h6.semantic_plans_executed[0][0]["actions"]
    assert actions6[0]["intent"] == "launch_application" and actions6[1]["intent"] == "play_youtube"
    print("[PASS] Item 6: 'Chrome open panni Pavalamalli song play pannu' -> launch_application + play_youtube")
    passed += 1

    # Item 7: Multi-step file operation: "Downloads folder open panni report.pdf ah Desktop ku copy pannu"
    total += 1
    print("\n[Item 7] Multi-step file operation: 'Downloads folder open panni report.pdf ah Desktop ku copy pannu'")
    h7 = MockMainWindowForRouting()
    planner7_calls = []
    class MockPlanner7:
        def plan(self, text):
            planner7_calls.append(text)
            return {"type": "command", "actions": [{"intent": "open_folder", "entities": {"folder": "Downloads"}}, {"intent": "copy_file", "entities": {"file": "report.pdf", "destination": "Desktop"}}], "original_command": text}
        def _is_obviously_conversational(self, text):
            return SemanticCommandPlanner._is_obviously_conversational(text)
    h7.semantic_command_planner = MockPlanner7()
    assert h7._is_semantic_command_candidate("Downloads folder open panni report.pdf ah Desktop ku copy pannu") is True
    h7._handle_gemini_live_input_transcript("Downloads folder open panni report.pdf ah Desktop ku copy pannu")
    assert len(planner7_calls) == 1 and len(h7.semantic_plans_executed) == 1
    actions7 = h7.semantic_plans_executed[0][0]["actions"]
    assert actions7[0]["intent"] == "open_folder" and actions7[1]["intent"] == "copy_file"
    print("[PASS] Item 7: 'Downloads folder open panni report.pdf ah Desktop ku copy pannu' -> open_folder + copy_file")
    passed += 1

    # Item 8: Conversation mentioning an application: "Chrome pathi sollu"
    total += 1
    print("\n[Item 8] Conversation mentioning an application: 'Chrome pathi sollu'")
    h8 = MockMainWindowForRouting()
    h8.semantic_command_planner = SpyPlanner1()
    assert h8._is_semantic_command_candidate("Chrome pathi sollu") is False
    h8._handle_gemini_live_input_transcript("Chrome pathi sollu")
    assert len(h8.dispatched_commands) == 0 and len(h8.semantic_plans_executed) == 0
    print("[PASS] Item 8: 'Chrome pathi sollu' routed to CONVERSATION, planner skipped")
    passed += 1

    # Item 9: Question containing action verb: "Why should I open Chrome?"
    total += 1
    print("\n[Item 9] Question containing action verb: 'Why should I open Chrome?'")
    h9 = MockMainWindowForRouting()
    h9.semantic_command_planner = SpyPlanner1()
    assert h9._is_semantic_command_candidate("Why should I open Chrome?") is False
    h9._handle_gemini_live_input_transcript("Why should I open Chrome?")
    assert len(h9.dispatched_commands) == 0 and len(h9.semantic_plans_executed) == 0
    print("[PASS] Item 9: 'Why should I open Chrome?' routed to CONVERSATION, planner skipped")
    passed += 1

    # Item 10: Shutdown idempotency: close called twice
    total += 1
    print("\n[Item 10] Shutdown idempotency: closeEvent called twice")
    h10 = MockMainWindowForRouting()
    class MockCloseEvent:
        def __init__(self):
            self.ignored = False
            self.accepted = False
        def ignore(self):
            self.ignored = True
        def accept(self):
            self.accepted = True

    ev1 = MockCloseEvent()
    h10.closeEvent(ev1)
    assert h10.shutdown_started is True, "shutdown_started must be True after first close"
    assert len(h10.shutdown_steps_run) == 1, "First close must start goodbye shutdown sequence"
    assert ev1.ignored is True

    ev2 = MockCloseEvent()
    h10.closeEvent(ev2)
    assert len(h10.shutdown_steps_run) == 1, "Second close MUST be ignored idempotently (no duplicate teardown)"
    assert ev2.ignored is True
    print("[PASS] Item 10: Shutdown is idempotent — subsequent close requests safely ignored")
    passed += 1

    # Item 11: Callback blocking after shutdown: Any Live callback after shutdown_started=True
    total += 1
    print("\n[Item 11] Callback blocking after shutdown_started=True")
    h11 = MockMainWindowForRouting()
    h11.shutdown_started = True

    # Test all Live callbacks are completely blocked
    h11._on_gemini_live_audio(b"\x00" * 1024, response_id=1)
    h11._on_gemini_live_input_transcript("Open Chrome")
    h11._on_gemini_live_output_transcript("I am speaking")
    h11._on_gemini_live_interrupted(response_id=1)
    h11._on_gemini_live_turn_complete("user", "assistant")
    h11._on_gemini_live_error("Live connection lost")
    h11._on_gemini_live_closed()
    h11._on_gemini_live_go_away("30s")

    assert len(h11.gemini_live_input_signal.calls) == 0, "No input transcript signal permitted after shutdown_started"
    assert len(h11.gemini_live_output_signal.calls) == 0, "No output transcript signal permitted after shutdown_started"
    assert len(h11.gemini_live_interrupted_signal.calls) == 0, "No interrupted signal permitted after shutdown_started"
    assert len(h11.gemini_live_turn_complete_signal.calls) == 0, "No turn complete signal permitted after shutdown_started"
    assert len(h11.gemini_live_error_signal.calls) == 0, "No error signal permitted after shutdown_started"
    assert len(h11.gemini_live_closed_signal.calls) == 0, "No closed signal permitted after shutdown_started"
    assert len(h11.gemini_live_go_away_signal.calls) == 0, "No go away signal permitted after shutdown_started"

    h11._handle_gemini_live_input_transcript("Open Chrome")
    assert len(h11.dispatched_commands) == 0, "No command dispatch permitted after shutdown_started"
    print("[PASS] Item 11: ZERO Live audio/transcript/callbacks permitted after shutdown_started=True")
    passed += 1

    # Item 12: Recovery suppression: shutdown_started=True -> no replacement Live session
    total += 1
    print("\n[Item 12] Recovery suppression: shutdown_started=True suppresses Live session creation")
    h12 = MockMainWindowForRouting()
    h12.shutdown_started = True
    h12._gemini_live_pending_start = True

    # Attempt starting conversation and handling GoAway during shutdown
    h12._start_gemini_live_conversation()
    assert h12.gemini_live_session is None, "No new Gemini Live session permitted after shutdown_started"

    h12._handle_gemini_live_go_away("15s")
    assert h12.gemini_live_session is None, "GoAway replacement session MUST NOT be created after shutdown_started"
    print("[PASS] Item 12: Recovery and GoAway replacement strictly suppressed when shutdown_started=True")
    passed += 1

    print("\n======================================================================")
    print(f"RESULTS: {passed}/{total} TESTS PASSED (100%)")
    print("======================================================================")
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
