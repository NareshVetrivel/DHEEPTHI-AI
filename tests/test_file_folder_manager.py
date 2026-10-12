"""
Test File and Folder Manager

ASTRA-AI V1
"""

from automation.folder_manager import FolderManager
from automation.file_manager import FileManager


def folder_menu():

    print("\n==============================")
    print("Folder Operations")
    print("==============================")

    print("1. Open Folder")
    print("2. Create Folder")
    print("3. Delete Folder")
    print("4. Empty Recycle Bin")
    print("5. Back")


def file_menu():

    print("\n==============================")
    print("File Operations")
    print("==============================")

    print("1. Delete File")
    print("2. Compress File")
    print("3. Extract ZIP")
    print("4. Search Extension")
    print("5. Search Size")
    print("6. Search Date")
    print("7. Back")


def main():

    folder = FolderManager()

    file = FileManager()

    while True:

        print("\n===================================")
        print("ASTRA File / Folder Manager Test")
        print("===================================")

        print("1. Folder Operations")
        print("2. File Operations")
        print("3. Exit")

        choice = input("\nChoice : ").strip()

        # ---------------------------------
        # Folder
        # ---------------------------------

        if choice == "1":

            while True:

                folder_menu()

                option = input(
                    "\nChoice : "
                ).strip()

                if option == "1":

                    name = input(
                        "\nFolder : "
                    )

                    print()

                    folder.open_folder(name)

                elif option == "2":

                    name = input(
                        "\nFolder Name : "
                    )

                    print()

                    folder.create_folder(name)

                elif option == "3":

                    name = input(
                        "\nFolder Name : "
                    )

                    print()

                    folder.delete_folder(name)

                elif option == "4":

                    print()

                    folder.empty_recycle_bin()

                elif option == "5":

                    break

                else:

                    print("\nInvalid Choice.")

        # ---------------------------------
        # File
        # ---------------------------------

        elif choice == "2":

            while True:

                file_menu()

                option = input(
                    "\nChoice : "
                ).strip()

                if option == "1":

                    name = input(
                        "\nFile : "
                    )

                    print()

                    file.delete_file(name)

                elif option == "2":

                    name = input(
                        "\nFile : "
                    )

                    print()

                    file.compress_file(name)

                elif option == "3":

                    name = input(
                        "\nZIP File : "
                    )

                    print()

                    file.extract_zip(name)

                elif option == "4":

                    extension = input(
                        "\nExtension : "
                    )

                    print()

                    results = (

                        file.search_by_extension(

                            extension

                        )

                    )

                    file.show_search_results(

                        results

                    )

                elif option == "5":

                    size = int(

                        input(

                            "\nMinimum Size (MB) : "

                        )

                    )

                    print()

                    results = (

                        file.search_by_size(

                            size

                        )

                    )

                    file.show_search_results(

                        results

                    )

                elif option == "6":

                    days = int(

                        input(

                            "\nModified within days : "

                        )

                    )

                    print()

                    results = (

                        file.search_by_date(

                            days

                        )

                    )

                    file.show_search_results(

                        results

                    )

                elif option == "7":

                    break

                else:

                    print("\nInvalid Choice.")

        elif choice == "3":

            break

        else:

            print("\nInvalid Choice.")


if __name__ == "__main__":

    main()