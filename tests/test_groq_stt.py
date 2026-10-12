"""
ASTRA-AI — Groq STT microphone test.

Isolated test only. It does not modify whisper_recognizer.py.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import speech_recognition as sr
from dotenv import load_dotenv
from groq import Groq

MODEL = "whisper-large-v3-turbo"


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] GROQ_API_KEY is missing from .env")
        return 1

    print("=" * 60)
    print("ASTRA-AI Groq Speech-to-Text Test")
    print("=" * 60)
    print(f"Model : {MODEL}")
    print()
    print("This test sends one short microphone recording to Groq.")

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.75
    recognizer.phrase_threshold = 0.30
    recognizer.non_speaking_duration = 0.40

    temp_path: Path | None = None

    try:
        with sr.Microphone() as source:
            print("Calibrating microphone...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("Calibration complete.")
            print()
            print("Speak now.")
            print("Example: DHEEPTHI create a Word document")

            audio = recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=8,
            )

        with tempfile.NamedTemporaryFile(
            prefix="astra_groq_test_",
            suffix=".wav",
            delete=False,
        ) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(audio.get_wav_data())

        print(f"Audio captured: {temp_path.stat().st_size} bytes")
        print("Sending audio to Groq...")

        client = Groq(api_key=api_key)

        with temp_path.open("rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(temp_path.name, audio_file.read()),
                model=MODEL,
                language="en",
                prompt=(
                    "ASTRA-AI voice assistant commands. "
                    "The assistant name is DHEEPTHI. "
                    "Common commands include Word, create document, "
                    "open document, save document, read document, "
                    "search, open website, and computer automation."
                ),
                response_format="json",
                temperature=0.0,
            )

        text = (transcription.text or "").strip()

        print()
        print("=" * 60)
        print("RESULT")
        print("=" * 60)
        print(f"Transcript : {text!r}")
        print()
        print("Groq STT request completed successfully.")
        return 0

    except sr.WaitTimeoutError:
        print("[ERROR] No speech started within 5 seconds.")
        return 1
    except sr.UnknownValueError:
        print("[ERROR] Microphone audio could not be captured clearly.")
        return 1
    except sr.RequestError as exc:
        print(f"[ERROR] Microphone backend error: {exc}")
        return 1
    except Exception as exc:
        print(f"[ERROR] Groq STT test failed: {exc}")
        return 1
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
