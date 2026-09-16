"""
DHEEPTHI-AI - System OSD / Toast Overlay

Reusable Windows-style overlay for screenshot and screen-recording
notifications. It is intentionally independent of the capture and
recording backends.

Public API:
    osd.show_screenshot(...)
    osd.start_recording()
    osd.stop_recording(...)
    osd.show_message(...)
    osd.hide_osd()

The widget uses stylesheet fonts only; no QFont/QFontMetrics objects
are created here.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class SystemOSD(QWidget):
    """Windows-style, non-interactive desktop OSD overlay."""

    OSD_WIDTH = 300
    OSD_MIN_HEIGHT = 82

    TOP_MARGIN = 24

    FADE_IN_MS = 180
    FADE_OUT_MS = 220

    SCREENSHOT_DURATION_MS = 2200
    MESSAGE_DURATION_MS = 2200
    SAVED_DURATION_MS = 2400

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._recording_active = False
        self._recording_seconds = 0
        self._fade_animation: Optional[QPropertyAnimation] = None

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._fade_out)

        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(1000)
        self._recording_timer.timeout.connect(self._update_recording_timer)

        self._build_ui()
        self._configure_window()
        self._move_to_screen()

    # =========================================================
    # WINDOW
    # =========================================================

    def _configure_window(self) -> None:
        """Configure the overlay so it never steals focus."""
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.setWindowOpacity(0.0)

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self) -> None:
        """Create the OSD visual component."""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("SystemOSDPanel")

        panel_layout = QHBoxLayout(self.panel)
        panel_layout.setContentsMargins(18, 14, 18, 14)
        panel_layout.setSpacing(14)

        self.icon_label = QLabel(self.panel)
        self.icon_label.setObjectName("SystemOSDIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(42, 42)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel(self.panel)
        self.title_label.setObjectName("SystemOSDTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.detail_label = QLabel(self.panel)
        self.detail_label.setObjectName("SystemOSDDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.detail_label)

        panel_layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        panel_layout.addLayout(text_layout, 1)
        root.addWidget(self.panel)

        self.setMinimumWidth(self.OSD_WIDTH)
        self.setMaximumWidth(self.OSD_WIDTH)
        self.setMinimumHeight(self.OSD_MIN_HEIGHT)
        self.setObjectName("SystemOSD")

        self.setStyleSheet(
            """
            QWidget#SystemOSD {
                background: transparent;
            }

            QFrame#SystemOSDPanel {
                background: rgba(28, 28, 30, 242);
                border: 1px solid rgba(255, 255, 255, 32);
                border-radius: 16px;
            }

            QLabel#SystemOSDIcon {
                color: #FFFFFF;
                background: rgba(255, 255, 255, 22);
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 21px;
                font-family: "Segoe UI";
                font-size: 20px;
                font-weight: 600;
            }

            QLabel#SystemOSDTitle {
                color: #FFFFFF;
                background: transparent;
                font-family: "Segoe UI";
                font-size: 15px;
                font-weight: 600;
            }

            QLabel#SystemOSDDetail {
                color: rgba(255, 255, 255, 180);
                background: transparent;
                font-family: "Segoe UI";
                font-size: 11px;
                font-weight: 400;
            }
            """
        )

        self._set_content("DHEEPTHI", "", "•")

    # =========================================================
    # POSITIONING
    # =========================================================

    def _target_screen(self):
        """Return the screen containing the active window when possible."""
        window = self.window()

        if window is not None:
            handle = window.windowHandle()
            if handle is not None and handle.screen() is not None:
                return handle.screen()

        return QGuiApplication.primaryScreen()

    def _move_to_screen(self) -> None:
        """Center the OSD horizontally near the top of its screen."""
        screen = self._target_screen()
        if screen is None:
            return

        available = screen.availableGeometry()
        self.adjustSize()

        x = available.left() + (available.width() - self.width()) // 2
        y = available.top() + self.TOP_MARGIN

        self.move(x, y)

    # =========================================================
    # CONTENT
    # =========================================================

    def _set_content(self, title: str, detail: str, icon: str) -> None:
        self.icon_label.setText(icon)
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.adjustSize()
        self._move_to_screen()

    def show_message(
        self,
        title: str,
        detail: str = "",
        icon: str = "✓",
        duration_ms: Optional[int] = None,
    ) -> None:
        """Show a generic temporary notification."""
        self._recording_active = False
        self._recording_timer.stop()

        self._set_content(title, detail, icon)
        self._show_overlay()

        self._schedule_hide(
            self.MESSAGE_DURATION_MS
            if duration_ms is None
            else duration_ms
        )

    def show_screenshot(self, filename: str = "") -> None:
        """Show a short screenshot-completed notification."""
        self._recording_active = False
        self._recording_timer.stop()

        detail = filename or "Saved successfully"

        self._set_content(
            "Screenshot Taken",
            detail,
            "📸",
        )

        self._show_overlay()
        self._schedule_hide(self.SCREENSHOT_DURATION_MS)

    # =========================================================
    # RECORDING
    # =========================================================

    def start_recording(self) -> None:
        """Show persistent recording state and start elapsed timer."""
        self._recording_active = True
        self._recording_seconds = 0

        self._auto_hide_timer.stop()
        self._recording_timer.stop()

        self._update_recording_content()
        self._show_overlay()

        self._recording_timer.start()

    def stop_recording(self, filename: str = "") -> None:
        """Stop the timer and show a short recording-saved toast."""
        elapsed = self._format_duration(self._recording_seconds)

        self._recording_active = False
        self._recording_timer.stop()

        detail = f"Duration {elapsed}"

        if filename:
            detail = f"Saved • {filename}"

        self._set_content(
            "Recording Saved",
            detail,
            "■",
        )

        self._show_overlay()
        self._schedule_hide(self.SAVED_DURATION_MS)

    def _update_recording_timer(self) -> None:
        if not self._recording_active:
            self._recording_timer.stop()
            return

        self._recording_seconds += 1
        self._update_recording_content()

    def _update_recording_content(self) -> None:
        self._set_content(
            "Recording",
            self._format_duration(self._recording_seconds),
            "●",
        )

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        total_seconds = max(0, int(total_seconds))

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return f"{minutes:02d}:{seconds:02d}"

    # =========================================================
    # ANIMATION
    # =========================================================

    def _show_overlay(self) -> None:
        self._auto_hide_timer.stop()
        self._move_to_screen()

        self.show()
        self.raise_()

        self._animate_opacity(
            0.0,
            1.0,
            self.FADE_IN_MS,
        )

    def _fade_out(self, immediate: bool = False) -> None:
        if self._recording_active:
            return

        self._auto_hide_timer.stop()

        if immediate:
            self._stop_fade_animation()
            self.setWindowOpacity(0.0)
            self.hide()
            return

        self._animate_opacity(
            self.windowOpacity(),
            0.0,
            self.FADE_OUT_MS,
            hide_after=True,
        )

    def _animate_opacity(
        self,
        start_value: float,
        end_value: float,
        duration_ms: int,
        hide_after: bool = False,
    ) -> None:
        self._stop_fade_animation()

        animation = QPropertyAnimation(
            self,
            b"windowOpacity",
            self,
        )

        animation.setDuration(max(1, int(duration_ms)))
        animation.setStartValue(float(start_value))
        animation.setEndValue(float(end_value))
        animation.setEasingCurve(QEasingCurve.OutCubic)

        if hide_after:
            animation.finished.connect(self._finish_fade_out)

        self._fade_animation = animation
        animation.start()

    def _finish_fade_out(self) -> None:
        if self._recording_active:
            return

        self.setWindowOpacity(0.0)
        self.hide()

    def _stop_fade_animation(self) -> None:
        if self._fade_animation is not None:
            self._fade_animation.stop()
            self._fade_animation.deleteLater()
            self._fade_animation = None

    def _schedule_hide(self, duration_ms: int) -> None:
        if self._recording_active:
            return

        self._auto_hide_timer.start(max(1, int(duration_ms)))

    # =========================================================
    # LIFECYCLE
    # =========================================================

    def hide_osd(self) -> None:
        """Immediately hide the overlay and stop active UI timers."""
        self._recording_active = False
        self._auto_hide_timer.stop()
        self._recording_timer.stop()
        self._fade_out(immediate=True)

    def closeEvent(self, event) -> None:
        self._auto_hide_timer.stop()
        self._recording_timer.stop()
        self._stop_fade_animation()
        super().closeEvent(event)
