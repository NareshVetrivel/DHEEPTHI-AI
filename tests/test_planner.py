"""
Planner Integration Test

This test combines
1. Intent Detection
2. Entity Extraction
"""

from planner.intent_detector import IntentDetector
from planner.entity_extractor import EntityExtractor


def main():

    intent_detector = IntentDetector()
    entity_extractor = EntityExtractor()

    while True:

        print("\n====================================")
        print("ASTRA-AI Planner Test")
        print("====================================")

        command = input("Enter Command : ")

        if command.lower() == "exit":
            print("Exiting Planner Test...")
            break

        intent = intent_detector.detect_intent(command)

        entity = entity_extractor.extract_application(command)

        print("\n------------- RESULT -------------")
        print(f"Command : {command}")
        print(f"Intent  : {intent}")
        print(f"Entity  : {entity}")
        print("----------------------------------")


if __name__ == "__main__":
    main()