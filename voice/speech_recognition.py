from __future__ import annotations

import os
import re
import threading
import time
from difflib import SequenceMatcher

import numpy as np
import sounddevice as sd
import speech_recognition as sr
from faster_whisper import WhisperModel


class SpeechRecognizer:
    """
    ASTRA-AI Speech Recognition

    WAKE WORD:
        Microphone
            ↓
        Local Faster-Whisper
            ↓
        DHEEPTHI detected
            ↓
        Wake audio discarded

    COMMAND:
        Fresh microphone recording
            ↓
        Existing command-processing pipeline

    Vosk is completely removed.
    Groq is NOT used for wake detection.
    """

    # ==================================================
    # FASTER-WHISPER WAKE CONFIGURATION
    # ==================================================

    WHISPER_MODEL = os.getenv(
        "ASTRA_WAKE_MODEL",
        "small",
    ).strip()

    WHISPER_DEVICE = os.getenv(
        "ASTRA_WAKE_DEVICE",
        "cpu",
    ).strip()

    WHISPER_COMPUTE_TYPE = os.getenv(
        "ASTRA_WAKE_COMPUTE_TYPE",
        "int8",
    ).strip()

    WHISPER_LANGUAGE = os.getenv(
        "ASTRA_WAKE_LANGUAGE",
        "en",
    ).strip()

    WAKE_SAMPLE_RATE = 16000
    WAKE_CHANNELS = 1
    WAKE_WINDOW_SECONDS = 3.0
    WAKE_INTERVAL_SECONDS = 0.20

    # ==================================================
    # NORMAL COMMAND SETTINGS
    # ==================================================

    COMMAND_TIMEOUT = 5
    COMMAND_PHRASE_TIME_LIMIT = int(
        os.getenv("DHEEPTHI_COMMAND_PHRASE_TIME_LIMIT", "12")
    )
    COMMAND_PAUSE_THRESHOLD = float(
        os.getenv("DHEEPTHI_COMMAND_PAUSE_THRESHOLD", "0.55")
    )
    COMMAND_NON_SPEAKING_DURATION = float(
        os.getenv("DHEEPTHI_COMMAND_NON_SPEAKING_DURATION", "0.30")
    )

    # ==================================================
    # MICROPHONE SETTINGS
    # ==================================================

    AMBIENT_DURATION = 0.5

    PAUSE_THRESHOLD = 0.8

    PHRASE_THRESHOLD = 0.3

    NON_SPEAKING_DURATION = 0.5

    # ==================================================
    # LIVE AUDIO METER
    # ==================================================

    AUDIO_METER_SAMPLE_RATE = 16000

    AUDIO_METER_CHANNELS = 1

    AUDIO_METER_BLOCKSIZE = 1024

    AUDIO_METER_DTYPE = "float32"

    AUDIO_NOISE_FLOOR = 0.008

    AUDIO_GAIN = 24.0

    AUDIO_SMOOTHING = 0.72

    AUDIO_ATTACK = 0.45

    AUDIO_RELEASE = 0.16

    # ==================================================
    # WAKE MATCHING
    # ==================================================

    WAKE_SINGLE_WORD_THRESHOLD = 0.72

    WAKE_FUZZY_THRESHOLD = 0.70

    # ==================================================
    # INITIALIZATION
    # ==================================================

    def __init__(self):

        # ==================================================
        # SPEECH RECOGNITION
        # ==================================================

        self.recognizer = sr.Recognizer()

        self.recognizer.dynamic_energy_threshold = True

        self.recognizer.energy_threshold = 180

        self.recognizer.dynamic_energy_adjustment_damping = 0.12

        self.recognizer.dynamic_energy_ratio = 1.5

        self.recognizer.pause_threshold = (
            self.PAUSE_THRESHOLD
        )

        self.recognizer.phrase_threshold = (
            self.PHRASE_THRESHOLD
        )

        self.recognizer.non_speaking_duration = (
            self.NON_SPEAKING_DURATION
        )

        self.recognizer.operation_timeout = None

        self.microphone = sr.Microphone()

        # ==================================================
        # FASTER-WHISPER
        # ==================================================

        self.whisper_model = None

        self._model_loaded = False

        self._model_lock = threading.RLock()

        # ==================================================
        # LIFECYCLE
        # ==================================================

        self._closing = False

        self._stop_requested = False

        self.wake_word_active = False

        # ==================================================
        # MANUAL LISTENING
        # ==================================================

        self._manual_listening = False

        self._noise_calibrated = False

        self.last_audio = None

        # ==================================================
        # LIVE AUDIO METER
        # ==================================================

        self.audio_level = 0.0

        self.audio_stream = None

        self.level_callback = None

        self._audio_meter_running = False

        self._audio_meter_lock = threading.RLock()

        # ==================================================
        # WAKE LOGGING
        # ==================================================

        self._last_wake_text = ""

        self._last_wake_log_time = 0.0

        # ==================================================
        # DHEEPTHI VARIATIONS
        # ==================================================

        self.wake_words = (
            "dheepthi",
            "deepthi",
            "deepti",
            "deepthee",
            "deepthy",
            "deeptee",
            "dhepti",
            "dhepthi",
            "dheethi",
            "dhethi",

            "deep the",
            "deep thee",
            "deep tea",
            "deep thi",
            "deep tee",
            "deep ti",
            "deep th",
            "deep t",

            "dheep the",
            "dheep thee",
            "dheep tea",
            "dheep thi",
            "dheep tee",
            "dheep ti",
            "dheep th",
            "dheep t",

            "beep the",
            "beep thi",
            "beep tea",

            "weep the",
            "weep thi",
            "weep tea",

            "hey dheepthi",
            "hey deepthi",
            "hey deepti",

            "hello dheepthi",
            "hello deepthi",
            "hello deepti",

            "hi dheepthi",
            "hi deepthi",
            "hi deepti",

            "okay dheepthi",
            "okay deepthi",
            "okay deepti",

            "ok dheepthi",
            "ok deepthi",
            "ok deepti",
        )

        self.wake_phrase_variations = (
            "deeply",
            "deep please",
            "deep t",
            "deep ti",
            "deep thi",
            "deep thee",
            "deep tee",
            "deep th",
            "deep d",

            "deep deep",
            "deepdeep",

            "deep deep wake up",
            "deepdeep wake up",

            "deep deep make up",
            "deepdeep make up",
        )

        self.wake_reject_phrases = (
            "deep sleep",
            "sleep deeply",
            "deep thought",
            "deep thoughts",
            "deep water",
            "deep voice",
            "deep breath",
            "deep breathing",
        )

        self._wake_candidates = (
            "dheepthi",
            "deepthi",
            "deepti",
            "deepthee",
            "deepthy",
            "deeptee",
            "dhepti",
            "dhepthi",
            "dheethi",
            "dhethi",
        )

        # ==================================================
        # STARTUP
        # ==================================================

        print(
            "\n========== ASTRA WAKE WORD =========="
        )

        print(
            "Wake Word : dheepthi"
        )

        print(
            "Engine : Faster-Whisper"
        )

        print(
            "Mode : LOCAL / OFFLINE"
        )

        print(
            f"Model : {self.WHISPER_MODEL}"
        )

        print(
            f"Device : {self.WHISPER_DEVICE}"
        )

        print(
            f"Compute Type : "
            f"{self.WHISPER_COMPUTE_TYPE}"
        )

        print(
            "Groq : DISABLED FOR WAKE"
        )

        print(
            "Vosk : DISABLED"
        )

        print(
            "Manual Audio Meter : ENABLED"
        )

        print(
            "=====================================\n"
        )

    # ==================================================
    # LOAD FASTER-WHISPER
    # ==================================================

    def load_model(self):

        if self._closing:
            return False

        if (
            self._model_loaded
            and self.whisper_model is not None
        ):
            return True

        with self._model_lock:

            if (
                self._model_loaded
                and self.whisper_model is not None
            ):
                return True

            try:

                print(
                    "\nLoading local "
                    "Faster-Whisper model..."
                )

                print(
                    f"Model : {self.WHISPER_MODEL}"
                )

                print(
                    f"Device : {self.WHISPER_DEVICE}"
                )

                print(
                    f"Compute Type : "
                    f"{self.WHISPER_COMPUTE_TYPE}"
                )

                self.whisper_model = WhisperModel(
                    self.WHISPER_MODEL,
                    device=self.WHISPER_DEVICE,
                    compute_type=self.WHISPER_COMPUTE_TYPE,
                )

                self._model_loaded = True

                print(
                    "Faster-Whisper model "
                    "loaded successfully."
                )

                print(
                    "DHEEPTHI wake detection ready."
                )

                return True

            except Exception as error:

                self.whisper_model = None

                self._model_loaded = False

                print(
                    "Faster-Whisper Model Error : "
                    f"{error}"
                )

                return False

    # ==================================================
    # TEXT NORMALIZATION
    # ==================================================

    @staticmethod
    def normalize_text(text):

        if not text:
            return ""

        text = str(
            text
        ).lower().strip()

        text = re.sub(
            r"[^a-z0-9\s_-]+",
            " ",
            text,
        )

        text = text.replace(
            "_",
            " ",
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    # ==================================================
    # WAKE SIMILARITY
    # ==================================================

    def wake_word_similarity(
        self,
        word,
    ):

        cleaned = re.sub(
            r"[^a-z]+",
            "",
            (word or "").lower(),
        )

        if not cleaned:
            return 0.0

        return max(
            SequenceMatcher(
                None,
                cleaned,
                candidate,
            ).ratio()
            for candidate
            in self._wake_candidates
        )

    # ==================================================
    # WAKE-LIKE TOKEN
    # ==================================================

    def _is_wake_like_token(
        self,
        token,
    ):

        token = re.sub(
            r"[^a-z]+",
            "",
            (token or "").lower(),
        )

        if len(token) < 5:
            return False

        return (
            self.wake_word_similarity(
                token
            )
            >= self.WAKE_SINGLE_WORD_THRESHOLD
        )

    # ==================================================
    # DEEP FAMILY
    # ==================================================

    def _contains_deep_family(
        self,
        words,
    ):

        if not words:
            return False

        for index, word in enumerate(
            words
        ):

            if word not in {
                "deep",
                "dheep",
            }:
                continue

            following = words[
                index + 1:
            ]

            if not following:
                continue

            if following[0] in {
                "the",
                "thee",
                "tea",
                "thi",
                "tee",
                "ti",
                "t",
                "th",
                "d",
                "please",
            }:

                return True

            if (
                "wake" in following
                and "up" in following
            ):

                return True

            if (
                "make" in following
                and "up" in following
            ):

                return True

        return False

    # ==================================================
    # CONTAINS WAKE WORD
    # ==================================================

    def contains_wake_word(
        self,
        text,
    ):

        normalized = self.normalize_text(
            text
        )

        if not normalized:
            return False

        if (
            normalized
            in self.wake_reject_phrases
        ):
            return False

        for rejected in (
            self.wake_reject_phrases
        ):

            if re.search(
                rf"\b{re.escape(rejected)}\b",
                normalized,
            ):

                return False

        words = normalized.split()

        for wake_word in (
            self.wake_words
        ):

            if re.search(
                rf"(?<!\w)"
                rf"{re.escape(wake_word)}"
                rf"(?!\w)",
                normalized,
            ):

                return True

        if (
            normalized
            in self.wake_phrase_variations
        ):

            return True

        if self._contains_deep_family(
            words
        ):

            return True

        for word in words:

            if self._is_wake_like_token(
                word
            ):

                return True

        joined = "".join(
            words
        )

        for candidate in (
            "deepdeep",
            "deepdee",
            "deepthi",
            "deepthee",
            "dheepthi",
            "dhepthi",
        ):

            if candidate in joined:
                return True

        if len(words) <= 4:

            for candidate in (
                self._wake_candidates
            ):

                score = SequenceMatcher(
                    None,
                    joined,
                    candidate,
                ).ratio()

                if (
                    score
                    >= self.WAKE_FUZZY_THRESHOLD
                ):

                    return True

        return False

    # ==================================================
    # AUDIO LEVEL
    # ==================================================

    def _emit_audio_level(
        self,
        level,
    ):

        level = max(
            0.0,
            min(
                float(level),
                1.0,
            ),
        )

        self.audio_level = level

        callback = self.level_callback

        if callback is not None:

            try:

                callback(level)

            except Exception:
                pass

    # ==================================================
    # AUDIO CALLBACK
    # ==================================================

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):

        if (
            self._closing
            or not self._audio_meter_running
        ):
            return

        try:

            if (
                indata is None
                or len(indata) == 0
            ):
                return

            samples = np.asarray(
                indata,
                dtype=np.float32,
            )

            if samples.size == 0:
                return

            if samples.ndim > 1:

                samples = np.mean(
                    samples,
                    axis=1,
                )

            rms = float(
                np.sqrt(
                    np.mean(
                        np.square(
                            samples
                        )
                    )
                )
            )

            if (
                rms
                <= self.AUDIO_NOISE_FLOOR
            ):

                target = 0.0

            else:

                target = min(
                    (
                        rms
                        - self.AUDIO_NOISE_FLOOR
                    )
                    * self.AUDIO_GAIN,
                    1.0,
                )

            previous = float(
                self.audio_level
            )

            if target > previous:

                alpha = self.AUDIO_ATTACK

            else:

                alpha = self.AUDIO_RELEASE

            level = (
                previous
                * (1.0 - alpha)
                + target
                * alpha
            )

            level = (
                level
                * (
                    1.0
                    - self.AUDIO_SMOOTHING
                )
                + previous
                * self.AUDIO_SMOOTHING
            )

            self._emit_audio_level(
                level
            )

        except Exception as error:

            print(
                "Audio Meter Callback Error : "
                f"{error}"
            )

    # ==================================================
    # START AUDIO METER
    # ==================================================

    def start_audio_meter(
        self,
    ):

        if self._closing:
            return False

        with self._audio_meter_lock:

            if self._audio_meter_running:
                return True

            self.audio_level = 0.0

            self._audio_meter_running = True

            self._emit_audio_level(
                0.0
            )

            try:

                self.audio_stream = (
                    sd.InputStream(
                        device=None,
                        channels=(
                            self.AUDIO_METER_CHANNELS
                        ),
                        samplerate=(
                            self.AUDIO_METER_SAMPLE_RATE
                        ),
                        blocksize=(
                            self.AUDIO_METER_BLOCKSIZE
                        ),
                        dtype=(
                            self.AUDIO_METER_DTYPE
                        ),
                        latency="low",
                        callback=(
                            self._audio_callback
                        ),
                    )
                )

                self.audio_stream.start()

                print(
                    "🎚️ Live microphone "
                    "audio meter started."
                )

                return True

            except Exception as error:

                print(
                    "Audio Meter Error : "
                    f"{error}"
                )

                self._audio_meter_running = False

                stream = self.audio_stream

                self.audio_stream = None

                if stream is not None:

                    try:
                        stream.stop()
                    except Exception:
                        pass

                    try:
                        stream.close()
                    except Exception:
                        pass

                self._emit_audio_level(
                    0.0
                )

                return False

    # ==================================================
    # STOP AUDIO METER
    # ==================================================

    def stop_audio_meter(
        self,
    ):

        with self._audio_meter_lock:

            self._audio_meter_running = False

            stream = self.audio_stream

            self.audio_stream = None

            if stream is not None:

                try:
                    stream.stop()
                except Exception:
                    pass

                try:
                    stream.close()
                except Exception:
                    pass

            self.audio_level = 0.0

            self._emit_audio_level(
                0.0
            )

        print(
            "🎚️ Live microphone "
            "audio meter stopped."
        )

    # ==================================================
    # MICROPHONE CALIBRATION
    # ==================================================

    def calibrate_microphone(
        self,
        source,
    ):

        if (
            self._noise_calibrated
            or self._closing
        ):
            return True

        try:

            print(
                "🎧 Calibrating microphone..."
            )

            self.recognizer.adjust_for_ambient_noise(
                source,
                duration=(
                    self.AMBIENT_DURATION
                ),
            )

            print(
                "🎧 Microphone calibrated."
            )

            print(
                "Energy Threshold : "
                f"{int(self.recognizer.energy_threshold)}"
            )

            self._noise_calibrated = True

            return True

        except Exception as error:

            print(
                "Microphone Calibration Error : "
                f"{error}"
            )

            return False

    # ==================================================
    # FASTER-WHISPER WAKE RECORDING
    # ==================================================

    def _record_wake_audio(
        self,
    ):

        frames = int(
            self.WAKE_SAMPLE_RATE
            * self.WAKE_WINDOW_SECONDS
        )

        try:

            audio = sd.rec(
                frames,
                samplerate=(
                    self.WAKE_SAMPLE_RATE
                ),
                channels=self.WAKE_CHANNELS,
                dtype="float32",
            )

            sd.wait()

            return np.asarray(
                audio,
                dtype=np.float32,
            ).reshape(-1)

        except Exception as error:

            print(
                "Wake microphone capture error : "
                f"{error}"
            )

            return None

    # ==================================================
    # FASTER-WHISPER TRANSCRIPTION
    # ==================================================

    def _transcribe_wake_audio(
        self,
        audio,
    ):

        if (
            audio is None
            or len(audio) == 0
        ):
            return ""

        if self.whisper_model is None:
            return ""

        try:

            segments, _ = (
                self.whisper_model.transcribe(
                    audio,
                    language=(
                        self.WHISPER_LANGUAGE
                    ),
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    vad_filter=True,
                    condition_on_previous_text=False,
                    without_timestamps=True,
                )
            )

            return self.normalize_text(
                " ".join(
                    segment.text.strip()
                    for segment in segments
                    if segment.text
                )
            )

        except Exception as error:

            print(
                "Faster-Whisper wake "
                "transcription error : "
                f"{error}"
            )

            return ""

    # ==================================================
    # WAKE LOG
    # ==================================================

    def _print_wake_text(
        self,
        text,
    ):

        text = self.normalize_text(
            text
        )

        if not text:
            return

        now = time.monotonic()

        if (
            text
            == self._last_wake_text
        ):

            if (
                now
                - self._last_wake_log_time
                < 0.5
            ):

                return

        self._last_wake_text = text

        self._last_wake_log_time = now

        print(
            f"Wake STT : {text}"
        )

    # ==================================================
    # FASTER-WHISPER WAKE DETECTION
    # ==================================================

    def listen_for_wake_word(
        self,
        retries=1,
    ):
        """
        LOCAL Faster-Whisper wake detection.

        Returns:
            True  -> DHEEPTHI detected
            False -> stopped / failed

        Wake audio is NOT returned as command audio.
        """

        if self._closing:
            return False

        if not self.load_model():
            return False

        self.wake_word_active = True

        self._stop_requested = False

        self._last_wake_text = ""

        self._last_wake_log_time = 0.0

        print(
            "\n========== "
            "DHEEPTHI / FASTER-WHISPER "
            "=========="
        )

        print(
            "DHEEPTHI standby: "
            "LOCAL Faster-Whisper wake detection."
        )

        print(
            "Groq wake detection: DISABLED"
        )

        print(
            "\n========== "
            "DHEEPTHI STANDBY "
            "=========="
        )

        print(
            "Listening locally with "
            "Faster-Whisper..."
        )

        print(
            "Say: DHEEPTHI"
        )

        print(
            "Wake Engine : Faster-Whisper"
        )

        print(
            "Wake Mode : LOCAL / OFFLINE"
        )

        print(
            f"Model : {self.WHISPER_MODEL}"
        )

        print(
            "Groq : COMMAND STT ONLY"
        )

        print(
            "Vosk : DISABLED"
        )

        print(
            "=======================================\n"
        )

        try:

            while (
                self.wake_word_active
                and not self._closing
                and not self._stop_requested
            ):

                audio = (
                    self._record_wake_audio()
                )

                if audio is None:

                    time.sleep(
                        self.WAKE_INTERVAL_SECONDS
                    )

                    continue

                text = (
                    self._transcribe_wake_audio(
                        audio
                    )
                )

                if text:

                    self._print_wake_text(
                        text
                    )

                    if self.contains_wake_word(
                        text
                    ):

                        print(
                            "\n⚡ DHEEPTHI "
                            "WAKE WORD DETECTED"
                        )

                        print(
                            f"Wake Text : "
                            f"{text}"
                        )

                        return True

                time.sleep(
                    self.WAKE_INTERVAL_SECONDS
                )

            return False

        except KeyboardInterrupt:

            print(
                "\nDHEEPTHI wake listener "
                "interrupted."
            )

            return False

        except Exception as error:

            print(
                "DHEEPTHI wake listener error : "
                f"{error}"
            )

            return False

        finally:

            self.wake_word_active = False

            print(
                "DHEEPTHI wake listener stopped."
            )

    # ==================================================
    # FRESH COMMAND AFTER WAKE
    # ==================================================

    def listen_after_wake_word(
        self,
        timeout=5,
        phrase_time_limit=20,
    ):
        """
        Wake audio is discarded.

        A completely fresh microphone capture
        starts here.

        main_window.py can speak:

            Listening

        before calling this method.
        """

        if self._closing:
            return None

        self._stop_requested = False

        print(
            "\n⚡ DHEEPTHI activated."
        )

        print(
            "🎤 Wake audio discarded."
        )

        print(
            "🎤 Starting a NEW "
            "command recording..."
        )

        return self.listen(
            timeout=timeout,
            phrase_time_limit=(
                phrase_time_limit
            ),
            calibrate=False,
        )

    # ==================================================
    # NORMAL COMMAND LISTENING
    # ==================================================

    def listen(
        self,
        timeout=None,
        phrase_time_limit=None,
        calibrate=True,
    ):
        """
        Fresh microphone command capture.

        Existing command pipeline can use
        the returned text.
        """

        if self._closing:
            return None

        self._manual_listening = True

        meter_started = False

        try:

            meter_started = (
                self.start_audio_meter()
            )

            if not meter_started:

                print(
                    "Warning: live audio meter "
                    "could not be started."
                )

            with self.microphone as source:

                print(
                    "🎤 Listening..."
                )

                if calibrate:

                    self.calibrate_microphone(
                        source
                    )

                print(
                    "🎙️ Speak your command..."
                )

                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=(
                        phrase_time_limit
                    ),
                )

                self.last_audio = audio

                print(
                    "🎧 Fresh command audio captured."
                )

                try:

                    text = (
                        self.recognizer
                        .recognize_google(
                            audio
                        )
                    )

                except sr.UnknownValueError:

                    print(
                        "No speech detected."
                    )

                    return None

                except sr.RequestError as error:

                    print(
                        "Speech Recognition "
                        "Service Error : "
                        f"{error}"
                    )

                    return None

                print(
                    f"Recognized Text : "
                    f"{text}"
                )

                return text

        except sr.WaitTimeoutError:

            print(
                "Listening timed out."
            )

            return None

        except Exception as error:

            print(
                "Speech Recognition Error : "
                f"{error}"
            )

            return None

        finally:

            self._manual_listening = False

            if meter_started:

                self.stop_audio_meter()

            else:

                self._emit_audio_level(
                    0.0
                )

    # ==================================================
    # FULL WAKE -> COMMAND FLOW
    # ==================================================

    def listen_for_command(
        self,
    ):
        """
        Compatibility method.

        Flow:

            Faster-Whisper
                ↓
            DHEEPTHI detected
                ↓
            main_window TTS "Listening"
                ↓
            Fresh command capture

        TTS is intentionally handled by main_window.py.
        """

        if self._closing:
            return None

        detected = (
            self.listen_for_wake_word()
        )

        if not detected:
            return None

        return (
            self.listen_after_wake_word(
                timeout=self.COMMAND_TIMEOUT,
                phrase_time_limit=(
                    self.COMMAND_PHRASE_TIME_LIMIT
                ),
            )
        )

    # ==================================================
    # REMOVE WAKE WORD
    # ==================================================

    def remove_wake_word(
        self,
        text,
    ):

        if not text:
            return ""

        original = (
            " ".join(
                str(text).strip().split()
            )
        )

        normalized = self.normalize_text(
            original
        )

        prefixes = (
            "hey dheepthi",
            "hey deepthi",
            "hey deepti",

            "hello dheepthi",
            "hello deepthi",
            "hello deepti",

            "hi dheepthi",
            "hi deepthi",
            "hi deepti",

            "okay dheepthi",
            "okay deepthi",
            "okay deepti",

            "ok dheepthi",
            "ok deepthi",
            "ok deepti",

            "deep deep wake up",
            "deepdeep wake up",

            "deep deep make up",
            "deepdeep make up",

            "deep please",

            "deep the",
            "deep thee",
            "deep tea",
            "deep thi",
            "deep tee",
            "deep ti",
            "deep t",
            "deep th",
            "deep d",

            "dheep the",
            "dheep thee",
            "dheep tea",
            "dheep thi",
            "dheep tee",
            "dheep ti",
            "dheep th",
            "dheep t",

            "beep the",
            "beep thi",
            "beep tea",

            "weep the",
            "weep thi",
            "weep tea",
        )

        for prefix in sorted(
            prefixes,
            key=len,
            reverse=True,
        ):

            if normalized.startswith(
                prefix
            ):

                words = original.split()

                return " ".join(
                    words[
                        len(prefix.split()):
                    ]
                ).strip()

        words = original.split()

        if not words:
            return ""

        first = re.sub(
            r"^[^\w-]+|[^\w-]+$",
            "",
            words[0].lower(),
        )

        singles = {
            "dheepthi",
            "deepthi",
            "deepti",
            "deepthee",
            "deepthy",
            "deeptee",
            "dhepti",
            "dhepthi",
            "dheethi",
            "dhethi",
            "deeply",
        }

        if (
            first in singles
            or self._is_wake_like_token(
                first
            )
        ):

            return " ".join(
                words[1:]
            ).strip()

        if len(words) >= 2:

            second = (
                words[1]
                .lower()
                .strip(".,?!")
            )

            if (
                first
                in {
                    "deep",
                    "dheep",
                }
                and second
                in {
                    "the",
                    "thee",
                    "tea",
                    "thi",
                    "tee",
                    "ti",
                    "th",
                    "t",
                    "d",
                }
            ):

                return " ".join(
                    words[2:]
                ).strip()

        return original

    # ==================================================
    # STOP WAKE WORD
    # ==================================================

    def stop_wake_word(
        self,
    ):

        self.wake_word_active = False

        self._stop_requested = True

        print(
            "DHEEPTHI Wake Word Mode stopped."
        )

    # ==================================================
    # PREPARE WAKE WORD
    # ==================================================

    def prepare_for_wake_word(
        self,
    ):

        if self._closing:
            return False

        if not self.load_model():
            return False

        self._stop_requested = False

        self.wake_word_active = True

        print(
            "DHEEPTHI Faster-Whisper "
            "local wake listener prepared."
        )

        return True

    # ==================================================
    # CONFIRMATION
    # ==================================================

    def listen_confirmation(
        self,
        retries=3,
    ):

        normalization = {
            "yep": "yes",
            "yup": "yes",
            "yeah": "yes",
            "yess": "yes",
            "yea": "yes",
            "you": "yes",
            "ok": "yes",
            "okay": "yes",
            "confirm": "yes",
            "sure": "yes",
            "correct": "yes",

            "nope": "no",
            "nah": "no",

            "cancel it": "cancel",
            "stop it": "stop",
        }

        for _ in range(
            max(
                1,
                int(retries),
            )
        ):

            text = self.listen(
                timeout=self.COMMAND_TIMEOUT,
                phrase_time_limit=10,
                calibrate=False,
            )

            if text is None:

                print(
                    "\nDidn't hear anything."
                )

                continue

            text = self.normalize_text(
                text
            )

            for old, new in (
                normalization.items()
            ):

                text = text.replace(
                    old,
                    new,
                )

            if "yes" in text:
                return "yes"

            if "no" in text:
                return "no"

            if "cancel" in text:
                return "cancel"

            if "stop" in text:
                return "stop"

            print(
                "\nPlease say Yes, No or Cancel."
            )

        return None

    # ==================================================
    # STATUS
    # ==================================================

    def is_model_loaded(
        self,
    ):

        return (
            self._model_loaded
            and self.whisper_model is not None
        )

    def is_audio_meter_running(
        self,
    ):

        return bool(
            self._audio_meter_running
        )

    def get_audio_level(
        self,
    ):

        return float(
            self.audio_level
        )

    # ==================================================
    # CALLBACK
    # ==================================================

    def set_level_callback(
        self,
        callback,
    ):

        self.level_callback = callback

    # ==================================================
    # COMMAND-MODE STATUS / STOP
    # ==================================================

    def is_listening(self):
        """Return whether the legacy command STT path is active."""
        return bool(self._manual_listening)

    def cancel_listening(self):
        """Cooperatively cancel command-mode listening and its audio meter."""
        self._stop_requested = True
        self._manual_listening = False

        try:
            self.stop_audio_meter()
        except Exception:
            pass

        self._emit_audio_level(0.0)

    def stop(self):
        """Compatibility stop method for UI shutdown/cancellation."""
        self.cancel_listening()
        self.stop_wake_word()

    # ==================================================
    # CLEANUP
    # ==================================================

    def close(
        self,
    ):

        self._closing = True

        self.wake_word_active = False

        self._stop_requested = True

        self._manual_listening = False

        try:

            self.stop_audio_meter()

        except Exception:
            pass

        self.level_callback = None

        self.microphone = None

        self.recognizer = None

        self.whisper_model = None

        self._model_loaded = False

        print(
            "Speech Recognizer "
            "shutdown completed."
        )


# ======================================================
# DIRECT TEST
# ======================================================

if __name__ == "__main__":

    print(
        "\n=========================================="
    )

    print(
        " ASTRA-AI SPEECH RECOGNITION TEST"
    )

    print(
        "=========================================="
    )

    recognizer = SpeechRecognizer()

    try:

        print(
            "\nTesting Faster-Whisper "
            "wake detection..."
        )

        print(
            "Say DHEEPTHI."
        )

        detected = (
            recognizer.listen_for_wake_word()
        )

        print(
            f"\nWake detected : {detected}"
        )

        if detected:

            print(
                'Next stage: main_window.py '
                'should speak "Listening" and '
                'then start fresh command capture.'
            )

    except KeyboardInterrupt:

        print(
            "\nTest interrupted."
        )

    finally:

        recognizer.close()