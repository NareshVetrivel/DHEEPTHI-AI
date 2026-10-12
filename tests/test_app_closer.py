"""
Unit Test for Application Closer
"""

from automation.app_closer import AppCloser


def main():

    closer = AppCloser()

    while True:

        print("\n===================================")
        print("ASTRA-AI App Closer Test")
        print("===================================")

        application = input(
            "Enter Application (.exe) : "
        )

        if application.lower() == "exit":

            print("Exiting Test...")

            break

        success = closer.close_application(
            application
        )

        if success:

            print("\nApplication Closed Successfully.")

        else:

            print("\nFailed to Close Application.")


if __name__ == "__main__":
    main()