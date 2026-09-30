from __future__ import annotations

"""
DHEEPTHI-AI
Physical Microphone Monitor Test

Purpose
-------
Test voice.microphone_monitor.MicrophoneMuteMonitor
independently before integrating it into main_window.py.

Expected behavior
-----------------
1. Start this test.
2. Windows default microphone state is printed.
3. Press the laptop physical microphone mute/unmute key.
4. The terminal should print the state change.
5. Press Ctrl+C to stop the test.

Example
-------
[MIC TEST] Starting...
[MIC MONITOR] Windows physical microphone monitor started.
[MIC MONITOR] Default Windows capture endpoint resolved.
[MIC MONITOR] Initial state : UNMUTED
[MIC TEST] mute_changed -> UNMUTED

After pressing physical mic mute key:

[MIC MONITOR] Microphone state changed -> MUTED
[MIC TEST] mute_changed -> MUTED

After pressing physical mic unmute key:

[MIC MONITOR] Microphone state changed -> UNMUTED
[MIC TEST] mute_changed -> UNMUTED
"""

import sys
import time
from pathlib import Path


# ============================================================
# Make project root importable
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PySide6
# ============================================================

try:
    from PySide6.QtCore import QCoreApplication

except Exception as exc:
    print(
        "[MIC TEST ERROR] PySide6 import failed:"
    )
    print(f"    {exc}")
    sys.exit(1)


# ============================================================
# DHEEPTHI microphone monitor
# ============================================================

try:
    from voice.microphone_monitor import (
        MicrophoneMuteMonitor,
    )

except Exception as exc:
    print(
        "[MIC TEST ERROR] "
        "Could not import MicrophoneMuteMonitor:"
    )
    print(f"    {exc}")
    sys.exit(1)


# ============================================================
# Test callback
# ============================================================

def on_mute_changed(muted: bool) -> None:
    """
    Receive microphone mute/unmute changes.
    """

    if muted:

        print(
            "[MIC TEST] "
            "mute_changed -> MUTED"
        )

    else:

        print(
            "[MIC TEST] "
            "mute_changed -> UNMUTED"
        )


def on_monitor_error(message: str) -> None:
    """
    Receive monitor errors.
    """

    print(
        "[MIC TEST ERROR] "
        f"{message}"
    )


# ============================================================
# Main test
# ============================================================

def main() -> int:

    print()
    print("=" * 60)
    print(" DHEEPTHI-AI Physical Microphone Monitor Test")
    print("=" * 60)
    print()

    print(
        "[MIC TEST] Project root : "
        f"{PROJECT_ROOT}"
    )

    print(
        "[MIC TEST] Creating Qt application..."
    )

    app = QCoreApplication.instance()

    if app is None:
        app = QCoreApplication(sys.argv)

    print(
        "[MIC TEST] Creating microphone monitor..."
    )

    monitor = MicrophoneMuteMonitor(
        interval_ms=250
    )

    # --------------------------------------------------------
    # Connect signals
    # --------------------------------------------------------

    monitor.mute_changed.connect(
        on_mute_changed
    )

    monitor.error.connect(
        on_monitor_error
    )

    # --------------------------------------------------------
    # Start monitor
    # --------------------------------------------------------

    print()
    print(
        "[MIC TEST] Starting microphone monitor..."
    )

    monitor.start_monitoring()

    # --------------------------------------------------------
    # Wait until monitor initializes
    # --------------------------------------------------------

    print(
        "[MIC TEST] Waiting for Windows microphone "
        "endpoint..."
    )

    start_time = time.monotonic()

    while (
        not monitor.is_initialized
        and monitor.isRunning()
        and (time.monotonic() - start_time) < 5.0
    ):

        app.processEvents()
        time.sleep(0.05)

    # --------------------------------------------------------
    # Initialization result
    # --------------------------------------------------------

    print()

    if monitor.is_initialized:

        print(
            "[MIC TEST] "
            "Microphone endpoint initialized successfully."
        )

        current_state = monitor.current_muted

        if current_state is True:

            print(
                "[MIC TEST] Current state : MUTED"
            )

        elif current_state is False:

            print(
                "[MIC TEST] Current state : UNMUTED"
            )

        else:

            print(
                "[MIC TEST] Current state : UNKNOWN"
            )

    else:

        print(
            "[MIC TEST] "
            "Microphone endpoint initialization failed."
        )

        print(
            "[MIC TEST] Check the error messages above."
        )

        monitor.stop_monitoring()

        if monitor.isRunning():
            monitor.wait(2000)

        return 1

    # --------------------------------------------------------
    # Interactive test
    # --------------------------------------------------------

    print()
    print("-" * 60)
    print(" PHYSICAL MICROPHONE TEST")
    print("-" * 60)
    print()
    print(
        "Now press your LAPTOP PHYSICAL MICROPHONE"
    )
    print(
        "MUTE / UNMUTE key."
    )
    print()
    print(
        "Expected:"
    )
    print(
        "    Physical mic OFF  -> MUTED"
    )
    print(
        "    Physical mic ON   -> UNMUTED"
    )
    print()
    print(
        "Press Ctrl+C to stop."
    )
    print()
    print("-" * 60)
    print()

    # --------------------------------------------------------
    # Keep Qt event processing alive
    # --------------------------------------------------------

    try:

        while monitor.isRunning():

            app.processEvents()

            time.sleep(0.05)

    except KeyboardInterrupt:

        print()
        print(
            "[MIC TEST] Ctrl+C received."
        )

    finally:

        print()
        print(
            "[MIC TEST] Stopping microphone monitor..."
        )

        monitor.stop_monitoring()

        if monitor.isRunning():

            monitor.wait(3000)

        print(
            "[MIC TEST] Monitor stopped."
        )

        print()
        print("=" * 60)
        print(" MIC MONITOR TEST FINISHED")
        print("=" * 60)
        print()

    return 0


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )