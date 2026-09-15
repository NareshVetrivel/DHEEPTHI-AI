"""
DHEEPTHI
Premium Conversation Panel

Lightweight ChatGPT/WhatsApp-style conversation UI.

Features:
- Compact adaptive message bubbles
- User messages on the right
- DHEEPTHI replies on the left
- Temporary in-memory history
- History survives panel hide/show
- History is lost automatically when the application exits
- Adaptive one-line composer
- Lightweight animated typing/loading indicator
- Rotating greeting whenever an empty conversation is opened
- No Gemini/backend dependency inside this widget
"""

from __future__ import annotations

import random

from typing import Callable, Optional

from PySide6.QtCore import (
    Qt,
    Signal,
    QTimer,
    QPropertyAnimation,
    QMimeData,
)

from PySide6.QtGui import (
    QColor,
    QPalette,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QMessageBox,
)


# ==============================================================
# Message Bubble
# ==============================================================

class MessageBubble(QFrame):

    MIN_BUBBLE_WIDTH = 72

    ABSOLUTE_MAX_WIDTH = 420

    def _normalize_message(self, message: str) -> str:

        lines = str(message).splitlines()

        cleaned = []
        previous_blank = False

        for line in lines:

            line = line.strip()

            if not line:

                if previous_blank:
                    continue

                previous_blank = True
                cleaned.append("")

            else:

                previous_blank = False
                cleaned.append(line)

        return "\n".join(cleaned).strip()

    def __init__(
        self,
        message: str,
        is_user: bool = False,
        max_width: int = 360,
        parent: Optional[QWidget] = None,
    ):

        super().__init__(parent)

        self.message = self._normalize_message(
            message
        )

        self.is_user = bool(
            is_user
        )

        self._max_width = max(
            self.MIN_BUBBLE_WIDTH,
            min(
                self.ABSOLUTE_MAX_WIDTH,
                int(max_width)
            ),
        )

        self.setObjectName(
            "UserMessage"
            if self.is_user
            else "AssistantMessage"
        )

        self.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Fixed
        )

        self.setMinimumHeight(
            0
        )

        layout = QVBoxLayout(
            self
        )

        # ------------------------------------------------------
        # Compact WhatsApp-style spacing
        # ------------------------------------------------------

        layout.setContentsMargins(
            12,
            9,
            12,
            7
        )

        layout.setSpacing(
            2
        )

        # ======================================================
        # SENDER
        # ======================================================

        self.sender_label = QLabel(
            "You"
            if self.is_user
            else "DHEEPTHI"
        )

        self.sender_label.setObjectName(
            "MessageSender"
        )

        self.sender_label.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Fixed
        )

        # ======================================================
        # MESSAGE
        # ======================================================

        self.text_label = QLabel(
            self.message
        )

        self.text_label.setObjectName(
            "MessageText"
        )

        self.text_label.setWordWrap(
            True
        )

        self.text_label.setAlignment(
            Qt.AlignLeft |
            Qt.AlignTop
        )

        self.text_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        self.text_label.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Fixed
        )

        layout.addWidget(
            self.sender_label
        )

        layout.addWidget(
            self.text_label
        )

        # ======================================================
        # STYLE
        # ======================================================

        self.setStyleSheet(
            """

            QFrame#UserMessage {

                background:rgba(124,58,237,175);

                border:1px solid rgba(255,255,255,175);

                border-radius:16px;

            }

            QFrame#AssistantMessage {

                background:rgba(255,255,255,105);

                border:1px solid rgba(255,255,255,190);

                border-radius:16px;

            }

            QLabel#MessageSender {

                color:#21134F;

                font-family:"Poppins";

                font-size:11px;

                font-weight:700;

                background:transparent;

            }

            QLabel#MessageText {

                color:#17142F;

                font-family:"Poppins";

                font-size:13px;

                background:transparent;

            }

            """
        )

        self.set_available_width(
            self._max_width
        )

    # ==========================================================
    # RESPONSIVE WIDTH / HEIGHT
    # ==========================================================

    def set_available_width(
        self,
        max_width: int
    ):

        try:

            max_width = max(
                self.MIN_BUBBLE_WIDTH,
                min(
                    self.ABSOLUTE_MAX_WIDTH,
                    int(max_width)
                ),
            )

            self._max_width = max_width

            # --------------------------------------------------
            # Fonts
            # --------------------------------------------------
            #
            # Keep font configuration in the stylesheet below.
            # This intentionally avoids constructing QFont objects
            # at runtime. Qt's family-only/default font paths can
            # temporarily carry a point size of -1 and produce:
            #   QFont::setPointSize: Point size <= 0 (-1)
            #
            # The stylesheet uses explicit positive pixel sizes for
            # MessageText (13px) and MessageSender (11px).
            # --------------------------------------------------

            self.text_label.ensurePolished()
            self.sender_label.ensurePolished()

            # --------------------------------------------------
            # Bubble horizontal padding
            # left + right = 20px
            # --------------------------------------------------

            horizontal = 20

            # --------------------------------------------------
            # Bubble vertical padding
            # top + bottom = 7px
            # --------------------------------------------------

            vertical = 16

            # --------------------------------------------------
            # Gap between DHEEPTHI/You and message
            # --------------------------------------------------

            spacing = 1

            # --------------------------------------------------
            # Calculate natural width without QFont/QFontMetrics.
            # --------------------------------------------------
            # QLabel sizeHint() uses the active stylesheet, so font
            # configuration remains entirely stylesheet-driven.
            # This avoids runtime font metric construction.
            # --------------------------------------------------

            longest_line = 0

            for line in self.message.split("\n"):

                probe = QLabel(line)
                probe.setObjectName("MessageText")
                probe.setStyleSheet(
                    "QLabel#MessageText { "
                    "font-family: \"Poppins\"; "
                    "font-size: 13px; "
                    "font-weight: 400; }"
                )
                probe.ensurePolished()

                longest_line = max(
                    longest_line,
                    probe.sizeHint().width()
                )

                probe.deleteLater()

            sender_probe = QLabel(
                self.sender_label.text()
            )
            sender_probe.setObjectName(
                "MessageSender"
            )
            sender_probe.setStyleSheet(
                "QLabel#MessageSender { "
                "font-family: \"Poppins\"; "
                "font-size: 11px; "
                "font-weight: 700; }"
            )
            sender_probe.ensurePolished()

            sender_width = sender_probe.sizeHint().width()
            sender_probe.deleteLater()

            natural_width = max(
                self.MIN_BUBBLE_WIDTH,
                longest_line + horizontal,
                sender_width + horizontal,
            )

            bubble_width = min(
                natural_width,
                max_width
            )

            inner_width = max(
                40,
                bubble_width - horizontal
            )

            # --------------------------------------------------
            # Set text width first
            # --------------------------------------------------

            self.text_label.setFixedWidth(
                inner_width
            )

            # --------------------------------------------------
            # IMPORTANT:
            # Let QLabel calculate its REAL wrapped height.
            #
            # Do NOT use QFontMetrics.boundingRect()
            # for the final widget height.
            # --------------------------------------------------

            self.text_label.setFixedHeight(
                0
            )

            self.text_label.adjustSize()

            text_height = max(
                18,
                self.text_label.sizeHint().height()
            )

            # --------------------------------------------------
            # Sender actual height
            # --------------------------------------------------

            self.sender_label.adjustSize()

            sender_height = max(
                16,
                self.sender_label.sizeHint().height()
            )

            # --------------------------------------------------
            # Apply exact heights
            # --------------------------------------------------

            self.sender_label.setFixedHeight(
                sender_height
            )

            self.text_label.setFixedHeight(
                text_height
            )

            self.setFixedWidth(
                bubble_width
            )

            # --------------------------------------------------
            # FINAL BUBBLE HEIGHT
            #
            # sender
            # + spacing
            # + actual text
            # + top/bottom padding
            # --------------------------------------------------

            total_height = (
                sender_height
                +
                spacing
                +
                text_height
                +
                vertical
            )

            self.setFixedHeight(
                max(
                    46,
                    total_height
                )
            )

        except RuntimeError:

            pass

    # ==========================================================
    # UPDATE MESSAGE
    # ==========================================================

    def update_message(
        self,
        message: str
    ):

        self.message = self._normalize_message(
            message
        )

        self.text_label.setText(
            self.message
        )

        self.set_available_width(
            self._max_width
        )


# ==============================================================
# LIGHTWEIGHT TYPING / LOADING BUBBLE
# ==============================================================

class TypingBubble(QFrame):

    """
    Lightweight DHEEPTHI loading indicator.

    Designed specifically for lower-end systems such as:
    - Intel i5
    - 8 GB RAM
    - Integrated graphics

    No GIF.
    No movie.
    No heavy graphics animation.

    Uses a tiny QTimer and text updates only.
    """

    def __init__(
        self,
        max_width: int = 230,
        parent: Optional[QWidget] = None,
    ):

        super().__init__(
            parent
        )

        self._max_width = max(
            140,
            min(
                260,
                int(max_width)
            )
        )

        self._step = 0

        self.setObjectName(
            "TypingBubble"
        )

        self.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Fixed
        )

        self.setStyleSheet(
            """

            QFrame#TypingBubble {

                background:rgba(255,255,255,95);

                border:1px solid rgba(255,255,255,175);

                border-radius:16px;

            }

            QLabel#TypingSender {

                color:#21134F;

                font-family:"Poppins";

                font-size:11px;

                font-weight:700;

                background:transparent;

            }

            QLabel#TypingDots {

                color:#7C3AED;

                font-family:"Segoe UI";

                font-size:14px;

                font-weight:700;

                background:transparent;

            }

            """
        )

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            14,
            8,
            14,
            8
        )

        layout.setSpacing(
            7
        )

        # ------------------------------------------------------
        # DHEEPTHI label
        # ------------------------------------------------------

        self.sender_label = QLabel(
            "DHEEPTHI"
        )

        self.sender_label.setObjectName(
            "TypingSender"
        )

        self.sender_label.setFixedHeight(
            18
        )

        # ------------------------------------------------------
        # Animated dots
        # ------------------------------------------------------

        self.dots_label = QLabel(
            "●  ○  ○"
        )

        self.dots_label.setObjectName(
            "TypingDots"
        )

        self.dots_label.setFixedWidth(
            48
        )

        self.dots_label.setFixedHeight(
            20
        )

        layout.addWidget(
            self.sender_label
        )

        layout.addWidget(
            self.dots_label
        )

        # ------------------------------------------------------
        # Calculate compact width
        # ------------------------------------------------------

        # Use the stylesheet-resolved QLabel size instead of
        # QLabel.fontMetrics().
        self.sender_label.ensurePolished()

        natural_width = (
            self.sender_label.sizeHint().width()
            +
            48
            +
            35
        )

        self.setFixedWidth(
            min(
                self._max_width,
                max(
                    125,
                    natural_width
                )
            )
        )

        self.setFixedHeight(
            42
        )

        # ------------------------------------------------------
        # Lightweight timer
        # ------------------------------------------------------

        self._timer = QTimer(
            self
        )

        self._timer.setInterval(
            320
        )

        self._timer.timeout.connect(
            self._animate
        )

        self._timer.start()

    # ==========================================================
    # ANIMATION
    # ==========================================================

    def _animate(
        self
    ):

        try:

            patterns = (
                "●  ○  ○",
                "○  ●  ○",
                "○  ○  ●",
                "○  ●  ○",
            )

            self._step = (
                self._step + 1
            ) % len(patterns)

            self.dots_label.setText(
                patterns[self._step]
            )

        except RuntimeError:

            self._timer.stop()

    # ==========================================================
    # STOP
    # ==========================================================

    def stop(
        self
    ):

        try:

            if self._timer.isActive():

                self._timer.stop()

        except RuntimeError:

            pass

    # ==========================================================
    # CLEANUP
    # ==========================================================

    def closeEvent(
        self,
        event
    ):

        self.stop()

        super().closeEvent(
            event
        )

    def hideEvent(
        self,
        event
    ):

        self.stop()

        super().hideEvent(
            event
        )


# ==============================================================
# Message Composer
# ==============================================================

class MessageComposer(QPlainTextEdit):

    send_requested = Signal()
    limit_exceeded = Signal()

    MAX_WORDS = 1000

    MIN_HEIGHT = 42

    MAX_HEIGHT = 105

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ):

        super().__init__(
            parent
        )

        self.setObjectName(
            "MessageInput"
        )

        self.setMinimumHeight(
            self.MIN_HEIGHT
        )

        self.setMaximumHeight(
            self.MAX_HEIGHT
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.textChanged.connect(
            self._update_height
        )

        QTimer.singleShot(
            0,
            self._update_height
        )

    # ==========================================================
    # WORD LIMIT HELPERS
    # ==========================================================

    @staticmethod
    def _word_count(text: str) -> int:

        return len(
            str(text).split()
        )

    def _text_after_replacement(
        self,
        inserted_text: str
    ) -> str:
        """Return the document text after replacing the current selection."""

        cursor = self.textCursor()

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        current = self.toPlainText()

        return (
            current[:start]
            + str(inserted_text)
            + current[end:]
        )

    def _would_exceed_limit(
        self,
        inserted_text: str
    ) -> bool:

        candidate = self._text_after_replacement(
            inserted_text
        )

        return (
            self._word_count(candidate)
            >
            self.MAX_WORDS
        )

    def _notify_limit_exceeded(self):

        self.limit_exceeded.emit()

    # ==========================================================
    # PASTE PROTECTION
    # ==========================================================

    def insertFromMimeData(
        self,
        source: QMimeData
    ):
        """
        Reject a paste that would push the message beyond
        1000 words. The pasted content is not partially trimmed.
        """

        try:

            if source is None:

                return

            pasted_text = source.text()

            if not pasted_text:

                return

            if self._would_exceed_limit(
                pasted_text
            ):

                self._notify_limit_exceeded()
                return

            super().insertFromMimeData(
                source
            )

        except RuntimeError:

            pass

    # ==========================================================
    # ADAPTIVE HEIGHT
    # ==========================================================

    def _update_height(
        self
    ):

        try:

            document_height = (
                self.document()
                .documentLayout()
                .documentSize()
                .height()
            )

            margins = (
                self.contentsMargins().top()
                +
                self.contentsMargins().bottom()
            )

            required = int(
                document_height
                +
                margins
                +
                8
            )

            required = max(
                self.MIN_HEIGHT,
                required
            )

            required = min(
                self.MAX_HEIGHT,
                required
            )

            self.setFixedHeight(
                required
            )

            if (
                document_height
                >
                self.MAX_HEIGHT - 20
            ):

                self.setVerticalScrollBarPolicy(
                    Qt.ScrollBarAsNeeded
                )

            else:

                self.setVerticalScrollBarPolicy(
                    Qt.ScrollBarAlwaysOff
                )

            self.updateGeometry()

        except RuntimeError:

            pass

    # ==========================================================
    # KEYBOARD
    # ==========================================================

    def _show_parent_limit_popup(self):
        parent = self.parentWidget()
        while parent is not None and not hasattr(parent, "_show_word_limit_popup"):
            parent = parent.parentWidget()
        if parent is not None:
            parent._show_word_limit_popup()

    def insertFromMimeData(self, source):
        current = self.toPlainText()
        incoming = source.text() if source is not None else ""
        cursor = self.textCursor()
        selected = cursor.selectedText()
        candidate = current[:cursor.selectionStart()] + incoming + current[cursor.selectionEnd():]

        if len(candidate.split()) > self.MAX_WORDS:
            self._show_parent_limit_popup()
            return

        super().insertFromMimeData(source)

    def _would_exceed_word_limit(self, text: str) -> bool:
        return len(str(text).split()) > self.MAX_WORDS

    def keyPressEvent(
        self,
        event
    ):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                cursor = self.textCursor()
                candidate = (
                    self.toPlainText()[:cursor.selectionStart()]
                    + "\n"
                    + self.toPlainText()[cursor.selectionEnd():]
                )
                if self._would_exceed_word_limit(candidate):
                    self._show_parent_limit_popup()
                    event.accept()
                    return
                cursor.insertText("\n")
                self.setTextCursor(cursor)
                return

            if self._would_exceed_word_limit(self.toPlainText()):
                self._show_parent_limit_popup()
                event.accept()
                return

            self.send_requested.emit()
            event.accept()
            return

        # Block normal typing once the next edit would cross 1000 words.
        # Navigation, deletion and shortcuts remain available.
        if (
            not (
                event.modifiers()
                & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
            )
            and event.text()
        ):
            cursor = self.textCursor()
            current = self.toPlainText()
            candidate = (
                current[:cursor.selectionStart()]
                + event.text()
                + current[cursor.selectionEnd():]
            )
            if self._would_exceed_word_limit(candidate):
                self._show_parent_limit_popup()
                event.accept()
                return

        super().keyPressEvent(event)


# ==============================================================
# PREMIUM GLASS CLOSE BUTTON
# ==============================================================

class PremiumCloseButton(QPushButton):

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ):

        super().__init__(
            "×",
            parent
        )

        self.setObjectName(
            "PremiumCloseButton"
        )

        self.setFixedSize(
            38,
            38
        )

        self.setCursor(
            Qt.PointingHandCursor
        )

        self.setFocusPolicy(
            Qt.NoFocus
        )

        self.setToolTip(
            "Close conversation"
        )

        self.setStyleSheet(
            """

            QPushButton#PremiumCloseButton {

                background:#DC2626;

                color:white;

                border:2px solid rgba(255,255,255,170);

                border-radius:19px;

                font-family:"Segoe UI";

                font-size:22px;

                font-weight:500;

                padding:0px;

            }

            QPushButton#PremiumCloseButton:hover {

                background:#B91C1C;

                border:2px solid rgba(255,255,255,210);

            }

            QPushButton#PremiumCloseButton:pressed {

                background:#991B1B;

                border:2px solid rgba(255,255,255,190);

            }

            """
        )

        # ------------------------------------------------------
        # Lightweight purple glow
        # ------------------------------------------------------

        self.shadow = QGraphicsDropShadowEffect(
            self
        )

        self.shadow.setOffset(
            0,
            0
        )

        self.shadow.setBlurRadius(
            0
        )

        self.shadow.setColor(
            QColor(
                124,
                58,
                237,
                0
            )
        )

        self.setGraphicsEffect(
            self.shadow
        )

        self.glow_animation = QPropertyAnimation(
            self.shadow,
            b"blurRadius",
            self
        )

        self.glow_animation.setDuration(
            160
        )

    # ==========================================================
    # HOVER ENTER
    # ==========================================================

    def enterEvent(
        self,
        event
    ):

        self.glow_animation.stop()

        self.shadow.setColor(
            QColor(
                124,
                58,
                237,
                170
            )
        )

        self.glow_animation.setStartValue(
            self.shadow.blurRadius()
        )

        self.glow_animation.setEndValue(
            22
        )

        self.glow_animation.start()

        super().enterEvent(
            event
        )

    # ==========================================================
    # HOVER LEAVE
    # ==========================================================

    def leaveEvent(
        self,
        event
    ):

        self.glow_animation.stop()

        self.glow_animation.setStartValue(
            self.shadow.blurRadius()
        )

        self.glow_animation.setEndValue(
            0
        )

        self.glow_animation.start()

        super().leaveEvent(
            event
        )

    # ==========================================================
    # HIDE
    # ==========================================================

    def hideEvent(
        self,
        event
    ):

        self.glow_animation.stop()

        super().hideEvent(
            event
        )


# ==============================================================
# Conversation Panel
# ==============================================================

class ConversationPanel(QWidget):

    send_requested = Signal(str)

    close_requested = Signal()

    MAX_WORDS = 1000

    GREETINGS = (

        "Welcome, Naresh!",

        "Hey Naresh! Ready when you are.",

        "Welcome back, Naresh!",

        "Good to see you, Naresh!",

        "Hi Naresh! What can I help you with today?",

        "Hello Naresh! DHEEPTHI is ready.",

        "Hey Naresh! Let's get things done.",

        "Welcome, Naresh!",

    )

    # ==========================================================
    # CONSTRUCTOR
    # ==========================================================

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        user_name: str = "Naresh",
    ):

        super().__init__(
            parent
        )

        self.user_name = user_name

        # ------------------------------------------------------
        # Existing message widget storage
        # ------------------------------------------------------

        self._message_widgets = []

        self._welcome_widget = None

        # ------------------------------------------------------
        # Existing callback integration
        # ------------------------------------------------------

        self._send_callback: Optional[
            Callable[[str], None]
        ] = None

        self._is_submitting = False

        # ------------------------------------------------------
        # Temporary in-memory conversation history
        # ------------------------------------------------------

        self._conversation_history: list[
            dict[str, str]
        ] = []

        self.MAX_HISTORY_MESSAGES = 40

        # ------------------------------------------------------
        # Greeting tracking
        # ------------------------------------------------------

        self._last_greeting = None

        # ------------------------------------------------------
        # Lightweight loading state
        # ------------------------------------------------------

        self._typing_bubble: Optional[
            TypingBubble
        ] = None

        self._typing_wrapper: Optional[
            QWidget
        ] = None

        # ------------------------------------------------------
        # Object
        # ------------------------------------------------------

        self.setObjectName(
            "ConversationPanel"
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.build_ui()

        self.start_new_conversation()

    # ==========================================================
    # BUILD UI
    # ==========================================================

    def build_ui(
        self
    ):

        self.setStyleSheet(
            """

            QWidget#ConversationPanel {

                background:transparent;

                border:none;

            }

            QFrame#ConversationCard {

                background:rgba(255,255,255,128);

                border:1px solid rgba(255,255,255,205);

                border-radius:24px;

            }

            QLabel#ConversationTitle {

                color:#21134F;

                font-family:"Poppins";

                font-size:18px;

                font-weight:800;

                letter-spacing:0px;

                background:transparent;

                padding-left:4px;

            }

            QLabel#WelcomeLabel {

                color:#21134F;

                font-family:"Poppins";

                font-size:21px;

                font-weight:600;

                background:transparent;

                padding-top:2px;

                padding-bottom:2px;

            }

            QScrollArea#ConversationScroll {

                background:transparent;

                border:none;

            }

            QWidget#MessageContainer,
            QWidget#MessageRow,
            QWidget#WelcomeWidget {

                background:transparent;

            }

            QFrame#ComposerFrame {

                background:rgba(255,255,255,105);

                border:1px solid rgba(255,255,255,190);

                border-radius:18px;

            }

            QPlainTextEdit#MessageInput {

                background:transparent;

                border:none;

                color:#17142F;

                font-family:"Poppins";

                font-size:13px;

                padding:7px 8px 2px 8px;

            }

            QPlainTextEdit#MessageInput:focus {

                border:none;

            }

            QPushButton#SendButton {

                background:#7C3AED;

                color:white;

                border:none;

                border-radius:17px;

                font-family:"Segoe UI";

                font-size:14px;

                font-weight:700;

                min-width:34px;

                min-height:34px;

                max-width:34px;

                max-height:34px;

            }

            QPushButton#SendButton:hover {

                background:#6D28D9;

            }

            QPushButton#SendButton:pressed {

                background:#5B21B6;

            }

            QPushButton#SendButton:disabled {

                background:#D1D5DB;

                color:white;

            }

            QLabel#WordCounter {

                color:rgba(33,19,79,175);

                font-family:"Poppins";

                font-size:9px;

                background:transparent;

            }

            QLabel#WordCounter[limitReached="true"] {

                color:#DC2626;

                font-weight:700;

            }

            QScrollBar:vertical {

                width:7px;

                background:transparent;

                margin:4px 1px 4px 1px;

            }

            QScrollBar::handle:vertical {

                background:rgba(124,58,237,105);

                border-radius:3px;

                min-height:30px;

            }

            QScrollBar::handle:vertical:hover {

                background:rgba(124,58,237,155);

            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {

                height:0px;

            }

            """
        )

        # ======================================================
        # OUTER
        # ======================================================

        outer_layout = QVBoxLayout(
            self
        )

        outer_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        outer_layout.setSpacing(
            0
        )

        # ======================================================
        # CARD
        # ======================================================

        self.chat_card = QFrame()

        self.chat_card.setObjectName(
            "ConversationCard"
        )

        self.chat_card.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        outer_layout.addWidget(
            self.chat_card
        )

        # ======================================================
        # CARD ROOT
        # ======================================================

        root = QVBoxLayout(
            self.chat_card
        )

        root.setContentsMargins(
            12,
            12,
            12,
            12
        )

        root.setSpacing(
            8
        )

        # ======================================================
        # CLOSE BUTTON
        # ======================================================

        header = QHBoxLayout()

        header.setContentsMargins(
            4,
            2,
            2,
            2
        )

        # --------------------------------------------------
        # Conversation heading
        # --------------------------------------------------

        self.conversation_title = QLabel(
            "CONVERSATION"
        )

        self.conversation_title.setObjectName(
            "ConversationTitle"
        )

        self.conversation_title.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        header.addWidget(
            self.conversation_title
        )

        header.addStretch()

        self.close_button = PremiumCloseButton()

        self.close_button.clicked.connect(
            self._handle_close_clicked
        )

        header.addWidget(
            self.close_button,
            0,
            Qt.AlignRight |
            Qt.AlignTop
        )

        root.addLayout(
            header
        )

        # ======================================================
        # SCROLL AREA
        # ======================================================

        self.scroll_area = QScrollArea()

        self.scroll_area.setObjectName(
            "ConversationScroll"
        )

        self.scroll_area.setWidgetResizable(
            True
        )

        self.scroll_area.setFrameShape(
            QFrame.NoFrame
        )

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        # ======================================================
        # MESSAGE CONTAINER
        # ======================================================

        self.message_container = QWidget()

        self.message_container.setObjectName(
            "MessageContainer"
        )

        self.message_layout = QVBoxLayout(
            self.message_container
        )

        self.message_layout.setContentsMargins(
            4,
            4,
            4,
            8
        )

        # ------------------------------------------------------
        # Reduced gap between messages
        # ------------------------------------------------------

        self.message_layout.setSpacing(
            3
        )

        self.message_layout.setAlignment(
            Qt.AlignTop
        )

        self.message_layout.addStretch()

        self.scroll_area.setWidget(
            self.message_container
        )

        root.addWidget(
            self.scroll_area,
            stretch=1
        )

        # ======================================================
        # COMPOSER
        # ======================================================

        composer_frame = QFrame()

        composer_frame.setObjectName(
            "ComposerFrame"
        )

        composer_layout = QVBoxLayout(
            composer_frame
        )

        composer_layout.setContentsMargins(
            8,
            7,
            7,
            7
        )

        composer_layout.setSpacing(
            2
        )

        # ======================================================
        # INPUT
        # ======================================================

        self.message_input = MessageComposer()

        self.message_input.setPlaceholderText(
            "Ask DHEEPTHI..."
        )

        # --------------------------------------------------
        # Readable placeholder on the dark glass composer.
        # --------------------------------------------------

        input_palette = self.message_input.palette()

        input_palette.setColor(
            QPalette.PlaceholderText,
            QColor(255, 255, 255, 155)
        )

        self.message_input.setPalette(
            input_palette
        )

        self.message_input.MAX_WORDS = self.MAX_WORDS

        self.message_input.limit_exceeded.connect(
            self._show_word_limit_popup
        )

        self.message_input.textChanged.connect(
            self._on_text_changed
        )

        self.message_input.send_requested.connect(
            self.submit_message
        )

        composer_layout.addWidget(
            self.message_input
        )

        # ======================================================
        # BOTTOM ROW
        # ======================================================

        bottom_row = QHBoxLayout()

        bottom_row.setContentsMargins(
            0,
            0,
            0,
            0
        )

        bottom_row.setSpacing(
            4
        )

        # ======================================================
        # WORD COUNTER
        # ======================================================

        self.word_counter = QLabel(
            "0 / 1000 words"
        )

        self.word_counter.setObjectName(
            "WordCounter"
        )

        bottom_row.addWidget(
            self.word_counter
        )

        bottom_row.addStretch()

        # ======================================================
        # SEND BUTTON
        # ======================================================

        self.send_button = QPushButton(
            "➤"
        )

        self.send_button.setObjectName(
            "SendButton"
        )

        self.send_button.setToolTip(
            "Send message"
        )

        self.send_button.setCursor(
            Qt.PointingHandCursor
        )

        self.send_button.setFocusPolicy(
            Qt.NoFocus
        )

        self.send_button.clicked.connect(
            self.submit_message
        )

        self.send_button.setEnabled(
            False
        )

        bottom_row.addWidget(
            self.send_button
        )

        composer_layout.addLayout(
            bottom_row
        )

        root.addWidget(
            composer_frame
        )

# ==============================================================
# CLOSE HANDLER
# ==============================================================

    def _handle_close_clicked(
        self
    ):
        """
        Close only the conversation panel.

        Conversation history is intentionally preserved in RAM so
        reopening the panel continues the current conversation.
        MainWindow owns the actual show/hide behavior through the
        close_requested signal.
        """

        try:

            # Stop any active lightweight loader.
            self._stop_loading()

            # Ask MainWindow to hide/fade the panel.
            self.close_requested.emit()

        except RuntimeError:

            pass


# ==============================================================
# SHOW EVENT
# ==============================================================

    def showEvent(
        self,
        event
    ):

        super().showEvent(
            event
        )

        try:

            # --------------------------------------------------
            # Empty conversation only:
            # show a fresh greeting.
            #
            # Existing messages are preserved when the panel
            # is hidden and shown again.
            # --------------------------------------------------

            if not self._conversation_history:

                self._show_fresh_greeting()

            # --------------------------------------------------
            # Focus composer
            # --------------------------------------------------

            QTimer.singleShot(
                0,
                self._focus_input
            )

            # --------------------------------------------------
            # Always restore the latest conversation position.
            # --------------------------------------------------

            QTimer.singleShot(
                30,
                self._scroll_to_bottom
            )

        except RuntimeError:

            pass


    # ==============================================================
    # FRESH GREETING
    # ==============================================================

    def _show_fresh_greeting(
        self
    ):

        try:

            # --------------------------------------------------
            # Remove existing greeting if one is already present.
            #
            # This is important because the conversation panel
            # can be closed and reopened while history is empty.
            # --------------------------------------------------

            if self._welcome_widget is not None:

                old_widget = self._welcome_widget

                self._welcome_widget = None

                index = self.message_layout.indexOf(
                    old_widget
                )

                if index >= 0:

                    item = self.message_layout.takeAt(
                        index
                    )

                    widget = item.widget()

                    if widget is not None:

                        widget.deleteLater()

            # --------------------------------------------------
            # Select a different greeting from the previous one.
            # --------------------------------------------------

            choices = [
                item
                for item in self.GREETINGS
                if item != self._last_greeting
            ]

            if not choices:

                choices = list(
                    self.GREETINGS
                )

            greeting = random.choice(
                choices
            )

            self._last_greeting = greeting

            # --------------------------------------------------
            # Greeting label
            # --------------------------------------------------

            welcome = QLabel(
                greeting
            )

            welcome.setObjectName(
                "WelcomeLabel"
            )

            welcome.setAlignment(
                Qt.AlignCenter
            )

            welcome.setWordWrap(
                True
            )

            # --------------------------------------------------
            # IMPORTANT:
            # The greeting can wrap into two lines.  A QLabel with
            # a Preferred vertical policy may receive an undersized
            # height while the surrounding WelcomeWidget is being
            # laid out, which causes the second line to be clipped.
            #
            # Keep enough vertical room for the two-line greeting
            # while preserving the existing responsive width.
            # --------------------------------------------------

            welcome.setMinimumHeight(
                64
            )

            welcome.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed
            )

            # --------------------------------------------------
            # Greeting container
            # --------------------------------------------------

            welcome_box = QWidget()

            welcome_box.setObjectName(
                "WelcomeWidget"
            )

            welcome_box.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Expanding
            )

            welcome_layout = QVBoxLayout(
                welcome_box
            )

            welcome_layout.setContentsMargins(
                18,
                12,
                18,
                12
            )

            welcome_layout.setSpacing(
                4
            )

            # --------------------------------------------------
            # Center greeting vertically
            # --------------------------------------------------

            welcome_layout.addStretch(
                1
            )

            welcome_layout.addWidget(
                welcome,
                0,
                Qt.AlignCenter
            )

            welcome_layout.addStretch(
                1
            )

            # --------------------------------------------------
            # Insert fresh greeting
            # --------------------------------------------------

            self.message_layout.insertWidget(
                0,
                welcome_box
            )

            self._welcome_widget = (
                welcome_box
            )

        except RuntimeError:

            pass


# ==============================================================
# FOCUS INPUT
# ==============================================================

    def _focus_input(
        self
    ):

        try:

            if self.isVisible():

                self.message_input.setFocus()

        except RuntimeError:

            pass


# ==============================================================
# START NEW CONVERSATION
# ==============================================================

    def start_new_conversation(
        self
    ):

        try:

            # --------------------------------------------------
            # Stop any active loading state.
            # --------------------------------------------------

            self._stop_loading()

            # --------------------------------------------------
            # Remove old visual messages.
            # --------------------------------------------------

            self._clear_message_widgets()

            # --------------------------------------------------
            # Clear temporary memory.
            # --------------------------------------------------

            self._conversation_history.clear()

            self._welcome_widget = None

            # --------------------------------------------------
            # Reset composer.
            # --------------------------------------------------

            self.message_input.blockSignals(
                True
            )

            try:

                self.message_input.clear()

            finally:

                self.message_input.blockSignals(
                    False
                )

            self.message_input.setFixedHeight(
                MessageComposer.MIN_HEIGHT
            )

            self._update_counter()

            # --------------------------------------------------
            # New greeting.
            # --------------------------------------------------

            self._show_fresh_greeting()

        except RuntimeError:

            pass


# ==============================================================
# CLEAR CONVERSATION
# ==============================================================

    def clear_conversation(
        self
    ):

        self.start_new_conversation()


# ==============================================================
# REMOVE WELCOME
# ==============================================================

    def _remove_welcome_widget(
        self
    ):

        if self._welcome_widget is None:

            return

        try:

            index = (
                self.message_layout.indexOf(
                    self._welcome_widget
                )
            )

            if index >= 0:

                item = (
                    self.message_layout.takeAt(
                        index
                    )
                )

                widget = item.widget()

                if widget is not None:

                    widget.deleteLater()

        except RuntimeError:

            pass

        self._welcome_widget = None


# ==============================================================
# CLEAR VISUAL MESSAGES
# ==============================================================

    def _clear_message_widgets(
        self
    ):

        try:

            while self.message_layout.count():

                item = (
                    self.message_layout.takeAt(
                        0
                    )
                )

                widget = item.widget()

                if widget is not None:

                    widget.deleteLater()

            self._message_widgets.clear()

            self._typing_bubble = None

            self._typing_wrapper = None

            # --------------------------------------------------
            # Keep final stretch.
            # --------------------------------------------------

            self.message_layout.addStretch()

        except RuntimeError:

            pass


# ==============================================================
# USER MESSAGE
# ==============================================================

    def add_user_message(
        self,
        message: str
    ):

        message = str(
            message
        ).strip()

        if not message:

            return

        # ------------------------------------------------------
        # Store in temporary conversation memory.
        # ------------------------------------------------------

        self._append_history(
            "user",
            message
        )

        # ------------------------------------------------------
        # Immediately display user message.
        # ------------------------------------------------------

        self._add_message(
            message,
            True
        )


# ==============================================================
# ASSISTANT MESSAGE
# ==============================================================

    def add_assistant_message(
        self,
        message: str
    ):

        message = str(
            message
        ).strip()

        if not message:

            return

        # ------------------------------------------------------
        # Remove loading state first.
        # ------------------------------------------------------

        self._stop_loading()

        # ------------------------------------------------------
        # Store assistant response.
        # ------------------------------------------------------

        self._append_history(
            "assistant",
            message
        )

        # ------------------------------------------------------
        # Display response.
        # ------------------------------------------------------

        self._add_message(
            message,
            False
        )


# ==============================================================
# TEMPORARY MEMORY
# ==============================================================

    def _append_history(
        self,
        role: str,
        content: str
    ):

        role = str(
            role
        ).strip().lower()

        content = str(
            content
        ).strip()

        if role not in (
            "user",
            "assistant"
        ):

            return

        if not content:

            return

        self._conversation_history.append(
            {
                "role": role,
                "content": content,
            }
        )

        # ------------------------------------------------------
        # Keep memory lightweight.
        # ------------------------------------------------------

        if (
            len(
                self._conversation_history
            )
            >
            self.MAX_HISTORY_MESSAGES
        ):

            overflow = (
                len(
                    self._conversation_history
                )
                -
                self.MAX_HISTORY_MESSAGES
            )

            del self._conversation_history[
                :overflow
            ]


# ==============================================================
# GET HISTORY
# ==============================================================

    def get_conversation_history(
        self
    ) -> list[dict[str, str]]:

        return [
            {
                "role": item["role"],
                "content": item["content"],
            }
            for item in self._conversation_history
        ]


# ==============================================================
# HISTORY ALIAS
# ==============================================================

    def conversation_history(
        self
    ) -> list[dict[str, str]]:

        return self.get_conversation_history()


# ==============================================================
# HISTORY COUNT
# ==============================================================

    def history_count(
        self
    ) -> int:

        return len(
            self._conversation_history
        )


# ==============================================================
# ADD MESSAGE
# ==============================================================

    def _add_message(
        self,
        message: str,
        is_user: bool
    ):

        message = str(
            message
        ).strip()

        if not message:

            return

        try:

            # --------------------------------------------------
            # Remove greeting.
            # --------------------------------------------------

            self._remove_welcome_widget()

            # --------------------------------------------------
            # Stop previous loading state.
            # --------------------------------------------------

            self._stop_loading()

            # --------------------------------------------------
            # Calculate current safe bubble width.
            # --------------------------------------------------

            available_width = (
                self._bubble_max_width()
            )

            bubble = MessageBubble(
                message,
                is_user=is_user,
                max_width=available_width,
            )

            # ==================================================
            # MESSAGE ROW
            # ==================================================

            row = QHBoxLayout()

            row.setContentsMargins(
                4,
                0,
                4,
                0
            )

            # Small gap keeps messages compact.
            row.setSpacing(
                3
            )

            # --------------------------------------------------
            # USER → RIGHT
            # --------------------------------------------------

            if is_user:

                row.addStretch(
                    1
                )

                row.addWidget(
                    bubble,
                    0,
                    Qt.AlignRight
                )

            # --------------------------------------------------
            # DHEEPTHI → LEFT
            # --------------------------------------------------

            else:

                row.addWidget(
                    bubble,
                    0,
                    Qt.AlignLeft
                )

                row.addStretch(
                    1
                )

            # ==================================================
            # WRAPPER
            # ==================================================

            wrapper = QWidget()

            wrapper.setObjectName(
                "MessageRow"
            )

            wrapper.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed
            )

            wrapper.setLayout(
                row
            )

            # ==================================================
            # INSERT BEFORE FINAL STRETCH
            # ==================================================

            insert_index = (
                self.message_layout.count()
            )

            if insert_index > 0:

                last_item = (
                    self.message_layout.itemAt(
                        insert_index - 1
                    )
                )

                if (
                    last_item is not None
                    and
                    last_item.spacerItem()
                    is not None
                ):

                    insert_index -= 1

            self.message_layout.insertWidget(
                insert_index,
                wrapper
            )

            self._message_widgets.append(
                bubble
            )

            # --------------------------------------------------
            # IMPORTANT:
            # Every new user/AI message automatically moves
            # the conversation to the newest bottom message.
            # --------------------------------------------------

            self._scroll_to_bottom()

        except RuntimeError:

            pass


# ==============================================================
# BUBBLE MAX WIDTH
# ==============================================================

    def _bubble_max_width(
        self
    ) -> int:

        try:

            viewport_width = (
                self.scroll_area
                .viewport()
                .width()
            )

            # --------------------------------------------------
            # Keep bubbles inside the actual viewport.
            # --------------------------------------------------

            safe_width = (
                viewport_width
                -
                38
            )

            if safe_width < 180:

                safe_width = 180

            # --------------------------------------------------
            # WhatsApp-style compact width.
            # --------------------------------------------------

            return max(
                180,
                min(
                    420,
                    int(
                        safe_width
                        *
                        0.82
                    )
                )
            )

        except RuntimeError:

            return 320


# ==============================================================
# RESIZE
# ==============================================================

    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )

        try:

            width = (
                self._bubble_max_width()
            )

            # --------------------------------------------------
            # Recalculate existing bubbles.
            # --------------------------------------------------

            for bubble in (
                self._message_widgets
            ):

                bubble.set_available_width(
                    width
                )

            # --------------------------------------------------
            # Recalculate loading bubble.
            # --------------------------------------------------

            if (
                self._typing_bubble
                is not None
            ):

                # TypingBubble is intentionally lightweight.
                self._typing_bubble.setFixedWidth(
                    min(
                        210,
                        width
                    )
                )

        except RuntimeError:

            pass


# ==============================================================
# LOADING STATE
# ==============================================================

    def show_loading(
        self
    ):

        try:

            # --------------------------------------------------
            # Already loading.
            # --------------------------------------------------

            if (
                self._typing_bubble
                is not None
            ):

                return

            self._remove_welcome_widget()

            # --------------------------------------------------
            # Create lightweight animated indicator.
            # --------------------------------------------------

            bubble = TypingBubble(
                max_width=min(
                    230,
                    self._bubble_max_width()
                )
            )

            row = QHBoxLayout()

            row.setContentsMargins(
                4,
                0,
                4,
                0
            )

            row.setSpacing(
                3
            )

            # --------------------------------------------------
            # DHEEPTHI loader stays on LEFT.
            # --------------------------------------------------

            row.addWidget(
                bubble,
                0,
                Qt.AlignLeft
            )

            row.addStretch(
                1
            )

            wrapper = QWidget()

            wrapper.setObjectName(
                "MessageRow"
            )

            wrapper.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed
            )

            wrapper.setLayout(
                row
            )

            # --------------------------------------------------
            # Insert before final stretch.
            # --------------------------------------------------

            insert_index = (
                self.message_layout.count()
            )

            if insert_index > 0:

                last_item = (
                    self.message_layout.itemAt(
                        insert_index - 1
                    )
                )

                if (
                    last_item is not None
                    and
                    last_item.spacerItem()
                    is not None
                ):

                    insert_index -= 1

            self.message_layout.insertWidget(
                insert_index,
                wrapper
            )

            self._typing_bubble = bubble

            self._typing_wrapper = wrapper

            # --------------------------------------------------
            # Disable input while Gemini processes.
            # --------------------------------------------------

            self.set_input_enabled(
                False
            )

            # --------------------------------------------------
            # Automatically move to bottom.
            # --------------------------------------------------

            self._scroll_to_bottom()

        except RuntimeError:

            pass


# ==============================================================
# SET LOADING
# ==============================================================

    def set_loading(
        self,
        loading: bool
    ):

        if loading:

            self.show_loading()

        else:

            self._stop_loading()


# ==============================================================
# STOP LOADING
# ==============================================================

    def _stop_loading(
        self
    ):

        bubble = (
            self._typing_bubble
        )

        wrapper = (
            self._typing_wrapper
        )

        self._typing_bubble = None

        self._typing_wrapper = None

        # ------------------------------------------------------
        # Stop animation first.
        # ------------------------------------------------------

        if bubble is not None:

            try:

                bubble.stop()

            except RuntimeError:

                pass

        # ------------------------------------------------------
        # Remove wrapper.
        # ------------------------------------------------------

        if wrapper is not None:

            try:

                wrapper.deleteLater()

            except RuntimeError:

                pass

        # ------------------------------------------------------
        # Re-enable composer.
        # ------------------------------------------------------

        try:

            self.set_input_enabled(
                True
            )

        except RuntimeError:

            pass


# ==============================================================
# SEND CALLBACK
# ==============================================================

    def set_send_callback(
        self,
        callback: Optional[
            Callable[[str], None]
        ]
    ):

        self._send_callback = callback


# ==============================================================
# SUBMIT MESSAGE
# ==============================================================

    def submit_message(
        self
    ):

        if self._is_submitting:
            return

        text = self.message_input.toPlainText().strip()

        if not text:
            return

        # Hard limit: never send an over-limit message.
        if self._word_count(text) > self.MAX_WORDS:
            self._show_word_limit_popup()
            self._update_counter()
            return

        self._is_submitting = True

        try:
            self.add_user_message(text)
            self.message_input.clear()
            self.message_input.setFixedHeight(MessageComposer.MIN_HEIGHT)
            self.show_loading()
            self.send_requested.emit(text)

            if self._send_callback is not None:
                self._send_callback(text)

        finally:
            self._is_submitting = False
            self._update_counter()

    def _show_word_limit_popup(self):
        """Show a lightweight native Qt warning without blocking the UI."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(
            self,
            "Message Limit",
            f"Limit is {self.MAX_WORDS} words.",
        )


# ==============================================================
# WORD COUNT
# ==============================================================

    @staticmethod
    def _word_count(
        text: str
    ) -> int:

        return len(
            text.split()
        )


# ==============================================================
# TEXT CHANGED
# ==============================================================

    def _on_text_changed(
        self
    ):
        self._update_counter()

        count = self._word_count(
            self.message_input.toPlainText()
        )

        self.send_button.setEnabled(
            bool(
                self.message_input.toPlainText().strip()
            ) and count <= self.MAX_WORDS
        )


# ==============================================================
# COUNTER
# ==============================================================

    def _update_counter(
        self
    ):

        try:

            count = self._word_count(
                self.message_input
                .toPlainText()
            )

            self.word_counter.setText(
                f"{count} / {self.MAX_WORDS} words"
            )

            reached = (
                count
                >=
                self.MAX_WORDS
            )

            self.word_counter.setProperty(
                "limitReached",
                reached
            )

            self.word_counter.style().unpolish(
                self.word_counter
            )

            self.word_counter.style().polish(
                self.word_counter
            )

            has_text = bool(
                self.message_input
                .toPlainText()
                .strip()
            )

            self.send_button.setEnabled(
                has_text
                and
                count <= self.MAX_WORDS
                and
                self.message_input.isEnabled()
            )

        except RuntimeError:

            pass


# ==============================================================
# DHEEPTHI RESPONSE
# ==============================================================

    def show_ai_response(
        self,
        response: str
    ):

        response = str(
            response
        ).strip()

        if not response:

            self.show_error(
                "I couldn't generate a response."
            )

            return

        # ------------------------------------------------------
        # Stop loading.
        # ------------------------------------------------------

        self._stop_loading()

        # ------------------------------------------------------
        # Add DHEEPTHI response.
        # ------------------------------------------------------

        self.add_assistant_message(
            response
        )

        # ------------------------------------------------------
        # Ensure latest response is visible.
        # ------------------------------------------------------

        self._scroll_to_bottom()


# ==============================================================
# ERROR
# ==============================================================

    def show_error(
        self,
        message: str
    ):

        self._stop_loading()

        safe_message = str(
            message
        ).strip()

        if not safe_message:

            safe_message = (
                "Something went wrong."
            )

        self.add_assistant_message(
            f"Sorry, {safe_message}"
        )

        self._scroll_to_bottom()


# ==============================================================
# INPUT ENABLE
# ==============================================================

    def set_input_enabled(
        self,
        enabled: bool
    ):

        try:

            self.message_input.setEnabled(
                enabled
            )

            has_text = bool(
                self.message_input
                .toPlainText()
                .strip()
            )

            count = self._word_count(
                self.message_input.toPlainText()
            )

            self.send_button.setEnabled(
                bool(
                    enabled
                    and
                    has_text
                    and
                    count <= self.MAX_WORDS
                )
            )

        except RuntimeError:

            pass


# ==============================================================
# SCROLL TO BOTTOM
# ==============================================================

    def _scroll_to_bottom(
        self
    ):

        """
        Schedule scrolling after Qt has completed the layout pass.

        This is important when the user is reading an older message
        and sends a new message. The conversation jumps to the
        newest message only after the new widget has been laid out.
        """

        try:

            QTimer.singleShot(
                0,
                self._perform_scroll_to_bottom
            )

            QTimer.singleShot(
                35,
                self._perform_scroll_to_bottom
            )

        except RuntimeError:

            pass


# ==============================================================
# PERFORM SCROLL
# ==============================================================

    def _perform_scroll_to_bottom(
        self
    ):

        try:

            scrollbar = (
                self.scroll_area
                .verticalScrollBar()
            )

            # --------------------------------------------------
            # Force the latest layout to calculate first.
            # --------------------------------------------------

            self.message_container.adjustSize()

            maximum = (
                scrollbar.maximum()
            )

            scrollbar.setValue(
                maximum
            )

        except RuntimeError:

            pass