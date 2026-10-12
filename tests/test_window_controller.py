"""
Window Controller Test Module

Tests all WindowController functions.
"""

import time

from automation.window_controller import WindowController


def main():

    controller = WindowController()

    while True:

        print("\n===================================")
        print("ASTRA Window Controller Test")
        print("===================================")

        print("\nChoose an Option")
        print("1. Get Active Window Title")
        print("2. Minimize Window")
        print("3. Maximize Window")
        print("4. Restore Window")
        print("5. Close Window")
        print("0. Exit")

        choice = input("\nEnter Choice : ")

        # ----------------------------------
        # Exit
        # ----------------------------------

        if choice == "0":

            print("\nExiting Test...")

            break

        # ----------------------------------
        # Window Title
        # ----------------------------------

        elif choice == "1":

            title = controller.get_window_title()

            if title:

                print(f"\nActive Window : {title}")

            else:

                print("\nNo Active Window Found.")

        # ----------------------------------
        # Minimize
        # ----------------------------------

        elif choice == "2":

            print("\nYou have 3 seconds...")
            print("Select any window.")

            time.sleep(3)

            if controller.minimize_window():

                print("\nWindow Minimized.")

            else:

                print("\nOperation Failed.")

        # ----------------------------------
        # Maximize
        # ----------------------------------

        elif choice == "3":

            print("\nYou have 3 seconds...")
            print("Select any window.")

            time.sleep(3)

            if controller.maximize_window():

                print("\nWindow Maximized.")

            else:

                print("\nOperation Failed.")

        # ----------------------------------
        # Restore
        # ----------------------------------

        elif choice == "4":

            print("\nYou have 3 seconds...")
            print("Select any window.")

            time.sleep(3)

            if controller.restore_window():

                print("\nWindow Restored.")

            else:

                print("\nOperation Failed.")

        # ----------------------------------
        # Close
        # ----------------------------------

        elif choice == "5":

            print("\nWARNING!")
            print("The selected active window will close.")

            confirm = input("\nContinue (y/n) : ")

            if confirm.lower() == "y":

                print("\nYou have 3 seconds...")
                print("Select target window.")

                time.sleep(3)

                if controller.close_window():

                    print("\nWindow Closed.")

                else:

                    print("\nOperation Failed.")

        else:

            print("\nInvalid Choice.")


if __name__ == "__main__":

    main()