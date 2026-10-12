"""
ASTRA File Indexer Test
"""

from automation.file_indexer import FileIndexer


def main():

    indexer = FileIndexer()

    while True:

        print("\n==========================")
        print("ASTRA File Indexer Test")
        print("==========================")

        print("1. Index Files")
        print("2. Show Indexed Files")
        print("3. Reindex Files")
        print("4. Exit")

        choice = input("\nEnter Choice : ").strip()

        if choice == "1":

            indexer.index_files()

        elif choice == "2":

            indexer.show_summary()

        elif choice == "3":

            indexer.reindex()

        elif choice == "4":

            indexer.close()

            print("\nExiting Test...")

            break

        else:

            print("\nInvalid Choice.")


if __name__ == "__main__":

    main()