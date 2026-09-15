import os
import sys
import ctypes

from PySide6.QtCore import (
    QTimer,
    qInstallMessageHandler,
)

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


# =============================================================
# DHEEPTHI-AI
# QT MESSAGE HANDLER
# =============================================================
#
# The application previously used diagnostic instrumentation to
# print the following Qt warning:
#
#   QFont::setPointSize: Point size <= 0 (-1),
#   must be greater than 0
#
# Investigation showed that the warning is triggered when the
# mouse hovers over the native/custom window title-bar controls
# (Minimize / Maximize / Close).
#
# This is a non-fatal Qt rendering warning and does not stop the
# application.
#
# We suppress ONLY this specific known warning.
#
# All other Qt messages continue through the normal stderr output.
#


def dheepthi_qt_message_handler(
    message_type,
    context,
    message,
):
    """
    Global Qt message handler.

    Suppresses only the known non-fatal QFont point-size warning
    triggered by the window title-bar hover path.

    All other Qt messages are forwarded to stderr.
    """

    # ---------------------------------------------------------
    # Known Qt warning
    # ---------------------------------------------------------
    #
    # This warning:
    #
    #   QFont::setPointSize: Point size <= 0 (-1)
    #
    # has been isolated to the window-control hover path.
    #
    # It is not an application crash or functional error.
    #
    # Do not print it to the terminal.
    #

    if (
        "QFont::setPointSize" in message
        and "Point size <= 0" in message
    ):
        return

    # ---------------------------------------------------------
    # Forward all other Qt messages normally.
    # ---------------------------------------------------------

    try:

        if context is not None:

            file_name = context.file or ""
            line_number = context.line or 0

            if file_name:

                print(
                    f"Qt: {message} "
                    f"({file_name}:{line_number})",
                    file=sys.stderr,
                )

            else:

                print(
                    f"Qt: {message}",
                    file=sys.stderr,
                )

        else:

            print(
                f"Qt: {message}",
                file=sys.stderr,
            )

    except Exception:

        # The message handler itself must never interfere with
        # the Qt event loop.
        pass


# =============================================================
# INSTALL QT MESSAGE HANDLER
# =============================================================
#
# Install before QApplication creation so Qt messages generated
# during application startup are handled consistently.
#

qInstallMessageHandler(
    dheepthi_qt_message_handler
)


def main():

    # ---------------------------------------------------------
    # Windows App User Model ID
    # ---------------------------------------------------------

    try:

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ASTRA.AI.Desktop.v1"
        )

    except Exception:

        pass

    # ---------------------------------------------------------
    # Create Application
    # ---------------------------------------------------------

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "ASTRA-AI"
    )

    app.setApplicationVersion(
        "1.0"
    )

    app.setOrganizationName(
        "ASTRA"
    )

    # ---------------------------------------------------------
    # Application Icon
    # ---------------------------------------------------------

    icon_path = os.path.abspath(
        "ui/assets/dheepthi_logo-2.png"
    )

    if os.path.exists(
        icon_path
    ):

        app_icon = QIcon(
            icon_path
        )

        app.setWindowIcon(
            app_icon
        )

    else:

        app_icon = QIcon()

        print(
            "Warning : Application icon not found."
        )

    # ---------------------------------------------------------
    # Create Main Window
    # ---------------------------------------------------------

    from ui.main_window import MainWindow

    window = MainWindow()

    window.setWindowIcon(
        app_icon
    )

    # ---------------------------------------------------------
    # Keep MainWindow reference alive
    # ---------------------------------------------------------

    app.window = window

    # ---------------------------------------------------------
    # Show Window
    # ---------------------------------------------------------

    window.showMaximized()

    window.raise_()

    window.activateWindow()

    # ---------------------------------------------------------
    # Let Qt completely paint the first frame.
    # ---------------------------------------------------------

    app.processEvents()

    # ---------------------------------------------------------
    # Start application initialization AFTER UI is visible.
    # ---------------------------------------------------------

    QTimer.singleShot(
        0,
        window.initialize_application,
    )

    # ---------------------------------------------------------
    # Run Application
    # ---------------------------------------------------------

    sys.exit(
        app.exec()
    )


# =============================================================
# APPLICATION ENTRY POINT
# =============================================================

if __name__ == "__main__":

    main()