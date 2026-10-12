import speech_recognition as sr


def main():
    recognizer = sr.Recognizer()

    print("================================")
    print(" ASTRA MICROPHONE TEST")
    print("================================")

    print("\nAvailable microphones:")

    for index, name in enumerate(
        sr.Microphone.list_microphone_names()
    ):
        print(f"{index}: {name}")

    print("\nUsing microphone device: 1")
    print("Microphone: Microphone (AB13X USB Audio)")

    microphone = sr.Microphone(
        device_index=1
    )

    try:

        with microphone as source:

            print("\nCalibrating microphone for 1 second...")
            
            recognizer.adjust_for_ambient_noise(
                source,
                duration=1
            )

            print(
                "Energy threshold:",
                recognizer.energy_threshold
            )

            print("\n================================")
            print("NOW SPEAK:")
            print("Say: open notepad")
            print("================================\n")

            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=10
            )

            print("\n✅ AUDIO CAPTURED SUCCESSFULLY")

            print("Audio duration captured.")

            print("\nTrying Google STT...")

            try:

                text = recognizer.recognize_google(
                    audio
                )

                print("\n✅ RECOGNIZED TEXT:")
                print(text)

            except sr.UnknownValueError:

                print(
                    "\n❌ Google STT could not understand audio."
                )

            except sr.RequestError as error:

                print(
                    "\n❌ Google STT request error:"
                )

                print(error)

    except sr.WaitTimeoutError:

        print(
            "\n❌ MICROPHONE TIMEOUT"
        )

        print(
            "SpeechRecognition did not detect speech."
        )

    except Exception as error:

        print(
            "\n❌ MICROPHONE ERROR:"
        )

        print(
            repr(error)
        )

    finally:

        print(
            "\n================================"
        )

        print("MIC TEST FINISHED")
        print("================================")


if __name__ == "__main__":
    main()