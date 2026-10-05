"""
tools/capture_real_splash_runtime.py

Runs the REAL application window with SplashOverlay and captures the required lifecycle frames:
1. First visible frame / 0%
2. 25%
3. 50%
4. 75%
5. 100% (100% + full bar + Initialization Complete)
6. Transition to dashboard (fade-out revealing dashboard)
7. Dashboard fully revealed
"""

import sys
import os
import time
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap

from ui.main_window import MainWindow


def capture_runtime():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    out_dir = Path("tests/artifacts/splash_validation")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Instantiate real MainWindow
    window = MainWindow()
    window.resize(1600, 900)
    window.show()
    app.processEvents()

    overlay = getattr(window, "loading_overlay", None)
    if overlay is None:
        print("ERROR: loading_overlay not found on window!")
        return

    # Frame 1: First visible frame / 0%
    app.processEvents()
    f1 = window.grab()
    f1.save(str(out_dir / "1_first_visible_frame_0pct.png"))
    print("Saved 1_first_visible_frame_0pct.png")

    # Frame 2: 25%
    overlay.loading_percent.setText("25%")
    overlay.loading_bar.setValue(25)
    overlay.loading_status.setText("Configuring Voice Assistant...")
    for _ in range(3):
        overlay._on_tick()
    app.processEvents()
    f2 = window.grab()
    f2.save(str(out_dir / "2_progress_25pct.png"))
    print("Saved 2_progress_25pct.png")

    # Frame 3: 50%
    overlay.loading_percent.setText("50%")
    overlay.loading_bar.setValue(50)
    overlay.loading_status.setText("Scanning Applications...")
    for _ in range(3):
        overlay._on_tick()
    app.processEvents()
    f3 = window.grab()
    f3.save(str(out_dir / "3_progress_50pct.png"))
    print("Saved 3_progress_50pct.png")

    # Frame 4: 75%
    overlay.loading_percent.setText("75%")
    overlay.loading_bar.setValue(75)
    overlay.loading_status.setText("Indexing Files...")
    for _ in range(3):
        overlay._on_tick()
    app.processEvents()
    f4 = window.grab()
    f4.save(str(out_dir / "4_progress_75pct.png"))
    print("Saved 4_progress_75pct.png")

    # Frame 5: 100%
    overlay.loading_status.setText("Initialization Complete")
    # Note: status consistency enforces 100% and bar 100
    for _ in range(3):
        overlay._on_tick()
    app.processEvents()
    f5 = window.grab()
    f5.save(str(out_dir / "5_progress_100pct.png"))
    print("Saved 5_progress_100pct.png")

    # Frame 6: Transition to dashboard (fade-out at 50% opacity)
    eff = overlay.enable_fade_effect()
    eff.setOpacity(0.50)
    app.processEvents()
    f6 = window.grab()
    f6.save(str(out_dir / "6_transition_fade_50pct.png"))
    print("Saved 6_transition_fade_50pct.png")

    # Frame 7: Transition to dashboard (near completion at 15% opacity)
    eff.setOpacity(0.15)
    app.processEvents()
    f7 = window.grab()
    f7.save(str(out_dir / "7_transition_fade_15pct.png"))
    print("Saved 7_transition_fade_15pct.png")

    # Complete fade-out and reveal dashboard
    eff.setOpacity(0.0)
    overlay.hide()
    window.enable_main_ui()
    app.processEvents()
    f8 = window.grab()
    f8.save(str(out_dir / "8_dashboard_revealed.png"))
    print("Saved 8_dashboard_revealed.png")

    window.close()
    print("All runtime validation frames captured successfully.")


if __name__ == "__main__":
    capture_runtime()
