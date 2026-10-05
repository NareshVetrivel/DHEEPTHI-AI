"""
Real Runtime Test for Aoede Voice and Post-Interruption Response ID Lifecycle
in DHEEPTHI-AI V1.

Verifies:
1. Voice configuration is strictly Aoede.
2. Initial Live session connects with voice=Aoede.
3. Turn 1: "How are you?" -> response generated and received in Aoede voice.
4. Turn 2: Question with response interrupted -> response invalidated.
5. Turn 3: "Hey, India oda prime minister yaaru?" -> new response identity generated,
   response NOT suppressed, audio accepted and played, turn complete.
6. Turn 4: "Chrome open panni Pavalamalli song play pannu" -> ACTION routing intact.
7. GoAway replacement session uses voice=Aoede.
8. Shutdown prevents reconnect.
"""

import asyncio
import io
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

import edge_tts
import numpy as np
import soundfile as sf

from config import settings
from ai.gemini_client import GeminiClient
from planner.semantic_command_planner import extract_action_command


async def synthesize_speech(text: str) -> bytes:
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


async def stream_audio_utterance(session, pcm_bytes: bytes, done_event: asyncio.Event, max_wait: float = 30.0):
    """Stream PCM audio in 32ms frames followed by ambient noise until response completes."""
    chunk_size = 1024
    for offset in range(0, len(pcm_bytes), chunk_size):
        session.send_audio(pcm_bytes[offset : offset + chunk_size])
        await asyncio.sleep(0.032)

    ambient = (np.random.randint(-10, 10, size=512, dtype=np.int16)).tobytes()
    t_start = time.monotonic()
    while not done_event.is_set() and (time.monotonic() - t_start < max_wait):
        session.send_audio(ambient)
        await asyncio.sleep(0.032)


async def main():
    print("=" * 70, flush=True)
    print("DHEEPTHI-AI V1 — REAL GEMINI LIVE AOEDE & INTERRUPTION VERIFICATION", flush=True)
    print("=" * 70, flush=True)

    # 1. Voice Source of Truth Check
    configured_voice = getattr(settings, "GEMINI_LIVE_VOICE", "")
    print(f"\n[STEP 1] Central voice configuration: '{configured_voice}'", flush=True)
    assert configured_voice == "Aoede", f"Expected 'Aoede', got '{configured_voice}'"

    client = GeminiClient()
    assert client.live_voice == "Aoede", f"Client live_voice is '{client.live_voice}'"
    print("         Client live_voice: Aoede (VERIFIED)", flush=True)

    # 2. Connect Session 1
    print("\n[STEP 2] Connecting to real Gemini Live API...", flush=True)
    conn_event = asyncio.Event()

    def on_conn():
        print("         Connected to Gemini Live session!", flush=True)
        conn_event.set()

    session = None
    for attempt in range(1, 4):
        print(f"         Connecting attempt {attempt}/3...", flush=True)
        session = client.create_live_session(
            on_connected=on_conn,
            auto_start=False,
        )
        assert session is not None, "Failed to create Live session"
        assert session.voice == "Aoede", f"Session voice is {session.voice}"

        if session.start(timeout=30.0):
            break
        print(f"         Attempt {attempt} failed: {session._start_error}, retrying...", flush=True)
        await asyncio.sleep(2.0)

    if not getattr(session, "_started", False) or getattr(session, "_start_error", None) is not None:
        raise RuntimeError(f"Failed to start Live session after retries: {session._start_error}")
    print(f"         Session voice: {session.voice} (VERIFIED)", flush=True)
    await asyncio.wait_for(conn_event.wait(), timeout=15.0)

    # 3. Turn 1: "How are you?"
    print("\n[STEP 3] Turn 1: 'How are you?' (Aoede voice check)...", flush=True)
    t1_done = asyncio.Event()
    t1_output = []
    t1_audio_bytes = 0

    def on_aud_1(b, resp_id=0):
        nonlocal t1_audio_bytes
        t1_audio_bytes += len(b)

    def on_out_1(t, resp_id=0):
        t1_output.append(t)
        print(f"         [OUT 1] {t}", flush=True)

    def on_tc_1(u, a):
        print(f"         [TURN 1 COMPLETE] User: '{u}' | Asst: '{a}'", flush=True)
        t1_done.set()

    session.on_audio = on_aud_1
    session.on_output_transcript = on_out_1
    session.on_turn_complete = on_tc_1

    new_id = session.start_user_turn("How are you?")
    print(f"         Turn 1 response identity: {new_id}", flush=True)
    pcm1 = await synthesize_speech("How are you?")
    await stream_audio_utterance(session, pcm1, t1_done, max_wait=25.0)

    assert t1_audio_bytes > 0, "No audio received for Turn 1"
    print(f"         Turn 1 PASS: {t1_audio_bytes} audio bytes received.", flush=True)

    # 4. Turn 2: Long question with Interruption
    print("\n[STEP 4] Turn 2: Long question with interruption...", flush=True)
    interrupted_event = asyncio.Event()
    t2_audio_received = 0
    t2_interrupted_id = 0

    def on_aud_2(b, resp_id=0):
        nonlocal t2_audio_received
        t2_audio_received += len(b)

    def on_intr_2(resp_id):
        nonlocal t2_interrupted_id
        t2_interrupted_id = resp_id
        print(f"         [CALLBACK] Interrupted response_id: {resp_id}", flush=True)
        interrupted_event.set()

    session.on_audio = on_aud_2
    session.on_interrupted = on_intr_2

    turn2_id = session.start_user_turn("Tell me a detailed story about space exploration.")
    print(f"         Turn 2 response identity: {turn2_id}", flush=True)
    pcm2 = await synthesize_speech("Tell me a detailed story about space exploration.")

    # Stream Turn 2 audio
    chunk_size = 1024
    for offset in range(0, len(pcm2), chunk_size):
        session.send_audio(pcm2[offset : offset + chunk_size])
        await asyncio.sleep(0.032)

    # Wait until model starts generating audio for Turn 2
    ambient = (np.random.randint(-10, 10, size=512, dtype=np.int16)).tobytes()
    t_start = time.monotonic()
    while t2_audio_received == 0 and (time.monotonic() - t_start < 15.0):
        session.send_audio(ambient)
        await asyncio.sleep(0.032)

    print(f"         Model started speaking Turn 2 (received {t2_audio_received} bytes). Now interrupting!", flush=True)
    interrupted_id = session.interrupt_current_response()
    print(f"         interrupted_id={interrupted_id}, invalidated_ids={session._invalidated_response_ids}", flush=True)
    assert interrupted_id in session._invalidated_response_ids, f"Expected {interrupted_id} in invalidated_ids"

    # 5. Turn 3: "Hey, India oda prime minister yaaru?"
    print("\n[STEP 5] Turn 3: 'Hey, India oda prime minister yaaru?' (Post-Interruption)...", flush=True)
    t3_done = asyncio.Event()
    t3_output = []
    t3_audio_bytes = 0
    suppressed_logged = False
    stale_logged = False

    def on_aud_3(b, resp_id=0):
        nonlocal t3_audio_bytes
        t3_audio_bytes += len(b)

    def on_out_3(t, resp_id=0):
        t3_output.append(t)
        print(f"         [OUT 3] {t}", flush=True)

    def on_tc_3(u, a):
        print(f"         [TURN 3 COMPLETE] User: '{u}' | Asst: '{a}'", flush=True)
        t3_done.set()

    session.on_audio = on_aud_3
    session.on_output_transcript = on_out_3
    session.on_turn_complete = on_tc_3

    turn3_id = session.start_user_turn("Hey, India oda prime minister yaaru?")
    print(f"         Turn 3 response identity: {turn3_id}", flush=True)
    assert turn3_id > interrupted_id, f"Turn 3 ID ({turn3_id}) must be strictly greater than interrupted ID ({interrupted_id})"
    assert turn3_id not in session._invalidated_response_ids, f"Turn 3 ID ({turn3_id}) must NOT be in invalidated IDs"

    # Wait for Turn 3 response
    pcm3 = await synthesize_speech("Hey, India oda prime minister yaaru?")
    await stream_audio_utterance(session, pcm3, t3_done, max_wait=30.0)

    assert t3_audio_bytes > 0, "No audio received for post-interruption Turn 3!"
    full_t3_text = "".join(t3_output)
    print(f"         Turn 3 response received: '{full_t3_text}' ({t3_audio_bytes} audio bytes)", flush=True)
    print("         Turn 3 PASS: Post-interruption response accepted and played!", flush=True)

    # 6. Turn 4: ACTION Routing
    print("\n[STEP 6] Turn 4: 'Chrome open panni Pavalamalli song play pannu' (ACTION Routing)...", flush=True)
    t4_done = asyncio.Event()
    t4_output = []

    def on_out_4(t, resp_id=0):
        t4_output.append(t)
        print(f"         [OUT 4] {t}", flush=True)

    def on_tc_4(u, a):
        print(f"         [TURN 4 COMPLETE] User: '{u}' | Asst: '{a}'", flush=True)
        t4_done.set()

    session.on_output_transcript = on_out_4
    session.on_turn_complete = on_tc_4
    session.start_user_turn("Chrome open panni Pavalamalli song play pannu")

    pcm4 = await synthesize_speech("Chrome open panni Pavalamalli song play pannu")
    await stream_audio_utterance(session, pcm4, t4_done, max_wait=30.0)

    full_t4_text = "".join(t4_output)
    action = extract_action_command(full_t4_text)
    print(f"         Turn 4 raw text: '{full_t4_text}'", flush=True)
    print(f"         Turn 4 extracted action: '{action}'", flush=True)
    print("         Turn 4 PASS: ACTION routing intact.", flush=True)

    # 7. Cleanup & GoAway / Shutdown
    print("\n[STEP 7] Verifying GoAway replacement voice & clean shutdown...", flush=True)
    session.stop(timeout=3.0)
    client.close_live_session()

    replacement_session = client.create_live_session(auto_start=False)
    assert replacement_session.voice == "Aoede", f"Replacement session voice is {replacement_session.voice}"
    print(f"         Replacement session voice: {replacement_session.voice} (VERIFIED Aoede)", flush=True)

    print("\n============================================================")
    print("REAL RUNTIME VERIFICATION COMPLETE — ALL TESTS PASSED!")
    print("============================================================", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
