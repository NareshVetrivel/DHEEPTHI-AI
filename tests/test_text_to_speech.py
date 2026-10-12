"""
tests/test_text_to_speech.py

ASTRA-AI
Text To Speech Test Utility

Tests
-----
1. Final OPEN greetings
2. Final CLOSE greetings
3. Custom text
4. Exit / cleanup
"""

from __future__ import annotations

from voice.text_to_speech import TextToSpeech


# ============================================================
# FINAL OPEN GREETINGS
# ============================================================

OPEN_GREETINGS = [

    "Vanakkam! Naan DHEEPTHI. Ungalukku assist panna ready-ah iruken.",

    "Vanakkam! Naan DHEEPTHI. Sollunga, enna help venum?",

    "Hello! Naan DHEEPTHI. Ungaloda task-ku assist panna ready.",

    "Vanakkam! DHEEPTHI online. Sollunga, enna seiyanum?",

    "Hello! Naan DHEEPTHI. Ungaloda command-ku ready-ah iruken.",

]


# ============================================================
# FINAL CLOSE GREETINGS
# ============================================================

CLOSE_GREETINGS = [

    "Okay… ippo namma session complete. Next time continue pannalaam.",

    "Okay… indha session inga mudiyudhu. Thirumbi sandhippom.",

    "Seri… ippo naan purappaduren. Adutha murai thodarnthu pesalaam.",

    "Seri… ippo kelamburen. Next time meet pannalaam.",

    "Seri… ippo naan kelamburen. Meendum thevaipadumbodhu sandhippom.",

]


# ============================================================
# DISPLAY HELP
# ============================================================

def print_header():

    print("\n" + "=" * 55)
    print("ASTRA-AI TEXT TO SPEECH TEST")
    print("=" * 55)


def print_menu():

    print("\nSelect Test:")
    print("-" * 55)

    print("1. Test OPEN greetings")

    print("2. Test CLOSE greetings")

    print("3. Test custom text")

    print("4. Test all greetings")

    print("5. Exit")

    print("-" * 55)


# ============================================================
# WAIT FOR SPEECH
# ============================================================

def wait_for_speech(
    speaker: TextToSpeech,
):
    """
    Wait until the currently selected TTS request finishes.
    """

    try:

        speaker.wait_until_done()

    except Exception as error:

        print(
            f"TTS wait error : {error}"
        )


# ============================================================
# SPEAK GREETING
# ============================================================

def speak_greeting(
    speaker: TextToSpeech,
    number: int,
    text: str,
    category: str,
):
    """
    Speak one greeting and wait for completion.
    """

    print("\n" + "-" * 55)

    print(
        f"{category} Greeting {number}"
    )

    print(
        f"Text : {text}"
    )

    print("-" * 55)

    speaker.speak(text)

    wait_for_speech(
        speaker
    )

    print(
        f"{category} Greeting {number} completed."
    )


# ============================================================
# TEST OPEN GREETINGS
# ============================================================

def test_open_greetings(
    speaker: TextToSpeech,
):

    print("\n")
    print("=" * 55)
    print("OPEN GREETING TEST")
    print("=" * 55)

    for index, greeting in enumerate(
        OPEN_GREETINGS,
        start=1,
    ):

        speak_greeting(
            speaker,
            index,
            greeting,
            "OPEN",
        )

        input(
            "\nPress ENTER for next greeting..."
        )


# ============================================================
# TEST CLOSE GREETINGS
# ============================================================

def test_close_greetings(
    speaker: TextToSpeech,
):

    print("\n")
    print("=" * 55)
    print("CLOSE GREETING TEST")
    print("=" * 55)

    for index, greeting in enumerate(
        CLOSE_GREETINGS,
        start=1,
    ):

        speak_greeting(
            speaker,
            index,
            greeting,
            "CLOSE",
        )

        input(
            "\nPress ENTER for next greeting..."
        )


# ============================================================
# TEST ALL GREETINGS
# ============================================================

def test_all_greetings(
    speaker: TextToSpeech,
):

    print("\n")
    print("=" * 55)
    print("ALL GREETINGS TEST")
    print("=" * 55)

    print("\nTesting OPEN greetings...")

    for index, greeting in enumerate(
        OPEN_GREETINGS,
        start=1,
    ):

        speak_greeting(
            speaker,
            index,
            greeting,
            "OPEN",
        )

    print("\nTesting CLOSE greetings...")

    for index, greeting in enumerate(
        CLOSE_GREETINGS,
        start=1,
    ):

        speak_greeting(
            speaker,
            index,
            greeting,
            "CLOSE",
        )

    print("\nAll greeting tests completed.")


# ============================================================
# CUSTOM TEXT
# ============================================================

def test_custom_text(
    speaker: TextToSpeech,
):

    print("\n")
    print("=" * 55)
    print("CUSTOM TTS TEST")
    print("=" * 55)

    text = input(
        "\nEnter Text : "
    ).strip()

    if not text:

        print(
            "No text entered."
        )

        return

    speaker.speak(
        text
    )

    wait_for_speech(
        speaker
    )

    print(
        "\nCustom TTS completed."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    speaker = None

    try:

        print_header()

        print(
            "\nInitializing ASTRA-AI TTS..."
        )

        speaker = TextToSpeech()

        print(
            "TTS initialized successfully."
        )

        while True:

            print_menu()

            choice = input(
                "Enter Choice : "
            ).strip()

            # ------------------------------------------------
            # OPEN
            # ------------------------------------------------

            if choice == "1":

                test_open_greetings(
                    speaker
                )

            # ------------------------------------------------
            # CLOSE
            # ------------------------------------------------

            elif choice == "2":

                test_close_greetings(
                    speaker
                )

            # ------------------------------------------------
            # CUSTOM
            # ------------------------------------------------

            elif choice == "3":

                test_custom_text(
                    speaker
                )

            # ------------------------------------------------
            # ALL
            # ------------------------------------------------

            elif choice == "4":

                test_all_greetings(
                    speaker
                )

            # ------------------------------------------------
            # EXIT
            # ------------------------------------------------

            elif choice == "5":

                print(
                    "\nExiting TTS Test..."
                )

                break

            else:

                print(
                    "\nInvalid choice."
                )

    except KeyboardInterrupt:

        print(
            "\n\nTTS Test interrupted."
        )

    except Exception as error:

        print(
            f"\nTTS Test Error : {error}"
        )

    finally:

        if speaker is not None:

            try:

                speaker.close()

            except Exception as error:

                print(
                    f"TTS cleanup error : {error}"
                )

        print(
            "\nTTS Test completed."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()