"""
DHEEPTHI-AI - Gemini Vision API Single Image Test

Purpose:
    Independently benchmark Gemini Vision for:

        - Screen understanding
        - OCR / text extraction
        - Object detection
        - UI element detection
        - Application identification
        - Response speed

IMPORTANT:
    - Existing vision/ files are NOT imported.
    - Existing YOLO model is NOT used.
    - Hugging Face is NOT used.
    - Existing Gemini client is NOT used.
    - Only GEMINI_API_KEY / GEMINI_VISION_API_KEY from .env is used.
    - ONE image is processed per execution.
    - Full results are saved to tests/vision_result/.
    - Terminal output is only a short summary.
    - Gemini structured response_schema is NOT used.
    - Gemini model is read from GEMINI_MODEL in .env.

Usage:

    .env:

        GEMINI_API_KEY=your_key_here
        GEMINI_MODEL=models/gemini-3.5-flash

    Run:

        python tests/test_gemini_vision.py

    Result:

        tests/vision_result/gemini_<image_name>_result.md
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

SAMPLES_DIR = (
    ROOT_DIR
    / "tests"
    / "vision_samples"
)

RESULTS_DIR = (
    ROOT_DIR
    / "tests"
    / "vision_result"
)

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(
    ROOT_DIR / ".env",
    override=True,
)


# ============================================================
# API KEY
# ============================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "",
).strip()

if not GEMINI_API_KEY:
    GEMINI_API_KEY = os.getenv(
        "GEMINI_VISION_API_KEY",
        "",
    ).strip()


# ============================================================
# MODEL
# ============================================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "models/gemini-3.5-flash",
).strip()


# ============================================================
# TEST CONFIGURATION
# ============================================================

# Change only this image name.

TEST_IMAGE = "sample_screen_10.png"


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


# ============================================================
# GENERATION CONFIGURATION
# ============================================================

TEMPERATURE = 0.0

# Increased from 1200 because OCR + UI analysis can require
# more output tokens.
MAX_OUTPUT_TOKENS = 4096


# ============================================================
# RETRY CONFIGURATION
# ============================================================

MAX_REQUEST_RETRIES = 3

RETRY_DELAY_SECONDS = 3.0


# ============================================================
# LOCATION / UI ENUMS
# ============================================================

VALID_LOCATIONS = {
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
}

VALID_UI_TYPES = {
    "button",
    "input",
    "menu",
    "tab",
    "icon",
    "checkbox",
    "window",
    "dialog",
    "image",
    "text",
    "other",
}


# ============================================================
# NORMAL VISION PROMPT
# ============================================================

VISION_PROMPT = """
You are the vision and OCR module of a desktop AI assistant.

Analyze ONLY what is actually visible in the supplied image.

Return ONE valid JSON object and NOTHING else.

Required JSON structure:

{
  "description": "Short factual description of the screen.",
  "application": "",
  "text": [
    {
      "content": "Exact visible text",
      "location": "center"
    }
  ],
  "objects": [
    {
      "label": "Clearly visible object",
      "location": "center"
    }
  ],
  "ui_elements": [
    {
      "type": "button",
      "label": "Visible label",
      "location": "center"
    }
  ]
}

Rules:

- Do not guess.
- Do not hallucinate.
- Extract only visible text.
- Preserve spelling exactly.
- Preserve numbers exactly.
- Preserve punctuation when visible.
- Do not translate text.
- Do not summarize OCR text.
- If application is unclear, use "".
- If no text exists, use [].
- If no objects exist, use [].
- If no UI elements exist, use [].
- Use only these locations:
  top-left, top, top-right, left, center, right,
  bottom-left, bottom, bottom-right.
- Use only these UI types:
  button, input, menu, tab, icon, checkbox,
  window, dialog, image, text, other.

Accuracy is more important than completeness.

Keep descriptions short.
Do not include unnecessary explanations.
"""


# ============================================================
# COMPACT RETRY PROMPT
# ============================================================

COMPACT_VISION_PROMPT = """
Analyze this screenshot for a desktop AI assistant.

Return ONLY one valid JSON object.

Use exactly:

{
  "description": "short factual screen description",
  "application": "",
  "text": [{"content": "exact visible text", "location": "center"}],
  "objects": [{"label": "visible object", "location": "center"}],
  "ui_elements": [{"type": "button", "label": "visible label", "location": "center"}]
}

STRICT RULES:

- JSON only.
- No markdown.
- No explanation.
- No code fence.
- No comments.
- Do not guess.
- Do not hallucinate.
- Preserve visible text exactly.
- If unclear, omit the item.
- If no text, use [].
- If no objects, use [].
- If no UI elements, use [].
- Keep the description short.
- Keep every field concise.

Locations:
top-left, top, top-right, left, center, right,
bottom-left, bottom, bottom-right.

UI types:
button, input, menu, tab, icon, checkbox,
window, dialog, image, text, other.
"""


# ============================================================
# IMAGE HELPERS
# ============================================================

def get_test_image() -> Path | None:
    """
    Return the single image selected by TEST_IMAGE.
    """

    image_name = TEST_IMAGE.strip()

    if not image_name:
        return None

    image_path = SAMPLES_DIR / image_name

    if not image_path.exists():
        return None

    if not image_path.is_file():
        return None

    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None

    return image_path


def load_image_bytes(
    image_path: Path,
) -> tuple[bytes, str]:
    """
    Read image bytes and determine MIME type.
    """

    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(
        image_path.suffix.lower(),
        "image/png",
    )

    return (
        image_path.read_bytes(),
        mime_type,
    )


# ============================================================
# JSON HELPERS
# ============================================================

def clean_json_response(
    text: str,
) -> str:
    """
    Remove common formatting accidentally added by Gemini.
    """

    if not text:
        return ""

    text = text.strip()

    # Remove markdown fences.

    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        while lines and not lines[-1].strip():
            lines.pop()

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(
            lines
        ).strip()

    # Remove leading json marker.

    if text.lower().startswith("json"):

        remaining = text[4:]

        if (
            not remaining
            or remaining[0] in "\r\n "
        ):
            text = remaining.lstrip()

    return text.strip()


def find_json_object(
    text: str,
) -> str:
    """
    Extract the first complete JSON object from arbitrary text.
    """

    cleaned = clean_json_response(text)

    if not cleaned:
        raise ValueError(
            "Gemini returned an empty response."
        )

    # Direct JSON.

    if (
        cleaned.startswith("{")
        and cleaned.endswith("}")
    ):
        return cleaned

    start = cleaned.find("{")

    if start == -1:
        raise ValueError(
            "No JSON object found in Gemini response."
        )

    decoder = json.JSONDecoder()

    try:

        parsed, end_index = decoder.raw_decode(
            cleaned[start:]
        )

        if isinstance(
            parsed,
            dict,
        ):
            return cleaned[
                start:start + end_index
            ]

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Gemini returned content, but the JSON "
            "could not be decoded."
        ) from exc

    raise ValueError(
        "Gemini response did not contain "
        "a valid JSON object."
    )


# ============================================================
# JSON REPAIR
# ============================================================

def repair_truncated_json(
    text: str,
) -> str:
    """
    Attempt to repair a truncated JSON object.

    This is a last-resort parser for cases where Gemini stops
    before completing the JSON response.

    It does NOT invent OCR text.

    It only closes JSON strings, arrays and objects when the
    existing response structure allows it.
    """

    cleaned = clean_json_response(text)

    if not cleaned:
        raise ValueError(
            "Cannot repair empty Gemini response."
        )

    start = cleaned.find("{")

    if start == -1:
        raise ValueError(
            "Cannot repair response without a JSON object."
        )

    candidate = cleaned[start:]

    # --------------------------------------------------------
    # First attempt normal decoding.
    # --------------------------------------------------------

    try:

        parsed = json.loads(candidate)

        if isinstance(parsed, dict):
            return json.dumps(
                parsed,
                ensure_ascii=False,
            )

    except Exception:
        pass

    # --------------------------------------------------------
    # State tracking.
    # --------------------------------------------------------

    in_string = False
    escaped = False

    stack: list[str] = []

    repaired_chars: list[str] = []

    for char in candidate:

        repaired_chars.append(char)

        if escaped:

            escaped = False
            continue

        if char == "\\" and in_string:

            escaped = True
            continue

        if char == '"':

            in_string = not in_string
            continue

        if in_string:
            continue

        if char in "{[":
            stack.append(char)

        elif char == "}":

            if stack and stack[-1] == "{":
                stack.pop()

        elif char == "]":

            if stack and stack[-1] == "[":
                stack.pop()

    # --------------------------------------------------------
    # If a string is still open, close it.
    # --------------------------------------------------------

    if in_string:

        repaired_chars.append('"')

    # --------------------------------------------------------
    # Remove trailing comma.
    # --------------------------------------------------------

    repaired = "".join(
        repaired_chars
    ).rstrip()

    while repaired.endswith(","):

        repaired = repaired[:-1].rstrip()

    # --------------------------------------------------------
    # Remove an incomplete final object/array entry.
    #
    # Example:
    #
    # "text": [
    #   {"content": "hello",
    #
    # We remove the unfinished item rather than inventing it.
    # --------------------------------------------------------

    if repaired.endswith(":"):
        repaired = repaired[:-1].rstrip()

    # --------------------------------------------------------
    # Close open containers.
    # --------------------------------------------------------

    for opening in reversed(stack):

        if opening == "[":
            repaired += "]"

        elif opening == "{":
            repaired += "}"

    # --------------------------------------------------------
    # Validate repaired JSON.
    # --------------------------------------------------------

    try:

        parsed = json.loads(
            repaired
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Gemini returned an incomplete JSON object."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):

        raise ValueError(
            "Repaired Gemini response is not a JSON object."
        )

    return repaired


def parse_json_response(
    text: str,
) -> dict[str, Any]:
    """
    Parse Gemini response.

    Order:

        1. Normal JSON extraction
        2. Truncated JSON repair
        3. Raise clear error
    """

    try:

        json_text = find_json_object(
            text
        )

        parsed = json.loads(
            json_text
        )

        if isinstance(
            parsed,
            dict,
        ):
            return parsed

    except Exception as first_error:

        try:

            repaired_text = repair_truncated_json(
                text
            )

            parsed = json.loads(
                repaired_text
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except Exception as repair_error:

            raise ValueError(
                "Gemini returned content, but valid JSON "
                "could not be obtained. "
                f"Initial error: {first_error}. "
                f"Repair error: {repair_error}"
            ) from repair_error

    raise ValueError(
        "Gemini response is not a JSON object."
    )


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def normalize_location(
    location: Any,
) -> str:
    """
    Normalize location to the allowed values.
    """

    if not isinstance(
        location,
        str,
    ):
        return "center"

    location = location.strip().lower()

    if location not in VALID_LOCATIONS:
        return "center"

    return location


def normalize_result(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize Gemini's response into the expected structure.
    """

    description = result.get(
        "description",
        "",
    )

    application = result.get(
        "application",
        "",
    )

    text = result.get(
        "text",
        [],
    )

    objects = result.get(
        "objects",
        [],
    )

    ui_elements = result.get(
        "ui_elements",
        [],
    )

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    if not isinstance(
        description,
        str,
    ):
        description = str(
            description
        )

    description = description.strip()

    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------

    if application is None:
        application = ""

    elif not isinstance(
        application,
        str,
    ):
        application = str(
            application
        )

    application = application.strip()

    # --------------------------------------------------------
    # Ensure lists.
    # --------------------------------------------------------

    if not isinstance(
        text,
        list,
    ):
        text = []

    if not isinstance(
        objects,
        list,
    ):
        objects = []

    if not isinstance(
        ui_elements,
        list,
    ):
        ui_elements = []

    # --------------------------------------------------------
    # Normalize text.
    # --------------------------------------------------------

    normalized_text: list[
        dict[str, Any]
    ] = []

    for item in text:

        if not isinstance(
            item,
            dict,
        ):
            continue

        content = item.get(
            "content",
            "",
        )

        location = item.get(
            "location",
            "center",
        )

        if not isinstance(
            content,
            str,
        ):
            content = str(
                content
            )

        content = content.strip()

        if not content:
            continue

        normalized_text.append(
            {
                "content": content,
                "location": normalize_location(
                    location
                ),
            }
        )

    # --------------------------------------------------------
    # Normalize objects.
    # --------------------------------------------------------

    normalized_objects: list[
        dict[str, Any]
    ] = []

    for item in objects:

        if not isinstance(
            item,
            dict,
        ):
            continue

        label = item.get(
            "label",
            "",
        )

        location = item.get(
            "location",
            "center",
        )

        if not isinstance(
            label,
            str,
        ):
            label = str(
                label
            )

        label = label.strip()

        if not label:
            continue

        normalized_objects.append(
            {
                "label": label,
                "location": normalize_location(
                    location
                ),
            }
        )

    # --------------------------------------------------------
    # Normalize UI elements.
    # --------------------------------------------------------

    normalized_ui_elements: list[
        dict[str, Any]
    ] = []

    for item in ui_elements:

        if not isinstance(
            item,
            dict,
        ):
            continue

        element_type = item.get(
            "type",
            "other",
        )

        label = item.get(
            "label",
            "",
        )

        location = item.get(
            "location",
            "center",
        )

        if not isinstance(
            element_type,
            str,
        ):
            element_type = "other"

        element_type = (
            element_type.strip().lower()
        )

        if element_type not in VALID_UI_TYPES:
            element_type = "other"

        if label is None:
            label = ""

        elif not isinstance(
            label,
            str,
        ):
            label = str(
                label
            )

        normalized_ui_elements.append(
            {
                "type": element_type,
                "label": label.strip(),
                "location": normalize_location(
                    location
                ),
            }
        )

    return {
        "description": description,
        "application": application,
        "text": normalized_text,
        "objects": normalized_objects,
        "ui_elements": normalized_ui_elements,
    }


# ============================================================
# OCR QUALITY
# ============================================================

def calculate_text_quality(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate structural text-output quality.

    IMPORTANT:

        This is NOT true OCR accuracy.

    Ground-truth OCR accuracy requires manually verified
    reference text.
    """

    items = result.get(
        "text",
        [],
    )

    if not isinstance(
        items,
        list,
    ):

        return {
            "status": "invalid",
            "score": 0.0,
            "reason": "text field is not a list",
        }

    if not items:

        return {
            "status": "no_text_detected",
            "score": None,
            "reason": "No text returned by Gemini.",
        }

    valid = 0
    invalid = 0

    text_values: list[str] = []

    for item in items:

        if not isinstance(
            item,
            dict,
        ):

            invalid += 1
            continue

        content = item.get(
            "content"
        )

        location = item.get(
            "location"
        )

        if (
            not isinstance(
                content,
                str,
            )
            or not content.strip()
        ):

            invalid += 1
            continue

        if not isinstance(
            location,
            str,
        ):

            invalid += 1
            continue

        valid += 1

        text_values.append(
            content.strip().lower()
        )

    duplicate_count = (
        len(text_values)
        - len(set(text_values))
    )

    structural_score = (
        valid / len(items)
    ) * 100.0

    return {
        "status": "text_detected",
        "score": round(
            structural_score,
            2,
        ),
        "valid_text_items": valid,
        "invalid_text_items": invalid,
        "duplicate_text_items": duplicate_count,
        "note": (
            "Structural quality only; "
            "not true OCR accuracy."
        ),
    }


# ============================================================
# GEMINI RESPONSE METADATA
# ============================================================

def get_finish_reason(
    response: Any,
) -> str | None:
    """
    Safely retrieve Gemini finish reason.
    """

    try:

        candidates = getattr(
            response,
            "candidates",
            None,
        )

        if not candidates:
            return None

        first_candidate = candidates[0]

        reason = getattr(
            first_candidate,
            "finish_reason",
            None,
        )

        if reason is None:
            return None

        return str(
            reason
        )

    except Exception:
        return None


def get_usage_metadata(
    response: Any,
) -> dict[str, Any]:
    """
    Safely extract token usage.
    """

    usage_metadata = getattr(
        response,
        "usage_metadata",
        None,
    )

    if usage_metadata is None:
        return {}

    return {
        "prompt_token_count": getattr(
            usage_metadata,
            "prompt_token_count",
            None,
        ),
        "candidates_token_count": getattr(
            usage_metadata,
            "candidates_token_count",
            None,
        ),
        "total_token_count": getattr(
            usage_metadata,
            "total_token_count",
            None,
        ),
    }


# ============================================================
# ERROR CLASSIFICATION
# ============================================================

def is_retryable_error(
    exc: Exception,
) -> bool:
    """
    Identify temporary Gemini errors.
    """

    error_text = str(
        exc
    ).lower()

    retryable_markers = (
        "503",
        "unavailable",
        "high demand",
        "temporarily unavailable",
        "service unavailable",
        "overloaded",
        "deadline exceeded",
        "429",
        "resource exhausted",
        "500",
        "internal server error",
    )

    return any(
        marker in error_text
        for marker in retryable_markers
    )


def is_json_format_error(
    exc: Exception,
) -> bool:
    """
    Identify malformed/incomplete JSON errors.
    """

    error_text = str(
        exc
    ).lower()

    markers = (
        "json",
        "incomplete json",
        "could not be decoded",
        "json object",
        "jsondecodeerror",
        "not a json",
    )

    return any(
        marker in error_text
        for marker in markers
    )


# ============================================================
# GEMINI REQUEST
# ============================================================

def send_gemini_request(
    client: genai.Client,
    image_part: types.Part,
    prompt: str,
    max_output_tokens: int,
) -> Any:
    """
    Send one Gemini Vision request.
    """

    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            image_part,
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=TEMPERATURE,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
        ),
    )


# ============================================================
# GEMINI VISION ANALYSIS
# ============================================================

def analyze_image(
    client: genai.Client,
    image_path: Path,
) -> dict[str, Any]:
    """
    Process exactly one image with Gemini Vision.

    Strategy:

        Attempt 1:
            Normal detailed JSON request.

        Attempt 2:
            Compact JSON request if parsing fails.

        Attempt 3:
            Compact JSON request again.

    Temporary server errors are retried separately.

    Truncated JSON is also repaired as a final safety measure.
    """

    image_bytes, mime_type = load_image_bytes(
        image_path
    )

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    prompts = [
        VISION_PROMPT,
        COMPACT_VISION_PROMPT,
        COMPACT_VISION_PROMPT,
    ]

    token_limits = [
        MAX_OUTPUT_TOKENS,
        MAX_OUTPUT_TOKENS,
        MAX_OUTPUT_TOKENS,
    ]

    last_exception: Exception | None = None

    total_attempts = 0

    for prompt_index, prompt in enumerate(
        prompts,
        start=1,
    ):

        request_attempt = 0

        while request_attempt < MAX_REQUEST_RETRIES:

            request_attempt += 1
            total_attempts += 1

            start_time = time.perf_counter()

            try:

                response = send_gemini_request(
                    client=client,
                    image_part=image_part,
                    prompt=prompt,
                    max_output_tokens=token_limits[
                        prompt_index - 1
                    ],
                )

                end_time = time.perf_counter()

                latency = (
                    end_time
                    - start_time
                )

                # ------------------------------------------------
                # Raw response
                # ------------------------------------------------

                raw_response = ""

                try:

                    raw_response = (
                        response.text
                        if response.text
                        else ""
                    )

                except Exception:
                    raw_response = ""

                finish_reason = get_finish_reason(
                    response
                )

                usage = get_usage_metadata(
                    response
                )

                if not raw_response.strip():

                    raise ValueError(
                        "Gemini returned an empty response."
                    )

                # ------------------------------------------------
                # Parse JSON
                # ------------------------------------------------

                try:

                    parsed_result = parse_json_response(
                        raw_response
                    )

                except Exception as json_error:

                    # ------------------------------------------------
                    # If Gemini stopped because of output limit,
                    # immediately use the compact prompt.
                    # ------------------------------------------------

                    if prompt_index < len(prompts):

                        print(
                            "Gemini returned non-standard "
                            "or incomplete JSON. "
                            f"Requesting compact JSON retry "
                            f"({prompt_index}/"
                            f"{len(prompts) - 1})..."
                        )

                        last_exception = json_error

                        break

                    raise json_error

                # ------------------------------------------------
                # Normalize
                # ------------------------------------------------

                normalized_result = normalize_result(
                    parsed_result
                )

                text_quality = calculate_text_quality(
                    normalized_result
                )

                return {
                    "success": True,
                    "provider": "Google Gemini",
                    "model": GEMINI_MODEL,
                    "image": image_path.name,
                    "latency_seconds": round(
                        latency,
                        4,
                    ),
                    "result": normalized_result,
                    "text_quality": text_quality,
                    "usage": usage,
                    "finish_reason": finish_reason,
                    "raw_response": raw_response,
                    "attempt": total_attempts,
                }

            except Exception as exc:

                last_exception = exc

                # ------------------------------------------------
                # JSON errors:
                #
                # Move directly to compact prompt.
                # ------------------------------------------------

                if is_json_format_error(
                    exc
                ):

                    if prompt_index < len(prompts):

                        print(
                            "Gemini returned non-standard "
                            "JSON. "
                            "Requesting compact JSON retry "
                            f"({prompt_index}/"
                            f"{len(prompts) - 1})..."
                        )

                        break

                    # ------------------------------------------------
                    # Last JSON attempt:
                    #
                    # Try a final local repair.
                    # ------------------------------------------------

                    try:

                        repaired_result = parse_json_response(
                            raw_response
                        )

                        normalized_result = normalize_result(
                            repaired_result
                        )

                        text_quality = (
                            calculate_text_quality(
                                normalized_result
                            )
                        )

                        return {
                            "success": True,
                            "provider": "Google Gemini",
                            "model": GEMINI_MODEL,
                            "image": image_path.name,
                            "latency_seconds": round(
                                time.perf_counter()
                                - start_time,
                                4,
                            ),
                            "result": normalized_result,
                            "text_quality": text_quality,
                            "usage": get_usage_metadata(
                                response
                            ),
                            "finish_reason": (
                                get_finish_reason(
                                    response
                                )
                            ),
                            "raw_response": raw_response,
                            "attempt": total_attempts,
                            "json_repaired": True,
                        }

                    except Exception:
                        raise

                # ------------------------------------------------
                # Temporary API errors.
                # ------------------------------------------------

                if is_retryable_error(
                    exc
                ):

                    if (
                        request_attempt
                        < MAX_REQUEST_RETRIES
                    ):

                        print(
                            "Temporary Gemini error "
                            f"(request retry "
                            f"{request_attempt}/"
                            f"{MAX_REQUEST_RETRIES}): "
                            f"{type(exc).__name__}"
                        )

                        print(
                            f"Retrying in "
                            f"{RETRY_DELAY_SECONDS:.1f} "
                            f"seconds..."
                        )

                        time.sleep(
                            RETRY_DELAY_SECONDS
                        )

                        continue

                # ------------------------------------------------
                # Permanent error.
                # ------------------------------------------------

                raise

    # ========================================================
    # FINAL FALLBACK
    # ========================================================

    if last_exception is not None:

        raise ValueError(
            "Gemini Vision could not produce a valid "
            "structured response after retries. "
            f"Last error: {last_exception}"
        )

    raise RuntimeError(
        "Gemini Vision request failed unexpectedly."
    )


# ============================================================
# RESULT FILE
# ============================================================

def get_result_file(
    image_path: Path,
) -> Path:
    """
    Create:

        gemini_<image_name>_result.md
    """

    safe_name = (
        image_path.stem
        .replace(
            " ",
            "_",
        )
    )

    return (
        RESULTS_DIR
        / f"gemini_{safe_name}_result.md"
    )


# ============================================================
# MARKDOWN REPORT
# ============================================================

def build_markdown_report(
    result: dict[str, Any],
) -> str:
    """
    Build complete benchmark report.
    """

    image_name = result.get(
        "image",
        TEST_IMAGE,
    )

    model = result.get(
        "model",
        GEMINI_MODEL,
    )

    latency = result.get(
        "latency_seconds"
    )

    lines: list[str] = []

    lines.append(
        f"# Gemini Vision Result — {image_name}"
    )

    lines.append("")

    # ========================================================
    # TEST INFORMATION
    # ========================================================

    lines.append(
        "## Test Information"
    )

    lines.append("")

    lines.append(
        f"- **Provider:** "
        f"{result.get('provider', 'Google Gemini')}"
    )

    lines.append(
        f"- **Model:** `{model}`"
    )

    lines.append(
        f"- **Image:** `{image_name}`"
    )

    if latency is not None:

        lines.append(
            f"- **Response Time:** "
            f"`{latency:.4f} seconds`"
        )

    else:

        lines.append(
            "- **Response Time:** `N/A`"
        )

    status = (
        "SUCCESS"
        if result.get("success")
        else "FAILED"
    )

    lines.append(
        f"- **Status:** `{status}`"
    )

    if result.get("attempt") is not None:

        lines.append(
            f"- **Request Attempts:** "
            f"`{result.get('attempt')}`"
        )

    if result.get("finish_reason"):

        lines.append(
            f"- **Finish Reason:** "
            f"`{result.get('finish_reason')}`"
        )

    if result.get("json_repaired"):

        lines.append(
            "- **JSON Repair:** `Used`"
        )

    lines.append("")

    # ========================================================
    # ERROR
    # ========================================================

    if not result.get("success"):

        lines.append(
            "## Error"
        )

        lines.append("")

        lines.append(
            "```text"
        )

        lines.append(
            str(
                result.get(
                    "error",
                    "Unknown error",
                )
            )
        )

        lines.append(
            "```"
        )

        lines.append("")

        raw = result.get(
            "raw_response",
            "",
        )

        if raw:

            lines.append(
                "## Raw Gemini Response"
            )

            lines.append("")

            lines.append(
                "```text"
            )

            lines.append(
                raw
            )

            lines.append(
                "```"
            )

            lines.append("")

        return "\n".join(
            lines
        )

    vision_result = result.get(
        "result",
        {},
    )

    # ========================================================
    # SCREEN DESCRIPTION
    # ========================================================

    lines.append(
        "## Screen Description"
    )

    lines.append("")

    lines.append(
        str(
            vision_result.get(
                "description",
                "",
            )
        )
    )

    lines.append("")

    # ========================================================
    # APPLICATION
    # ========================================================

    lines.append(
        "## Application"
    )

    lines.append("")

    application = vision_result.get(
        "application"
    )

    if application:

        lines.append(
            f"`{application}`"
        )

    else:

        lines.append(
            "`Not confidently identified`"
        )

    lines.append("")

    # ========================================================
    # OCR
    # ========================================================

    lines.append(
        "## Extracted Text / OCR"
    )

    lines.append("")

    text_items = vision_result.get(
        "text",
        [],
    )

    if (
        isinstance(
            text_items,
            list,
        )
        and text_items
    ):

        for index, item in enumerate(
            text_items,
            start=1,
        ):

            if isinstance(
                item,
                dict,
            ):

                content = item.get(
                    "content",
                    "",
                )

                location = item.get(
                    "location",
                    "",
                )

                lines.append(
                    f"{index}. **{content}** "
                    f"— `{location}`"
                )

            else:

                lines.append(
                    f"{index}. {item}"
                )

    else:

        lines.append(
            "No text detected."
        )

    lines.append("")

    # ========================================================
    # TEXT QUALITY
    # ========================================================

    lines.append(
        "## Text Quality"
    )

    lines.append("")

    text_quality = result.get(
        "text_quality",
        {},
    )

    if isinstance(
        text_quality,
        dict,
    ):

        for key, value in text_quality.items():

            lines.append(
                f"- **{key}:** {value}"
            )

    lines.append("")

    # ========================================================
    # OBJECTS
    # ========================================================

    lines.append(
        "## Objects"
    )

    lines.append("")

    objects = vision_result.get(
        "objects",
        [],
    )

    if (
        isinstance(
            objects,
            list,
        )
        and objects
    ):

        for index, item in enumerate(
            objects,
            start=1,
        ):

            if isinstance(
                item,
                dict,
            ):

                label = item.get(
                    "label",
                    "",
                )

                location = item.get(
                    "location",
                    "",
                )

                lines.append(
                    f"{index}. **{label}** "
                    f"— `{location}`"
                )

            else:

                lines.append(
                    f"{index}. {item}"
                )

    else:

        lines.append(
            "No objects detected."
        )

    lines.append("")

    # ========================================================
    # UI ELEMENTS
    # ========================================================

    lines.append(
        "## UI Elements"
    )

    lines.append("")

    ui_elements = vision_result.get(
        "ui_elements",
        [],
    )

    if (
        isinstance(
            ui_elements,
            list,
        )
        and ui_elements
    ):

        for index, item in enumerate(
            ui_elements,
            start=1,
        ):

            if isinstance(
                item,
                dict,
            ):

                element_type = item.get(
                    "type",
                    "other",
                )

                label = item.get(
                    "label",
                    "",
                )

                location = item.get(
                    "location",
                    "",
                )

                lines.append(
                    f"{index}. "
                    f"**{element_type}** "
                    f"— `{label}` "
                    f"— `{location}`"
                )

            else:

                lines.append(
                    f"{index}. {item}"
                )

    else:

        lines.append(
            "No UI elements detected."
        )

    lines.append("")

    # ========================================================
    # TOKEN USAGE
    # ========================================================

    usage = result.get(
        "usage",
        {},
    )

    if usage:

        lines.append(
            "## Token Usage"
        )

        lines.append("")

        for key, value in usage.items():

            lines.append(
                f"- **{key}:** {value}"
            )

        lines.append("")

    # ========================================================
    # RAW RESPONSE
    # ========================================================

    lines.append(
        "## Raw Gemini Response"
    )

    lines.append("")

    lines.append(
        "```json"
    )

    lines.append(
        result.get(
            "raw_response",
            "",
        )
    )

    lines.append(
        "```"
    )

    lines.append("")

    # ========================================================
    # PARSED RESULT
    # ========================================================

    lines.append(
        "## Parsed Result"
    )

    lines.append("")

    lines.append(
        "```json"
    )

    lines.append(
        json.dumps(
            vision_result,
            indent=2,
            ensure_ascii=False,
        )
    )

    lines.append(
        "```"
    )

    lines.append("")

    return "\n".join(
        lines
    )


# ============================================================
# SAVE REPORT
# ============================================================

def save_report(
    result: dict[str, Any],
    image_path: Path,
) -> Path:
    """
    Save complete Markdown report.
    """

    output_file = get_result_file(
        image_path
    )

    report = build_markdown_report(
        result
    )

    output_file.write_text(
        report,
        encoding="utf-8",
    )

    return output_file


# ============================================================
# TERMINAL SUMMARY
# ============================================================

def print_terminal_summary(
    result: dict[str, Any],
    output_file: Path,
) -> None:
    """
    Print compact result information.
    """

    print()

    print(
        "=" * 78
    )

    print(
        "GEMINI VISION TEST RESULT"
    )

    print(
        "=" * 78
    )

    print(
        f"Image      : "
        f"{result.get('image')}"
    )

    print(
        f"Model      : "
        f"{result.get('model')}"
    )

    latency = result.get(
        "latency_seconds"
    )

    if latency is not None:

        print(
            f"Response   : "
            f"{latency:.4f} seconds"
        )

    if result.get(
        "success"
    ):

        print(
            "Status     : SUCCESS"
        )

        vision_result = result.get(
            "result",
            {},
        )

        application = vision_result.get(
            "application"
        )

        text_items = vision_result.get(
            "text",
            [],
        )

        objects = vision_result.get(
            "objects",
            [],
        )

        ui_elements = vision_result.get(
            "ui_elements",
            [],
        )

        print(
            "Application: "
            f"{application if application else 'Not identified'}"
        )

        print(
            "Text items : "
            f"{len(text_items) if isinstance(text_items, list) else 0}"
        )

        print(
            "Objects    : "
            f"{len(objects) if isinstance(objects, list) else 0}"
        )

        print(
            "UI elements: "
            f"{len(ui_elements) if isinstance(ui_elements, list) else 0}"
        )

        text_quality = result.get(
            "text_quality",
            {},
        )

        if text_quality.get(
            "score"
        ) is not None:

            print(
                "Text score : "
                f"{text_quality['score']:.2f}% "
                "(structural only)"
            )

        usage = result.get(
            "usage",
            {},
        )

        total_tokens = usage.get(
            "total_token_count"
        )

        if total_tokens is not None:

            print(
                "Tokens     : "
                f"{total_tokens}"
            )

        if result.get(
            "json_repaired"
        ):

            print(
                "JSON       : "
                "Repaired successfully"
            )

    else:

        print(
            "Status     : FAILED"
        )

        print(
            f"Error      : "
            f"{result.get('error')}"
        )

        if result.get(
            "raw_response"
        ):

            print(
                "Raw response saved "
                "to the report."
            )

    print()

    print(
        "FULL REPORT:"
    )

    print(
        output_file
    )

    print(
        "=" * 78
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    print()

    print(
        "#" * 78
    )

    print(
        "DHEEPTHI-AI - "
        "GEMINI VISION SINGLE IMAGE TEST"
    )

    print(
        "#" * 78
    )

    # ========================================================
    # API KEY CHECK
    # ========================================================

    if not GEMINI_API_KEY:

        print()

        print(
            "ERROR: Gemini API key is missing."
        )

        print()

        print(
            "Add this to .env:"
        )

        print()

        print(
            "GEMINI_API_KEY=your_key_here"
        )

        print()

        print(
            "or:"
        )

        print()

        print(
            "GEMINI_VISION_API_KEY=your_key_here"
        )

        return 1

    # ========================================================
    # MODEL CHECK
    # ========================================================

    if not GEMINI_MODEL:

        print()

        print(
            "ERROR: GEMINI_MODEL is empty."
        )

        print()

        print(
            "Expected:"
        )

        print(
            "GEMINI_MODEL=models/gemini-3.5-flash"
        )

        return 1

    # ========================================================
    # IMAGE CHECK
    # ========================================================

    image_path = get_test_image()

    if image_path is None:

        print()

        print(
            "ERROR: Test image was not found."
        )

        print()

        print(
            f"Selected image : "
            f"{TEST_IMAGE}"
        )

        print(
            f"Image folder   : "
            f"{SAMPLES_DIR}"
        )

        print()

        print(
            "Change TEST_IMAGE "
            "at the top of this file."
        )

        print()

        print(
            'Example: TEST_IMAGE = '
            '"sample_screen_2.png"'
        )

        return 1

    # ========================================================
    # CLIENT
    # ========================================================

    try:

        client = genai.Client(
            api_key=GEMINI_API_KEY,
        )

    except Exception as exc:

        print()

        print(
            "ERROR: Could not initialize Gemini client."
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1

    # ========================================================
    # START TEST
    # ========================================================

    print()

    print(
        f"Image : "
        f"{image_path.name}"
    )

    print(
        f"Model : "
        f"{GEMINI_MODEL}"
    )

    print()

    print(
        "Sending image to Gemini Vision..."
    )

    try:

        result = analyze_image(
            client=client,
            image_path=image_path,
        )

    except Exception as exc:

        result = {
            "success": False,
            "provider": "Google Gemini",
            "model": GEMINI_MODEL,
            "image": image_path.name,
            "latency_seconds": None,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
            "raw_response": "",
            "reasoning": "",
        }

    # ========================================================
    # SAVE REPORT
    # ========================================================

    output_file = save_report(
        result=result,
        image_path=image_path,
    )

    # ========================================================
    # TERMINAL SUMMARY
    # ========================================================

    print_terminal_summary(
        result=result,
        output_file=output_file,
    )

    return (
        0
        if result.get("success")
        else 1
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )