"""
DHEEPTHI-AI
Gemini Vision Engine

Responsibilities
----------------
- Screenshot / image understanding using Gemini Vision
- Text extraction from screen/image
- Object detection / identification
- UI element identification
- Screen description
- Automatic Vision API-key rotation
- Quota-aware fallback
- Invalid-key fallback
- Thread-safe Gemini Vision requests

API Keys
--------
Primary:
    GEMINI_VISION_API_KEY

Backup:
    GEMINI_API_KEY_3
    GEMINI_API_KEY_4

Important
---------
This module is responsible ONLY for cloud-based vision
processing through Gemini.

It does NOT:
- control the mouse
- click UI elements
- double-click files
- execute desktop commands
- perform local OCR
- use pytesseract
- use YOLO
- modify command_dispatcher.py
- modify main_window.py

OCR remains modular and can be implemented separately
inside:

    vision/ocr.py

Mouse automation remains a separate module.
"""

from __future__ import annotations

import mimetypes
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google import genai
from google.genai import types

from config import settings


# ==========================================================
# Gemini Vision Client
# ==========================================================

class GeminiVision:
    """
    Central Gemini Vision client used by DHEEPTHI.

    Responsibilities
    ----------------
    - Gemini Vision API communication
    - Vision API-key rotation
    - Image loading
    - Screen understanding
    - Cloud-based text extraction
    - Object understanding
    - UI element understanding

    This class performs visual understanding only.

    It does not perform desktop actions.
    """

    # ------------------------------------------------------
    # Initialize
    # ------------------------------------------------------

    def __init__(self):

        # ------------------------------------------
        # Vision API Keys
        # ------------------------------------------

        self.api_keys: List[str] = []

        # ------------------------------------------
        # Primary Vision Key
        # ------------------------------------------

        primary_key = getattr(
            settings,
            "GEMINI_VISION_API_KEY",
            None
        )

        if primary_key:

            primary_key = str(
                primary_key
            ).strip()

            if primary_key:

                self.api_keys.append(
                    primary_key
                )

        # ------------------------------------------
        # Backup Key 1
        # ------------------------------------------

        backup_key_1 = getattr(
            settings,
            "GEMINI_API_KEY_3",
            None
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

        # ------------------------------------------
        # Backup Key 2
        # ------------------------------------------

        backup_key_2 = getattr(
            settings,
            "GEMINI_API_KEY_4",
            None
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

        # ------------------------------------------
        # Validate API Keys
        # ------------------------------------------

        if not self.api_keys:

            raise RuntimeError(
                "No Gemini Vision API keys configured.\n"
                "Please configure:\n"
                "GEMINI_VISION_API_KEY\n"
                "GEMINI_API_KEY_3\n"
                "GEMINI_API_KEY_4"
            )

        # ------------------------------------------
        # Runtime Configuration
        # ------------------------------------------

        self.current_key_index = 0

        self.model = getattr(
            settings,
            "GEMINI_MODEL",
            "models/gemini-3.5-flash"
        )

        # ------------------------------------------
        # Thread Safety
        # ------------------------------------------

        self.lock = threading.RLock()

        # ------------------------------------------
        # Gemini Client
        # ------------------------------------------

        self.client: Optional[
            genai.Client
        ] = None

        self._closing = False

        # ------------------------------------------
        # Create Initial Client
        # ------------------------------------------

        self._create_client()

        print(
            f"Gemini Vision Ready | "
            f"Model : {self.model} | "
            f"Keys : {len(self.api_keys)}"
        )

    # ======================================================
    # Create Gemini Client
    # ======================================================

    def _create_client(self):
        """
        Create a Gemini client using the currently
        selected API key.
        """

        if self._closing:

            return

        api_key = self.api_keys[
            self.current_key_index
        ]

        print(
            "\nCreating Gemini Vision Client..."
        )

        print(
            f"Vision Model : {self.model}"
        )

        print(
            "Vision API Key : "
            f"{self._masked_key(api_key)}"
        )

        self.client = genai.Client(
            api_key=api_key
        )

    # ======================================================
    # Mask API Key
    # ======================================================

    @staticmethod
    def _masked_key(
        api_key: str
    ) -> str:
        """
        Safely mask an API key for console logging.
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
        Switch to the next configured Gemini Vision key.

        Key order:

            1. GEMINI_VISION_API_KEY
            2. GEMINI_API_KEY_3
            3. GEMINI_API_KEY_4

        Returns
        -------
        bool
            True if another key was selected.
            False if no alternate key exists.
        """

        with self.lock:

            total_keys = len(
                self.api_keys
            )

            if total_keys <= 1:

                print(
                    "No alternate Gemini Vision API key available."
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
                f"Switched to Gemini Vision API Key "
                f"{self.current_key_index + 1}/"
                f"{total_keys}"
            )

            return True

    # ======================================================
    # Retryable Error Detection
    # ======================================================

    @staticmethod
    def _is_retryable_error(
        error: Exception
    ) -> bool:
        """
        Determine whether the request should be retried
        using another API key.
        """

        error_text = str(
            error
        ).lower()

        retry_keywords = (
            # Rate / quota
            "429",
            "quota",
            "resource_exhausted",
            "resource exhausted",
            "rate limit",
            "rate_limit",
            "too many requests",

            # Authentication
            "401",
            "unauthorized",
            "invalid api key",
            "invalid_api_key",
            "api key not valid",

            # Permission
            "403",
            "permission denied",
            "permission_denied",

            # API argument / request failures
            "invalid argument",
            "invalid_argument",
        )

        return any(
            keyword in error_text
            for keyword in retry_keywords
        )

    # ======================================================
    # Read Image
    # ======================================================

    @staticmethod
    def _read_image(
        image_path: Union[str, Path]
    ) -> tuple[bytes, str]:
        """
        Read an image from disk.

        Returns
        -------
        tuple
            image bytes and MIME type.
        """

        path = Path(
            image_path
        )

        # ------------------------------------------
        # Validate Path
        # ------------------------------------------

        if not path.exists():

            raise FileNotFoundError(
                f"Image not found: {path}"
            )

        if not path.is_file():

            raise ValueError(
                f"Image path is not a file: {path}"
            )

        # ------------------------------------------
        # Read Bytes
        # ------------------------------------------

        image_bytes = path.read_bytes()

        if not image_bytes:

            raise ValueError(
                f"Image is empty: {path}"
            )

        # ------------------------------------------
        # Detect MIME Type
        # ------------------------------------------

        mime_type, _ = mimetypes.guess_type(
            str(path)
        )

        if not mime_type:

            mime_type = "image/png"

        if not mime_type.startswith(
            "image/"
        ):

            raise ValueError(
                f"Unsupported image type: {mime_type}"
            )

        return (
            image_bytes,
            mime_type
        )

    # ======================================================
    # Convert Image To Gemini Part
    # ======================================================

    @staticmethod
    def _image_part(
        image_bytes: bytes,
        mime_type: str
    ) -> types.Part:
        """
        Convert image bytes into a Gemini image part.
        """

        return types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type
        )

    # ======================================================
    # Build Vision Prompt
    # ======================================================

    @staticmethod
    def _build_vision_prompt(
        instruction: str
    ) -> str:
        """
        Build the standard DHEEPTHI Vision prompt.
        """

        return f"""
You are the Vision Engine of DHEEPTHI.

Analyze the provided image carefully.

Your task is to understand only what is visually
present in the image.

USER REQUEST
------------
{instruction}

STRICT RULES
------------
1. Analyze only visible information.
2. Never invent text.
3. Never invent objects.
4. Never invent applications.
5. Never invent UI elements.
6. Preserve visible text accurately.
7. Preserve numbers accurately.
8. If something is unclear, say that it is unclear.
9. Do not assume information that is not visible.
10. Do not execute any action.
11. Do not click anything.
12. Do not control the mouse.
13. Do not claim that an action was performed.
14. Do not provide imaginary coordinates.
15. Return only information requested by the user.
""".strip()

    # ======================================================
    # Extract Response Text
    # ======================================================

    @staticmethod
    def _extract_response_text(
        response: Any
    ) -> str:
        """
        Safely extract text from Gemini response.
        """

        if response is None:

            return ""

        text = getattr(
            response,
            "text",
            None
        )

        if text:

            return str(
                text
            ).strip()

        # ------------------------------------------
        # Fallback: Inspect candidates
        # ------------------------------------------

        candidates = getattr(
            response,
            "candidates",
            None
        )

        if not candidates:

            return ""

        collected: List[str] = []

        for candidate in candidates:

            content = getattr(
                candidate,
                "content",
                None
            )

            if content is None:

                continue

            parts = getattr(
                content,
                "parts",
                None
            )

            if not parts:

                continue

            for part in parts:

                part_text = getattr(
                    part,
                    "text",
                    None
                )

                if part_text:

                    collected.append(
                        str(part_text)
                    )

        return "\n".join(
            collected
        ).strip()

    # ======================================================
    # Generate Vision Content
    # ======================================================

    def _generate_content(
        self,
        image_bytes: bytes,
        mime_type: str,
        instruction: str,
        *,
        temperature: float = 0.15,
        max_output_tokens: int = 4096
    ) -> str:
        """
        Internal Gemini Vision request.

        Automatically rotates through available API keys
        when a retryable API error occurs.
        """

        if self._closing:

            return ""

        prompt = self._build_vision_prompt(
            instruction
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

                if current_index in attempted_keys:

                    break

                attempted_keys.add(
                    current_index
                )

                try:

                    # ----------------------------------
                    # Safety check
                    # ----------------------------------

                    if self.client is None:

                        self._create_client()

                    print(
                        f"\nUsing Gemini Vision Key "
                        f"{current_index + 1}/"
                        f"{total_keys}"
                    )

                    print(
                        f"Using Vision Model : "
                        f"{self.model}"
                    )

                    # ----------------------------------
                    # Build Image Part
                    # ----------------------------------

                    image_part = (
                        self._image_part(
                            image_bytes,
                            mime_type
                        )
                    )

                    # ----------------------------------
                    # Gemini Request
                    # ----------------------------------

                    response = (
                        self.client.models.generate_content(
                            model=self.model,
                            contents=[
                                image_part,
                                prompt
                            ],
                            config=(
                                types.GenerateContentConfig(
                                    temperature=temperature,
                                    top_p=0.90,
                                    top_k=20,
                                    max_output_tokens=(
                                        max_output_tokens
                                    ),
                                    candidate_count=1
                                )
                            )
                        )
                    )

                    # ----------------------------------
                    # Extract Response
                    # ----------------------------------

                    text = (
                        self._extract_response_text(
                            response
                        )
                    )

                    if not text:

                        raise RuntimeError(
                            "Gemini Vision returned "
                            "an empty response."
                        )

                    print(
                        "\n========== GEMINI VISION RESPONSE =========="
                    )

                    print(
                        text
                    )

                    print(
                        "Length :",
                        len(text)
                    )

                    print(
                        "Key Used :",
                        current_index + 1
                    )

                    print(
                        "============================================\n"
                    )

                    return text

                except Exception as error:

                    print(
                        "\nGemini Vision Error :",
                        error
                    )

                    # ----------------------------------
                    # Retry With Next Key
                    # ----------------------------------

                    if self._is_retryable_error(
                        error
                    ):

                        print(
                            "Current Gemini Vision API "
                            "key is unavailable."
                        )

                        if self.rotate_api_key():

                            continue

                    # ----------------------------------
                    # Non-retryable Error
                    # ----------------------------------

                    print(
                        "Gemini Vision request failed."
                    )

                    raise

        return ""

    # ======================================================
    # Analyze Image
    # ======================================================

    def analyze_image(
        self,
        image_path: Union[str, Path],
        instruction: str
    ) -> str:
        """
        Analyze a single image using Gemini Vision.

        Parameters
        ----------
        image_path:
            Screenshot/image path.

        instruction:
            What should be analyzed.

        Returns
        -------
        str
            Gemini Vision response.
        """

        if self._closing:

            return ""

        instruction = str(
            instruction
        ).strip()

        if not instruction:

            instruction = (
                "Describe what is visible in the image."
            )

        # ------------------------------------------
        # Load Image
        # ------------------------------------------

        image_bytes, mime_type = (
            self._read_image(
                image_path
            )
        )

        # ------------------------------------------
        # Send To Gemini
        # ------------------------------------------

        return self._generate_content(
            image_bytes,
            mime_type,
            instruction
        )

    # ======================================================
    # Read Screen
    # ======================================================

    def read_screen(
        self,
        image_path: Union[str, Path]
    ) -> str:
        """
        Understand the complete visible screen.

        Example commands:

            "Read my screen"

            "Screen-la enna irukku?"

            "Ippo screen-la enna irukku?"
        """

        instruction = """
Read and understand the complete visible screen.

Identify the currently visible:

- application or window
- important UI sections
- visible text
- buttons
- menus
- icons
- folders
- files
- dialogs
- notifications
- other clearly visible objects

Give a concise but useful description of what is
currently visible.

Mention only information that can actually be seen.
""".strip()

        return self.analyze_image(
            image_path,
            instruction
        )

    # ======================================================
    # Extract Text
    # ======================================================

    def extract_text(
        self,
        image_path: Union[str, Path]
    ) -> str:
        """
        Extract visible text from an image using
        Gemini Vision.

        IMPORTANT
        ---------
        This is cloud-based text extraction.

        No local OCR engine is used here.

        A separate OCR module can later call this
        functionality without changing the Vision client.
        """

        instruction = """
Extract all clearly visible text from the image.

Requirements:

- Preserve original wording.
- Preserve capitalization when visible.
- Preserve numbers.
- Preserve punctuation.
- Preserve button labels.
- Preserve menu labels.
- Preserve file and folder names.
- Preserve application names.
- Preserve visible headings.
- Do not describe objects.
- Do not invent missing characters.
- If text is genuinely unreadable, do not guess it.

Return only the visible text.
""".strip()

        return self.analyze_image(
            image_path,
            instruction
        )

    # ======================================================
    # Detect Objects
    # ======================================================

    def detect_objects(
        self,
        image_path: Union[str, Path]
    ) -> str:
        """
        Identify clearly visible objects.

        This is visual understanding through Gemini.

        No local object-detection model is used.
        """

        instruction = """
Identify the clearly visible objects in the image.

Focus on meaningful visible objects such as:

- applications
- windows
- folders
- files
- buttons
- icons
- menus
- dialogs
- images
- navigation elements
- other obvious visible objects

For each object, provide:

- object name
- approximate screen region
- brief description when useful

Use only information visible in the image.

Do not invent objects.
Do not provide mouse actions.
Do not provide imaginary coordinates.
""".strip()

        return self.analyze_image(
            image_path,
            instruction
        )

    # ======================================================
    # Detect UI Elements
    # ======================================================

    def detect_ui_elements(
        self,
        image_path: Union[str, Path]
    ) -> str:
        """
        Identify visible user-interface elements.

        This method only understands the UI.

        It does not perform any mouse action.
        """

        instruction = """
Identify visible user-interface elements.

Look for:

- buttons
- text fields
- checkboxes
- radio buttons
- menus
- tabs
- links
- list items
- folders
- files
- dialog controls
- navigation controls
- window controls
- visible labels

For each element, provide:

- visible label/name
- element type
- approximate screen region when clear

Only report elements that are actually visible.

Do not invent UI elements.
Do not click anything.
Do not control the mouse.
""".strip()

        return self.analyze_image(
            image_path,
            instruction
        )

    # ======================================================
    # Analyze Screen
    # ======================================================

    def analyze_screen(
        self,
        image_path: Union[str, Path],
        question: Optional[str] = None
    ) -> str:
        """
        Analyze a screen according to a question.

        Examples
        --------
        analyze_screen(
            screenshot,
            "What application is open?"
        )

        analyze_screen(
            screenshot,
            "What files are visible?"
        )
        """

        if question:

            question = str(
                question
            ).strip()

        if question:

            instruction = (
                "Analyze the screen and answer this "
                "question accurately:\n\n"
                f"{question}"
            )

        else:

            instruction = (
                "Analyze the complete visible screen "
                "and explain what is currently visible."
            )

        return self.analyze_image(
            image_path,
            instruction
        )

    # ======================================================
    # Analyze Image JSON
    # ======================================================

    def analyze_image_json(
        self,
        image_path: Union[str, Path],
        instruction: str
    ) -> str:
        """
        Generate a structured JSON response from
        Gemini Vision.

        The response is requested using Gemini's
        application/json response format.

        This method does not perform any desktop action.
        """

        if self._closing:

            return ""

        instruction = str(
            instruction
        ).strip()

        if not instruction:

            instruction = (
                "Analyze the image and return the "
                "visible information."
            )

        # ------------------------------------------
        # Load Image
        # ------------------------------------------

        image_bytes, mime_type = (
            self._read_image(
                image_path
            )
        )

        # ------------------------------------------
        # Build Strict JSON Prompt
        # ------------------------------------------

        prompt = f"""
You are the Vision Engine of DHEEPTHI.

Analyze the provided image carefully.

TASK
----
{instruction}

OUTPUT REQUIREMENT
------------------
Return valid JSON only.

STRICT JSON RULES
-----------------
1. Return one complete JSON object.
2. Do not use Markdown code fences.
3. Do not add text before JSON.
4. Do not add text after JSON.
5. Do not truncate the JSON.
6. Do not invent information.
7. Use null when a single value is not visible.
8. Use [] when a list contains no visible items.
9. Preserve visible text accurately.
10. Return only information observable in the image.
""".strip()

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

                if current_index in attempted_keys:

                    break

                attempted_keys.add(
                    current_index
                )

                try:

                    # ----------------------------------
                    # Ensure Client
                    # ----------------------------------

                    if self.client is None:

                        self._create_client()

                    print(
                        f"\nUsing Gemini Vision JSON Key "
                        f"{current_index + 1}/"
                        f"{total_keys}"
                    )

                    print(
                        f"Using Vision Model : "
                        f"{self.model}"
                    )

                    # ----------------------------------
                    # Image Part
                    # ----------------------------------

                    image_part = (
                        self._image_part(
                            image_bytes,
                            mime_type
                        )
                    )

                    # ----------------------------------
                    # Gemini JSON Request
                    # ----------------------------------

                    response = (
                        self.client.models.generate_content(
                            model=self.model,
                            contents=[
                                image_part,
                                prompt
                            ],
                            config=(
                                types.GenerateContentConfig(
                                    temperature=0.10,
                                    top_p=0.90,
                                    top_k=20,
                                    max_output_tokens=4096,
                                    candidate_count=1,
                                    response_mime_type=(
                                        "application/json"
                                    )
                                )
                            )
                        )
                    )

                    # ----------------------------------
                    # Extract Response
                    # ----------------------------------

                    text = (
                        self._extract_response_text(
                            response
                        )
                    )

                    if not text:

                        raise RuntimeError(
                            "Gemini Vision returned "
                            "an empty JSON response."
                        )

                    print(
                        "\n========== GEMINI VISION JSON =========="
                    )

                    print(
                        text
                    )

                    print(
                        "Length :",
                        len(text)
                    )

                    print(
                        "Key Used :",
                        current_index + 1
                    )

                    print(
                        "========================================\n"
                    )

                    return text

                except Exception as error:

                    print(
                        "\nGemini Vision JSON Error :",
                        error
                    )

                    # ----------------------------------
                    # Retry With Next Key
                    # ----------------------------------

                    if self._is_retryable_error(
                        error
                    ):

                        print(
                            "Current Gemini Vision API "
                            "key is unavailable."
                        )

                        if self.rotate_api_key():

                            continue

                    # ----------------------------------
                    # Non-retryable Error
                    # ----------------------------------

                    print(
                        "Gemini Vision JSON request failed."
                    )

                    raise

        return ""

    # ======================================================
    # Current API Key
    # ======================================================

    def current_api_key(self) -> str:
        """
        Return the currently active Vision API key.

        Internal use only.
        """

        return self.api_keys[
            self.current_key_index
        ]

    # ======================================================
    # Current API Key Number
    # ======================================================

    def current_api_key_number(self) -> int:
        """
        Return the active API key number.
        """

        return (
            self.current_key_index + 1
        )

    # ======================================================
    # Total API Keys
    # ======================================================

    def total_api_keys(self) -> int:
        """
        Return total configured Vision API keys.
        """

        return len(
            self.api_keys
        )

    # ======================================================
    # Key Status
    # ======================================================

    def key_status(self) -> Dict[str, Any]:
        """
        Return safe Vision API-key information.

        Actual API keys are never returned.
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
                        )
                    }
                    for index, key
                    in enumerate(
                        self.api_keys
                    )
                ]
            }

    # ======================================================
    # Cleanup
    # ======================================================

    def close(self):
        """
        Release Gemini Vision resources.

        No conversation state is stored by this module.
        """

        with self.lock:

            self._closing = True

            self.client = None

            print(
                "Gemini Vision Client shutdown completed."
            )


# ==========================================================
# Compatibility Alias
# ==========================================================

GeminiVisionClient = GeminiVision


# ==========================================================
# Module Export
# ==========================================================

__all__ = [
    "GeminiVision",
    "GeminiVisionClient",
]