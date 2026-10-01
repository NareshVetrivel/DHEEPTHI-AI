"""
Automated Multi-Turn and Command Handoff Test Suite for DHEEPTHI-AI V1
Runs 100% programmatically without requiring human microphone interaction.
"""

import asyncio
import io
import os
import sys
import time
import wave
import struct

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from config import settings
from ai.gemini_client import GeminiLiveSession
from planner.intent_detector import IntentDetector
import numpy as np
import soundfile as sf
import edge_tts


async def generate_speech_pcm(text: str) -> bytes:
    """Generate known-good 16 kHz mono 16-bit PCM for testing."""
    tts = edge_tts.Communicate(text=text, voice="en-US-GuyNeural")
    mp3_data = b""
    async for chunk in tts.stream():
        if chunk["type"] == "audio":
            mp3_data += chunk["data"]

    data, samplerate = sf.read(io.BytesIO(mp3_data))
    if len(data.shape) > 1:
        data = data.mean(axis=1)

    if samplerate != 16000:
        import scipy.signal
        num_samples = int(len(data) * 16000 / samplerate)
        data = scipy.signal.resample(data, num_samples)

    pcm16 = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    return pcm16.tobytes()


async def run_automated_tests():
    print("=" * 70)
    print("DHEEPTHI-AI V1 — AUTOMATED VERIFICATION SUITE")
    print("=" * 70)

    # ----------------------------------------------------
    # TEST SUITE 1: Intent Routing Unit Verification
    # ----------------------------------------------------
    print("\n--- TEST SUITE 1: INTENT ROUTING (AUTOMATED) ---")
    detector = IntentDetector()
    
    test_cases = [
        ("Hello, how are you?", "ai_chat"),
        ("Open Chrome", "launch_application"),
        ("Open Downloads", "open_folder"),
        ("Tell me about Chrome", "ai_chat"),
    ]

    routing_passed = True
    for phrase, expected_intent in test_cases:
        actual_intent = detector.detect_local_intent_only(phrase)
        status = "PASS" if actual_intent == expected_intent else "FAIL"
        if status == "FAIL":
            routing_passed = False
        print(f"Phrase: '{phrase}' | Expected: {expected_intent} | Actual: {actual_intent} | [{status}]")

    print(f"Intent Routing Test Result: {'PASS' if routing_passed else 'FAIL'}")

    # ----------------------------------------------------
    # TEST SUITE 2: Persistent Gemini Live Multi-Turn Test
    # ----------------------------------------------------
    print("\n--- TEST SUITE 2: PERSISTENT GEMINI LIVE MULTI-TURN (AUTOMATED) ---")
    
    api_key = os.getenv("GEMINI_API_KEY_1") or os.getenv("GEMINI_API_KEY")
    model = getattr(settings, "GEMINI_LIVE_MODEL", None) or os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
    
    if not api_key:
        print("[FAIL] No Gemini API key available.")
        return

    print(f"Connecting Gemini Live Session (Model: {model})...")

    turn_1_done = asyncio.Event()
    turn_2_done = asyncio.Event()

    turn_1_rx_user = ""
    turn_1_rx_ai = ""
    turn_1_audio_bytes = 0

    turn_2_rx_user = ""
    turn_2_rx_ai = ""
    turn_2_audio_bytes = 0

    current_turn = 1

    def on_connected():
        print("[LIVE] Connected successfully.")

    def on_input_transcript(text):
        nonlocal turn_1_rx_user, turn_2_rx_user
        print(f"[LIVE RX USER]: '{text}'")
        if current_turn == 1:
            turn_1_rx_user += text
        else:
            turn_2_rx_user += text

    def on_output_transcript(text):
        nonlocal turn_1_rx_ai, turn_2_rx_ai
        print(f"[LIVE RX AI]: '{text}'")
        if current_turn == 1:
            turn_1_rx_ai += text
        else:
            turn_2_rx_ai += text

    def on_audio(audio_bytes):
        nonlocal turn_1_audio_bytes, turn_2_audio_bytes
        if current_turn == 1:
            turn_1_audio_bytes += len(audio_bytes)
        else:
            turn_2_audio_bytes += len(audio_bytes)

    def on_turn_complete(user_text, assistant_text):
        nonlocal turn_1_done, turn_2_done
        print(f"[LIVE TURN COMPLETE] Turn {current_turn} complete.")
        if current_turn == 1:
            turn_1_done.set()
        else:
            turn_2_done.set()

    def on_error(err):
        print(f"[LIVE ERROR]: {err}")

    session = GeminiLiveSession(
        api_key=api_key,
        model=model,
        system_instruction="You are DHEEPTHI. Reply concisely.",
        on_connected=on_connected,
        on_audio=on_audio,
        on_input_transcript=on_input_transcript,
        on_output_transcript=on_output_transcript,
        on_turn_complete=on_turn_complete,
        on_error=on_error,
    )

    if not session.start(timeout=15.0):
        print("[FAIL] Session failed to start.")
        return

    session_id_start = session.session_id
    print(f"Session ID at startup: {session_id_start}")

    # Continuous Virtual Microphone Feeder
    mic_audio_queue = asyncio.Queue()
    mic_running = True

    async def virtual_mic_loop():
        ambient_chunk = (np.random.randint(-5, 5, size=512, dtype=np.int16)).tobytes()
        chunk_duration = 0.032
        next_time = time.monotonic()
        while mic_running:
            try:
                chunk = mic_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                chunk = ambient_chunk

            session.send_audio(chunk)
            next_time += chunk_duration
            sleep_sec = next_time - time.monotonic()
            if sleep_sec > 0:
                await asyncio.sleep(sleep_sec)
            else:
                next_time = time.monotonic()
                await asyncio.sleep(0.001)

    mic_task = asyncio.create_task(virtual_mic_loop())

    # Generate test audio for Turn 1
    pcm_turn_1 = await generate_speech_pcm("Hello DHEEPTHI, how are you doing today?")
    print(f"\n[TURN 1] Streaming {len(pcm_turn_1)} bytes of PCM speech...")

    chunk_size = 1024
    for offset in range(0, len(pcm_turn_1), chunk_size):
        mic_audio_queue.put_nowait(pcm_turn_1[offset : offset + chunk_size])

    try:
        await asyncio.wait_for(turn_1_done.wait(), timeout=15.0)
        print(f"[TURN 1 SUCCESS] User: '{turn_1_rx_user}' | AI: '{turn_1_rx_ai}' | Audio bytes: {turn_1_audio_bytes}")
    except asyncio.TimeoutError:
        print("[TURN 1 FAIL] Timeout waiting for turn 1 completion.")

    # Pause 2.0s between turns (mic continues streaming ambient background)
    print("\n[PAUSE] Pausing 2.0s between Turn 1 and Turn 2...")
    await asyncio.sleep(2.0)

    # Execute Turn 2 on the SAME session!
    current_turn = 2
    session_id_turn2 = session.session_id
    print(f"[TURN 2] Testing second turn on SAME session_id: {session_id_turn2}")

    pcm_turn_2 = await generate_speech_pcm("Tell me a short interesting fact about outer space.")
    print(f"[TURN 2] Streaming {len(pcm_turn_2)} bytes of PCM speech...")

    for offset in range(0, len(pcm_turn_2), chunk_size):
        mic_audio_queue.put_nowait(pcm_turn_2[offset : offset + chunk_size])

    try:
        await asyncio.wait_for(turn_2_done.wait(), timeout=15.0)
        print(f"[TURN 2 SUCCESS] User: '{turn_2_rx_user}' | AI: '{turn_2_rx_ai}' | Audio bytes: {turn_2_audio_bytes}")
    except asyncio.TimeoutError:
        print("[TURN 2 FAIL] Timeout waiting for turn 2 completion.")

    mic_running = False
    await mic_task
    session.stop()

    same_session_preserved = (session_id_start == session_id_turn2)
    multi_turn_passed = turn_1_done.is_set() and turn_2_done.is_set() and same_session_preserved

    print("\n" + "=" * 70)
    print("AUTOMATED VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"1. Intent Routing Test        : {'PASS' if routing_passed else 'FAIL'}")
    print(f"2. Live Session Startup       : PASS (session_id={session_id_start})")
    print(f"3. Turn 1 PCM Conversation    : {'PASS' if turn_1_done.is_set() else 'FAIL'}")
    print(f"4. Turn 2 PCM Conversation    : {'PASS' if turn_2_done.is_set() else 'FAIL'}")
    print(f"5. Same Session Preserved     : {'PASS' if same_session_preserved else 'FAIL'} ({session_id_start})")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_automated_tests())
