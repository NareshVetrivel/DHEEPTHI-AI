"""
DHEEPTHI-AI
Gemini Request Diagnostic - Test 2

Purpose:
    Test all configured Gemini API keys using the same
    model and GenerateContentConfig used by DHEEPTHI.

IMPORTANT:
    API keys are never printed.
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


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
# Test Prompt
# ==========================================================

PROMPT = """
You are DHEEPTHI.

Reply naturally in Tanglish.

User:
what is the time now?

DHEEPTHI:
"""


# ==========================================================
# Error Classification
# ==========================================================

def classify_error(error):
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

    if "timeout" in text:
        return "NETWORK TIMEOUT"

    if "connection" in text:
        return "NETWORK ERROR"

    if "invalid api key" in text:
        return "INVALID API KEY"

    return "OTHER ERROR"


# ==========================================================
# Test One Key
# ==========================================================

def test_key(key_number):

    env_name = f"GEMINI_API_KEY_{key_number}"

    api_key = os.getenv(
        env_name,
        ""
    ).strip()

    print()
    print("=" * 65)
    print(f"Testing Gemini Key {key_number}/4")
    print(f"Model : {MODEL}")
    print("=" * 65)

    if not api_key:

        print("RESULT : NOT CONFIGURED")
        return

    try:

        client = genai.Client(
            api_key=api_key
        )

    except Exception as error:

        print("RESULT : CLIENT CREATION FAILED")
        print("CATEGORY :", classify_error(error))
        return

    try:

        print("Sending DHEEPTHI-style request...")

        response = client.models.generate_content(

            model=MODEL,

            contents=PROMPT,

            config=types.GenerateContentConfig(

                temperature=0.55,

                top_p=0.90,

                top_k=40,

                max_output_tokens=2048,

                candidate_count=1

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

        print()
        print("RESULT : SUCCESS")
        print("RESPONSE :")

        if text:
            print(text[:500])
        else:
            print("(empty response)")

    except Exception as error:

        print()
        print("RESULT : FAILED")
        print(
            "CATEGORY :",
            classify_error(error)
        )
        print(
            "DETAIL : Gemini rejected this request."
        )


# ==========================================================
# Main
# ==========================================================

def main():

    print()
    print("=" * 65)
    print("DHEEPTHI-AI GEMINI REQUEST DIAGNOSTIC")
    print("=" * 65)

    print(
        "Model :",
        MODEL
    )

    print(
        "Config : temperature=0.55 | top_p=0.90 | "
        "top_k=40 | max_output_tokens=2048"
    )

    print(
        "API keys are NOT displayed."
    )

    print()

    for key_number in range(1, 5):

        test_key(
            key_number
        )

    print()
    print("=" * 65)
    print("REQUEST DIAGNOSTIC COMPLETED")
    print("=" * 65)
    print()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()