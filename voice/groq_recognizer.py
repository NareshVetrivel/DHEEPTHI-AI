"""
Groq Speech Recognition Module
==============================

Online Speech-to-Text using Groq Whisper.

This module is responsible for:
    - Groq STT HTTP transport (direct httpx multipart)
    - Audio-file transcription
    - Audio bytes transcription
    - Command transcription
    - Error handling and transcript cleanup
"""

from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from pathlib import Path

import httpx
from dotenv import load_dotenv


# ======================================================
# Environment Loading
# ======================================================

# ASTRA-AI project root:
#
#     ASTRA-AI/
#         .env
#         voice/
#             groq_recognizer.py
#
# __file__:
#
#     ASTRA-AI/voice/groq_recognizer.py
#
# parents[1]:
#
#     ASTRA-AI/
#
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = PROJECT_ROOT / ".env"

# Load the project-level .env immediately.
#
# This is intentionally done at module import time because
# WhisperRecognizer may create GroqRecognizer during its
# own initialization.
#
# Therefore main_window.py does NOT need to load .env first.
load_dotenv(
    dotenv_path=ENV_FILE,
    override=False,
)


# ======================================================
# Exceptions
# ======================================================


class GroqSTTError(Exception):
    """Base exception for Groq Speech-to-Text failures."""


class GroqSTTRateLimitError(GroqSTTError):
    """Raised when Groq rate limits are reached."""


class GroqSTTAccessError(GroqSTTError):
    """Raised when Groq/Cloudflare blocks the API request."""


class GroqSTTConfigurationError(GroqSTTError):
    """Raised when Groq STT configuration is missing."""


# ======================================================
# Groq Recognizer
# ======================================================


class GroqRecognizer:
    """
    Groq Whisper Speech-to-Text recognizer.

    The recognizer accepts an already-recorded audio file.

    It supports two distinct ASTRA voice stages:

        1. Wake Window
           - recorded audio window
           - Groq transcription
           - DHEEPTHI detection

        2. Fresh Command
           - NEW microphone recording
           - Groq transcription
           - command returned to caller

    The wake recording is NEVER reused as the command
    recording.

    Audio transcription uses direct httpx HTTP transport
    because the Groq SDK audio endpoint was triggering
    Cloudflare HTTP 403 / Error 1010 in this environment.
    """

    # ==================================================
    # Configuration
    # ==================================================

    DEFAULT_MODEL = "whisper-large-v3-turbo"

    MAX_TEXT_LENGTH = 10000

    # ==================================================
    # Groq API
    # ==================================================

    GROQ_BASE_URL = (
        "https://api.groq.com/openai/v1"
    )

    GROQ_TRANSCRIPTION_URL = (
        f"{GROQ_BASE_URL}/audio/transcriptions"
    )

    # ==================================================
    # HTTP User-Agent
    # ==================================================

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    # ==================================================
    # Initialization
    # ==================================================

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:

        # --------------------------------------------------
        # Ensure .env is loaded.
        #
        # This second call is intentional and harmless.
        # It also protects direct construction of this class
        # after environment changes during runtime.
        # --------------------------------------------------

        load_dotenv(
            dotenv_path=ENV_FILE,
            override=False,
        )

        # --------------------------------------------------
        # API Key
        # --------------------------------------------------

        self.api_key = (
            api_key
            or os.getenv(
                "GROQ_API_KEY",
                "",
            ).strip()
        )

        # --------------------------------------------------
        # Model
        # --------------------------------------------------

        self.model = (
            model
            or os.getenv(
                "GROQ_STT_MODEL",
                self.DEFAULT_MODEL,
            ).strip()
            or self.DEFAULT_MODEL
        )

        # --------------------------------------------------
        # Configuration Validation
        # --------------------------------------------------

        if not self.api_key:

            raise GroqSTTConfigurationError(
                "GROQ_API_KEY is not configured. "
                f"Checked environment and .env at: {ENV_FILE}"
            )

        # ==================================================
        # Direct HTTP Client
        # ==================================================

        self.default_headers = {
            "Authorization": (
                f"Bearer {self.api_key}"
            ),
            "User-Agent": (
                self.DEFAULT_USER_AGENT
            ),
            "Accept": "application/json",
        }

        self.http_client = httpx.Client(
            headers=self.default_headers,
            timeout=httpx.Timeout(
                connect=30.0,
                read=60.0,
                write=60.0,
                pool=30.0,
            ),
            follow_redirects=True,
        )

        # --------------------------------------------------
        # Startup Logs
        # --------------------------------------------------

        print(
            f"Groq STT Ready | Model : {self.model}"
        )

        print(
            "Groq STT User-Agent : "
            f"{self.DEFAULT_USER_AGENT}"
        )

        print(
            "Groq STT Transport : Direct HTTP"
        )

        print(
            "Groq STT Environment : "
            f"{ENV_FILE}"
        )

    # ======================================================
    # Audio File Validation
    # ======================================================

    def _validate_audio_file(
        self,
        audio_file: str | Path,
    ) -> Path:

        path = Path(
            audio_file
        ).resolve()

        if not path.exists():

            raise GroqSTTError(
                f"Audio file does not exist: {path}"
            )

        if not path.is_file():

            raise GroqSTTError(
                f"Audio path is not a file: {path}"
            )

        if path.stat().st_size <= 0:

            raise GroqSTTError(
                f"Audio file is empty: {path}"
            )

        return path

    # ======================================================
    # General Text Normalization
    # ======================================================

    @staticmethod
    def normalize_text(
        text: str | None,
    ) -> str:

        if not text:
            return ""

        text = str(text)

        text = " ".join(
            text.split()
        )

        text = re.sub(
            r"\s+([,.!?;:])",
            r"\1",
            text,
        )

        return text.strip()


    # ======================================================
    # Garbage Detection
    # ======================================================

    @staticmethod
    def _is_repetitive_garbage(
        text: str,
    ) -> bool:

        if not text:
            return True

        words = re.findall(
            r"[A-Za-z]+",
            text.lower(),
        )

        if len(words) < 5:
            return False

        if len(set(words)) == 1:
            return True

        counts: dict[str, int] = {}

        for word in words:

            counts[word] = (
                counts.get(
                    word,
                    0,
                )
                + 1
            )

        highest_count = max(
            counts.values()
        )

        if (
            highest_count >= 8
            and
            highest_count / len(words) >= 0.80
        ):
            return True

        return False

    # ======================================================
    # Groq Error Classification
    # ======================================================

    @staticmethod
    def _raise_groq_error(
        error: Exception,
    ) -> None:

        status_code = getattr(
            error,
            "status_code",
            None,
        )

        response = getattr(
            error,
            "response",
            None,
        )

        if response is not None:

            response_status = getattr(
                response,
                "status_code",
                None,
            )

            if response_status is not None:
                status_code = response_status

        error_text = str(
            error
        ).lower()

        # --------------------------------------------------
        # Rate limit
        # --------------------------------------------------

        if status_code == 429:

            raise GroqSTTRateLimitError(
                "Groq STT rate limit reached."
            ) from error

        if (
            "rate limit" in error_text
            or
            "too many requests" in error_text
            or
            "429" in error_text
        ):

            raise GroqSTTRateLimitError(
                "Groq STT rate limit reached."
            ) from error

        # --------------------------------------------------
        # Cloudflare / 403
        # --------------------------------------------------

        if status_code == 403:

            if (
                "cloudflare" in error_text
                or
                "browser_signature_banned"
                in error_text
                or
                "error 1010" in error_text
                or
                "access denied" in error_text
            ):

                raise GroqSTTAccessError(
                    "Groq STT was blocked by Cloudflare "
                    "(HTTP 403 / Error 1010)."
                ) from error

            raise GroqSTTAccessError(
                "Groq STT request was forbidden "
                "(HTTP 403)."
            ) from error

        # --------------------------------------------------
        # Cloudflare text without status
        # --------------------------------------------------

        if (
            "browser_signature_banned"
            in error_text
            or
            "error 1010" in error_text
            or
            "cloudflare" in error_text
        ):

            raise GroqSTTAccessError(
                "Groq STT was blocked by Cloudflare."
            ) from error

        # --------------------------------------------------
        # Generic error
        # --------------------------------------------------

        raise GroqSTTError(
            f"Groq STT request failed: {error}"
        ) from error

    # ======================================================
    # Core Groq Transcription
    # ======================================================

    def transcribe(
        self,
        audio_file: str | Path,
    ) -> str:

        path = self._validate_audio_file(
            audio_file
        )

        print(
            "\n🧠 Sending audio to Groq STT..."
        )

        print(
            f"Audio File : {path}"
        )

        print(
            f"Audio Size : "
            f"{path.stat().st_size} bytes"
        )

        print(
            "Transport : Direct HTTP multipart"
        )

        data = {
            "model": self.model,
            "response_format": "text",
            "language": "en",
            "temperature": "0.0",
        }

        try:

            with path.open(
                "rb"
            ) as audio:

                files = {
                    "file": (
                        path.name,
                        audio,
                        "audio/wav",
                    )
                }

                response = self.http_client.post(
                    self.GROQ_TRANSCRIPTION_URL,
                    data=data,
                    files=files,
                )

            # ------------------------------------------------
            # Status Handling
            # ------------------------------------------------

            if response.status_code >= 400:

                error_message = (
                    f"HTTP {response.status_code}: "
                    f"{response.text}"
                )

                class _GroqHTTPError(Exception):
                    pass

                http_error = _GroqHTTPError(
                    error_message
                )

                http_error.status_code = (
                    response.status_code
                )

                http_error.response = response

                self._raise_groq_error(
                    http_error
                )

            # ------------------------------------------------
            # Response
            # ------------------------------------------------

            response_text = response.text

            text = self.normalize_text(
                response_text
            )

            # ------------------------------------------------
            # Empty response
            # ------------------------------------------------

            if not text:

                print(
                    "Groq STT returned empty "
                    "transcript."
                )

                return ""

            # ------------------------------------------------
            # Repetitive garbage
            # ------------------------------------------------

            if self._is_repetitive_garbage(
                text
            ):

                print(
                    "Groq STT rejected obvious "
                    "repetitive transcription garbage."
                )

                return ""

            # ------------------------------------------------
            # Maximum transcript length
            # ------------------------------------------------

            if len(text) > self.MAX_TEXT_LENGTH:

                text = (
                    text[
                        :self.MAX_TEXT_LENGTH
                    ]
                    .rstrip()
                )

            # ------------------------------------------------
            # Success log
            # ------------------------------------------------

            print(
                "\n========== GROQ STT =========="
            )

            print(
                f"Transcript : {text}"
            )

            print(
                "==============================\n"
            )

            return text

        except GroqSTTError:
            raise

        except httpx.HTTPStatusError as error:

            self._raise_groq_error(
                error
            )

        except httpx.TimeoutException as error:

            raise GroqSTTError(
                "Groq STT request timed out."
            ) from error

        except httpx.RequestError as error:

            raise GroqSTTError(
                f"Groq STT network request failed: "
                f"{error}"
            ) from error

        except Exception as error:

            self._raise_groq_error(
                error
            )

        return ""


    # ======================================================
    # Fresh Command Transcription
    # ======================================================

    def transcribe_command(
        self,
        audio_file: str | Path,
    ) -> str:

        print(
            "\n========== GROQ COMMAND =========="
        )

        print(
            "Groq STT: processing fresh "
            "command audio..."
        )

        try:

            text = self.transcribe(
                audio_file
            )

        except GroqSTTAccessError as error:

            print(
                f"Groq Command Access Error : {error}"
            )

            return ""

        except GroqSTTRateLimitError as error:

            print(
                f"Groq Command Rate Limit : {error}"
            )

            return ""

        except GroqSTTError as error:

            print(
                f"Groq Command STT Error : {error}"
            )

            return ""

        print(
            f"Command Transcript : "
            f"{text or '<empty>'}"
        )

        print(
            "==================================\n"
        )

        return text

    # ======================================================
    # Wake Word Similarity
    # ======================================================

    @classmethod
    def wake_word_similarity(
        cls,
        word: str,
    ) -> float:

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
            for candidate in cls.WAKE_CANDIDATES
        )

    # ======================================================
    # Wake-Like Token
    # ======================================================

    @classmethod
    def _is_wake_like_token(
        cls,
        token: str,
    ) -> bool:

        token = re.sub(
            r"[^a-z]+",
            "",
            token.lower(),
        )

        if len(token) < 5:
            return False

        return (
            cls.wake_word_similarity(
                token
            )
            >= cls.WAKE_SINGLE_WORD_THRESHOLD
        )

    # ======================================================
    # Deep Family Detection
    # ======================================================

    @classmethod
    def _contains_deep_family(
        cls,
        words: list[str],
    ) -> bool:

        for index, word in enumerate(
            words
        ):

            if word != "deep":
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
                "d",
                "please",
            }:

                return True

            if (
                "wake" in following
                and
                "up" in following
            ):

                return True

            if (
                "make" in following
                and
                "up" in following
            ):

                return True

        return False

    # ======================================================
    # DHEEPTHI Wake Detection
    # ======================================================

    @classmethod
    def contains_wake_word(
        cls,
        text: str | None,
    ) -> bool:

        normalized = cls.normalize_wake_text(
            text
        )

        if not normalized:
            return False

        # --------------------------------------------------
        # Reject obvious normal English.
        # --------------------------------------------------

        if normalized in cls.WAKE_REJECT_PHRASES:
            return False

        # --------------------------------------------------
        # Exact known wake phrases.
        # --------------------------------------------------

        for wake in cls.WAKE_WORDS:

            if re.search(
                rf"\b{re.escape(wake)}\b",
                normalized,
            ):

                return True

        # --------------------------------------------------
        # Known ASR wake variations.
        # --------------------------------------------------

        if normalized in cls.WAKE_PHRASE_VARIATIONS:
            return True

        # --------------------------------------------------
        # Token detection.
        # --------------------------------------------------

        words = normalized.split()

        for word in words:

            if cls._is_wake_like_token(
                word
            ):

                return True

        # --------------------------------------------------
        # Deep family.
        # --------------------------------------------------

        if cls._contains_deep_family(
            words
        ):

            return True

        # --------------------------------------------------
        # Joined transcription.
        # --------------------------------------------------

        joined = "".join(
            words
        )

        for candidate in (
            "deepdeep",
            "deepdee",
            "deepthi",
            "deepthee",
            "dheepthi",
        ):

            if candidate in joined:
                return True

        # --------------------------------------------------
        # Whole phrase fuzzy matching.
        #
        # Restricted to short utterances so normal
        # commands are not accidentally classified as
        # DHEEPTHI.
        # --------------------------------------------------

        if len(words) <= 4:

            for candidate in cls.WAKE_CANDIDATES:

                score = SequenceMatcher(
                    None,
                    joined,
                    candidate,
                ).ratio()

                if (
                    score
                    >= cls.WAKE_FUZZY_THRESHOLD
                ):

                    return True

        return False

    # ======================================================
    # Remove Wake Word
    # ======================================================

    @classmethod
    def remove_wake_word(
        cls,
        text: str | None,
    ) -> str:

        if not text:
            return ""

        original = text.strip()

        normalized = cls.normalize_wake_text(
            original
        )

        prefixes = (
            "hey dheepthi",
            "hey deepthi",
            "hey deepti",
            "hey deepthee",

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
            "deep d",

            "dheep the",
            "dheep thee",
            "dheep tea",
            "dheep thi",
            "dheep tee",
            "dheep ti",

            "beep the",
            "weep the",
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

                prefix_count = len(
                    prefix.split()
                )

                return " ".join(
                    words[prefix_count:]
                ).strip()

        # --------------------------------------------------
        # Single-word wake variants.
        # --------------------------------------------------

        words = original.split()

        if not words:
            return ""

        first_word = re.sub(
            r"^[^\w-]+|[^\w-]+$",
            "",
            words[0].lower(),
        )

        single_words = {
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
            first_word in single_words
            or
            cls._is_wake_like_token(
                first_word
            )
        ):

            return " ".join(
                words[1:]
            ).strip()

        return original

    # ======================================================
    # Compatibility Alias
    # ======================================================

    def listen(
        self,
        audio_file: str | Path,
    ) -> str | None:

        try:

            text = self.transcribe(
                audio_file
            )

            return text or None

        except GroqSTTError as error:

            print(
                f"Groq STT Error : {error}"
            )

            return None

    # ======================================================
    # Health Check
    # ======================================================

    def is_configured(
        self,
    ) -> bool:

        return bool(
            self.api_key
        )

    # ======================================================
    # Model
    # ======================================================

    def get_model(
        self,
    ) -> str:

        return self.model

    # ======================================================
    # Cleanup
    # ======================================================

    def close(
        self,
    ) -> None:

        http_client = getattr(
            self,
            "http_client",
            None,
        )

        if http_client is not None:

            try:

                http_client.close()

            except Exception:
                pass

            self.http_client = None

    # ======================================================
    # Safe Representation
    # ======================================================

    def __repr__(
        self,
    ) -> str:

        return (
            f"GroqRecognizer("
            f"model={self.model!r}, "
            f"configured="
            f"{self.is_configured()!r}"
            f")"
        )