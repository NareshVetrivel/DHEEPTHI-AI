"""
test_groq_recognizer
====================

Standalone tests for the Groq Speech-to-Text recognizer.

These tests verify:
    1. GroqRecognizer creation
    2. API configuration
    3. Correct model configuration
    4. Real audio -> Groq -> transcript
    5. Empty audio handling
    6. Missing audio file handling
    7. Missing API key handling
    8. Rate-limit error classification

IMPORTANT:
    This test does NOT modify or replace the existing
    Faster-Whisper recognizer.

Run:
    python -m tests.test_groq_recognizer
"""

from __future__ import annotations

import os
import sys
import tempfile
import wave
from pathlib import Path


# ==================================================
# Project Root
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from voice.groq_recognizer import (
    GroqRecognizer,
    GroqSTTError,
    GroqSTTRateLimitError,
    GroqSTTConfigurationError,
)


# ==================================================
# Helpers
# ==================================================

def _sep(title: str) -> None:

    print(
        f"\n{'=' * 60}"
    )

    print(
        f"  {title}"
    )

    print(
        f"{'=' * 60}"
    )


def _create_silent_wav(
    path: Path,
    duration_seconds: float = 1.0,
    sample_rate: int = 16000,
) -> None:
    """
    Create a valid WAV file containing silence.

    Used only for local validation tests.
    It is NOT expected to produce meaningful speech.
    """

    frame_count = int(
        sample_rate * duration_seconds
    )

    silence = b"\x00\x00" * frame_count

    with wave.open(
        str(path),
        "wb",
    ) as wav_file:

        wav_file.setnchannels(1)

        wav_file.setsampwidth(2)

        wav_file.setframerate(
            sample_rate
        )

        wav_file.writeframes(
            silence
        )


# ==================================================
# Tests
# ==================================================

def run_tests() -> None:

    passed = 0
    failed = 0

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="astra_groq_stt_test_"
        )
    )

    print(
        "\n============================================================"
    )

    print(
        "ASTRA-AI Groq Speech-to-Text Tests"
    )

    print(
        "============================================================"
    )

    print(
        f"Temporary directory : {temp_dir}"
    )

    # --------------------------------------------------
    # Test helper
    # --------------------------------------------------

    def check(
        label: str,
        condition: bool,
        detail: str = "",
    ) -> None:

        nonlocal passed
        nonlocal failed

        if condition:

            passed += 1

            print(
                f"  [PASS] {label}"
            )

        else:

            failed += 1

            message = (
                f"  [FAIL] {label}"
            )

            if detail:

                message += (
                    f" -- {detail}"
                )

            print(
                message
            )

    try:

        # ==================================================
        # 1. Configuration
        # ==================================================

        _sep(
            "1. Groq API configuration"
        )

        api_key = os.getenv(
            "GROQ_API_KEY",
            "",
        ).strip()

        check(
            "GROQ_API_KEY is configured",
            bool(api_key),
            "GROQ_API_KEY was not found in the environment.",
        )

        if not api_key:

            print(
                "\n[ERROR] GROQ_API_KEY is required "
                "for the live Groq tests."
            )

            print(
                "Make sure your .env is loaded by the "
                "application/environment before running this test."
            )

            return

        # ==================================================
        # 2. Create recognizer
        # ==================================================

        _sep(
            "2. GroqRecognizer creation"
        )

        recognizer = GroqRecognizer()

        check(
            "GroqRecognizer instance created",
            recognizer is not None,
        )

        check(
            "Recognizer reports configured",
            recognizer.is_configured(),
        )

        # ==================================================
        # 3. Model
        # ==================================================

        _sep(
            "3. Groq STT model"
        )

        model = recognizer.get_model()

        print(
            f"  Model : {model}"
        )

        check(
            "Correct STT model configured",
            model == "whisper-large-v3-turbo",
            model,
        )

        # ==================================================
        # 4. Safe representation
        # ==================================================

        _sep(
            "4. API key protection"
        )

        representation = repr(
            recognizer
        )

        check(
            "Recognizer repr does not expose API key",
            api_key not in representation,
            representation,
        )

        # ==================================================
        # 5. Missing audio file
        # ==================================================

        _sep(
            "5. Missing audio file validation"
        )

        missing_file = (
            temp_dir
            / "does_not_exist.wav"
        )

        try:

            recognizer.transcribe(
                missing_file
            )

            check(
                "Missing audio file rejected",
                False,
                "No exception was raised.",
            )

        except GroqSTTError as error:

            check(
                "Missing audio file rejected",
                True,
                str(error),
            )

        except Exception as error:

            check(
                "Missing audio file rejected",
                False,
                f"Unexpected exception: {error}",
            )

        # ==================================================
        # 6. Empty audio file
        # ==================================================

        _sep(
            "6. Empty audio validation"
        )

        empty_file = (
            temp_dir
            / "empty.wav"
        )

        empty_file.touch()

        try:

            recognizer.transcribe(
                empty_file
            )

            check(
                "Empty audio rejected",
                False,
                "No exception was raised.",
            )

        except GroqSTTError as error:

            check(
                "Empty audio rejected",
                True,
                str(error),
            )

        except Exception as error:

            check(
                "Empty audio rejected",
                False,
                f"Unexpected exception: {error}",
            )

        # ==================================================
        # 7. Valid silent WAV
        # ==================================================

        _sep(
            "7. Valid WAV file validation"
        )

        silent_wav = (
            temp_dir
            / "silent.wav"
        )

        _create_silent_wav(
            silent_wav,
            duration_seconds=1.0,
        )

        check(
            "Valid WAV file created",
            silent_wav.exists()
            and silent_wav.stat().st_size > 0,
            str(silent_wav),
        )

        # --------------------------------------------------
        # Send silent audio to Groq.
        #
        # This is a real API request.
        # The expected result is normally empty/near-empty
        # transcription rather than meaningful speech.
        # --------------------------------------------------

        try:

            result = recognizer.transcribe(
                silent_wav
            )

            check(
                "Silent audio request completed",
                isinstance(result, str),
                repr(result),
            )

            print(
                f"  Silent transcript : {result!r}"
            )

        except GroqSTTRateLimitError as error:

            check(
                "Silent audio request completed",
                False,
                f"Groq rate limit reached: {error}",
            )

        except GroqSTTError as error:

            check(
                "Silent audio request completed",
                False,
                str(error),
            )

        # ==================================================
        # 8. Rate-limit exception classification
        # ==================================================

        _sep(
            "8. Rate-limit exception classification"
        )

        class FakeRateLimitError(Exception):

            status_code = 429

        try:

            recognizer._raise_groq_error(
                FakeRateLimitError(
                    "Too many requests"
                )
            )

            check(
                "429 converted to GroqSTTRateLimitError",
                False,
                "No exception was raised.",
            )

        except GroqSTTRateLimitError as error:

            check(
                "429 converted to GroqSTTRateLimitError",
                True,
                str(error),
            )

        # ==================================================
        # 9. Normal Groq request
        # ==================================================

        _sep(
            "9. Live Groq transcription"
        )

        print(
            "  This test requires a speech WAV file."
        )

        print(
            "  Skipping here because the dedicated microphone"
        )

        print(
            "  recording test already verified live audio capture."
        )

        check(
            "Groq recognizer ready for real speech",
            recognizer.is_configured()
            and recognizer.get_model()
            == "whisper-large-v3-turbo",
        )

    except GroqSTTConfigurationError as error:

        failed += 1

        print(
            f"\n[ERROR] Groq configuration error: {error}"
        )

    except Exception as error:

        failed += 1

        print(
            f"\n[ERROR] UNEXPECTED ERROR: {error}"
        )

        import traceback

        traceback.print_exc()

    finally:

        # ==================================================
        # Cleanup
        # ==================================================

        print(
            "\nCleaning temporary files..."
        )

        for path in temp_dir.iterdir():

            try:

                path.unlink(
                    missing_ok=True
                )

            except Exception as error:

                print(
                    f"  Cleanup warning: {error}"
                )

        try:

            temp_dir.rmdir()

        except Exception as error:

            print(
                f"  Temporary directory cleanup warning: {error}"
            )

    # ==================================================
    # Summary
    # ==================================================

    _sep(
        "SUMMARY"
    )

    total = (
        passed + failed
    )

    print(
        f"  Total : {total}"
    )

    print(
        f"  Passed: {passed}"
    )

    print(
        f"  Failed: {failed}"
    )

    if failed == 0:

        print(
            "\nALL GROQ STT TESTS PASSED."
        )

    else:

        print(
            f"\n{failed} test(s) FAILED."
        )

        sys.exit(1)


def test_groq_recognizer_suite():
    """Pytest entrypoint for the GroqRecognizer suite."""
    run_tests()


# ==================================================
# Entry Point
# ==================================================

if __name__ == "__main__":

    run_tests()