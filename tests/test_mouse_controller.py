"""
Unit Test for Mouse Controller
"""

import time

from automation.mouse_controller import MouseController


def main():

    controller = MouseController()

    print("\n===================================")
    print("ASTRA Mouse Controller Test")
    print("===================================")

    print("\nChoose an Option")
    print("1. Left Click")
    print("2. Right Click")
    print("3. Double Click")
    print("4. Scroll Up")
    print("5. Scroll Down")
    print("6. Move To Position")
    print("7. Move Relative")
    print("8. Get Mouse Position")
    print("0. Exit")

    choice = input("\nEnter Choice : ")

    if choice == "1":

        print("\nYou have 5 seconds...")
        print("Move cursor to target location.")

        time.sleep(5)

        success = controller.left_click()

        if success:
            print("\nLeft Click Executed.")
        else:
            print("\nFailed.")

    elif choice == "2":

        print("\nYou have 5 seconds...")
        print("Move cursor to target location.")

        time.sleep(5)

        success = controller.right_click()

        if success:
            print("\nRight Click Executed.")
        else:
            print("\nFailed.")

    elif choice == "3":

        print("\nYou have 5 seconds...")
        print("Move cursor to target location.")

        time.sleep(5)

        success = controller.double_click()

        if success:
            print("\nDouble Click Executed.")
        else:
            print("\nFailed.")

    elif choice == "4":

        print("\nYou have 5 seconds...")
        print("Place cursor over a scrollable window.")

        time.sleep(5)

        success = controller.scroll_up()

        if success:
            print("\nScrolled Up.")
        else:
            print("\nFailed.")

    elif choice == "5":

        print("\nYou have 5 seconds...")
        print("Place cursor over a scrollable window.")

        time.sleep(5)

        success = controller.scroll_down()

        if success:
            print("\nScrolled Down.")
        else:
            print("\nFailed.")

    elif choice == "6":

        x = int(input("\nEnter X Position : "))
        y = int(input("Enter Y Position : "))

        print("\nYou have 3 seconds...")

        time.sleep(3)

        success = controller.move_to(x, y)

        if success:
            print("\nMouse Moved Successfully.")
        else:
            print("\nFailed.")

    elif choice == "7":

        x = int(input("\nEnter X Offset : "))
        y = int(input("Enter Y Offset : "))

        print("\nYou have 3 seconds...")

        time.sleep(3)

        success = controller.move_relative(x, y)

        if success:
            print("\nRelative Movement Completed.")
        else:
            print("\nFailed.")

    elif choice == "8":

        position = controller.get_position()

        if position:
            print(f"\nCurrent Position : {position}")
        else:
            print("\nFailed.")

    elif choice == "0":

        print("\nExiting Test...")

    else:

        print("\nInvalid Choice.")


if __name__ == "__main__":
    main()