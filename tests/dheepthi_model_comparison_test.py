"""
ASTRA-AI :: DHEEPTHI Wake Word Model Comparison Test

Tests:
    1. dheepthi.onnx
    2. dheepthi_float16.tflite
    3. dheepthi_float32.tflite

Purpose:
    Compare DHEEPTHI wake-word models using the same microphone input.

Detection:
    Fixed threshold = 0.0005

The test does NOT use STT, PyAutoGUI, audio queue, or inference worker.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.model import Model


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


MODEL_DIR = PROJECT_ROOT / "models" / "wakeword"

MODEL_FILES = [
    ("ONNX", MODEL_DIR / "dheepthi.onnx", "onnx"),
    ("TFLITE FP16", MODEL_DIR / "dheepthi_float16.tflite", "tflite"),
    ("TFLITE FP32", MODEL_DIR / "dheepthi_float32.tflite", "tflite"),
]


SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1280

TEST_SECONDS = 30.0
DISPLAY_INTERVAL = 0.10

WAKE_WORD = "dheepthi"
WAKE_THRESHOLD = 0.0005
DETECTION_COOLDOWN_SECONDS = 1.5


stream = None
current_model = None
current_model_name = ""
current_model_label = ""
current_framework = ""

running = False

audio_blocks = 0
inference_count = 0
inference_errors = 0
detection_count = 0

audio_level = 0.0
wake_score = 0.0
peak_score = 0.0

last_detection_time = 0.0


def normalize_label(label: object) -> str:
    if label is None:
        return ""

    return (
        str(label)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def is_dheepthi_label(label: object) -> bool:
    normalized = normalize_label(label)
    return normalized == WAKE_WORD or WAKE_WORD in normalized


def calculate_audio_level(audio: np.ndarray) -> float:
    if audio is None or audio.size == 0:
        return 0.0

    try:
        values = audio.astype(np.float32, copy=False)
        values /= 32768.0

        rms = float(np.sqrt(np.mean(np.square(values))))

        return max(0.0, min(1.0, rms * 8.0))

    except Exception:
        return 0.0


def extract_dheepthi_score(prediction, model_label: str) -> float:
    if prediction is None:
        return 0.0

    if isinstance(prediction, dict):

        if model_label in prediction:
            try:
                return float(prediction[model_label])
            except (TypeError, ValueError):
                return 0.0

        for key, value in prediction.items():
            if is_dheepthi_label(key):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0

        return 0.0

    try:
        return float(prediction)

    except (TypeError, ValueError):
        return 0.0


def find_model_label(model: Model, model_path: Path) -> str:
    labels = []

    try:
        models = getattr(model, "models", None)

        if isinstance(models, dict):
            labels = [str(label) for label in models.keys()]

    except Exception:
        labels = []

    print()
    print("Model labels:")

    for label in labels:
        print(f"    -> {label}")

    for label in labels:
        if is_dheepthi_label(label):
            return label

    filename_label = model_path.stem

    if is_dheepthi_label(filename_label):
        return filename_label

    return ""


def load_test_model(
    name: str,
    model_path: Path,
    framework: str,
):
    print()
    print("=" * 70)
    print(f"LOADING MODEL : {name}")
    print("=" * 70)

    print(f"Path      : {model_path}")
    print(f"Framework : {framework}")
    print(f"Threshold : {WAKE_THRESHOLD}")

    if not model_path.exists():
        print("❌ File not found.")
        return None, ""

    if not model_path.is_file():
        print("❌ Path is not a file.")
        return None, ""

    try:
        model = Model(
            wakeword_models=[str(model_path)],
            inference_framework=framework,
        )

    except TypeError:
        try:
            model = Model(
                wakeword_models=[str(model_path)]
            )

        except Exception as error:
            print()
            print("❌ Model loading failed:")
            print(f"   {error}")
            return None, ""

    except Exception as error:
        print()
        print("❌ Model loading failed:")
        print(f"   {error}")
        return None, ""

    label = find_model_label(model, model_path)

    if not label:
        print()
        print("❌ DHEEPTHI label could not be found.")
        return None, ""

    print()
    print("✅ Model loaded.")
    print(f"Detected Label : {label}")

    return model, label


def check_detection(score: float):
    global detection_count
    global last_detection_time

    if score < WAKE_THRESHOLD:
        return

    now = time.monotonic()

    if now - last_detection_time < DETECTION_COOLDOWN_SECONDS:
        return

    last_detection_time = now
    detection_count += 1

    print()
    print()
    print("⚡ DHEEPTHI DETECTED")
    print(f"   Model      : {current_model_name}")
    print(f"   Score      : {score:.6f}")
    print(f"   Threshold  : {WAKE_THRESHOLD:.6f}")
    print(f"   Detection  : #{detection_count}")
    print()


def audio_callback(
    indata,
    frames,
    time_info,
    status,
):
    global audio_blocks
    global inference_count
    global inference_errors
    global audio_level
    global wake_score
    global peak_score

    if not running:
        return

    try:
        audio = np.asarray(indata, dtype=np.int16)

        if audio.ndim == 2:
            audio = audio[:, 0]

        audio = audio.copy()

    except Exception:
        inference_errors += 1
        return

    if audio.size == 0:
        return

    audio_level = calculate_audio_level(audio)
    audio_blocks += 1

    model = current_model

    if model is None:
        return

    try:
        prediction = model.predict(audio)
        inference_count += 1

    except Exception:
        inference_errors += 1
        return

    score = extract_dheepthi_score(
        prediction,
        current_model_label,
    )

    score = max(0.0, min(1.0, score))

    wake_score = score

    if score > peak_score:
        peak_score = score

    check_detection(score)


def reset_runtime():
    global audio_blocks
    global inference_count
    global inference_errors
    global detection_count
    global audio_level
    global wake_score
    global peak_score
    global last_detection_time

    audio_blocks = 0
    inference_count = 0
    inference_errors = 0
    detection_count = 0

    audio_level = 0.0
    wake_score = 0.0
    peak_score = 0.0

    last_detection_time = 0.0


def start_microphone() -> bool:
    global stream
    global running

    print()
    print("Starting microphone...")

    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            callback=audio_callback,
            device=None,
            latency="low",
        )

        running = True
        stream.start()

    except Exception as error:
        running = False
        stream = None

        print()
        print("❌ Microphone failed.")
        print(f"Error : {error}")

        return False

    print()
    print("🎤 Microphone : ON")
    print("🧠 Direct inference : ON")
    print(f"🎯 Detection threshold : {WAKE_THRESHOLD:.6f}")

    return True


def stop_microphone():
    global stream
    global running

    running = False

    current_stream = stream
    stream = None

    if current_stream is not None:
        try:
            current_stream.stop()
        except Exception:
            pass

        try:
            current_stream.close()
        except Exception:
            pass


def test_model_live(
    name: str,
    model_path: Path,
    framework: str,
) -> dict:
    global current_model
    global current_model_name
    global current_model_label
    global current_framework

    print()
    print()
    print("#" * 70)
    print(f"# TESTING : {name}")
    print("#" * 70)

    print(f"Model     : {model_path.name}")
    print(f"Framework : {framework}")
    print(f"Threshold : {WAKE_THRESHOLD:.6f}")

    print()
    print("Detection is ENABLED.")
    print("DHEEPTHI score >= threshold will trigger detection.")
    print()
    print("Say DHEEPTHI several times.")
    print("Speak normally.")
    print("Watch the Wake Score.")
    print("Watch DHEEPTHI DETECTED messages.")
    print()
    print("Press CTRL+C to skip/stop.")

    model, label = load_test_model(
        name,
        model_path,
        framework,
    )

    if model is None:
        return {
            "name": name,
            "path": str(model_path),
            "framework": framework,
            "loaded": False,
            "peak": 0.0,
            "detections": 0,
            "error": True,
        }

    current_model = model
    current_model_name = name
    current_model_label = label
    current_framework = framework

    reset_runtime()

    if not start_microphone():
        current_model = None

        return {
            "name": name,
            "path": str(model_path),
            "framework": framework,
            "loaded": True,
            "peak": 0.0,
            "detections": 0,
            "error": True,
        }

    start_time = time.monotonic()
    last_display = 0.0
    interrupted = False

    try:
        while True:
            now = time.monotonic()

            if now - start_time >= TEST_SECONDS:
                break

            if now - last_display >= DISPLAY_INTERVAL:
                print(
                    "\r"
                    f"🎤 Audio={audio_level:.3f} | "
                    f"🧠 Wake={wake_score:.6f} | "
                    f"📈 Peak={peak_score:.6f} | "
                    f"🎯 Threshold={WAKE_THRESHOLD:.6f} | "
                    f"⚡ Detect={detection_count} | "
                    f"RX={audio_blocks} | "
                    f"INF={inference_count} | "
                    f"ERR={inference_errors}",
                    end="",
                    flush=True,
                )

                last_display = now

            time.sleep(0.01)

    except KeyboardInterrupt:
        interrupted = True
        print()

    finally:
        stop_microphone()

    print()
    print()
    print("-" * 70)
    print(f"RESULT : {name}")
    print("-" * 70)

    print(f"Model Loaded     : {True}")
    print(f"Model Label      : {label}")
    print(f"Threshold        : {WAKE_THRESHOLD:.6f}")
    print(f"Audio Blocks     : {audio_blocks}")
    print(f"Inferences       : {inference_count}")
    print(f"Inference Errors : {inference_errors}")
    print(f"Peak DHEEPTHI    : {peak_score:.6f}")
    print(f"Last DHEEPTHI    : {wake_score:.6f}")
    print(f"Detections       : {detection_count}")

    print("-" * 70)

    result = {
        "name": name,
        "path": str(model_path),
        "framework": framework,
        "loaded": True,
        "peak": peak_score,
        "detections": detection_count,
        "error": inference_errors > 0,
        "interrupted": interrupted,
    }

    current_model = None

    return result


def print_summary(results):
    print()
    print()
    print("=" * 90)
    print(" ASTRA-AI :: DHEEPTHI MODEL COMPARISON")
    print("=" * 90)

    print()
    print(f"Detection threshold : {WAKE_THRESHOLD:.6f}")
    print("Purpose : MODEL + THRESHOLD DETECTION TEST")
    print()

    print(
        f"{'MODEL':<18}"
        f"{'FRAMEWORK':<12}"
        f"{'LOADED':<10}"
        f"{'PEAK SCORE':<15}"
        f"{'DETECTIONS':<13}"
        f"{'ERRORS':<10}"
    )

    print("-" * 90)

    for result in results:
        print(
            f"{result['name']:<18}"
            f"{result['framework']:<12}"
            f"{str(result['loaded']):<10}"
            f"{result['peak']:<15.6f}"
            f"{result.get('detections', 0):<13}"
            f"{str(result['error']):<10}"
        )

    print()
    print("=" * 90)
    print("HOW TO READ THIS")
    print("=" * 90)

    print()
    print(f"1. Detection threshold is {WAKE_THRESHOLD:.6f}.")
    print("2. Say DHEEPTHI multiple times.")
    print("3. Check the Wake Score.")
    print("4. If Wake Score >= threshold,")
    print("   DHEEPTHI DETECTED will appear.")
    print("5. Check Peak Score and Detection Count.")

    print()
    print("The threshold is intentionally very low")
    print("for this development/testing phase.")

    print()
    print("False detections are acceptable for")
    print("this test because the goal is to confirm")
    print("that the trained DHEEPTHI model can activate.")

    print()
    print("Later, the threshold can be tuned after")
    print("successful activation is confirmed.")

    print()
    print("=" * 90)


def main() -> int:
    global current_model

    print()
    print("=" * 80)
    print(" ASTRA-AI :: DHEEPTHI WAKE WORD MODEL TEST")
    print("=" * 80)

    print()
    print(f"Wake Word   : {WAKE_WORD}")
    print(f"Sample Rate : {SAMPLE_RATE}")
    print(f"Block Size  : {BLOCK_SIZE}")
    print(f"Threshold   : {WAKE_THRESHOLD:.6f}")
    print(f"Cooldown    : {DETECTION_COOLDOWN_SECONDS:.1f}s")
    print()

    print("Available models:")

    for name, path, framework in MODEL_FILES:
        exists = "FOUND" if path.exists() else "MISSING"

        print(
            f"  {name:<15} "
            f"{framework:<8} "
            f"{exists:<8} "
            f"{path.name}"
        )

    print()
    print("=" * 60)
    print("⚠️ DETECTION MODE")
    print("=" * 60)
    print(f"Threshold : {WAKE_THRESHOLD:.6f}")
    print("Wake score >= threshold -> DHEEPTHI DETECTED")
    print("False detections are acceptable during this test.")
    print("=" * 60)
    print()

    results = []

    try:
        for name, path, framework in MODEL_FILES:
            result = test_model_live(
                name=name,
                model_path=path,
                framework=framework,
            )

            results.append(result)

            print()

            if name != MODEL_FILES[-1][0]:
                print("Moving to next model...")
                time.sleep(1.0)

    except KeyboardInterrupt:
        print()
        print()
        print("⚠️ Test stopped by user.")

    finally:
        stop_microphone()
        current_model = None

    print_summary(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
