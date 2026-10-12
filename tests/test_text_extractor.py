"""
Unit Test for Text Extractor
"""

from planner.text_extractor import TextExtractor

def main():

    extractor = TextExtractor()

    while True:

        print("\n===================================")
        print("ASTRA Text Extractor Test")
        print("===================================")

        command = input("Enter Command : ")

        if command.lower() == "exit":
            
            print("Exiting Test...")

            break

        text = extractor.extract_text(command)

        print("\n------------ RESULT ------------")
        print(f"Input : {command}")
        print(f"Text  : {text}")
        print("--------------------------------")

if __name__ == "__main__":
    main()