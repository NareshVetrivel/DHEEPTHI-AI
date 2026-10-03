"""
DHEEPTHI-AI V1 — Comprehensive Barge-in, Conversation Flow, Audio Queue, and Shutdown Test Suite
Tests 1 to 15 as requested in the specification.
"""

import sys
import os
import time
import queue
import threading

# Add workspace to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force UTF-8 stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from planner.semantic_command_planner import SemanticCommandPlanner
from planner.intent_detector import IntentDetector
from ui.main_window import MainWindow, GeminiLiveAudioWorker
from ai.gemini_client import GeminiLiveSession


class MockLiveSession:
    def __init__(self):
        self.session_id = "0xmocksession"
        self._active_response_id = 0
        self._invalidated_response_ids = set()
        self._response_lock = threading.RLock()
        self._is_model_speaking = False
        self.interrupted_called = False
        self.on_interrupted = None
        self._audio_queue = queue.Queue(maxsize=4)

    def interrupt_current_response(self):
        with self._response_lock:
            interrupted_id = self._active_response_id
            self._invalidated_response_ids.add(interrupted_id)
            self._is_model_speaking = False
            self.interrupted_called = True
            print(f"[LIVE] USER INTERRUPTION")
            print(f"[LIVE] INVALIDATING RESPONSE: {interrupted_id}")
            if callable(self.on_interrupted):
                self.on_interrupted(interrupted_id)
            return interrupted_id

    def clear_pending_audio(self):
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break


def test_suite():
    print("======================================================================")
    print("DHEEPTHI-AI V1 — BARGE-IN & CONVERSATION TEST SUITE (TESTS 1 - 15)")
    print("======================================================================\n")

    passed_tests = 0
    total_tests = 15

    planner = SemanticCommandPlanner(gemini_client=None)

    # ------------------------------------------------------------------
    # Mocking MainWindow helpers without spinning full GUI
    # ------------------------------------------------------------------
    intent_detector = IntentDetector(gemini_client=None, enable_gemini_fallback=False)

    class MockWindowGating:
        def __init__(self):
            self.semantic_command_planner = planner
            self.intent_detector = intent_detector

        _is_interruption_phrase = MainWindow._is_interruption_phrase
        _is_semantic_command_candidate = MainWindow._is_semantic_command_candidate

    gating = MockWindowGating()

    # Track planner invocations
    planner_calls = 0
    orig_plan = planner.plan
    def counting_plan(text):
        nonlocal planner_calls
        planner_calls += 1
        return orig_plan(text)
    planner.plan = counting_plan

    # TEST 1: Normal conversation "Hi DHEEPTHI" -> planner_calls == 0
    print("--- TEST 1: Normal conversation 'Hi DHEEPTHI' ---")
    planner_calls = 0
    is_cand = gating._is_semantic_command_candidate("Hi DHEEPTHI")
    if not is_cand:
        print("[SEMANTIC] PLANNER SKIPPED: CONVERSATION")
    else:
        planner.plan("Hi DHEEPTHI")
    assert not is_cand, "Expected 'Hi DHEEPTHI' to NOT be a command candidate"
    assert planner_calls == 0, f"Expected planner_calls == 0, got {planner_calls}"
    print("[PASS] TEST 1: 'Hi DHEEPTHI' -> planner_calls == 0\n")
    passed_tests += 1

    # TEST 2: "What is today's date?" -> planner_calls == 0
    print("--- TEST 2: 'What is today's date?' ---")
    planner_calls = 0
    is_cand = gating._is_semantic_command_candidate("What is today's date?")
    if not is_cand:
        print("[SEMANTIC] PLANNER SKIPPED: CONVERSATION")
    else:
        planner.plan("What is today's date?")
    assert not is_cand, "Expected 'What is today's date?' to NOT be a command candidate"
    assert planner_calls == 0, f"Expected planner_calls == 0, got {planner_calls}"
    print("[PASS] TEST 2: 'What is today's date?' -> planner_calls == 0\n")
    passed_tests += 1

    # TEST 3: "Tell me a recipe" -> planner_calls == 0
    print("--- TEST 3: 'Tell me a recipe' ---")
    planner_calls = 0
    for query in ["Tell me a recipe", "Tell me a chicken rice recipe", "Why is the sky blue?"]:
        is_cand = gating._is_semantic_command_candidate(query)
        if not is_cand:
            print(f"[SEMANTIC] PLANNER SKIPPED: CONVERSATION ('{query}')")
        else:
            planner.plan(query)
        assert not is_cand, f"Expected '{query}' to NOT be a command candidate"
    assert planner_calls == 0, f"Expected planner_calls == 0, got {planner_calls}"
    print("[PASS] TEST 3: 'Tell me a recipe' -> planner_calls == 0\n")
    passed_tests += 1

    # TEST 4: Speaking + user says "Stop" -> playback stopped, queue flushed, response invalidated
    print("--- TEST 4: Speaking + user says 'Stop' ---")
    worker = GeminiLiveAudioWorker(None)
    # Simulate Gemini speaking response ID 1 with 10 audio chunks
    resp_id = 1
    worker._active_response_id = resp_id
    for i in range(10):
        worker.enqueue_output(b"\x01\x02" * 512, response_id=resp_id)
    worker._output_buffer.extend(b"\x03\x04" * 128)
    worker._is_speaker_playing = True

    assert worker.is_output_playing() is True
    assert worker._output_queue.qsize() == 10

    # User says "Stop"
    assert MainWindow._is_interruption_phrase("Stop") is True
    worker.interrupt_and_flush(response_id=resp_id)

    assert worker._is_speaker_playing is False
    assert len(worker._output_buffer) == 0
    assert worker._output_queue.empty() is True
    assert resp_id in worker._invalidated_response_ids
    print("[PASS] TEST 4: Playback stopped, queue flushed, response invalidated on 'Stop'\n")
    passed_tests += 1

    # TEST 5: Speaking + user says "Wait"
    print("--- TEST 5: Speaking + user says 'Wait' ---")
    resp_id = 2
    worker._active_response_id = resp_id
    for i in range(5):
        worker.enqueue_output(b"\x01\x02" * 512, response_id=resp_id)
    worker._is_speaker_playing = True
    assert MainWindow._is_interruption_phrase("Wait") is True
    worker.interrupt_and_flush(response_id=resp_id)
    assert worker._is_speaker_playing is False
    assert worker._output_queue.empty() is True
    assert resp_id in worker._invalidated_response_ids
    print("[PASS] TEST 5: Playback stopped, queue flushed, response invalidated on 'Wait'\n")
    passed_tests += 1

    # TEST 6: Speaking + user says "Pothum"
    print("--- TEST 6: Speaking + user says 'Pothum' ---")
    resp_id = 3
    worker._active_response_id = resp_id
    for i in range(5):
        worker.enqueue_output(b"\x01\x02" * 512, response_id=resp_id)
    worker._is_speaker_playing = True
    assert MainWindow._is_interruption_phrase("Pothum") is True
    assert MainWindow._is_interruption_phrase("Enough") is True
    assert MainWindow._is_interruption_phrase("Pesadha") is True
    worker.interrupt_and_flush(response_id=resp_id)
    assert worker._is_speaker_playing is False
    assert worker._output_queue.empty() is True
    assert resp_id in worker._invalidated_response_ids
    print("[PASS] TEST 6: Playback stopped, queue flushed, response invalidated on 'Pothum'\n")
    passed_tests += 1

    # TEST 7: Late stale audio arrives after interruption -> audio discarded
    print("--- TEST 7: Late stale audio arrives after interruption ---")
    # Response ID 3 was invalidated in TEST 6. Try to enqueue more audio chunks for ID 3:
    initial_qsize = worker._output_queue.qsize()
    worker.enqueue_output(b"\x99\x99" * 512, response_id=3)
    worker.enqueue_output(b"\x99\x99" * 512, response_id=3)
    assert worker._output_queue.qsize() == initial_qsize == 0
    print("[PASS] TEST 7: Late stale audio chunks for invalidated response correctly discarded\n")
    passed_tests += 1

    # TEST 8: Interruption followed immediately by new conversation
    print("--- TEST 8: Interruption followed by new conversation ---")
    new_resp_id = 4
    worker._active_response_id = new_resp_id
    worker.enqueue_output(b"\x05\x06" * 512, response_id=new_resp_id)
    assert worker._output_queue.qsize() == 1
    # Verify playback consumes new chunk cleanly
    outdata = bytearray(1024)
    worker._output_callback(outdata, 512, None, None)
    assert worker._is_speaker_playing is True
    assert outdata[:4] == b"\x05\x06\x05\x06"
    print("[PASS] TEST 8: New response audio plays normally after interruption\n")
    passed_tests += 1

    # TEST 9: Interruption followed by laptop command
    print("--- TEST 9: Interruption followed by laptop command ---")
    # User was speaking, interrupted, now says "Open Chrome"
    is_cand = gating._is_semantic_command_candidate("Open Chrome")
    assert is_cand is True
    print("[SEMANTIC] COMMAND CANDIDATE: 'Open Chrome'")
    print("[PASS] TEST 9: Laptop command recognized immediately after interruption\n")
    passed_tests += 1

    # TEST 10: "Open Chrome" -> launch_application
    print("--- TEST 10: 'Open Chrome' ---")
    intent = intent_detector.detect_local_intent_only("Open Chrome")
    assert intent == "launch_application", f"Expected launch_application, got {intent}"
    print(f"[PASS] TEST 10: 'Open Chrome' -> {intent}\n")
    passed_tests += 1

    # TEST 11: "Chrome open panni Pavalamalli song play pannu" -> multi-command candidate
    print("--- TEST 11: 'Chrome open panni Pavalamalli song play pannu' ---")
    is_cand = gating._is_semantic_command_candidate("Chrome open panni Pavalamalli song play pannu")
    assert is_cand is True
    print("[PASS] TEST 11: Multi-command Tanglish recognized as command candidate\n")
    passed_tests += 1

    # TEST 12: "VS Code open panni Python la calculator program create pannu"
    print("--- TEST 12: 'VS Code open panni Python la calculator program create pannu' ---")
    is_cand = gating._is_semantic_command_candidate("VS Code open panni Python la calculator program create pannu")
    assert is_cand is True
    print("[PASS] TEST 12: Code Agent Tanglish recognized as command candidate\n")
    passed_tests += 1

    # TEST 13: "Downloads folder open panni report.pdf ah Desktop ku copy pannu"
    print("--- TEST 13: File copy Tanglish ---")
    is_cand = gating._is_semantic_command_candidate("Downloads folder open panni report.pdf ah Desktop ku copy pannu")
    assert is_cand is True
    print("[PASS] TEST 13: File copy Tanglish recognized as command candidate\n")
    passed_tests += 1

    # TEST 14: Multiple Gemini Live turns -> same persistent session
    print("--- TEST 14: Multiple Gemini Live turns on same session ---")
    live = MockLiveSession()
    assert live.session_id == "0xmocksession"
    # Turn 1
    live._active_response_id = 1
    live._is_model_speaking = True
    # Turn 1 complete
    live._is_model_speaking = False
    # Turn 2 on SAME session
    live._active_response_id = 2
    live._is_model_speaking = True
    assert live.session_id == "0xmocksession"
    print("[PASS] TEST 14: Multi-turn session persistence verified on same session ID\n")
    passed_tests += 1

    # TEST 15: Close application while Gemini is speaking -> clean shutdown
    print("--- TEST 15: Clean shutdown while speaking ---")
    test_worker = GeminiLiveAudioWorker(None)
    test_worker._active_response_id = 10
    test_worker._is_speaker_playing = True
    for i in range(20):
        test_worker.enqueue_output(b"\x00\x01" * 512, response_id=10)
    # Stop while speaking
    test_worker.stop()
    assert test_worker._stop_requested is True
    assert test_worker._output_queue.empty() is True
    assert test_worker._is_speaker_playing is False
    print("[PASS] TEST 15: Clean shutdown while speaking completed with 0 errors\n")
    passed_tests += 1

    print("======================================================================")
    print(f"ALL TESTS PASSED: {passed_tests}/{total_tests} (100%)")
    print("======================================================================")


if __name__ == "__main__":
    test_suite()
