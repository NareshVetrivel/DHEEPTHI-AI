"""
ASTRA-AI
========

DHEEPTHI Wake Word Detector
---------------------------

Engine:
    openWakeWord + TensorFlow Lite

Audio:
    sounddevice

Mode:
    LOCAL / OFFLINE

Model:
    dheepthi_float32.tflite

Protection:
    - microphone/activity gate
    - startup noise-floor calibration
    - WebRTC human-speech gate
    - openWakeWord VAD
    - wake-score threshold
    - 2 consecutive positive inference frames
    - confirmation time limit
    - cooldown + score release
    - silence reset
    - TFLite runtime compatibility for Windows + TensorFlow

No STT.
No PyAutoGUI.
"""

from __future__ import annotations

import sys
import threading
import time
import types
from collections import deque
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import sounddevice as sd


# Optional human-speech VAD.  If the package is unavailable, the
# existing audio/noise/openWakeWord gates continue to work unchanged.
try:
    import webrtcvad
except ImportError:
    webrtcvad = None


# ----------------------------------------------------------------------
# TFLITE RUNTIME COMPATIBILITY
# ----------------------------------------------------------------------

def _install_tflite_compatibility() -> bool:
    """
    Make TensorFlow Lite available under the runtime module names
    expected by different openWakeWord versions.
    """

    # 1. Newer LiteRT
    try:
        import importlib

        importlib.import_module(
            "ai_edge_litert.interpreter"
        )

        return True

    except ImportError:
        pass


    try:
        import importlib

        importlib.import_module(
            "tflite_runtime.interpreter"
        )

        return True

    except ImportError:
        pass

    # 3. TensorFlow Lite fallback
    try:
        from tensorflow.lite.python.interpreter import Interpreter

        try:
            from tensorflow.lite.python.interpreter import load_delegate

        except ImportError:
            load_delegate = None

    except ImportError:
        return False

    # ------------------------------------------------------------------
    # tflite_runtime compatibility module
    # ------------------------------------------------------------------

    try:
        tflite_runtime_module = types.ModuleType(
            "tflite_runtime"
        )

        tflite_interpreter_module = types.ModuleType(
            "tflite_runtime.interpreter"
        )

        tflite_interpreter_module.Interpreter = Interpreter

        if load_delegate is not None:
            tflite_interpreter_module.load_delegate = (
                load_delegate
            )

        tflite_runtime_module.interpreter = (
            tflite_interpreter_module
        )

        sys.modules["tflite_runtime"] = (
            tflite_runtime_module
        )

        sys.modules["tflite_runtime.interpreter"] = (
            tflite_interpreter_module
        )

    except Exception as error:
        print(
            "⚠️ Failed to install tflite_runtime "
            f"compatibility layer: {error}"
        )

    # ------------------------------------------------------------------
    # ai_edge_litert compatibility module
    # ------------------------------------------------------------------

    try:
        ai_edge_module = types.ModuleType(
            "ai_edge_litert"
        )

        ai_edge_interpreter_module = types.ModuleType(
            "ai_edge_litert.interpreter"
        )

        ai_edge_interpreter_module.Interpreter = (
            Interpreter
        )

        if load_delegate is not None:
            ai_edge_interpreter_module.load_delegate = (
                load_delegate
            )

        ai_edge_module.interpreter = (
            ai_edge_interpreter_module
        )

        sys.modules["ai_edge_litert"] = (
            ai_edge_module
        )

        sys.modules["ai_edge_litert.interpreter"] = (
            ai_edge_interpreter_module
        )

    except Exception as error:
        print(
            "⚠️ Failed to install ai_edge_litert "
            f"compatibility layer: {error}"
        )

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    return (
        "tflite_runtime.interpreter" in sys.modules
        or "ai_edge_litert.interpreter" in sys.modules
    )


# Install compatibility BEFORE importing openWakeWord.
_TFLITE_AVAILABLE = _install_tflite_compatibility()


# ----------------------------------------------------------------------
# OPENWAKEWORD
# ----------------------------------------------------------------------

try:
    from openwakeword.model import Model

except ImportError as error:
    raise ImportError(
        "openWakeWord install pannala. "
        "Run: pip install openwakeword"
    ) from error


class WakeWordDetector:
    """Production DHEEPTHI wake-word detector."""

    WAKE_WORD = "dheepthi"

    SAMPLE_RATE = 16000
    CHANNELS = 1

    # 80 ms @ 16 kHz
    BLOCK_SIZE = 1280

    # Standard openWakeWord embedding dimension.
    FEATURE_DIMENSION = 96

    # Detection
    DEFAULT_THRESHOLD = 0.000250

    REQUIRED_CONSECUTIVE_DETECTIONS = 2

    MAX_CONFIRMATION_GAP_SECONDS = 0.25

    DETECTION_COOLDOWN_SECONDS = 1.5

    RELEASE_THRESHOLD = 0.30

    RELEASE_SILENCE_SECONDS = 0.25

    # Audio activity / noise gate
    DEFAULT_VAD_THRESHOLD = 0.025

    MIN_AUDIO_LEVEL = 0.025

    NOISE_MARGIN = 0.020

    NOISE_CALIBRATION_BLOCKS = 12

    SILENCE_RMS = 0.0015

    # openWakeWord VAD
    OPENWAKEWORD_VAD_THRESHOLD = 0.50

    # Human-speech gate
    #
    # WebRTC VAD only accepts 10/20/30 ms PCM frames.  Our production
    # microphone block is 80 ms, so each block is evaluated as four
    # 20 ms frames.  A modest speech ratio keeps short wake-word speech
    # segments usable while rejecting most music/background-only blocks.
    SPEECH_VAD_MODE = 3
    SPEECH_VAD_FRAME_MS = 20
    SPEECH_VAD_FRAME_SAMPLES = (
        SAMPLE_RATE * SPEECH_VAD_FRAME_MS // 1000
    )
    SPEECH_VAD_MIN_RATIO = 0.25

    def __init__(
        self,
        model_path: str | Path,
        threshold: float = DEFAULT_THRESHOLD,
        vad_threshold: float = DEFAULT_VAD_THRESHOLD,
        on_detected: Optional[Callable[[str], None]] = None,
        level_callback: Optional[Callable[[float], None]] = None,
    ):
        # ==============================================================
        # LOCK INITIALIZATION
        # ==============================================================

        self._model_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._audio_lock = threading.Lock()

        self.model_path = Path(model_path)

        self.threshold = float(threshold)
        self.vad_threshold = float(vad_threshold)

        self.on_detected = on_detected
        self.level_callback = level_callback

        # ==============================================================
        # OPENWAKEWORD MODEL
        # ==============================================================

        self._model: Optional[Model] = None
        self._model_label = ""
        self._model_loaded = False

        # ==============================================================
        # MODEL INPUT INFORMATION
        # ==============================================================

        self._model_input_shape: tuple[int, ...] = ()
        self._model_output_shape: tuple[int, ...] = ()

        self._model_input_frames = 0
        self._model_input_features = 0

        self._model_input_index: Optional[int] = None
        self._model_output_index: Optional[int] = None

        self._model_layout = "unknown"

        # ==============================================================
        # RUNTIME
        # ==============================================================

        self._running = False
        self._closed = False

        self._armed = True

        # ==============================================================
        # MICROPHONE
        # ==============================================================

        self._stream: Optional[sd.InputStream] = None

        # ==============================================================
        # DETECTION STATE
        # ==============================================================

        self._consecutive_positive = 0

        self._last_positive_time = 0.0

        self._last_detection_time = 0.0

        self._waiting_for_release = False

        self._last_active_time = 0.0

        self._positive_scores: deque[float] = deque(
            maxlen=4
        )

        # ==============================================================
        # NOISE CALIBRATION
        # ==============================================================

        self._noise_calibration_remaining = 0

        self._noise_floor = 0.0

        self._noise_samples: list[float] = []

        # ==============================================================
        # HUMAN SPEECH GATE
        # ==============================================================

        self._speech_vad = None
        self._speech_vad_available = False
        self._speech_ratio = 0.0
        self._speech_detected = False

        if webrtcvad is not None:
            try:
                self._speech_vad = webrtcvad.Vad(
                    self.SPEECH_VAD_MODE
                )
                self._speech_vad_available = True
            except Exception as error:
                print(
                    f"⚠️ WebRTC speech VAD unavailable: {error}"
                )

        # ==============================================================
        # DIAGNOSTICS
        # ==============================================================

        self._audio_level = 0.0

        self._wake_score = 0.0

        self._peak_wake_score = 0.0

        self._audio_blocks_received = 0

        self._inference_count = 0

        self._inference_errors = 0

        self._skipped_inference_frames = 0

        self._last_feature_energy = 0.0

        self._available_feature_frames = 0

    # ==================================================================
    # LOCK SAFETY
    # ==================================================================

    def _ensure_locks(self) -> None:
        """Guarantee that all internal locks exist."""

        if not hasattr(self, "_model_lock"):
            self._model_lock = threading.RLock()

        if not hasattr(self, "_state_lock"):
            self._state_lock = threading.RLock()

        if not hasattr(self, "_audio_lock"):
            self._audio_lock = threading.Lock()

    # ==================================================================
    # MODEL LABEL HELPERS
    # ==================================================================

    @staticmethod
    def _normalize_label(label: object) -> str:

        if label is None:
            return ""

        return (
            str(label)
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

    def _is_dheepthi_label(
        self,
        label: object,
    ) -> bool:

        normalized = self._normalize_label(
            label
        )

        return (
            normalized == self.WAKE_WORD
            or self.WAKE_WORD in normalized
        )

    def _find_model_label(
        self,
        model: Model,
    ) -> str:
        """
        Find the DHEEPTHI output key exposed by openWakeWord.
        """

        try:

            models = getattr(
                model,
                "models",
                None,
            )

            if isinstance(models, dict):

                labels = [
                    str(label)
                    for label in models.keys()
                ]

                print()
                print("Model labels:")

                for label in labels:
                    print(
                        f"    -> {label}"
                    )

                for label in labels:

                    if self._is_dheepthi_label(
                        label
                    ):
                        return label

        except Exception:
            pass

        # Filename fallback
        filename_label = self._normalize_label(
            self.model_path.stem
        )

        if self._is_dheepthi_label(
            filename_label
        ):
            return filename_label

        return ""

    # ==================================================================
    # MODEL TENSOR INSPECTION
    # ==================================================================

    def _inspect_model_tensor(
        self,
        model: Model,
        label: str,
    ) -> None:
        """
        Inspect the actual TFLite tensor shape.

        This is important for custom wake-word models because the
        feature window can differ from the standard 16-frame model.
        """

        self._model_input_shape = ()
        self._model_output_shape = ()

        self._model_input_frames = 0
        self._model_input_features = 0

        self._model_input_index = None
        self._model_output_index = None

        self._model_layout = "unknown"

        try:

            interpreter = model.models.get(
                label
            )

            if interpreter is None:
                return

            input_details = (
                interpreter.get_input_details()
            )

            output_details = (
                interpreter.get_output_details()
            )

            if not input_details:
                raise RuntimeError(
                    "TFLite model has no input tensor."
                )

            if not output_details:
                raise RuntimeError(
                    "TFLite model has no output tensor."
                )

            input_detail = input_details[0]
            output_detail = output_details[0]

            input_shape = tuple(
                int(x)
                for x in input_detail["shape"]
            )

            output_shape = tuple(
                int(x)
                for x in output_detail["shape"]
            )

            self._model_input_shape = (
                input_shape
            )

            self._model_output_shape = (
                output_shape
            )

            self._model_input_index = int(
                input_detail["index"]
            )

            self._model_output_index = int(
                output_detail["index"]
            )

            # ----------------------------------------------------------
            # Expected openWakeWord model:
            #
            # [1, frames, 96]
            #
            # Some custom exports may use:
            #
            # [1, 96, frames]
            # ----------------------------------------------------------

            if (
                len(input_shape) == 3
                and input_shape[0] == 1
            ):

                dim1 = input_shape[1]
                dim2 = input_shape[2]

                if (
                    dim2
                    == self.FEATURE_DIMENSION
                ):

                    self._model_input_frames = (
                        dim1
                    )

                    self._model_input_features = (
                        dim2
                    )

                    self._model_layout = (
                        "frames_features"
                    )

                elif (
                    dim1
                    == self.FEATURE_DIMENSION
                ):

                    self._model_input_features = (
                        dim1
                    )

                    self._model_input_frames = (
                        dim2
                    )

                    self._model_layout = (
                        "features_frames"
                    )

                else:

                    self._model_input_frames = (
                        dim1
                    )

                    self._model_input_features = (
                        dim2
                    )

                    self._model_layout = (
                        "custom"
                    )

            print()
            print("TFLite Tensor Inspection")
            print(
                f"    Input shape  : "
                f"{self._model_input_shape}"
            )
            print(
                f"    Output shape : "
                f"{self._model_output_shape}"
            )
            print(
                f"    Input frames : "
                f"{self._model_input_frames}"
            )
            print(
                f"    Features     : "
                f"{self._model_input_features}"
            )
            print(
                f"    Layout       : "
                f"{self._model_layout}"
            )
            print()

        except Exception as error:

            print(
                "⚠️ Could not inspect "
                f"TFLite tensor: {error}"
            )

    # ==================================================================
    # MODEL LOADING
    # ==================================================================

    def load_model(self) -> bool:
        """
        Load DHEEPTHI model using native openWakeWord.
        """

        self._ensure_locks()

        with self._model_lock:

            if (
                self._model_loaded
                and self._model is not None
            ):
                return True

            # ----------------------------------------------------------
            # FILE CHECK
            # ----------------------------------------------------------

            if not self.model_path.exists():

                print(
                    "❌ Wake-word model not found:"
                )

                print(
                    f"   {self.model_path}"
                )

                return False

            if not self.model_path.is_file():

                print(
                    "❌ Wake-word model path "
                    "is not a file:"
                )

                print(
                    f"   {self.model_path}"
                )

                return False

            # ----------------------------------------------------------
            # TFLITE BACKEND CHECK
            # ----------------------------------------------------------

            if not _TFLITE_AVAILABLE:

                print(
                    "❌ No usable TensorFlow Lite "
                    "interpreter found."
                )

                print(
                    "   Install TensorFlow:"
                )

                print(
                    "   pip install tensorflow"
                )

                return False

            # ----------------------------------------------------------
            # LOAD OPENWAKEWORD MODEL
            # ----------------------------------------------------------

            try:

                try:

                    model = Model(
                        wakeword_models=[
                            str(self.model_path)
                        ],
                        inference_framework="tflite",
                        vad_threshold=(
                            self.OPENWAKEWORD_VAD_THRESHOLD
                        ),
                    )

                except TypeError:

                    # Compatibility with older versions.
                    model = Model(
                        wakeword_models=[
                            str(self.model_path)
                        ],
                        inference_framework="tflite",
                    )

            except Exception as error:

                self._model = None
                self._model_loaded = False
                self._model_label = ""

                print(
                    "❌ openWakeWord model "
                    "loading failed:"
                )

                print(
                    f"   {error}"
                )

                return False

            # ----------------------------------------------------------
            # FIND LABEL
            # ----------------------------------------------------------

            label = self._find_model_label(
                model
            )

            if not label:

                print(
                    "❌ DHEEPTHI model label "
                    "could not be found."
                )

                print(
                    f"   Model file: "
                    f"{self.model_path.name}"
                )

                try:
                    model.reset()

                except Exception:
                    pass

                return False

            # ----------------------------------------------------------
            # INSPECT ACTUAL TFLITE TENSOR
            # ----------------------------------------------------------

            self._inspect_model_tensor(
                model,
                label,
            )

            # ----------------------------------------------------------
            # VALIDATE MODEL SHAPE
            # ----------------------------------------------------------

            if not self._model_input_shape:

                print(
                    "❌ Could not determine "
                    "TFLite model input shape."
                )

                try:
                    model.reset()

                except Exception:
                    pass

                return False

            if len(
                self._model_input_shape
            ) != 3:

                print(
                    "❌ Unsupported wake-word "
                    "model input shape:"
                )

                print(
                    f"   {self._model_input_shape}"
                )

                print(
                    "   Expected a 3D tensor such as:"
                )

                print(
                    "   [1, 16, 96]"
                )

                print(
                    "   or"
                )

                print(
                    "   [1, 96, 16]"
                )

                try:
                    model.reset()

                except Exception:
                    pass

                return False

            # ----------------------------------------------------------
            # STORE MODEL
            # ----------------------------------------------------------

            self._model = model
            self._model_label = label
            self._model_loaded = True

            print()
            print(
                "✅ DHEEPTHI openWakeWord "
                "model loaded."
            )

            print(
                f"Model      : "
                f"{self.model_path.name}"
            )

            print(
                "Framework  : TFLITE"
            )

            print(
                "Runtime    : "
                "TensorFlow Lite compatibility"
            )

            print(
                f"Label      : "
                f"{self._model_label}"
            )

            print(
                "Input      : "
                "16 kHz / int16 PCM / "
                f"{self.BLOCK_SIZE} samples"
            )

            print(
                "Features   : "
                "openWakeWord internal "
                "preprocessing"
            )

            print(
                f"Model input: "
                f"{self._model_input_shape}"
            )

            print(
                f"Feature window: "
                f"{self._model_input_frames} frames"
            )

            print(
                f"openWakeWord VAD : "
                f"{self.OPENWAKEWORD_VAD_THRESHOLD:.2f}"
            )

            return True

    # ==================================================================
    # MODEL STATUS
    # ==================================================================

    def is_model_loaded(self) -> bool:

        self._ensure_locks()

        with self._model_lock:

            return (
                self._model is not None
                and self._model_loaded
            )

    # ==================================================================
    # RESET MODEL STATE
    # ==================================================================

    def _reset_model_state(self) -> None:
        """
        Reset openWakeWord streaming state.
        """

        self._ensure_locks()

        with self._model_lock:

            model = self._model

        if model is None:
            return

        try:

            model.reset()

        except Exception as error:

            print(
                f"\n⚠️ Wake model reset warning: "
                f"{error}"
            )

    # ==================================================================
    # AUDIO LEVEL
    # ==================================================================

    @staticmethod
    def _calculate_audio_level(
        audio: np.ndarray,
    ) -> float:

        if (
            audio is None
            or audio.size == 0
        ):
            return 0.0

        try:

            values = np.asarray(
                audio,
                dtype=np.float32,
            ).reshape(-1)

            values /= 32768.0

            rms = float(
                np.sqrt(
                    np.mean(
                        np.square(values)
                    )
                )
            )

            return max(
                0.0,
                min(
                    1.0,
                    rms * 8.0,
                ),
            )

        except Exception:
            return 0.0

    # ==================================================================
    # RMS
    # ==================================================================

    @staticmethod
    def _calculate_rms(
        audio_float: np.ndarray,
    ) -> float:

        if (
            audio_float is None
            or audio_float.size == 0
        ):
            return 0.0

        values = np.asarray(
            audio_float,
            dtype=np.float32,
        ).reshape(-1)

        return float(
            np.sqrt(
                np.mean(
                    np.square(values)
                )
            )
        )

    # ==================================================================
    # NOISE FLOOR
    # ==================================================================

    def _update_noise_floor(
        self,
        level: float,
    ) -> None:

        self._ensure_locks()

        with self._state_lock:

            if (
                self._noise_calibration_remaining
                <= 0
            ):
                return

            self._noise_samples.append(
                float(level)
            )

            self._noise_calibration_remaining -= 1

            if (
                self._noise_calibration_remaining
                == 0
            ):

                if self._noise_samples:

                    self._noise_floor = float(
                        np.median(
                            np.asarray(
                                self._noise_samples,
                                dtype=np.float32,
                            )
                        )
                    )

                else:

                    self._noise_floor = 0.0

                print(
                    f"\n🎧 Noise floor calibrated: "
                    f"{self._noise_floor:.4f}"
                )

    # ==================================================================
    # AUDIO ACTIVITY
    # ==================================================================

    def _audio_is_active(
        self,
        level: float,
        rms: float,
    ) -> bool:

        if rms < self.SILENCE_RMS:
            return False

        absolute_gate = max(
            self.MIN_AUDIO_LEVEL,
            self.vad_threshold,
        )

        if level < absolute_gate:
            return False

        self._ensure_locks()

        with self._state_lock:

            noise_floor = self._noise_floor

            calibration_remaining = (
                self._noise_calibration_remaining
            )

        if calibration_remaining > 0:
            return True

        return level >= (
            noise_floor
            + self.NOISE_MARGIN
        )

    # ==================================================================
    # HUMAN SPEECH GATE
    # ==================================================================

    def _detect_human_speech(
        self,
        audio_int16: np.ndarray,
    ) -> tuple[bool, float]:
        """Return whether the current block contains human speech.

        This is deliberately an additional gate, not a replacement for
        the existing openWakeWord detector.  The detector still receives
        the original PCM when speech is present, so model preprocessing
        and inference remain unchanged.

        When WebRTC VAD is unavailable, return ``True`` so the production
        wake-word pipeline falls back to its original gates rather than
        becoming unusable.
        """

        if not self._speech_vad_available or self._speech_vad is None:
            return True, 1.0

        values = np.asarray(
            audio_int16,
            dtype=np.int16,
        ).reshape(-1)

        frame_size = self.SPEECH_VAD_FRAME_SAMPLES

        if values.size < frame_size:
            return False, 0.0

        total_frames = values.size // frame_size
        voiced_frames = 0

        for index in range(total_frames):
            start = index * frame_size
            end = start + frame_size
            frame = values[start:end]

            if frame.size != frame_size:
                continue

            try:
                if self._speech_vad.is_speech(
                    frame.tobytes(),
                    self.SAMPLE_RATE,
                ):
                    voiced_frames += 1
            except Exception:
                # Do not allow VAD implementation/runtime issues to
                # break the already-working wake-word detector.
                return True, 1.0

        ratio = (
            float(voiced_frames) / float(total_frames)
            if total_frames > 0
            else 0.0
        )

        return (
            ratio >= self.SPEECH_VAD_MIN_RATIO,
            ratio,
        )

    # ==================================================================
    # PREDICTION SCORE
    # ==================================================================

    def _extract_wake_score(
        self,
        prediction: Any,
    ) -> float:

        if prediction is None:
            return 0.0

        if isinstance(
            prediction,
            dict,
        ):

            if (
                self._model_label
                in prediction
            ):

                try:

                    return float(
                        prediction[
                            self._model_label
                        ]
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    return 0.0

            for key, value in (
                prediction.items()
            ):

                if self._is_dheepthi_label(
                    key
                ):

                    try:

                        return float(
                            value
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        return 0.0

            return 0.0

        try:

            return float(
                prediction
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

    # ==================================================================
    # FEATURE WINDOW
    # ==================================================================

    def _get_feature_window(
        self,
    ) -> Optional[np.ndarray]:
        """
        Get exactly the number of feature frames required by the
        TFLite model.

        IMPORTANT:
            openWakeWord's feature buffer needs enough frames before
            the custom model can be invoked.

        Example:
            buffer = 42 frames
            model = 96 frames

        Result:
            inference is skipped safely until buffer >= 96.
        """

        with self._model_lock:

            model = self._model

        if model is None:
            return None

        try:

            preprocessor = getattr(
                model,
                "preprocessor",
                None,
            )

            if preprocessor is None:
                return None

            required_frames = (
                self._model_input_frames
            )

            if required_frames <= 0:
                return None

            # ----------------------------------------------------------
            # IMPORTANT:
            #
            # Do not call get_features() blindly.
            #
            # If the buffer has only 42 frames and the model expects
            # 96 frames, get_features(96) returns only 42 frames.
            #
            # That was the source of:
            #
            # Got 42 but expected 96
            # ----------------------------------------------------------

            feature_buffer = getattr(
                preprocessor,
                "feature_buffer",
                None,
            )

            if feature_buffer is None:
                return None

            available_frames = int(
                len(feature_buffer)
            )

            with self._audio_lock:

                self._available_feature_frames = (
                    available_frames
                )

            if (
                available_frames
                < required_frames
            ):

                return None

            features = (
                preprocessor.get_features(
                    required_frames
                )
            )

            features = np.asarray(
                features,
                dtype=np.float32,
            )

            return features

        except Exception:

            return None

    # ==================================================================
    # MODEL INPUT PREPARATION
    # ==================================================================

    def _prepare_model_input(
        self,
        features: np.ndarray,
    ) -> Optional[np.ndarray]:
        """
        Convert openWakeWord features to the exact tensor layout
        required by the TFLite model.
        """

        if features is None:
            return None

        values = np.asarray(
            features,
            dtype=np.float32,
        )

        expected = (
            self._model_input_shape
        )

        if not expected:
            return None

        # --------------------------------------------------------------
        # Normal openWakeWord layout:
        #
        # [1, frames, 96]
        # --------------------------------------------------------------

        if (
            len(expected) == 3
            and expected[0] == 1
        ):

            expected_dim1 = expected[1]
            expected_dim2 = expected[2]

            # ----------------------------------------------------------
            # Remove accidental extra dimensions only if necessary.
            # ----------------------------------------------------------

            if values.ndim == 2:

                values = values[None, ...]

            if values.ndim != 3:
                return None

            # ----------------------------------------------------------
            # [1, frames, features]
            # ----------------------------------------------------------

            if (
                values.shape[1]
                == expected_dim1
                and values.shape[2]
                == expected_dim2
            ):

                return values.astype(
                    np.float32
                )

            # ----------------------------------------------------------
            # [1, features, frames]
            #
            # Transpose openWakeWord output.
            # ----------------------------------------------------------

            if (
                values.shape[1]
                == expected_dim2
                and values.shape[2]
                == expected_dim1
            ):

                return np.transpose(
                    values,
                    (0, 2, 1),
                ).astype(
                    np.float32
                )

        # --------------------------------------------------------------
        # Unsupported shape.
        # --------------------------------------------------------------

        return None

    # ==================================================================
    # RAW TFLITE INFERENCE
    # ==================================================================

    def _infer_tflite_from_features(
        self,
        features: np.ndarray,
    ) -> float:
        """
        Run the already-generated openWakeWord features directly through
        the underlying TFLite interpreter.

        This avoids the openWakeWord Model.predict() path attempting to
        pass an incomplete feature window to the custom TFLite model.
        """

        with self._model_lock:

            model = self._model

        if model is None:
            raise RuntimeError(
                "openWakeWord model "
                "is not loaded."
            )

        interpreter = model.models.get(
            self._model_label
        )

        if interpreter is None:
            raise RuntimeError(
                "Underlying TFLite interpreter "
                "not found."
            )

        input_index = (
            self._model_input_index
        )

        output_index = (
            self._model_output_index
        )

        if (
            input_index is None
            or output_index is None
        ):

            raise RuntimeError(
                "TFLite input/output tensor "
                "indices are not available."
            )

        model_input = (
            self._prepare_model_input(
                features
            )
        )

        if model_input is None:

            raise RuntimeError(
                "Unable to prepare TFLite "
                "model input.\n"
                f"Feature shape : "
                f"{features.shape}\n"
                f"Expected shape: "
                f"{self._model_input_shape}"
            )

        # --------------------------------------------------------------
        # FINAL SHAPE CHECK
        # --------------------------------------------------------------

        if tuple(
            model_input.shape
        ) != tuple(
            self._model_input_shape
        ):

            raise RuntimeError(
                "TFLite input shape mismatch.\n"
                f"Prepared : "
                f"{model_input.shape}\n"
                f"Expected : "
                f"{self._model_input_shape}"
            )

        # --------------------------------------------------------------
        # SET + INVOKE
        # --------------------------------------------------------------

        interpreter.set_tensor(
            input_index,
            model_input,
        )

        interpreter.invoke()

        output = interpreter.get_tensor(
            output_index
        )

        output = np.asarray(
            output,
            dtype=np.float32,
        )

        if output.size == 0:
            return 0.0

        score = float(
            output.reshape(-1)[0]
        )

        return max(
            0.0,
            min(
                1.0,
                score,
            ),
        )

    # ==================================================================
    # INFERENCE
    # ==================================================================

    def _infer(
        self,
        audio_int16: np.ndarray,
    ) -> Optional[float]:
        """
        Run one 80 ms PCM frame through openWakeWord preprocessing
        and then the actual TFLite wake-word model.

        Returns:
            float:
                Wake score

            None:
                Feature buffer is not ready yet.
        """

        self._ensure_locks()

        with self._model_lock:

            model = self._model

        if model is None:

            raise RuntimeError(
                "openWakeWord model "
                "is not loaded."
            )

        audio_int16 = np.asarray(
            audio_int16,
            dtype=np.int16,
        ).reshape(-1)

        if audio_int16.size == 0:
            return 0.0

        # --------------------------------------------------------------
        # IMPORTANT:
        #
        # Feed audio into openWakeWord's actual preprocessor.
        #
        # We intentionally DO NOT call model.predict() here because
        # model.predict() immediately attempts the custom model when
        # n_prepared_samples == 1280.
        #
        # For a 96-frame custom model the feature buffer initially has
        # only ~42 frames, causing:
        #
        # Got 42 but expected 96
        # --------------------------------------------------------------

        try:

            n_prepared_samples = (
                model.preprocessor(
                    audio_int16
                )
            )

        except Exception as error:

            raise RuntimeError(
                "openWakeWord preprocessing "
                f"failed: {error}"
            ) from error

        # --------------------------------------------------------------
        # No complete 80 ms processing yet.
        # --------------------------------------------------------------

        if (
            n_prepared_samples
            < self.BLOCK_SIZE
        ):

            return None

        # --------------------------------------------------------------
        # Get exact required feature window.
        # --------------------------------------------------------------

        features = (
            self._get_feature_window()
        )

        if features is None:

            with self._audio_lock:

                self._skipped_inference_frames += 1

            return None

        # --------------------------------------------------------------
        # Diagnostics
        # --------------------------------------------------------------

        try:

            self._last_feature_energy = float(
                np.mean(
                    np.abs(features)
                )
            )

        except Exception:
            self._last_feature_energy = 0.0

        # --------------------------------------------------------------
        # TFLite inference
        # --------------------------------------------------------------

        score = (
            self._infer_tflite_from_features(
                features
            )
        )

        return score

    # ==================================================================
    # SCORE UPDATE
    # ==================================================================

    def _update_wake_score(
        self,
        score: float,
    ) -> None:

        score = max(
            0.0,
            min(
                1.0,
                float(score),
            ),
        )

        self._ensure_locks()

        with self._audio_lock:

            self._wake_score = score

            if (
                score
                > self._peak_wake_score
            ):

                self._peak_wake_score = (
                    score
                )

    # ==================================================================
    # CONFIRMATION RESET
    # ==================================================================

    def _reset_confirmation(
        self,
    ) -> None:

        self._consecutive_positive = 0

        self._last_positive_time = 0.0

        self._positive_scores.clear()

    # ==================================================================
    # AUTOMATIC RELEASE
    # ==================================================================

    def _try_auto_release(
        self,
        score: float,
    ) -> None:
        """
        Re-arm detector after cooldown + low score + silence.
        """

        self._ensure_locks()

        now = time.monotonic()

        with self._state_lock:

            if (
                not self._running
                or self._closed
            ):
                return

            if self._armed:
                return

            if not self._waiting_for_release:
                return

            elapsed = (
                now
                - self._last_detection_time
            )

            silence_elapsed = (
                now
                - self._last_active_time
            )

            if (
                elapsed
                >= self.DETECTION_COOLDOWN_SECONDS
                and score
                <= self.RELEASE_THRESHOLD
                and silence_elapsed
                >= self.RELEASE_SILENCE_SECONDS
            ):

                self._armed = True

                self._waiting_for_release = (
                    False
                )

        self._reset_confirmation()

    # ==================================================================
    # DETECTION
    # ==================================================================

    def _check_detection(
        self,
        score: float,
        audio_active: bool = True,
    ) -> None:
        """
        Conservative two-frame confirmation state machine.
        """

        self._ensure_locks()

        score = float(score)

        now = time.monotonic()

        with self._state_lock:

            running = self._running

            armed = self._armed

            waiting_for_release = (
                self._waiting_for_release
            )

            last_detection = (
                self._last_detection_time
            )

            last_positive_time = (
                self._last_positive_time
            )

        # --------------------------------------------------------------
        # NOT RUNNING
        # --------------------------------------------------------------

        if not running:
            return

        # --------------------------------------------------------------
        # AUDIO NOT ACTIVE
        # --------------------------------------------------------------

        if not audio_active:

            self._reset_confirmation()

            self._try_auto_release(
                score
            )

            return

        # --------------------------------------------------------------
        # RELEASE / RE-ARM
        # --------------------------------------------------------------

        if not armed:

            elapsed = (
                now
                - last_detection
            )

            with self._state_lock:

                silence_elapsed = (
                    now
                    - self._last_active_time
                )

            if (
                waiting_for_release
                and elapsed
                >= self.DETECTION_COOLDOWN_SECONDS
                and score
                <= self.RELEASE_THRESHOLD
                and silence_elapsed
                >= self.RELEASE_SILENCE_SECONDS
            ):

                with self._state_lock:

                    if (
                        self._running
                        and not self._closed
                    ):

                        self._armed = True

                        self._waiting_for_release = (
                            False
                        )

                self._reset_confirmation()

            return

        # --------------------------------------------------------------
        # BELOW THRESHOLD
        # --------------------------------------------------------------

        if score < self.threshold:

            self._reset_confirmation()

            return

        # --------------------------------------------------------------
        # CONFIRMATION GAP
        # --------------------------------------------------------------

        if (
            self._consecutive_positive > 0
            and (
                now
                - last_positive_time
            )
            > self.MAX_CONFIRMATION_GAP_SECONDS
        ):

            self._reset_confirmation()

        # --------------------------------------------------------------
        # POSITIVE FRAME
        # --------------------------------------------------------------

        self._consecutive_positive += 1

        self._last_positive_time = now

        self._positive_scores.append(
            score
        )

        # --------------------------------------------------------------
        # REQUIRED = 2
        # --------------------------------------------------------------

        if (
            self._consecutive_positive
            < self.REQUIRED_CONSECUTIVE_DETECTIONS
        ):

            return

        # --------------------------------------------------------------
        # FINAL CONFIRMATION
        # --------------------------------------------------------------

        callback = None

        with self._state_lock:

            if (
                not self._running
                or not self._armed
            ):

                return

            if (
                now
                - self._last_detection_time
                < self.DETECTION_COOLDOWN_SECONDS
            ):

                return

            self._armed = False

            self._waiting_for_release = True

            self._last_detection_time = now

            callback = self.on_detected

        confirmation_peak = max(
            self._positive_scores,
            default=score,
        )

        self._reset_confirmation()

        # Clear openWakeWord streaming state.
        self._reset_model_state()

        print()
        print(
            "=" * 70
        )
        print(
            "⚡ DHEEPTHI DETECTED"
        )
        print(
            "=" * 70
        )
        print(
            "Wake Word : dheepthi"
        )
        print(
            "Detection : confirmed"
        )
        print(
            "Frames    : 2 consecutive"
        )
        print(
            f"Peak      : "
            f"{confirmation_peak:.6f}"
        )
        print(
            "=" * 70
        )

        if callback is not None:

            try:

                callback(
                    self.WAKE_WORD
                )

            except Exception as error:

                print(
                    f"⚠️ Wake callback error: "
                    f"{error}"
                )

    # ==================================================================
    # MICROPHONE CALLBACK
    # ==================================================================

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ) -> None:

        self._ensure_locks()

        with self._state_lock:

            if (
                not self._running
                or self._closed
            ):

                return

        # --------------------------------------------------------------
        # COPY MICROPHONE DATA
        # --------------------------------------------------------------

        try:

            audio_int16 = np.asarray(
                indata,
                dtype=np.int16,
            )

            if audio_int16.ndim == 2:

                audio_int16 = (
                    audio_int16[:, 0]
                )

            audio_int16 = (
                audio_int16.copy()
            )

        except Exception as error:

            with self._audio_lock:

                self._inference_errors += 1

            print(
                f"\n⚠️ Audio processing error: "
                f"{error}"
            )

            return

        if audio_int16.size == 0:
            return

        # --------------------------------------------------------------
        # AUDIO LEVEL
        # --------------------------------------------------------------

        level = (
            self._calculate_audio_level(
                audio_int16
            )
        )

        audio_float = (
            audio_int16.astype(
                np.float32
            )
            / 32768.0
        )

        rms = (
            self._calculate_rms(
                audio_float
            )
        )

        with self._audio_lock:

            self._audio_level = level

            self._audio_blocks_received += 1

        # --------------------------------------------------------------
        # NOISE CALIBRATION
        # --------------------------------------------------------------

        self._update_noise_floor(
            level
        )

        # --------------------------------------------------------------
        # UI LEVEL CALLBACK
        # --------------------------------------------------------------

        callback = self.level_callback

        if callback is not None:

            try:

                callback(level)

            except Exception:
                pass

        # --------------------------------------------------------------
        # HARD LOCAL AUDIO GATE
        # --------------------------------------------------------------

        active = self._audio_is_active(
            level,
            rms,
        )

        if active:

            with self._state_lock:

                self._last_active_time = (
                    time.monotonic()
                )

        else:

            with self._audio_lock:

                self._wake_score = 0.0
                self._speech_ratio = 0.0
                self._speech_detected = False

            self._reset_confirmation()

            self._try_auto_release(
                0.0
            )

            return

        # --------------------------------------------------------------
        # HUMAN SPEECH GATE
        # --------------------------------------------------------------
        #
        # IMPORTANT:
        #
        # This gate only decides whether wake-word inference should run.
        # It does not alter the PCM supplied to openWakeWord/TFLite.
        # Therefore the existing production model path remains intact.

        speech_active, speech_ratio = (
            self._detect_human_speech(
                audio_int16
            )
        )

        with self._audio_lock:

            self._speech_ratio = float(
                speech_ratio
            )

            self._speech_detected = bool(
                speech_active
            )

        if not speech_active:

            with self._audio_lock:

                self._wake_score = 0.0

            self._reset_confirmation()

            self._try_auto_release(
                0.0
            )

            return

        # --------------------------------------------------------------
        # MODEL CHECK
        # --------------------------------------------------------------

        with self._model_lock:

            model = self._model

        if model is None:
            return

        # --------------------------------------------------------------
        # INFERENCE
        # --------------------------------------------------------------

        try:

            score = self._infer(
                audio_int16
            )

            # ----------------------------------------------------------
            # IMPORTANT:
            #
            # None means the feature buffer is still warming up.
            #
            # This is NOT an inference error.
            # ----------------------------------------------------------

            if score is None:

                return

            with self._audio_lock:

                self._inference_count += 1

        except Exception as error:

            with self._audio_lock:

                self._inference_errors += 1

            print(
                f"\n⚠️ openWakeWord "
                f"inference error: "
                f"{error}"
            )

            return

        # --------------------------------------------------------------
        # SCORE
        # --------------------------------------------------------------

        self._update_wake_score(
            score
        )

        # --------------------------------------------------------------
        # DETECTION
        # --------------------------------------------------------------

        self._check_detection(
            score,
            audio_active=active,
        )

    # ==================================================================
    # START
    # ==================================================================

    def start(self) -> bool:
        """
        Start microphone capture and wake-word detection.
        """

        self._ensure_locks()

        with self._state_lock:

            if self._closed:

                print(
                    "❌ Cannot start "
                    "closed detector."
                )

                return False

            if self._running:
                return True

        # --------------------------------------------------------------
        # MODEL
        # --------------------------------------------------------------

        if (
            not self.is_model_loaded()
            and not self.load_model()
        ):

            return False

        # --------------------------------------------------------------
        # CLEAN MODEL STATE
        # --------------------------------------------------------------

        self._reset_model_state()

        # --------------------------------------------------------------
        # STATE RESET
        # --------------------------------------------------------------

        with self._state_lock:

            self._running = True

            self._armed = True

            self._waiting_for_release = False

            self._last_detection_time = 0.0

            self._last_positive_time = 0.0

            self._last_active_time = 0.0

            self._noise_calibration_remaining = (
                self.NOISE_CALIBRATION_BLOCKS
            )

            self._noise_floor = 0.0

            self._noise_samples = []

        self._reset_confirmation()

        # --------------------------------------------------------------
        # DIAGNOSTICS RESET
        # --------------------------------------------------------------

        with self._audio_lock:

            self._audio_level = 0.0

            self._wake_score = 0.0

            self._peak_wake_score = 0.0

            self._audio_blocks_received = 0

            self._inference_count = 0

            self._inference_errors = 0

            self._skipped_inference_frames = 0

            self._last_feature_energy = 0.0

            self._available_feature_frames = 0

            self._speech_ratio = 0.0

            self._speech_detected = False

        # --------------------------------------------------------------
        # MICROPHONE
        # --------------------------------------------------------------

        try:

            self._stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="int16",
                blocksize=self.BLOCK_SIZE,
                callback=self._audio_callback,
                device=None,
                latency="low",
            )

            self._stream.start()

        except Exception as error:

            print(
                f"❌ Microphone stream failed: "
                f"{error}"
            )

            with self._state_lock:

                self._running = False

                self._armed = False

            stream = self._stream

            self._stream = None

            if stream is not None:

                try:
                    stream.stop()

                except Exception:
                    pass

                try:
                    stream.close()

                except Exception:
                    pass

            return False

        # --------------------------------------------------------------
        # START MESSAGE
        # --------------------------------------------------------------

        print(
            "🎤 DHEEPTHI wake listener started."
        )

        print(
            f"🛡️ Audio gate active | "
            f"VAD={self.vad_threshold:.4f} | "
            f"Noise margin={self.NOISE_MARGIN:.4f} | "
            f"Threshold={self.threshold:.4f} | "
            f"Consecutive="
            f"{self.REQUIRED_CONSECUTIVE_DETECTIONS}"
        )

        print(
            f"🧠 openWakeWord VAD active | "
            f"threshold="
            f"{self.OPENWAKEWORD_VAD_THRESHOLD:.2f}"
        )

        if self._speech_vad_available:
            print(
                f"🗣️ Human speech gate active | "
                f"WebRTC mode={self.SPEECH_VAD_MODE} | "
                f"frame={self.SPEECH_VAD_FRAME_MS}ms | "
                f"ratio>={self.SPEECH_VAD_MIN_RATIO:.2f}"
            )
        else:
            print(
                "⚠️ Human speech gate unavailable | "
                "using existing audio/openWakeWord gates"
            )

        print(
            f"🧩 Model input shape: "
            f"{self._model_input_shape}"
        )

        print(
            f"🧩 Required feature frames: "
            f"{self._model_input_frames}"
        )

        print(
            "🎧 Calibrating ambient noise..."
        )

        print(
            "⏳ Warming up wake-word feature buffer..."
        )

        return True

    # ==================================================================
    # RE-ARM
    # ==================================================================

    def rearm(self) -> bool:
        """
        Manually re-arm the detector.
        """

        self._ensure_locks()

        with self._state_lock:

            if (
                self._closed
                or not self._running
            ):

                return False

            self._armed = True

            self._waiting_for_release = False

            self._last_detection_time = 0.0

            self._last_active_time = (
                time.monotonic()
            )

        self._reset_confirmation()

        self._reset_model_state()

        with self._audio_lock:

            self._wake_score = 0.0

        return True

    # ==================================================================
    # STOP
    # ==================================================================

    def stop(self) -> bool:
        """
        Stop microphone capture and detection.
        """

        self._ensure_locks()

        with self._state_lock:

            if not self._running:
                return True

            self._running = False

            self._armed = False

            self._waiting_for_release = False

        self._reset_confirmation()

        stream = self._stream

        self._stream = None

        if stream is not None:

            try:
                stream.stop()

            except Exception:
                pass

            try:
                stream.close()

            except Exception:
                pass

        return True

    # ==================================================================
    # CLOSE
    # ==================================================================

    def close(self) -> bool:
        """
        Completely release microphone and model resources.
        """

        self._ensure_locks()

        with self._state_lock:

            if self._closed:
                return True

        self.stop()

        with self._model_lock:

            model = self._model

            self._model = None

            self._model_label = ""

            self._model_loaded = False

            self._model_input_shape = ()

            self._model_output_shape = ()

            self._model_input_frames = 0

            self._model_input_features = 0

            self._model_input_index = None

            self._model_output_index = None

            self._model_layout = "unknown"

        if model is not None:

            try:
                model.reset()

            except Exception:
                pass

        with self._state_lock:

            self._closed = True

            self._armed = False

            self._waiting_for_release = False

        return True

    # ==================================================================
    # RUNNING
    # ==================================================================

    def is_running(self) -> bool:

        self._ensure_locks()

        with self._state_lock:

            if not self._running:
                return False

        stream = self._stream

        if stream is None:
            return False

        try:

            return bool(
                stream.active
            )

        except Exception:
            return False

    # ==================================================================
    # AUDIO LEVEL
    # ==================================================================

    def get_audio_level(self) -> float:

        self._ensure_locks()

        with self._audio_lock:

            return float(
                self._audio_level
            )

    # ==================================================================
    # WAKE SCORE
    # ==================================================================

    def get_wake_score(self) -> float:

        self._ensure_locks()

        with self._audio_lock:

            return float(
                self._wake_score
            )

    # ==================================================================
    # PEAK SCORE
    # ==================================================================

    def get_peak_wake_score(self) -> float:

        self._ensure_locks()

        with self._audio_lock:

            return float(
                self._peak_wake_score
            )

    # ==================================================================
    # DIAGNOSTICS
    # ==================================================================

    def get_diagnostics(self) -> dict:

        self._ensure_locks()

        with self._audio_lock:

            audio_level = (
                self._audio_level
            )

            wake_score = (
                self._wake_score
            )

            peak_score = (
                self._peak_wake_score
            )

            received = (
                self._audio_blocks_received
            )

            inference = (
                self._inference_count
            )

            errors = (
                self._inference_errors
            )

            skipped = (
                self._skipped_inference_frames
            )

            feature_energy = (
                self._last_feature_energy
            )

            available_features = (
                self._available_feature_frames
            )

        with self._state_lock:

            running = self._running

            armed = self._armed

            waiting_for_release = (
                self._waiting_for_release
            )

            noise_floor = (
                self._noise_floor
            )

            calibration_remaining = (
                self._noise_calibration_remaining
            )

            consecutive = (
                self._consecutive_positive
            )

        with self._model_lock:

            model_loaded = (
                self._model_loaded
            )

            model_label = (
                self._model_label
            )

            model_input_shape = (
                self._model_input_shape
            )

            model_output_shape = (
                self._model_output_shape
            )

            model_input_frames = (
                self._model_input_frames
            )

            model_input_features = (
                self._model_input_features
            )

            model_layout = (
                self._model_layout
            )

        stream = self._stream

        try:

            microphone_active = bool(
                stream is not None
                and stream.active
            )

        except Exception:

            microphone_active = False

        return {
            "wake_word": (
                self.WAKE_WORD
            ),

            "model_label": (
                model_label
            ),

            "model_loaded": (
                model_loaded
            ),

            "model_type": (
                "TFLITE FP32 "
                "via openWakeWord"
            ),

            "model_path": str(
                self.model_path
            ),

            "inference_framework": (
                "tensorflow-lite"
            ),

            "running": (
                running
            ),

            "armed": (
                armed
            ),

            "waiting_for_release": (
                waiting_for_release
            ),

            "microphone": (
                microphone_active
            ),

            "audio_level": (
                audio_level
            ),

            "wake_score": (
                wake_score
            ),

            "peak_wake_score": (
                peak_score
            ),

            "threshold": (
                self.threshold
            ),

            "release_threshold": (
                self.RELEASE_THRESHOLD
            ),

            "vad_threshold": (
                self.vad_threshold
            ),

            "openwakeword_vad_threshold": (
                self.OPENWAKEWORD_VAD_THRESHOLD
            ),

            "speech_vad_available": (
                self._speech_vad_available
            ),

            "speech_vad_mode": (
                self.SPEECH_VAD_MODE
            ),

            "speech_vad_frame_ms": (
                self.SPEECH_VAD_FRAME_MS
            ),

            "speech_vad_min_ratio": (
                self.SPEECH_VAD_MIN_RATIO
            ),

            "speech_ratio": (
                self._speech_ratio
            ),

            "speech_detected": (
                self._speech_detected
            ),

            "min_audio_level": (
                self.MIN_AUDIO_LEVEL
            ),

            "noise_margin": (
                self.NOISE_MARGIN
            ),

            "noise_floor": (
                noise_floor
            ),

            "noise_calibration_remaining": (
                calibration_remaining
            ),

            "audio_blocks_received": (
                received
            ),

            "inference_count": (
                inference
            ),

            "inference_errors": (
                errors
            ),

            "skipped_inference_frames": (
                skipped
            ),

            "available_feature_frames": (
                available_features
            ),

            "required_feature_frames": (
                model_input_frames
            ),

            "feature_energy": (
                feature_energy
            ),

            "feature_shape": (
                "openWakeWord internal"
            ),

            "model_input_shape": (
                model_input_shape
            ),

            "model_output_shape": (
                model_output_shape
            ),

            "model_input_frames": (
                model_input_frames
            ),

            "model_input_features": (
                model_input_features
            ),

            "model_layout": (
                model_layout
            ),

            "required_consecutive": (
                self.REQUIRED_CONSECUTIVE_DETECTIONS
            ),

            "consecutive_positive": (
                consecutive
            ),

            "max_confirmation_gap_seconds": (
                self.MAX_CONFIRMATION_GAP_SECONDS
            ),
        }