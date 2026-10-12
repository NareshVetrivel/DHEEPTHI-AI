"""
Automation Pipeline Test

Intent
↓

Entity

↓

Application Launcher
"""

from planner.intent_detector import IntentDetector
from planner.entity_extractor import EntityExtractor
from automation.app_launcher import AppLauncher


def main():

    intent_detector = IntentDetector()
    entity_extractor = EntityExtractor()
    launcher = AppLauncher()

    while True:

        print("\n====================================")
        print("ASTRA-AI Automation Pipeline Test")
        print("====================================")

        command = input("Enter Command : ")

        if command.lower() == "exit":
            print("Exiting...")
            break

        intent = intent_detector.detect_intent(command)

        entity = entity_extractor.extract_application(command)

        print("\n---------- ANALYSIS ----------")
        print(f"Intent : {intent}")
        print(f"Entity : {entity}")

        # Launch Application
        if intent == "launch_application" and entity:

            success = launcher.launch_application(entity)

            if success:
                print("\n✅ Application Opened Successfully.")

            else:
                print("\n❌ Failed to Open Application.")

        else:

            print("\n⚠ No automation performed.")

        print("-------------------------------")


if __name__ == "__main__":
    main()