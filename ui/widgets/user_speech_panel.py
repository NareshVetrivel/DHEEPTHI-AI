"""
ui/widgets/user_speech_panel.py

DHEEPTHI-AI
Realtime User Speech Panel & Voice-Reactive Waveform
---------------------------------------------------
Replaces the old center circular microphone button with a sleek,
translucent glassmorphism user speech panel.

Features:
✓ Glassmorphic translucent panel with soft purple/pink glow
✓ Displays realtime user transcript from Gemini Live
✓ Voice-reactive 9-bar waveform driven by real captured microphone PCM
✓ Dynamic visual states: IDLE, LISTENING, USER SPEAKING, SPEAKING, MUTED
✓ Graceful text wrapping and elision with zero overflow
✓ Thread-safe audio level ingestion from Gemini Live PCM callback
✓ Zero secondary microphone streams or devices
✓ Fully backwards-compatible API for MainWindow calls
"""

from __future__ import annotations

import math
import unicodedata
from typing import Optional

from PySide6.QtCore import (
    Qt,
    QTimer,
    QRectF,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QLinearGradient,
    QFont,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QPushButton,
)


# ==============================================================
# COLOR PALETTE (DHEEPTHI-AI FUTURISTIC THEME)
# ==============================================================

COLOR_PURPLE_PRIMARY = QColor(124, 58, 237)      # #7C3AED
COLOR_PURPLE_LIGHT = QColor(168, 85, 247)        # #A855F7
COLOR_PURPLE_BORDER = QColor(216, 180, 254, 210) # #D8B4FE
COLOR_PINK_ACCENT = QColor(236, 72, 153)         # #EC4899
COLOR_PINK_LIGHT = QColor(244, 114, 182)         # #F472B6
COLOR_TEXT_INDIGO = "#1E1B4B"                    # Deep indigo
COLOR_TEXT_PURPLE = "#6D28D9"                    # Violet
COLOR_TEXT_MUTED = "#6B7280"                     # Gray / subdued
COLOR_TEXT_ERROR = "#DC2626"                     # Red for muted


# ==============================================================
# TRANSCRIPT DISPLAY LANGUAGE FILTER & NORMALIZATION
# ==============================================================

FALLBACK_OTHER_LANGUAGE = "Other language detected"


def is_supported_speech_transcript(text: str) -> bool:
    """
    Validates whether the user speech transcript text belongs to supported display scripts:
    1. English / Latin (includes Roman/Latin Tanglish)
    2. Tamil (Unicode block U+0B80 to U+0BFF)
    3. Mixed Latin + Tamil script
    4. Common punctuation, symbols, whitespace, numbers, and emojis.

    Returns False if foreign scripts (Devanagari, Telugu, Malayalam, Kannada,
    Bengali, Gujarati, Arabic, Cyrillic, CJK, etc.) are present.
    """
    cleaned = str(text or "").strip()
    if not cleaned:
        return False

    for ch in cleaned:
        cat = unicodedata.category(ch)
        # We only examine Letter ('L*') and Combining Mark ('M*') categories.
        # Punctuation ('P*'), Symbols ('S*'), Numbers ('N*'), Separators ('Z*')
        # are universally accepted regardless of language.
        if cat.startswith(("L", "M")):
            code = ord(ch)
            # Fast-path check: standard ASCII Latin
            if (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
                continue
            # Fast-path check: Tamil block (U+0B80 to U+0BFF)
            if 0x0B80 <= code <= 0x0BFF:
                continue
            # General Latin check via Unicode name
            name = unicodedata.name(ch, "")
            if "LATIN" in name or "TAMIL" in name:
                continue
            return False

    return True


def filter_user_speech_display_transcript(
    text: str, fallback: str = FALLBACK_OTHER_LANGUAGE
) -> str:
    """
    Deterministic display-layer transcript filter for UserSpeechPanel.
    Ensures that only English, Tamil, and Tanglish (Roman script) are
    visually displayed. If an unsupported foreign script is detected, returns
    a safe UI-only fallback indicator ('Other language detected') without
    calling any external translation APIs.
    """
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    if is_supported_speech_transcript(cleaned):
        return cleaned

    return fallback


# ==============================================================
# SPEECH WAVEFORM WIDGET
# ==============================================================

class SpeechWaveformWidget(QWidget):
    """
    Lightweight, voice-reactive waveform visualization.
    Renders 9 balanced vertical harmonic bars.
    Driven exclusively by real PCM amplitude values.
    """

    BAR_COUNT = 9
    WEIGHTS = [0.26, 0.46, 0.72, 0.90, 1.00, 0.90, 0.72, 0.46, 0.26]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedHeight(34)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._target_level: float = 0.0
        self._current_level: float = 0.0
        self._phase: float = 0.0
        self._is_active: bool = True
        self._is_muted: bool = False

        # ~35 FPS rendering timer for smooth spring interpolation
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(28)
        self._render_timer.timeout.connect(self._on_render_tick)
        self._render_timer.start()

    def set_target_level(self, level: float) -> None:
        """Update the target PCM amplitude level (0.0 to 1.0)."""
        self._target_level = max(0.0, min(1.0, float(level)))

    def set_muted(self, muted: bool) -> None:
        """Set whether the microphone is muted."""
        self._is_muted = bool(muted)
        if self._is_muted:
            self._target_level = 0.0
            self._current_level = 0.0
            self.update()

    def set_active(self, active: bool) -> None:
        """Set active state (e.g. False during DHEEPTHI speaking)."""
        self._is_active = bool(active)
        if not self._is_active:
            self._target_level = 0.0

    def _on_render_tick(self) -> None:
        if self._is_muted:
            if self._current_level > 0.001:
                self._current_level = 0.0
                self.update()
            return

        # Responsive attack & smooth natural decay
        if self._target_level > self._current_level:
            # Fast snappy attack
            self._current_level += (self._target_level - self._current_level) * 0.46
        else:
            # Smooth musical decay
            self._current_level += (self._target_level - self._current_level) * 0.14

        # Clamp very small values
        if self._current_level < 0.005:
            self._current_level = 0.0

        if self._current_level > 0.01:
            self._phase += 0.24
            if self._phase > 6.283185:
                self._phase -= 6.283185

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        width = self.width()
        height = self.height()
        center_y = height / 2.0

        bar_width = 4.5
        bar_gap = 6.5
        total_waveform_width = (self.BAR_COUNT * bar_width) + ((self.BAR_COUNT - 1) * bar_gap)
        start_x = (width - total_waveform_width) / 2.0

        base_bar_h = 3.5
        max_dynamic_h = height - 4.0  # 30.0px

        # Perceptual dynamic curve: makes normal conversational volume
        # clearly visible without sacrificing headroom for loud speech
        eff_level = math.pow(self._current_level, 0.76) if self._current_level > 0.005 else 0.0

        for i in range(self.BAR_COUNT):
            weight = self.WEIGHTS[i]

            if self._is_muted:
                bar_h = 2.5
            else:
                # Organic harmonic micro-variation
                harmonic = 1.0 + 0.16 * math.sin(self._phase + (i * 0.72))
                bar_h = base_bar_h + (max_dynamic_h - base_bar_h) * eff_level * weight * harmonic
                bar_h = max(base_bar_h, min(max_dynamic_h, bar_h))

            bar_x = start_x + (i * (bar_width + bar_gap))
            bar_y = center_y - (bar_h / 2.0)

            # Vibrant DHEEPTHI multi-tone vertical gradient per bar
            grad = QLinearGradient(0, bar_y, 0, bar_y + bar_h)
            if self._is_muted:
                grad.setColorAt(0.0, QColor(248, 113, 113, 180))
                grad.setColorAt(1.0, QColor(239, 68, 68, 220))
            elif self._current_level > 0.04:
                # Color progression: soft lavender/violet at low level -> purple -> vibrant pink/magenta at high level
                intensity = min(1.0, self._current_level * 1.35)
                top_r = int(196 + (236 - 196) * intensity)
                top_g = int(181 + (72 - 181) * intensity)
                top_b = int(253 + (153 - 253) * intensity)
                grad.setColorAt(0.0, QColor(top_r, top_g, top_b, 235))
                grad.setColorAt(0.55, COLOR_PURPLE_PRIMARY)  # #7C3AED
                grad.setColorAt(1.0, COLOR_PURPLE_LIGHT)    # #A855F7
            else:
                # Calm resting state (soft lavender / violet)
                grad.setColorAt(0.0, QColor(196, 181, 253, 180))
                grad.setColorAt(1.0, QColor(168, 85, 247, 190))

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)

            rect = QRectF(bar_x, bar_y, bar_width, bar_h)
            radius = bar_width / 2.0
            painter.drawRoundedRect(rect, radius, radius)

        painter.end()


# ==============================================================
# USER SPEECH PANEL WIDGET
# ==============================================================

class UserSpeechPanel(QFrame):
    """
    Center User Speech Panel for DHEEPTHI-AI V1.
    
    Replaces the center circular microphone button with a wide,
    translucent glassmorphic speech rectangle.
    Displays user transcripts in realtime, animated voice-reactive
    waveform, and clear UI states.
    """

    STATE_IDLE = "idle"
    STATE_LISTENING = "listening"
    STATE_USER_SPEAKING = "user_speaking"
    STATE_SPEAKING = "speaking"
    STATE_MUTED = "muted"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName("UserSpeechPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.NoFrame)

        # Proportions: Compact centered glass speech capsule
        # Approx 55-65% of prior width, visually balanced with the 485px avatar
        self.setMinimumWidth(350)
        self.setMaximumWidth(420)
        self.setMinimumHeight(82)
        self.setMaximumHeight(90)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._state: str = self.STATE_IDLE
        self._current_transcript: str = ""
        self._last_user_utterance: str = ""
        self._current_audio_level: float = 0.0

        # Timer to clear active user transcript after turn completion
        self._transcript_fade_timer = QTimer(self)
        self._transcript_fade_timer.setSingleShot(True)
        self._transcript_fade_timer.timeout.connect(self._on_transcript_fade_timeout)

        # Backward compatibility dummy button (never shown, intercepts no clicks)
        self._dummy_button = QPushButton(self)
        self._dummy_button.hide()
        self._dummy_button.setEnabled(True)

        self._build_ui()
        self._apply_panel_style()

    def _build_ui(self) -> None:
        """Construct the glassmorphism layout."""
        # Glow Effect - subtle, elegant, non-intrusive
        self._glow_effect = QGraphicsDropShadowEffect(self)
        self._glow_effect.setBlurRadius(16)
        self._glow_effect.setOffset(0, 2)
        self._glow_effect.setColor(QColor(168, 85, 247, 50))
        self.setGraphicsEffect(self._glow_effect)

        # Main Layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(16, 8, 16, 6)
        self._main_layout.setSpacing(3)
        self._main_layout.setAlignment(Qt.AlignCenter)

        # Transcript / State Label
        self.transcript_label = QLabel(self)
        self.transcript_label.setAlignment(Qt.AlignCenter)
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setMaximumHeight(36)
        self.transcript_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        font = QFont("Segoe UI", 11)
        font.setWeight(QFont.Weight.DemiBold)
        self.transcript_label.setFont(font)
        self.transcript_label.setText("Speak to DHEEPTHI...")
        self.transcript_label.setStyleSheet(
            f"color: {COLOR_TEXT_MUTED}; background: transparent; font-size: 12px; font-weight: 500;"
        )

        # Waveform Widget
        self.waveform_widget = SpeechWaveformWidget(self)

        self._main_layout.addWidget(self.transcript_label)
        self._main_layout.addWidget(self.waveform_widget, alignment=Qt.AlignCenter)

    def _apply_panel_style(self) -> None:
        """Apply dynamic translucent glass stylesheet matching dashboard status cards."""
        if self._state == self.STATE_MUTED:
            border_color = "rgba(248, 113, 113, 0.78)"
            bg_gradient = """
                qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 0.64),
                    stop:0.6 rgba(254, 242, 242, 0.58),
                    stop:1 rgba(255, 245, 245, 0.60)
                )
            """
            glow_color = QColor(239, 68, 68, 40)
            glow_radius = 12
        elif self._state == self.STATE_USER_SPEAKING:
            border_color = "rgba(236, 72, 153, 0.82)"
            bg_gradient = """
                qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 0.70),
                    stop:0.6 rgba(253, 242, 250, 0.64),
                    stop:1 rgba(255, 244, 252, 0.66)
                )
            """
            glow_color = QColor(236, 72, 153, int(60 + min(1.0, self._current_audio_level) * 55))
            glow_radius = int(16 + min(1.0, self._current_audio_level) * 8)
        elif self._state == self.STATE_SPEAKING:
            border_color = "rgba(147, 51, 234, 0.72)"
            bg_gradient = """
                qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 0.65),
                    stop:0.6 rgba(247, 242, 255, 0.58),
                    stop:1 rgba(250, 245, 255, 0.62)
                )
            """
            glow_color = QColor(147, 51, 234, 45)
            glow_radius = 15
        elif self._state == self.STATE_LISTENING:
            border_color = "rgba(168, 85, 247, 0.75)"
            bg_gradient = """
                qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 0.66),
                    stop:0.6 rgba(246, 240, 255, 0.60),
                    stop:1 rgba(250, 244, 255, 0.63)
                )
            """
            glow_color = QColor(168, 85, 247, 58)
            glow_radius = 16
        else:
            # Idle
            border_color = "rgba(216, 180, 254, 0.70)"
            bg_gradient = """
                qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 0.62),
                    stop:0.6 rgba(248, 244, 255, 0.56),
                    stop:1 rgba(252, 246, 255, 0.58)
                )
            """
            glow_color = QColor(168, 85, 247, 40)
            glow_radius = 14

        self.setStyleSheet(
            f"""
            QFrame#UserSpeechPanel {{
                background: {bg_gradient};
                border: 1px solid {border_color};
                border-radius: 20px;
            }}
            """
        )

        if hasattr(self, "_glow_effect"):
            self._glow_effect.setColor(glow_color)
            self._glow_effect.setBlurRadius(glow_radius)

    # ==========================================================
    # PUBLIC API: STATE MANAGEMENT
    # ==========================================================

    def set_state(self, state: str) -> None:
        """
        Transition between panel states:
        - 'idle': Subtle placeholder
        - 'listening': Mic unmuted, awaiting user utterance
        - 'user_speaking': Real user voice captured
        - 'speaking': DHEEPTHI model is speaking
        - 'muted': Physical microphone is muted
        """
        normalized = str(state or "").strip().lower()
        if normalized not in (
            self.STATE_IDLE,
            self.STATE_LISTENING,
            self.STATE_USER_SPEAKING,
            self.STATE_SPEAKING,
            self.STATE_MUTED,
        ):
            normalized = self.STATE_IDLE

        if self._state == normalized and normalized != self.STATE_USER_SPEAKING:
            return

        self._state = normalized

        if self._state == self.STATE_MUTED:
            self._transcript_fade_timer.stop()
            self.waveform_widget.set_muted(True)
            self.transcript_label.setText("🔒 Microphone Muted")
            self.transcript_label.setStyleSheet(
                f"color: {COLOR_TEXT_ERROR}; background: transparent; font-size: 13px; font-weight: 600;"
            )
        elif self._state == self.STATE_LISTENING:
            self.waveform_widget.set_muted(False)
            self.waveform_widget.set_active(True)
            if self._current_transcript:
                self._render_transcript_text(self._current_transcript)
            else:
                self.transcript_label.setText("Listening...")
                self.transcript_label.setStyleSheet(
                    f"color: {COLOR_TEXT_PURPLE}; background: transparent; font-size: 13px; font-weight: 600;"
                )
        elif self._state == self.STATE_USER_SPEAKING:
            self.waveform_widget.set_muted(False)
            self.waveform_widget.set_active(True)
            if self._current_transcript:
                self._render_transcript_text(self._current_transcript)
            else:
                self.transcript_label.setText("Listening...")
                self.transcript_label.setStyleSheet(
                    f"color: {COLOR_TEXT_PURPLE}; background: transparent; font-size: 13px; font-weight: 600;"
                )
        elif self._state == self.STATE_SPEAKING:
            self.waveform_widget.set_muted(False)
            self.waveform_widget.set_active(False)
            if self._last_user_utterance:
                # Subdued display of what user asked
                self.transcript_label.setText(f"DHEEPTHI Speaking...")
            else:
                self.transcript_label.setText("Speaking...")
            self.transcript_label.setStyleSheet(
                f"color: {COLOR_TEXT_PURPLE}; background: transparent; font-size: 13px; font-weight: 600;"
            )
        elif self._state == self.STATE_IDLE:
            self.waveform_widget.set_muted(False)
            self.waveform_widget.set_active(True)
            self.transcript_label.setText("Speak to DHEEPTHI...")
            self.transcript_label.setStyleSheet(
                f"color: {COLOR_TEXT_MUTED}; background: transparent; font-size: 13px; font-weight: 500;"
            )

        self._apply_panel_style()

    def get_state(self) -> str:
        """Return the current panel state."""
        return self._state

    # ==========================================================
    # PUBLIC API: TRANSCRIPT DISPLAY
    # ==========================================================

    def set_transcript(self, text: str) -> None:
        """
        Update the user transcript displayed in the panel.
        Handles long text gracefully without overflow.
        Enforces language display filter: English, Tamil, Tanglish (Roman),
        or fallback 'Other language detected'.
        """
        cleaned = str(text or "").strip()
        if not cleaned:
            return

        display_text = filter_user_speech_display_transcript(cleaned)

        self._current_transcript = display_text
        self._last_user_utterance = display_text

        if self._state != self.STATE_MUTED:
            self._state = self.STATE_USER_SPEAKING
            self._render_transcript_text(display_text)
            self._apply_panel_style()

    def get_transcript(self) -> str:
        """Return the current filtered transcript text."""
        return self._current_transcript

    def _render_transcript_text(self, text: str) -> None:
        """Render text with safe elision to prevent panel overflow."""
        # Use QFontMetrics to ensure bounds without clipping
        fm = self.transcript_label.fontMetrics()
        max_w = max(260, self.width() - 32)

        # If text fits cleanly across 1 or 2 lines
        rect = fm.boundingRect(0, 0, max_w, 36, Qt.TextWordWrap, text)
        if rect.height() > 36:
            # Elide overflow gracefully
            elided = fm.elidedText(text, Qt.ElideMiddle, max_w * 2 - 16)
            display_text = f'"{elided}"'
        else:
            display_text = f'"{text}"'

        self.transcript_label.setText(display_text)
        if text == FALLBACK_OTHER_LANGUAGE:
            self.transcript_label.setStyleSheet(
                f"color: {COLOR_TEXT_PURPLE}; background: transparent; font-size: 11px; font-weight: 500; font-style: italic;"
            )
        else:
            self.transcript_label.setStyleSheet(
                f"color: {COLOR_TEXT_INDIGO}; background: transparent; font-size: 12px; font-weight: 600;"
            )

    def _on_transcript_fade_timeout(self) -> None:
        """Return to listening placeholder after a completed utterance."""
        if self._state not in (self.STATE_MUTED, self.STATE_SPEAKING):
            self._current_transcript = ""
            self.set_state(self.STATE_LISTENING)

    # ==========================================================
    # PUBLIC API: REALTIME AUDIO REACTIVITY
    # ==========================================================

    def update_audio_level(self, level: float) -> None:
        """
        Receive real PCM audio level (0.0 to 1.0) captured by the
        authoritative microphone stream.
        """
        if self._state == self.STATE_MUTED:
            self._current_audio_level = 0.0
            self.waveform_widget.set_target_level(0.0)
            return

        clamped = max(0.0, min(1.0, float(level or 0.0)))
        self._current_audio_level = clamped
        self.waveform_widget.set_target_level(clamped)

        # If user speaks and we're in listening state, switch to USER SPEAKING
        if clamped > 0.06 and self._state == self.STATE_LISTENING:
            self._state = self.STATE_USER_SPEAKING
            self._apply_panel_style()
        elif clamped <= 0.02 and self._state == self.STATE_USER_SPEAKING and not self._current_transcript:
            self._state = self.STATE_LISTENING
            self._apply_panel_style()

    # ==========================================================
    # BACKWARD COMPATIBILITY SHIM (FOR LEGACY MicWidget CALLS)
    # ==========================================================

    def button(self) -> QPushButton:
        """Backward compatibility: return dummy QPushButton."""
        return self._dummy_button

    def show_listening(self) -> None:
        """Backward compatibility: transition to listening display."""
        if self._state != self.STATE_MUTED:
            self.set_state(self.STATE_LISTENING)

    def set_listening(self, listening: bool) -> None:
        """Backward compatibility: set listening state."""
        if listening:
            if self._state != self.STATE_MUTED:
                self.set_state(self.STATE_LISTENING)
        else:
            if self._state != self.STATE_MUTED:
                self.set_state(self.STATE_IDLE)

    def update_user_message(self, text: str) -> None:
        """Backward compatibility: update user message text."""
        self.set_transcript(text)

    def update_ai_message(self, text: str) -> None:
        """Backward compatibility: handle AI message/state update."""
        msg = str(text or "").strip()
        if msg and self._state != self.STATE_MUTED:
            # When model speaks or executes an action
            self.set_state(self.STATE_SPEAKING)

    def show_conversation(self, user_text: str = "", ai_text: str = "") -> None:
        """Backward compatibility: show conversation utterance."""
        if user_text:
            self.set_transcript(user_text)

    def set_enabled(self, enabled: bool) -> None:
        """Backward compatibility: enabled state."""
        self.setEnabled(bool(enabled))
        self._dummy_button.setEnabled(bool(enabled))

    def reset(self) -> None:
        """Reset panel to initial state."""
        self._current_transcript = ""
        self._last_user_utterance = ""
        self._current_audio_level = 0.0
        self.waveform_widget.set_target_level(0.0)
        self.set_state(self.STATE_IDLE)
