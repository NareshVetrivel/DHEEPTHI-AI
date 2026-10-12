def main():
    try:
        from voice.speech_recognition import SpeechRecognizer
    except ImportError:
        print("voice.speech_recognition.SpeechRecognizer is not available.")
        return

    recognizer = SpeechRecognizer()

    text = recognizer.listen()

    if text:
        print(f"You said: {text}")
    else:
        print("No speech recognized.")


if __name__ == "__main__":
    main()