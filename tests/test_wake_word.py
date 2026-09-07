"""
ASTRA-AI
========

Production Wake Word Test
-------------------------

Purpose:
    Test the ACTUAL production WakeWordDetector from
    wake_word.py using the real microphone.

No:
    - STT
    - PyAutoGUI
    - Model comparison

Test:
    - Production model loading
    - Microphone capture
    - TFLite inference
    - Wake-word detection
    - Callback
    - Cooldown / re-arm
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


# ----------------------------------------------------------------------
# PROJECT ROOT
# ----------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ----------------------------------------------------------------------
# IMPORT ACTUAL PRODUCTION DETECTOR
# ----------------------------------------------------------------------

from voice.wake_word import WakeWordDetector


# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------

WAKE_WORD = "dheepthi"

TEST_DURATION_SECONDS = 30.0

# Use the SAME production threshold from wake_word.py.
THRESHOLD = WakeWordDetector.DEFAULT_THRESHOLD


# ----------------------------------------------------------------------
# MODEL PATH
# ----------------------------------------------------------------------

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "wakeword"
    / "dheepthi_float32.tflite"
)


# ----------------------------------------------------------------------
# CALLBACK
# ----------------------------------------------------------------------

detection_count = 0


def on_wake_detected(word: str) -> None:
    global detection_count

    detection_count += 1

    print()
    print("=" * 70)
    print("⚡ DHEEPTHI DETECTED")
    print("=" * 70)
    print(f"Wake Word : {word}")
    print(f"Detection : #{detection_count}")
    print("=" * 70)
    print()


# ----------------------------------------------------------------------
# MAIN TEST
# ----------------------------------------------------------------------

def main() -> int:

    print()
    print("=" * 80)
    print(" ASTRA-AI :: PRODUCTION WAKE WORD TEST")
    print("=" * 80)
    print()
    print(f"Wake Word       : {WAKE_WORD}")
    print(f"Duration        : {TEST_DURATION_SECONDS:.1f} seconds")
    print("Detector        : ACTUAL production WakeWordDetector")
    print(
        f"Threshold       : {THRESHOLD:.6f} "
        f"(from production wake_word.py)"
    )
    print("STT             : Disabled")
    print("PyAutoGUI       : Disabled")
    print()

    print("-" * 80)
    print("Creating production WakeWordDetector...")
    print("-" * 80)
    print()

    # --------------------------------------------------------------
    # Validate model path BEFORE creating detector.
    # --------------------------------------------------------------

    if not MODEL_PATH.exists():

        print("❌ Model file not found.")
        print()
        print("Expected path:")
        print(f"  {MODEL_PATH}")
        print()

        return 1

    if not MODEL_PATH.is_file():

        print("❌ Model path is not a file.")
        print()
        print("Path:")
        print(f"  {MODEL_PATH}")
        print()

        return 1

    print("✅ Model file found.")
    print()

    # --------------------------------------------------------------
    # CREATE PRODUCTION DETECTOR
    # --------------------------------------------------------------

    try:

        detector = WakeWordDetector(
            model_path=MODEL_PATH,
            threshold=THRESHOLD,
            on_detected=on_wake_detected,
        )

    except Exception as error:

        print()
        print("❌ Failed to create WakeWordDetector.")
        print(f"Error: {error}")
        print()

        return 1

    print("✅ Production WakeWordDetector created.")
    print()

    # --------------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------------

    print("-" * 80)
    print("Loading production wake-word model...")
    print("-" * 80)
    print()

    try:

        if not detector.load_model():

            print()
            print(
                "❌ Production wake-word "
                "model loading failed."
            )
            print()

            try:
                detector.close()
            except Exception:
                pass

            return 1

    except Exception as error:

        print()
        print("❌ Exception while loading model.")
        print(f"Error: {error}")
        print()

        try:
            detector.close()
        except Exception:
            pass

        return 1

    print()
    print("✅ Production model loaded.")
    print()

    # --------------------------------------------------------------
    # START DETECTOR
    # --------------------------------------------------------------

    print("-" * 80)
    print("Starting production wake-word detector...")
    print("-" * 80)
    print()

    try:

        if not detector.start():

            print()
            print(
                "❌ Failed to start "
                "production detector."
            )
            print()

            try:
                detector.close()
            except Exception:
                pass

            return 1

    except Exception as error:

        print()
        print("❌ Exception while starting detector.")
        print(f"Error: {error}")
        print()

        try:
            detector.close()
        except Exception:
            pass

        return 1

    print()
    print("✅ PRODUCTION DETECTOR STARTED")
    print()
    print("🎤 Microphone is active.")
    print("🧠 TFLite FP32 inference is active.")
    print()
    print("IMPORTANT:")
    print()
    print("First, remain SILENT.")
    print("The detector should NOT detect anything.")
    print()
    print("Then say:")
    print()
    print("    DHEEPTHI")
    print()
    print("multiple times.")
    print()
    print("Waiting for detection...")
    print()

    # --------------------------------------------------------------
    # MONITOR
    # --------------------------------------------------------------

    start_time = time.monotonic()

    last_print_time = 0.0

    # Keep final diagnostics BEFORE detector.close().
    final_diagnostics = {}

    try:

        while (
            time.monotonic() - start_time
            < TEST_DURATION_SECONDS
        ):

            now = time.monotonic()

            # ------------------------------------------------------
            # Print diagnostics approximately every 250 ms.
            # ------------------------------------------------------

            if now - last_print_time >= 0.25:

                last_print_time = now

                diagnostics = (
                    detector.get_diagnostics()
                )

                audio_level = diagnostics.get(
                    "audio_level",
                    0.0,
                )

                wake_score = diagnostics.get(
                    "wake_score",
                    0.0,
                )

                peak_score = diagnostics.get(
                    "peak_wake_score",
                    0.0,
                )

                audio_blocks = diagnostics.get(
                    "audio_blocks_received",
                    0,
                )

                inference_count = diagnostics.get(
                    "inference_count",
                    0,
                )

                inference_errors = diagnostics.get(
                    "inference_errors",
                    0,
                )

                consecutive = diagnostics.get(
                    "consecutive_positive",
                    0,
                )

                print(
                    f"Audio={audio_level:.3f} | "
                    f"Wake={wake_score:.6f} | "
                    f"Peak={peak_score:.6f} | "
                    f"Threshold={THRESHOLD:.6f} | "
                    f"RX={audio_blocks} | "
                    f"INF={inference_count} | "
                    f"ERR={inference_errors} | "
                    f"Consecutive={consecutive}",
                    flush=True,
                )

            time.sleep(0.01)

    except KeyboardInterrupt:

        print()
        print()
        print("⚠️ Test interrupted by user.")

    finally:

        # ----------------------------------------------------------
        # IMPORTANT:
        #
        # Capture diagnostics BEFORE stop()/close().
        #
        # close() clears the model:
        #     _model = None
        #     _model_loaded = False
        #
        # Therefore diagnostics must be captured first.
        # ----------------------------------------------------------

        try:

            final_diagnostics = (
                detector.get_diagnostics()
            )

        except Exception as error:

            print(
                f"⚠️ Final diagnostics warning: "
                f"{error}"
            )

            final_diagnostics = {}

        print()
        print("-" * 80)
        print("Stopping detector...")
        print("-" * 80)
        print()

        try:

            detector.stop()

        except Exception as error:

            print(
                f"⚠️ Detector stop warning: "
                f"{error}"
            )

        print()
        print("-" * 80)
        print("Closing detector...")
        print("-" * 80)
        print()

        try:

            detector.close()

        except Exception as error:

            print(
                f"⚠️ Detector close warning: "
                f"{error}"
            )

    # --------------------------------------------------------------
    # FINAL DIAGNOSTICS
    # --------------------------------------------------------------

    diagnostics = final_diagnostics

    model_loaded = diagnostics.get(
        "model_loaded",
        False,
    )

    model_type = diagnostics.get(
        "model_type",
        "unknown",
    )

    model_path = diagnostics.get(
        "model_path",
        str(MODEL_PATH),
    )

    framework = diagnostics.get(
        "inference_framework",
        "unknown",
    )

    audio_blocks = diagnostics.get(
        "audio_blocks_received",
        0,
    )

    inference_count = diagnostics.get(
        "inference_count",
        0,
    )

    inference_errors = diagnostics.get(
        "inference_errors",
        0,
    )

    peak_score = diagnostics.get(
        "peak_wake_score",
        0.0,
    )

    last_score = diagnostics.get(
        "wake_score",
        0.0,
    )

    release_threshold = diagnostics.get(
        "release_threshold",
        WakeWordDetector.RELEASE_THRESHOLD,
    )

    detection_count_final = detection_count

    # --------------------------------------------------------------
    # RESULT
    # --------------------------------------------------------------

    print()
    print("=" * 80)
    print(" FINAL RESULT")
    print("=" * 80)
    print()

    print(
        f"Model Loaded       : "
        f"{model_loaded}"
    )

    print(
        f"Model Type         : "
        f"{model_type}"
    )

    print(
        f"Model Path         : "
        f"{model_path}"
    )

    print(
        f"Framework          : "
        f"{framework}"
    )

    print()

    print(
        f"Audio Blocks       : "
        f"{audio_blocks}"
    )

    print(
        f"Inferences         : "
        f"{inference_count}"
    )

    print(
        f"Inference Errors   : "
        f"{inference_errors}"
    )

    print()

    print(
        f"Peak Wake Score    : "
        f"{peak_score:.6f}"
    )

    print(
        f"Last Wake Score    : "
        f"{last_score:.6f}"
    )

    print(
        f"Threshold          : "
        f"{THRESHOLD:.6f}"
    )

    print(
        f"Release Threshold  : "
        f"{release_threshold:.6f}"
    )

    print()

    print(
        f"DHEEPTHI Detection : "
        f"{detection_count_final}"
    )

    print()

    print("=" * 80)
    print("VERDICT")
    print("-" * 80)
    print()

    # --------------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------------

    if (
        model_loaded
        and inference_count > 0
        and inference_errors == 0
        and detection_count_final > 0
    ):

        print("✅ WAKE WORD SYSTEM WORKING")
        print()

        print(
            "Production wake_word.py successfully:"
        )

        print("  ✓ Loaded TFLite model")
        print("  ✓ Captured microphone audio")
        print("  ✓ Ran inference")
        print("  ✓ Applied audio/VAD gate")
        print("  ✓ Applied wake threshold")
        print("  ✓ Confirmed DHEEPTHI")
        print("  ✓ Triggered callback")
        print("  ✓ Kept microphone active")
        print()

        print(
            "Next step: "
            "integrate into main_window.py."
        )

        return 0

    # --------------------------------------------------------------
    # FAILURE
    # --------------------------------------------------------------

    print(
        "❌ WAKE WORD SYSTEM TEST FAILED"
    )

    print()

    if not model_loaded:

        print(
            "  ✗ Model was not loaded."
        )

    if inference_count == 0:

        print(
            "  ✗ No inference was performed."
        )

    if inference_errors > 0:

        print(
            f"  ✗ Inference errors: "
            f"{inference_errors}"
        )

    if detection_count_final == 0:

        print(
            "  ✗ DHEEPTHI was not detected "
            "during the test."
        )

    print()

    return 1


# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(main())