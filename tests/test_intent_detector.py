"""
Unit Test for Intent Detector
"""

from planner.intent_detector import IntentDetector


def main():

    detector = IntentDetector()

    while True:

        print("\n==============================")
        print("ASTRA-AI Intent Detector Test")
        print("==============================")

        text = input("Enter Command : ")

        if text.lower() == "exit":
            print("Exiting Test...")
            break

        intent = detector.detect_intent(text)

        print(f"\nInput   : {text}")
        print(f"Intent  : {intent}")


if __name__ == "__main__":
    main()