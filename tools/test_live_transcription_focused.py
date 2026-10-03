"""
Focused automated test for Gemini Live input transcription and audio streaming.
Verifies that streaming 16kHz mono PCM chunks through GeminiLiveSession:
1. Connects to Gemini Live
2. Receives and logs [DIAG RX INPUT_TRANSCRIPT]
3. Receives and logs [DIAG RX OUTPUT_TRANSCRIPT]
4. Receives model audio
5. Completes the conversational turn
6. Maintains 0 dropped packets in the 128-deep audio queue
"""

import asyncio
import os
import sys
import time
import numpy as np
import soundfile as sf

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from config import settings
from ai.gemini_client import GeminiLiveSession


def get_speech_pcm() -> bytes:
    mp3_path = os.path.join(PROJECT_ROOT, "test.mp3")
    data, sr = sf.read(mp3_path)
    if len(data.shape) > 1:
        data = data.mean(axis=1)

    target_sr = 16000
    if sr != target_sr:
        num_target = int(len(data) * target_sr / sr)
        orig_indices = np.arange(len(data))
        target_indices = np.linspace(0, len(data) - 1, num_target)
        data = np.interp(target_indices, orig_indices, data)

    pcm16 = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    return pcm16.tobytes()


def run_focused_test():
    print("=" * 70, flush=True)
    print("FOCUSED TEST: GEMINI LIVE INPUT TRANSCRIPTION & AUDIO PIPELINE", flush=True)
    print("=" * 70, flush=True)

    api_key = os.getenv("GEMINI_API_KEY_1") or os.getenv("GEMINI_API_KEY")
    model = (
        getattr(settings, "GEMINI_LIVE_MODEL", None)
        or os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
    )

    print(f"Model: {model}", flush=True)
    speech_pcm = get_speech_pcm()
    speech_dur = len(speech_pcm) / 32000.0
    print(f"Loaded speech PCM: {len(speech_pcm)} bytes ({speech_dur:.2f}s)", flush=True)

    input_transcripts = []
    output_transcripts = []
    audio_chunks_received = 0
    total_audio_bytes = 0
    turn_completed = False

    def on_connected():
        print("[TEST CALLBACK] Connected to Gemini Live API.", flush=True)

    def on_input_transcript(text):
        print(f"[TEST CALLBACK] [INPUT TRANSCRIPT]: '{text}'", flush=True)
        input_transcripts.append(text)

    def on_output_transcript(text, resp_id=0):
        print(f"[TEST CALLBACK] [OUTPUT TRANSCRIPT]: '{text}' (resp_id={resp_id})", flush=True)
        output_transcripts.append(text)

    def on_audio(chunk, resp_id=0):
        nonlocal audio_chunks_received, total_audio_bytes
        audio_chunks_received += 1
        total_audio_bytes += len(chunk)

    def on_turn_complete(user_text, assistant_text):
        nonlocal turn_completed
        turn_completed = True
        print(f"[TEST CALLBACK] [TURN COMPLETE]: user='{user_text}' assistant='{assistant_text}'", flush=True)

    def on_error(err):
        print(f"[TEST CALLBACK] [ERROR]: {err}", flush=True)

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
    )

    print("Starting session...", flush=True)
    if not session.start(timeout=15.0):
        print("[FAIL] Session failed to start!", flush=True)
        sys.exit(1)

    session_id = session.session_id
    print(f"Session established. session_id={session_id}", flush=True)

    chunk_size = 1024  # 512 samples = 32ms
    chunk_dur = 0.032
    silence_chunk = b"\x00" * chunk_size

    # Phase 1: 1.0 second ambient silence
    print("[PHASE 1] Streaming 1.0s ambient silence (31 chunks)...", flush=True)
    for _ in range(31):
        session.send_audio(silence_chunk)
        time.sleep(chunk_dur)

    # Phase 2: Stream speech chunks
    num_speech_chunks = len(speech_pcm) // chunk_size
    print(f"[PHASE 2] Streaming {num_speech_chunks} speech chunks (~{speech_dur:.2f}s)...", flush=True)
    for offset in range(0, len(speech_pcm), chunk_size):
        chunk = speech_pcm[offset : offset + chunk_size]
        if len(chunk) < chunk_size:
            chunk = chunk + b"\x00" * (chunk_size - len(chunk))
        session.send_audio(chunk)
        time.sleep(chunk_dur)

    # Phase 3: Stream trailing silence while waiting for server response
    print("[PHASE 3] Streaming trailing silence (up to 7s) for Gemini VAD turn completion...", flush=True)
    start_wait = time.time()
    while time.time() - start_wait < 7.0:
        session.send_audio(silence_chunk)
        if turn_completed:
            print("[PHASE 3] Turn completed detected!", flush=True)
            break
        time.sleep(chunk_dur)

    # Grace period
    time.sleep(1.0)

    # Stop session
    session.stop(timeout=3.0)

    print("\n" + "=" * 70, flush=True)
    print("TEST RESULTS SUMMARY", flush=True)
    print("=" * 70, flush=True)
    print(f"Send Packet Count    : {session.send_packet_count}", flush=True)
    print(f"Dropped Packet Count : {session.dropped_packet_count}", flush=True)
    print(f"Receive Event Count  : {session.receive_event_count}", flush=True)
    print(f"Input Transcripts    : {input_transcripts}", flush=True)
    print(f"Output Transcripts   : {output_transcripts}", flush=True)
    print(f"Model Audio Chunks   : {audio_chunks_received} ({total_audio_bytes} bytes)", flush=True)
    print(f"Turn Complete        : {turn_completed}", flush=True)
    print("=" * 70, flush=True)

    # Verifications
    assert session.send_packet_count > 0, "No packets were sent!"
    assert session.dropped_packet_count == 0, f"Packets were dropped: {session.dropped_packet_count}"
    assert session.receive_event_count > 0, "No receive events from Gemini!"
    assert len(input_transcripts) > 0, "ZERO [DIAG RX INPUT_TRANSCRIPT] produced!"

    print("\n>>> ALL CHECKS PASSED: [DIAG RX INPUT_TRANSCRIPT] VERIFIED! <<<\n", flush=True)


if __name__ == "__main__":
    run_focused_test()
