"""
Initialization Worker

Runs startup tasks in a
background thread to keep
the UI responsive.

ASTRA-AI V1
"""

from PySide6.QtCore import (
    QThread,
    Signal
)

from automation.application_scanner import (
    ApplicationScanner
)

from automation.file_indexer import (
    FileIndexer
)


class InitializationWorker(QThread):
    """
    Background initialization worker.

    Responsibilities:

    - Load Whisper model
    - Scan installed applications
    - Synchronize file index

    Conversation memory objects such as GeminiClient,
    IntentDetector and CommandDispatcher are intentionally
    NOT created here.

    This worker must not create another GeminiClient instance,
    because MainWindow owns the active runtime instances used
    for typed chat, voice chat and AI conversation routing.

    Live File Monitor is intentionally NOT started here.

    MainWindow owns the FileMonitor so only one monitor runs
    during the ASTRA application lifetime.
    """

    status_changed = Signal(str)

    progress_changed = Signal(int)

    finished_success = Signal()

    finished_error = Signal(str)

    def __init__(
        self,
        recognizer,
        parent=None
    ):

        super().__init__(parent)

        self.recognizer = recognizer

        self._stop_requested = False

    # -------------------------------------------------
    # Stop Request
    # -------------------------------------------------

    def stop(self):
        """
        Request graceful initialization shutdown.

        The running operation will stop at the next safe
        checkpoint.
        """

        self._stop_requested = True

        self.requestInterruption()

    # -------------------------------------------------
    # Check Stop
    # -------------------------------------------------

    def should_stop(self):
        """
        Return True when initialization should stop safely.
        """

        return (

            self._stop_requested

            or

            self.isInterruptionRequested()

        )

    # -------------------------------------------------
    # Emit Status Safely
    # -------------------------------------------------

    def _update_status(
        self,
        progress: int,
        status: str
    ):
        """
        Update initialization progress and status.

        No update is emitted after a stop request.
        """

        if self.should_stop():

            return

        self.progress_changed.emit(
            int(progress)
        )

        self.status_changed.emit(
            str(status)
        )

    # -------------------------------------------------
    # Run
    # -------------------------------------------------

    def run(self):

        scanner = None

        indexer = None

        completed = False

        try:

            print(
                "\n========== INITIALIZATION =========="
            )

            if self.should_stop():

                return

            # ------------------------------------------
            # Starting
            # ------------------------------------------

            self._update_status(
                0,
                "Starting DHEEPTHI-AI..."
            )

            if self.should_stop():

                return

            # ------------------------------------------
            # Load Groq Model
            # ------------------------------------------

            self._update_status(
                10,
                "Loading Groq Model..."
            )

            print(
                "Loading Groq model..."
            )

            if self.recognizer is None:

                raise RuntimeError(
                    "Speech recognizer is not available."
                )

            self.recognizer.load_model()

            if self.should_stop():

                return

            print(
                "Whisper model loaded."
            )

            # ------------------------------------------
            # Scan Applications
            # ------------------------------------------

            self._update_status(
                30,
                "Scanning Applications..."
            )

            print(
                "Scanning applications..."
            )

            scanner = ApplicationScanner()

            scanner.scan()

            if self.should_stop():

                return

            print(
                "Application scan completed."
            )

            # ------------------------------------------
            # Prepare File Index
            # ------------------------------------------

            self._update_status(
                55,
                "Preparing File Index..."
            )

            if self.should_stop():

                return

            # ------------------------------------------
            # File Indexing / Synchronization
            # ------------------------------------------

            self._update_status(
                70,
                "Indexing Files..."
            )

            print(
                "Indexing files..."
            )

            indexer = FileIndexer()

            indexer.index_files()

            if self.should_stop():

                return

            print(
                "File indexing completed."
            )

            # ------------------------------------------
            # Important
            # ------------------------------------------
            #
            # Live File Monitor is NOT started here.
            #
            # MainWindow owns and starts the FileMonitor
            # after initialization completes successfully.
            #
            # This prevents duplicate watchdog observers
            # and duplicate database event processing.
            # ------------------------------------------

            # ------------------------------------------
            # Preparing ASTRA
            # ------------------------------------------

            self._update_status(
                95,
                "Preparing DHEEPTHI-AI..."
            )

            print(
                "Initialization worker completed."
            )

            if self.should_stop():

                return

            # ------------------------------------------
            # Completed
            # ------------------------------------------

            self._update_status(
                100,
                "Initialization Complete"
            )

            completed = True

            print(
                "Initialization completed."
            )

            print(
                "====================================\n"
            )

            if not self.should_stop():

                self.finished_success.emit()

        except Exception as error:

            import traceback

            traceback.print_exc()

            if not self.should_stop():

                self.finished_error.emit(
                    str(error)
                )

        finally:

            # ------------------------------------------
            # Close Application Scanner
            # ------------------------------------------

            try:

                if scanner:

                    scanner.close()

            except Exception as error:

                print(
                    "Application scanner cleanup error:",
                    error
                )

            # ------------------------------------------
            # Close File Indexer
            # ------------------------------------------

            try:

                if indexer:

                    indexer.close()

            except Exception as error:

                print(
                    "File indexer cleanup error:",
                    error
                )

            if not completed and self.should_stop():

                print(
                    "Initialization stopped safely."
                )