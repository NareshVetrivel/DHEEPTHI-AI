"""
Standalone test script to test TWO consecutive PCM audio turns on ONE persistent Gemini Live session.
"""

import asyncio
import io
import os
import sys
import time
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from config import settings
from ai.gemini_client import GeminiLiveSession
import numpy as np
import soundfile as sf
import edge_tts


async def generate_pcm(text: str) -> bytes:
    """Generate 16kHz mono 16-bit PCM speech audio."""
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


async def main():
    print("=" * 70)
    print("TEST: TWO CONSECUTIVE PCM SPEECH TURNS ON SAME GEMINI LIVE SESSION")
    print("=" * 70)

    api_key = os.getenv("GEMINI_API_KEY_1") or os.getenv("GEMINI_API_KEY")
    model = getattr(settings, "GEMINI_LIVE_MODEL", None) or os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")

    print(f"Model: {model}")
    print("Generating speech audio for Turn 1 and Turn 2...")
    pcm_1 = await generate_pcm("Hello, can you hear me clearly?")
    pcm_2 = await generate_pcm("What is the capital of France?")
    print(f"Turn 1 PCM: {len(pcm_1)} bytes ({len(pcm_1)/32000:.2f}s)")
    print(f"Turn 2 PCM: {len(pcm_2)} bytes ({len(pcm_2)/32000:.2f}s)")

    turn_1_complete = asyncio.Event()
    turn_2_complete = asyncio.Event()

    t1_user_text = []
    t1_ai_text = []
    t1_audio_bytes = 0

    t2_user_text = []
    t2_ai_text = []
    t2_audio_bytes = 0

    current_turn = 1

    def on_connected():
        print(f"[TEST CALLBACK] Connected to Gemini Live API.")

    def on_input_transcript(text):
        nonlocal current_turn
        print(f"[TEST CALLBACK] [INPUT TRANSCRIPT (Turn {current_turn})]: '{text}'")
        if current_turn == 1:
            t1_user_text.append(text)
        else:
            t2_user_text.append(text)

    def on_output_transcript(text):
        nonlocal current_turn
        print(f"[TEST CALLBACK] [OUTPUT TRANSCRIPT (Turn {current_turn})]: '{text}'")
        if current_turn == 1:
            t1_ai_text.append(text)
        else:
            t2_ai_text.append(text)

    def on_audio(audio_bytes):
        nonlocal t1_audio_bytes, t2_audio_bytes, current_turn
        if current_turn == 1:
            t1_audio_bytes += len(audio_bytes)
        else:
            t2_audio_bytes += len(audio_bytes)

    def on_turn_complete(user_text, assistant_text):
        nonlocal current_turn
        print(f"[TEST CALLBACK] [TURN COMPLETE] Turn {current_turn} complete. user='{user_text}' ai='{assistant_text}'")
        if current_turn == 1:
            turn_1_complete.set()
        else:
            turn_2_complete.set()

    def on_error(err):
        print(f"[TEST CALLBACK] [ERROR]: {type(err).__name__}: {err}")

    def on_closed():
        print(f"[TEST CALLBACK] [CLOSED] Session closed.")

    session = GeminiLiveSession(
        api_key=api_key,
        model=model,
        system_instruction="You are a helpful assistant. Reply concisely in one sentence.",
        on_connected=on_connected,
        on_audio=on_audio,
        on_input_transcript=on_input_transcript,
        on_output_transcript=on_output_transcript,
        on_turn_complete=on_turn_complete,
        on_error=on_error,
        on_closed=on_closed,
    )

    print("Starting GeminiLiveSession...")
    if not session.start(timeout=15.0):
        print("[FAIL] Could not start session.")
        return

    session_id_1 = session.session_id
    print(f"Session established. session_id = {session_id_1}")

    # Continuous Virtual Microphone Feeder
    mic_audio_queue = asyncio.Queue()
    mic_running = True
    mic_fed_packets = 0

    async def virtual_mic_loop():
        nonlocal mic_fed_packets
        ambient_chunk = (np.random.randint(-5, 5, size=512, dtype=np.int16)).tobytes()
        chunk_duration = 0.032
        next_time = time.monotonic()
        while mic_running:
            try:
                chunk = mic_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                chunk = ambient_chunk

            session.send_audio(chunk)
            mic_fed_packets += 1
            if mic_fed_packets % 100 == 0:
                print(f"[TEST MIC] Fed {mic_fed_packets} packets to session (tx_cnt={session.send_packet_count}, rx_cnt={session.receive_event_count})")
            next_time += chunk_duration
            sleep_sec = next_time - time.monotonic()
            if sleep_sec > 0:
                await asyncio.sleep(sleep_sec)
            else:
                next_time = time.monotonic()
                await asyncio.sleep(0.001)

    mic_task = asyncio.create_task(virtual_mic_loop())

    # ----------------------------------------------------
    # TURN 1: 'Hello, can you hear me clearly?'
    # ----------------------------------------------------
    print("\n" + "=" * 50)
    print("EXECUTING TURN 1: 'Hello, can you hear me clearly?'")
    print("=" * 50)

    chunk_size = 1024
    for offset in range(0, len(pcm_1), chunk_size):
        mic_audio_queue.put_nowait(pcm_1[offset : offset + chunk_size])

    print("[TURN 1] Speech injected into continuous mic stream. Waiting for Gemini response...")
    try:
        await asyncio.wait_for(turn_1_complete.wait(), timeout=15.0)
        print(f"[TURN 1 PASS] User: '{''.join(t1_user_text)}' | AI: '{''.join(t1_ai_text)}' | Audio bytes: {t1_audio_bytes}")
    except asyncio.TimeoutError:
        print("[TURN 1 FAIL] Timeout waiting for turn 1 completion.")

    # ----------------------------------------------------
    # PAUSE BETWEEN TURNS (continuous mic continues streaming ambient frames)
    # ----------------------------------------------------
    print("\n[PAUSE] Waiting 2 seconds between turns...")
    await asyncio.sleep(2.0)

    # ----------------------------------------------------
    # TURN 2: 'What is the capital of France?'
    # ----------------------------------------------------
    current_turn = 2
    session_id_2 = session.session_id
    print("\n" + "=" * 50)
    print(f"EXECUTING TURN 2: 'What is the capital of France?' on SAME session ({session_id_2})")
    print("=" * 50)

    for offset in range(0, len(pcm_2), chunk_size):
        mic_audio_queue.put_nowait(pcm_2[offset : offset + chunk_size])

    print("[TURN 2] Speech injected into continuous mic stream. Waiting for Gemini response...")
    try:
        await asyncio.wait_for(turn_2_complete.wait(), timeout=15.0)
        print(f"[TURN 2 PASS] User: '{''.join(t2_user_text)}' | AI: '{''.join(t2_ai_text)}' | Audio bytes: {t2_audio_bytes}")
    except asyncio.TimeoutError:
        print("[TURN 2 FAIL] Timeout waiting for turn 2 completion.")

    mic_running = False
    await mic_task

    session.stop()

    print("\n" + "=" * 70)
    print("MULTI-TURN RESULTS SUMMARY")
    print("=" * 70)
    print(f"Turn 1 Status : {'PASS' if turn_1_complete.is_set() else 'FAIL'}")
    print(f"Turn 2 Status : {'PASS' if turn_2_complete.is_set() else 'FAIL'}")
    print(f"Same Session  : {'PASS' if session_id_1 == session_id_2 else 'FAIL'} ({session_id_1})")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
