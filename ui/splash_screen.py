"""
ui/splash_screen.py

DHEEPTHI-AI V1 — Final Splash Screen Implementation
====================================================
Features:
- Official approved background asset: assets/ui/splash_background.png (artwork untouched)
- Official DHEEPTHI logo from ui/assets/dheepthi_logo-1.png (210–250px, prefer ~230px)
- Elegant ambient breathing glow behind logo (violet + purple + cyan)
- Prominent DHEEPTHI-AI title (34px bold Segoe UI, white, subtle dark contrast shadow)
- Clean, minimal hierarchy: ONLY Logo -> DHEEPTHI-AI -> Percentage -> Progress Bar
- Completely removed: subtitle ("Your Personal AI Desktop Assistant") and status text
- Bright electric cyan startup percentage (28px bold, #00F0FF)
- Vibrant glassmorphic progress bar (500px x 10px) with PURPLE -> PINK -> CYAN gradient
- Guaranteed progress/status consistency (100% + full bar on "Initialization Complete")
- Cached scaled QPixmap background on resize for <0.1ms paint time on Intel i3
- 20 FPS (50ms) lightweight animation timer for subtle sparkles & gentle breathing
- Lazy-applied fade effect for smooth cross-dissolve into dashboard without flash
"""

import math
import random
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QRectF,
    QPointF,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QBrush,
    QRadialGradient,
    QLinearGradient,
    QPixmap,
)
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
)


class SplashStatusLabel(QLabel):
    """
    Status label that displays real startup initialization messages
    (e.g., 'Starting DHEEPTHI...', 'Scanning Applications...', 'Initialization Complete')
    in 19px Segoe UI with a subtle DHEEPTHI color accent (white -> soft lavender -> cyan),
    strong dark contrast shadow, and subtle ambient glow.
    Guarantees synchronization with progress: when 'Initialization Complete' is set,
    automatically coordinates with SplashOverlay so 100% and a full progress bar are displayed.
    """

    def __init__(self, overlay=None, text="Starting DHEEPTHI...", parent=None):
        super().__init__(text, parent)
        self._overlay = overlay
        self.setObjectName("splashStatus")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedWidth(550)
        self.setFixedHeight(36)
        self.setFont(QFont("Segoe UI", 19, QFont.DemiBold))
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def setText(self, text: str):
        super().setText(text)
        if self._overlay is not None and "complete" in text.lower():
            self._overlay.enforce_completion_state()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        text = self.text()
        if not text:
            painter.end()
            return

        font = QFont("Segoe UI", 19, QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        painter.setFont(font)

        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        w = float(self.width())
        h = float(self.height())
        tx = (w - tw) / 2.0
        ty = (h + fm.ascent() - fm.descent()) / 2.0

        # 1. Strong dark contrast shadow backing (for legibility against bright backgrounds)
        painter.setPen(QColor(8, 4, 20, 235))
        painter.drawText(int(tx), int(ty + 2), text)
        painter.drawText(int(tx), int(ty + 1), text)
        painter.drawText(int(tx - 1), int(ty + 1), text)
        painter.drawText(int(tx + 1), int(ty + 1), text)

        # 2. Subtle cyan / violet glow accent around glyphs
        painter.setPen(QColor(0, 240, 255, 90))
        painter.drawText(int(tx), int(ty - 1), text)
        painter.drawText(int(tx - 1), int(ty), text)
        painter.drawText(int(tx + 1), int(ty), text)

        # 3. DHEEPTHI Color Accent gradient: white -> soft lavender -> cyan accent
        grad = QLinearGradient(tx, 0, tx + tw, 0)
        grad.setColorAt(0.00, QColor("#FFFFFF"))    # Brilliant white base
        grad.setColorAt(0.40, QColor("#F5F3FF"))    # Clear white / lavender
        grad.setColorAt(0.70, QColor("#DDD6FE"))    # Soft lavender
        grad.setColorAt(1.00, QColor("#67E8F9"))    # Cyan accent

        painter.setPen(QPen(QBrush(grad), 1))
        painter.drawText(int(tx), int(ty), text)
        painter.end()


class SplashPercentLabel(QLabel):
    """
    Percentage label that displays real startup percentage.
    Guarantees no regression below 100% once initialization is complete.
    """

    def __init__(self, overlay=None, text="0%", parent=None):
        super().__init__(text, parent)
        self._overlay = overlay

    def setText(self, text: str):
        if self._overlay is not None and self._overlay.is_completed():
            super().setText("100%")
            return
        super().setText(text)


class SplashProgressBar(QProgressBar):
    """
    High-contrast, vibrant glassmorphic progress bar.
    Paints a visible translucent dark-glass track with crisp lavender border,
    and a vivid purple -> violet -> magenta/pink -> electric cyan gradient chunk.
    Works reliably across all platforms without Qt stylesheet clipping artifacts.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setFixedWidth(500)
        self.setFixedHeight(10)
        self.setTextVisible(False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0  # 5px rounded pill

        # 1. Subtle dark glass backing for contrast against bright backgrounds
        bg_rect = QRectF(0, 0, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(15, 10, 32, 185)))
        painter.drawRoundedRect(bg_rect, radius, radius)

        # 2. Translucent white/lavender glass inner track
        painter.setBrush(QBrush(QColor(255, 255, 255, 42)))
        painter.drawRoundedRect(bg_rect, radius, radius)

        # 3. Crisp lavender glass border
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(216, 180, 254, 180), 1.2))
        painter.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), radius, radius)

        # 4. Colored Progress Chunk (Vivid PURPLE -> MAGENTA/PINK -> CYAN)
        val = max(0, min(100, self.value()))
        if val > 0:
            chunk_w = max(h, (w - 2.0) * (val / 100.0))
            chunk_rect = QRectF(1.0, 1.0, chunk_w, h - 2.0)
            chunk_radius = (h - 2.0) / 2.0

            # Gradient mapped across the chunk itself so the full spectrum is visible at every stage
            grad = QLinearGradient(1.0, 0.0, chunk_w, 0.0)
            grad.setColorAt(0.0, QColor("#8B5CF6"))   # Vibrant purple
            grad.setColorAt(0.35, QColor("#C026D3"))  # Violet / Magenta
            grad.setColorAt(0.70, QColor("#EC4899"))  # Radiant pink
            grad.setColorAt(1.0, QColor("#00F0FF"))   # Electric Neon Cyan

            # Draw the vibrant chunk
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(0, 240, 255, 140), 0.8))
            painter.drawRoundedRect(chunk_rect, chunk_radius, chunk_radius)

        painter.end()


class SplashOverlay(QWidget):
    """
    Futuristic Startup Splash Overlay.

    Renders the approved background artwork (assets/ui/splash_background.png)
    with clean floating UI elements (large official logo, high-contrast title,
    bright cyan percentage, vibrant progress bar) connected to the real
    InitializationWorker.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SplashOverlay")
        self.setAttribute(Qt.WA_StyledBackground, False)

        # -----------------------------------------------------
        # Pre-generated deterministic sparkles
        # -----------------------------------------------------
        rnd = random.Random(42)
        self._sparkles = []
        sparkle_colors = [
            QColor(255, 255, 255),       # Soft white
            QColor(224, 231, 255),       # Soft ice blue
            QColor(196, 181, 253),       # Soft lavender
            QColor(125, 211, 252),       # Soft cyan
            QColor(244, 114, 182),       # Soft pink
        ]

        # 16 lightweight particles (subtle secondary twinkle)
        for i in range(16):
            self._sparkles.append({
                "rel_x": rnd.uniform(0.04, 0.96),
                "rel_y": rnd.uniform(0.04, 0.96),
                "dx": rnd.uniform(-0.00018, 0.00018),
                "dy": rnd.uniform(-0.00012, 0.00012),
                "radius": rnd.uniform(1.0, 2.2),
                "base_alpha": rnd.randint(80, 180),
                "phase": rnd.uniform(0.0, 6.28),
                "twinkle_speed": rnd.uniform(0.03, 0.07),
                "color": rnd.choice(sparkle_colors),
                "is_flare": (i % 4 == 0),
            })

        self._phase = 0.0
        self._cached_bg = None
        self._cached_w = 0
        self._cached_h = 0
        self._cached_logo_size = 0

        # -----------------------------------------------------
        # Load Approved Splash Background Asset
        # -----------------------------------------------------
        bg_candidates = [
            Path("assets/ui/splash_background.png"),
            Path(__file__).resolve().parent.parent / "assets" / "ui" / "splash_background.png",
            Path("ui/splash_background.png"),
            Path(__file__).resolve().parent.parent / "ui" / "splash_background.png",
        ]
        self._source_bg = QPixmap()
        self.bg_asset_path = ""
        for bp in bg_candidates:
            if bp.exists():
                pix = QPixmap(str(bp))
                if not pix.isNull():
                    self._source_bg = pix
                    self.bg_asset_path = str(bp)
                    break

        # -----------------------------------------------------
        # Load Official DHEEPTHI Logo Asset (ONLY dheepthi_logo-1.png)
        # -----------------------------------------------------
        logo_candidates = [
            Path("ui/assets/dheepthi_logo-1.png"),
            Path(__file__).resolve().parent.parent / "ui" / "assets" / "dheepthi_logo-1.png",
        ]
        self._source_logo = QPixmap()
        self.logo_asset_path = ""
        for lp in logo_candidates:
            if lp.exists():
                pix = QPixmap(str(lp))
                if not pix.isNull():
                    self._source_logo = pix
                    self.logo_asset_path = str(lp)
                    break

        # -----------------------------------------------------
        # Root Layout: Centers the floating startup composition
        # -----------------------------------------------------
        root_layout = QVBoxLayout(self)
        root_layout.setAlignment(Qt.AlignCenter)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -----------------------------------------------------
        # Transparent Floating Content Container (NO CARD, NO BORDER)
        # -----------------------------------------------------
        self.card = QWidget()
        self.card.setObjectName("SplashContentContainer")
        self.card.setFixedWidth(560)
        self.card.setStyleSheet("""
        QWidget#SplashContentContainer {
            background: transparent;
            border: none;
        }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # -----------------------------------------------------
        # 1. Logo: Large Official DHEEPTHI Logo (320–350px, starting around 330px)
        # -----------------------------------------------------
        self.loading_logo = QLabel()
        self.loading_logo.setObjectName("splashLogo")
        self.loading_logo.setAlignment(Qt.AlignCenter)
        initial_logo_size = 330
        self._cached_logo_size = initial_logo_size
        if not self._source_logo.isNull():
            scaled_logo = self._source_logo.scaled(
                initial_logo_size,
                initial_logo_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.loading_logo.setPixmap(scaled_logo)
        self.loading_logo.setFixedSize(initial_logo_size + 16, initial_logo_size + 16)

        logo_glow = QGraphicsDropShadowEffect(self.loading_logo)
        logo_glow.setBlurRadius(38)
        logo_glow.setOffset(0, 0)
        logo_glow.setColor(QColor(168, 85, 247, 175))
        self.loading_logo.setGraphicsEffect(logo_glow)
        card_layout.addWidget(self.loading_logo, alignment=Qt.AlignCenter)

        # Comfortable gap between Logo and Percentage
        card_layout.addSpacing(22)

        # -----------------------------------------------------
        # 2. Percentage Display: Bright cyan (28px bold), high contrast
        # -----------------------------------------------------
        self.loading_percent = SplashPercentLabel(self, "0%")
        self.loading_percent.setObjectName("splashPercent")
        self.loading_percent.setAlignment(Qt.AlignCenter)
        self.loading_percent.setFont(QFont("Segoe UI", 28, QFont.Bold))
        self.loading_percent.setStyleSheet("""
        QLabel#splashPercent {
            color: #00F0FF;
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.8px;
            background: transparent;
        }
        """)
        pct_shadow = QGraphicsDropShadowEffect(self.loading_percent)
        pct_shadow.setBlurRadius(14)
        pct_shadow.setOffset(0, 1)
        pct_shadow.setColor(QColor(10, 6, 25, 235))
        self.loading_percent.setGraphicsEffect(pct_shadow)
        card_layout.addWidget(self.loading_percent, alignment=Qt.AlignCenter)

        # Comfortable gap between Percentage and Progress Bar
        card_layout.addSpacing(14)

        # -----------------------------------------------------
        # 3. Colorful Progress Bar (500px x 10px, PURPLE -> PINK -> CYAN)
        # -----------------------------------------------------
        self.loading_bar = SplashProgressBar(self)
        self.loading_bar.setObjectName("splashProgressBar")
        card_layout.addWidget(self.loading_bar, alignment=Qt.AlignCenter)

        # Small gap between Progress Bar and Status
        card_layout.addSpacing(14)

        # -----------------------------------------------------
        # 4. Restored Real Initialization Status Text (15px near-white, readable)
        # -----------------------------------------------------
        self.loading_status = SplashStatusLabel(self, "Starting DHEEPTHI...")
        card_layout.addWidget(self.loading_status, alignment=Qt.AlignCenter)

        root_layout.addWidget(self.card, alignment=Qt.AlignCenter)

        # -----------------------------------------------------
        # Fade Effect Target (Lazy-installed on fade out)
        # -----------------------------------------------------
        self.overlay_opacity = None

        # -----------------------------------------------------
        # Lightweight Animation Timer (50ms -> 20 FPS for i3)
        # -----------------------------------------------------
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def is_completed(self) -> bool:
        """Return True if initialization completion status is currently set."""
        if hasattr(self, "loading_status") and self.loading_status is not None:
            return "complete" in self.loading_status.text().lower()
        return False

    def enforce_completion_state(self):
        """
        Enforce that 100% progress and full progress bar always match
        the 'Initialization Complete' status text.
        """
        if hasattr(self, "loading_bar") and self.loading_bar is not None:
            self.loading_bar.setValue(100)
        if hasattr(self, "loading_percent") and self.loading_percent is not None:
            self.loading_percent.setText("100%")

    def enable_fade_effect(self):
        """
        Create and attach the QGraphicsOpacityEffect on demand for smooth
        fade-out into the dashboard without blocking child rendering during startup.
        Also stops the animation timer to keep transitions silky smooth.
        """
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()

        if self.overlay_opacity is None:
            self.overlay_opacity = QGraphicsOpacityEffect(self)
            self.overlay_opacity.setOpacity(1.0)
            self.setGraphicsEffect(self.overlay_opacity)
        return self.overlay_opacity

    def _render_background(self, w: int, h: int):
        """
        Pre-render approved splash background into a cached QPixmap.
        Scales proportionally to fill the available splash area.
        Runs only on resize, ensuring paintEvent executes in <0.1ms on Intel i3.
        """
        if w <= 0 or h <= 0:
            return

        pix = QPixmap(w, h)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # Base background fill matching cyber/futuristic theme
        p.fillRect(0, 0, w, h, QColor("#140E2D"))

        # Render approved splash background asset
        if not self._source_bg.isNull():
            scaled_bg = self._source_bg.scaled(
                w,
                h,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            sx = (scaled_bg.width() - w) // 2
            sy = (scaled_bg.height() - h) // 2
            p.drawPixmap(-max(0, sx), -max(0, sy), scaled_bg)

        p.end()
        self._cached_bg = pix
        self._cached_w = w
        self._cached_h = h

    def _update_logo_scale(self, h: int):
        """Scale official logo proportionally (320–350px) based on screen height."""
        target_size = max(320, min(350, int(h * 0.31)))
        if target_size != self._cached_logo_size and not self._source_logo.isNull():
            scaled = self._source_logo.scaled(
                target_size,
                target_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._cached_logo_size = target_size
            self.loading_logo.setPixmap(scaled)
            self.loading_logo.setFixedSize(target_size + 16, target_size + 16)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        if w > 0 and h > 0 and (w != self._cached_w or h != self._cached_h):
            self._render_background(w, h)
            self._update_logo_scale(h)

    def _on_tick(self):
        """Update sparkle drift and twinkle phases at max 20 FPS."""
        if not self.isVisible():
            if hasattr(self, "_timer") and self._timer.isActive():
                self._timer.stop()
            return

        self._phase += 0.05

        # Move sparkles slowly across screen boundaries
        for s in self._sparkles:
            s["rel_x"] += s["dx"]
            s["rel_y"] += s["dy"]
            if s["rel_x"] < 0.01:
                s["rel_x"] = 0.99
            elif s["rel_x"] > 0.99:
                s["rel_x"] = 0.01
            if s["rel_y"] < 0.01:
                s["rel_y"] = 0.99
            elif s["rel_y"] > 0.99:
                s["rel_y"] = 0.01

        self.update()

    def paintEvent(self, event):
        """Paint cached background + subtle ambient glow + animated sparkles."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        if self._cached_bg is None or w != self._cached_w or h != self._cached_h:
            self._render_background(w, h)

        if self._cached_bg is not None:
            painter.drawPixmap(0, 0, self._cached_bg)

        breath = (math.sin(self._phase * 0.6) + 1.0) / 2.0

        # -----------------------------------------------------
        # Subtle ambient breathing glow behind logo (Violet + Purple + Cyan)
        # -----------------------------------------------------
        logo_pos = self.loading_logo.mapTo(self, self.loading_logo.rect().center())
        lx = float(logo_pos.x()) if logo_pos.x() > 0 else (w / 2.0)
        ly = float(logo_pos.y()) if logo_pos.y() > 0 else (h * 0.36)
        glow_r = 185.0 + 15.0 * breath

        logo_glow_grad = QRadialGradient(lx, ly, glow_r)
        logo_glow_grad.setColorAt(0.0, QColor(168, 85, 247, int(38 + 15 * breath)))
        logo_glow_grad.setColorAt(0.55, QColor(0, 240, 255, int(16 + 10 * breath)))
        logo_glow_grad.setColorAt(1.0, QColor(124, 58, 237, 0))
        painter.setBrush(logo_glow_grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(lx, ly), glow_r, glow_r)

        # -----------------------------------------------------
        # Very subtle local contrast backing (maximum 9% opacity, seamless fade)
        # -----------------------------------------------------
        center_y = h * 0.50
        contrast_glow = QRadialGradient(w * 0.5, center_y, max(w, h) * 0.32)
        contrast_glow.setColorAt(0.0, QColor(10, 6, 24, 25))
        contrast_glow.setColorAt(0.65, QColor(10, 6, 24, 12))
        contrast_glow.setColorAt(1.0, QColor(10, 6, 24, 0))
        painter.setBrush(contrast_glow)
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        # -----------------------------------------------------
        # Smooth Animated Sparkles (Secondary, subtle overlay)
        # -----------------------------------------------------
        painter.setPen(Qt.NoPen)
        for s in self._sparkles:
            sx = s["rel_x"] * w
            sy = s["rel_y"] * h
            twinkle = (math.sin(self._phase * (s["twinkle_speed"] / 0.05) + s["phase"]) + 1.0) / 2.0
            alpha = int(s["base_alpha"] * (0.35 + 0.65 * twinkle))
            alpha = max(20, min(240, alpha))

            col = QColor(s["color"])
            col.setAlpha(alpha)
            painter.setBrush(col)
            r = s["radius"] * (0.85 + 0.30 * twinkle)
            painter.drawEllipse(QPointF(sx, sy), r, r)

            if s["is_flare"] and twinkle > 0.55:
                flare_len = r * 2.0 * twinkle
                flare_col = QColor(s["color"])
                flare_col.setAlpha(int(alpha * 0.50))
                painter.setPen(QPen(flare_col, 1.0))
                painter.drawLine(QPointF(sx - flare_len, sy), QPointF(sx + flare_len, sy))
                painter.drawLine(QPointF(sx, sy - flare_len), QPointF(sx, sy + flare_len))
                painter.setPen(Qt.NoPen)

        painter.end()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()

    def closeEvent(self, event):
        super().closeEvent(event)
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()


class SplashScreen(QWidget):
    """
    Standalone Futuristic Splash Screen Window.
    Can be used independently or as a dedicated top-level dialog.
    """

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(700, 750)
        self.overlay = SplashOverlay(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.overlay)

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def start(self, finished_callback):
        self.show()
        self.raise_()
        self.activateWindow()

        def finish():
            eff = self.overlay.enable_fade_effect()
            fade_out = QPropertyAnimation(
                eff,
                b"opacity"
            )
            fade_out.setDuration(350)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.finished.connect(self.close)
            fade_out.finished.connect(finished_callback)
            fade_out.start()
            self.fade_out = fade_out

        QTimer.singleShot(1500, finish)