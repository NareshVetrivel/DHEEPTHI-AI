"""
ui/widgets/background_widget.py

DHEEPTHI-AI
Lightweight Static Image Background Widget

The previous version generated the background at runtime using many
QLinearGradient / QRadialGradient / particle / halo / ray operations.

This version uses one pre-rendered PNG instead. The image is loaded once,
scaled only when the widget size changes, and painted as a single pixmap.
The content widget is still placed above the background through the
existing setContentWidget() API.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QWidget


class BackgroundWidget(QWidget):
    """Lightweight static-image background container."""

    _BACKGROUND_RELATIVE_PATH = Path(
        "ui",
        "assets",
        "backgrounds",
        "dheepthi_halo_background.png",
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        # Background is rendered directly by QPainter.
        # No stylesheet background painting is required.
        self.setAttribute(Qt.WA_StyledBackground, False)

        self.layout = QVBoxLayout(self)

        self.layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.layout.setSpacing(0)

        # Kept for compatibility with existing code.
        self.fast_mode = True

        # Load the source image only once.
        self._background_pixmap = self._load_background()

        # Cached scaled version.
        self._scaled_background = QPixmap()

        if (
            not self._background_pixmap.isNull()
            and self.width() > 0
            and self.height() > 0
        ):
            self._update_scaled_background()

    # ------------------------------------------------
    # Public API
    # ------------------------------------------------

    def setContentWidget(self, widget):
        """
        Place the existing application content above
        the static background.
        """
        self.layout.addWidget(widget)

    # ------------------------------------------------
    # Background Asset
    # ------------------------------------------------

    @classmethod
    def _asset_path(cls) -> Path:
        """
        Resolve the project-root-relative background asset.

        Expected structure:

        DHEEPTHI-AI/
        └── ui/
            └── assets/
                └── backgrounds/
                    └── dheepthi_halo_background.png
        """

        project_root = Path(__file__).resolve().parents[2]

        return project_root / cls._BACKGROUND_RELATIVE_PATH

    @classmethod
    def _load_background(cls) -> QPixmap:
        """Load the static background image once."""

        path = cls._asset_path()

        pixmap = QPixmap(str(path))

        # Null pixmap is allowed so the application can still start
        # if the asset is temporarily missing.
        return pixmap

    # ------------------------------------------------
    # Cached Scaling
    # ------------------------------------------------

    def _update_scaled_background(self):
        """
        Scale the source image only when the widget size changes.

        Normal paint events reuse this cached pixmap.
        """

        if self._background_pixmap.isNull():
            self._scaled_background = QPixmap()
            return

        self._scaled_background = self._background_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

    # ------------------------------------------------
    # Qt Events
    # ------------------------------------------------

    def resizeEvent(self, event):
        """
        Re-scale only when the window/widget is resized.
        """

        super().resizeEvent(event)

        self._update_scaled_background()

    # ------------------------------------------------
    # Paint
    # ------------------------------------------------

    def paintEvent(self, event):
        """
        Paint the complete background using one cached pixmap.

        No gradients.
        No radial glow calculations.
        No particles.
        No halo construction.
        No floor effects.
        No animated effects.
        """

        painter = QPainter(self)

        try:

            painter.setRenderHint(
                QPainter.SmoothPixmapTransform,
                True,
            )

            if not self._scaled_background.isNull():

                # KeepAspectRatioByExpanding means the image may be
                # slightly larger than the widget.
                #
                # Center crop it so the complete widget is covered.

                x = (
                    self._scaled_background.width()
                    - self.width()
                ) // 2

                y = (
                    self._scaled_background.height()
                    - self.height()
                ) // 2

                painter.drawPixmap(
                    -max(0, x),
                    -max(0, y),
                    self._scaled_background,
                )

            else:

                # Safe fallback if image is missing.
                painter.fillRect(
                    self.rect(),
                    Qt.transparent,
                )

        finally:

            painter.end()