"""
ASTRA-AI
Premium Header V3
--------------------------------------------

Features
✓ Glass Header
✓ Premium Logo Glow
✓ Dynamic Greeting
✓ Live Clock
✓ Responsive Layout
✓ Lavender Conversation SVG Icon
✓ Conversation Callback
✓ Clean Architecture
"""

import os
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    QSize,
    QTimer,
)

from PySide6.QtGui import (
    QColor,
    QFont,
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
    QGraphicsDropShadowEffect,
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
        # HEADER STYLE
        # ======================================================

        self.setStyleSheet("""

        QFrame#HeaderWidget {

            background: qlineargradient(

                x1: 0,
                y1: 0,
                x2: 1,
                y2: 1,

                stop: 0 rgba(255, 250, 255, 235),
                stop: 0.18 rgba(250, 245, 255, 230),
                stop: 0.45 rgba(243, 238, 255, 220),
                stop: 0.72 rgba(240, 236, 255, 225),
                stop: 1 rgba(255, 252, 255, 235)

            );

            border: 2px solid rgba(255, 255, 255, 210);

            border-radius: 32px;

        }

        """)

        # ======================================================
        # HEADER SHADOW
        # ======================================================

        shadow = QGraphicsDropShadowEffect(
            self
        )

        shadow.setBlurRadius(
            40
        )

        shadow.setOffset(
            0,
            12
        )

        shadow.setColor(
            QColor(
                170,
                155,
                255,
                60
            )
        )

        self.setGraphicsEffect(
            shadow
        )

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

        glow = QGraphicsDropShadowEffect()

        glow.setBlurRadius(
            90
        )

        glow.setOffset(
            0,
            0
        )

        glow.setColor(
            QColor(
                146,
                96,
                255,
                210
            )
        )

        self.logo.setGraphicsEffect(
            glow
        )

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

        self.title = QLabel(
            "DHEEPTHI-AI"
        )

        self.title.setFont(
            QFont(
                "Segoe UI Variable",
                31,
                QFont.Bold
            )
        )

        self.title.setStyleSheet("""
        QLabel {
            color: #1F2937;
            background: transparent;
            border: none;
        }
        """)

        self.subtitle = QLabel(
            "Your Personal AI Desktop Assistant"
        )

        self.subtitle.setFont(
            QFont(
                "Segoe UI",
                14
            )
        )

        self.subtitle.setStyleSheet("""
        QLabel {
            color: #64748B;
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

        self.greeting_label.setFont(
            QFont(
                "Segoe UI Variable",
                22,
                QFont.Bold
            )
        )

        self.greeting_label.setStyleSheet("""
        QLabel {
            color: #111827;
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
        # GLASS CARD STYLE
        # ======================================================

        chip_style = """

        QLabel {

            background: qlineargradient(

                x1: 0,
                y1: 0,
                x2: 1,
                y2: 1,

                stop: 0 rgba(255, 255, 255, 245),
                stop: 1 rgba(246, 243, 255, 225)

            );

            border: 1px solid rgba(255, 255, 255, 220);

            border-radius: 18px;

            color: #374151;

            padding: 8px 18px;

            font-size: 13px;

            font-weight: 600;

        }

        """

        # ======================================================
        # APPLY CARD STYLE
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

            chip_shadow = QGraphicsDropShadowEffect(
                chip
            )

            chip_shadow.setBlurRadius(
                20
            )

            chip_shadow.setOffset(
                0,
                5
            )

            chip_shadow.setColor(
                QColor(
                    180,
                    170,
                    255,
                    35
                )
            )

            chip.setGraphicsEffect(
                chip_shadow
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
        # CONVERSATION BUTTON STYLE
        # ======================================================

        self.power_button.setStyleSheet("""

        QPushButton#ConversationButton {

            background: qlineargradient(

                x1: 0,
                y1: 0,
                x2: 1,
                y2: 1,

                stop: 0 #FFFFFF,
                stop: 1 #F7F2FF

            );

            border: 2px solid #DDD6FE;

            border-radius: 22px;

            padding: 6px;

        }

        QPushButton#ConversationButton:hover {

            background: qlineargradient(

                x1: 0,
                y1: 0,
                x2: 1,
                y2: 1,

                stop: 0 #FFFFFF,
                stop: 1 #F1EBFF

            );

            border: 2px solid #A78BFA;

        }

        QPushButton#ConversationButton:pressed {

            background: #EDE5FF;

            border: 2px solid #7C3AED;

        }

        QPushButton#ConversationButton:disabled {

            background: #F3F4F6;

            border: 2px solid #E5E7EB;

        }

        """)

        # ======================================================
        # LAVENDER GLOW
        # ======================================================

        conversation_glow = QGraphicsDropShadowEffect(
            self.power_button
        )

        conversation_glow.setBlurRadius(
            28
        )

        conversation_glow.setOffset(
            0,
            4
        )

        conversation_glow.setColor(
            QColor(
                139,
                92,
                246,
                90
            )
        )

        self.power_button.setGraphicsEffect(
            conversation_glow
        )

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
            f"{greeting}, {self.username} 👋"
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