"""
DHEEPTHI-AI
Gemini API Key Diagnostic Test

Purpose
-------
Tests Gemini API Keys 1-4 individually using the SAME model.

IMPORTANT
---------
- API keys are NEVER printed.
- Only key number, model, HTTP/status category and result are shown.
- This test does NOT modify DHEEPTHI-AI configuration.
"""

import os

from dotenv import load_dotenv
from google import genai


# ==========================================================
# Load Environment
# ==========================================================

load_dotenv()


# ==========================================================
# Configuration
# ==========================================================

MODEL = os.getenv(
    "GEMINI_MODEL",
    "models/gemini-3.5-flash"
).strip()


# ==========================================================
# Safe Error Classification
# ==========================================================

def classify_error(error):
    """
    Convert Gemini error into a simple diagnostic category.
    """

    text = str(error).lower()

    if "401" in text:
        return "401 AUTHENTICATION"

    if "403" in text:
        return "403 PERMISSION"

    if "429" in text:
        return "429 QUOTA / RATE LIMIT"

    if "503" in text:
        return "503 SERVICE UNAVAILABLE"

    if "502" in text:
        return "502 BAD GATEWAY"

    if "504" in text:
        return "504 GATEWAY TIMEOUT"

    if "500" in text:
        return "500 SERVER ERROR"

    if (
        "timeout" in text
        or "timed out" in text
    ):
        return "NETWORK TIMEOUT"

    if (
        "connection" in text
        or "network" in text
    ):
        return "NETWORK ERROR"

    if (
        "invalid api key" in text
        or "api key not valid" in text
    ):
        return "INVALID API KEY"

    return "OTHER ERROR"


# ==========================================================
# Test One Key
# ==========================================================

def test_key(key_number):
    """
    Test one Gemini API key.

    The actual key value is never printed.
    """

    env_name = f"GEMINI_API_KEY_{key_number}"

    api_key = os.getenv(
        env_name,
        ""
    ).strip()

    print()
    print("=" * 60)
    print(f"Testing Gemini Key {key_number}/4")
    print(f"Model : {MODEL}")
    print("=" * 60)

    # ------------------------------------------------------
    # Check configuration
    # ------------------------------------------------------

    if not api_key:

        print("RESULT : NOT CONFIGURED")
        return

    # ------------------------------------------------------
    # Create client
    # ------------------------------------------------------

    try:

        client = genai.Client(
            api_key=api_key
        )

    except Exception as error:

        print(
            "RESULT : CLIENT CREATION FAILED"
        )

        print(
            "CATEGORY :",
            classify_error(error)
        )

        return

    # ------------------------------------------------------
    # Send minimal request
    # ------------------------------------------------------

    try:

        response = (
            client.models.generate_content(
                model=MODEL,
                contents="Reply with exactly: OK"
            )
        )

        text = ""

        if response is not None:

            if hasattr(
                response,
                "text"
            ):

                text = (
                    response.text
                    or ""
                ).strip()

        print("RESULT : SUCCESS")
        print(
            "RESPONSE :",
            text[:100]
        )

    except Exception as error:

        print("RESULT : FAILED")
        print(
            "CATEGORY :",
            classify_error(error)
        )

        # Print only the error category,
        # NOT the complete error because
        # some SDK errors may contain sensitive data.

        print(
            "DETAIL : Gemini request was rejected."
        )


# ==========================================================
# Main
# ==========================================================

def main():

    print()
    print("=" * 60)
    print("DHEEPTHI-AI GEMINI API KEY DIAGNOSTIC")
    print("=" * 60)

    print(
        "Model being tested:",
        MODEL
    )

    print(
        "API key values will NOT be displayed."
    )

    print(
        "Each key is tested independently."
    )

    print()

    # ------------------------------------------------------
    # Test all four keys
    # ------------------------------------------------------

    for key_number in range(1, 5):

        test_key(
            key_number
        )

    # ------------------------------------------------------
    # Finish
    # ------------------------------------------------------

    print()
    print("=" * 60)
    print("DIAGNOSTIC TEST COMPLETED")
    print("=" * 60)
    print()


if __name__ == "__main__":

    main()