"""
Standalone diagnostic script for testing Gemini Live API transport.

Isolates Gemini Live from PyQt, PortAudio, MainWindow, microphone monitor, and audio workers.
Runs two tests:
TEST A: Gemini Live + text input
TEST B: Gemini Live + known-good 16k PCM speech input
"""

import asyncio
import io
import os
import sys
import time
import wave
import traceback

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import config settings same as ai/gemini_client.py
from config import settings

import google.genai as genai
from google.genai import types

import numpy as np
import soundfile as sf
import edge_tts


def get_gemini_api_key() -> str:
    """Retrieve the same Gemini API key used by ai/gemini_client.py."""
    for idx in range(1, 5):
        key = getattr(settings, f"GEMINI_API_KEY_{idx}", None)
        if not key:
            key = os.getenv(f"GEMINI_API_KEY_{idx}", "")
        if key and str(key).strip():
            return str(key).strip()
    # Fallback to general GEMINI_API_KEY
    key = os.getenv("GEMINI_API_KEY", "")
    if key and str(key).strip():
        return str(key).strip()
    raise RuntimeError("No Gemini API key found in settings or environment.")


def get_live_model() -> str:
    """Retrieve the same Live model used by ai/gemini_client.py."""
    model = (
        getattr(settings, "GEMINI_LIVE_MODEL", None)
        or os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
    )
    return str(model).strip()


async def generate_known_good_pcm(duration_sec: float = 3.5) -> bytes:
    """
    Generate a known-good 16000 Hz, mono, 16-bit signed PCM speech file.
    Verifies sample rate, channels, and sample width.
    """
    text = "Hello Gemini, this is a test audio message. Please tell me if you can hear me clearly."
    print(f"\n[AUDIO GEN] Generating speech audio via Edge-TTS: '{text}'...")
    tts = edge_tts.Communicate(text=text, voice="en-US-GuyNeural")
    mp3_data = b""
    async for chunk in tts.stream():
        if chunk["type"] == "audio":
            mp3_data += chunk["data"]

    # Read MP3 with soundfile
    data, samplerate = sf.read(io.BytesIO(mp3_data))
    if len(data.shape) > 1:
        data = data.mean(axis=1)

    # Resample to 16000 Hz if necessary
    if samplerate != 16000:
        import scipy.signal
        num_samples = int(len(data) * 16000 / samplerate)
        data = scipy.signal.resample(data, num_samples)

    # Convert to 16-bit signed integer PCM
    pcm16 = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    raw_pcm = pcm16.tobytes()

    # Wrap in in-memory WAV to verify specs with standard wave module
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(raw_pcm)

    wav_io.seek(0)
    with wave.open(wav_io, "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        extracted_pcm = wf.readframes(nframes)

    duration = nframes / framerate
    print(f"[AUDIO GEN] WAV verified specs:")
    print(f"  - Channels: {channels} (expected: 1)")
    print(f"  - Sample width: {sampwidth} bytes (expected: 2)")
    print(f"  - Sample rate: {framerate} Hz (expected: 16000)")
    print(f"  - Duration: {duration:.2f} s")
    print(f"  - Total PCM bytes: {len(extracted_pcm)} bytes")

    assert channels == 1, "Channels must be 1 (mono)"
    assert sampwidth == 2, "Sample width must be 2 bytes (16-bit)"
    assert framerate == 16000, "Sample rate must be 16000 Hz"

    return extracted_pcm


# ==========================================================
# TEST A: TEXT INPUT
# ==========================================================
async def run_test_a_text(api_key: str, model: str):
    print("\n" + "=" * 60)
    print("RUNNING TEST A: Gemini Live + Text Input")
    print("=" * 60)
    print(f"[TEST A] Model: {model}")
    print(f"[TEST A] Connecting to Gemini Live API...")

    client = genai.Client(api_key=api_key)

    config = {
        "response_modalities": ["AUDIO"],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "system_instruction": "You are a helpful assistant. Reply concisely.",
        "realtime_input_config": {
            "automatic_activity_detection": {
                "disabled": False,
            },
        },
    }

    test_passed = False
    error_occurred = None
    output_transcripts = []
    audio_bytes_received = 0

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            print("[TEST A] Connection SUCCESS!")

            async def receive_loop():
                nonlocal audio_bytes_received, test_passed
                try:
                    async for response in session.receive():
                        server_content = getattr(response, "server_content", None)
                        if server_content is None:
                            continue

                        # Text transcript from output audio
                        out_transcript = getattr(server_content, "output_audio_transcription", None) or getattr(
                            server_content, "output_transcription", None
                        )
                        if out_transcript:
                            text = getattr(out_transcript, "text", "")
                            if text:
                                output_transcripts.append(text)
                                print(f"[TEST A OUTPUT TRANSCRIPT]: {text}")

                        # Model turn parts (audio)
                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn:
                            for part in getattr(model_turn, "parts", []):
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    audio_chunk = bytes(inline_data.data)
                                    audio_bytes_received += len(audio_chunk)
                                text_data = getattr(part, "text", None)
                                if text_data:
                                    print(f"[TEST A PART TEXT]: {text_data}")

                        # Turn complete
                        turn_complete = getattr(server_content, "turn_complete", False)
                        if turn_complete:
                            print(f"[TEST A] turn_complete: True")
                            print(f"[TEST A] Total model audio bytes received: {audio_bytes_received}")
                            test_passed = True
                            return

                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"[TEST A RECEIVE ERROR]: {type(e).__name__}: {e}")
                    raise

            receive_task = asyncio.create_task(receive_loop())

            # Send text
            text_prompt = "Hello, please reply briefly."
            print(f"[TEST A] Sending realtime text: '{text_prompt}'")
            await session.send_realtime_input(text=text_prompt)

            # Wait for response with timeout
            try:
                await asyncio.wait_for(receive_task, timeout=15.0)
            except asyncio.TimeoutError:
                print("[TEST A] TIMEOUT waiting for turn_complete.")
            finally:
                if not receive_task.done():
                    receive_task.cancel()

    except Exception as exc:
        error_occurred = exc
        print(f"[TEST A EXCEPTION]: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    print("\n--- TEST A SUMMARY ---")
    print(f"Connection Success: True (session context entered)")
    print(f"Model Used: {model}")
    print(f"Output Transcript Received: {' '.join(output_transcripts) if output_transcripts else 'NONE'}")
    print(f"Model Audio Bytes Received: {audio_bytes_received}")
    print(f"Turn Complete: {test_passed}")
    print(f"Exception: {error_occurred}")
    print("=" * 60)
    return test_passed, error_occurred


# ==========================================================
# TEST B: KNOWN-GOOD 16K PCM INPUT
# ==========================================================
async def run_test_b_pcm(api_key: str, model: str, pcm_bytes: bytes):
    print("\n" + "=" * 60)
    print("RUNNING TEST B: Gemini Live + Known-Good 16k PCM Input")
    print("=" * 60)
    print(f"[TEST B] Model: {model}")
    print(f"[TEST B] PCM byte count: {len(pcm_bytes)} bytes")
    print(f"[TEST B] Connecting to Gemini Live API...")

    client = genai.Client(api_key=api_key)

    config = {
        "response_modalities": ["AUDIO"],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "system_instruction": "You are a helpful assistant. Reply concisely.",
        "realtime_input_config": {
            "automatic_activity_detection": {
                "disabled": False,
            },
        },
    }

    test_passed = False
    error_occurred = None
    input_transcripts = []
    output_transcripts = []
    audio_bytes_received = 0

    chunk_size = 1024  # 512 samples = 1024 bytes (32 ms @ 16kHz)
    print(f"[TEST B] Chunk size: {chunk_size} bytes ({chunk_size // 2} samples, {chunk_size / 32000 * 1000:.1f} ms)")

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            print("[TEST B] Connection SUCCESS!")

            async def receive_loop():
                nonlocal audio_bytes_received, test_passed
                try:
                    async for response in session.receive():
                        # Debug raw response
                        server_content = getattr(response, "server_content", None)
                        if server_content is None:
                            print(f"[TEST B RAW RESPONSE (no server_content)]: {response}")
                            continue

                        # Input transcription (user's audio transcribed by Google)
                        in_transcript = getattr(server_content, "input_transcription", None) or getattr(
                            server_content, "interim_input_transcription", None
                        )
                        if in_transcript:
                            text = getattr(in_transcript, "text", "")
                            if text:
                                input_transcripts.append(text)
                                print(f"[TEST B INPUT TRANSCRIPT]: {text}")

                        # Output transcription (model's response text)
                        out_transcript = getattr(server_content, "output_audio_transcription", None) or getattr(
                            server_content, "output_transcription", None
                        )
                        if out_transcript:
                            text = getattr(out_transcript, "text", "")
                            if text:
                                output_transcripts.append(text)
                                print(f"[TEST B OUTPUT TRANSCRIPT]: {text}")

                        # Model turn parts (audio)
                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn:
                            for part in getattr(model_turn, "parts", []):
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    audio_chunk = bytes(inline_data.data)
                                    audio_bytes_received += len(audio_chunk)

                        # Turn complete
                        turn_complete = getattr(server_content, "turn_complete", False)
                        if turn_complete:
                            print(f"[TEST B] turn_complete: True")
                            print(f"[TEST B] Total model audio bytes received: {audio_bytes_received}")
                            test_passed = True
                            return

                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"[TEST B RECEIVE ERROR]: {type(e).__name__}: {e}")
                    raise

            receive_task = asyncio.create_task(receive_loop())

            # Stream PCM chunks with real-time pacing
            print(f"[TEST B] Streaming {len(pcm_bytes)} PCM bytes to session...")
            total_sent = 0
            chunk_duration = (chunk_size / 2) / 16000.0  # seconds

            start_time = time.monotonic()
            chunk_count = 0
            for offset in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[offset : offset + chunk_size]
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=chunk,
                        mime_type="audio/pcm",
                    )
                )
                total_sent += len(chunk)
                chunk_count += 1
                target_time = start_time + (chunk_count * chunk_duration)
                sleep_sec = target_time - time.monotonic()
                if sleep_sec > 0:
                    await asyncio.sleep(sleep_sec)

            print(f"[TEST B] Finished sending speech ({total_sent} bytes). Sending audio_stream_end=True...")
            try:
                await session.send_realtime_input(audio_stream_end=True)
            except Exception as e:
                print(f"[TEST B] audio_stream_end signal note: {e}")

            print(f"[TEST B] Waiting for response...")

            # Wait for receive loop to finish turn
            try:
                await asyncio.wait_for(receive_task, timeout=15.0)
            except asyncio.TimeoutError:
                print("[TEST B] TIMEOUT waiting for turn_complete after sending PCM.")
            finally:
                if not receive_task.done():
                    receive_task.cancel()

    except Exception as exc:
        error_occurred = exc
        print(f"[TEST B EXCEPTION]: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    print("\n--- TEST B SUMMARY ---")
    print(f"Connection Success: True (session context entered)")
    print(f"Model Used: {model}")
    print(f"PCM Bytes Sent: {len(pcm_bytes)}")
    print(f"Input Transcript Received: {' '.join(input_transcripts) if input_transcripts else 'NONE'}")
    print(f"Output Transcript Received: {' '.join(output_transcripts) if output_transcripts else 'NONE'}")
    print(f"Model Audio Bytes Received: {audio_bytes_received}")
    print(f"Turn Complete: {test_passed}")
    print(f"Exception: {error_occurred}")
    print("=" * 60)
    return test_passed, error_occurred


async def main():
    api_key = get_gemini_api_key()
    model = get_live_model()

    print("==================================================")
    print("GEMINI LIVE DIAGNOSTIC TOOL")
    print("==================================================")
    print(f"google-genai SDK Version : {getattr(genai, '__version__', 'unknown')}")
    print(f"Model Configured         : {model}")
    print(f"API Key (masked)         : {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''}")

    # Test A: Text input
    test_a_ok, test_a_err = await run_test_a_text(api_key, model)

    # Generate speech PCM
    pcm_bytes = await generate_known_good_pcm()

    # Test B: PCM audio input
    test_b_ok, test_b_err = await run_test_b_pcm(api_key, model, pcm_bytes)

    print("\n==================================================")
    print("FINAL RESULTS")
    print("==================================================")
    print(f"A. Text-only Live works       : {test_a_ok}")
    print(f"B. Known-good PCM Live works  : {test_b_ok}")
    print(f"C. Exact Model Used           : {model}")
    print(f"D. Exact SDK Version          : {getattr(genai, '__version__', 'unknown')}")
    print(f"E. Test A Error               : {test_a_err}")
    print(f"   Test B Error               : {test_b_err}")
    has_1011 = ("1011" in str(test_a_err) if test_a_err else False) or (
        "1011" in str(test_b_err) if test_b_err else False
    )
    print(f"F. 1011 Error Occurred        : {has_1011}")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
