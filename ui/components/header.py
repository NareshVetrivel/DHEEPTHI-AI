"""
DHEEPTHI-AI
Lightweight Glass Header V5
--------------------------------------------

Features
✓ Lightweight Glass Header
✓ Transparent / Frosted Glass Feel
✓ Improved Text Visibility
✓ No Real-Time Blur
✓ No Graphics Shadow Effects
✓ Dynamic Greeting
✓ Live Clock
✓ Responsive Layout
✓ Lavender Conversation SVG Icon
✓ Conversation Callback
✓ i3-Friendly Visual Rendering
✓ Existing Public API Preserved
"""

import os
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    QSize,
    QTimer,
)

from PySide6.QtGui import (
    QPixmap,
    QIcon,
)

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QHBoxLayout,
    QVBoxLayout,
)


class HeaderWidget(QFrame):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName(
            "HeaderWidget"
        )

        self.username = "Naresh"

        # Keep callback reference.
        # This avoids unsafe signal disconnect calls.
        self._conversation_callback = None

        self.setFixedHeight(
            126
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        # ======================================================
        # LIGHTWEIGHT GLASS HEADER
        # ======================================================
        #
        # This is a simulated glass effect.
        #
        # We intentionally DO NOT use:
        #
        #   QGraphicsBlurEffect
        #   QGraphicsDropShadowEffect
        #   animated opacity
        #   animated gradients
        #
        # Slightly higher transparency than V4 gives better
        # text contrast while keeping the background visible.
        #
        self.setStyleSheet("""

        QFrame#HeaderWidget {

            background-color: rgba(
                255,
                255,
                255,
                115
            );

            border: 1px solid rgba(
                255,
                255,
                255,
                210
            );

            border-radius: 30px;

        }

        """)

        # ======================================================
        # BUILD
        # ======================================================

        self.build_ui()

        self.start_clock()

    # ==========================================================
    # BUILD UI
    # ==========================================================

    def build_ui(self):

        self.main_layout = QHBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            38,
            14,
            38,
            14
        )

        self.main_layout.setSpacing(
            34
        )

        self.build_left_section()

        self.build_center_section()

        self.build_right_section()

        # ------------------------------------------------------
        # LEFT
        # ------------------------------------------------------

        self.main_layout.addLayout(
            self.left_layout
        )

        self.main_layout.addSpacing(
            40
        )

        self.main_layout.addStretch()

        # ------------------------------------------------------
        # CENTER
        # ------------------------------------------------------

        self.main_layout.addLayout(
            self.center_layout
        )

        self.main_layout.addStretch()

        # ------------------------------------------------------
        # RIGHT
        # ------------------------------------------------------

        self.main_layout.addLayout(
            self.right_layout
        )

    # ==========================================================
    # LEFT SECTION
    # ==========================================================

    def build_left_section(self):

        self.left_layout = QHBoxLayout()

        self.left_layout.setSpacing(
            14
        )

        self.left_layout.setAlignment(
            Qt.AlignVCenter
        )

        # ======================================================
        # LOGO
        # ======================================================

        self.logo = QLabel()

        self.logo.setFixedSize(
            100,
            100
        )

        self.logo.setAlignment(
            Qt.AlignCenter
        )

        self.logo.setStyleSheet("""
        QLabel {
            background: transparent;
            border: none;
        }
        """)

        # ======================================================
        # PERFORMANCE
        # ======================================================
        #
        # No QGraphicsDropShadowEffect.
        #
        # The logo PNG already contains its visual glow.
        #

        self.load_logo()

        # ======================================================
        # BRAND
        # ======================================================

        brand_layout = QVBoxLayout()

        brand_layout.setSpacing(
            3
        )

        brand_layout.setAlignment(
            Qt.AlignLeft |
            Qt.AlignVCenter
        )

        # ======================================================
        # TITLE
        # ======================================================

        self.title = QLabel(
            "DHEEPTHI-AI"
        )

        # Font is defined by the stylesheet with an explicit
        # positive pixel size. This avoids QFont construction
        # and Qt point-size initialization for this widget.

        # ======================================================
        # TITLE COLOUR
        # ======================================================

        self.title.setStyleSheet("""
        QLabel {

            color: #1E0A4F;

            font-family: "Segoe UI Variable";
            font-size: 31px;
            font-weight: 700;

            background: transparent;

            border: none;

        }
        """)

        # ======================================================
        # SUBTITLE
        # ======================================================

        self.subtitle = QLabel(
            "Your Personal AI Desktop Assistant"
        )

        # Font is defined by the stylesheet with an explicit
        # positive pixel size.

        # ======================================================
        # SUBTITLE COLOUR
        # ======================================================

        self.subtitle.setStyleSheet("""
        QLabel {

            color: #26324A;

            font-family: "Segoe UI";
            font-size: 14px;
            font-weight: 700;

            background: transparent;

            border: none;

        }
        """)

        brand_layout.addWidget(
            self.title
        )

        brand_layout.addWidget(
            self.subtitle
        )

        self.left_layout.addWidget(
            self.logo
        )

        self.left_layout.addLayout(
            brand_layout
        )

    # ==========================================================
    # CENTER SECTION
    # ==========================================================

    def build_center_section(self):

        self.center_layout = QVBoxLayout()

        self.center_layout.setAlignment(
            Qt.AlignCenter
        )

        self.greeting_label = QLabel()

        self.greeting_label.setAlignment(
            Qt.AlignCenter
        )

        # Font is defined by the stylesheet with an explicit
        # positive pixel size.

        # ======================================================
        # GREETING COLOUR
        # ======================================================

        self.greeting_label.setStyleSheet("""
        QLabel {

            color: #2B0A63;

            font-family: "Segoe UI Variable";
            font-size: 22px;
            font-weight: 700;

            background: transparent;

            border: none;

        }
        """)

        self.center_layout.addWidget(
            self.greeting_label,
            alignment=Qt.AlignCenter
        )

    # ==========================================================
    # RIGHT SECTION
    # ==========================================================

    def build_right_section(self):

        self.right_layout = QHBoxLayout()

        self.right_layout.setSpacing(
            10
        )

        self.right_layout.setAlignment(
            Qt.AlignRight |
            Qt.AlignVCenter
        )

        # ======================================================
        # TIME CARD
        # ======================================================

        self.time_chip = QLabel()

        # ======================================================
        # DATE CARD
        # ======================================================

        self.date_chip = QLabel()

        # ======================================================
        # DAY CARD
        # ======================================================

        self.day_chip = QLabel()

        chips = [
            self.time_chip,
            self.date_chip,
            self.day_chip,
        ]

        # ======================================================
        # LIGHTWEIGHT GLASS CHIP
        # ======================================================
        #
        # No blur.
        # No shadow.
        # No gradient.
        #
        # ONLY text visibility is improved here:
        #
        #   font-size  : 14px
        #   weight     : 700
        #   color      : deep navy-indigo
        #
        chip_style = """

        QLabel {

            background-color: rgba(
                255,
                255,
                255,
                110
            );

            border: 1px solid rgba(
                255,
                255,
                255,
                190
            );

            border-radius: 17px;

            color: #172554;

            padding: 8px 18px;

            font-size: 14px;

            font-weight: 700;

        }

        """

        # ======================================================
        # APPLY CHIP STYLE
        # ======================================================

        for chip in chips:

            chip.setMinimumHeight(
                42
            )

            chip.setMinimumWidth(
                120
            )

            chip.setAlignment(
                Qt.AlignCenter
            )

            chip.setStyleSheet(
                chip_style
            )

        # ======================================================
        # DAY CARD SMALLER
        # ======================================================

        self.day_chip.setMinimumWidth(
            95
        )

        # ======================================================
        # CONVERSATION BUTTON
        # ======================================================

        self.power_button = QPushButton()

        self.power_button.setObjectName(
            "ConversationButton"
        )

        self.power_button.setCursor(
            Qt.PointingHandCursor
        )

        self.power_button.setFixedSize(
            QSize(
                64,
                64
            )
        )

        self.power_button.setToolTip(
            "Open Conversation"
        )

        self.power_button.setFocusPolicy(
            Qt.NoFocus
        )

        # ======================================================
        # LOAD LAVENDER CONVERSATION SVG
        # ======================================================

        conversation_icon_path = os.path.join(
            "ui",
            "assets",
            "icons",
            "conversation_icon.svg"
        )

        if os.path.exists(
            conversation_icon_path
        ):

            self.power_button.setIcon(
                QIcon(
                    conversation_icon_path
                )
            )

            self.power_button.setIconSize(
                QSize(
                    44,
                    44
                )
            )

        else:

            self.power_button.setText(
                ""
            )

        # ======================================================
        # LIGHTWEIGHT GLASS BUTTON
        # ======================================================

        self.power_button.setStyleSheet("""

        QPushButton#ConversationButton {

            background-color: rgba(
                255,
                255,
                255,
                130
            );

            border: 1px solid rgba(
                255,
                255,
                255,
                205
            );

            border-radius: 21px;

            padding: 6px;

        }

        QPushButton#ConversationButton:hover {

            background-color: rgba(
                255,
                255,
                255,
                175
            );

            border: 1px solid rgba(
                167,
                139,
                250,
                220
            );

        }

        QPushButton#ConversationButton:pressed {

            background-color: rgba(
                237,
                229,
                255,
                185
            );

            border: 1px solid rgba(
                124,
                58,
                237,
                220
            );

        }

        QPushButton#ConversationButton:disabled {

            background-color: rgba(
                243,
                244,
                246,
                105
            );

            border: 1px solid rgba(
                229,
                231,
                235,
                140
            );

        }

        """)

        # ======================================================
        # PERFORMANCE
        # ======================================================
        #
        # No QGraphicsDropShadowEffect.
        #

        # ======================================================
        # ADD TIME / DATE / DAY CARDS
        # ======================================================

        self.right_layout.addWidget(
            self.time_chip
        )

        self.right_layout.addWidget(
            self.date_chip
        )

        self.right_layout.addWidget(
            self.day_chip
        )

        # ======================================================
        # GAP
        # ======================================================

        self.right_layout.addSpacing(
            8
        )

        # ======================================================
        # CONVERSATION BUTTON
        # ======================================================

        self.right_layout.addWidget(
            self.power_button
        )

    # ==========================================================
    # LOAD LOGO
    # ==========================================================

    def load_logo(self):

        logo_paths = [

            "ui/assets/dheepthi_logo-2.png",

            "assets/dheepthi_logo-2.png",

            "ui/assets/logo.png",

            "assets/logo.png",

        ]

        for path in logo_paths:

            if os.path.exists(
                path
            ):

                pix = QPixmap(
                    path
                )

                pix = pix.scaled(
                    94,
                    94,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

                self.logo.setPixmap(
                    pix
                )

                return

    # ==========================================================
    # LIVE CLOCK
    # ==========================================================

    def start_clock(self):

        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.update_datetime
        )

        self.timer.start(
            1000
        )

        self.update_datetime()

    # ==========================================================
    # UPDATE DATE / TIME / GREETING
    # ==========================================================

    def update_datetime(self):

        now = datetime.now()

        hour = now.hour

        if 5 <= hour < 12:

            greeting = "Good Morning"

        elif 12 <= hour < 17:

            greeting = "Good Afternoon"

        elif 17 <= hour < 21:

            greeting = "Good Evening"

        else:

            greeting = "Good Night"

        self.greeting_label.setText(
            f"{greeting}, {self.username} 👋🏻"
        )

        self.time_chip.setText(
            "🕒 "
            + now.strftime(
                "%I:%M:%S %p"
            )
        )

        self.date_chip.setText(
            "📅 "
            + now.strftime(
                "%d %b %Y"
            )
        )

        self.day_chip.setText(
            "☀ "
            + now.strftime(
                "%A"
            )
        )

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def set_username(
        self,
        username
    ):

        self.username = username

        self.update_datetime()

    # ----------------------------------------------------------

    def set_tagline(
        self,
        text
    ):

        self.subtitle.setText(
            text
        )

    # ----------------------------------------------------------

    def set_logo(
        self,
        image_path
    ):

        if os.path.exists(
            image_path
        ):

            pix = QPixmap(
                image_path
            )

            pix = pix.scaled(
                94,
                94,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.logo.setPixmap(
                pix
            )

    # ==========================================================
    # CONVERSATION CALLBACK
    # ==========================================================

    def set_conversation_callback(
        self,
        callback
    ):

        # ------------------------------------------------------
        # Disconnect ONLY the callback that this widget owns.
        #
        # This avoids:
        #
        # RuntimeWarning:
        # Failed to disconnect (None) from signal clicked()
        # ------------------------------------------------------

        if (
            self._conversation_callback is not None
        ):

            try:

                self.power_button.clicked.disconnect(
                    self._conversation_callback
                )

            except (
                TypeError,
                RuntimeError
            ):

                pass

        self._conversation_callback = callback

        if callback is not None:

            self.power_button.clicked.connect(
                callback
            )

    # ==========================================================
    # LEGACY POWER CALLBACK
    # ==========================================================

    def set_power_callback(
        self,
        callback
    ):

        """
        Compatibility method.

        Existing MainWindow code can continue
        using the old method name.
        """

        self.set_conversation_callback(
            callback
        )

    # ==========================================================
    # ENABLE / DISABLE
    # ==========================================================

    def set_power_enabled(
        self,
        enabled=True
    ):

        self.power_button.setEnabled(
            enabled
        )

    # ==========================================================
    # TITLE
    # ==========================================================

    def set_title(
        self,
        title
    ):

        self.title.setText(
            title
        )

    # ==========================================================
    # GREETING
    # ==========================================================

    def set_greeting(
        self,
        text
    ):

        self.greeting_label.setText(
            text
        )
