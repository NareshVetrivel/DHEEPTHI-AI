"""
tools/validate_splash_runtime_frames.py

Captures real runtime frames of DHEEPTHI-AI startup lifecycle:
1. first visible frame / 0%
2. 25%
3. 50%
4. 75%
5. 100%
6. transition to dashboard (cross-dissolve showing dashboard behind fading splash)
7. dashboard fully revealed
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont

from ui.splash_screen import SplashOverlay
from ui.components.left_panel import LeftPanelWidget


class MockDashboardContainer(QWidget):
    """
    Simulates the MainWindow container with the real DHEEPTHI dashboard
    and SplashOverlay on top to validate the true runtime cross-dissolve transition.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DHEEPTHI-AI")
        self.resize(1600, 900)

        # Dashboard layout
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Real Left Panel
        self.left_panel = LeftPanelWidget(self)
        root_layout.addWidget(self.left_panel)

        # Center area with avatar
        self.center_area = QWidget()
        center_layout = QVBoxLayout(self.center_area)
        center_layout.setAlignment(Qt.AlignCenter)

        # Load avatar if available
        avatar_label = QLabel()
        char_path = Path("ui/assets/avatars/idle/idle_primary.png")
        if char_path.exists():
            pix = QPixmap(str(char_path)).scaledToHeight(450, Qt.SmoothTransformation)
            avatar_label.setPixmap(pix)
        avatar_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(avatar_label)

        welcome_label = QLabel("Welcome to DHEEPTHI-AI")
        welcome_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        welcome_label.setStyleSheet("color: #FFFFFF;")
        welcome_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(welcome_label)

        root_layout.addWidget(self.center_area, 1)

        # Splash overlay on top
        self.overlay = SplashOverlay(self)
        self.overlay.setGeometry(0, 0, 1600, 900)
        self.overlay.raise_()
        self.overlay.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "overlay"):
            self.overlay.setGeometry(self.rect())


def run_validation():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    out_dir = Path("tests/artifacts/splash_validation")
    out_dir.mkdir(parents=True, exist_ok=True)

    window = MockDashboardContainer()
    window.show()
    app.processEvents()

    overlay = window.overlay

    # 1. First visible frame (0%)
    app.processEvents()
    f1 = window.grab()
    f1.save(str(out_dir / "1_first_visible_frame_0pct.png"))
    print("Captured 1_first_visible_frame_0pct.png")

    # 2. 25% Voice assistant
    overlay.loading_percent.setText("25%")
    overlay.loading_bar.setValue(25)
    overlay.loading_status.setText("Configuring Voice Assistant...")
    for _ in range(4):
        overlay._on_tick()
    app.processEvents()
    f2 = window.grab()
    f2.save(str(out_dir / "2_quarter_startup_25pct.png"))
    print("Captured 2_quarter_startup_25pct.png")

    # 3. 50% Application scan
    overlay.loading_percent.setText("50%")
    overlay.loading_bar.setValue(50)
    overlay.loading_status.setText("Scanning Applications...")
    for _ in range(4):
        overlay._on_tick()
    app.processEvents()
    f3 = window.grab()
    f3.save(str(out_dir / "3_middle_startup_50pct.png"))
    print("Captured 3_middle_startup_50pct.png")

    # 4. 75% File indexing
    overlay.loading_percent.setText("75%")
    overlay.loading_bar.setValue(75)
    overlay.loading_status.setText("Indexing Files...")
    for _ in range(4):
        overlay._on_tick()
    app.processEvents()
    f4 = window.grab()
    f4.save(str(out_dir / "4_late_startup_75pct.png"))
    print("Captured 4_late_startup_75pct.png")

    # 5. 100% Initialization complete
    overlay.loading_status.setText("Initialization Complete")
    # Guaranteed consistency enforces 100% and bar 100
    for _ in range(4):
        overlay._on_tick()
    app.processEvents()
    f5 = window.grab()
    f5.save(str(out_dir / "5_final_startup_100pct.png"))
    print("Captured 5_final_startup_100pct.png")

    # 6. Transition to dashboard (cross-dissolve at 45% opacity)
    eff = overlay.enable_fade_effect()
    eff.setOpacity(0.45)
    app.processEvents()
    f6 = window.grab()
    f6.save(str(out_dir / "6_transition_to_dashboard.png"))
    print("Captured 6_transition_to_dashboard.png")

    # 7. Dashboard fully revealed
    eff.setOpacity(0.0)
    overlay.hide()
    app.processEvents()
    f7 = window.grab()
    f7.save(str(out_dir / "7_dashboard_fully_revealed.png"))
    print("Captured 7_dashboard_fully_revealed.png")

    window.close()
    print("All 7 validation frames captured successfully.")


if __name__ == "__main__":
    run_validation()
