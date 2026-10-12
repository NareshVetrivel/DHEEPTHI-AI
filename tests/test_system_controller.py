"""
System Controller Test Module

Tests all System Controller functions.
"""

import time

from automation.system_controller import SystemController


def main():
    """
    Run System Controller tests.
    """

    controller = SystemController()

    while True:

        print("\n===================================")
        print("ASTRA System Controller Test")
        print("===================================\n")

        print("Choose an Option")
        print("1. Volume Up")
        print("2. Volume Down")
        print("3. Mute / Unmute")
        print("4. Lock Screen")
        print("5. Take Screenshot")
        print("6. Open Task Manager")
        print("7. Open File Explorer")
        print("0. Exit\n")

        choice = input("Enter Choice : ").strip()

        # ---------------------------------

        if choice == "1":

            print("\nIncreasing volume in 3 seconds...")
            time.sleep(3)

            if controller.volume_up():

                print("\nVolume Increased.")

            else:

                print("\nOperation Failed.")

        # ---------------------------------

        elif choice == "2":

            print("\nDecreasing volume in 3 seconds...")
            time.sleep(3)

            if controller.volume_down():

                print("\nVolume Decreased.")

            else:

                print("\nOperation Failed.")

        # ---------------------------------

        elif choice == "3":

            print("\nMuting / Unmuting in 3 seconds...")
            time.sleep(3)

            if controller.mute():

                print("\nMute Executed.")

            else:

                print("\nOperation Failed.")

        # ---------------------------------

        elif choice == "4":

            print("\nWARNING!")
            print("Your PC will be locked.")

            confirm = input(
                "\nContinue (y/n) : "
            ).lower()

            if confirm == "y":

                print("\nLocking in 3 seconds...")
                time.sleep(3)

                if controller.lock_screen():

                    print("\nSystem Locked.")

                else:

                    print("\nOperation Failed.")

        # ---------------------------------

        elif choice == "5":

            print("\nTaking Screenshot in 3 seconds...")
            time.sleep(3)

            filename = controller.take_screenshot()

            if filename:

                print(
                    f"\nScreenshot Saved : {filename}"
                )

            else:

                print("\nOperation Failed.")

        # ---------------------------------

        elif choice == "6":

            print("\nOpening Task Manager...")
            time.sleep(1)

            if controller.open_task_manager():

                print("\nTask Manager Opened.")

            else:

                print("\nOperation Failed.")

        # ---------------------------------

        elif choice == "7":

            print("\nOpening File Explorer...")
            time.sleep(1)

            if controller.open_file_explorer():

                print("\nFile Explorer Opened.")

            else:

                print("\nOperation Failed.")

        # ---------------------------------

        elif choice == "0":

            print("\nExiting Test...")

            break

        # ---------------------------------

        else:

            print("\nInvalid Choice.")


if __name__ == "__main__":

    main()