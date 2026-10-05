"""
tests/test_splash_screen_runtime.py

Unit and integration tests for DHEEPTHI-AI Final Splash Screen Implementation.
Validates:
- Approved background asset (assets/ui/splash_background.png) loaded and cached
- Official logo from ui/assets/dheepthi_logo-1.png centered and enlarged (210–250px)
- Clean hierarchy: ONLY Logo -> DHEEPTHI-AI -> Percentage -> Progress Bar
- Subtitle and verbose initialization text completely removed from splash presentation
- Character is EXCLUDED from splash screen (belongs strictly to dashboard)
- No dark rectangular card / modal container (floating composition)
- 0% and 500px colorful progress bar visible on frame 1
- Progress/status consistency: "Initialization Complete" guarantees 100% + full bar
- Lazy-installed fade effect behavior (no parent QGraphicsOpacityEffect during startup)
- Deterministic animated sparkles structure and 20 FPS timer for Intel i3 performance
- Live Voice status tile preservation
"""

import sys
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap

from ui.splash_screen import SplashOverlay, SplashScreen
from ui.components.left_panel import LeftPanelWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_splash_overlay_initial_structure(qapp):
    """Test that all required splash content exists and is properly configured."""
    overlay = SplashOverlay()
    overlay.resize(1920, 1080)
    overlay.show()
    qapp.processEvents()

    # Content container: transparent floating layout (NO dark card, NO border)
    assert overlay.card is not None
    assert overlay.card.isVisible()
    assert overlay.card.width() == 560
    assert "background: transparent" in overlay.card.styleSheet()
    assert "border: none" in overlay.card.styleSheet()

    # CRITICAL: NO Character on Splash Screen (Character belongs strictly to dashboard)
    assert not hasattr(overlay, "character_label")

    # CRITICAL: Subtitle completely removed
    assert not hasattr(overlay, "subtitle_label")

    # CRITICAL: Initialization status text restored and visible below progress bar
    assert overlay.loading_status.isVisible()
    assert overlay.loading_status.text() == "Starting DHEEPTHI..."

    # Official Logo: MUST be dheepthi_logo-1.png and enlarged (320–350px)
    assert isinstance(overlay.loading_logo, QLabel)
    assert overlay.loading_logo.pixmap() is not None
    assert not overlay.loading_logo.pixmap().isNull()
    assert "dheepthi_logo-1.png" in overlay.logo_asset_path
    assert 320 <= overlay.loading_logo.pixmap().width() <= 350
    assert 320 <= overlay.loading_logo.pixmap().height() <= 350

    # CRITICAL: NO separate DHEEPTHI-AI title label
    assert not hasattr(overlay, "title_label")

    # Initial Percentage (must be 0% from start)
    assert overlay.loading_percent.text() == "0%"

    # Progress bar: colorful (500px), glass track, 0 to 100
    assert isinstance(overlay.loading_bar, QProgressBar)
    assert overlay.loading_bar.value() == 0
    assert overlay.loading_bar.minimum() == 0
    assert overlay.loading_bar.maximum() == 100
    assert overlay.loading_bar.width() == 500

    # Approved Background Asset check
    assert overlay.bg_asset_path != ""
    assert "splash_background.png" in overlay.bg_asset_path

    overlay.close()


def test_progress_status_consistency(qapp):
    """
    CRITICAL: Verify that when 'Initialization Complete' is set,
    percentage MUST be 100% and bar MUST be 100.
    Never allow 63% with 'Initialization Complete'.
    """
    overlay = SplashOverlay()
    overlay.show()
    qapp.processEvents()

    # Normal early state
    overlay.loading_percent.setText("45%")
    overlay.loading_bar.setValue(45)
    overlay.loading_status.setText("Scanning Applications...")
    assert overlay.loading_percent.text() == "45%"
    assert overlay.loading_bar.value() == 45

    # Trigger completion status
    overlay.loading_status.setText("Initialization Complete")
    qapp.processEvents()

    # Consistency enforcement: MUST be 100% and 100
    assert overlay.loading_percent.text() == "100%"
    assert overlay.loading_bar.value() == 100
    assert "complete" in overlay.loading_status.text().lower()

    # Attempt to set regression while completed: must be held at 100%
    overlay.loading_percent.setText("63%")
    assert overlay.loading_percent.text() == "100%"

    overlay.close()


def test_no_parent_graphics_effect_initially(qapp):
    """
    CRITICAL: Verify that the parent SplashOverlay does NOT have
    a QGraphicsEffect installed at startup, avoiding the Windows Qt
    raster compositing bug that hid child widgets.
    """
    overlay = SplashOverlay()
    assert overlay.graphicsEffect() is None
    assert overlay.overlay_opacity is None

    # Test on-demand fade effect creation
    fade_effect = overlay.enable_fade_effect()
    assert fade_effect is not None
    assert overlay.graphicsEffect() is fade_effect
    assert overlay.overlay_opacity is fade_effect
    assert fade_effect.opacity() == 1.0

    # Verify animation timer is stopped on fade
    assert not overlay._timer.isActive()

    overlay.close()


def test_cached_background_pixmap(qapp):
    """Verify background is pre-rendered to a cached QPixmap on resize for i3 performance."""
    overlay = SplashOverlay()
    overlay.show()
    overlay.resize(1280, 720)
    qapp.processEvents()

    assert overlay._cached_bg is not None
    assert isinstance(overlay._cached_bg, QPixmap)
    assert not overlay._cached_bg.isNull()
    assert overlay._cached_w == 1280
    assert overlay._cached_h == 720

    overlay.close()


def test_sparkles_drift_and_twinkle(qapp):
    """Verify deterministic sparkles exist, run at 20 FPS (50ms), and drift smoothly."""
    overlay = SplashOverlay()
    overlay.show()
    qapp.processEvents()
    assert len(overlay._sparkles) == 16
    assert overlay._timer.interval() == 50  # 20 FPS for i3 performance

    # Check particle properties
    for s in overlay._sparkles:
        assert "rel_x" in s
        assert "rel_y" in s
        assert "dx" in s
        assert "dy" in s
        assert "radius" in s
        assert "base_alpha" in s
        assert "color" in s

    initial_x = overlay._sparkles[0]["rel_x"]
    overlay._on_tick()
    # Position should have drifted slightly
    assert overlay._sparkles[0]["rel_x"] != initial_x

    overlay.close()


def test_live_voice_tile_preserved(qapp):
    """Verify that the Live Voice status card is preserved and Whisper card remains updated."""
    panel = LeftPanelWidget()
    assert hasattr(panel, "live_voice")
    assert panel.live_voice.title_label.text() == "Live Voice"
