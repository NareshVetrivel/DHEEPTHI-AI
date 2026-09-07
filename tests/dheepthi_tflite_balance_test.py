import os
import sys
import time
import signal
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice install pannala.")
    print("Run: pip install sounddevice")
    raise

# ----------------------------------------------------------------------
# TFLITE
# ----------------------------------------------------------------------
# TensorFlow is already installed in the project environment.
# Using the public tf.lite.Interpreter API also avoids the
# Pylance warning for "tflite_runtime.interpreter".

try:
    import tensorflow as tf

    Interpreter = tf.lite.Interpreter

except ImportError:
    print("ERROR: TensorFlow install pannala.")
    print("Run: pip install tensorflow")
    raise


# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

WAKE_WORD = "dheepthi"

SAMPLE_RATE = 16000
BLOCK_SIZE = 1280

THRESHOLD = 0.0005
COOLDOWN = 1.5

TEST_DURATION = 30

MODEL_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "models",
        "wakeword"
    )
)

MODELS = {
    "TFLITE FP16": os.path.join(
        MODEL_DIR,
        "dheepthi_float16.tflite"
    ),
    "TFLITE FP32": os.path.join(
        MODEL_DIR,
        "dheepthi_float32.tflite"
    ),
}


# ----------------------------------------------------------------------
# OUTPUT FILE
# ----------------------------------------------------------------------

RESULT_DIR = os.path.join(
    os.path.dirname(__file__),
    "results"
)

os.makedirs(
    RESULT_DIR,
    exist_ok=True
)

TIMESTAMP = time.strftime(
    "%Y%m%d_%H%M%S"
)

OUTPUT_FILE = os.path.join(
    RESULT_DIR,
    f"dheepthi_tflite_balance_test_{TIMESTAMP}.txt"
)


# ----------------------------------------------------------------------
# TERMINAL + FILE OUTPUT
# ----------------------------------------------------------------------

class TeeOutput:

    def __init__(self, terminal, file_handle):

        self.terminal = terminal
        self.file_handle = file_handle

    def write(self, text):

        if not text:
            return

        # Terminal:
        self.terminal.write(text)
        self.terminal.flush()

        # File:
        # Convert carriage-return based live progress into
        # clean separate lines for easier reading later.
        file_text = text.replace("\r", "\n")

        self.file_handle.write(file_text)
        self.file_handle.flush()

    def flush(self):

        self.terminal.flush()
        self.file_handle.flush()

    def isatty(self):

        return self.terminal.isatty()


# ----------------------------------------------------------------------
# GLOBAL STOP
# ----------------------------------------------------------------------

STOP_REQUESTED = False


def signal_handler(sig, frame):

    global STOP_REQUESTED

    STOP_REQUESTED = True

    print("\n\nStopping current test...")


signal.signal(
    signal.SIGINT,
    signal_handler
)


# ----------------------------------------------------------------------
# TFLITE MODEL
# ----------------------------------------------------------------------

class TFLiteWakeWordModel:

    def __init__(self, model_path):

        self.model_path = model_path

        self.interpreter = None

        self.input_details = None
        self.output_details = None

        self.input_index = None
        self.output_index = None

        self.input_shape = None
        self.input_dtype = None

        self.output_shape = None
        self.output_dtype = None

        self.labels = []

    # ------------------------------------------------------------------
    # LOAD
    # ------------------------------------------------------------------

    def load(self):

        print("\n" + "=" * 70)
        print("LOADING MODEL : TFLITE")
        print("=" * 70)

        print(
            f"Path : {self.model_path}"
        )

        if not os.path.exists(self.model_path):

            raise FileNotFoundError(
                self.model_path
            )

        self.interpreter = Interpreter(
            model_path=self.model_path,
            num_threads=max(
                1,
                os.cpu_count() or 1
            )
        )

        self.interpreter.allocate_tensors()

        self.input_details = (
            self.interpreter.get_input_details()
        )

        self.output_details = (
            self.interpreter.get_output_details()
        )

        self.input_index = (
            self.input_details[0]["index"]
        )

        self.output_index = (
            self.output_details[0]["index"]
        )

        self.input_shape = tuple(
            self.input_details[0]["shape"]
        )

        self.input_dtype = (
            self.input_details[0]["dtype"]
        )

        self.output_shape = tuple(
            self.output_details[0]["shape"]
        )

        self.output_dtype = (
            self.output_details[0]["dtype"]
        )

        print("\nInput:")

        print(
            f"  Shape    : {self.input_shape}"
        )

        print(
            f"  DType    : {self.input_dtype}"
        )

        print(
            f"  Quant    : "
            f"{self.input_details[0].get('quantization')}"
        )

        print("\nOutput:")

        print(
            f"  Shape    : {self.output_shape}"
        )

        print(
            f"  DType   : {self.output_dtype}"
        )

        print(
            f"  Quant   : "
            f"{self.output_details[0].get('quantization')}"
        )

        print("\nModel loaded successfully.")

    # ------------------------------------------------------------------
    # INPUT PREPARATION
    # ------------------------------------------------------------------

    def prepare_input(self, audio):

        audio = np.asarray(
            audio,
            dtype=np.float32
        )

        # Flatten audio.
        audio = audio.reshape(-1)

        required_size = int(
            np.prod(self.input_shape)
        )

        # Pad / crop to model input size.
        if len(audio) < required_size:

            padded = np.zeros(
                required_size,
                dtype=np.float32
            )

            padded[:len(audio)] = audio

            audio = padded

        else:

            audio = audio[:required_size]

        audio = audio.reshape(
            self.input_shape
        )

        # --------------------------------------------------------------
        # FLOAT32 MODEL
        # --------------------------------------------------------------

        if self.input_dtype == np.float32:

            return audio.astype(
                np.float32
            )

        # --------------------------------------------------------------
        # FLOAT16 MODEL
        # --------------------------------------------------------------

        if self.input_dtype == np.float16:

            return audio.astype(
                np.float16
            )

        # --------------------------------------------------------------
        # QUANTIZED MODEL
        # --------------------------------------------------------------

        if self.input_dtype in (
            np.int8,
            np.uint8
        ):

            scale, zero_point = (
                self.input_details[0][
                    "quantization"
                ]
            )

            if scale == 0:

                raise RuntimeError(
                    "Invalid TFLite quantization scale."
                )

            quantized = (
                audio / scale
            ) + zero_point

            if self.input_dtype == np.int8:

                quantized = np.clip(
                    quantized,
                    -128,
                    127
                )

            else:

                quantized = np.clip(
                    quantized,
                    0,
                    255
                )

            return quantized.astype(
                self.input_dtype
            )

        raise RuntimeError(
            f"Unsupported input dtype: "
            f"{self.input_dtype}"
        )

    # ------------------------------------------------------------------
    # INFERENCE
    # ------------------------------------------------------------------

    def infer(self, audio):

        input_data = self.prepare_input(
            audio
        )

        self.interpreter.set_tensor(
            self.input_index,
            input_data
        )

        self.interpreter.invoke()

        output = self.interpreter.get_tensor(
            self.output_index
        )

        output = np.asarray(
            output
        )

        # --------------------------------------------------------------
        # DEQUANTIZE OUTPUT
        # --------------------------------------------------------------

        if self.output_dtype in (
            np.int8,
            np.uint8
        ):

            scale, zero_point = (
                self.output_details[0][
                    "quantization"
                ]
            )

            if scale != 0:

                output = (
                    output.astype(
                        np.float32
                    )
                    - zero_point
                ) * scale

        output = (
            output
            .astype(np.float32)
            .reshape(-1)
        )

        if len(output) == 0:

            return 0.0

        # Single output.
        if len(output) == 1:

            return float(
                output[0]
            )

        # Multiple outputs:
        # Use maximum score.
        return float(
            np.max(output)
        )


# ----------------------------------------------------------------------
# AUDIO TEST
# ----------------------------------------------------------------------

def test_model(
    model_name,
    model_path
):

    global STOP_REQUESTED

    STOP_REQUESTED = False

    print("\n")
    print("#" * 70)
    print(
        f"# TESTING : {model_name}"
    )
    print("#" * 70)

    print(
        f"Model     : "
        f"{os.path.basename(model_path)}"
    )

    print(
        f"Framework : tflite"
    )

    print(
        f"Threshold : {THRESHOLD:.6f}"
    )

    print(
        f"Duration  : {TEST_DURATION}s"
    )

    model = TFLiteWakeWordModel(
        model_path
    )

    # ------------------------------------------------------------------
    # MODEL LOAD
    # ------------------------------------------------------------------

    try:

        model.load()

    except Exception as e:

        print("\nMODEL LOAD ERROR")

        print(
            f"ERROR : {e}"
        )

        return {
            "model": model_name,
            "loaded": False,
            "peak": 0.0,
            "last": 0.0,
            "detections": 0,
            "inferences": 0,
            "errors": 1,
        }

    # ------------------------------------------------------------------
    # START AUDIO
    # ------------------------------------------------------------------

    print("\n🎤 Starting microphone...")

    print(
        "Say DHEEPTHI several times."
    )

    print(
        "Speak normally."
    )

    print(
        "Press CTRL+C to stop this model test."
    )

    peak_score = 0.0

    last_score = 0.0

    detections = 0

    inference_count = 0

    errors = 0

    last_detection_time = 0.0

    start_time = time.time()

    print("\n🎤 Microphone : ON")

    print(
        "🧠 Direct inference : ON"
    )

    print(
        f"🎯 Detection threshold : "
        f"{THRESHOLD:.6f}"
    )

    # ------------------------------------------------------------------
    # AUDIO STREAM
    # ------------------------------------------------------------------

    try:

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=1,
            dtype="float32"
        ) as stream:

            while not STOP_REQUESTED:

                elapsed = (
                    time.time()
                    - start_time
                )

                if elapsed >= TEST_DURATION:

                    break

                audio, overflowed = (
                    stream.read(
                        BLOCK_SIZE
                    )
                )

                audio = np.asarray(
                    audio,
                    dtype=np.float32
                ).reshape(-1)

                # ------------------------------------------------------
                # AUDIO ACTIVITY
                # ------------------------------------------------------

                audio_peak = float(
                    np.max(
                        np.abs(audio)
                    )
                )

                # ------------------------------------------------------
                # INFERENCE
                # ------------------------------------------------------

                try:

                    score = model.infer(
                        audio
                    )

                    inference_count += 1

                    last_score = score

                    if score > peak_score:

                        peak_score = score

                    now = time.time()

                    detected = False

                    # --------------------------------------------------
                    # DETECTION
                    # --------------------------------------------------

                    if (
                        score >= THRESHOLD
                        and
                        (
                            now
                            - last_detection_time
                            >= COOLDOWN
                        )
                    ):

                        detections += 1

                        last_detection_time = (
                            now
                        )

                        detected = True

                        print("\n")

                        print(
                            "⚡ DHEEPTHI DETECTED"
                        )

                        print(
                            f"   Model      : "
                            f"{model_name}"
                        )

                        print(
                            f"   Score      : "
                            f"{score:.6f}"
                        )

                        print(
                            f"   Threshold  : "
                            f"{THRESHOLD:.6f}"
                        )

                        print(
                            f"   Detection  : "
                            f"#{detections}"
                        )

                        print()

                    # --------------------------------------------------
                    # LIVE STATUS
                    # --------------------------------------------------

                    print(
                        f"\r🎤 Audio={audio_peak:.3f} "
                        f"| 🧠 Wake={score:.6f} "
                        f"| 📈 Peak={peak_score:.6f} "
                        f"| 🎯 Threshold={THRESHOLD:.6f} "
                        f"| ⚡ Detect={detections} "
                        f"| INF={inference_count} "
                        f"| ERR={errors}",
                        end="",
                        flush=True
                    )

                except Exception as e:

                    errors += 1

                    print(
                        f"\n\n❌ INFERENCE ERROR : {e}"
                    )

    except KeyboardInterrupt:

        STOP_REQUESTED = True

    except Exception as e:

        errors += 1

        print(
            f"\n\n❌ AUDIO ERROR : {e}"
        )

    # ------------------------------------------------------------------
    # RESULT
    # ------------------------------------------------------------------

    print("\n")

    print(
        "-" * 70
    )

    print(
        f"RESULT : {model_name}"
    )

    print(
        "-" * 70
    )

    print(
        "Model Loaded     : True"
    )

    print(
        f"Model Label      : {WAKE_WORD}"
    )

    print(
        f"Threshold        : "
        f"{THRESHOLD:.6f}"
    )

    print(
        f"Audio Blocks     : "
        f"{inference_count}"
    )

    print(
        f"Inferences       : "
        f"{inference_count}"
    )

    print(
        f"Inference Errors : "
        f"{errors}"
    )

    print(
        f"Peak DHEEPTHI    : "
        f"{peak_score:.6f}"
    )

    print(
        f"Last DHEEPTHI    : "
        f"{last_score:.6f}"
    )

    print(
        f"Detections       : "
        f"{detections}"
    )

    print(
        "-" * 70
    )

    return {
        "model": model_name,
        "loaded": True,
        "peak": peak_score,
        "last": last_score,
        "detections": detections,
        "inferences": inference_count,
        "errors": errors,
    }


# ----------------------------------------------------------------------
# COMPARISON
# ----------------------------------------------------------------------

def print_comparison(results):

    print("\n")

    print(
        "=" * 90
    )

    print(
        " ASTRA-AI :: DHEEPTHI TFLITE MODEL COMPARISON"
    )

    print(
        "=" * 90
    )

    print(
        f"Detection threshold : "
        f"{THRESHOLD:.6f}"
    )

    print(
        f"Test duration       : "
        f"{TEST_DURATION}s / model"
    )

    print()

    print(
        f"{'MODEL':<18}"
        f"{'LOADED':<10}"
        f"{'PEAK SCORE':<15}"
        f"{'DETECTIONS':<13}"
        f"{'INFERENCES':<13}"
        f"{'ERRORS':<8}"
    )

    print(
        "-" * 90
    )

    for result in results:

        print(
            f"{result['model']:<18}"
            f"{str(result['loaded']):<10}"
            f"{result['peak']:<15.6f}"
            f"{result['detections']:<13}"
            f"{result['inferences']:<13}"
            f"{result['errors']:<8}"
        )

    print(
        "=" * 90
    )

    # ------------------------------------------------------------------
    # SELECT BEST
    # ------------------------------------------------------------------

    valid = [
        r
        for r in results
        if r["loaded"]
        and r["errors"] == 0
    ]

    if not valid:

        print(
            "\n❌ No valid TFLite model result."
        )

        return

    # First prefer models that actually detected.
    detected_models = [
        r
        for r in valid
        if r["detections"] > 0
    ]

    if detected_models:

        valid = detected_models

    # Highest peak score.
    best = max(
        valid,
        key=lambda r: r["peak"]
    )

    print(
        "\n🏆 CURRENT BEST TFLITE MODEL"
    )

    print(
        "-" * 50
    )

    print(
        f"Model       : "
        f"{best['model']}"
    )

    print(
        f"Peak Score  : "
        f"{best['peak']:.6f}"
    )

    print(
        f"Detections  : "
        f"{best['detections']}"
    )

    print(
        f"Errors      : "
        f"{best['errors']}"
    )

    print(
        "-" * 50
    )

    print(
        "\nNOTE:"
    )

    print(
        "Best model is selected only from this TFLite test."
    )

    print(
        "Final ONNX vs FP16 vs FP32 selection should be made"
    )

    print(
        "after testing all three under the same conditions."
    )


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():

    print()

    print(
        "=" * 80
    )

    print(
        " ASTRA-AI :: DHEEPTHI TFLITE BALANCE MODEL TEST"
    )

    print(
        "=" * 80
    )

    print()

    print(
        f"Wake Word   : {WAKE_WORD}"
    )

    print(
        f"Sample Rate : {SAMPLE_RATE}"
    )

    print(
        f"Block Size  : {BLOCK_SIZE}"
    )

    print(
        f"Threshold   : {THRESHOLD:.6f}"
    )

    print(
        f"Cooldown    : {COOLDOWN}s"
    )

    print(
        f"Duration    : {TEST_DURATION}s / model"
    )

    print()

    print(
        "Output File :"
    )

    print(
        f"  {OUTPUT_FILE}"
    )

    print()

    print(
        "Available models:"
    )

    for name, path in MODELS.items():

        status = (
            "FOUND"
            if os.path.exists(path)
            else "MISSING"
        )

        print(
            f"  {name:<16} "
            f"{status:<8} "
            f"{os.path.basename(path)}"
        )

    print()

    print(
        "=" * 70
    )

    print(
        "DETECTION MODE"
    )

    print(
        "=" * 70
    )

    print(
        f"Threshold : "
        f"{THRESHOLD:.6f}"
    )

    print(
        "Wake score >= threshold -> "
        "DHEEPTHI DETECTED"
    )

    print(
        "False detections are acceptable during this test."
    )

    print(
        "=" * 70
    )

    results = []

    # ------------------------------------------------------------------
    # TEST FP16
    # ------------------------------------------------------------------

    if os.path.exists(
        MODELS["TFLITE FP16"]
    ):

        result = test_model(
            "TFLITE FP16",
            MODELS["TFLITE FP16"]
        )

        results.append(result)

    else:

        print(
            "\n❌ TFLITE FP16 model missing."
        )

    if STOP_REQUESTED:

        print(
            "\n⚠️ Test stopped by user."
        )

        return

    print(
        "\nMoving to next model...\n"
    )

    time.sleep(1)

    # ------------------------------------------------------------------
    # TEST FP32
    # ------------------------------------------------------------------

    if os.path.exists(
        MODELS["TFLITE FP32"]
    ):

        result = test_model(
            "TFLITE FP32",
            MODELS["TFLITE FP32"]
        )

        results.append(result)

    else:

        print(
            "\n❌ TFLITE FP32 model missing."
        )

    # ------------------------------------------------------------------
    # FINAL COMPARISON
    # ------------------------------------------------------------------

    print_comparison(
        results
    )

    print("\n")

    print(
        "=" * 80
    )

    print(
        " TEST OUTPUT SAVED"
    )

    print(
        "=" * 80
    )

    print(
        f"File : {OUTPUT_FILE}"
    )

    print(
        "=" * 80
    )


# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------

if __name__ == "__main__":

    # --------------------------------------------------------------
    # Create output file and duplicate terminal output into it.
    # --------------------------------------------------------------

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as log_file:

        tee_stdout = TeeOutput(
            original_stdout,
            log_file
        )

        tee_stderr = TeeOutput(
            original_stderr,
            log_file
        )

        sys.stdout = tee_stdout
        sys.stderr = tee_stderr

        try:

            main()

        except KeyboardInterrupt:

            print(
                "\n\n⚠️ Test interrupted by user."
            )

        except Exception as e:

            print(
                "\n\n❌ FATAL ERROR"
            )

            print(
                f"ERROR : {e}"
            )

            raise

        finally:

            sys.stdout.flush()
            sys.stderr.flush()

            sys.stdout = original_stdout
            sys.stderr = original_stderr

    print()
    print(
        f"📄 Full output saved to:"
    )
    print(
        f"   {OUTPUT_FILE}"
    )