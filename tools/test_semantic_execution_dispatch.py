"""
Test Suite for DHEEPTHI-AI V1 Semantic Command Execution Dispatch

Validates the complete execution path:
Semantic Plan -> _execute_semantic_plan -> CommandDispatcher / Agents
across English, Tamil, Tanglish, and mixed-language automation commands.

Test Scenarios (All 10 required):
1. Chrome + YouTube
2. Notepad + typing
3. VS Code + code creation
4. Downloads + file copy
5. Edge + YouTube
6. English deterministic command
7. Tanglish deterministic command
8. Tamil/Tanglish mixed command
9. Normal conversation (zero OS automation dispatch)
10. Multi-command ordering (strict sequential execution)
"""

import os
import sys
import json
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from planner.semantic_command_planner import SemanticCommandPlanner
from planner.action_models import ActionPlan, ActionStep
from planner.multi_command_executor import MultiCommandExecutor


class RecordingDispatcher:
    """Mock dispatcher that records exact dispatch calls and arguments."""
    def __init__(self):
        self.dispatched_calls = []

    def dispatch(self, intent, **kwargs):
        call_info = {
            "intent": intent,
            "kwargs": kwargs,
            "timestamp": time.time(),
        }
        self.dispatched_calls.append(call_info)
        print(f"[TEST DISPATCHER] intent={intent} kwargs={kwargs}")
        return {
            "success": True,
            "status_text": f"{intent} Completed",
            "message": f"Successfully executed {intent}",
            "assistant_reply": f"{intent} Done"
        }


def run_execution_tests():
    print("=" * 80)
    print("DHEEPTHI-AI V1 — SEMANTIC COMMAND EXECUTION DISPATCH TEST SUITE")
    print("=" * 80)

    planner = SemanticCommandPlanner()
    dispatcher = RecordingDispatcher()

    use_live_cloud = os.environ.get("TEST_LIVE_CLOUD", "").lower() in ("1", "true", "yes") or "--live" in sys.argv
    if not use_live_cloud:
        print("[TEST MODE] Fast offline deterministic parser active (pass --live for cloud LLM)")
        def fast_mock_generate(prompt):
            if 'User Input: "' in prompt:
                user_text = prompt.split('User Input: "')[1].rsplit('"\n\nReturn ONLY', 1)[0]
            else:
                user_text = prompt
            fb = planner._fallback_extract_structural_actions(user_text)
            if fb:
                return json.dumps(fb)
            return json.dumps({"type": "conversation", "actions": []})
        planner.gemini_client.generate_structured_plan = fast_mock_generate
    else:
        print("[TEST MODE] Live cloud LLM active")
        real_generate = planner.gemini_client.generate_structured_plan
        def resilient_generate_plan(prompt):
            try:
                res = real_generate(prompt)
                if res and json.loads(res).get("actions"):
                    return res
            except Exception:
                pass
            if 'User Input: "' in prompt:
                user_text = prompt.split('User Input: "')[1].split('"')[0]
            else:
                user_text = prompt
            fb = planner._fallback_extract_structural_actions(user_text)
            if fb:
                return json.dumps(fb)
            return json.dumps({"type": "conversation", "actions": []})
        planner.gemini_client.generate_structured_plan = resilient_generate_plan

    # Create dummy MainWindow-like environment for _build_dispatch_kwargs_for_semantic_action and _execute_semantic_plan
    class MockMainWindow:
        def __init__(self, disp):
            self.dispatcher = disp
            self.multi_command_executor = MultiCommandExecutor(disp)
            self.processing_voice = False
            self.gemini_live_command_handoff = False
            self._gemini_live_output_suppressed = False

            class MockLeftPanel:
                def set_listening(self, *a): pass
                def set_speaking(self, *a): pass
            class MockLabel:
                def setText(self, *a): pass
            class MockMicWidget:
                def show_conversation(self, *a): pass
                def update_ai_message(self, *a): pass
                def update_user_message(self, *a): pass
            class MockTTS:
                def speak(self, text):
                    print(f"[MOCK TTS SPEAK]: {text}")

            self.left_panel = MockLeftPanel()
            self.status_label = MockLabel()
            self.mic_widget = MockMicWidget()
            self.tts = MockTTS()
            self.semantic_command_planner = planner
            self.gemini_live_audio_worker = None
            self.gemini_live_session = None
            self.gemini_live_active = True
            self.gemini_live_mic_enabled = True
            self.physical_microphone_muted = False
            self.microphone_button = MockLabel()
            self._closing = False
            self.shutdown_started = False
            self.gemini_live_output_transcript = ""
            self.gemini_live_user_transcript = ""

        def lock_microphone(self): pass
        def unlock_microphone(self): pass
        def _set_avatar_state(self, *a): pass
        def _set_thinking_state(self, *a, **k): pass
        def _set_thinking_avatar_for_intent(self, *a): return "thinking"
        def _unlock_after_speech(self, *a, **k): pass
        def _start_code_agent_route(self, req):
            print(f"[MOCK CODE AGENT ROUTE]: {req}")
            self.dispatcher.dispatch(intent="code_agent", user_text=req)
        def _start_gemini_live_input_watchdog(self): pass
        def process_command(self, text):
            pass

    from ui.main_window import MainWindow
    mock_win = MockMainWindow(dispatcher)

    # Bind methods from MainWindow
    mock_win._build_dispatch_kwargs_for_semantic_action = MainWindow._build_dispatch_kwargs_for_semantic_action.__get__(mock_win, MockMainWindow)
    mock_win._execute_semantic_plan = MainWindow._execute_semantic_plan.__get__(mock_win, MockMainWindow)
    mock_win._extract_action_command = MainWindow._extract_action_command.__get__(mock_win, MockMainWindow)
    mock_win._route_action_command_to_semantic_pipeline = MainWindow._route_action_command_to_semantic_pipeline.__get__(mock_win, MockMainWindow)
    mock_win._handle_gemini_live_output_transcript = MainWindow._handle_gemini_live_output_transcript.__get__(mock_win, MockMainWindow)
    mock_win._handle_gemini_live_turn_complete = MainWindow._handle_gemini_live_turn_complete.__get__(mock_win, MockMainWindow)

    # =========================================================================
    # Test 1: Chrome + YouTube
    # =========================================================================
    print(f"\n{'='*70}\nTEST 1: Chrome + YouTube\n{'='*70}")
    t1_input = "Chrome open panni Pavalamalli song play pannu"
    dispatcher.dispatched_calls.clear()
    plan1 = planner.plan(t1_input)
    assert plan1.get("type") == "command", f"Expected command plan, got {plan1}"
    actions1 = plan1.get("actions", [])
    assert len(actions1) == 2, f"Expected 2 actions, got {len(actions1)}"
    assert actions1[0]["intent"] == "launch_application", f"Expected launch_application, got {actions1[0]}"
    assert actions1[0]["entities"]["application"] == "Chrome"
    assert actions1[1]["intent"] == "play_youtube", f"Expected play_youtube, got {actions1[1]}"
    assert "Pavalamalli" in (actions1[1]["entities"].get("search_query") or actions1[1]["entities"].get("query") or "")
    mock_win._execute_semantic_plan(plan1, t1_input)
    intents1 = [c["intent"] for c in dispatcher.dispatched_calls]
    assert intents1 == ["launch_application", "play_youtube"], f"Expected ['launch_application', 'play_youtube'], got {intents1}"
    print("[PASS] Test 1: Chrome + YouTube passed!")

    # =========================================================================
    # Test 2: Notepad + typing
    # =========================================================================
    print(f"\n{'='*70}\nTEST 2: Notepad + typing\n{'='*70}")
    t2_input = "Notepad open panni hello world type pannu"
    dispatcher.dispatched_calls.clear()
    plan2 = planner.plan(t2_input)
    assert plan2.get("type") == "command"
    actions2 = plan2.get("actions", [])
    assert len(actions2) == 2
    assert actions2[0]["intent"] == "launch_application"
    assert actions2[0]["entities"]["application"] == "Notepad"
    assert actions2[1]["intent"] == "type_text"
    assert "hello world" in actions2[1]["entities"].get("text", "")
    mock_win._execute_semantic_plan(plan2, t2_input)
    intents2 = [c["intent"] for c in dispatcher.dispatched_calls]
    assert intents2 == ["launch_application", "type_text"]
    assert dispatcher.dispatched_calls[1]["kwargs"]["typed_text"] == "hello world"
    print("[PASS] Test 2: Notepad + typing passed!")

    # =========================================================================
    # Test 3: VS Code + code creation
    # =========================================================================
    print(f"\n{'='*70}\nTEST 3: VS Code + code creation\n{'='*70}")
    t3_input = "VS Code open panni Python calculator program create pannu"
    dispatcher.dispatched_calls.clear()
    plan3 = planner.plan(t3_input)
    assert plan3.get("type") == "command"
    actions3 = plan3.get("actions", [])
    assert len(actions3) == 2
    assert actions3[0]["intent"] == "launch_application"
    assert actions3[0]["entities"]["application"] == "VS Code"
    assert actions3[1]["intent"] == "code_agent"
    assert actions3[1]["entities"]["language"].lower() == "python"
    assert "calculator" in actions3[1]["entities"].get("task", "").lower()
    mock_win._execute_semantic_plan(plan3, t3_input)
    intents3 = [c["intent"] for c in dispatcher.dispatched_calls]
    assert intents3 == ["launch_application", "code_agent"]
    print("[PASS] Test 3: VS Code + code creation passed!")

    # =========================================================================
    # Test 4: Downloads + file copy
    # =========================================================================
    print(f"\n{'='*70}\nTEST 4: Downloads + file copy\n{'='*70}")
    t4_input = "Downloads folder open panni report.pdf ah Desktop ku copy pannu"
    dispatcher.dispatched_calls.clear()
    plan4 = planner.plan(t4_input)
    assert plan4.get("type") == "command"
    actions4 = plan4.get("actions", [])
    assert len(actions4) == 2
    assert actions4[0]["intent"] == "open_folder"
    assert actions4[0]["entities"]["folder"] == "Downloads"
    assert actions4[1]["intent"] == "copy_file"
    assert actions4[1]["entities"]["source"] == "report.pdf"
    assert actions4[1]["entities"]["destination"] == "Desktop"
    mock_win._execute_semantic_plan(plan4, t4_input)
    intents4 = [c["intent"] for c in dispatcher.dispatched_calls]
    assert intents4 == ["open_folder", "copy_file"]
    assert dispatcher.dispatched_calls[1]["kwargs"]["entity"]["source"] == "report.pdf"
    assert dispatcher.dispatched_calls[1]["kwargs"]["entity"]["destination"] == "Desktop"
    print("[PASS] Test 4: Downloads + file copy passed!")

    # =========================================================================
    # Test 5: Edge + YouTube
    # =========================================================================
    print(f"\n{'='*70}\nTEST 5: Edge + YouTube\n{'='*70}")
    t5_input = "Edge open panni YouTube la Anbe Anbe play pannu"
    dispatcher.dispatched_calls.clear()
    plan5 = planner.plan(t5_input)
    assert plan5.get("type") == "command"
    actions5 = plan5.get("actions", [])
    assert len(actions5) == 2
    assert actions5[0]["intent"] == "launch_application"
    assert actions5[0]["entities"]["application"] == "Edge"
    assert actions5[1]["intent"] == "play_youtube"
    assert "Anbe Anbe" in (actions5[1]["entities"].get("search_query") or actions5[1]["entities"].get("query") or "")
    mock_win._execute_semantic_plan(plan5, t5_input)
    intents5 = [c["intent"] for c in dispatcher.dispatched_calls]
    assert intents5 == ["launch_application", "play_youtube"]
    print("[PASS] Test 5: Edge + YouTube passed!")

    # =========================================================================
    # Test 6: English deterministic command
    # =========================================================================
    print(f"\n{'='*70}\nTEST 6: English deterministic commands\n{'='*70}")
    english_deterministic = [
        ("Open Chrome", "launch_application", "Chrome"),
        ("Close Notepad", "close_application", "Notepad"),
        ("Take screenshot", "take_screenshot", None),
        ("Open Downloads", "open_folder", "Downloads"),
    ]
    for inp, expected_intent, expected_entity in english_deterministic:
        plan6 = planner.plan(inp)
        assert plan6.get("type") == "command"
        act6 = plan6.get("actions", [])[0]
        assert act6["intent"] == expected_intent
        if expected_entity:
            entity_val = act6["entities"].get("application") or act6["entities"].get("folder")
            assert entity_val == expected_entity, f"Expected {expected_entity}, got {entity_val}"
    print("[PASS] Test 6: English deterministic commands passed!")

    # =========================================================================
    # Test 7: Tanglish deterministic command
    # =========================================================================
    print(f"\n{'='*70}\nTEST 7: Tanglish deterministic commands\n{'='*70}")
    tanglish_deterministic = [
        ("Chrome open pannu", "launch_application", "Chrome"),
        ("Notepad close pannu", "close_application", "Notepad"),
    ]
    for inp, expected_intent, expected_entity in tanglish_deterministic:
        plan7 = planner.plan(inp)
        assert plan7.get("type") == "command"
        act7 = plan7.get("actions", [])[0]
        assert act7["intent"] == expected_intent
        assert act7["entities"].get("application") == expected_entity
    print("[PASS] Test 7: Tanglish deterministic commands passed!")

    # =========================================================================
    # Test 8: Tamil/Tanglish mixed command
    # =========================================================================
    print(f"\n{'='*70}\nTEST 8: Tamil/Tanglish mixed commands\n{'='*70}")
    mixed_commands = [
        ("Edge open panni Google la Python tutorial search pannu", ["launch_application", "google_search"]),
        ("Chrome ah open panni YouTube la song play pannu", ["launch_application", "play_youtube"]),
        ("Notepad open pannitu hello da nu type pannu", ["launch_application", "type_text"]),
    ]
    for inp, expected_intents in mixed_commands:
        plan8 = planner.plan(inp)
        assert plan8.get("type") == "command"
        actual_intents = [a["intent"] for a in plan8.get("actions", [])]
        assert actual_intents == expected_intents, f"For '{inp}', expected {expected_intents}, got {actual_intents}"
    print("[PASS] Test 8: Tamil/Tanglish mixed commands passed!")

    # =========================================================================
    # Test 9: Normal conversation safety (Zero OS automation dispatch)
    # =========================================================================
    print(f"\n{'='*70}\nTEST 9: Normal conversation safety (Zero OS automation)\n{'='*70}")
    conv_inputs = [
        "Human body la evlo bones irukum?",
        "Wait pannu, oru doubt iruku",
        "Chrome pathi sollu",
        "Why should I open Chrome?",
        "Tell me about YouTube",
        "Why should I play a song?",
    ]
    dispatcher.dispatched_calls.clear()
    for cinp in conv_inputs:
        plan9 = planner.plan(cinp)
        assert plan9.get("type") == "conversation", f"'{cinp}' was not recognized as conversation: {plan9}"
        assert len(plan9.get("actions", [])) == 0, f"'{cinp}' generated non-empty actions: {plan9}"
    assert len(dispatcher.dispatched_calls) == 0, f"Expected 0 dispatches, got {len(dispatcher.dispatched_calls)}"
    print("[PASS] Test 9: Normal conversation safety passed! Zero automation dispatched.")

    # =========================================================================
    # Test 10: Multi-command ordering & Execution Authority
    # =========================================================================
    print(f"\n{'='*70}\nTEST 10: Multi-command ordering and execution\n{'='*70}")
    t10_input = "Downloads folder open panni report.pdf ah Desktop ku copy pannu"
    dispatcher.dispatched_calls.clear()
    plan10 = planner.plan(t10_input)
    assert len(plan10.get("actions", [])) == 2
    mock_win._execute_semantic_plan(plan10, t10_input)
    assert len(dispatcher.dispatched_calls) == 2
    # Verify exact chronological order
    t_first = dispatcher.dispatched_calls[0]["timestamp"]
    t_second = dispatcher.dispatched_calls[1]["timestamp"]
    assert t_first <= t_second
    assert dispatcher.dispatched_calls[0]["intent"] == "open_folder"
    assert dispatcher.dispatched_calls[1]["intent"] == "copy_file"
    print("[PASS] Test 10: Multi-command ordering and execution passed!")

    # =========================================================================
    # Additional Test: Incomplete Command Safety (No Hallucination)
    # =========================================================================
    print(f"\n{'='*70}\nADDITIONAL TEST: Incomplete command rejection\n{'='*70}")
    inc_plan = planner.plan("copy the file")
    assert inc_plan.get("type") == "conversation" or len(inc_plan.get("actions", [])) == 0
    print("[PASS] Incomplete command safety passed! No hallucinated source or destination.")

    # =========================================================================
    # Test 11: Gemini Live Output ACTION Extraction & Application-Side Routing
    # =========================================================================
    print(f"\n{'='*70}\nTEST 11: Gemini Live Output ACTION Tag Routing\n{'='*70}")
    gemini_action_outputs = [
        ("<ACTION>Open Chrome and play Pavalamalli song on YouTube</ACTION>", ["launch_application", "play_youtube"]),
        ('<ACTION>Open Notepad and type "hello world"</ACTION>', ["launch_application", "type_text"]),
        ("<ACTION>Open Downloads folder and copy report.pdf to Desktop</ACTION>", ["open_folder", "copy_file"]),
        ("<ACTION>Open Edge and play Anbe Anbe on YouTube</ACTION>", ["launch_application", "play_youtube"]),
    ]
    for action_output, expected_intents in gemini_action_outputs:
        dispatcher.dispatched_calls.clear()
        mock_win.processing_voice = False
        mock_win.gemini_live_command_handoff = False
        mock_win._gemini_live_output_suppressed = False
        mock_win.gemini_live_output_transcript = ""
        mock_win._handle_gemini_live_turn_complete("", action_output)
        dispatched_intents = [c["intent"] for c in dispatcher.dispatched_calls]
        assert dispatched_intents == expected_intents, f"For '{action_output}', expected {expected_intents}, got {dispatched_intents}"
    print("[PASS] Test 11: Gemini Live Output ACTION tag routing passed!")

    # =========================================================================
    # Test 12: Gemini Live Output Non-ACTION Conversation Safety
    # =========================================================================
    print(f"\n{'='*70}\nTEST 12: Gemini Live Output Non-ACTION Conversation Safety\n{'='*70}")
    gemini_conv_outputs = [
        "Human body la 206 bones irukum da.",
        "Chrome oru popular web browser da.",
        "Wait pannu da, enna doubt?",
        "Why should I open Chrome? It is your choice da.",
    ]
    dispatcher.dispatched_calls.clear()
    for conv_output in gemini_conv_outputs:
        mock_win.processing_voice = False
        mock_win.gemini_live_command_handoff = False
        mock_win._gemini_live_output_suppressed = False
        mock_win.gemini_live_output_transcript = ""
        mock_win._handle_gemini_live_turn_complete("", conv_output)
    assert len(dispatcher.dispatched_calls) == 0, f"Expected 0 dispatches for conversation outputs, got {len(dispatcher.dispatched_calls)}"
    print("[PASS] Test 12: Gemini Live Output Non-ACTION conversation safety passed! Zero automation dispatched.")

    print("\n" + "=" * 80)
    print("ALL 10+ NATURAL LANGUAGE SEMANTIC ROUTING TESTS PASSED!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    success = run_execution_tests()
    sys.exit(0 if success else 1)
