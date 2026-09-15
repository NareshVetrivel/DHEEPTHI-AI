"""
DHEEPTHI-AI
Lightweight Glass Status Metric Tile
--------------------------------------------

Features
✓ Lightweight Glass Metric Card
✓ Transparent / Frosted Glass Feel
✓ Background Remains Visible
✓ Strong Text Visibility
✓ High Contrast Titles
✓ High Contrast Metric Values
✓ No Real-Time Blur
✓ No Graphics Drop Shadow
✓ No Hover Animation
✓ Lightweight Hover State
✓ Existing Public API Preserved
✓ i3-Friendly Rendering
✓ Existing Right Panel Integration Preserved
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
)

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
)


class StatusMetricTile(QFrame):

    def __init__(
        self,
        title,
        value,
        icon="📊",
        color="#16A34A",
        parent=None,
    ):

        super().__init__(
            parent
        )

        # =====================================================
        # DATA
        # =====================================================

        self.title = title

        self.value = value

        self.icon = icon

        self.value_color = color

        # =====================================================
        # OBJECT
        # =====================================================

        self.setObjectName(
            "MetricTile"
        )

        self.setCursor(
            Qt.PointingHandCursor
        )

        self.setAttribute(
            Qt.WA_Hover,
            True
        )

        # =====================================================
        # FIXED TILE SIZE
        # =====================================================

        self.setMinimumSize(
            150,
            118
        )

        self.setMaximumSize(
            150,
            118
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        # =====================================================
        # RUNTIME STATE
        # =====================================================

        self._hovered = False

        # -----------------------------------------------------
        # Compatibility with RightPanelWidget
        # -----------------------------------------------------
        #
        # RightPanelWidget checks tile.shadow.
        #
        # We intentionally do not create a graphics effect.
        #

        self.shadow = None

        # =====================================================
        # NORMAL GLASS STYLE
        # =====================================================
        #
        # Slightly stronger glass layer than previous version.
        #
        # This keeps the background visible while improving
        # readability of the metric card.
        #

        self.NORMAL_STYLE = """

        QFrame#MetricTile {

            background-color: rgba(
                248,
                247,
                255,
                168
            );

            border: 1px solid rgba(
                255,
                255,
                255,
                225
            );

            border-radius: 20px;

        }

        """

        # =====================================================
        # HOVER GLASS STYLE
        # =====================================================

        self.HOVER_STYLE = """

        QFrame#MetricTile {

            background-color: rgba(
                255,
                255,
                255,
                190
            );

            border: 2px solid rgba(
                124,
                58,
                237,
                210
            );

            border-radius: 20px;

        }

        """

        # =====================================================
        # ICON NORMAL STYLE
        # =====================================================

        self.ICON_NORMAL_STYLE = """

        QLabel {

            background-color: rgba(
                255,
                255,
                255,
                155
            );

            border: 1px solid rgba(
                221,
                214,
                254,
                220
            );

            border-radius: 23px;

            font-size: 22px;

            color: #17142F;

        }

        """

        # =====================================================
        # ICON HOVER STYLE
        # =====================================================

        self.ICON_HOVER_STYLE = """

        QLabel {

            background-color: rgba(
                255,
                255,
                255,
                180
            );

            border: 2px solid rgba(
                124,
                58,
                237,
                220
            );

            border-radius: 23px;

            font-size: 23px;

            color: #17142F;

        }

        """

        # =====================================================
        # BUILD
        # =====================================================

        self.build_ui()

    # =========================================================
    # BUILD UI
    # =========================================================

    def build_ui(self):

        # =====================================================
        # CARD STYLE
        # =====================================================

        self.setStyleSheet(
            self.NORMAL_STYLE
        )

        # =====================================================
        # ROOT LAYOUT
        # =====================================================

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            14,
            10,
            14,
            10
        )

        root.setSpacing(
            6
        )

        root.setAlignment(
            Qt.AlignCenter
        )

        # =====================================================
        # ICON
        # =====================================================

        self.icon_label = QLabel(
            self.icon
        )

        self.icon_label.setAlignment(
            Qt.AlignCenter
        )

        self.icon_label.setFixedSize(
            46,
            46
        )

        self.icon_label.setStyleSheet(
            self.ICON_NORMAL_STYLE
        )

        root.addWidget(
            self.icon_label,
            alignment=Qt.AlignCenter
        )

        # =====================================================
        # TITLE
        # =====================================================
        #
        # Increased contrast:
        #
        # Old:
        #   #17142F
        #
        # New:
        #   #0B0820
        #
        # This makes Health / CPU / Memory / Storage etc.
        # clearly readable over the glass background.
        #

        self.title_label = QLabel(
            self.title
        )

        self.title_label.setAlignment(
            Qt.AlignCenter
        )

        self.title_label.setWordWrap(
            True
        )

        self.title_label.setStyleSheet(
            """

            QLabel {

                color: #0B0820;

                font-size: 15px;

                font-weight: 800;

                background: transparent;

                border: none;

            }

            """
        )

        root.addWidget(
            self.title_label
        )

        # =====================================================
        # VALUE
        # =====================================================

        self.value_label = QLabel()

        self.value_label.setAlignment(
            Qt.AlignCenter
        )

        root.addWidget(
            self.value_label
        )

        # =====================================================
        # INITIAL VALUE
        # =====================================================

        self.update_value(
            self.value,
            self.value_color
        )

    # =========================================================
    # UPDATE VALUE
    # =========================================================

    def update_value(
        self,
        value,
        color=None,
    ):

        self.value = value

        # -----------------------------------------------------
        # Update color
        # -----------------------------------------------------

        if color is not None:

            self.value_color = color

        # -----------------------------------------------------
        # Set value
        # -----------------------------------------------------

        self.value_label.setText(
            str(value)
        )

        # -----------------------------------------------------
        # Strong readable metric value
        # -----------------------------------------------------

        self.value_label.setStyleSheet(
            f"""

            QLabel {{

                color: {self.value_color};

                font-size: 13px;

                font-weight: 800;

                background: transparent;

                border: none;

            }}

            """
        )

    # =========================================================
    # PUBLIC API
    # =========================================================

    def set_title(
        self,
        title
    ):

        self.title = title

        self.title_label.setText(
            title
        )

    # ---------------------------------------------------------

    def set_icon(
        self,
        icon
    ):

        self.icon = icon

        self.icon_label.setText(
            icon
        )

    # ---------------------------------------------------------

    def set_value(
        self,
        value,
        color=None
    ):

        self.update_value(
            value,
            color
        )

    # ---------------------------------------------------------

    def set_card_enabled(
        self,
        enabled
    ):

        self.setEnabled(
            enabled
        )

        if enabled:

            self.setWindowOpacity(
                1.0
            )

        else:

            self.setWindowOpacity(
                0.55
            )

    # =========================================================
    # HOVER ENTER
    # =========================================================

    def enterEvent(
        self,
        event
    ):

        self._hovered = True

        # -----------------------------------------------------
        # Lightweight hover.
        #
        # No shadow.
        # No animation.
        # No blur.
        # -----------------------------------------------------

        self.setStyleSheet(
            self.HOVER_STYLE
        )

        self.icon_label.setStyleSheet(
            self.ICON_HOVER_STYLE
        )

        super().enterEvent(
            event
        )

    # =========================================================
    # HOVER LEAVE
    # =========================================================

    def leaveEvent(
        self,
        event
    ):

        self._hovered = False

        # -----------------------------------------------------
        # Restore normal glass.
        # -----------------------------------------------------

        self.setStyleSheet(
            self.NORMAL_STYLE
        )

        self.icon_label.setStyleSheet(
            self.ICON_NORMAL_STYLE
        )

        super().leaveEvent(
            event
        )