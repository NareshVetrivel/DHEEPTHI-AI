"""
DHEEPTHI-AI
Screen Recorder Module

Provides screen recording functionality for DHEEPTHI-AI on Windows.

The recorder is responsible only for capturing and saving the screen.
The UI OSD/timer is intentionally handled by ``ui.widgets.system_osd``.

Return-value contract
---------------------
``start_recording()``
    Returns the absolute recording path as ``str`` when recording
    starts successfully.

    Returns ``None`` when recording cannot be started.

``stop_recording()``
    Returns the saved recording path as ``str`` when recording
    stops successfully.

    Returns ``None`` when there is no active recording or the output
    file could not be created.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import mss
import numpy as np


class ScreenRecorder:
    """
    Controls screen recording.

    The recording itself runs on a daemon worker thread so the Qt UI
    remains responsive.

    OSD integration is deliberately kept outside this class. The
    application UI can use ``get_output_path()`` and
    ``is_recording()`` to update the SystemOSD.
    """

    # --------------------------------------------------
    # Recording configuration
    # --------------------------------------------------

    FPS = 20.0

    def __init__(self):

        # --------------------------------------------------
        # Recording state
        # --------------------------------------------------

        self.recording = False

        self.thread = None

        self.output_path = None

        self.output_directory = (
            Path.cwd() / "screen_recordings"
        )

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        self._stop_event = threading.Event()

        # --------------------------------------------------
        # Worker error state
        # --------------------------------------------------

        self.last_error = None

        # --------------------------------------------------
        # Recording timing
        #
        # The SystemOSD owns the visual timer.
        # These values expose backend timing information.
        # --------------------------------------------------

        self.recording_started_at = None

        self.recording_stopped_at = None

    # ==================================================
    # Start Recording
    # ==================================================

    def start_recording(self):
        """
        Start screen recording.

        Returns
        -------
        str | None
            Absolute recording path when recording starts
            successfully.

            ``None`` when recording is already active or the
            recording could not be initialized.
        """

        # --------------------------------------------------
        # Prevent duplicate recording
        # --------------------------------------------------

        if self.recording:

            return None

        # --------------------------------------------------
        # Reset previous state
        # --------------------------------------------------

        self._stop_event.clear()

        self.last_error = None

        self.recording_stopped_at = None

        # --------------------------------------------------
        # Create output filename
        # --------------------------------------------------

        timestamp = time.strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            f"dheepthi_screen_recording_{timestamp}.mp4"
        )

        self.output_path = (
            self.output_directory /
            filename
        ).resolve()

        # --------------------------------------------------
        # Remove accidental stale file with same timestamp
        # --------------------------------------------------

        try:

            if self.output_path.exists():

                self.output_path.unlink()

        except OSError as error:

            self.last_error = (
                "Unable to prepare recording output file: "
                f"{error}"
            )

            print(
                f"DHEEPTHI Screen Recording Error : "
                f"{self.last_error}"
            )

            self.output_path = None

            return None

        # --------------------------------------------------
        # Start timing
        # --------------------------------------------------

        self.recording_started_at = (
            time.monotonic()
        )

        # --------------------------------------------------
        # Mark recording active BEFORE starting worker.
        #
        # This guarantees that the UI can immediately show
        # the recording OSD after start_recording() returns.
        # --------------------------------------------------

        self.recording = True

        # --------------------------------------------------
        # Create worker thread
        # --------------------------------------------------

        self.thread = threading.Thread(
            target=self._record_screen,
            daemon=True,
            name="DHEEPTHI-ScreenRecorder"
        )

        try:

            self.thread.start()

        except Exception as error:

            self.recording = False

            self.recording_stopped_at = (
                time.monotonic()
            )

            self.last_error = (
                "Unable to start recording worker: "
                f"{error}"
            )

            print(
                f"DHEEPTHI Screen Recording Error : "
                f"{self.last_error}"
            )

            return None

        # --------------------------------------------------
        # IMPORTANT:
        #
        # Return the actual path, NOT True.
        #
        # MainWindow uses this value as the recording path.
        # --------------------------------------------------

        return str(
            self.output_path
        )

    # ==================================================
    # Stop Recording
    # ==================================================

    def stop_recording(self):
        """
        Stop the current screen recording.

        Returns
        -------
        str | None
            Saved recording path when successful.
        """

        # --------------------------------------------------
        # Nothing is recording
        # --------------------------------------------------

        if not self.recording:

            # The worker may have completed by itself.
            # If a valid output file exists, return it.
            if (
                self.output_path is not None
                and self.output_path.exists()
                and self.output_path.stat().st_size > 0
            ):

                return str(
                    self.output_path
                )

            return None

        # --------------------------------------------------
        # Signal worker to stop
        # --------------------------------------------------

        self._stop_event.set()

        # --------------------------------------------------
        # Wait for worker to release VideoWriter.
        #
        # Five seconds is retained from the original
        # implementation.
        # --------------------------------------------------

        if self.thread is not None:

            self.thread.join(
                timeout=5
            )

        # --------------------------------------------------
        # Record stop time
        # --------------------------------------------------

        self.recording_stopped_at = (
            time.monotonic()
        )

        # --------------------------------------------------
        # Worker should normally have set this to False.
        # Force the state here as a safety measure.
        # --------------------------------------------------

        self.recording = False

        # --------------------------------------------------
        # No output path
        # --------------------------------------------------

        if self.output_path is None:

            return None

        # --------------------------------------------------
        # Worker still alive after timeout
        #
        # Do not pretend the file is finalized.
        # --------------------------------------------------

        if (
            self.thread is not None
            and self.thread.is_alive()
        ):

            self.last_error = (
                "Recording worker did not stop within "
                "the expected timeout."
            )

            print(
                f"DHEEPTHI Screen Recording Error : "
                f"{self.last_error}"
            )

            return None

        # --------------------------------------------------
        # Validate output file
        # --------------------------------------------------

        if not self.output_path.exists():

            return None

        try:

            file_size = (
                self.output_path.stat().st_size
            )

        except OSError:

            return None

        if file_size <= 0:

            return None

        # --------------------------------------------------
        # Return actual saved path
        # --------------------------------------------------

        return str(
            self.output_path
        )

    # ==================================================
    # Recording Worker
    # ==================================================

    def _record_screen(self):
        """
        Internal screen recording worker.

        Captures the primary monitor using MSS and writes
        frames to an MP4 file using OpenCV.
        """

        writer = None

        try:

            # --------------------------------------------------
            # Validate output path before starting capture
            # --------------------------------------------------

            if self.output_path is None:

                self.last_error = (
                    "Recording output path is not available."
                )

                return

            # --------------------------------------------------
            # MSS screen capture
            # --------------------------------------------------

            with mss.mss() as screen:

                # --------------------------------------------------
                # Primary monitor
                # --------------------------------------------------

                if len(screen.monitors) < 2:

                    self.last_error = (
                        "No primary monitor was detected."
                    )

                    return

                monitor = screen.monitors[1]

                width = int(
                    monitor["width"]
                )

                height = int(
                    monitor["height"]
                )

                # --------------------------------------------------
                # Validate monitor dimensions
                # --------------------------------------------------

                if width <= 0 or height <= 0:

                    self.last_error = (
                        "Invalid monitor dimensions: "
                        f"{width}x{height}"
                    )

                    return

                # --------------------------------------------------
                # Video Writer
                # --------------------------------------------------

                fourcc = (
                    cv2.VideoWriter_fourcc(
                        *"mp4v"
                    )
                )

                writer = cv2.VideoWriter(

                    str(
                        self.output_path
                    ),

                    fourcc,

                    self.FPS,

                    (
                        width,
                        height
                    )
                )

                # --------------------------------------------------
                # Verify writer
                # --------------------------------------------------

                if not writer.isOpened():

                    self.last_error = (
                        "Unable to create video file."
                    )

                    print(
                        "DHEEPTHI Screen Recording Error : "
                        f"{self.last_error}"
                    )

                    return

                # --------------------------------------------------
                # Capture loop
                # --------------------------------------------------

                frame_interval = (
                    1.0 /
                    self.FPS
                )

                while not self._stop_event.is_set():

                    frame_start = (
                        time.perf_counter()
                    )

                    # --------------------------------------------------
                    # Capture screen
                    # --------------------------------------------------

                    screenshot = screen.grab(
                        monitor
                    )

                    # --------------------------------------------------
                    # Convert MSS frame to NumPy
                    # --------------------------------------------------

                    frame = np.array(
                        screenshot
                    )

                    # --------------------------------------------------
                    # BGRA → BGR for OpenCV
                    # --------------------------------------------------

                    frame = cv2.cvtColor(
                        frame,
                        cv2.COLOR_BGRA2BGR
                    )

                    # --------------------------------------------------
                    # Write frame
                    # --------------------------------------------------

                    writer.write(
                        frame
                    )

                    # --------------------------------------------------
                    # Maintain approximately 20 FPS
                    # --------------------------------------------------

                    elapsed = (
                        time.perf_counter()
                        - frame_start
                    )

                    remaining = (
                        frame_interval
                        - elapsed
                    )

                    if remaining > 0:

                        time.sleep(
                            remaining
                        )

        except Exception as error:

            self.last_error = str(
                error
            )

            print(
                "DHEEPTHI Screen Recording Error : "
                f"{error}"
            )

        finally:

            # --------------------------------------------------
            # Always release OpenCV writer.
            # --------------------------------------------------

            if writer is not None:

                try:

                    writer.release()

                except Exception as error:

                    print(
                        "DHEEPTHI Screen Recording Writer "
                        f"Release Error : {error}"
                    )

            # --------------------------------------------------
            # Mark worker stopped.
            # --------------------------------------------------

            self.recording = False

            # --------------------------------------------------
            # If stop time wasn't explicitly recorded,
            # capture it here.
            # --------------------------------------------------

            if self.recording_stopped_at is None:

                self.recording_stopped_at = (
                    time.monotonic()
                )

    # ==================================================
    # Status
    # ==================================================

    def is_recording(self):
        """
        Check recording state.

        Returns
        -------
        bool
        """

        return bool(
            self.recording
        )

    # ==================================================
    # Current Output
    # ==================================================

    def get_output_path(self):
        """
        Get current recording path.

        Returns
        -------
        str | None
        """

        if self.output_path is None:

            return None

        return str(
            self.output_path
        )

    # ==================================================
    # Last Error
    # ==================================================

    def get_last_error(self):
        """
        Return the latest recorder error.

        Returns
        -------
        str | None
        """

        return self.last_error

    # ==================================================
    # Recording Start Time
    # ==================================================

    def get_recording_elapsed_seconds(self):
        """
        Return the actual elapsed recording time.

        Returns
        -------
        int
            Elapsed recording seconds.

        Notes
        -----
        This helper does not control the recording timer shown
        in the UI. It exposes backend timing information for
        UI synchronization and final duration reporting.
        """

        if self.recording_started_at is None:

            return 0

        # --------------------------------------------------
        # Active recording
        # --------------------------------------------------

        if self.recording:

            end_time = (
                time.monotonic()
            )

        # --------------------------------------------------
        # Recording stopped
        # --------------------------------------------------

        elif self.recording_stopped_at is not None:

            end_time = (
                self.recording_stopped_at
            )

        else:

            return 0

        elapsed = (
            end_time
            -
            self.recording_started_at
        )

        return max(
            0,
            int(
                elapsed
            )
        )

    # ==================================================
    # Reset State
    # ==================================================

    def reset(self):
        """
        Reset recorder metadata after a completed recording.

        The saved file itself is never deleted.
        """

        if self.recording:

            return False

        self.thread = None

        self.output_path = None

        self.recording_started_at = None

        self.recording_stopped_at = None

        self.last_error = None

        self._stop_event.clear()

        return True