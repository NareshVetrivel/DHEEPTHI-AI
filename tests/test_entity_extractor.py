"""
Unit Test for Entity Extractor
"""

from planner.entity_extractor import EntityExtractor


def main():

    extractor = EntityExtractor()

    while True:

        print("\n==============================")
        print("ASTRA-AI Entity Extractor Test")
        print("==============================")

        text = input("Enter Command : ")

        if text.lower() == "exit":
            print("Exiting Test...")
            break

        entity = extractor.extract_application(text)

        print(f"\nInput  : {text}")
        print(f"Entity : {entity}")


if __name__ == "__main__":
    main()