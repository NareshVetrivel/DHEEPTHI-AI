"""
Unit Test for Application Launcher
"""

from automation.app_launcher import AppLauncher


def main():

    launcher = AppLauncher()

    while True:

        print("\n===================================")
        print("ASTRA-AI App Launcher Test")
        print("===================================")

        application = input(
            "Enter Application (.exe) : "
        )

        if application.lower() == "exit":

            print("Exiting Test...")

            break

        success = launcher.launch_application(
            application
        )

        if success:

            print("\nApplication Opened Successfully.")

        else:

            print("\nFailed to Open Application.")


if __name__ == "__main__":
    main()