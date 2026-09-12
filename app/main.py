import os
import sys
import ctypes

from PySide6.QtCore import QTimer

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


def main():

    # -------------------------------------------------
    # Windows App User Model ID
    # -------------------------------------------------

    try:

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ASTRA.AI.Desktop.v1"
        )

    except Exception:

        pass

    # -------------------------------------------------
    # Create Application
    # -------------------------------------------------

    app = QApplication(sys.argv)

    app.setApplicationName("ASTRA-AI")

    app.setApplicationVersion("1.0")

    app.setOrganizationName("ASTRA")

    # -------------------------------------------------
    # Application Icon
    # -------------------------------------------------

    icon_path = os.path.abspath(
        "ui/assets/dheepthi_logo-2.png"
    )

    if os.path.exists(icon_path):

        app_icon = QIcon(icon_path)

        app.setWindowIcon(app_icon)

    else:

        app_icon = QIcon()

        print(
            "Warning : Application icon not found."
        )

    # -------------------------------------------------
    # Create Main Window
    # -------------------------------------------------

    from ui.main_window import MainWindow

    window = MainWindow()

    window.setWindowIcon(app_icon)

    # Keep reference alive

    app.window = window

    # -------------------------------------------------
    # Show Window
    # -------------------------------------------------

    window.showMaximized()

    window.raise_()

    window.activateWindow()

    # Let Qt completely paint first frame

    app.processEvents()

    # -------------------------------------------------
    # Start Initialization AFTER UI is visible
    # -------------------------------------------------

    QTimer.singleShot(

        0,

        window.initialize_application

    )

    # -------------------------------------------------
    # Run Application
    # -------------------------------------------------

    sys.exit(

        app.exec()

    )


if __name__ == "__main__":

    main()