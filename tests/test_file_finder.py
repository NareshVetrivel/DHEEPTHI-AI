"""
Unit Test for File Finder
"""

from automation.file_finder import FileFinder


def main():

    finder = FileFinder()

    while True:

        print("\n==========================")
        print("ASTRA File Finder Test")
        print("==========================")

        filename = input(
            "Enter File Name : "
        )

        if filename.lower() == "exit":

            finder.close()

            break

        success = finder.open_file(
            filename
        )

        if success:

            print(
                "\nFile Opened Successfully."
            )

        else:

            print(
                "\nFile Not Found."
            )


if __name__ == "__main__":

    main()