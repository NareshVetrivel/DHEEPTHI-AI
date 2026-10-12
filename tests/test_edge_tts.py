from voice.edge_tts_engine import EdgeTTSEngine


def main():

    speaker = EdgeTTSEngine()

    while True:

        print("\n==============================")
        print("ASTRA Edge TTS Test")
        print("==============================")

        text = input("Enter Text : ")

        if text.lower() == "exit":
            print("Exiting...")
            break

        speaker.speak(text)


if __name__ == "__main__":
    main()