"""
DHEEPTHI-AI
Gemini Prompt Size Diagnostic

Purpose
-------
Find whether Gemini API Key 1 starts returning 503 when the
request/prompt becomes larger.

Keys 1 and 2 are tested with the SAME prompts and SAME config.

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
# Prompts
# ==========================================================

PROMPTS = [

    (
        "TEST 1 - Tiny",
        "Reply with exactly: OK"
    ),

    (
        "TEST 2 - Small",
        """
You are DHEEPTHI, a personal desktop assistant.

Always respond naturally in Tanglish.

User:
Who created you?

DHEEPTHI:
"""
    ),

    (
        "TEST 3 - Medium",
        """
You are DHEEPTHI.

Your role is your personal desktop assistant.

Always respond in natural conversational Tanglish.
Do not use Tamil script.
Be friendly, clear, direct and helpful.

Your name is DHEEPTHI.

If the user asks who created you, say:
"Enna Naresh um Ragavendhiran um create pannanga da."

If the user asks your name, identify yourself as:
DHEEPTHI, your personal desktop assistant.

Use relevant context when available.
Do not invent facts.
Do not claim actions were completed unless they
were actually completed.

User:
Who created you?

DHEEPTHI:
"""
    ),

    (
        "TEST 4 - Large",
        """
You are DHEEPTHI.

Your role is your personal desktop assistant.

==================================================
IDENTITY
==================================================

Your name is DHEEPTHI.

Never mention a version number as part of your name.

If the user asks:

"What is your name?"

Answer:

"I am DHEEPTHI, your personal desktop assistant."

If the user asks:

"Who are you?"

Answer naturally in Tanglish:

"Naan DHEEPTHI, your personal desktop assistant da."

==================================================
CREATOR
==================================================

DHEEPTHI was created by:

Naresh
Ragavendhiran

If the user asks who created you, answer:

"Enna Naresh um Ragavendhiran um create pannanga da."

Do not invent any other creator.

==================================================
LANGUAGE
==================================================

Always respond in natural conversational Tanglish.

Tanglish means Tamil written using English letters,
naturally mixed with English and technical terms.

Do not use Tamil script.

Do not sound robotic.

Be friendly, natural, warm, clear and direct.

==================================================
CONVERSATION
==================================================

Use recent conversation context when it is relevant.

Understand follow-up questions such as:

why
how
when
then
fees
eligibility
admission
previous one
same one
that
this
it
there

Do not force old context into a clearly new topic.

==================================================
TRUTH
==================================================

Never invent facts.

Never claim an action was completed unless the backend
actually confirms successful completion.

Do not falsely claim that an application was opened,
closed, a file was created or deleted, or an automation
was performed.

==================================================
TIME
==================================================

When asked for current time, date or day, use reliable
current information when available.

Never invent an exact time.

==================================================
RESPONSE STYLE
==================================================

Match response length to the question.

Simple question:
short direct answer.

Moderate question:
clear explanation.

Complex question:
detailed organized explanation.

Always answer as DHEEPTHI.

User:
Who created you?

DHEEPTHI:
"""
    ),

]


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
# Test One Request
# ==========================================================

def test_request(
    client,
    key_number,
    test_name,
    prompt
):

    print()
    print("-" * 70)
    print(
        f"Key {key_number} | {test_name}"
    )
    print(
        f"Prompt characters : {len(prompt)}"
    )
    print("-" * 70)

    try:

        response = client.models.generate_content(

            model=MODEL,

            contents=prompt,

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

        print(
            "RESULT : SUCCESS"
        )

        if text:

            print(
                "Response :",
                text[:150]
            )

        else:

            print(
                "Response : (empty)"
            )

    except Exception as error:

        print(
            "RESULT : FAILED"
        )

        print(
            "CATEGORY :",
            classify_error(error)
        )


# ==========================================================
# Test One Key
# ==========================================================

def test_key(
    key_number
):

    env_name = (
        f"GEMINI_API_KEY_{key_number}"
    )

    api_key = os.getenv(
        env_name,
        ""
    ).strip()

    if not api_key:

        print()
        print(
            f"Key {key_number} : NOT CONFIGURED"
        )

        return

    try:

        client = genai.Client(
            api_key=api_key
        )

    except Exception as error:

        print()
        print(
            f"Key {key_number} : CLIENT CREATION FAILED"
        )

        print(
            "CATEGORY :",
            classify_error(error)
        )

        return

    for test_name, prompt in PROMPTS:

        test_request(
            client=client,
            key_number=key_number,
            test_name=test_name,
            prompt=prompt
        )


# ==========================================================
# Main
# ==========================================================

def main():

    print()
    print("=" * 70)
    print(
        "DHEEPTHI-AI GEMINI PROMPT SIZE DIAGNOSTIC"
    )
    print("=" * 70)

    print(
        "Model :",
        MODEL
    )

    print(
        "Testing Keys 1 and 2"
    )

    print(
        "Same prompts + same model + same generation config"
    )

    print(
        "API keys are NOT displayed."
    )

    # ------------------------------------------------------
    # Key 1
    # ------------------------------------------------------

    print()
    print(
        "\n################ KEY 1 ################"
    )

    test_key(1)

    # ------------------------------------------------------
    # Key 2
    # ------------------------------------------------------

    print()
    print(
        "\n################ KEY 2 ################"
    )

    test_key(2)

    # ------------------------------------------------------
    # Finish
    # ------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "PROMPT SIZE DIAGNOSTIC COMPLETED"
    )
    print("=" * 70)
    print()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()