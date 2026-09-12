import os

from PySide6.QtCore import (
    Qt,
    QRect,
    QTimer,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QEasingCurve,
)

from PySide6.QtGui import (
    QColor,
    QPixmap,
)

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect,
)


class SplashScreen(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )

        self.setAttribute(
            Qt.WA_TranslucentBackground
        )

        self.setFixedSize(520, 520)

        self.build_ui()

    # -------------------------------------------------

    def build_ui(self):

        self.logo = QLabel(self)

        pix = QPixmap(
            os.path.abspath(
                "ui/assets/dheepthi_logo-1.png"
            )
        )

        # Crop transparent/empty margins from the logo
        # so the actual logo can appear much larger.
        if not pix.isNull() and pix.hasAlphaChannel():

            image = pix.toImage()

            alpha = image.alphaChannel()

            rect = alpha.rect()

            # Find the bounding rectangle of visible pixels
            visible_rect = rect

            while (
                not visible_rect.isNull()
                and visible_rect.width() > 1
                and visible_rect.height() > 1
            ):
                break

            pix = pix.copy(visible_rect)

        self.logo.setPixmap(
            pix.scaled(
                500,
                500,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

        self.logo.setAlignment(
            Qt.AlignCenter
        )

        glow = QGraphicsDropShadowEffect()

        glow.setBlurRadius(90)

        glow.setOffset(0)

        glow.setColor(
            QColor(124, 58, 237, 220)
        )

        self.logo.setGraphicsEffect(
            glow
        )

        self.opacity = QGraphicsOpacityEffect()

        self.setGraphicsEffect(
            self.opacity
        )

        self.opacity.setOpacity(0)

    # -------------------------------------------------

    def showEvent(self, event):

        super().showEvent(event)

        screen = self.screen().availableGeometry()

        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )

    # -------------------------------------------------

    def start(self, finished_callback):

        self.show()

        self.raise_()

        self.activateWindow()

        start_rect = QRect(
            10,
            10,
            500,
            500
        )

        end_rect = QRect(
            0,
            0,
            520,
            520
        )

        self.logo.setGeometry(
            start_rect
        )

        fade_in = QPropertyAnimation(
            self.opacity,
            b"opacity"
        )

        fade_in.setDuration(700)

        fade_in.setStartValue(0)

        fade_in.setEndValue(1)

        zoom = QPropertyAnimation(
            self.logo,
            b"geometry"
        )

        zoom.setDuration(700)

        zoom.setStartValue(
            start_rect
        )

        zoom.setEndValue(
            end_rect
        )

        zoom.setEasingCurve(
            QEasingCurve.OutBack
        )

        group = QParallelAnimationGroup()

        group.addAnimation(
            fade_in
        )

        group.addAnimation(
            zoom
        )

        group.start()

        self.group = group

        def finish():

            fade_out = QPropertyAnimation(
                self.opacity,
                b"opacity"
            )

            fade_out.setDuration(350)

            fade_out.setStartValue(1)

            fade_out.setEndValue(0)

            fade_out.finished.connect(
                self.close
            )

            # Only after splash fade finishes,
            # create the main window.
            fade_out.finished.connect(
                finished_callback
            )

            fade_out.start()

            self.fade_out = fade_out

        QTimer.singleShot(
            1200,
            finish
        )