"""
DHEEPTHI-AI
Lightweight Glass Status Tile
--------------------------------------------

Features
✓ Lightweight Glass Card
✓ Transparent / Frosted Glass Feel
✓ Lavender Glass Border
✓ Static Hover Feedback
✓ No Real-Time Blur
✓ No Graphics Shadow Effects
✓ No Hover Animation
✓ i3-Friendly Rendering
✓ Existing Status Colors Preserved
✓ Existing Public API Preserved
"""

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
)


class StatusTileWidget(QFrame):

    # =========================================================
    # STATUS COLORS
    # =========================================================

    STATUS_COLORS = {

        "Ready": "#16A34A",
        "Online": "#16A34A",
        "Connected": "#16A34A",
        "Loaded": "#16A34A",

        "Idle": "#7C3AED",
        "Listening": "#7C3AED",

        "Silent": "#2563EB",
        "Standby": "#2563EB",

        "Inactive": "#EF4444",
        "Error": "#EF4444",

        "Thinking": "#F59E0B",

    }

    # =========================================================
    # INITIALIZATION
    # =========================================================

    def __init__(
        self,
        title,
        status,
        icon="⚙",
        parent=None
    ):

        super().__init__(parent)

        self.title = title

        self.status = status

        self.icon = icon

        self.setObjectName(
            "StatusTile"
        )

        # -----------------------------------------------------
        # Cursor
        # -----------------------------------------------------

        self.setCursor(
            Qt.PointingHandCursor
        )

        # -----------------------------------------------------
        # Hover support
        #
        # No animation.
        # No graphics effect.
        # -----------------------------------------------------

        self.setAttribute(
            Qt.WA_Hover,
            True
        )

        # -----------------------------------------------------
        # Existing card dimensions preserved
        # -----------------------------------------------------

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
        # LIGHTWEIGHT GLASS STYLE
        # =====================================================

        self.NORMAL_STYLE = """

        QFrame#StatusTile {

            background-color: rgba(
                255,
                255,
                255,
                145
            );

            border: 1px solid rgba(
                255,
                255,
                255,
                205
            );

            border-radius: 20px;

        }

        """

        # =====================================================
        # STATIC HOVER STYLE
        # =====================================================
        #
        # No shadow.
        # No animation.
        # Only a slightly stronger glass border.
        #

        self.HOVER_STYLE = """

        QFrame#StatusTile {

            background-color: rgba(
                255,
                255,
                255,
                175
            );

            border: 2px solid rgba(
                196,
                181,
                253,
                225
            );

            border-radius: 20px;

        }

        """

        # =====================================================
        # ICON GLASS STYLE
        # =====================================================

        self.ICON_NORMAL_STYLE = """

        QLabel {

            background-color: rgba(
                238,
                242,
                255,
                175
            );

            border: 1px solid rgba(
                221,
                214,
                254,
                210
            );

            border-radius: 23px;

            font-size: 22px;

        }

        """

        # =====================================================
        # ICON HOVER STYLE
        # =====================================================
        #
        # Static change only.
        #

        self.ICON_HOVER_STYLE = """

        QLabel {

            background-color: rgba(
                237,
                233,
                254,
                205
            );

            border: 2px solid rgba(
                196,
                181,
                253,
                225
            );

            border-radius: 23px;

            font-size: 24px;

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

        # -----------------------------------------------------
        # Apply normal glass style
        # -----------------------------------------------------

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
            12,
            14,
            12
        )

        root.setSpacing(
            8
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

        self.title_label = QLabel(
            self.title
        )

        self.title_label.setAlignment(
            Qt.AlignCenter
        )

        self.title_label.setWordWrap(
            True
        )

        self.title_label.setStyleSheet("""

        QLabel {

            color: #172554;

            font-size: 14px;

            font-weight: 700;

            background: transparent;

            border: none;

        }

        """)

        root.addWidget(
            self.title_label
        )

        # =====================================================
        # STATUS
        # =====================================================

        self.status_label = QLabel()

        self.status_label.setAlignment(
            Qt.AlignCenter
        )

        self.status_label.setStyleSheet("""

        QLabel {

            background: transparent;

            border: none;

        }

        """)

        root.addWidget(
            self.status_label
        )

        # =====================================================
        # INITIAL STATUS
        # =====================================================

        self.update_status(
            self.status
        )

    # =========================================================
    # UPDATE STATUS
    # =========================================================

    def update_status(
        self,
        status
    ):

        self.status = status

        # -----------------------------------------------------
        # Preserve existing status color behavior
        # -----------------------------------------------------

        color = self.STATUS_COLORS.get(
            status.title(),
            "#475569"
        )

        self.status_label.setText(
            status
        )

        self.status_label.setStyleSheet(
            f"""
            QLabel {{

                color: {color};

                font-size: 12px;

                font-weight: 700;

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

    def set_status(
        self,
        status
    ):

        self.update_status(
            status
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
    #
    # IMPORTANT:
    #
    # This is intentionally static.
    #
    # No QPropertyAnimation.
    # No shadow.
    # No graphics effect.
    #
    # =========================================================

    def enterEvent(
        self,
        event
    ):

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

        self.setStyleSheet(
            self.NORMAL_STYLE
        )

        self.icon_label.setStyleSheet(
            self.ICON_NORMAL_STYLE
        )

        super().leaveEvent(
            event
        )