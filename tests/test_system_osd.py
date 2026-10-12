"""
DHEEPTHI-AI
System OSD + Screenshot + Screen Recording Test

Interactive integration test for:

1. Real screenshot capture + custom DHEEPTHI OSD toast.
2. Real screen recording + live recording OSD timer.
3. Ctrl+C based recording stop.
4. Recording saved OSD confirmation.

This test intentionally does NOT start the full DHEEPTHI MainWindow.

It verifies the screenshot/recording backend together with the
SystemOSD UI before MainWindow integration.
"""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

# ------------------------------------------------------------
# Project root
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ------------------------------------------------------------
# DHEEPTHI imports
# ------------------------------------------------------------

from automation.screen_recorder import ScreenRecorder
from automation.system_controller import SystemController
from ui.widgets.system_osd import SystemOSD


class DHEEPTHIOSDTest:
    """
    Interactive test runner for DHEEPTHI screenshot and
    screen-recording functionality.
    """

    def __init__(self):
        # ----------------------------------------------------
        # Qt Application
        # ----------------------------------------------------

        self.app = QApplication.instance()

        if self.app is None:
            self.app = QApplication(sys.argv)

        # ----------------------------------------------------
        # DHEEPTHI components
        # ----------------------------------------------------

        self.system_controller = SystemController()

        self.screen_recorder = ScreenRecorder()

        self.osd = SystemOSD()

        # ----------------------------------------------------
        # Ctrl+C state
        # ----------------------------------------------------

        self._stop_recording_requested = False

        self._previous_sigint_handler = None

    # ========================================================
    # Console UI
    # ========================================================

    @staticmethod
    def print_header():
        """Print the interactive test menu."""

        print()
        print("=" * 64)
        print("                 DHEEPTHI-AI")
        print("          SCREEN CAPTURE TEST")
        print("=" * 64)
        print()
        print("Choose an option:")
        print()
        print("  1. Screenshot")
        print("  2. Screen Recording")
        print("  q. Exit")
        print()
        print("=" * 64)

    # ========================================================
    # Screenshot
    # ========================================================

    def test_screenshot(self):
        """
        Test the complete screenshot flow.

        Flow:

            SystemController
                    ↓
            Real Screenshot
                    ↓
            PNG saved
                    ↓
            SystemOSD
                    ↓
            📸 Screenshot Taken
        """

        print()
        print("-" * 64)
        print("DHEEPTHI Screenshot Test")
        print("-" * 64)

        print()
        print("Taking screenshot...")

        # ----------------------------------------------------
        # Real screenshot capture
        # ----------------------------------------------------

        screenshot_path = self.system_controller.take_screenshot()

        if not screenshot_path:
            print()
            print("❌ Screenshot capture failed.")
            print()

            self.osd.show_message(
                title="Screenshot Failed",
                detail="Unable to capture the screen.",
                icon="⚠️",
                duration_ms=2500,
            )

            self.app.processEvents()

            self._wait_with_qt_events(2.6)

            return False

        # ----------------------------------------------------
        # Validate screenshot file
        # ----------------------------------------------------

        screenshot_file = Path(screenshot_path)

        if not screenshot_file.exists():
            print()
            print("❌ Screenshot path returned but file does not exist:")
            print(screenshot_file)

            self.osd.show_message(
                title="Screenshot Failed",
                detail="Screenshot file was not created.",
                icon="⚠️",
                duration_ms=2500,
            )

            self.app.processEvents()

            self._wait_with_qt_events(2.6)

            return False

        if screenshot_file.stat().st_size <= 0:
            print()
            print("❌ Screenshot file is empty:")
            print(screenshot_file)

            self.osd.show_message(
                title="Screenshot Failed",
                detail="Screenshot file is empty.",
                icon="⚠️",
                duration_ms=2500,
            )

            self.app.processEvents()

            self._wait_with_qt_events(2.6)

            return False

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        print()
        print("✅ Screenshot captured successfully.")
        print()
        print(f"File : {screenshot_file}")
        print(
            f"Size : {screenshot_file.stat().st_size:,} bytes"
        )

        # ----------------------------------------------------
        # Show custom DHEEPTHI OSD
        # ----------------------------------------------------

        self.osd.show_screenshot(
            screenshot_file.name
        )

        self.app.processEvents()

        print()
        print("📸 DHEEPTHI Screenshot OSD displayed.")

        # ----------------------------------------------------
        # Keep toast visible long enough to verify visually
        # ----------------------------------------------------

        self._wait_with_qt_events(2.6)

        print()
        print("Screenshot test completed.")
        print()

        return True

    # ========================================================
    # Screen Recording
    # ========================================================

    def test_screen_recording(self):
        """
        Test the complete screen-recording flow.

        Flow:

            ScreenRecorder.start_recording()
                    ↓
            🔴 Recording
                    ↓
            00:00
            00:01
            00:02
                    ↓
            Ctrl+C
                    ↓
            ScreenRecorder.stop_recording()
                    ↓
            ■ Recording Saved
        """

        print()
        print("-" * 64)
        print("DHEEPTHI Screen Recording Test")
        print("-" * 64)

        print()
        print("Starting screen recording...")

        # ----------------------------------------------------
        # Reset Ctrl+C state
        # ----------------------------------------------------

        self._stop_recording_requested = False

        # ----------------------------------------------------
        # Start real recording
        # ----------------------------------------------------

        recording_path = self.screen_recorder.start_recording()

        if not recording_path:
            print()
            print("❌ Unable to start screen recording.")
            print()

            self.osd.show_message(
                title="Recording Failed",
                detail="Unable to start screen recording.",
                icon="⚠️",
                duration_ms=2500,
            )

            self.app.processEvents()

            self._wait_with_qt_events(2.6)

            return False

        # ----------------------------------------------------
        # Show recording OSD
        # ----------------------------------------------------

        self.osd.start_recording()

        self.app.processEvents()

        print()
        print("🔴 Recording started.")
        print()
        print("Recording file:")
        print(recording_path)
        print()
        print("Press Ctrl+C in this terminal to stop recording.")
        print()

        # ----------------------------------------------------
        # Install Ctrl+C handler
        # ----------------------------------------------------

        self._previous_sigint_handler = signal.getsignal(
            signal.SIGINT
        )

        signal.signal(
            signal.SIGINT,
            self._handle_ctrl_c
        )

        # ----------------------------------------------------
        # Recording event loop
        # ----------------------------------------------------

        try:
            while not self._stop_recording_requested:

                # Keep Qt OSD responsive.
                self.app.processEvents()

                # Small sleep prevents CPU spinning.
                time.sleep(0.05)

                # ------------------------------------------------
                # Safety check:
                # Recorder may have stopped internally.
                # ------------------------------------------------

                if not self.screen_recorder.is_recording():

                    print()
                    print(
                        "⚠️ Screen recorder stopped unexpectedly."
                    )

                    self._stop_recording_requested = True

        finally:

            # ----------------------------------------------------
            # Restore previous SIGINT handler
            # ----------------------------------------------------

            if self._previous_sigint_handler is not None:

                signal.signal(
                    signal.SIGINT,
                    self._previous_sigint_handler
                )

                self._previous_sigint_handler = None

        # --------------------------------------------------------
        # Stop real recording
        # --------------------------------------------------------

        print()
        print("Stopping screen recording...")

        final_path = self.screen_recorder.stop_recording()

        # --------------------------------------------------------
        # Calculate elapsed duration
        # --------------------------------------------------------

        duration_seconds = (
            self.screen_recorder.get_recording_elapsed_seconds()
        )

        # --------------------------------------------------------
        # Validate output
        # --------------------------------------------------------

        if not final_path:

            print()
            print("❌ Recording stopped but no output file returned.")
            print()

            self.osd.stop_recording()

            self.app.processEvents()

            return False

        final_file = Path(final_path)

        if not final_file.exists():

            print()
            print(
                "❌ Recording path returned but file does not exist:"
            )
            print(final_file)

            self.osd.stop_recording()

            self.app.processEvents()

            return False

        if final_file.stat().st_size <= 0:

            print()
            print("❌ Recording file is empty:")
            print(final_file)

            self.osd.stop_recording()

            self.app.processEvents()

            return False

        # --------------------------------------------------------
        # Recording success
        # --------------------------------------------------------

        print()
        print("✅ Screen recording saved successfully.")
        print()
        print(f"File     : {final_file}")
        print(
            f"Size     : {final_file.stat().st_size:,} bytes"
        )
        print(
            f"Duration : {self._format_duration(duration_seconds)}"
        )

        # --------------------------------------------------------
        # Show saved OSD
        # --------------------------------------------------------

        self.osd.stop_recording(
            final_file.name
        )

        self.app.processEvents()

        print()
        print("■ Recording Saved OSD displayed.")

        # --------------------------------------------------------
        # Keep saved toast visible
        # --------------------------------------------------------

        self._wait_with_qt_events(2.8)

        print()
        print("Screen recording test completed.")
        print()

        return True

    # ========================================================
    # Ctrl+C
    # ========================================================

    def _handle_ctrl_c(self, signum, frame):
        """
        Handle Ctrl+C from the terminal.

        We do not stop the recorder directly from the signal
        handler. We only set a flag and let the normal event
        loop perform the shutdown safely.
        """

        if self._stop_recording_requested:
            return

        print()
        print()
        print("🛑 Ctrl+C detected.")
        print("Stopping DHEEPTHI screen recording...")

        self._stop_recording_requested = True

    # ========================================================
    # Qt Event Waiting
    # ========================================================

    def _wait_with_qt_events(self, seconds: float):
        """
        Wait while continuing to process Qt events.

        This allows:
        - OSD fade animation
        - OSD timer
        - auto-hide
        - repainting
        - window updates
        """

        end_time = time.monotonic() + seconds

        while time.monotonic() < end_time:

            self.app.processEvents()

            remaining = end_time - time.monotonic()

            if remaining > 0:
                time.sleep(
                    min(0.02, remaining)
                )

        self.app.processEvents()

    # ========================================================
    # Duration Formatting
    # ========================================================

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""

        total_seconds = max(
            0,
            int(seconds)
        )

        hours, remainder = divmod(
            total_seconds,
            3600
        )

        minutes, seconds = divmod(
            remainder,
            60
        )

        if hours > 0:

            return (
                f"{hours:02d}:"
                f"{minutes:02d}:"
                f"{seconds:02d}"
            )

        return (
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    # ========================================================
    # Cleanup
    # ========================================================

    def cleanup(self):
        """Cleanly close OSD and stop recording if necessary."""

        # ----------------------------------------------------
        # Restore signal handler
        # ----------------------------------------------------

        if self._previous_sigint_handler is not None:

            signal.signal(
                signal.SIGINT,
                self._previous_sigint_handler
            )

            self._previous_sigint_handler = None

        # ----------------------------------------------------
        # Stop active recorder
        # ----------------------------------------------------

        if self.screen_recorder.is_recording():

            print()
            print(
                "Stopping active recording during cleanup..."
            )

            try:
                final_path = (
                    self.screen_recorder.stop_recording()
                )

                if final_path:
                    print(
                        f"Recording saved: {final_path}"
                    )

            except Exception as exc:

                print(
                    "⚠️ Recording cleanup error:"
                )
                print(exc)

        # ----------------------------------------------------
        # Hide OSD
        # ----------------------------------------------------

        try:

            self.osd.hide_osd()
            self.osd.close()

            self.app.processEvents()

        except Exception:
            pass

    # ========================================================
    # Interactive Menu
    # ========================================================

    def run(self):
        """Run the interactive DHEEPTHI capture test."""

        self.print_header()

        while True:

            try:

                choice = input(
                    "Choose an option (1/2/q): "
                ).strip().lower()

            except EOFError:

                print()
                print("Input closed. Exiting.")

                break

            except KeyboardInterrupt:

                print()
                print()
                print("Ctrl+C detected. Exiting.")

                break

            # ------------------------------------------------
            # Screenshot
            # ------------------------------------------------

            if choice == "1":

                self.test_screenshot()

                self.print_header()

            # ------------------------------------------------
            # Screen Recording
            # ------------------------------------------------

            elif choice == "2":

                self.test_screen_recording()

                self.print_header()

            # ------------------------------------------------
            # Exit
            # ------------------------------------------------

            elif choice in {
                "q",
                "quit",
                "exit",
            }:

                print()
                print("DHEEPTHI capture test closed.")
                print()

                break

            # ------------------------------------------------
            # Invalid option
            # ------------------------------------------------

            else:

                print()
                print(
                    "❌ Invalid option."
                )
                print(
                    "Please choose 1, 2, or q."
                )
                print()

    # ========================================================
    # Static Entry Point
    # ========================================================

    @staticmethod
    def start():
        """Create and execute the test runner."""

        runner = DHEEPTHIOSDTest()

        try:

            runner.run()

        except KeyboardInterrupt:

            print()
            print()
            print(
                "🛑 Ctrl+C detected."
            )

        except Exception as exc:

            print()
            print(
                "❌ DHEEPTHI test failed:"
            )
            print(
                f"{type(exc).__name__}: {exc}"
            )

        finally:

            runner.cleanup()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    DHEEPTHIOSDTest.start()