"""
DHEEPTHI-AI
Cloud OCR Engine

Responsibilities
----------------
- Extract text from screenshots/images using Gemini Cloud
- Gemini Vision API key fallback
- Automatic API key rotation
- Quota-aware fallback
- Invalid-key fallback
- Clean OCR text
- Extract individual text lines
- Search text inside OCR result
- Thread-safe API access
- Direct image-bytes OCR support

Architecture
------------
vision/
    gemini_vision.py
        General image/screen understanding

    ocr.py
        OCR / text extraction only

This module does NOT use:
    - pytesseract
    - Tesseract
    - OpenCV
    - YOLO
    - local OCR models
    - mouse automation
    - keyboard automation

OCR processing is performed through Gemini Cloud API.

Environment Variables
---------------------
GEMINI_VISION_API_KEY=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=

Optional:
GEMINI_MODEL=models/gemini-3.5-flash
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google import genai
from google.genai import types

from config import settings


# ==========================================================
# Cloud OCR Engine
# ==========================================================

class OCREngine:
    """
    Gemini-based cloud OCR engine.

    Responsibilities
    ----------------
    - Image -> text extraction
    - OCR text cleanup
    - Line extraction
    - Text searching
    - Gemini API fallback
    - API key rotation

    No local OCR engine is used.
    """

    # ------------------------------------------------------
    # Initialize
    # ------------------------------------------------------

    def __init__(
        self,
        language: str = "eng",
    ):
        """
        Initialize the cloud OCR engine.

        Parameters
        ----------
        language:
            OCR language hint.

        Examples
        --------
        eng
        tam
        eng+tam
        """

        self.language = (
            str(language).strip()
            or "eng"
        )

        # --------------------------------------------------
        # Gemini API Keys
        # --------------------------------------------------

        self.api_keys: List[str] = []

        # Primary Vision/OCR key
        primary_key = getattr(
            settings,
            "GEMINI_VISION_API_KEY",
            None,
        )

        if primary_key:

            primary_key = str(
                primary_key
            ).strip()

            if primary_key:

                self.api_keys.append(
                    primary_key
                )

        # Backup keys
        backup_key_1 = getattr(
            settings,
            "GEMINI_API_KEY_3",
            None,
        )

        if backup_key_1:

            backup_key_1 = str(
                backup_key_1
            ).strip()

            if (
                backup_key_1
                and backup_key_1 not in self.api_keys
            ):

                self.api_keys.append(
                    backup_key_1
                )

        backup_key_2 = getattr(
            settings,
            "GEMINI_API_KEY_4",
            None,
        )

        if backup_key_2:

            backup_key_2 = str(
                backup_key_2
            ).strip()

            if (
                backup_key_2
                and backup_key_2 not in self.api_keys
            ):

                self.api_keys.append(
                    backup_key_2
                )

        # --------------------------------------------------
        # Validate API Keys
        # --------------------------------------------------

        if not self.api_keys:

            raise RuntimeError(
                "No Gemini Vision/OCR API keys configured. "
                "Set GEMINI_VISION_API_KEY, "
                "GEMINI_API_KEY_3 or GEMINI_API_KEY_4."
            )

        # --------------------------------------------------
        # Runtime Configuration
        # --------------------------------------------------

        self.current_key_index = 0

        self.model = getattr(
            settings,
            "GEMINI_MODEL",
            "models/gemini-3.5-flash",
        )

        self.model = (
            str(self.model).strip()
            or "models/gemini-3.5-flash"
        )

        # --------------------------------------------------
        # Thread Safety
        # --------------------------------------------------

        self.lock = threading.RLock()

        # --------------------------------------------------
        # Gemini Client
        # --------------------------------------------------

        self.client: Optional[genai.Client] = None

        self._closing = False

        self._create_client()

        print(
            f"Cloud OCR Engine Ready | "
            f"Model : {self.model} | "
            f"Keys : {len(self.api_keys)}"
        )

    # ======================================================
    # Create Gemini Client
    # ======================================================

    def _create_client(self) -> None:
        """
        Create Gemini client using the currently
        selected API key.
        """

        if self._closing:

            return

        if not self.api_keys:

            raise RuntimeError(
                "No Gemini OCR API keys available."
            )

        api_key = self.api_keys[
            self.current_key_index
        ]

        self.client = genai.Client(
            api_key=api_key
        )

        print(
            f"OCR Gemini Client Created | "
            f"Key : {self.current_key_index + 1}/"
            f"{len(self.api_keys)} | "
            f"Model : {self.model}"
        )

    # ======================================================
    # Mask API Key
    # ======================================================

    @staticmethod
    def _masked_key(
        api_key: str,
    ) -> str:
        """
        Safely display an API key without exposing
        the complete secret.
        """

        if not api_key:

            return "Unavailable"

        if len(api_key) <= 8:

            return "********"

        return (
            api_key[:4]
            + "..."
            + api_key[-4:]
        )

    # ======================================================
    # Rotate API Key
    # ======================================================

    def rotate_api_key(self) -> bool:
        """
        Switch to the next available Gemini API key.

        Returns
        -------
        bool
            True when another key is available.
            False when there is no alternate key.
        """

        with self.lock:

            total_keys = len(
                self.api_keys
            )

            if total_keys <= 1:

                print(
                    "OCR: No alternate Gemini API key available."
                )

                return False

            old_index = (
                self.current_key_index
            )

            self.current_key_index = (
                self.current_key_index + 1
            ) % total_keys

            if (
                self.current_key_index
                == old_index
            ):

                return False

            self._create_client()

            print(
                f"OCR switched to Gemini API Key "
                f"{self.current_key_index + 1}/"
                f"{total_keys}"
            )

            return True

    # ======================================================
    # Retryable Error Detection
    # ======================================================

    @staticmethod
    def _is_retryable_error(
        error: Exception,
    ) -> bool:
        """
        Determine whether another Gemini API key
        should be attempted.

        Retryable cases include:
        - quota exhaustion
        - rate limiting
        - authentication failures
        - invalid API keys
        - temporary service failures
        """

        error_text = str(
            error
        ).lower()

        retry_keywords = (
            # Rate limit / quota
            "429",
            "quota",
            "resource_exhausted",
            "resource exhausted",
            "rate limit",
            "rate_limit",
            "too many requests",

            # Authentication / API key
            "401",
            "403",
            "unauthorized",
            "permission denied",
            "api key",
            "invalid api key",
            "invalid_api_key",
            "expired",

            # Temporary service failures
            "deadline exceeded",
            "temporarily unavailable",
            "service unavailable",
            "unavailable",
            "internal server error",
            "internal error",
            "503",
            "500",
        )

        return any(
            keyword in error_text
            for keyword in retry_keywords
        )

    # ======================================================
    # Validate Image
    # ======================================================

    @staticmethod
    def _validate_image(
        image_path: Union[str, Path],
    ) -> Path:
        """
        Validate image path before sending it to Gemini.
        """

        path = Path(
            image_path
        )

        if not path.exists():

            raise FileNotFoundError(
                f"Image not found: {path}"
            )

        if not path.is_file():

            raise ValueError(
                f"Image path is not a file: {path}"
            )

        if path.stat().st_size <= 0:

            raise ValueError(
                f"Image file is empty: {path}"
            )

        return path

    # ======================================================
    # Detect MIME Type
    # ======================================================

    @staticmethod
    def _detect_mime_type(
        image_path: Path,
    ) -> str:
        """
        Detect supported image MIME type.
        """

        suffix = (
            image_path.suffix.lower()
        )

        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }

        mime_type = mime_types.get(
            suffix
        )

        if not mime_type:

            raise ValueError(
                f"Unsupported image format: {suffix}"
            )

        return mime_type

    # ======================================================
    # Read Image Bytes
    # ======================================================

    @staticmethod
    def _read_image_bytes(
        image_path: Path,
    ) -> bytes:
        """
        Read image bytes from disk.
        """

        try:

            image_bytes = (
                image_path.read_bytes()
            )

        except Exception as error:

            raise RuntimeError(
                f"Unable to read image: {image_path}"
            ) from error

        if not image_bytes:

            raise ValueError(
                f"Image bytes are empty: {image_path}"
            )

        return image_bytes

    # ======================================================
    # Build OCR Prompt
    # ======================================================

    def _build_ocr_prompt(
        self,
    ) -> str:
        """
        Build the dedicated OCR-only Gemini prompt.

        Gemini must extract text only.
        """

        language = (
            self.language.lower()
        )

        if (
            "tam" in language
            and "eng" in language
        ):

            language_instruction = (
                "The visible text may contain "
                "both Tamil and English."
            )

        elif "tam" in language:

            language_instruction = (
                "The visible text may be Tamil."
            )

        else:

            language_instruction = (
                "The primary expected language is English."
            )

        return f"""
You are the OCR engine inside DHEEPTHI-AI.

Your ONLY task is to extract visible text from
the supplied image.

{language_instruction}

OCR RULES
==================================================

1. Extract all clearly visible textual content.

2. Preserve the original wording as accurately
   as possible.

3. Preserve the natural reading order whenever
   possible.

4. Preserve numbers exactly when visible.

5. Preserve punctuation and symbols when visible.

6. Preserve UI labels, buttons, menus, titles,
   filenames, folder names and other visible text.

7. Do not describe the image.

8. Do not identify objects.

9. Do not explain what the screen contains.

10. Do not answer questions about the image.

11. Do not add information that is not visible.

12. Do not invent missing words or characters.

13. If a word is genuinely unreadable, use
    [UNREADABLE] instead of guessing.

14. Return ONLY the extracted text.

15. Put separate visible text regions on separate
    lines whenever possible.

16. Do not use Markdown code fences.

17. Do not add an introduction.

18. Do not add a conclusion.

19. If no readable text is visible, return exactly:

[NO TEXT DETECTED]

LANGUAGE HINT
==================================================

Configured OCR language:
{self.language}
""".strip()

    # ======================================================
    # Clean OCR Response
    # ======================================================

    @staticmethod
    def _clean_ocr_response(
        text: str,
    ) -> str:
        """
        Clean Gemini OCR response while preserving
        legitimate extracted content.
        """

        if not text:

            return ""

        text = str(
            text
        ).strip()

        # --------------------------------------------------
        # Remove Markdown code fences
        # --------------------------------------------------

        if text.startswith("```"):

            text = re.sub(
                r"^```[a-zA-Z0-9_-]*\s*",
                "",
                text,
            )

            text = re.sub(
                r"\s*```$",
                "",
                text,
            )

        # --------------------------------------------------
        # Remove accidental OCR prefixes
        # --------------------------------------------------

        prefixes = (
            "OCR:",
            "OCR Result:",
            "Extracted Text:",
            "Extracted text:",
            "Text:",
        )

        for prefix in prefixes:

            if text.startswith(prefix):

                text = text[
                    len(prefix):
                ].strip()

                break

        # --------------------------------------------------
        # Normalize line endings
        # --------------------------------------------------

        text = text.replace(
            "\r\n",
            "\n",
        )

        text = text.replace(
            "\r",
            "\n",
        )

        # --------------------------------------------------
        # Remove null characters
        # --------------------------------------------------

        text = text.replace(
            "\x00",
            "",
        )

        # --------------------------------------------------
        # Normalize spaces/tabs
        # --------------------------------------------------

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        # --------------------------------------------------
        # Normalize excessive blank lines
        # --------------------------------------------------

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        # --------------------------------------------------
        # Remove whitespace around line breaks
        # --------------------------------------------------

        text = re.sub(
            r" *\n *",
            "\n",
            text,
        )

        return text.strip()

    # ======================================================
    # Extract Response Text
    # ======================================================

    @staticmethod
    def _get_response_text(
        response: Any,
    ) -> str:
        """
        Safely extract text from Gemini response.
        """

        if response is None:

            return ""

        text = getattr(
            response,
            "text",
            None,
        )

        if text is None:

            return ""

        return str(
            text
        ).strip()

    # ======================================================
    # Generate OCR Request
    # ======================================================

    def _generate_ocr(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
    ) -> str:
        """
        Internal Gemini OCR request.

        Automatically rotates through configured API
        keys when the active key is unavailable.
        """

        if self._closing:

            return ""

        if not image_bytes:

            raise ValueError(
                "Image bytes are empty."
            )

        if not mime_type.startswith(
            "image/"
        ):

            raise ValueError(
                f"Invalid image MIME type: {mime_type}"
            )

        with self.lock:

            total_keys = len(
                self.api_keys
            )

            attempted_keys = set()

            for _ in range(
                total_keys
            ):

                if self._closing:

                    return ""

                current_index = (
                    self.current_key_index
                )

                # ------------------------------------------
                # Prevent retrying the same key
                # ------------------------------------------

                if (
                    current_index
                    in attempted_keys
                ):

                    break

                attempted_keys.add(
                    current_index
                )

                try:

                    print(
                        "\n========== CLOUD OCR =========="
                    )

                    print(
                        f"Model : {self.model}"
                    )

                    print(
                        f"Gemini Key : "
                        f"{self._masked_key(self.api_keys[current_index])}"
                    )

                    # --------------------------------------
                    # Build image part
                    # --------------------------------------

                    image_part = (
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type=mime_type,
                        )
                    )

                    # --------------------------------------
                    # Gemini request
                    # --------------------------------------

                    if self.client is None:

                        self._create_client()

                    response = (
                        self.client.models.generate_content(
                            model=self.model,
                            contents=[
                                image_part,
                                prompt,
                            ],
                            config=types.GenerateContentConfig(
                                temperature=0.0,
                                top_p=0.90,
                                top_k=20,
                                max_output_tokens=4096,
                                candidate_count=1,
                            ),
                        )
                    )

                    # --------------------------------------
                    # Extract response
                    # --------------------------------------

                    text = (
                        self._get_response_text(
                            response
                        )
                    )

                    text = (
                        self._clean_ocr_response(
                            text
                        )
                    )

                    # --------------------------------------
                    # Empty response
                    # --------------------------------------

                    if not text:

                        raise RuntimeError(
                            "Gemini OCR returned "
                            "an empty response."
                        )

                    # --------------------------------------
                    # Success
                    # --------------------------------------

                    print(
                        "\nExtracted Text:"
                    )

                    print(
                        text
                    )

                    print(
                        "Text Length :",
                        len(text),
                    )

                    print(
                        "Key Used :",
                        current_index + 1,
                    )

                    print(
                        "================================\n"
                    )

                    return text

                except Exception as error:

                    print(
                        "\nCloud OCR Error :",
                        error,
                    )

                    # --------------------------------------
                    # Fallback to next key
                    # --------------------------------------

                    if self._is_retryable_error(
                        error
                    ):

                        print(
                            f"OCR Gemini Key "
                            f"{current_index + 1} unavailable."
                        )

                        if self.rotate_api_key():

                            print(
                                "Trying next OCR Gemini API key..."
                            )

                            continue

                    # --------------------------------------
                    # No more fallback
                    # --------------------------------------

                    raise RuntimeError(
                        f"Cloud OCR failed: {error}"
                    ) from error

        raise RuntimeError(
            "All Gemini OCR API keys are unavailable."
        )

    # ======================================================
    # Extract Text From Image
    # ======================================================

    def extract_text(
        self,
        image_path: Union[str, Path],
    ) -> str:
        """
        Extract text from an image using Gemini Cloud.

        Parameters
        ----------
        image_path:
            Path to screenshot/image.

        Returns
        -------
        str
            Extracted OCR text.
        """

        if self._closing:

            return ""

        path = self._validate_image(
            image_path
        )

        mime_type = (
            self._detect_mime_type(
                path
            )
        )

        image_bytes = (
            self._read_image_bytes(
                path
            )
        )

        prompt = (
            self._build_ocr_prompt()
        )

        return self._generate_ocr(
            image_bytes,
            mime_type,
            prompt,
        )

    # ======================================================
    # Extract Lines
    # ======================================================

    def extract_lines(
        self,
        image_path: Union[str, Path],
    ) -> List[str]:
        """
        Extract OCR text as a list of individual lines.
        """

        text = self.extract_text(
            image_path
        )

        if not text:

            return []

        if text == "[NO TEXT DETECTED]":

            return []

        lines: List[str] = []

        for line in text.split("\n"):

            line = line.strip()

            if line:

                lines.append(
                    line
                )

        return lines

    # ======================================================
    # Extract Structured OCR Data
    # ======================================================

    def extract_data(
        self,
        image_path: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Return OCR result with metadata.
        """

        try:

            path = self._validate_image(
                image_path
            )

            text = self.extract_text(
                path
            )

            lines: List[str] = []

            if text != "[NO TEXT DETECTED]":

                lines = [
                    line.strip()
                    for line in text.split("\n")
                    if line.strip()
                ]

            return {
                "success": True,
                "text": text,
                "lines": lines,
                "character_count": len(text),
                "line_count": len(lines),
                "language": self.language,
                "provider": "gemini_cloud",
                "model": self.model,
                "api_key_number": (
                    self.current_key_index + 1
                ),
                "total_api_keys": len(
                    self.api_keys
                ),
                "error": None,
            }

        except Exception as error:

            return {
                "success": False,
                "text": "",
                "lines": [],
                "character_count": 0,
                "line_count": 0,
                "language": self.language,
                "provider": "gemini_cloud",
                "model": self.model,
                "api_key_number": (
                    self.current_key_index + 1
                ),
                "total_api_keys": len(
                    self.api_keys
                ),
                "error": str(error),
            }

    # ======================================================
    # Extract From Raw Image Bytes
    # ======================================================

    def extract_from_bytes(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> str:
        """
        Extract text directly from image bytes.

        Useful when screenshot data is already available
        in memory and does not need to be written to disk.
        """

        if self._closing:

            return ""

        if not image_bytes:

            raise ValueError(
                "Image bytes are empty."
            )

        mime_type = (
            str(mime_type)
            .strip()
            .lower()
        )

        if not mime_type.startswith(
            "image/"
        ):

            raise ValueError(
                f"Invalid image MIME type: {mime_type}"
            )

        prompt = (
            self._build_ocr_prompt()
        )

        return self._generate_ocr(
            image_bytes,
            mime_type,
            prompt,
        )

    # ======================================================
    # Contains Text
    # ======================================================

    def contains_text(
        self,
        image_path: Union[str, Path],
        target: str,
        *,
        case_sensitive: bool = False,
    ) -> bool:
        """
        Check whether target text exists in the image.
        """

        target = str(
            target
        ).strip()

        if not target:

            return False

        text = self.extract_text(
            image_path
        )

        if case_sensitive:

            return target in text

        return (
            target.lower()
            in text.lower()
        )

    # ======================================================
    # Find Text
    # ======================================================

    def find_text(
        self,
        image_path: Union[str, Path],
        target: str,
        *,
        case_sensitive: bool = False,
    ) -> List[str]:
        """
        Return OCR lines containing target text.
        """

        target = str(
            target
        ).strip()

        if not target:

            return []

        lines = self.extract_lines(
            image_path
        )

        if case_sensitive:

            return [
                line
                for line in lines
                if target in line
            ]

        target_lower = (
            target.lower()
        )

        return [
            line
            for line in lines
            if target_lower in line.lower()
        ]

    # ======================================================
    # Status
    # ======================================================

    def status(self) -> Dict[str, Any]:
        """
        Return OCR engine status.
        """

        with self.lock:

            return {
                "provider": "gemini_cloud",
                "model": self.model,
                "language": self.language,
                "total_api_keys": len(
                    self.api_keys
                ),
                "current_api_key": (
                    self.current_key_index + 1
                ),
                "current_api_key_masked": (
                    self._masked_key(
                        self.api_keys[
                            self.current_key_index
                        ]
                    )
                ),
                "closing": self._closing,
                "available": (
                    self.client is not None
                    and not self._closing
                ),
            }

    # ======================================================
    # Current API Key
    # ======================================================

    def current_api_key(self) -> str:
        """
        Return current API key.

        Internal use only.
        """

        with self.lock:

            return self.api_keys[
                self.current_key_index
            ]

    # ======================================================
    # Current API Key Number
    # ======================================================

    def current_api_key_number(self) -> int:
        """
        Return current active API key number.
        """

        with self.lock:

            return (
                self.current_key_index + 1
            )

    # ======================================================
    # Total API Keys
    # ======================================================

    def total_api_keys(self) -> int:
        """
        Return number of configured API keys.
        """

        return len(
            self.api_keys
        )

    # ======================================================
    # Key Status
    # ======================================================

    def key_status(self) -> Dict[str, Any]:
        """
        Return safe API-key status information.

        Complete API keys are never exposed.
        """

        with self.lock:

            return {
                "total_keys": len(
                    self.api_keys
                ),
                "current_key": (
                    self.current_key_index + 1
                ),
                "keys": [
                    {
                        "number": index + 1,
                        "configured": bool(key),
                        "masked": self._masked_key(
                            key
                        ),
                    }
                    for index, key in enumerate(
                        self.api_keys
                    )
                ],
            }

    # ======================================================
    # Cleanup
    # ======================================================

    def close(self) -> None:
        """
        Release Gemini OCR resources.
        """

        with self.lock:

            if self._closing:

                return

            self._closing = True

            self.client = None

            print(
                "Cloud OCR Engine shutdown completed."
            )


# ==========================================================
# Compatibility Alias
# ==========================================================

OCREngineClient = OCREngine


# ==========================================================
# Module Exports
# ==========================================================

__all__ = [
    "OCREngine",
    "OCREngineClient",
]