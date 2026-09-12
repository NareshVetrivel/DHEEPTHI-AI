import os
import re
import html
import random
from pathlib import Path

from dotenv import load_dotenv


# =====================================================
# ASTRA-AI ENVIRONMENT
# =====================================================
#
# main_window.py is the main UI/controller entry point.
# Load the project .env here so every backend created by
# MainWindow can access environment-based API credentials.
#
# IMPORTANT:
# - Never print the actual API key.
# - Existing functionality is preserved.
# - main.py remains a lightweight application launcher.
# =====================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

ENV_FILE = (
    PROJECT_ROOT
    / ".env"
)

load_dotenv(
    ENV_FILE
)

GROQ_API_KEY = (
    os.getenv(
        "GROQ_API_KEY",
        ""
    )
    .strip()
)

GROQ_STT_MODEL = (
    os.getenv(
        "GROQ_STT_MODEL",
        "whisper-large-v3-turbo"
    )
    .strip()
)

from PySide6.QtCore import (
    Qt,
    QUrl,
    QCoreApplication,
    QThread,
    Signal,
    Slot,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QPoint,
)

from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QDesktopServices,
    QPixmap,
)

from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QToolButton,
)

from config import settings

from ui.styles.theme import Theme

from ui.components.center_panel import CenterPanelWidget
from ui.components.header import HeaderWidget
from ui.components.left_panel import LeftPanelWidget
from ui.components.right_panel import RightPanelWidget
from ui.widgets.conversation_panel import ConversationPanel

from ui.widgets.background_widget import BackgroundWidget
from ui.widgets.mic_widget import MicWidget
from ui.widgets.file_selection_panel import FileSelectionPanel

from voice.speech_recognition import SpeechRecognizer
from voice.text_to_speech import TextToSpeech

# Production DHEEPTHI wake-word detector:
# openWakeWord + TFLite, owned by wake_word.py.
from voice.wake_word import WakeWordDetector

from planner.intent_detector import IntentDetector
from planner.entity_extractor import EntityExtractor
from planner.text_extractor import TextExtractor
from planner.command_normalizer import CommandNormalizer
from planner.command_dispatcher import CommandDispatcher
from ai.gemini_client import GeminiClient
from planner.multi_command_planner import MultiCommandPlanner
from planner.multi_command_executor import MultiCommandExecutor

from automation.keyboard_controller import KeyboardController
from automation.mouse_controller import MouseController
from automation.window_controller import WindowController
from automation.system_controller import SystemController
from automation.app_launcher import AppLauncher
from automation.app_closer import AppCloser
from automation.file_finder import FileFinder
from automation.folder_manager import FolderManager
from automation.file_manager import FileManager
from automation.browser_controller import BrowserController
from automation.file_monitor import FileMonitor

from workers.initialization_worker import InitializationWorker
from vision.vision_engine import VisionEngine


# =====================================================
# FINAL ASTRA-AI STARTUP / GOODBYE GREETINGS
# =====================================================

OPEN_GREETINGS = [
    "Vanakkam! Naan DHEEPTHI. Ungalukku assist panna ready-ah iruken.",
    "Vanakkam! Naan DHEEPTHI. Sollunga, enna help venum?",
    "Hello! Naan DHEEPTHI. Ungaloda task-ku assist panna ready.",
    "Vanakkam! DHEEPTHI online. Sollunga, enna seiyanum?",
    "Hello! Naan DHEEPTHI. Ungaloda command-ku ready-ah iruken.",
]

CLOSE_GREETINGS = [
    "Okay… ippo namma session complete. Next time continue pannalaam.",
    "Okay… indha session inga mudiyudhu. Thirumbi sandhippom.",
    "Seri… ippo naan purappaduren. Adutha murai thodarnthu pesalaam.",
    "Seri… ippo kelamburen. Next time meet pannalaam.",
    "Seri… ippo naan kelamburen. Meendum thevaipadumbodhu sandhippom.",
]


# =====================================================
# Voice Worker
# =====================================================

class WakeWordWorker(QThread):
    """Background worker dedicated to the production DHEEPTHI detector.

    Wake detection is completely separate from command STT:
        WakeWordDetector -> DHEEPTHI detected -> stop detector -> MainWindow
        -> existing Listening/TTS/manual STT command pipeline.
    """

    wake_detected = Signal(str)
    finished = Signal()
    audio_level = Signal(float)

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self._stop = False
        self._detected_emitted = False

        if self.detector is not None:
            self.detector.on_detected = self._on_detected
            self.detector.level_callback = self._on_level

    def _on_detected(self, wake_word):
        if self._stop or self._detected_emitted:
            return

        self._detected_emitted = True
        print(f"⚡ Production wake word detected: {wake_word}")
        self.wake_detected.emit(str(wake_word))

    def _on_level(self, level):
        try:
            self.audio_level.emit(float(level))
        except Exception:
            pass

    def run(self):
        try:
            if self._stop or self.isInterruptionRequested():
                return

            if self.detector is None:
                print("❌ WakeWordDetector is not available.")
                return

            print("\n========== DHEEPTHI / OPENWAKEWORD ==========")
            print("DHEEPTHI standby: Production openWakeWord + TFLite.")
            print("Threshold: 0.000250")
            print("STT wake detection: DISABLED")

            if not self.detector.start():
                print("❌ Production DHEEPTHI detector failed to start.")
                return

            print("🎤 Production DHEEPTHI listener active.")

            # WakeWordDetector.start() opens the sounddevice stream and
            # returns immediately. Keep this QThread alive until the detector
            # is stopped, so MainWindow does not accidentally restart it.
            while (
                not self._stop
                and not self.isInterruptionRequested()
                and self.detector.is_running()
            ):
                self.msleep(40)

        except Exception as error:
            print(f"WakeWordWorker Error : {error}")
        finally:
            try:
                if self.detector is not None and self.detector.is_running():
                    self.detector.stop()
            except Exception:
                pass

            self.finished.emit()

    def stop(self):
        """Stop the production detector without blocking the GUI thread."""
        self._stop = True
        self.requestInterruption()

        try:
            if self.detector is not None:
                self.detector.stop()
        except Exception as error:
            print(f"Wake detector stop error: {error}")


class VoiceWorker(QThread):
    """Background worker for existing manual command STT.

    IMPORTANT:
        This worker no longer performs wake-word recognition.
        Production DHEEPTHI detection belongs exclusively to WakeWordWorker.
        The existing SpeechRecognizer command-capture path is preserved.
    """

    command_ready = Signal(str)
    finished = Signal()
    audio_level = Signal(float)

    def __init__(self, recognizer, tts, wake_word_mode=False):
        super().__init__()
        self.recognizer = recognizer
        self.tts = tts
        self.wake_word_mode = bool(wake_word_mode)
        self._stop = False
        self._command_emitted = False

        try:
            self.recognizer.level_callback = self.audio_level.emit
        except Exception as error:
            print(f"VoiceWorker Audio Callback Error : {error}")

    def run(self):
        try:
            if self._stop or self.isInterruptionRequested():
                return

            # Wake mode is intentionally rejected here. The production
            # detector has its own worker and microphone owner.
            if self.wake_word_mode:
                print(
                    "⚠️ VoiceWorker received wake mode unexpectedly; "
                    "use WakeWordWorker for DHEEPTHI detection."
                )
                return

            # Existing manual microphone command capture.
            self.msleep(180)

            if self._stop or self.isInterruptionRequested():
                return

            command = self.recognizer.listen(
                timeout=5,
                phrase_time_limit=20,
                calibrate=False,
            )

            if self._stop or self.isInterruptionRequested():
                return

            if command:
                command = str(command).strip()

                if command and not self._command_emitted:
                    self._command_emitted = True
                    print(f"Command Ready : {command}")
                    self.command_ready.emit(command)

        except TypeError as error:
            print(f"VoiceWorker API Error : {error}")

        except Exception as error:
            print(f"VoiceWorker Error : {error}")

        finally:
            self.finished.emit()

    def stop(self):
        """Stop the existing command microphone operation."""
        self._stop = True
        self.requestInterruption()

        try:
            self.recognizer.stop_audio_meter()
        except Exception:
            pass


# =====================================================
# Gemini Conversation Worker
# =====================================================

class ChatWorker(QThread):
    """
    Background worker for Gemini conversation.

    IMPORTANT:
        Gemini API call happens outside the Qt GUI thread.

    This keeps ASTRA-AI responsive on lower-spec systems
    such as i5 / 8GB RAM laptops.
    """

    reply_ready = Signal(str)

    error_occurred = Signal(str)

    def __init__(
        self,
        gemini,
        message,
    ):
        super().__init__()

        self.gemini = gemini

        self.message = str(
            message
        ).strip()

    def run(self):
        """
        Generate Gemini response in background.
        """

        try:

            if not self.message:

                self.reply_ready.emit(
                    "Please say something."
                )

                return

            if self.gemini is None:

                self.error_occurred.emit(
                    "Gemini is not available right now."
                )

                return

            # -----------------------------------------
            # Gemini API call
            # -----------------------------------------

            response = self.gemini.generate_response(
                self.message
            )

            response = str(
                response or ""
            ).strip()

            if not response:

                response = (
                    "Sorry, I couldn't generate "
                    "a response right now."
                )

            # -----------------------------------------
            # Send result back to GUI thread
            # -----------------------------------------

            self.reply_ready.emit(
                response
            )

        except Exception as error:

            print(
                f"Conversation Gemini Error : {error}"
            )

            self.error_occurred.emit(
                "Sorry, I couldn't connect to DHEEPTHI right now."
            )


# =====================================================
# DHEEPTHI Code Agent Worker
# =====================================================

class CodeAgentWorker(QThread):
    """
    Run the complete Code Agent dispatcher workflow outside the
    Qt GUI thread.

    The worker performs no UI operations. It sends the final
    CommandDispatcher result back to MainWindow through a Qt signal.
    """

    result_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, dispatcher, command):
        super().__init__()
        self.dispatcher = dispatcher
        self.command = str(command or "").strip()

    def run(self):
        try:
            if self.dispatcher is None:
                self.error_occurred.emit(
                    "CommandDispatcher is not available."
                )
                return

            if not self.command:
                self.error_occurred.emit(
                    "Empty Code Agent command."
                )
                return

            print(
                "\n========== CODE AGENT BACKGROUND WORKER ==========",
                flush=True,
            )
            print(f"Request : {self.command}", flush=True)
            print("GUI thread blocked : NO", flush=True)
            print("=================================================\n", flush=True)

            result = self.dispatcher.dispatch(
                intent="code_agent",
                entity=None,
                typed_text=self.command,
                browser=None,
                website=None,
                search_query=None,
                profile=None,
                user_text=self.command,
                multi_command=False,
            )

            if not isinstance(result, dict):
                result = {
                    "success": False,
                    "code_agent": True,
                    "status": "Status : Code Agent Failed",
                    "message": (
                        "Code Agent did not return a valid result."
                    ),
                    "error": "Invalid CommandDispatcher result.",
                }
            else:
                result = dict(result)
                result["code_agent"] = True

            self.result_ready.emit(result)

        except Exception as error:
            print(
                "\n========== CODE AGENT WORKER ERROR ==========",
                flush=True,
            )
            print(f"Request : {self.command}", flush=True)
            print(f"Error   : {error}", flush=True)
            print("=============================================\n", flush=True)

            self.error_occurred.emit(str(error))


# =====================================================
# Vision Worker
# =====================================================

class VisionWorker(QThread):
    """Run full screen Vision analysis outside the Qt GUI thread."""

    analysis_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, vision_engine):
        super().__init__()
        self.vision_engine = vision_engine

    def run(self):
        try:
            if self.vision_engine is None:
                self.error_occurred.emit(
                    "Vision is not available right now."
                )
                return

            analysis = self.vision_engine.analyze_screen(
                preprocess_ocr=True
            )

            self.analysis_ready.emit(
                analysis or {}
            )

        except Exception as error:
            print(
                f"Vision Worker Error : {error}"
            )
            self.error_occurred.emit(
                "I could not analyze the current screen."
            )

# =====================================================
# Custom Application Title Bar
# =====================================================

class ApplicationTitleBar(QWidget):
    """Custom DHEEPTHI-AI title bar used instead of the native Windows bar.

    The native Windows title bar has a system-controlled height, so it cannot
    be reliably enlarged from Qt stylesheets. This widget keeps the existing
    main window behaviour while giving the application a controllable title
    bar height.
    """

    HEIGHT = 40

    def __init__(self, parent=None):

        super().__init__(parent)

        self._drag_position = None

        self.setObjectName("applicationTitleBar")
        self.setFixedHeight(self.HEIGHT)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""

        QWidget#applicationTitleBar {

            background: rgb(31, 31, 31);
            border: none;

        }

        QLabel#applicationTitle {

            color: white;
            font-size: 18px;
            font-weight: 700;
            padding-left: 3px;

        }

        QToolButton {

            background: transparent;
            border: none;
            color: rgb(235, 235, 235);
            font-size: 18px;
            min-width: 70px;
            max-width: 70px;
            min-height: 40px;
            max-height: 40px;

        }

        QToolButton:hover {

            background: rgb(55, 55, 55);

        }

        QToolButton#closeButton:hover {

            background: rgb(196, 43, 43);

        }

        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(0)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(38, 38)
        self.icon_label.setAlignment(Qt.AlignCenter)

        icon_path = os.path.abspath(
            "ui/assets/dheepthi_logo-2.png"
        )

        if os.path.exists(icon_path):

            pixmap = QPixmap(icon_path)

            if not pixmap.isNull():
                self.icon_label.setPixmap(
                    pixmap.scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

        self.title_label = QLabel("DHEEPTHI-AI")
        self.title_label.setObjectName("applicationTitle")
        self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        layout.addWidget(self.icon_label)
        layout.addSpacing(8)
        layout.addWidget(self.title_label, 1)

        self.minimize_button = QToolButton()
        self.minimize_button.setText("−")
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.clicked.connect(self._minimize)

        self.maximize_button = QToolButton()
        self.maximize_button.setText("□")
        self.maximize_button.setToolTip("Maximize / Restore")
        self.maximize_button.clicked.connect(self._toggle_maximize)

        self.close_button = QToolButton()
        self.close_button.setObjectName("closeButton")
        self.close_button.setText("×")
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(self._close)

        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def _minimize(self):
        window = self.window()
        if window is not None:
            window.showMinimized()

    def _toggle_maximize(self):
        window = self.window()
        if window is None:
            return

        if window.isMaximized():
            window.showNormal()
            self.maximize_button.setText("□")
        else:
            window.showMaximized()
            self.maximize_button.setText("❐")

    def _close(self):
        window = self.window()
        if window is not None:
            window.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:

            window = self.window()

            if window is not None:

                self._drag_position = (
                    event.globalPosition().toPoint() - window.frameGeometry().topLeft()
                )

            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:

            window = self.window()

            if window is not None and not window.isMaximized():

                window.move(
                    event.globalPosition().toPoint() - self._drag_position
                )

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)


# =====================================================
# Main Window
# =====================================================

class MainWindow(QMainWindow):
    """
    ASTRA-AI Main Window
    """

    def __init__(self):

        super().__init__()

        self._closing = False

        # ----------------------------------
        # Graceful Okii, byee! See youu soon 🫶 Shutdown
        # ----------------------------------
        # The native window X must NOT destroy the window immediately.
        # First show the AvatarWidget goodbye state and play the selected
        # goodbye TTS, then perform the normal resource cleanup and close.
        self._shutdown_goodbye_started = False
        self._shutdown_finalizing = False
        self._goodbye_tts_signal_connected = False
        self._goodbye_tts_finished = False

        # Startup greeting owns the microphone until TTS is fully finished.
        self._startup_greeting_active = False
        self._startup_greeting_finished = False
        self._startup_sequence_complete = False
        self._startup_tts_signal_connected = False
        self._startup_tts_started_signal_connected = False
        self._startup_tts_observed_speaking = False
        self._startup_greeting_started_at = None
        self._startup_greeting_token = 0
        self._startup_tts_request_id = None
        self._startup_unlock_watchdog = None
        self._startup_poll_timer = None

        # ----------------------------------
        # Wake-word -> command lifecycle guard
        # ----------------------------------
        # A DHEEPTHI detection is converted into the SAME command
        # lifecycle used by the manual microphone. This guard prevents
        # duplicate transitions while the wake worker is stopping and
        # its finished signal is travelling back to the GUI thread.
        self._wake_command_transition_active = False

        # Safety timeout only. Normal unlock happens from the real
        # TTS completion signal or the speaking-state fallback.
        self._startup_unlock_watchdog_ms = 30000
        self._startup_min_fallback_wait_ms = 7000

        # ----------------------------------
        # Backend
        # ----------------------------------

        self.recognizer = None

        self.tts = None

        self.intent_detector = None

        self.entity_extractor = None

        self.text_extractor = None

        self.command_normalizer = None

        self.dispatcher = None

        # DHEEPTHI Code Agent V1 lifecycle state.
        # CommandDispatcher owns generation/compile/retry/run;
        # MainWindow owns presentation and microphone lifecycle.
        #
        # Code Agent work runs in a background QThread so Groq,
        # compilation, retry logic, and terminal launch never block
        # the Qt GUI thread.
        self._code_agent_processing = False
        self._code_agent_worker = None

        self.multi_command_planner = None

        self.multi_command_executor = None

        self.app_launcher = None

        self.app_closer = None

        self.keyboard_controller = None

        self.mouse_controller = None

        self.window_controller = None

        self.system_controller = None

        self.file_finder = None

        self.folder_manager = None

        self.file_manager = None

        self.browser_controller = None

        self.file_monitor = None

        self.gemini = None

        # ----------------------------------
        # Vision Engine
        # ----------------------------------
        self.vision = None
        self.vision_worker = None
        self.vision_processing = False
        self._vision_speak_response = False

        self._backend_ready = False
        self._backend_initialization_started = False

        # ----------------------------------
        # Groq Speech-to-Text Configuration
        # ----------------------------------
        #
        # The key is loaded from the project .env above.
        # Keep only configuration state here; the actual STT
        # implementation remains owned by the voice layer.
        # ----------------------------------

        self.groq_api_key = (
            GROQ_API_KEY
        )

        self.groq_stt_model = (
            GROQ_STT_MODEL
        )

        self.groq_stt_available = bool(
            self.groq_api_key
        )

        # ----------------------------------
        # Runtime
        # ----------------------------------

        self.last_application = None

        self.typing_mode = False

        self.loading_finished = False

        self.voice_worker = None
        self.worker = None

        # ----------------------------------
        # Gemini Conversation Worker
        # ----------------------------------
        # Only ONE text conversation request
        # is allowed at a time.
        #
        # This prevents multiple Gemini API
        # calls from running simultaneously
        # on lower-spec systems.
        # ----------------------------------

        self.chat_worker = None

        self.chat_processing = False

        # ----------------------------------
        # Voice Worker State
        # ----------------------------------

        self.current_voice_mode = None

        # "wake"   -> DHEEPTHI standby listener
        # "manual" -> microphone button listener

        self.manual_listening_requested = False

        # ----------------------------------
        # DHEEPTHI Wake Word Mode
        # ----------------------------------

        self.wake_word_enabled = True

        self.wake_word_running = False

        # Production DHEEPTHI detector is separate from the existing
        # SpeechRecognizer command STT backend.
        self.wake_word_detector = None
        self.wake_word_model_path = (
            PROJECT_ROOT
            / "models"
            / "wakeword"
            / "dheepthi_float32.tflite"
        )

        # Prevent multiple mic clicks
        self.processing_voice = False

        # ----------------------------------
        # Pending File Selection
        # ----------------------------------
        # When a file operation matches multiple files, the
        # dispatcher returns candidates instead of selecting
        # the first match. MainWindow keeps the original
        # command here and applies the user's numeric choice
        # to that exact operation.
        self._pending_file_selection = None

        self._file_selection_candidates = []

        self._file_selection_operation = None

        self._loading_overlay_deleted = False

        # ----------------------------------
        # Conversation Panel
        # ----------------------------------

        self.conversation_panel = None

        self.conversation_panel_open = False

        # Lightweight position animation.
        # Only the panel position is animated instead of
        # continuously animating the complete QRect geometry.
        self.conversation_animation = None

        # Prevent repeated clicks while the panel is moving.
        self.conversation_animating = False

        # Used to know whether the current animation is opening
        # or closing the conversation panel.
        self.conversation_animation_mode = None

        self.conversation_overlay_effect = None

        # ----------------------------------
        # Pending Confirmation
        # ----------------------------------
        # CommandDispatcher returns a non-blocking confirmation
        # request. MainWindow owns the microphone confirmation flow.
        self._pending_confirmation = None

        # ----------------------------------
        # Pending Microsoft Word clarification
        # ----------------------------------
        # Preserve the original Word action while the user supplies
        # missing information such as rows/columns, path, text, font,
        # or other required parameters.
        self._pending_word_clarification = None

        # ----------------------------------
        # Window
        # ----------------------------------
        # Use a custom title bar so its height is fully controllable.
        # The native Windows title bar height cannot be reliably changed
        # from Qt stylesheets.
        # ----------------------------------

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Window
        )

        self.setWindowTitle("DHEEPTHI-AI")

        icon_path = os.path.abspath(
            "ui/assets/dheepthi_logo-1.png"
        )

        if os.path.exists(icon_path):

            icon = QIcon(icon_path)

            self.setWindowIcon(icon)

            QApplication.instance().setWindowIcon(icon)

        self.resize(1600, 900)

        self.setMinimumSize(1400, 850)

        self.setStyleSheet(
            Theme.get_stylesheet()
        )

        # ----------------------------------
        # Build UI
        # ----------------------------------

        self.setup_ui()

        # ----------------------------------
        # Custom Title Bar
        # ----------------------------------

        self.application_title_bar = ApplicationTitleBar(self)
        self.application_title_bar.setGeometry(
            0,
            0,
            self.width(),
            ApplicationTitleBar.HEIGHT
        )
        self.application_title_bar.raise_()

    def setup_ui(self):
        """
        Build the main user interface.
        """

        # --------------------------------------------------
        # Background
        # --------------------------------------------------

        self.background = BackgroundWidget()

        self.setCentralWidget(
            self.background
        )

        # --------------------------------------------------
        # Transparent Content
        # --------------------------------------------------

        self.content = QWidget()

        self.content.setObjectName(
            "mainContent"
        )

        self.content.setStyleSheet("""

        QWidget#mainContent{

            background:transparent;

        }

        """)

        self.background.setContentWidget(
            self.content
        )

        # --------------------------------------------------
        # Root Layout
        # --------------------------------------------------

        self.root_layout = QVBoxLayout(
            self.content
        )

        self.root_layout.setContentsMargins(
            28,
            ApplicationTitleBar.HEIGHT + 14,
            28,
            0
        )

        self.root_layout.setSpacing(0)

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        self.header_widget = HeaderWidget()

        # --------------------------------------------------
        # Conversation Button
        # --------------------------------------------------
        # Header-la irukkura existing right-side button
        # ippo application close button illa.
        #
        # It opens / closes the Conversation Panel.
        # --------------------------------------------------

        self.header_widget.set_conversation_callback(
            self.toggle_conversation_panel
        )

        self.root_layout.addWidget(
            self.header_widget
        )

        self.root_layout.addSpacing(26)

        # --------------------------------------------------
        # Body Layout
        # --------------------------------------------------

        self.body_layout = QHBoxLayout()

        self.body_layout.setContentsMargins(
            18,
            0,
            18,
            8
        )

        self.body_layout.setSpacing(18)

        # --------------------------------------------------
        # Left Panel
        # --------------------------------------------------

        self.left_panel = LeftPanelWidget()

        self.body_layout.addWidget(
            self.left_panel,
            0,
            Qt.AlignTop
        )

        # --------------------------------------------------
        # Center Panel
        # --------------------------------------------------

        self.center_container = QWidget()

        self.center_layout = QVBoxLayout(
            self.center_container
        )

        self.center_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        self.center_layout.setSpacing(4)

        # --------------------------------------------------
        # File / Folder Selection Glass Panel
        # --------------------------------------------------
        # IMPORTANT:
        # Do NOT add this panel to center_layout.
        #
        # It is positioned manually above the microphone so it
        # does not push the microphone/halo/avatar downward.
        # --------------------------------------------------

        self.file_selection_panel = FileSelectionPanel(
            self.center_container
        )

        self.file_selection_panel.hide()

        self.file_selection_panel.selection_requested.connect(
            self._on_file_selection_clicked
        )

        self.file_selection_panel.cancelled.connect(
            self._on_file_selection_cancelled
        )

        # --------------------------------------------------
        # ASTRA IMAGE AVATAR PANEL
        # --------------------------------------------------

        self.center_panel = CenterPanelWidget(
            self.center_container
        )

        self.center_panel.setObjectName(
            "astraCenterPanel"
        )

        self.center_panel.setMinimumSize(
            1,
            1
        )

        # --------------------------------------------------
        # AVATAR SIZE
        # --------------------------------------------------

        self.center_panel.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Fixed
        )

        self.center_panel.setFixedSize(
            485,
            540
        )

        self.center_layout.addWidget(
            self.center_panel,
            1,
            Qt.AlignHCenter | Qt.AlignVCenter
        )

        # Compatibility reference for backend code.
        self.avatar_widget = self.center_panel.avatar_widget

        # --------------------------------------------------
        # Goodbye shutdown ownership
        # --------------------------------------------------
        # AvatarWidget's goodbye_finished signal only marks the end of
        # the visual 4-second avatar timer. It MUST NOT close the main
        # window because the goodbye TTS sentence may still be speaking.
        # The TextToSpeech speech_finished signal is the single source
        # of truth for the final shutdown.
        #
        # Therefore we intentionally do NOT connect:
        #
        #     avatar_widget.goodbye_finished -> close
        #
        # The avatar remains visible while TTS is running. If TTS takes
        # longer than 4 seconds, the avatar timer may finish, but the
        # application remains alive until the complete TTS sentence ends.
        # --------------------------------------------------

        # --------------------------------------------------
        # Thinking Avatar Synchronization
        # --------------------------------------------------
        # The left-panel THINKING status and the center avatar
        # must always move together.  This remembers whether the
        # current command is an AI task or a desktop automation task.
        self._thinking_avatar_mode = "thinking_ai"

        print(
            "[AVATAR] Image-based CenterPanelWidget added to main window."
        )

        # --------------------------------------------------
        # Microphone
        # --------------------------------------------------

        self.mic_widget = MicWidget()

        self.center_layout.addWidget(
            self.mic_widget,
            alignment=Qt.AlignBottom | Qt.AlignHCenter
        )

        # The microphone must remain visually in front of the
        # avatar layer whenever their paint areas overlap.
        self.mic_widget.raise_()

        self.center_layout.addSpacing(
            12
        )

        self.body_layout.addWidget(

            self.center_container,

            1

        )

        # --------------------------------------------------
        # Right Panel
        # --------------------------------------------------

        self.right_panel = RightPanelWidget()

        self.body_layout.addWidget(

            self.right_panel,

            0,

            Qt.AlignTop

        )

        # --------------------------------------------------
        # Conversation Panel
        # --------------------------------------------------
        # The panel is created once and reused.
        # It does NOT participate in body_layout.
        #
        # This is important because the panel must slide
        # independently from the main UI.
        # --------------------------------------------------

        self.conversation_panel = ConversationPanel(
            self
        )

        # --------------------------------------------------
        # Conversation close button
        # --------------------------------------------------

        self.conversation_panel.close_requested.connect(
            self.close_conversation_panel
        )

        # --------------------------------------------------
        # Conversation text message
        # --------------------------------------------------
        # User sends a message from the conversation panel.
        # --------------------------------------------------

        self.conversation_panel.send_requested.connect(
            self.handle_conversation_message
        )

        self.conversation_panel.hide()

        self.conversation_panel_open = False

        self.root_layout.addLayout(

            self.body_layout,

            1

        )

        # --------------------------------------------------
        # Dummy References
        # --------------------------------------------------

        self.status_label = QLabel()

        self.status_label.setText(
            "Status : Ready"
        )

        self.conversation_label = QLabel()

        self.microphone_button = self.mic_widget.button()

        self.microphone_button.clicked.connect(

            self.start_listening

        )

        # --------------------------------------------------
        # Loading Overlay
        # --------------------------------------------------

        self.loading_overlay = QWidget(self)

        self.loading_overlay.setStyleSheet("""

        QWidget{

            background-color: rgb(247,242,255);

        }

        """)

        self.loading_overlay.setGeometry(self.rect())

        self.loading_overlay.raise_()

        self.loading_overlay.show()

        # --------------------------------------------------
        # Overlay Layout
        # --------------------------------------------------

        overlay_layout = QVBoxLayout(
            self.loading_overlay
        )

        overlay_layout.setAlignment(
            Qt.AlignCenter
        )

        overlay_layout.setSpacing(18)

        # --------------------------------------------------
        # Logo
        # --------------------------------------------------

        self.loading_logo = QLabel()

        icon = QApplication.windowIcon()

        pixmap = icon.pixmap(420, 420)

        self.loading_logo.setPixmap(pixmap)

        self.loading_logo.setAlignment(
            Qt.AlignCenter
        )

        glow = QGraphicsDropShadowEffect()

        glow.setBlurRadius(80)

        glow.setOffset(0)

        glow.setColor(
            QColor(124,58,237,180)
        )

        self.loading_logo.setGraphicsEffect(
            glow
        )

        overlay_layout.addWidget(
            self.loading_logo,
            alignment=Qt.AlignCenter
        )

        # --------------------------------------------------
        # Percentage
        # --------------------------------------------------

        self.loading_percent = QLabel(
            "0%"
        )

        self.loading_percent.setAlignment(
            Qt.AlignCenter
        )

        self.loading_percent.setFont(
            QFont(
                "Segoe UI",
                24,
                QFont.Bold
            )
        )

        self.loading_percent.setStyleSheet("""

        color:#6A40FF;

        background:transparent;

        """)

        overlay_layout.addWidget(
            self.loading_percent
        )

        # --------------------------------------------------
        # Progress Bar
        # --------------------------------------------------

        self.loading_bar = QProgressBar()

        self.loading_bar.setRange(
            0,
            100
        )

        self.loading_bar.setValue(0)

        self.loading_bar.setFixedWidth(420)

        self.loading_bar.setFixedHeight(10)

        self.loading_bar.setTextVisible(False)

        self.loading_bar.setStyleSheet("""

        QProgressBar{

            border:none;

            border-radius:5px;

            background:#E5E7EB;

        }

        QProgressBar::chunk{

            border-radius:5px;

            background:#7C3AED;

        }

        """)

        overlay_layout.addWidget(
            self.loading_bar,
            alignment=Qt.AlignCenter
        )

        # --------------------------------------------------
        # Status
        # --------------------------------------------------

        self.loading_status = QLabel(
            "Starting DHEEPTHI..."
        )

        self.loading_status.setAlignment(
            Qt.AlignCenter
        )

        self.loading_status.setFont(
            QFont(
                "Segoe UI",
                11
            )
        )

        self.loading_status.setStyleSheet("""

        color:#666;

        background:transparent;

        """)

        overlay_layout.addWidget(
            self.loading_status
        )

        # --------------------------------------------------
        # Overlay Opacity
        # (Used only while closing overlay)
        # --------------------------------------------------

        self.overlay_opacity = QGraphicsOpacityEffect()

        self.loading_overlay.setGraphicsEffect(
            self.overlay_opacity
        )

        self.overlay_opacity.setOpacity(1.0)

        # --------------------------------------------------
        # Disable Mic Until Initialization Completes
        # --------------------------------------------------

        self.microphone_button.setEnabled(False)

        # --------------------------------------------------
        # Initial UI State
        # --------------------------------------------------

        try:

            self.left_panel.set_listening(
                "Offline"
            )

            self._set_thinking_state(
                "Initializing"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:

            pass

        # --------------------------------------------------
        # Initial Conversation
        # --------------------------------------------------

        self.conversation_label.setText(

            "Initializing DHEEPTHI-AI..."

        )

        # --------------------------------------------------
        # Force Initial Paint
        # --------------------------------------------------

        self.setUpdatesEnabled(True)

        self.update()

        QApplication.processEvents()

    # --------------------------------------------------
    # Create Backend
    # --------------------------------------------------

    def create_backend(self):
        """Create all backend modules once and return whether startup succeeded."""

        if self._backend_ready:
            return True

        if self._closing:
            return False

        print("\n========== BACKEND ==========")

        # ------------------------------------------
        # Groq STT Environment Check
        # ------------------------------------------
        #
        # Do not expose the secret itself in logs.
        # This confirms that MainWindow successfully loaded
        # GROQ_API_KEY from the project environment.
        # ------------------------------------------

        if self.groq_stt_available:

            print(
                "Groq STT Environment : READY"
            )

            print(
                f"Groq STT Model : {self.groq_stt_model}"
            )

        else:

            print(
                "Groq STT Environment : NOT CONFIGURED"
            )

            print(
                "Set GROQ_API_KEY in the project .env file."
            )

        # ------------------------------------------
        # Speech Recognition
        # ------------------------------------------

        self.recognizer = SpeechRecognizer()

        print("Vosk Speech Recognizer Created.")
        print("Command STT : Existing SpeechRecognizer pipeline")
        print("Faster-Whisper wake detection : DISABLED")

        # ------------------------------------------
        # Production DHEEPTHI Wake Word
        # ------------------------------------------

        try:
            self.wake_word_detector = WakeWordDetector(
                model_path=self.wake_word_model_path,
                threshold=0.000250,
            )

            print(
                "Production WakeWordDetector created."
            )

            print(
                f"Wake Model : {self.wake_word_model_path}"
            )

        except Exception as error:
            self.wake_word_detector = None

            print(
                f"Production WakeWordDetector creation failed: {error}"
            )

        # ------------------------------------------
        # Voice
        # ------------------------------------------

        self.tts = TextToSpeech()

        # ------------------------------------------
        # NLP
        # ------------------------------------------

        self.intent_detector = IntentDetector()

        self.entity_extractor = EntityExtractor()

        self.text_extractor = TextExtractor()

        # ------------------------------------------
        # Command Normalization
        # ------------------------------------------

        self.command_normalizer = CommandNormalizer()

        # ------------------------------------------
        # Automation Modules
        # ------------------------------------------

        self.app_launcher = AppLauncher()

        self.app_closer = AppCloser()

        self.keyboard_controller = KeyboardController()

        self.mouse_controller = MouseController()

        self.window_controller = WindowController()

        self.system_controller = SystemController()

        self.file_finder = FileFinder()

        self.folder_manager = FolderManager()

        self.file_manager = FileManager(
            whisper=self.recognizer
        )

        self.browser_controller = BrowserController()

        # ------------------------------------------
        # Vision Engine
        # ------------------------------------------

        try:

            self.vision = VisionEngine(
                ocr_language="eng"
            )

            print(
                "Vision Engine Ready."
            )

            print(
                f"Vision OCR : {self.vision.is_available()}"
            )

            print(
                f"Vision Objects : "
                f"{self.vision.is_object_detection_available()}"
            )

        except Exception as error:

            self.vision = None

            print(
                f"Vision Engine Initialization Error : {error}"
            )

        # ------------------------------------------
        # Gemini AI
        # ------------------------------------------

        self.gemini = GeminiClient()

        # ------------------------------------------
        # Multi-Command Planning
        # ------------------------------------------

        self.multi_command_planner = MultiCommandPlanner(
            gemini_client=self.gemini
        )

        # ------------------------------------------
        # Dispatcher
        # ------------------------------------------

        self.dispatcher = CommandDispatcher(

            tts=self.tts,

            app_launcher=self.app_launcher,

            app_closer=self.app_closer,

            keyboard_controller=self.keyboard_controller,

            mouse_controller=self.mouse_controller,

            window_controller=self.window_controller,

            system_controller=self.system_controller,

            file_finder=self.file_finder,

            folder_manager=self.folder_manager,

            file_manager=self.file_manager,

            browser_controller=self.browser_controller,

            whisper=self.recognizer,

            gemini_client=self.gemini

        )

        # ------------------------------------------
        # Multi-Command Executor
        # ------------------------------------------

        self.multi_command_executor = MultiCommandExecutor(
            dispatcher=self.dispatcher
        )

        print("Backend Ready.")

        print("=============================\n")

        self._backend_ready = True
        return True

    # --------------------------------------------------
    # Speech Completion / Non-Blocking UI Helpers
    # --------------------------------------------------

    def _unlock_after_speech(
        self,
        restart_wake=True,
        terminal_avatar_state="idle"
    ):
        """
        Keep the microphone locked while ASTRA is speaking,
        without blocking the Qt GUI thread.

        This replaces blocking calls to
        ``tts.wait_until_done()`` inside the UI thread.
        """

        def check_speech():

            if self._closing:
                return

            try:
                speaking = (
                    self.tts is not None
                    and self.tts.speaking()
                )
            except Exception:
                speaking = False

            if speaking:
                QTimer.singleShot(
                    60,
                    check_speech
                )
                return

            self.unlock_microphone()

            # Command/TTS lifecycle is complete. Keep the terminal
            # result visible (success/error) after speech ends.
            # Normal lifecycle still returns to the idle slideshow.
            self._set_avatar_state(
                terminal_avatar_state or "idle"
            )

            try:
                self.left_panel.set_speaking(
                    "Silent"
                )
            except Exception:
                pass

            if (
                restart_wake
                and self.wake_word_enabled
                and not self.manual_listening_requested
                and not self._pending_file_selection
            ):
                QTimer.singleShot(
                    350,
                    self.start_wake_word_worker
                )

        # Give the TTS worker a moment to start before polling.
        QTimer.singleShot(
            120,
            check_speech
        )

    def _extract_selection_number(
        self,
        text
    ):
        """
        Extract a numeric file-selection answer.

        Accepts:
            1
            2.
            number 2
            option 2
            choose 2
            select number 2
        """

        if text is None:
            return None

        cleaned = str(text).strip().lower()

        match = re.search(
            r"\b(?:number|option|choice|select|choose)\s*(\d+)\b",
            cleaned
        )

        if match:
            return int(match.group(1))

        match = re.fullmatch(
            r"(?:the\s+)?(\d+)[\s\.!?]*",
            cleaned
        )

        if match:
            return int(match.group(1))

        # Whisper may return a spoken number.
        spoken_numbers = {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }

        for word, number in spoken_numbers.items():

            if re.search(
                rf"\b{word}\b",
                cleaned
            ):
                return number

        return None

    def _wait_for_speech_then_start_selection(
        self
    ):
        """
        Start the numeric selection listener only after ASTRA
        has completely stopped speaking.
        """

        if not self._pending_file_selection:
            return

        def check():

            if not self._pending_file_selection:
                return

            if self.tts is not None:

                try:
                    if self.tts.speaking():
                        QTimer.singleShot(
                            80,
                            check
                        )
                        return
                except Exception:
                    pass

            self.status_label.setText(
                "Status : Waiting for File Selection"
            )

            try:
                self.left_panel.set_listening(
                    "Select File Number"
                )

                self._set_thinking_state(
                    "Waiting for Selection"
                )

                self.left_panel.set_speaking(
                    "Silent"
                )

                self.mic_widget.show_listening()

                self.mic_widget.set_listening(
                    True
                )

            except Exception:
                pass

            self.manual_listening_requested = True

            # --------------------------------------------------
            # Lock microphone while ASTRA is preparing the
            # selection listener.
            # --------------------------------------------------

            self.lock_microphone()

            QTimer.singleShot(
                180,
                lambda: self._start_file_selection_listener()
            )

        QTimer.singleShot(
            120,
            check
        )

    def _start_file_selection_listener(self):
        """
        Start microphone listening specifically for a pending
        file-selection number.

        This method is called only after ASTRA has stopped speaking.
        """

        if self._closing:
            return

        if not self._pending_file_selection:
            return

        # --------------------------------------------------
        # Safety: never start another worker if one is alive.
        # --------------------------------------------------

        if self.voice_worker is not None:

            try:

                if self.voice_worker.isRunning():
                    return

            except Exception:
                pass

        self.status_label.setText(
            "Status : Listening for File Selection"
        )

        try:

            self.left_panel.set_listening(
                "Listening for Number"
            )

            self._set_thinking_state(
                "Waiting for Selection"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

            self.mic_widget.show_listening()

            # Start a clean visual meter for every recording session.
            self.mic_widget.set_listening(
                True
            )

            self.mic_widget.update_audio_level(
                0.0
            )

        except Exception:
            pass

        # --------------------------------------------------
        # Start manual listener.
        # --------------------------------------------------

        self.start_voice_worker(
            wake_word_mode=False
        )

    def _handle_pending_file_selection(
        self,
        text
    ):
        """
        Handle the numeric selection for a pending file operation.

        The original dispatcher payload is preserved so that the
        selected number resumes the exact same operation instead of
        sending the number back through intent detection.
        """

        pending = self._pending_file_selection

        if not pending:
            return False

        selection = self._extract_selection_number(
            text
        )

        candidates = pending.get(
            "candidates",
            []
        )

        # --------------------------------------------------
        # No candidates
        # --------------------------------------------------

        if not candidates:

            self._pending_file_selection = None

            self.clear_file_selection()

            message = (
                "The file selection list is no longer available. "
                "Please repeat the command."
            )

            self.mic_widget.update_ai_message(
                message
            )

            self.status_label.setText(
                "Status : File Selection Expired"
            )

            try:

                self.tts.speak(
                    message
                )

            except Exception:
                pass

            self._unlock_after_speech(
                restart_wake=True
            )

            return True

        # --------------------------------------------------
        # Invalid / unclear selection
        # --------------------------------------------------

        if selection is None:

            message = (
                "Please say the number of the file "
                "you want to select."
            )

            self.mic_widget.update_ai_message(
                message
            )

            self.status_label.setText(
                "Status : Waiting for File Selection"
            )

            try:

                self.left_panel.set_listening(
                    "Waiting for Number"
                )

                self._set_thinking_state(
                    "Select File"
                )

                self.left_panel.set_speaking(
                    "Speaking"
                )

            except Exception:
                pass

            try:

                self.tts.speak(
                    message
                )

            except Exception:
                pass

            self._wait_for_speech_then_start_selection()

            return True

        # --------------------------------------------------
        # Range validation
        # --------------------------------------------------

        if not (
            1 <= selection <= len(candidates)
        ):

            message = (
                f"That selection is invalid. "
                f"Please choose a number between "
                f"1 and {len(candidates)}."
            )

            self.mic_widget.update_ai_message(
                message
            )

            self.status_label.setText(
                "Status : Invalid File Selection"
            )

            try:

                self.tts.speak(
                    message
                )

            except Exception:
                pass

            self._wait_for_speech_then_start_selection()

            return True

        # --------------------------------------------------
        # Preserve the COMPLETE dispatcher payload
        # --------------------------------------------------

        pending_command = dict(
            pending
        )

        # --------------------------------------------------
        # Consume pending state BEFORE dispatching.
        # This prevents duplicate microphone events from
        # executing the same selection twice.
        # --------------------------------------------------

        self._pending_file_selection = None

        self.clear_file_selection()

        # --------------------------------------------------
        # Selected candidate
        # --------------------------------------------------

        selected_candidate = candidates[
            selection - 1
        ]

        if isinstance(
            selected_candidate,
            dict
        ):

            selected_name = (
                selected_candidate.get(
                    "name"
                )
                or selected_candidate.get(
                    "filename"
                )
                or "file"
            )

            selected_path = (
                selected_candidate.get(
                    "path"
                )
                or ""
            )

        else:

            selected_name = str(
                selected_candidate
            )

            selected_path = ""

        # --------------------------------------------------
        # UI
        # --------------------------------------------------

        # The user has selected the exact candidate, but the
        # filesystem operation must NOT execute from the UI at this
        # point. Resume the original command and let the dispatcher
        # return a confirmation request when required.
        self.status_label.setText(
            "Status : File Selected"
        )

        self.mic_widget.update_ai_message(
            f"Selected option {selection}. Preparing confirmation..."
        )

        self.conversation_label.setText(
            f"Selected File\n\n"
            f"{selection}. {selected_name}"
            + (
                f"\n\nLocation:\n{selected_path}"
                if selected_path
                else ""
            )
        )

        try:

            self.left_panel.set_listening(
                "Idle"
            )

            self._set_thinking_state(
                "Preparing Confirmation"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:
            pass

        # --------------------------------------------------
        # Resume ORIGINAL dispatcher command
        # --------------------------------------------------

        payload = pending_command.get(
            "payload"
        )

        if isinstance(
            payload,
            dict
        ):

            payload = dict(
                payload
            )

        else:

            # Backward-compatible fallback for old pending
            # structures already stored by MainWindow.
            payload = {
                "intent": pending_command.get(
                    "intent"
                ),
                "entity": pending_command.get(
                    "entity"
                ),
                "typed_text": pending_command.get(
                    "typed_text"
                ),
                "browser": pending_command.get(
                    "browser"
                ),
                "website": pending_command.get(
                    "website"
                ),
                "search_query": pending_command.get(
                    "search_query"
                ),
                "profile": pending_command.get(
                    "profile"
                ),
                "user_text": pending_command.get(
                    "user_text"
                ),
                "multi_command": pending_command.get(
                    "multi_command",
                    False
                ),
            }

        # Preserve the exact candidate path selected by the user.
        # CommandDispatcher still receives the numeric selection for
        # backward compatibility, while this metadata prevents the
        # selected candidate from being lost during confirmation.
        if selected_path:
            selected_entity = payload.get("entity")

            if isinstance(selected_entity, dict):
                selected_entity = dict(selected_entity)
            else:
                selected_entity = {
                    "entity": selected_entity
                } if selected_entity else {}

            selected_entity["selected_path"] = selected_path
            selected_entity["selection_path"] = selected_path
            payload["entity"] = selected_entity

        try:

            result = self.dispatcher.dispatch(

                intent=payload.get(
                    "intent"
                ),

                entity=payload.get(
                    "entity"
                ),

                typed_text=payload.get(
                    "typed_text"
                ),

                browser=payload.get(
                    "browser"
                ),

                website=payload.get(
                    "website"
                ),

                search_query=payload.get(
                    "search_query"
                ),

                profile=payload.get(
                    "profile"
                ),

                user_text=payload.get(
                    "user_text"
                ),

                multi_command=payload.get(
                    "multi_command",
                    False
                ),

                selection=selection

            )

        except Exception as error:

            print(
                f"Selected File Dispatch Error : {error}"
            )

            result = {
                "success": False,
                "status": "Status : File Selection Failed",
                "message": (
                    "I could not complete the selected "
                    "file operation."
                )
            }

        # --------------------------------------------------
        # Use ONE result handler only
        # --------------------------------------------------

        self._handle_dispatch_result(

            result,

            payload.get(
                "user_text",
                str(text)
            ),

            payload.get(
                "intent"
            ),

            payload.get(
                "entity"
            ),

        )

        return True

    def _finish_dispatch_result(
        self,
        result,
        text,
        intent=None,
        entity=None
    ):
        """
        Backward-compatible wrapper.

        All dispatcher results now use one centralized result
        handler so file selection and confirmation state cannot
        diverge between two different flows.
        """

        self._handle_dispatch_result(
            result,
            text,
            intent,
            entity,
        )

    # --------------------------------------------------
    # Confirmation Helpers
    # --------------------------------------------------

    def _parse_confirmation(self, text):
        """
        Parse a YES/NO confirmation answer.

        Returns:
            True  -> explicit yes
            False -> explicit no
            None  -> unclear answer
        """

        if text is None:
            return None

        cleaned = re.sub(
            r"[^a-z0-9\s]",
            " ",
            str(text).strip().lower()
        )

        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned
        )

        yes_patterns = (
            "yes",
            "yeah",
            "yep",
            "yup",
            "sure",
            "okay",
            "ok",
            "confirm",
            "confirmed",
            "do it",
            "go ahead",
            "proceed",
            "continue",
            "please do",
            "affirmative",
        )

        no_patterns = (
            "no",
            "nope",
            "nah",
            "cancel",
            "cancel it",
            "stop",
            "dont",
            "do not",
            "negative",
            "abort",
        )

        if cleaned in yes_patterns:
            return True

        if cleaned in no_patterns:
            return False

        # Whisper often returns a short phrase such as
        # "yes please" or "no please".
        yes_prefixes = (
            "yes ",
            "yeah ",
            "yep ",
            "sure ",
            "okay ",
            "ok ",
            "confirm ",
            "go ahead ",
            "please do ",
        )

        no_prefixes = (
            "no ",
            "nope ",
            "cancel ",
            "stop ",
            "dont ",
            "do not ",
        )

        if cleaned.startswith(yes_prefixes):
            return True

        if cleaned.startswith(no_prefixes):
            return False

        return None

    def _start_confirmation_listener_after_prompt(self):
        """
        Start the microphone only after the confirmation prompt
        has completely finished speaking.
        """

        if self._closing:
            return

        if not self._pending_confirmation:
            return

        if self.voice_worker is not None:
            try:
                if self.voice_worker.isRunning():
                    return
            except Exception:
                pass

        self.manual_listening_requested = True

        self.status_label.setText(
            "Status : Waiting for Confirmation"
        )

        try:
            self.mic_widget.show_listening()
            self.mic_widget.set_listening(True)

            self.left_panel.set_listening(
                "Say Yes or No"
            )
            self._set_thinking_state(
                "Waiting for Confirmation"
            )
            self.left_panel.set_speaking(
                "Silent"
            )
        except Exception:
            pass

        QApplication.processEvents()

        QTimer.singleShot(
            80,
            lambda: self.start_voice_worker(
                wake_word_mode=False
            )
        )

    def _wait_for_confirmation_prompt(self):
        """
        Wait asynchronously until ASTRA finishes the confirmation
        prompt. The Qt GUI thread is never blocked.
        """

        if self._closing:
            return

        if not self._pending_confirmation:
            return

        try:
            speaking = (
                self.tts is not None
                and self.tts.speaking()
            )
        except Exception:
            speaking = False

        if speaking:
            QTimer.singleShot(
                60,
                self._wait_for_confirmation_prompt
            )
            return

        self._start_confirmation_listener_after_prompt()

    def _begin_confirmation_flow(self, result):
        """
        Store the dispatcher confirmation payload and ask the user
        for YES/NO through the existing voice worker.

        CommandDispatcher never listens for confirmation itself.
        """

        self._pending_confirmation = {
            "action": result.get(
                "confirmation_action",
                result.get("intent")
            ),
            "payload": result.get(
                "confirmation_payload",
                {}
            ),
            "message": result.get(
                "confirmation_message",
                result.get(
                    "message",
                    "Please confirm."
                )
            ),
        }

        self.manual_listening_requested = True
        self.lock_microphone()

        message = self._pending_confirmation["message"]

        self.status_label.setText(
            "Status : Confirmation Required"
        )

        self.mic_widget.update_ai_message(
            message
        )

        self.conversation_label.setText(
            f"Confirmation Required\n\n{message}\n\n"
            "Please say Yes or No."
        )

        try:
            self.left_panel.set_listening(
                "Waiting for Confirmation"
            )
            self._set_thinking_state(
                "Confirmation Required"
            )
            self.left_panel.set_speaking(
                "Speaking"
            )
            self.mic_widget.show_listening()
            self.mic_widget.set_listening(False)
        except Exception:
            pass

        # The dispatcher did not speak this confirmation.
        # MainWindow owns TTS and waits asynchronously before
        # starting Whisper, preventing ASTRA from hearing itself.
        try:
            self.tts.speak(
                f"{message} Please say yes or no."
            )
        except Exception as error:
            print(
                f"Confirmation TTS Error : {error}"
            )

        QTimer.singleShot(
            100,
            self._wait_for_confirmation_prompt
        )

    def _cancel_pending_confirmation(self):
        """
        Cancel the pending operation without executing it.
        """

        self._pending_confirmation = None
        self.manual_listening_requested = False

        self.status_label.setText(
            "Status : Cancelled"
        )

        self.mic_widget.update_ai_message(
            "Operation cancelled."
        )

        self.conversation_label.setText(
            "Operation Cancelled"
        )

        try:
            self.left_panel.set_listening(
                "Idle"
            )
            self._set_thinking_state(
                "Inactive"
            )
            self.left_panel.set_speaking(
                "Speaking"
            )
        except Exception:
            pass

        try:
            self.tts.speak(
                "Operation cancelled."
            )
        except Exception:
            pass

        self._unlock_after_speech(
            restart_wake=True
        )

    def _handle_confirmation_response(self, text):
        """
        Handle a YES/NO answer for the pending confirmation.

        Returns True when the input was consumed by the
        confirmation flow.
        """

        if not self._pending_confirmation:
            return False

        answer = self._parse_confirmation(text)

        # ---------------------------------
        # Unclear answer
        # ---------------------------------

        if answer is None:

            message = (
                "I did not understand. "
                "Please say yes or no."
            )

            self.mic_widget.update_ai_message(
                message
            )

            self.status_label.setText(
                "Status : Confirmation Required"
            )

            try:
                self.left_panel.set_listening(
                    "Waiting for Confirmation"
                )
                self._set_thinking_state(
                    "Say Yes or No"
                )
                self.left_panel.set_speaking(
                    "Speaking"
                )
            except Exception:
                pass

            try:
                self.tts.speak(
                    message
                )
            except Exception:
                pass

            # Keep the pending confirmation and listen again
            # only after TTS has stopped.
            QTimer.singleShot(
                100,
                self._wait_for_confirmation_prompt
            )

            return True

        # ---------------------------------
        # NO
        # ---------------------------------

        if answer is False:

            self._cancel_pending_confirmation()

            return True

        # ---------------------------------
        # YES
        # ---------------------------------

        pending = self._pending_confirmation

        self._pending_confirmation = None
        self.manual_listening_requested = False

        self.status_label.setText(
            "Status : Executing Confirmed Action"
        )

        self.mic_widget.update_ai_message(
            "Confirmed. Executing..."
        )

        try:
            self.left_panel.set_listening(
                "Idle"
            )
            self._set_thinking_state(
                "Executing"
            )
            self.left_panel.set_speaking(
                "Silent"
            )
        except Exception:
            pass

        payload = dict(
            pending.get(
                "payload",
                {}
            )
        )

        action = pending.get(
            "action"
        )

        try:

            result = self.dispatcher.execute_confirmed_action(
                action,
                payload
            )

        except Exception as error:

            print(
                f"Confirmed Action Error : {error}"
            )

            result = {
                "success": False,
                "status": "Status : Confirmation Execution Failed",
                "message": (
                    "I could not complete the confirmed action."
                ),
            }

        self._handle_dispatch_result(
            result,
            payload.get(
                "user_text",
                ""
            ),
            payload.get(
                "intent",
                action
            ),
            payload.get("entity"),
        )

        return True

    # --------------------------------------------------
    # Microsoft Word V1 Clarification Helpers
    # --------------------------------------------------

    @staticmethod
    def _word_clarification_prompt(missing_parameters):
        """Return a natural prompt for missing Word parameters."""

        missing = [
            str(value).strip().lower()
            for value in (missing_parameters or [])
            if str(value).strip()
        ]

        if not missing:
            return "I need a little more information to continue."

        prompts = {
            "rows": "How many rows should the table have?",
            "columns": "How many columns should the table have?",
            "path": "What file path should I use?",
            "text": "What text would you like me to use?",
            "name": "What font name should I use?",
            "size": "What font size should I use?",
            "r": "What red color value should I use?",
            "g": "What green color value should I use?",
            "b": "What blue color value should I use?",
            "value": "What value should I use?",
            "style_name": "Which document style should I use?",
            "find_text": "What text should I find?",
            "replace_text": "What should I replace it with?",
            "url": "What URL should I use?",
            "display_text": "What display text should I use?",
        }

        if "rows" in missing and "columns" in missing:
            return "How many rows and columns should the table have?"

        if len(missing) == 1:
            key = missing[0]
            return prompts.get(
                key,
                f"What {key.replace('_', ' ')} should I use?",
            )

        readable = ", ".join(
            item.replace("_", " ") for item in missing
        )
        return f"Please provide these Word details: {readable}."

    @staticmethod
    def _extract_word_clarification_values(text, missing_parameters):
        """Extract missing Word values from a natural-language answer."""

        answer = str(text or "").strip()
        missing = [
            str(value).strip().lower()
            for value in (missing_parameters or [])
            if str(value).strip()
        ]
        values = {}

        if not answer or not missing:
            return values

        # Table dimensions: "5 rows and 3 columns" / "rows 5 columns 3".
        if "rows" in missing or "columns" in missing:
            row_match = re.search(
                r"(?:rows?|row\s*count)\s*(?:are|is|=|:)?\s*(\d+)",
                answer,
                flags=re.IGNORECASE,
            )
            col_match = re.search(
                r"(?:columns?|cols?|column\s*count)\s*(?:are|is|=|:)?\s*(\d+)",
                answer,
                flags=re.IGNORECASE,
            )

            if row_match:
                values["rows"] = int(row_match.group(1))
            if col_match:
                values["columns"] = int(col_match.group(1))

            if "rows" in missing and "rows" not in values:
                match = re.search(r"(\d+)\s*rows?", answer, re.IGNORECASE)
                if match:
                    values["rows"] = int(match.group(1))

            if "columns" in missing and "columns" not in values:
                match = re.search(r"(\d+)\s*columns?", answer, re.IGNORECASE)
                if match:
                    values["columns"] = int(match.group(1))

            if len(missing) == 2 and not values:
                numbers = re.findall(r"\d+", answer)
                if len(numbers) >= 2:
                    if "rows" in missing:
                        values["rows"] = int(numbers[0])
                    if "columns" in missing:
                        values["columns"] = int(numbers[1])

        # Numeric values such as font size / spacing / RGB.
        numeric_keys = {"size", "value", "r", "g", "b"}
        numeric_missing = [key for key in missing if key in numeric_keys]
        if numeric_missing:
            numbers = re.findall(r"-?\d+(?:\.\d+)?", answer)
            for index, key in enumerate(numeric_missing):
                if index < len(numbers):
                    raw = numbers[index]
                    values[key] = float(raw) if "." in raw else int(raw)

        for key in missing:
            if key in values:
                continue

            if key in {"path", "url"}:
                cleaned = answer.strip().strip('"').strip("'")
                prefixes = (
                    "the path is ",
                    "path is ",
                    "the file is ",
                    "file is ",
                    "the url is ",
                    "url is ",
                    "link is ",
                )
                lowered = cleaned.lower()
                for prefix in prefixes:
                    if lowered.startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                        break
                values[key] = cleaned
                continue

            if key in {
                "text",
                "name",
                "style_name",
                "find_text",
                "replace_text",
                "display_text",
            }:
                values[key] = answer

        return values

    def _begin_word_clarification(self, result, text, intent=None, entity=None):
        """Store a Word clarification request and prepare the follow-up."""

        missing = list(result.get("missing_parameters", []) or [])
        action = result.get("word_action") or intent

        base_entity = (
            dict(entity)
            if isinstance(entity, dict)
            else ({"entity": entity} if entity is not None else {})
        )

        self._pending_word_clarification = {
            "action": action,
            "entity": base_entity,
            "typed_text": result.get("typed_text"),
            "user_text": text,
            "missing_parameters": missing,
        }

        prompt = self._word_clarification_prompt(missing)

        try:
            self.mic_widget.update_ai_message(prompt)
        except Exception:
            pass

        try:
            self.conversation_panel.show_ai_response(prompt)
        except Exception:
            pass

        self.status_label.setText(
            "Status : Waiting for Word Information"
        )

        try:
            self.left_panel.set_listening(
                "Waiting for Word Information"
            )
            self._set_thinking_state(
                "Waiting for Word Information",
                avatar_state="thinking_laptop",
            )
            self.left_panel.set_speaking("Speaking")
        except Exception:
            pass

        # CommandDispatcher already sends the clarification through TTS.
        # MainWindow therefore only waits for that speech to finish.
        self._unlock_after_speech(
            restart_wake=True,
            terminal_avatar_state="thinking_laptop",
        )

    def _handle_word_clarification_response(self, text):
        """Resume the pending Word operation using the user's answer."""

        pending = self._pending_word_clarification
        if not pending:
            return False

        answer = str(text or "").strip()
        if not answer:
            return True

        values = self._extract_word_clarification_values(
            answer,
            pending.get("missing_parameters", []),
        )

        missing = [
            key
            for key in pending.get("missing_parameters", [])
            if key not in values or values[key] in (None, "")
        ]

        if missing:
            pending["entity"].update(values)
            pending["missing_parameters"] = missing

            prompt = self._word_clarification_prompt(missing)

            try:
                self.mic_widget.update_ai_message(prompt)
                self.conversation_panel.show_ai_response(prompt)
            except Exception:
                pass

            self.status_label.setText(
                "Status : Waiting for Word Information"
            )

            try:
                self.tts.speak(prompt)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_wake=True,
                terminal_avatar_state="thinking_laptop",
            )
            return True

        entity = dict(pending.get("entity") or {})
        entity.update(values)
        action = pending.get("action")
        original_command = pending.get("user_text") or action or "Word operation"

        self._pending_word_clarification = None
        self.lock_microphone()

        self.status_label.setText(
            "Status : Executing Word Operation..."
        )

        try:
            self.mic_widget.show_conversation(answer, "Executing...")
            self.conversation_panel.show_ai_response(
                "Got it. Continuing with the Word operation..."
            )
        except Exception:
            pass

        try:
            self._set_thinking_state(
                "Executing",
                avatar_state="thinking_laptop",
            )
            self.left_panel.set_speaking("Silent")
        except Exception:
            pass

        try:
            result = self.dispatcher.dispatch(
                intent=action,
                entity=entity,
                typed_text=pending.get("typed_text"),
                user_text=original_command,
            )
        except Exception as error:
            print(f"Word Clarification Dispatch Error : {error}")
            result = {
                "success": False,
                "status": "Status : Word Operation Failed",
                "message": "I could not complete the Word operation.",
            }

        self._handle_dispatch_result(
            result,
            original_command,
            action,
            entity,
        )
        return True

    def _handle_dispatch_result(
        self,
        result,
        text,
        intent=None,
        entity=None,
    ):
        """
        Apply a CommandDispatcher result to the UI.

        This centralizes confirmation, multi-file selection,
        success, and failure handling so both normal commands and
        confirmed commands follow the same lifecycle.
        """

        result = result or {}

        # Code Agent has its own complete generation/compile/run
        # lifecycle. Present its result before generic branches.
        if self._handle_code_agent_result(result, text):
            return

        # ---------------------------------
        # Word Information Required
        # ---------------------------------
        if result.get("requires_information") or (
            result.get("requires_clarification")
            and result.get("word_action")
        ):

            self._begin_word_clarification(
                result,
                text,
                intent,
                entity,
            )

            return

        # ---------------------------------
        # Confirmation Required
        # ---------------------------------

        if result.get(
            "requires_confirmation"
        ) or result.get(
            "confirmation_required"
        ):

            self._begin_confirmation_flow(
                result
            )

            return

        # ---------------------------------
        # File Selection Required
        # ---------------------------------

        if result.get(
            "requires_selection"
        ):

            candidates = result.get(
                "candidates",
                []
            )

            if not candidates:

                failure_message = (
                    "I could not find any selectable files."
                )

                self.mic_widget.update_ai_message(
                    failure_message
                )

                self.status_label.setText(
                    "Status : File Selection Failed"
                )

                try:

                    self.tts.speak(
                        failure_message
                    )

                except Exception:
                    pass

                self._unlock_after_speech(
                    restart_wake=True
                )

                return

            # ---------------------------------
            # IMPORTANT:
            # Preserve the exact payload created by
            # CommandDispatcher.
            # ---------------------------------

            pending_payload = result.get(
                "pending_payload"
            )

            if not isinstance(
                pending_payload,
                dict
            ):

                # Backward-compatible fallback
                pending_payload = {
                    "intent": intent,
                    "entity": entity,
                    "typed_text": result.get(
                        "typed_text"
                    ),
                    "browser": result.get(
                        "browser"
                    ),
                    "website": result.get(
                        "website"
                    ),
                    "search_query": result.get(
                        "search_query"
                    ),
                    "profile": result.get(
                        "profile"
                    ),
                    "user_text": text,
                    "multi_command": False,
                }

            else:

                pending_payload = dict(
                    pending_payload
                )

            # Make sure current command context exists.
            pending_payload.setdefault(
                "intent",
                intent
            )

            pending_payload.setdefault(
                "entity",
                entity
            )

            pending_payload.setdefault(
                "user_text",
                text
            )

            # ---------------------------------
            # Store selection state
            # ---------------------------------

            self._pending_file_selection = {

                "payload": pending_payload,

                "candidates": candidates,

                "operation": result.get(
                    "pending_action",
                    "file"
                ),

            }

            # ---------------------------------
            # Show candidates ONLY in UI.
            # Do not read the full paths through TTS.
            # ---------------------------------

            self.show_file_selection(

                candidates,

                operation=result.get(
                    "pending_action",
                    "file"
                )

            )

            # ---------------------------------
            # Short voice prompt
            # ---------------------------------

            message = (
                f"I found {len(candidates)} matching "
                f"{result.get('pending_action', 'file')}s. "
                "Please say the number you want."
            )

            self.mic_widget.update_ai_message(
                message
            )

            self.status_label.setText(
                "Status : Waiting for File Selection"
            )

            try:

                self.left_panel.set_listening(
                    "Waiting for File Number"
                )

                self._set_thinking_state(
                    "Select a File"
                )

                self.left_panel.set_speaking(
                    "Speaking"
                )

            except Exception:
                pass

            # ---------------------------------
            # MainWindow owns TTS + microphone
            # lifecycle.
            # ---------------------------------

            try:

                self.tts.speak(
                    message
                )

            except Exception as error:

                print(
                    f"File Selection Prompt Error : {error}"
                )

            # Start microphone only AFTER TTS ends.
            self._wait_for_speech_then_start_selection()

            return

        # ---------------------------------
        # Success
        # ---------------------------------

        if result.get(
            "success",
            False
        ):

            reply = result.get(
                "message",
                result.get(
                    "status",
                    "Done."
                )
            )

            self.mic_widget.update_ai_message(
                reply
            )

            self.status_label.setText(
                result.get(
                    "status",
                    "Status : Completed"
                )
            )

            self.conversation_label.setText(
                f"Executed Successfully\n\n{text}"
            )

            if (
                intent == "launch_application"
                and entity
            ):

                self.last_application = self._entity_text(entity)

                entity_name = self._entity_text(entity).lower()

                if (
                    "notepad" in entity_name
                    or "word" in entity_name
                ):
                    self.typing_mode = True

            try:
                self.left_panel.set_listening(
                    "Idle"
                )
                self._set_thinking_state(
                    "Inactive"
                )
                self.left_panel.set_speaking(
                    "Speaking"
                )
                self.right_panel.update_system_metrics()
            except Exception:
                pass

            # Show success immediately and keep it visible until the
            # next command changes the avatar state.
            self._set_avatar_state("success")

            # Dispatcher normally speaks successful replies itself.
            # Wait asynchronously instead of blocking the GUI.
            self._unlock_after_speech(
                restart_wake=True,
                terminal_avatar_state="success"
            )

            QTimer.singleShot(
                1400,
                lambda: self.left_panel.set_speaking(
                    "Silent"
                )
            )

            return

        # ---------------------------------
        # Failed / Cancelled
        # ---------------------------------

        failure_reply = result.get(
            "message",
            "Sorry, I could not complete that request."
        )

        self.mic_widget.update_ai_message(
            failure_reply
        )

        self.status_label.setText(
            result.get(
                "status",
                "Status : No Action"
            )
        )

        self.conversation_label.setText(
            f"Command Failed\n\n{text}\n\n"
            f"{result.get('status', '')}"
        )

        try:
            self.left_panel.set_listening(
                "Idle"
            )
            self._set_thinking_state(
                "Inactive"
            )
            self.left_panel.set_speaking(
                "Speaking"
            )
        except Exception:
            pass

        # Avoid speaking twice if the dispatcher already has TTS
        # running. If it is not speaking, provide the failure reply.
        try:
            if (
                self.tts is not None
                and not self.tts.speaking()
            ):
                self.tts.speak(
                    failure_reply
                )
        except Exception:
            pass

        # Show the command failure state for unsupported/failed local
        # automation commands.
        self._set_avatar_state("error")

        self._unlock_after_speech(
            restart_wake=True,
            terminal_avatar_state="error"
        )

        QTimer.singleShot(
            1400,
            lambda: self.left_panel.set_speaking(
                "Silent"
            )
        )

    # --------------------------------------------------
    # Intent Routing Helpers
    # --------------------------------------------------

    @staticmethod
    def _is_code_agent_request(text):
        """Return True only for explicit Python/Java code-generation requests.

        MainWindow keeps a final routing guard because conversational
        protection inside IntentDetector may classify some explicit coding
        commands as ``ai_chat``. Explicit executable requests must reach
        CommandDispatcher -> CodeAgent instead of Gemini.
        """

        cleaned = str(text or "").strip().lower()
        if not cleaned:
            return False

        # V1 supports Python and Java only, and the language must be explicit.
        has_python = bool(re.search(r"\bpython\b|\bpy\b", cleaned))
        has_java = bool(re.search(r"\bjava\b", cleaned))

        if not (has_python or has_java):
            return False

        code_actions = (
            r"\bwrite\b",
            r"\bcreate\b",
            r"\bgenerate\b",
            r"\bbuild\b",
            r"\bdevelop\b",
            r"\bimplement\b",
            r"\bmake\b.*\bprogram\b",
        )

        has_code_action = any(
            re.search(pattern, cleaned)
            for pattern in code_actions
        )

        has_code_noun = bool(
            re.search(
                r"\b(code|program|programme|source\s+code|script)\b",
                cleaned,
            )
        )

        has_algorithm_request = bool(
            re.search(
                r"\b(algorithm|data\s+structure)\b.*\b(in|using|with)\b",
                cleaned,
            )
            or re.search(
                r"\b(in|using|with)\b.*\b(algorithm|data\s+structure)\b",
                cleaned,
            )
        )

        if not (
            has_code_action
            or has_code_noun
            or has_algorithm_request
        ):
            return False

        # Keep educational/conversational programming questions in Gemini.
        conversational_markers = (
            "what is ",
            "what are ",
            "what does ",
            "what do ",
            "who is ",
            "why ",
            "how does ",
            "how do ",
            "explain ",
            "tell me about ",
            "difference between ",
            "meaning of ",
            "definition of ",
        )

        if any(
            cleaned.startswith(marker)
            for marker in conversational_markers
        ) and not has_code_action:
            return False

        return True

    def _is_word_command_context(self, text):
        """Detect explicit or active Microsoft Word command context."""
        cleaned = str(text or "").strip().lower()
        if not cleaned:
            return False

        word_terms = (
            "word", "ms word", "microsoft word", "document", "docx",
            "paragraph", "font", "font size", "text size", "bold",
            "italic", "underline", "strikethrough", "highlight",
            "heading", "bullet", "numbered list", "table", "rows",
            "columns", "align left", "align center", "align right",
            "justify", "page break", "header", "footer", "page number",
        )

        if any(term in cleaned for term in word_terms):
            return True

        return "word" in str(self.last_application or "").lower()

    def _detect_intent_with_context(self, text):
        """Detect intent while preserving Word context omitted by speech."""
        detector = self.intent_detector
        cleaned = str(text or "").strip()
        if detector is None or not cleaned:
            return None

        if self._is_word_command_context(cleaned):
            word_text = cleaned.lower()
            if not any(token in word_text for token in ("word", "document", "docx")):
                word_text = "word " + word_text

            try:
                intent = detector.detect_intent(word_text)
                word_intents = {
                    "open_word", "close_word", "create_blank_document",
                    "open_existing_document", "save", "save_as", "save_docx",
                    "save_pdf", "close_current_document", "create_specified_filename",
                    "read_existing_document", "add_text_at_cursor", "replace_content",
                    "read_document", "clear_document", "select_all", "copy", "cut",
                    "paste", "type_text", "strikethrough", "underline", "italic",
                    "bold", "font_size", "font", "text_color", "highlight",
                    "align_left", "align_center", "align_right", "justify",
                    "line_spacing", "paragraph_spacing", "indentation", "bullets",
                    "numbering", "title", "heading_1", "normal", "document_style",
                    "read_table_data", "create_table", "replace", "find", "image",
                    "hyperlink", "page_break", "new_page", "header", "footer",
                    "page_number",
                }
                if intent in word_intents:
                    return intent
            except Exception as error:
                print(f"Word Intent Detection Error : {error}")

        try:
            return detector.detect_intent(cleaned)
        except Exception as error:
            print(f"Intent Detection Error : {error}")
            return None

    @staticmethod
    def _entity_text(entity):
        """Return a safe display name from scalar or structured entities."""
        if isinstance(entity, dict):
            for key in ("application", "app", "name", "entity", "target", "value"):
                if entity.get(key):
                    return str(entity[key])
            return ""
        return str(entity or "")

    # --------------------------------------------------
    # --------------------------------------------------
    # Vision Command Detection
    # --------------------------------------------------

    @staticmethod
    def _is_vision_command(text):
        """Detect explicit requests to describe/analyze the current screen."""

        cleaned = re.sub(
            r"\s+",
            " ",
            str(text or "").strip().lower()
        )

        if not cleaned:
            return False

        phrases = (
            "what is on screen",
            "what's on screen",
            "what is on my screen",
            "what's on my screen",
            "tell me what is on screen",
            "tell me what's on screen",
            "describe the screen",
            "describe screen",
            "analyze the screen",
            "analyze screen",
            "analyse the screen",
            "analyse screen",
            "what do you see on screen",
            "what do you see on my screen",
            "what can you see on screen",
            "look at the screen",
            "look at my screen",
            "read the screen",
            "read my screen",
            "screen-la enna irukku",
            "screen la enna irukku",
            "screen-la enna iruku",
            "screen la enna iruku",
            "screen la enna irukku nu sollu",
            "screen la enna iruku nu sollu",
        )

        return any(
            phrase in cleaned
            for phrase in phrases
        )

    @staticmethod
    def _format_vision_response(analysis):
        """Build a human-readable response with object/text coordinates."""

        analysis = analysis or {}

        description = str(
            analysis.get("description", "") or ""
        ).strip()

        objects = analysis.get("objects") or []
        words = analysis.get("ocr_words") or []

        parts = []

        if description:
            parts.append(description)
        else:
            parts.append(
                "I could not identify any readable text or supported objects on the screen."
            )

        if objects:
            locations = []

            for obj in objects[:50]:
                label = str(
                    obj.get("label", "object")
                )

                confidence = float(
                    obj.get("confidence", 0.0) or 0.0
                )

                locations.append(
                    f"{label}: box={obj.get('box')}, "
                    f"center={obj.get('center')}, "
                    f"confidence={confidence:.2f}"
                )

            parts.append(
                "Object coordinates: "
                + "; ".join(locations)
                + "."
            )

        if words:
            text_locations = []

            for word in words[:40]:
                word_text = str(
                    word.get("text", "")
                ).strip()

                if not word_text:
                    continue

                text_locations.append(
                    f"{word_text}: box={word.get('box')}, "
                    f"center={word.get('center')}"
                )

            if text_locations:
                parts.append(
                    "Text coordinates: "
                    + "; ".join(text_locations)
                    + "."
                )

        width = analysis.get("image_width")
        height = analysis.get("image_height")

        if width and height:
            parts.append(
                f"Screen size: {width} x {height} pixels."
            )

        return " ".join(parts).strip()

    def _start_vision_screen_analysis(
        self,
        speak_response=False
    ):
        """Analyze the current screen in a background VisionWorker."""

        if self._closing:
            return True

        if self.vision is None:
            message = (
                "Vision is not available. "
                "Please check the VisionEngine setup."
            )

            try:
                self.mic_widget.update_ai_message(message)
            except Exception:
                pass

            try:
                self.conversation_panel.show_error(message)
            except Exception:
                pass

            self.status_label.setText(
                "Status : Vision Unavailable"
            )

            if speak_response and self.tts is not None:
                try:
                    self.tts.speak(message)
                    self._unlock_after_speech(
                        restart_wake=True,
                        terminal_avatar_state="error"
                    )
                except Exception:
                    self.unlock_microphone()

            return True

        worker = getattr(
            self,
            "vision_worker",
            None
        )

        if worker is not None:
            try:
                if worker.isRunning():
                    message = "Vision is already analyzing the screen."

                    try:
                        self.mic_widget.update_ai_message(message)
                    except Exception:
                        pass

                    return True

            except RuntimeError:
                self.vision_worker = None

        self.vision_processing = True
        self._vision_speak_response = bool(
            speak_response
        )

        try:
            self.status_label.setText(
                "Status : Analyzing Screen..."
            )

            self.mic_widget.update_ai_message(
                "Let me look at the screen..."
            )

            self.conversation_label.setText(
                "Vision Analysis\n\n"
                "Analyzing the current screen..."
            )

            self._set_thinking_state(
                "Thinking",
                avatar_state="thinking_laptop"
            )

            self._set_avatar_state(
                "thinking_laptop"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:
            pass

        self.vision_worker = VisionWorker(
            self.vision
        )

        self.vision_worker.analysis_ready.connect(
            self._on_vision_analysis_ready
        )

        self.vision_worker.error_occurred.connect(
            self._on_vision_analysis_error
        )

        self.vision_worker.finished.connect(
            self._on_vision_worker_finished
        )

        print(
            "\n========== VISION SCREEN ANALYSIS =========="
        )

        print(
            "VisionWorker Started"
        )

        print(
            "===========================================\n"
        )

        self.vision_worker.start()

        return True

    @Slot(dict)
    def _on_vision_analysis_ready(
        self,
        analysis
    ):
        """Display completed Vision analysis on the GUI thread."""

        if self._closing:
            return

        message = self._format_vision_response(
            analysis
        )

        print(
            "\n========== VISION RESULT =========="
        )

        print(
            message
        )

        print(
            "===================================\n"
        )

        try:
            self.mic_widget.update_ai_message(
                message
            )
        except Exception:
            pass

        try:
            self.conversation_panel.show_ai_response(
                message
            )
        except Exception:
            pass

        self.conversation_label.setText(
            f"Vision Analysis\n\n{message}"
        )

        self.status_label.setText(
            "Status : Vision Analysis Complete"
        )

        try:
            self.right_panel.update_system_metrics()
        except Exception:
            pass

        try:
            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Speaking"
                if self._vision_speak_response
                else "Silent"
            )

        except Exception:
            pass

        if self._vision_speak_response:

            self._set_avatar_state(
                "speaking"
            )

            try:
                self.tts.speak(
                    message
                )

                self._unlock_after_speech(
                    restart_wake=True,
                    terminal_avatar_state="success"
                )

            except Exception as error:

                print(
                    f"Vision TTS Error : {error}"
                )

                self.unlock_microphone()

                self._set_avatar_state(
                    "success"
                )

        else:

            self._set_avatar_state(
                "success"
            )

    @Slot(str)
    def _on_vision_analysis_error(
        self,
        message
    ):
        """Handle Vision analysis errors."""

        if self._closing:
            return

        error_message = str(
            message or
            "I could not analyze the current screen."
        )

        print(
            f"Vision Analysis Failed : {error_message}"
        )

        try:
            self.mic_widget.update_ai_message(
                error_message
            )
        except Exception:
            pass

        try:
            self.conversation_panel.show_error(
                error_message
            )
        except Exception:
            pass

        self.status_label.setText(
            "Status : Vision Analysis Failed"
        )

        try:
            self.conversation_label.setText(
                f"Vision Analysis Failed\n\n"
                f"{error_message}"
            )

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Speaking"
                if self._vision_speak_response
                else "Silent"
            )

            self._set_avatar_state(
                "error"
            )

        except Exception:
            pass

        if (
            self._vision_speak_response
            and self.tts is not None
        ):

            try:

                self.tts.speak(
                    error_message
                )

                self._unlock_after_speech(
                    restart_wake=True,
                    terminal_avatar_state="error"
                )

                return

            except Exception:
                pass

        self.unlock_microphone()

    @Slot()
    def _on_vision_worker_finished(self):
        """Release VisionWorker after Qt reports that it has finished."""

        worker = getattr(
            self,
            "vision_worker",
            None
        )

        if worker is not None:

            try:

                if worker.isRunning():
                    return

            except RuntimeError:
                pass

        self.vision_processing = False
        self.vision_worker = None

    # Process Command
    # --------------------------------------------------

    def _start_code_agent_worker(self, command):
        """
        Start the complete Code Agent workflow in a background QThread.

        Voice and typed programming requests use this same entry point.
        MainWindow remains responsive while CommandDispatcher performs
        generation -> save -> compile -> retry -> terminal launch.
        """

        command = str(command or "").strip()

        if not command:
            self._handle_code_agent_worker_error(
                "Empty Code Agent command."
            )
            return False

        current_worker = getattr(
            self,
            "_code_agent_worker",
            None,
        )

        if current_worker is not None:
            try:
                if current_worker.isRunning():
                    print(
                        "[CODE AGENT] Existing worker is still running; "
                        "new request ignored."
                    )
                    return False
            except RuntimeError:
                self._code_agent_worker = None

        if self.dispatcher is None:
            self._handle_code_agent_worker_error(
                "CommandDispatcher is not available."
            )
            return False

        self._code_agent_processing = True

        try:
            self.status_label.setText(
                "Status : Code Agent Executing..."
            )

            self._thinking_avatar_mode = "thinking_laptop"
            self._set_avatar_state("thinking_laptop")

            try:
                self.left_panel.set_listening("Code Agent")
                self._set_thinking_state(
                    "Code Agent",
                    avatar_state="thinking_laptop",
                )
                self.left_panel.set_speaking("Silent")
                self.mic_widget.update_ai_message(
                    "Generating and running your program..."
                )
            except Exception:
                pass

            print(
                "\n========== CODE AGENT ASYNC ROUTE ==========",
                flush=True,
            )
            print(f"Request : {command}", flush=True)
            print(
                "Route   : MainWindow -> CodeAgentWorker -> "
                "CommandDispatcher -> CodeAgent",
                flush=True,
            )
            print("GUI     : NON-BLOCKING", flush=True)
            print("============================================\n", flush=True)

            worker = CodeAgentWorker(
                dispatcher=self.dispatcher,
                command=command,
            )

            self._code_agent_worker = worker

            worker.result_ready.connect(
                lambda result, original_command=command:
                self._handle_code_agent_worker_result(
                    result,
                    original_command,
                )
            )

            worker.error_occurred.connect(
                self._handle_code_agent_worker_error
            )

            worker.finished.connect(
                self._on_code_agent_worker_finished
            )

            worker.finished.connect(
                worker.deleteLater
            )

            worker.start()
            return True

        except Exception as error:
            self._code_agent_processing = False
            self._code_agent_worker = None
            self._handle_code_agent_worker_error(str(error))
            return False

    @Slot(object)
    def _handle_code_agent_worker_result(
        self,
        result,
        original_command,
    ):
        """
        Handle the completed Code Agent result on the Qt GUI thread.
        """

        if not isinstance(result, dict):
            result = {
                "success": False,
                "code_agent": True,
                "status": "Status : Code Agent Failed",
                "message": (
                    "Code Agent did not return a valid result."
                ),
                "error": "Invalid worker result.",
            }

        result = dict(result)
        result["code_agent"] = True

        execution = result.get("execution")
        if not isinstance(execution, dict):
            execution = {}

        print(
            "\n========== CODE AGENT GUI RESULT ==========",
            flush=True,
        )
        print(
            f"Success          : {result.get('success', False)}",
            flush=True,
        )
        print(
            f"Status           : {result.get('status', '')}",
            flush=True,
        )
        print(
            f"File             : {result.get('file_path', '')}",
            flush=True,
        )
        print(
            f"Compile Attempts : {result.get('compile_attempts', 0)}",
            flush=True,
        )
        print(
            f"Terminal Opened  : "
            f"{execution.get('terminal_opened', False)}",
            flush=True,
        )
        print(
            f"Execution Mode   : "
            f"{execution.get('execution_mode', '')}",
            flush=True,
        )
        print("===========================================\n", flush=True)

        self._handle_code_agent_result(
            result,
            original_command,
        )

    @Slot(str)
    def _handle_code_agent_worker_error(self, error):
        """
        Handle a Code Agent worker exception on the Qt GUI thread.
        """

        self._code_agent_processing = False

        error = str(error or "").strip()
        if not error:
            error = "Unknown Code Agent error."

        print(
            "\n========== CODE AGENT ASYNC ERROR ==========",
            flush=True,
        )
        print(f"Error : {error}", flush=True)
        print("============================================\n", flush=True)

        message = (
            "Sorry da, Code Agent could not complete that program."
        )

        try:
            self.conversation_panel.show_error(message)
        except Exception:
            pass

        try:
            self.mic_widget.update_ai_message(message)
        except Exception:
            pass

        try:
            self.status_label.setText(
                "Status : Code Agent Error"
            )
            self.conversation_label.setText(
                "Code Agent Error\n\n"
                f"Error:\n{error}"
            )
            self._set_thinking_state("Inactive")
            self.left_panel.set_speaking("Speaking")
        except Exception:
            pass

        self._set_avatar_state("error")

        try:
            if self.tts is not None:
                self.tts.speak(message)
        except Exception:
            pass

        self._unlock_after_speech(
            restart_wake=True,
            terminal_avatar_state="error",
        )

        QTimer.singleShot(
            1400,
            lambda: self.left_panel.set_speaking("Silent"),
        )

    @Slot()
    def _on_code_agent_worker_finished(self):
        """
        Clear the worker reference after the background QThread stops.
        """

        worker = self._code_agent_worker

        if worker is None:
            return

        try:
            if worker.isRunning():
                return
        except RuntimeError:
            pass

        self._code_agent_worker = None

    def _start_code_agent_route(self, original_text):
        """
        Common Code Agent entry point for voice and typed commands.
        """

        command = str(original_text or "").strip()

        if not command:
            return False

        return self._start_code_agent_worker(command)

    def process_command(
        self,
        text
    ):
        """
        Process the recognized voice command.

        Once a command is received, the microphone is
        immediately locked so the user cannot trigger
        another microphone action while ASTRA is processing.
        """

        # ------------------------------------------
        # Lock microphone immediately
        # ------------------------------------------

        self.lock_microphone()

        # ------------------------------------------
        # Pending Word clarification
        # ------------------------------------------
        if self._pending_word_clarification:

            if not text:
                return

            if self._handle_word_clarification_response(text):
                return

        # ------------------------------------------
        # Pending YES/NO confirmation
        # ------------------------------------------
        # Confirmation answers must never go through intent
        # detection. The original command payload is stored in
        # _pending_confirmation and is executed only after YES.
        if self._pending_confirmation:

            if not text:
                return

            if self._handle_confirmation_response(
                text
            ):
                return

        # ------------------------------------------
        # Pending numeric file selection
        # ------------------------------------------
        # A selection answer must not go through intent
        # detection again. Otherwise "2" can be treated as
        # a new/unknown command and the original operation
        # starts over.
        if self._pending_file_selection:

            if not text:
                return

            if self._handle_pending_file_selection(
                text
            ):
                return

        # ------------------------------------------
        # Normalize text
        # ------------------------------------------

        if not text:

            self.unlock_microphone()

            return

        text = text.strip()

        if not text:

            self.unlock_microphone()

            return

        # ------------------------------------------
        # Command Normalization
        # ------------------------------------------

        original_text = text

        if self.command_normalizer:

            text = self.command_normalizer.normalize(
                text
            )

            if text != original_text:

                print(
                    "\n========== COMMAND NORMALIZER =========="
                )

                print(
                    f"Original   : {original_text}"
                )

                print(
                    f"Normalized : {text}"
                )

                print(
                    "========================================\n"
                )

        # ------------------------------------------
        # Normalization Result Check
        # ------------------------------------------

        if not text:

            self.unlock_microphone()

            return

        # ------------------------------------------
        # Vision Command
        # ------------------------------------------
        # Full screen analysis: readable text + detected objects
        # + coordinates. Existing screenshot commands are untouched.
        # ------------------------------------------

        if self._is_vision_command(text):

            self.mic_widget.show_conversation(
                text,
                "Looking at the screen..."
            )

            self._start_vision_screen_analysis(
                speak_response=True
            )

            return

        # ------------------------------------------
        # Reset Conversation
        # ------------------------------------------

        self.mic_widget.show_conversation(
            text,
            "Thinking..."
        )

        # ------------------------------------------
        # DHEEPTHI Code Agent V1 Routing Guard
        # ------------------------------------------
        # Decide explicit Python/Java code generation before multi-command
        # planning and before the generic Gemini branch.
        code_agent_requested = self._is_code_agent_request(text)

        if code_agent_requested:
            print(
                "\n========== CODE AGENT ROUTING GUARD =========="
            )
            print(
                f"Programming request detected : {text}"
            )
            print(
                "Forcing intent : code_agent"
            )
            print(
                "==============================================\n"
            )

            # --------------------------------------------------
            # HARD V1 CODE-AGENT ROUTE
            # --------------------------------------------------
            # Run the complete dispatcher workflow in a background
            # QThread. This keeps the Qt event loop responsive while
            # Groq generation, compile/retry, and terminal launch run.
            # --------------------------------------------------

            self._start_code_agent_route(
                original_text
            )

            return

        # ------------------------------------------
        # Multi-Command Detection
        # ------------------------------------------
        #
        # IMPORTANT:
        # Do not show a generic thinking state before we know
        # whether this is an automation command or a Gemini chat.
        # A generic state could reuse the previous AI mode and briefly
        # display thinking_ai.png for an automation command.
        # ------------------------------------------

        is_multi_command = False

        if (
            self.multi_command_planner
            and
            self.multi_command_executor
        ):

            try:

                is_multi_command = (
                    self.multi_command_planner
                    .is_multi_command(
                        text
                    )
                )

            except Exception as error:

                print(
                    f"Multi-Command Detection Error : {error}"
                )

                is_multi_command = False

        if is_multi_command and not code_agent_requested:

            print(
                "\n========== MULTI COMMAND =========="
            )

            print(
                f"Command : {text}"
            )

            # Multi-command execution is a desktop automation flow.
            self._thinking_avatar_mode = (
                "thinking_laptop"
            )

            self._set_avatar_state(
                "thinking_laptop"
            )

            try:

                self.status_label.setText(
                    "Status : Planning..."
                )

                self.mic_widget.update_ai_message(
                    "Planning your command..."
                )

                try:

                    self.left_panel.set_listening(
                        "Idle"
                    )

                    self._set_thinking_state(
                        "Planning",
                        avatar_state="thinking_laptop",
                    )

                    self.left_panel.set_speaking(
                        "Silent"
                    )

                except Exception:

                    pass

                # ----------------------------------
                # Create Action Plan
                # ----------------------------------

                plan = (
                    self.multi_command_planner
                    .create_plan(
                        text
                    )
                )

                print(
                    "\n---------- ACTION PLAN ----------"
                )

                print(
                    self.multi_command_planner
                    .plan_to_json(
                        plan
                    )
                )

                print(
                    "---------------------------------\n"
                )

                # ----------------------------------
                # Execute Action Plan
                # ----------------------------------

                self.status_label.setText(
                    "Status : Executing..."
                )

                result = (
                    self.multi_command_executor
                    .execute(
                        plan
                    )
                )

                print(
                    "\n---------- EXECUTION RESULT ----------"
                )

                print(
                    result
                )

                print(
                    "--------------------------------------\n"
                )

                # ----------------------------------
                # Success
                # ----------------------------------

                if result.get(
                    "success",
                    False
                ):

                    completed_steps = result.get(
                        "completed_steps",
                        0
                    )

                    total_steps = result.get(
                        "total_steps",
                        plan.total_steps
                    )

                    reply = (
                        f"Completed all "
                        f"{completed_steps} "
                        f"steps successfully."
                    )

                    self.mic_widget.update_ai_message(
                        reply
                    )

                    self.status_label.setText(
                        "Status : Multi-Command Completed"
                    )

                    self.conversation_label.setText(
                        f"Multi-Command Completed\n\n"
                        f"{text}\n\n"
                        f"Steps : "
                        f"{completed_steps}/{total_steps}"
                    )

                    try:

                        self.left_panel.set_listening(
                            "Idle"
                        )

                        self._set_thinking_state(
                            "Inactive"
                        )

                        self.left_panel.set_speaking(
                            "Speaking"
                        )

                        self.right_panel.update_system_metrics()

                    except Exception:

                        pass

                    self._set_avatar_state("success")

                    self.tts.speak(
                        reply
                    )

                    self._unlock_after_speech(
                        restart_wake=True,
                        terminal_avatar_state="success"
                    )

                    QTimer.singleShot(
                        1400,
                        lambda: (
                            self.left_panel
                            .set_speaking(
                                "Silent"
                            )
                        )
                    )

                    # _unlock_after_speech() owns microphone
                    # unlock + wake-word restart.

                    return

                # ----------------------------------
                # Multi-command Failed
                # ----------------------------------

                failed_step = result.get(
                    "failed_step"
                )

                if failed_step:

                    failed_action = failed_step.get(
                        "action",
                        "unknown action"
                    )

                    failure_message = (
                        f"I completed "
                        f"{result.get('completed_steps', 0)} "
                        f"step(s), but failed at "
                        f"{failed_action}."
                    )

                else:

                    failure_message = (
                        "I could not complete "
                        "the multi-step command."
                    )

                self.mic_widget.update_ai_message(
                    failure_message
                )

                self.status_label.setText(
                    "Status : Multi-Command Failed"
                )

                self.conversation_label.setText(
                    f"Multi-Command Failed\n\n"
                    f"{text}\n\n"
                    f"{result.get('status', '')}"
                )

                try:

                    self.left_panel.set_listening(
                        "Idle"
                    )

                    self._set_thinking_state(
                        "Inactive"
                    )

                    self.left_panel.set_speaking(
                        "Speaking"
                    )

                except Exception:

                    pass

                self._set_avatar_state("error")

                self.tts.speak(
                    failure_message
                )

                self._unlock_after_speech(
                    restart_wake=True,
                    terminal_avatar_state="error"
                )

                QTimer.singleShot(
                    1400,
                    lambda: (
                        self.left_panel
                        .set_speaking(
                            "Silent"
                        )
                    )
                )

                return

            except Exception as error:

                print(
                    "\nMulti-Command Error :",
                    error
                )

                error_message = (
                    "I could not plan or "
                    "execute that multi-step command."
                )

                self.mic_widget.update_ai_message(
                    error_message
                )

                self.status_label.setText(
                    "Status : Multi-Command Error"
                )

                try:

                    self.left_panel.set_listening(
                        "Idle"
                    )

                    self._set_thinking_state(
                        "Inactive"
                    )

                    self.left_panel.set_speaking(
                        "Speaking"
                    )

                except Exception:

                    pass

                self._set_avatar_state("error")

                self.tts.speak(
                    error_message
                )

                self._unlock_after_speech(
                    restart_wake=True,
                    terminal_avatar_state="error"
                )

                return

        # ------------------------------------------
        # Detect Intent
        # ------------------------------------------

        intent = self._detect_intent_with_context(
            text
        )

        # Final routing protection: explicit Python/Java programming
        # requests must never fall through to the Gemini ai_chat branch.
        if self._is_code_agent_request(text):
            if intent != "code_agent":
                print(
                    "IntentDetector returned "
                    f"{intent!r}; overriding to code_agent."
                )
            intent = "code_agent"

        # ------------------------------------------
        # Avatar Thinking Mode
        # ------------------------------------------
        # Decide only after intent detection so the image matches
        # the real command route. ai_chat -> Gemini/AI, everything
        # else -> local/desktop automation.
        thinking_avatar = (
            self._set_thinking_avatar_for_intent(
                intent
            )
        )

        try:

            self.left_panel.set_listening(
                "Idle"
            )

            self._set_thinking_state(
                "Thinking",
                avatar_state=thinking_avatar,
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:
            pass

        # ------------------------------------------
        # Typing Mode
        # ------------------------------------------

        if (

            intent == "type_text"

            and

            self.typing_mode

        ):

            self.keyboard_controller.type_text(
                text
            )

            self._set_avatar_state("success")

            self.tts.speak(
                "Typed successfully."
            )

            self._unlock_after_speech(
                restart_wake=True,
                terminal_avatar_state="success"
            )

            self.status_label.setText(
                "Status : Typed"
            )

            self.mic_widget.update_ai_message(
                "Typed successfully."
            )

            # ---------------------------------
            # Command completed
            # ---------------------------------
            # Keep the microphone locked until TTS finishes.
            # _unlock_after_speech() handles the unlock and
            # DHEEPTHI restart.

            try:

                self.left_panel.set_listening(
                    "Idle"
                )

                self._set_thinking_state(
                    "Inactive"
                )

                self.left_panel.set_speaking(
                    "Silent"
                )

            except Exception:

                pass

            return

        # ------------------------------------------
        # Unknown Command
        # ------------------------------------------

        if intent == "ai_chat":

            # Voice and typed chat share the same persistent
            # self.gemini instance. Preserve the complete recognized
            # message so follow-up/context meaning is not lost.
            conversation_message = str(
                text or ""
            ).strip()

            if not conversation_message:

                self._unlock_after_speech(
                    restart_wake=True
                )

                return

            self.lock_microphone()

            try:
                ai_reply = self.gemini.generate_response(
                    conversation_message
                )

                if not ai_reply or not str(ai_reply).strip():
                    raise RuntimeError("Gemini returned an empty response")

                ai_reply = str(ai_reply).strip()

                self.mic_widget.update_ai_message(
                    ai_reply
                )

                try:
                    self._set_thinking_state("Inactive")
                    self.left_panel.set_speaking("Speaking")
                except Exception:
                    pass

                # AI / Gemini response flow:
                #
                # thinking_ai
                #       ↓
                # speaking
                #       ↓
                # TTS completes
                #       ↓
                # success
                #       ↓
                # AvatarWidget automatically returns to idle
                self._set_avatar_state("speaking")

                self.tts.speak(ai_reply)

                self._unlock_after_speech(
                    restart_wake=True,
                    terminal_avatar_state="success"
                )

                self.status_label.setText(
                    "Status : Gemini AI Completed"
                )

            except Exception as error:

                print(f"Gemini Command Error : {error}")

                error_message = (
                    "Sorry, I could not understand or complete that request."
                )

                self.mic_widget.update_ai_message(error_message)
                self.status_label.setText("Status : Gemini AI Error")
                self.conversation_label.setText(
                    f"Gemini Command Failed\n\n{text}"
                )

                try:
                    self._set_thinking_state("Inactive")
                    self.left_panel.set_speaking("Speaking")
                except Exception:
                    pass

                # Keep the avatar in SPEAKING state while the
                # AI error reply is being spoken. The terminal ERROR
                # state is applied after TTS completion.
                self._set_avatar_state("speaking")

                try:
                    self.tts.speak(error_message)
                except Exception:
                    pass

                self._unlock_after_speech(
                    restart_wake=True,
                    terminal_avatar_state="error"
                )

            QTimer.singleShot(
                1400,
                lambda: self.left_panel.set_speaking("Silent")
            )

            return

        # ---------------------------------
        # System Automation Commands
        # ---------------------------------

        if intent in {

            "set_volume",

            "set_brightness"

        }:

            entity = self.entity_extractor.extract_percentage(
                text
            )

        elif intent in {

            "volume_up",

            "volume_down",

            "mute",

            "lock_screen",

            "take_screenshot",

            "open_task_manager",

            "open_file_explorer",

            "brightness_up",

            "brightness_down",

            "shutdown",

            "restart",

            "sleep",

            "sign_out",

            "open_settings",

            "open_cmd",

            "open_powershell",

            "open_control_panel",

            "open_camera",

            "capture_photo",

            "start_screen_recording",

            "stop_screen_recording"

        }:

            entity = None

        # ---------------------------------
        # File Commands
        # ---------------------------------

        elif intent in {

            "open_file",

            "create_file",

            "delete_file"

        }:

            entity = self.entity_extractor.extract_file_query(
                text
            )

        elif intent == "compress_file":

            entity = self.entity_extractor.extract_compress_file(
                text
            )

        elif intent == "extract_zip":

            entity = self.entity_extractor.extract_extract_zip(
                text
            )

        elif intent == "rename_file":

            entity = self.entity_extractor.extract_rename_file(
                text
            )

        elif intent == "copy_file":

            entity = self.entity_extractor.extract_copy_file(
                text
            )

        elif intent == "move_file":

            entity = self.entity_extractor.extract_move_file(
                text
            )

        elif intent == "search_extension":

            entity = self.entity_extractor.extract_search_extension(
                text
            )

        elif intent == "search_size":

            entity = self.entity_extractor.extract_search_size(
                text
            )

        elif intent == "search_date":

            entity = self.entity_extractor.extract_search_date(
                text
            )

        # ---------------------------------
        # Browser Commands
        # ---------------------------------

        elif intent in {

            "launch_application",

            "create_word_document",

            "create_excel_workbook",

            "create_powerpoint_presentation",

            "open_website",

            "open_google",

            "open_youtube",

            "google_search",

            "youtube_search",

            "play_youtube",

            "new_tab",

            "close_tab",

            "next_tab",

            "previous_tab",

            "refresh",

            "browser_downloads",

            "browser_history",

            "browser_bookmarks",

            "bookmark_page",

            "address_bar",

            "browser_back",

            "browser_forward",

            "private_window",

            "open_chrome_profile",

        }:

            if intent in {

                "launch_application",

                "create_word_document",

                "create_excel_workbook",

                "create_powerpoint_presentation"

            }:

                entity = self.entity_extractor.extract_application(
                    text
                )

            elif intent == "open_website":

                entity = self.entity_extractor.extract_website(
                    text
                )

            elif intent == "open_google":

                entity = "google.com"

            elif intent == "open_youtube":

                entity = "youtube.com"

            elif intent == "google_search":

                entity = self.entity_extractor.extract_search_query(
                    text
                )

            elif intent == "youtube_search":

                entity = self.entity_extractor.extract_youtube_query(
                    text
                )

            elif intent == "play_youtube":

                entity = self.entity_extractor.extract_youtube_query(
                    text
                )

            else:

                entity = None

        # ---------------------------------
        # Folder Commands
        # ---------------------------------

        elif intent == "rename_folder":

            entity = self.entity_extractor.extract_rename_folder(
                text
            )

        elif intent == "copy_folder":

            entity = self.entity_extractor.extract_copy_folder(
                text
            )

        elif intent == "move_folder":

            entity = self.entity_extractor.extract_move_folder(
                text
            )

        elif intent in {

            "open_folder",

            "create_folder",

            "delete_folder",

        }:

            entity = self.entity_extractor.extract_folder(
                text
            )

        elif intent == "empty_recycle_bin":

            entity = None

        # ---------------------------------
        # Application Commands
        # ---------------------------------

        else:

            entity = self.entity_extractor.extract_application(
                text
            )

        # ---------------------------------
        # Extract Additional Information
        # ---------------------------------

        typed_text = self.text_extractor.extract_text(
            text
        )

        browser = self.entity_extractor.extract_browser(
            text
        )

        website = self.entity_extractor.extract_website(
            text
        )

        if intent == "google_search":

            search_query = self.entity_extractor.extract_search_query(
                text
            )

        elif intent in {

            "youtube_search",

            "play_youtube"

        }:

            search_query = self.entity_extractor.extract_youtube_query(
                text
            )

        else:

            search_query = None

        profile = self.entity_extractor.extract_profile(
            text
        )

        # ---------------------------------
        # Debug Information
        # ---------------------------------

        self.conversation_label.setText(

            f"You Said:\n\n{text}\n\n"

            f"Intent : {intent}\n"

            f"Entity : {entity}\n"

            f"Browser : {browser}\n"

            f"Website : {website}\n"

            f"Search Query : {search_query}\n"

            f"Profile : {profile}\n"

            f"Text : {typed_text}"

        )

        if getattr(settings, "DEBUG", False):

            print("\n========== DHEEPTHI ==========")

            print(f"Text    : {text}")

            print(f"Intent  : {intent}")

            print(f"Entity  : {entity}")

            print(f"Browser : {browser}")

            print(f"Website : {website}")

            print(f"Search  : {search_query}")

            print(f"Profile : {profile}")

            print(f"Typing  : {typed_text}")

            print("===========================\n")

        # ---------------------------------
        # Future Compound Commands
        # ---------------------------------

        if (

            intent == "launch_application"

            and

            typed_text

        ):

            print(

                "Compound Command Detected."

            )

        self.status_label.setText(
            "Status : Executing..."
        )

        try:

            # Still processing command
            self.left_panel.set_listening(
                "Idle"
            )

            self._set_thinking_state(
                "Thinking"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:

            pass

        # ---------------------------------
        # Execute Command
        # ---------------------------------

        self._code_agent_processing = (
            intent == "code_agent"
            or intent == "generate_code"
            or intent == "write_code"
            or intent == "create_code"
            or intent == "programming"
        )

        result = self.dispatcher.dispatch(

            intent=intent,

            entity=entity,

            typed_text=typed_text,

            browser=browser,

            website=website,

            search_query=search_query,

            profile=profile,

            user_text=text

        )
        # ---------------------------------
        # Handle Dispatcher Result
        # ---------------------------------

        self._handle_dispatch_result(
            result,
            text,
            intent,
            entity,
        )

    # --------------------------------------------------
    # Position File Selection Panel
    # --------------------------------------------------

    def _position_file_selection_panel(self):
        """
        Position the File/Folder Selection Panel at the
        bottom-center, directly above the ACTUAL microphone
        button.

        IMPORTANT:
            - MicWidget is NOT moved.
            - MicWidget size is NOT changed.
            - User message area is NOT changed.
            - ASTRA response area is NOT changed.
            - Only the floating file-selection panel is moved.
            - The panel follows the real microphone button,
            not the large MicWidget container.
        """

        panel = getattr(
            self,
            "file_selection_panel",
            None
        )

        mic_button = getattr(
            self,
            "microphone_button",
            None
        )

        center = getattr(
            self,
            "center_container",
            None
        )

        if (
            panel is None
            or mic_button is None
            or center is None
        ):
            return

        try:

            # --------------------------------------------------
            # Panel must be visible
            # --------------------------------------------------

            if not panel.isVisible():
                return

            # --------------------------------------------------
            # Make sure layouts are updated first.
            # --------------------------------------------------

            layout = center.layout()

            if layout is not None:
                layout.activate()

            QApplication.processEvents()

            # --------------------------------------------------
            # Panel Width
            # --------------------------------------------------

            available_width = center.width()

            panel_width = min(
                700,
                max(
                    500,
                    available_width - 30
                )
            )

            panel.setFixedWidth(
                panel_width
            )

            # --------------------------------------------------
            # Recalculate panel height.
            # --------------------------------------------------

            panel.adjustSize()

            QApplication.processEvents()

            # --------------------------------------------------
            # ACTUAL MICROPHONE BUTTON POSITION
            #
            # IMPORTANT:
            #
            # Do NOT use:
            #
            #     self.mic_widget.height()
            #
            # because MicWidget contains the complete
            # left / center / right conversation area.
            #
            # Instead use the real microphone button.
            # --------------------------------------------------

            mic_top_left = mic_button.mapTo(
                center,
                QPoint(0, 0)
            )

            mic_x = mic_top_left.x()

            mic_y = mic_top_left.y()

            mic_width = mic_button.width()

            # --------------------------------------------------
            # Center panel relative to ACTUAL microphone.
            #
            # This also keeps the panel aligned with the mic
            # if the internal 3-column microphone area changes.
            # --------------------------------------------------

            x = (
                mic_x
                + (mic_width - panel.width()) // 2
            )

            # --------------------------------------------------
            # Small visual gap.
            #
            # Panel:
            #
            #   ┌──────────────────────┐
            #   │ File Selection       │
            #   └──────────────────────┘
            #
            #              6 px
            #
            #              🎤
            #
            # --------------------------------------------------

            gap = 6

            y = (
                mic_y
                - panel.height()
                - gap
            )

            # --------------------------------------------------
            # Horizontal safety boundary
            # --------------------------------------------------

            x = max(
                8,
                min(
                    x,
                    center.width()
                    - panel.width()
                    - 8
                )
            )

            # --------------------------------------------------
            # Vertical safety boundary
            # --------------------------------------------------

            y = max(
                8,
                y
            )

            # --------------------------------------------------
            # Final geometry
            #
            # ONLY THE FILE PANEL MOVES.
            # --------------------------------------------------

            panel.setGeometry(
                x,
                y,
                panel.width(),
                panel.height()
            )

            # --------------------------------------------------
            # Keep panel above background/avatar layer.
            # --------------------------------------------------

            panel.raise_()

            panel.update()

        except RuntimeError:

            # Qt object may already be closing/deleted.
            return

        except Exception as error:

            print(
                f"File Selection Position Error : {error}"
            )

    # --------------------------------------------------
    # File Selection UI
    # --------------------------------------------------

    def show_file_selection(
        self,
        candidates,
        operation="file"
    ):
        """
        Show file/folder candidates in the glassmorphism
        FileSelectionPanel.

        The panel floats directly above the microphone
        without changing the microphone, halo, or avatar
        layout position.
        """

        if not candidates:
            return

        self._file_selection_candidates = list(
            candidates
        )

        self._file_selection_operation = (
            operation or "file"
        )

        try:

            # --------------------------------------------------
            # Prepare panel content
            # --------------------------------------------------

            self.file_selection_panel.show_candidates(
                candidates,
                operation=operation
            )

            # --------------------------------------------------
            # Main UI status
            # --------------------------------------------------

            self.status_label.setText(
                f"Status : Select {operation.title()}"
            )

            # --------------------------------------------------
            # Short AI message beside microphone
            # --------------------------------------------------

            message = (
                f"I found {len(candidates)} matching "
                f"{operation}s. Please say the number you want."
            )

            self.mic_widget.update_ai_message(
                message
            )

            # --------------------------------------------------
            # Keep conversation area clean.
            # Full file paths remain ONLY inside the panel.
            # --------------------------------------------------

            self.conversation_label.setText(
                f"{operation.title()} Selection\n\n"
                f"{len(candidates)} matching items found.\n\n"
                "Choose a number from the panel."
            )

            # --------------------------------------------------
            # Left status cards
            # --------------------------------------------------

            try:

                self.left_panel.set_listening(
                    "Waiting for File Number"
                )

                self._set_thinking_state(
                    "Select a File"
                )

                self.left_panel.set_speaking(
                    "Silent"
                )

            except Exception:
                pass

            # --------------------------------------------------
            # Show panel
            # --------------------------------------------------

            self.file_selection_panel.show()

            # --------------------------------------------------
            # Let Qt calculate the panel's final size.
            # --------------------------------------------------

            QApplication.processEvents()

            self.file_selection_panel.adjustSize()

            QApplication.processEvents()

            # --------------------------------------------------
            # Position panel relative to microphone.
            #
            # IMPORTANT:
            # Use delayed positioning because the microphone
            # geometry may finish updating only after this
            # event loop pass.
            # --------------------------------------------------

            QTimer.singleShot(
                0,
                self._position_file_selection_panel
            )

            # --------------------------------------------------
            # Second positioning pass.
            #
            # This handles final layout/paint geometry and
            # keeps the panel locked to the microphone.
            # --------------------------------------------------

            QTimer.singleShot(
                80,
                self._position_file_selection_panel
            )

            self.file_selection_panel.raise_()

            self.file_selection_panel.update()

            self.center_container.update()

            self.update()

        except Exception as error:

            print(
                f"File Selection Panel Error : {error}"
            )

    def clear_file_selection(self):
        """
        Clear the current filesystem selection state
        and hide the glass selection panel.
        """

        self._file_selection_candidates = []

        self._file_selection_operation = None

        # --------------------------------------------------
        # Hide the dedicated file/folder selection UI
        # --------------------------------------------------

        try:

            self.file_selection_panel.hide_panel()

        except Exception as error:

            print(
                f"File Selection Panel Hide Error : {error}"
            )

    # --------------------------------------------------
    # File Selection Button Click
    # --------------------------------------------------

    def _on_file_selection_clicked(
        self,
        selection_index
    ):
        """
        Handle a direct UI selection.

        Example:
            User clicks option 2
            -> selection_index = 2
            -> same pending voice command is resumed
            -> no second intent detection
        """

        if self._closing:
            return

        if not self._pending_file_selection:
            return

        try:

            selection_index = int(
                selection_index
            )

        except (
            TypeError,
            ValueError
        ):

            return

        print(
            f"File Selection UI Choice : {selection_index}"
        )

        # --------------------------------------------------
        # Reuse the SAME pending-command selection flow
        # --------------------------------------------------

        self._handle_pending_file_selection(
            str(selection_index)
        )


    # --------------------------------------------------
    # File Selection Cancel
    # --------------------------------------------------

    def _on_file_selection_cancelled(
        self
    ):
        """
        Cancel the currently pending file/folder selection.
        """

        if self._closing:
            return

        if not self._pending_file_selection:
            return

        print(
            "File Selection UI Cancelled."
        )

        self._pending_file_selection = None

        self.clear_file_selection()

        self.status_label.setText(
            "Status : File Selection Cancelled"
        )

        self.mic_widget.update_ai_message(
            "File selection cancelled."
        )

        self.conversation_label.setText(
            "File Selection Cancelled"
        )

        try:

            self.left_panel.set_listening(
                "Idle"
            )

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Speaking"
            )

        except Exception:
            pass

        try:

            self.tts.speak(
                "File selection cancelled."
            )

        except Exception:
            pass

        self._unlock_after_speech(
            restart_wake=True
        )

    # --------------------------------------------------
    # Start Initialization
    # --------------------------------------------------

    def start_initialization(self):
        """Start background initialization after backend readiness."""

        if self._closing or not self._backend_ready:
            return

        if self._backend_initialization_started:
            return

        self._backend_initialization_started = True

        self.status_label.setText(
            "Status : Initializing..."
        )

        self.microphone_button.setEnabled(False)

        self.loading_bar.setValue(0)

        self.loading_percent.setText("0%")

        self.loading_status.setText(
            "Starting DHEEPTHI-AI..."
        )

        self.worker = InitializationWorker(
            recognizer=self.recognizer
        )

        self.worker.status_changed.connect(
            self.update_initialization_status
        )

        self.worker.progress_changed.connect(
            self.update_loading_progress
        )

        self.worker.finished_success.connect(
            self.initialization_completed
        )

        self.worker.finished_error.connect(
            self.initialization_failed
        )

        self.worker.start()

    # --------------------------------------------------
    # Update Initialization Status
    # --------------------------------------------------

    def update_initialization_status(
        self,
        message
    ):
        """
        Update loading status.
        """

        self.status_label.setText(
            f"Status : {message}"
        )

        self.loading_status.setText(
            message
        )

        try:

            self._set_thinking_state(
                message
            )

        except Exception:

            pass

    # --------------------------------------------------
    # Update Loading Progress
    # --------------------------------------------------

    def update_loading_progress(
        self,
        value
    ):
        """
        Smooth loading progress.
        """

        current = self.loading_bar.value()

        # Never move backwards

        if value < current:

            return

        self.progress_animation = QPropertyAnimation(

            self.loading_bar,

            b"value"

        )

        self.progress_animation.setStartValue(
            current
        )

        self.progress_animation.setEndValue(
            value
        )

        self.progress_animation.setDuration(

            max(
                250,
                (value - current) * 18
            )

        )

        self.progress_animation.setEasingCurve(

            QEasingCurve.Linear

        )

        self.progress_animation.valueChanged.connect(

            lambda v: self.loading_percent.setText(

                f"{int(v)}%"

            )

        )

        self.progress_animation.start()

    # --------------------------------------------------
    # Initialization Completed
    # --------------------------------------------------

    def initialization_completed(self):
        """
        Called when initialization finishes.
        UI will open ONLY after progress reaches 100%.
        """

        self.status_label.setText(
            "Status : Ready"
        )

        self.loading_status.setText(
            "Initialization Complete"
        )

        # Already completed?
        if self.loading_finished:
            return

        self.loading_finished = True

        # Wait until animation reaches 100%

        def wait_for_completion():

            if self.loading_bar.value() >= 100:

                self.finish_loading_animation()

            else:

                QTimer.singleShot(
                    30,
                    wait_for_completion
                )

        wait_for_completion()

    # --------------------------------------------------
    # Finish Loading Animation
    # --------------------------------------------------

    def finish_loading_animation(self):
        """
        Remove loading overlay safely.

        The overlay is detached from MainWindow before
        deleteLater() so resizeEvent() can never access
        a QWidget that has already been deleted.
        """

        overlay = getattr(
            self,
            "loading_overlay",
            None
        )

        if overlay is None:
            self.enable_main_ui()
            return

        try:

            if not overlay.isVisible():
                self.loading_overlay = None
                self.enable_main_ui()
                return

        except RuntimeError:

            # Qt object has already been deleted.
            self.loading_overlay = None
            self.enable_main_ui()
            return

        fade = QPropertyAnimation(
            self.overlay_opacity,
            b"opacity"
        )

        fade.setDuration(350)

        fade.setStartValue(1.0)

        fade.setEndValue(0.0)

        fade.setEasingCurve(
            QEasingCurve.OutCubic
        )

        def remove_overlay():

            try:
                overlay.hide()

            except RuntimeError:
                pass

            # IMPORTANT:
            # Remove the Python reference BEFORE deleteLater().
            # This prevents resizeEvent() from touching the
            # deleted QWidget.

            self.loading_overlay = None

            try:
                overlay.deleteLater()

            except RuntimeError:
                pass

            self.enable_main_ui()

        fade.finished.connect(
            remove_overlay
        )

        fade.start()

        self.fade_animation = fade

    # --------------------------------------------------
    # Start Live File Monitor
    # --------------------------------------------------

    def start_file_monitor(self):
        """
        Start live file and folder monitoring.

        The monitor keeps the SQLite file index
        synchronized while ASTRA is running.

        This method is intentionally idempotent:
        repeated calls must never create a second
        watchdog observer.
        """

        # ----------------------------------
        # Prevent Duplicate Monitor
        # ----------------------------------

        existing_monitor = self.file_monitor

        if existing_monitor is not None:

            try:

                if existing_monitor.running:

                    print(
                        "Live File Monitor already running."
                    )

                    return

            except Exception:

                pass

            # A stale monitor reference can remain after
            # a failed startup. Close it before replacing it.

            try:

                existing_monitor.close()

            except Exception:

                pass

            self.file_monitor = None

        try:

            monitor = FileMonitor()

            monitor.start()

            # Store the reference only after startup so the
            # MainWindow remains the owner of the live monitor.
            self.file_monitor = monitor

            if monitor.running:

                print(
                    "Live File Monitor Started."
                )

            else:

                print(
                    "Live File Monitor did not start."
                )

        except Exception as error:

            self.file_monitor = None

            print(
                f"File Monitor Start Error : {error}"
            )

    # --------------------------------------------------
    # Enable Main UI
    # --------------------------------------------------

    def enable_main_ui(self):
        """
        Enable ASTRA after loading and start the startup greeting.

        IMPORTANT: the startup greeting owns the microphone from the
        moment this method starts.  No later UI initialization code may
        re-enable the microphone until the greeting completion path calls
        ``unlock_microphone()``.
        """

        # ==================================================
        # STARTUP MIC LOCK — SET THE GATE FIRST
        # ==================================================
        self._startup_greeting_token += 1
        self._startup_greeting_active = True
        self._startup_greeting_finished = False
        self._startup_sequence_complete = False
        self._startup_tts_observed_speaking = False
        self._startup_greeting_started_at = None
        self._startup_tts_request_id = None

        try:
            self.lock_microphone()
            print(
                "[STARTUP] MIC LOCKED | enable_main_ui | "
                f"button_enabled={self.microphone_button.isEnabled()} | "
                f"processing_voice={self.processing_voice}"
            )
        except Exception as error:
            print(
                f"[STARTUP] MIC LOCK ERROR | enable_main_ui | {error}"
            )

        self.status_label.setText(
            "Status : Ready"
        )

        self.conversation_label.setText(
            "Welcome to DHEEPTHI-AI\n\n"
            "Click the microphone to start."
        )

        # Keep the MicWidget disabled.  Do NOT call set_enabled(True) here.
        try:
            self.microphone_button.setEnabled(False)
            self.microphone_button.setCursor(Qt.ForbiddenCursor)
            self.mic_widget.set_enabled(False)
            self.mic_widget.set_listening(False)
        except Exception as error:
            print(
                f"[STARTUP] MIC UI LOCK ERROR | {error}"
            )

        try:
            self.left_panel.set_listening(
                "Waiting for DHEEPTHI"
            )
            self._set_thinking_state(
                "Inactive"
            )
            self.left_panel.set_speaking(
                "Silent"
            )
        except Exception:
            pass

        print(
            "[STARTUP] Microphone is now LOCKED. "
            "Waiting for opening greeting."
        )

        QTimer.singleShot(
            300,
            self._play_startup_greeting
        )

        # ----------------------------------
        # Start Live File Monitor
        # ----------------------------------
        self.start_file_monitor()

        # ----------------------------------
        # DHEEPTHI is NOT started here.
        # _finish_startup_greeting() is the ONLY startup release point.
        # ----------------------------------

    def _set_thinking_state(
        self,
        status="Thinking",
        avatar_state=None,
    ):
        """
        Keep the left THINKING tile and center avatar synchronized.

        Automation commands use thinking_laptop.
        Gemini / AI chat uses thinking_ai.

        Inactive/initializing terminal states do not force a thinking
        avatar, preventing stale thinking images from replacing the
        current listening/speaking/success/error state.
        """

        if avatar_state:

            normalized_avatar = (
                str(avatar_state)
                .strip()
                .lower()
            )

            if normalized_avatar in {
                "thinking_ai",
                "thinking_laptop",
            }:

                self._thinking_avatar_mode = (
                    normalized_avatar
                )

        try:

            self.left_panel.set_thinking(
                status
            )

        except RuntimeError:

            return

        except Exception as error:

            print(
                f"Thinking panel state error: {error}"
            )

            return

        normalized_status = (
            str(status or "")
            .strip()
            .lower()
        )

        # These are non-active informational states.
        if normalized_status in {
            "",
            "inactive",
            "offline",
            "initializing",
            "idle",
            "silent",
        }:

            return

        # Active thinking/planning/processing state:
        # immediately update the center avatar as well.
        self._set_avatar_state(
            self._thinking_avatar_mode
        )

    def _set_avatar_state(
        self,
        state: str,
    ):
        """Safely update both CenterPanelWidget and AvatarWidget."""

        requested_state = str(
            state or ""
        ).strip().lower()

        state_map = {
            "hello": "hello",
            "idle": "idle",
            "listening": "listening",
            "thinking": "thinking_ai",
            "processing": "thinking_ai",
            "thinking_laptop": "thinking_laptop",
            "thinking_ai": "thinking_ai",
            "speaking": "speaking",
            "success": "success",
            "error": "error",
        }

        avatar_state = state_map.get(
            requested_state,
            "idle",
        )

        if avatar_state in {
            "thinking_ai",
            "thinking_laptop",
        }:

            self._thinking_avatar_mode = (
                avatar_state
            )

        center_panel = getattr(
            self,
            "center_panel",
            None,
        )

        # Prefer the CenterPanel API. It already owns and forwards
        # avatar state changes to the real AvatarWidget. Calling both
        # routes can restart temporary SUCCESS / ERROR timers twice.
        if center_panel is not None:

            try:

                if hasattr(
                    center_panel,
                    "set_avatar_state",
                ):

                    center_panel.set_avatar_state(
                        avatar_state
                    )

                    return

            except RuntimeError:

                return

            except Exception as error:

                print(
                    f"Center avatar state error: {error}"
                )

        # Compatibility fallback for layouts where the real
        # AvatarWidget is exposed directly on MainWindow.
        avatar_widget = getattr(
            self,
            "avatar_widget",
            None,
        )

        if avatar_widget is None and center_panel is not None:

            avatar_widget = getattr(
                center_panel,
                "avatar_widget",
                None,
            )

        if avatar_widget is None:

            return

        try:

            if hasattr(
                avatar_widget,
                "set_state",
            ):

                avatar_widget.set_state(
                    avatar_state
                )

            elif hasattr(
                avatar_widget,
                "set_avatar_state",
            ):

                avatar_widget.set_avatar_state(
                    avatar_state
                )

        except RuntimeError:

            return

        except Exception as error:

            print(
                f"Direct avatar state error: {error}"
            )

    def _set_thinking_avatar_for_intent(
        self,
        intent: str,
    ):
        """Select the correct thinking avatar for the recognized command."""

        normalized_intent = (
            str(intent or "")
            .strip()
            .lower()
        )

        # Gemini/free-form AI requests use the AI thinking image.
        if normalized_intent == "ai_chat":

            self._thinking_avatar_mode = (
                "thinking_ai"
            )

            self._set_avatar_state(
                "thinking_ai"
            )

            return "thinking_ai"

        # Every recognized desktop/file/folder/browser/system/application
        # command is processed as an automation command.
        self._thinking_avatar_mode = (
            "thinking_laptop"
        )

        self._set_avatar_state(
            "thinking_laptop"
        )

        return "thinking_laptop"

    def _play_startup_greeting(self):
        """
        Play exactly one random opening greeting while the microphone
        is locked.

        Strict lifecycle:

            MIC LOCK
                ↓
            HELLO avatar
                ↓
            TTS speech
                ↓
            TTS COMPLETE
                ↓
            HELLO -> IDLE
                ↓
            MIC UNLOCK
                ↓
            DHEEPTHI wake listener
        """

        if getattr(self, "_closing", False):
            return

        self._startup_greeting_token += 1

        self._startup_greeting_active = True
        self._startup_greeting_finished = False
        self._startup_sequence_complete = False
        self._startup_tts_observed_speaking = False
        self._startup_greeting_started_at = __import__("time").monotonic()
        self._startup_tts_request_id = None

        try:
            self.lock_microphone()

            print(
                "[STARTUP] MIC LOCKED | greeting started | "
                f"button_enabled={self.microphone_button.isEnabled()} | "
                f"processing_voice={self.processing_voice}"
            )

        except Exception as error:
            print(
                f"[STARTUP] MIC LOCK ERROR | {error}"
            )

        # --------------------------------------------------
        # HELLO avatar
        # --------------------------------------------------
        try:
            print("\n========== DHEEPTHI STARTUP GREETING ==========")

            center_panel = getattr(
                self,
                "center_panel",
                None,
            )

            if center_panel is not None:

                center_panel.show()

                mic_widget = getattr(
                    self,
                    "mic_widget",
                    None,
                )

                if mic_widget is not None:
                    mic_widget.raise_()

                center_panel.set_avatar_state(
                    "hello"
                )

                print(
                    "[STARTUP] HELLO avatar displayed."
                )

            else:
                print(
                    "[STARTUP] CenterPanel not found."
                )

        except Exception as error:
            print(
                f"[STARTUP] Avatar error | {error}"
            )

        # --------------------------------------------------
        # TTS
        # --------------------------------------------------
        tts = getattr(
            self,
            "tts",
            None,
        )

        if tts is None:

            print(
                "[STARTUP] TTS unavailable. "
                "Finishing greeting safely."
            )

            self._finish_startup_greeting()
            return

        startup_greeting = random.choice(
            OPEN_GREETINGS
        )

        print(
            f"[STARTUP] Selected greeting : {startup_greeting}"
        )

        # --------------------------------------------------
        # Connect speech_started.
        # --------------------------------------------------
        speech_started_signal = getattr(
            tts,
            "speech_started",
            None,
        )

        if (
            speech_started_signal is not None
            and hasattr(
                speech_started_signal,
                "connect",
            )
            and not self._startup_tts_started_signal_connected
        ):

            try:

                speech_started_signal.connect(
                    self._on_startup_tts_started
                )

                self._startup_tts_started_signal_connected = True

                print(
                    "[STARTUP] TTS speech_started signal CONNECTED."
                )

            except Exception as error:

                print(
                    "[STARTUP] TTS speech_started connection FAILED | "
                    f"{error}"
                )

                self._startup_tts_started_signal_connected = False

        # --------------------------------------------------
        # Connect speech_finished.
        # --------------------------------------------------
        speech_finished_signal = getattr(
            tts,
            "speech_finished",
            None,
        )

        if (
            speech_finished_signal is not None
            and hasattr(
                speech_finished_signal,
                "connect",
            )
            and not self._startup_tts_signal_connected
        ):

            try:

                speech_finished_signal.connect(
                    self._on_startup_tts_finished
                )

                self._startup_tts_signal_connected = True

                print(
                    "[STARTUP] TTS speech_finished signal CONNECTED."
                )

            except Exception as error:

                print(
                    "[STARTUP] TTS speech_finished connection FAILED | "
                    f"{error}"
                )

                self._startup_tts_signal_connected = False

        # --------------------------------------------------
        # Start exactly one greeting.
        # --------------------------------------------------
        try:

            result = tts.speak(
                startup_greeting
            )

            try:
                self._startup_tts_request_id = getattr(
                    tts,
                    "_request_id",
                    None,
                )
            except Exception:
                self._startup_tts_request_id = None

            print(
                "[STARTUP] Greeting TTS STARTED | "
                f"result={'started' if result is not None else 'accepted'} | "
                f"tts_request_id={self._startup_tts_request_id}"
            )

        except Exception as error:

            print(
                f"[STARTUP] Greeting TTS ERROR | {error}"
            )

            self._finish_startup_greeting()
            return

        # --------------------------------------------------
        # Poll actual speaking state as a backup.
        # --------------------------------------------------
        old_timer = getattr(
            self,
            "_startup_poll_timer",
            None,
        )

        if old_timer is not None:

            try:
                old_timer.stop()
                old_timer.deleteLater()
            except Exception:
                pass

        self._startup_poll_timer = QTimer(
            self
        )

        self._startup_poll_timer.setInterval(
            75
        )

        self._startup_poll_timer.timeout.connect(
            self._wait_for_startup_greeting
        )

        self._startup_poll_timer.start()

        # --------------------------------------------------
        # Last-resort watchdog.
        # --------------------------------------------------
        old_watchdog = getattr(
            self,
            "_startup_unlock_watchdog",
            None,
        )

        if old_watchdog is not None:

            try:
                old_watchdog.stop()
                old_watchdog.deleteLater()
            except Exception:
                pass

        self._startup_unlock_watchdog = QTimer(
            self
        )

        self._startup_unlock_watchdog.setSingleShot(
            True
        )

        self._startup_unlock_watchdog.timeout.connect(
            self._startup_unlock_watchdog_timeout
        )

        self._startup_unlock_watchdog.start(
            self._startup_unlock_watchdog_ms
        )

        print(
            "[STARTUP] MIC LOCK ACTIVE | "
            "waiting for actual greeting completion."
        )

    @Slot(str)
    def _on_startup_tts_started(
        self,
        text,
    ):
        """
        Mark the startup TTS request as actually started.

        This never unlocks the microphone.
        """

        if getattr(
            self,
            "_closing",
            False,
        ):
            return

        if not getattr(
            self,
            "_startup_greeting_active",
            False,
        ):
            return

        if getattr(
            self,
            "_startup_greeting_finished",
            False,
        ):
            return

        self._startup_tts_observed_speaking = True

        print(
            "[STARTUP] TTS speech_started RECEIVED."
        )

    def _on_startup_tts_finished(
        self,
        success=True,
    ):
        """
        Handle the startup TTS completion signal.

        A completion signal never unlocks the mic while the TTS manager
        still reports active speech.
        """

        if getattr(
            self,
            "_closing",
            False,
        ):
            return

        if not getattr(
            self,
            "_startup_greeting_active",
            False,
        ):
            return

        if getattr(
            self,
            "_startup_greeting_finished",
            False,
        ):
            return

        print(
            "[STARTUP] TTS speech_finished RECEIVED | "
            f"success={bool(success)}"
        )

        try:

            if (
                self.tts is not None
                and self.tts.speaking()
            ):

                self._startup_tts_observed_speaking = True

                print(
                    "[STARTUP] Completion signal received, but TTS "
                    "still reports speaking=True. Waiting."
                )

                return

        except Exception:
            pass

        self._finish_startup_greeting()

    def _wait_for_startup_greeting(self):
        """
        Poll the real TTS state.

        This is the fallback path when a provider does not emit
        ``speech_finished`` reliably.
        """

        if getattr(
            self,
            "_closing",
            False,
        ):
            return

        if not getattr(
            self,
            "_startup_greeting_active",
            False,
        ):
            return

        if getattr(
            self,
            "_startup_greeting_finished",
            False,
        ):
            return

        tts = getattr(
            self,
            "tts",
            None,
        )

        if tts is None:

            self._finish_startup_greeting()
            return

        try:

            speaking_method = getattr(
                tts,
                "speaking",
                None,
            )

            if not callable(
                speaking_method
            ):
                return

            speaking = bool(
                speaking_method()
            )

        except Exception as error:

            print(
                "[STARTUP] TTS speaking-state check ERROR | "
                f"{error}"
            )

            return

        if speaking:

            if not self._startup_tts_observed_speaking:

                print(
                    "[STARTUP] TTS speaking=True | "
                    "greeting is ACTIVE."
                )

            self._startup_tts_observed_speaking = True
            return

        # --------------------------------------------------
        # speaking=False after actual speech was observed.
        # --------------------------------------------------
        if self._startup_tts_observed_speaking:

            print(
                "[STARTUP] TTS speaking=False | "
                "greeting COMPLETED."
            )

            self._finish_startup_greeting()
            return

        # --------------------------------------------------
        # Provider did not expose speaking=True.
        # Do not unlock immediately; wait through the startup
        # race window first.
        # --------------------------------------------------
        started_at = (
            self._startup_greeting_started_at
        )

        if started_at is not None:

            elapsed_ms = (
                __import__("time").monotonic()
                - started_at
            ) * 1000.0

            if (
                elapsed_ms
                >= self._startup_min_fallback_wait_ms
            ):

                print(
                    "[STARTUP] TTS never exposed speaking=True after "
                    f"{int(elapsed_ms)} ms. "
                    "Using safe fallback completion."
                )

                self._finish_startup_greeting()

    def _startup_unlock_watchdog_timeout(self):
        """
        Last-resort recovery if the TTS provider never reports completion.
        """

        if not getattr(
            self,
            "_startup_greeting_active",
            False,
        ):
            return

        print(
            "[STARTUP] TTS watchdog TIMEOUT | "
            "forcing startup microphone unlock."
        )

        self._finish_startup_greeting()

    def _finish_startup_greeting(self):
        """
        Single authoritative startup completion point.

        The microphone is unlocked HERE and nowhere else in the startup
        sequence.
        """

        if getattr(
            self,
            "_shutdown_goodbye_started",
            False,
        ):
            return

        if getattr(
            self,
            "_startup_greeting_finished",
            False,
        ):
            return

        # Never unlock while TTS is still active.
        try:

            if (
                self.tts is not None
                and self.tts.speaking()
            ):

                self._startup_tts_observed_speaking = True

                QTimer.singleShot(
                    75,
                    self._wait_for_startup_greeting
                )

                return

        except Exception:
            pass

        self._startup_greeting_finished = True
        self._startup_greeting_active = False
        self._startup_sequence_complete = True

        # Stop startup timers.
        for timer_name in (
            "_startup_poll_timer",
            "_startup_unlock_watchdog",
        ):

            timer = getattr(
                self,
                timer_name,
                None,
            )

            if timer is not None:

                try:
                    timer.stop()
                    timer.deleteLater()
                except Exception:
                    pass

                setattr(
                    self,
                    timer_name,
                    None,
                )

        print(
            "\n========== STARTUP COMPLETE =========="
        )

        # --------------------------------------------------
        # HELLO -> IDLE
        # --------------------------------------------------
        center_panel = getattr(
            self,
            "center_panel",
            None,
        )

        try:

            if center_panel is not None:

                center_panel.show()

                center_panel.set_avatar_state(
                    "idle"
                )

                print(
                    "[STARTUP] HELLO state finished."
                )

                print(
                    "[STARTUP] idle_primary started."
                )

                print(
                    "[STARTUP] Idle slideshow is active."
                )

                mic_widget = getattr(
                    self,
                    "mic_widget",
                    None,
                )

                if mic_widget is not None:
                    mic_widget.raise_()

            else:

                print(
                    "[STARTUP] CenterPanel not available."
                )

        except Exception as error:

            print(
                f"[STARTUP] Avatar transition ERROR | {error}"
            )

        if getattr(
            self,
            "_closing",
            False,
        ):

            print(
                "[STARTUP] Closing requested; "
                "microphone remains LOCKED."
            )

            print(
                "======================================\n"
            )

            return

        # --------------------------------------------------
        # AUTHORITATIVE MICROPHONE UNLOCK
        # --------------------------------------------------
        try:

            self.processing_voice = False
            self.manual_listening_requested = False

            self.microphone_button.setEnabled(
                True
            )

            self.microphone_button.setCursor(
                Qt.PointingHandCursor
            )

            mic_widget = getattr(
                self,
                "mic_widget",
                None,
            )

            if mic_widget is not None:

                custom_enable = getattr(
                    mic_widget,
                    "set_enabled",
                    None,
                )

                if callable(
                    custom_enable
                ):

                    custom_enable(
                        True
                    )

                else:

                    mic_widget.setEnabled(
                        True
                    )

                set_listening = getattr(
                    mic_widget,
                    "set_listening",
                    None,
                )

                if callable(
                    set_listening
                ):

                    set_listening(
                        False
                    )

                mic_widget.update()

            QApplication.processEvents()

            print(
                "[MIC] UNLOCKED AFTER GREETING | "
                f"button_enabled={self.microphone_button.isEnabled()} | "
                f"mic_widget_enabled={mic_widget.isEnabled() if mic_widget is not None else 'N/A'} | "
                f"processing_voice={self.processing_voice} | "
                f"startup_active={self._startup_greeting_active}"
            )

        except Exception as error:

            print(
                f"[MIC] UNLOCK ERROR AFTER GREETING | {error}"
            )

        # Verify after the current Qt event-loop turn.
        QTimer.singleShot(
            0,
            self._verify_startup_microphone_unlocked
        )

        # Start DHEEPTHI only after the mic is explicitly enabled.
        if (
            getattr(
                self,
                "wake_word_enabled",
                False,
            )
            and not getattr(
                self,
                "manual_listening_requested",
                False,
            )
            and not getattr(
                self,
                "processing_voice",
                False,
            )
            and not getattr(
                self,
                "wake_word_running",
                False,
            )
            and not getattr(
                self,
                "_closing",
                False,
            )
        ):

            QTimer.singleShot(
                250,
                self._start_wake_word_after_startup
            )

            print(
                "[STARTUP] DHEEPTHI wake listener scheduled "
                "AFTER MIC UNLOCK."
            )

        else:

            print(
                "[STARTUP] DHEEPTHI not started: "
                "another voice mode or shutdown is active."
            )

        print(
            "======================================\n"
        )

    def _verify_startup_microphone_unlocked(self):
        """
        Verify and repair the microphone UI after startup greeting.

        This catches a stale QWidget/MicWidget enabled state without
        changing the normal command lifecycle.
        """

        if getattr(
            self,
            "_closing",
            False,
        ):
            return

        if not getattr(
            self,
            "_startup_sequence_complete",
            False,
        ):
            return

        if getattr(
            self,
            "_startup_greeting_active",
            False,
        ):
            return

        if getattr(
            self,
            "processing_voice",
            False,
        ):
            return

        try:
            button_enabled = bool(
                self.microphone_button.isEnabled()
            )
        except Exception:
            button_enabled = False

        try:
            mic_enabled = bool(
                self.mic_widget.isEnabled()
            )
        except Exception:
            mic_enabled = False

        print(
            "[STARTUP] MIC STATE VERIFY | "
            f"button_enabled={button_enabled} | "
            f"mic_widget_enabled={mic_enabled} | "
            f"processing_voice={self.processing_voice} | "
            f"startup_active={self._startup_greeting_active}"
        )

        if not button_enabled or not mic_enabled:

            print(
                "[STARTUP] MIC STATE VERIFY | "
                "repairing stale disabled microphone state."
            )

            try:
                self.unlock_microphone()
            except Exception as error:
                print(
                    f"[STARTUP] MIC VERIFY REPAIR ERROR | {error}"
                )

    def _start_wake_word_after_startup(self):
        """
        Start DHEEPTHI only after the startup greeting has completely
        finished AND the microphone UI has been explicitly released.
        """

        if getattr(
            self,
            "_closing",
            False,
        ):
            return

        if getattr(
            self,
            "_startup_greeting_active",
            False,
        ):

            print(
                "[STARTUP] Wake start BLOCKED: "
                "greeting still active."
            )

            return

        if not getattr(
            self,
            "_startup_sequence_complete",
            False,
        ):

            print(
                "[STARTUP] Wake start BLOCKED: "
                "startup sequence not complete."
            )

            return

        if not getattr(
            self,
            "wake_word_enabled",
            False,
        ):
            return

        if getattr(
            self,
            "manual_listening_requested",
            False,
        ):
            return

        if getattr(
            self,
            "processing_voice",
            False,
        ):
            return

        try:

            if not self.microphone_button.isEnabled():

                print(
                    "[STARTUP] Wake start BLOCKED: "
                    "microphone button is still disabled."
                )

                QTimer.singleShot(
                    100,
                    self._start_wake_word_after_startup
                )

                return

        except Exception:
            pass

        print(
            "[STARTUP] Startup gate OPEN | "
            "MIC is unlocked | starting DHEEPTHI."
        )

        self.start_wake_word_worker()

    # --------------------------------------------------
    # Initialization Failed
    # --------------------------------------------------

    def initialization_failed(
        self,
        error
    ):
        """
        Called when initialization fails.
        """

        self.status_label.setText(
            "Status : Initialization Failed"
        )

        self.loading_status.setText(
            "Initialization Failed"
        )

        self.microphone_button.setEnabled(False)

        self.conversation_label.setText(

            f"Initialization Error\n\n{error}"

        )

        try:

            self.left_panel.set_listening(
                "Offline"
            )

            self._set_thinking_state(
                "Error"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:

            pass

    # --------------------------------------------------
    # Lock Microphone
    # --------------------------------------------------

    def lock_microphone(
        self
    ):
        """
        Lock the microphone button while ASTRA
        is listening or processing a command.
        """

        self.processing_voice = True

        # ---------------------------------
        # Disable button
        # ---------------------------------

        self.microphone_button.setEnabled(
            False
        )

        # ---------------------------------
        # Explicit blocked cursor
        # ---------------------------------

        self.microphone_button.setCursor(
            Qt.ForbiddenCursor
        )

        # ---------------------------------
        # Keep MicWidget disabled state
        # ---------------------------------

        try:

            custom_disable = getattr(
                self.mic_widget,
                "set_enabled",
                None,
            )

            if callable(
                custom_disable
            ):

                custom_disable(
                    False
                )

            else:

                self.mic_widget.setEnabled(
                    False
                )

            self.mic_widget.set_listening(
                False
            )

        except Exception:

            try:
                self.mic_widget.setEnabled(False)
            except Exception:
                pass

        QApplication.processEvents()

        try:
            print(
                "[MIC] LOCKED | "
                f"button_enabled={self.microphone_button.isEnabled()} | "
                f"mic_widget_enabled={self.mic_widget.isEnabled()} | "
                f"processing_voice={self.processing_voice}"
            )
        except Exception:
            print("[MIC] LOCKED")


    # --------------------------------------------------
    # Unlock Microphone
    # --------------------------------------------------

    def unlock_microphone(
        self
    ):
        """
        Unlock the microphone UI.

        Both the actual QPushButton and MicWidget's custom enabled state
        are updated so they can never disagree.
        """

        if getattr(
            self,
            "_closing",
            False,
        ):
            return

        self.processing_voice = False

        try:

            self.microphone_button.setEnabled(
                True
            )

            self.microphone_button.setCursor(
                Qt.PointingHandCursor
            )

        except Exception as error:

            print(
                f"[MIC] Button unlock error | {error}"
            )

        try:

            mic_widget = getattr(
                self,
                "mic_widget",
                None,
            )

            if mic_widget is not None:

                custom_enable = getattr(
                    mic_widget,
                    "set_enabled",
                    None,
                )

                if callable(
                    custom_enable
                ):

                    custom_enable(
                        True
                    )

                else:

                    mic_widget.setEnabled(
                        True
                    )

                set_listening = getattr(
                    mic_widget,
                    "set_listening",
                    None,
                )

                if callable(
                    set_listening
                ):

                    set_listening(
                        False
                    )

                mic_widget.update()

        except Exception as error:

            print(
                f"[MIC] MicWidget unlock error | {error}"
            )

        QApplication.processEvents()

        try:

            print(
                "[MIC] UNLOCKED | "
                f"button_enabled={self.microphone_button.isEnabled()} | "
                f"mic_widget_enabled={self.mic_widget.isEnabled()} | "
                f"processing_voice={self.processing_voice}"
            )

        except Exception:

            print(
                "[MIC] UNLOCKED"
            )

    # --------------------------------------------------
    # Start Listening
    # --------------------------------------------------

    def start_listening(self):
        """
        Start manual voice recognition.

        Manual microphone lifecycle:

            Mic Click
                ↓
            Stop DHEEPTHI wake listener
                ↓
            Show "Listening" immediately
                ↓
            ASTRA says "Listening"
                ↓
            Wait until TTS finishes
                ↓
            Start the actual microphone listener
                ↓
            Capture one command
                ↓
            Disable microphone while ASTRA processes / speaks
                ↓
            Restart DHEEPTHI after the task is complete

        The GUI thread is never blocked waiting for the wake-word
        worker. This is important because blocking QThread.wait()
        from the Qt GUI thread can make the window appear as
        "Not Responding".
        """

        if self._closing:
            return

        # ---------------------------------
        # Startup greeting owns the microphone
        # ---------------------------------

        if getattr(
            self,
            "_startup_greeting_active",
            False
        ):

            print(
                "[MIC] Click ignored: startup greeting is active."
            )

            return

        # ---------------------------------
        # Already processing
        # ---------------------------------

        if self.processing_voice:
            return

        # ---------------------------------
        # Manual listening already requested
        # ---------------------------------

        if self.manual_listening_requested:
            return

        # ---------------------------------
        # Request Manual Mode
        # ---------------------------------

        self.manual_listening_requested = True
        self._wake_command_transition_active = False

        # Lock immediately so the user cannot start another
        # microphone action while the mode is switching.
        self.lock_microphone()

        # ---------------------------------
        # Update UI immediately
        # ---------------------------------
        # The user asked for the first manual click to show
        # "Listening", not "Preparing".
        #
        # The actual audio capture is still delayed until
        # ASTRA finishes saying "Listening", preventing Whisper
        # from capturing ASTRA's own voice.
        # ---------------------------------

        self.status_label.setText(
            "Status : Listening..."
        )

        # ---------------------------------
        # Avatar: switch immediately when
        # the microphone is clicked.
        # ---------------------------------

        self._set_avatar_state(
            "listening"
        )

        try:
            self.mic_widget.show_listening()

            self.mic_widget.set_listening(
                False
            )

            self.left_panel.set_listening(
                "Listening"
            )

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:
            pass

        QApplication.processEvents()

        # ---------------------------------
        # Stop DHEEPTHI Wake Worker
        # ---------------------------------
        # IMPORTANT:
        # Do NOT call voice_worker.wait() here.
        # The GUI must remain responsive.
        #
        # listening_finished() will continue the manual flow
        # after the wake worker has actually finished.
        # ---------------------------------

        if self.voice_worker is not None:

            try:

                if self.voice_worker.isRunning():

                    if self.current_voice_mode == "wake":

                        print(
                            "Stopping DHEEPTHI listener for manual microphone..."
                        )

                        try:
                            self.voice_worker.stop()

                        except Exception as error:
                            print(
                                f"Wake Worker Stop Error : {error}"
                            )

                        return

                    # Manual worker is already running.
                    self.manual_listening_requested = False
                    self.unlock_microphone()
                    return

            except Exception as error:

                print(
                    f"Voice Worker State Error : {error}"
                )

        # ---------------------------------
        # No wake worker is running.
        # Start the manual prompt now.
        # ---------------------------------

        self._begin_manual_listening_prompt()

    # --------------------------------------------------
    # Begin Manual Listening Prompt
    # --------------------------------------------------

    def _begin_manual_listening_prompt(self):
        """
        Start the manual-listening TTS prompt.

        This is called only after the wake-word worker has
        stopped, so ASTRA cannot speak while the wake listener
        still owns the microphone.
        """

        if self._closing:
            return

        if not self.manual_listening_requested:
            return

        # ---------------------------------
        # Safety: wake worker must be gone
        # ---------------------------------

        if self.voice_worker is not None:

            try:

                if self.voice_worker.isRunning():

                    return

            except Exception:
                pass

        # ---------------------------------
        # Keep the UI in Listening state
        # ---------------------------------

        self.status_label.setText(
            "Status : Listening..."
        )

        try:

            self.mic_widget.show_listening()

            self.mic_widget.set_listening(
                False
            )

            self.left_panel.set_listening(
                "Listening"
            )

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Speaking"
            )

        except Exception:
            pass

        # ---------------------------------
        # ASTRA Voice Prompt
        # ---------------------------------
        # Only the word "Listening" is used.
        # No "Sollunga" prompt is generated here.
        # ---------------------------------

        try:

            if self.tts is not None:

                self.tts.speak(
                    "Listening"
                )

        except Exception as error:

            print(
                f"Listening Prompt TTS Error : {error}"
            )

            # If TTS fails, start microphone directly.
            self._start_manual_listener_after_prompt()

            return

        # ---------------------------------
        # Wait asynchronously for TTS
        # ---------------------------------

        QTimer.singleShot(
            100,
            self._wait_for_manual_listening_prompt
        )

    # --------------------------------------------------
    # Wait For Manual Listening Prompt
    # --------------------------------------------------

    def _wait_for_manual_listening_prompt(self):
        """
        Wait asynchronously until ASTRA finishes saying
        "Listening".

        The microphone remains disabled at the backend while
        TTS is speaking. This prevents Whisper from hearing
        ASTRA's own voice.
        """

        if self._closing:
            return

        if not self.manual_listening_requested:
            return

        try:

            speaking = (
                self.tts is not None
                and self.tts.speaking()
            )

        except Exception:

            speaking = False

        if speaking:

            QTimer.singleShot(
                60,
                self._wait_for_manual_listening_prompt
            )

            return

        # ---------------------------------
        # TTS finished
        # ---------------------------------

        self._start_manual_listener_after_prompt()

    # --------------------------------------------------
    # Start Manual Listener After Prompt
    # --------------------------------------------------

    def _start_manual_listener_after_prompt(self):
        """
        Start the actual microphone listener only after
        ASTRA's "Listening" prompt has completely finished.
        """

        if self._closing:
            return

        if not self.manual_listening_requested:
            return

        # ---------------------------------
        # Safety: existing worker
        # ---------------------------------

        if self.voice_worker is not None:

            try:

                if self.voice_worker.isRunning():
                    return

            except Exception:
                pass

        # ---------------------------------
        # Update UI
        # ---------------------------------

        self.status_label.setText(
            "Status : Listening..."
        )

        # ---------------------------------
        # Avatar: keep LISTENING visible
        # during actual microphone capture.
        # ---------------------------------

        self._set_avatar_state(
            "listening"
        )

        try:

            self.mic_widget.show_listening()

            # Start a clean visual meter for every recording session.
            self.mic_widget.set_listening(
                True
            )

            self.mic_widget.update_audio_level(
                0.0
            )

            self.left_panel.set_listening(
                "Listening"
            )

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:
            pass

        QApplication.processEvents()

        # ---------------------------------
        # Start Manual Worker
        # ---------------------------------

        QTimer.singleShot(
            50,
            lambda: self.start_voice_worker(
                wake_word_mode=False
            )
        )

    def listening_finished(self):
        """
        Handle completion of both:

        1. Production DHEEPTHI wake-word listening
        2. Manual microphone listening

        IMPORTANT:
        This method never blocks the Qt GUI thread with
        QThread.wait(). The worker's finished signal already
        tells us that its run() method has returned.
        """

        finished_mode = self.current_voice_mode

        current_worker = self.voice_worker

        self.voice_worker = None

        self.current_voice_mode = None

        # ---------------------------------
        # Stop Audio UI
        # ---------------------------------

        try:

            self.mic_widget.update_audio_level(
                0.0
            )

            # Use the widget's public state API instead of touching
            # the private _listening attribute directly.
            self.mic_widget.set_listening(False)

        except Exception:
            pass

        # ---------------------------------
        # Non-blocking Worker Cleanup
        # ---------------------------------

        if current_worker:

            try:

                current_worker.deleteLater()

            except Exception as error:

                print(
                    f"Voice Worker Cleanup Error : {error}"
                )

        # ==================================================
        # MANUAL MICROPHONE MODE
        # ==================================================

        if finished_mode == "manual":

            print(
                "Manual microphone listening finished."
            )

            self.manual_listening_requested = False

            self.wake_word_running = False

            # --------------------------------------------------
            # Pending YES/NO confirmation
            # --------------------------------------------------
            # process_command() can receive the confirmation request
            # while the manual worker is still unwinding. Start the
            # confirmation listener only after this worker has fully
            # finished, otherwise two voice workers could overlap.

            # =================================================
            # Pending File Selection - FIRST PRIORITY
            # =================================================

            if self._pending_file_selection:

                print(
                    "Manual listening finished. "
                    "Pending file selection is active."
                )

                self.status_label.setText(
                    "Status : Waiting for File Selection"
                )

                try:

                    self.left_panel.set_listening(
                        "Select File Number"
                    )

                    self._set_thinking_state(
                        "Waiting for Selection"
                    )

                    self.left_panel.set_speaking(
                        "Silent"
                    )

                    self.mic_widget.show_listening()

                    self.mic_widget.set_listening(
                        False
                    )

                except Exception as error:

                    print(
                        f"File Selection State Error : {error}"
                    )

                QTimer.singleShot(
                    150,
                    self._wait_for_speech_then_start_selection
                )

                return


            # =================================================
            # Pending Confirmation - SECOND PRIORITY
            # =================================================

            if self._pending_confirmation:

                print(
                    "Manual listening finished. "
                    "Pending confirmation is active."
                )

                self.status_label.setText(
                    "Status : Waiting for Confirmation"
                )

                try:

                    self.left_panel.set_listening(
                        "Say Yes or No"
                    )

                    self._set_thinking_state(
                        "Waiting for Confirmation"
                    )

                    self.left_panel.set_speaking(
                        "Silent"
                    )

                except Exception as error:

                    print(
                        f"Confirmation State Error : {error}"
                    )

                QTimer.singleShot(
                    120,
                    self._wait_for_confirmation_prompt
                )

                return

            # --------------------------------------------------
            # Normal manual command
            # --------------------------------------------------
            # DO NOT unlock or restart wake-word mode here.
            # process_command() owns the command lifecycle and
            # _unlock_after_speech() will unlock + restart wake
            # only after processing/TTS has completed.
            # --------------------------------------------------

            self.status_label.setText(
                "Status : Processing..."
            )

            # IMPORTANT:
            # Do not force thinking_ai here. command_ready/process_command()
            # already detects the intent and selects thinking_laptop or
            # thinking_ai. Keeping that state prevents this finished callback
            # from overwriting the correct avatar.

            try:

                self.left_panel.set_listening(
                    "Idle"
                )

                self._set_thinking_state(
                    "Thinking",
                    avatar_state="thinking_laptop",
                )

                self.left_panel.set_speaking(
                    "Silent"
                )

            except Exception:
                pass

            return

        # ==================================================
        # DHEEPTHI WAKE WORD MODE
        # ==================================================

        if finished_mode == "wake":

            self.wake_word_running = False

            # The wake listener has released the microphone. The transition
            # guard can now be cleared because command capture is about to
            # take ownership through the existing manual path.
            self._wake_command_transition_active = False

            # ---------------------------------
            # Manual microphone has priority
            # ---------------------------------

            if self.manual_listening_requested:

                print(
                    "Wake listener stopped for manual microphone."
                )

                QTimer.singleShot(
                    0,
                    self._begin_manual_listening_prompt
                )

                return

            # ---------------------------------
            # Wake-word command is being processed.
            # ---------------------------------

            if self.processing_voice:

                return

            # ---------------------------------
            # Normal Wake Word Loop
            # ---------------------------------

            if self.wake_word_enabled:

                try:

                    self.left_panel.set_listening(
                        "Waiting for DHEEPTHI"
                    )

                    self._set_thinking_state(
                        "Inactive"
                    )

                    self.left_panel.set_speaking(
                        "Silent"
                    )

                except Exception:
                    pass

                QTimer.singleShot(
                    700,
                    lambda: (
                        self.start_wake_word_worker()
                        if self.wake_word_enabled
                        and not self.manual_listening_requested
                        and not self.processing_voice
                        else None
                    )
                )

            return

        # ---------------------------------
        # Unknown / Safety
        # ---------------------------------

        if not self.processing_voice:

            self.manual_listening_requested = False

            QTimer.singleShot(
                120,
                self.unlock_microphone
            )

    def start_voice_worker(
        self,
        wake_word_mode=False
    ):
        """
        Start a voice worker in either:

        wake_word_mode=True
            -> DHEEPTHI standby

        wake_word_mode=False
            -> Manual microphone
        """

        # ---------------------------------
        # Startup Greeting Safety Gate
        # ---------------------------------
        # No wake/manual voice worker may start while the opening greeting
        # owns the microphone.  This blocks stale QTimer callbacks and any
        # initialization race from stealing the microphone.

        if getattr(
            self,
            "_startup_greeting_active",
            False,
        ):

            print(
                "[VOICE] Startup greeting active. "
                "Voice worker start blocked."
            )

            return

        if not getattr(
            self,
            "_startup_sequence_complete",
            False,
        ):

            print(
                "[VOICE] Startup sequence incomplete. "
                "Voice worker start blocked."
            )

            return

        # ---------------------------------
        # Existing worker check
        # ---------------------------------

        if self.voice_worker is not None:

            try:
                if self.voice_worker.isRunning():
                    return
            except RuntimeError:
                # The previous QThread object may already have been deleted.
                self.voice_worker = None

        # ---------------------------------
        # Set Worker Mode
        # ---------------------------------

        if wake_word_mode:
            # Wake mode is owned by start_wake_word_worker().
            # Do not route production wake detection through SpeechRecognizer.
            print(
                "[VOICE] Wake mode request redirected to production detector."
            )

            self.start_wake_word_worker()
            return

        self.current_voice_mode = "manual"

        # ---------------------------------
        # Create Worker
        # ---------------------------------

        self.voice_worker = VoiceWorker(
            self.recognizer,
            self.tts,
            wake_word_mode=False,
        )

        # ---------------------------------
        # Signals
        # ---------------------------------

        self.voice_worker.command_ready.connect(
            self.process_command
        )

        self.voice_worker.audio_level.connect(
            self.update_audio_wave
        )

        self.voice_worker.finished.connect(
            self.listening_finished
        )

        # ---------------------------------
        # Start
        # ---------------------------------

        self.voice_worker.start()

        if wake_word_mode:

            self.wake_word_running = True

            print(
                "DHEEPTHI wake listener started."
            )

        else:

            print(
                "Manual microphone listener started."
            )

    # --------------------------------------------------
    # Start DHEEPTHI Wake Word Worker
    # --------------------------------------------------

    def start_wake_word_worker(self):

        # ----------------------------------
        # Startup Greeting Safety Gate
        # ----------------------------------
        # Any stale timer/signal must be ignored until the opening TTS has
        # completely finished and _finish_startup_greeting() has explicitly
        # released the microphone.

        if getattr(
            self,
            "_startup_greeting_active",
            False,
        ):

            print(
                "[WAKE] Startup greeting active. "
                "DHEEPTHI start request ignored."
            )

            return

        if not getattr(
            self,
            "_startup_sequence_complete",
            False,
        ):

            print(
                "[WAKE] Startup sequence incomplete. "
                "DHEEPTHI start request ignored."
            )

            return

        if not self.wake_word_enabled:

            return

        # ---------------------------------
        # Manual microphone has priority
        # ---------------------------------

        if self.manual_listening_requested:

            return

        if self.processing_voice:

            return

        # ---------------------------------
        # Existing Worker
        # ---------------------------------

        if self.voice_worker is not None:

            if self.voice_worker.isRunning():

                return

        # ---------------------------------
        # Start Wake Mode
        # ---------------------------------

        self.wake_word_running = True

        self.current_voice_mode = "wake"

        self.status_label.setText(
            "Status : Waiting for DHEEPTHI"
        )

        try:

            self.left_panel.set_listening(
                "Waiting for DHEEPTHI"
            )

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:

            pass

        # Production detector owns the wake-word microphone.
        self.voice_worker = WakeWordWorker(
            self.wake_word_detector
        )

        self.voice_worker.wake_detected.connect(
            self._on_wake_word_detected
        )

        self.voice_worker.audio_level.connect(
            self.update_audio_wave
        )

        self.voice_worker.finished.connect(
            self.listening_finished
        )

        self.voice_worker.start()

        self.wake_word_running = True

        print(
            "DHEEPTHI production wake listener started."
        )

    # --------------------------------------------------
    # Production DHEEPTHI Detection Callback
    # --------------------------------------------------

    @Slot(str)
    def _on_wake_word_detected(
        self,
        wake_word,
    ):
        """Convert DHEEPTHI detection into the existing manual command flow.

        Production wake-word recognition stays completely inside
        ``WakeWordDetector``. Once it confirms DHEEPTHI, MainWindow only
        performs the hand-off: stop the wake listener, show the existing
        LISTENING avatar/state, say ``Listening``, and then start the exact
        same command STT worker used by the manual microphone button.

        This method intentionally does NOT add a second STT path and does
        NOT send the wake-word text into the command dispatcher.
        """

        if self._closing:
            return

        if not self.wake_word_enabled:
            return

        if self.processing_voice:
            return

        if self.manual_listening_requested:
            return

        # The detector already guarantees one callback per detection.
        # The additional GUI-side guard protects against a race between
        # the detector callback, the worker shutdown signal, and queued
        # Qt events.
        if self._wake_command_transition_active:
            return

        normalized = (
            str(wake_word or "")
            .strip()
            .lower()
        )

        if normalized and "dheepthi" not in normalized:
            return

        self._wake_command_transition_active = True

        print(
            "\n⚡ DHEEPTHI confirmed by production detector."
        )
        print(
            "[WAKE -> COMMAND] Handing control to the existing manual STT lifecycle."
        )

        # --------------------------------------------------
        # Reuse the EXACT manual microphone lifecycle
        # --------------------------------------------------
        # This flag is consumed by listening_finished(). When the wake
        # worker releases the microphone, listening_finished() calls
        # _begin_manual_listening_prompt(), which says "Listening" and then
        # starts the normal VoiceWorker command capture.
        self.manual_listening_requested = True
        self.lock_microphone()

        # Immediate UI transition: identical to a manual mic click.
        self.status_label.setText(
            "Status : Listening..."
        )

        self._set_avatar_state(
            "listening"
        )

        try:
            self.mic_widget.show_listening()
            self.mic_widget.set_listening(False)

            self.left_panel.set_listening(
                "Listening"
            )

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

            QApplication.processEvents()

        except Exception as error:
            print(
                f"Wake listening UI state error: {error}"
            )

        # --------------------------------------------------
        # Release wake-word microphone before TTS/STT
        # --------------------------------------------------
        # Never run command STT while the production wake detector still
        # owns the sounddevice stream. This also prevents the following
        # "Listening" TTS from being captured by the wake detector.
        wake_worker = self.voice_worker

        if wake_worker is not None:
            try:
                if wake_worker.isRunning():
                    print(
                        "Stopping production DHEEPTHI listener "
                        "before command capture..."
                    )
                    wake_worker.stop()
                    return
            except Exception as error:
                print(
                    f"Wake worker state error: {error}"
                )

        # Worker already finished: continue through the same manual prompt.
        QTimer.singleShot(
            0,
            self._begin_manual_listening_prompt
        )


    # --------------------------------------------------
    # Audio Wave Update
    # --------------------------------------------------

    @Slot(float)
    def update_audio_wave(
        self,
        level
    ):

        try:

            self.mic_widget.update_audio_level(
                level
            )

        except Exception:

            pass

    # --------------------------------------------------
    # Premium Background
    # --------------------------------------------------

    def enable_premium_background(self):

        try:

            self.background.fast_mode = False

            self.background.update()

        except Exception:

            pass

    # =====================================================
    # Conversation Message Handling
    # =====================================================

    @Slot(str)
    def handle_conversation_message(
        self,
        text
    ):
        """
        Handle text submitted from ConversationPanel.

        Flow:

            ConversationPanel
                    ↓
              MainWindow
                    ↓
          Pending State Check
                    ↓
          Command Normalization
                    ↓
        Multi-Command Detection
             ↙              ↘
          YES                NO
           ↓                  ↓
        Planner          IntentDetector
           ↓                  ↓
        Executor       AI Chat / Automation
           ↓                  ↓
          Result          Dispatcher
        """

        if self._closing:
            return

        # =================================================
        # 1. CLEAN INPUT
        # =================================================

        original_text = str(
            text or ""
        ).strip()

        if not original_text:
            return

        # =================================================
        # 2. PREVENT OVERLAPPING GEMINI CHAT REQUESTS
        # =================================================

        if self.chat_processing:

            try:

                self.conversation_panel.show_error(
                    "DHEEPTHI is still processing the previous request."
                )

            except Exception:
                pass

            return

        # =================================================
        # 3. PENDING WORD CLARIFICATION
        # =================================================
        if self._pending_word_clarification:

            self._handle_word_clarification_response(
                original_text
            )

            return

        # =================================================
        # 4. PENDING CONFIRMATION
        # =================================================
        #
        # Example:
        #
        # User:
        #   shutdown computer
        #
        # ASTRA:
        #   Please confirm.
        #
        # User:
        #   yes
        #
        # The answer must NOT go through IntentDetector.
        # =================================================

        if self._pending_confirmation:

            self._handle_text_confirmation_response(
                original_text
            )

            return

        # =================================================
        # 5. PENDING FILE SELECTION
        # =================================================
        #
        # Example:
        #
        # User:
        #   open report
        #
        # ASTRA:
        #   I found 3 files. Choose a number.
        #
        # User:
        #   2
        #
        # "2" must resume the original command.
        # It must NOT become a new intent.
        # =================================================

        if self._pending_file_selection:

            self._handle_pending_file_selection(
                original_text
            )

            return

        # =================================================
        # 6. COMMAND NORMALIZATION
        # =================================================

        normalized_text = original_text

        if self.command_normalizer:

            try:

                normalized_text = (
                    self.command_normalizer.normalize(
                        original_text
                    )
                )

            except Exception as error:

                print(
                    f"Text Command Normalization Error : {error}"
                )

                normalized_text = original_text

        normalized_text = str(
            normalized_text or ""
        ).strip()

        if not normalized_text:
            return

        print(
            "\n========== TEXT INPUT =========="
        )

        print(
            f"Original   : {original_text}"
        )

        print(
            f"Normalized : {normalized_text}"
        )

        print(
            "================================\n"
        )

        # =================================================
        # 7. MULTI-COMMAND DETECTION
        # =================================================
        #
        # THIS MUST COME BEFORE IntentDetector.
        #
        # Example:
        #
        # open chrome then search sonatech.ac.in
        # then click first result
        #
        # If IntentDetector runs first, it can classify
        # the whole sentence as google_search.
        #
        # MultiCommandPlanner detects the chain first.
        # =================================================

        is_multi_command = False

        if self.multi_command_planner:

            try:

                is_multi_command = (
                    self.multi_command_planner
                    .is_multi_command(
                        normalized_text
                    )
                )

            except Exception as error:

                print(
                    f"Multi-Command Detection Error : {error}"
                )

                is_multi_command = False

        # =================================================
        # 8. MULTI-COMMAND FLOW
        # =================================================

        if (
            is_multi_command
            and
            self.multi_command_executor
        ):

            print(
                "\n========== TEXT MULTI COMMAND =========="
            )

            print(
                f"Command : {normalized_text}"
            )

            try:

                # -----------------------------------------
                # Planning State
                # -----------------------------------------

                self.status_label.setText(
                    "Status : Planning..."
                )

                try:

                    self.conversation_panel.show_ai_response(
                        "Planning your command..."
                    )

                except Exception:
                    pass

                try:

                    self.left_panel.set_listening(
                        "Text Command"
                    )

                    self._set_thinking_state(
                        "Planning",
                        avatar_state="thinking_laptop",
                    )

                    self.left_panel.set_speaking(
                        "Silent"
                    )

                except Exception:
                    pass

                QApplication.processEvents()

                # -----------------------------------------
                # Create Action Plan
                # -----------------------------------------

                plan = (
                    self.multi_command_planner
                    .create_plan(
                        normalized_text
                    )
                )

                print(
                    "\n---------- TEXT ACTION PLAN ----------"
                )

                print(
                    self.multi_command_planner
                    .plan_to_json(
                        plan
                    )
                )

                print(
                    "---------------------------------------\n"
                )

                # -----------------------------------------
                # Execution State
                # -----------------------------------------

                self.status_label.setText(
                    "Status : Executing..."
                )

                try:

                    self.conversation_panel.show_ai_response(
                        "Executing your command..."
                    )

                except Exception:
                    pass

                try:

                    self._set_thinking_state(
                        "Executing",
                        avatar_state="thinking_laptop",
                    )

                except Exception:
                    pass

                QApplication.processEvents()

                # -----------------------------------------
                # Execute Sequentially
                # -----------------------------------------

                result = (
                    self.multi_command_executor
                    .execute(
                        plan
                    )
                )

                print(
                    "\n---------- TEXT EXECUTION RESULT ----------"
                )

                print(
                    result
                )

                print(
                    "--------------------------------------------\n"
                )

                result = result or {}

                # =================================================
                # MULTI-COMMAND SUCCESS
                # =================================================

                if result.get(
                    "success",
                    False
                ):

                    completed_steps = result.get(
                        "completed_steps",
                        0
                    )

                    total_steps = result.get(
                        "total_steps",
                        getattr(
                            plan,
                            "total_steps",
                            len(plan.steps)
                        )
                    )

                    reply = (
                        f"Completed all "
                        f"{completed_steps} "
                        f"steps successfully."
                    )

                    try:

                        self.conversation_panel.show_ai_response(
                            reply
                        )

                    except Exception:
                        pass

                    self.status_label.setText(
                        "Status : Multi-Command Completed"
                    )

                    self.conversation_label.setText(
                        f"Multi-Command Completed\n\n"
                        f"{original_text}\n\n"
                        f"Steps : "
                        f"{completed_steps}/{total_steps}"
                    )

                    try:

                        self.left_panel.set_listening(
                            "Text Command"
                        )

                        self._set_thinking_state(
                            "Inactive"
                        )

                        self.left_panel.set_speaking(
                            "Silent"
                        )

                        self.right_panel.update_system_metrics()

                    except Exception:
                        pass

                    print(
                        "\nText multi-command completed successfully."
                    )

                    return

                # =================================================
                # MULTI-COMMAND FAILURE
                # =================================================

                failed_step = result.get(
                    "failed_step"
                )

                completed_steps = result.get(
                    "completed_steps",
                    0
                )

                if failed_step:

                    failed_action = failed_step.get(
                        "action",
                        "unknown action"
                    )

                    failure_message = (
                        f"I completed "
                        f"{completed_steps} "
                        f"step(s), but failed at "
                        f"{failed_action}."
                    )

                else:

                    failure_message = (
                        "I could not complete "
                        "the multi-step command."
                    )

                try:

                    self.conversation_panel.show_error(
                        failure_message
                    )

                except Exception:
                    pass

                self.status_label.setText(
                    "Status : Multi-Command Failed"
                )

                self.conversation_label.setText(
                    f"Multi-Command Failed\n\n"
                    f"{original_text}\n\n"
                    f"{result.get('status', '')}"
                )

                try:

                    self.left_panel.set_listening(
                        "Text Command"
                    )

                    self._set_thinking_state(
                        "Inactive"
                    )

                    self.left_panel.set_speaking(
                        "Silent"
                    )

                except Exception:
                    pass

                print(
                    "\nText multi-command failed."
                )

                return

            except Exception as error:

                print(
                    "\n========== TEXT MULTI COMMAND ERROR =========="
                )

                print(
                    error
                )

                print(
                    "==============================================\n"
                )

                error_message = (
                    "I could not plan or "
                    "execute that multi-step command."
                )

                try:

                    self.conversation_panel.show_error(
                        error_message
                    )

                except Exception:
                    pass

                self.status_label.setText(
                    "Status : Multi-Command Error"
                )

                self.conversation_label.setText(
                    f"Multi-Command Error\n\n"
                    f"{original_text}"
                )

                try:

                    self._set_thinking_state(
                        "Inactive"
                    )

                    self.left_panel.set_speaking(
                        "Silent"
                    )

                except Exception:
                    pass

                return

        # =================================================
        # 8. SINGLE COMMAND → INTENT DETECTOR
        # =================================================

        try:

            intent = self._detect_intent_with_context(
                normalized_text
            )

            # Final routing protection: explicit Python/Java programming
            # requests must never enter the Gemini ai_chat branch.
            if self._is_code_agent_request(normalized_text):
                if intent != "code_agent":
                    print(
                        "Text IntentDetector returned "
                        f"{intent!r}; overriding to code_agent."
                    )
                intent = "code_agent"

        except Exception as error:

            print(
                f"Text Intent Detection Error : {error}"
            )

            try:

                self.conversation_panel.show_error(
                    "I could not understand that command."
                )

            except Exception:
                pass

            self.status_label.setText(
                "Status : Intent Detection Error"
            )

            return

        print(
            "\n========== TEXT COMMAND =========="
        )

        print(
            f"Text   : {normalized_text}"
        )

        print(
            f"Intent : {intent}"
        )

        print(
            "==================================\n"
        )

        # =================================================
        # 9. AI CHAT
        # =================================================

        if intent == "ai_chat":

            # Always preserve the complete original message.
            # GeminiClient combines it with temporary session history.
            conversation_message = str(
                original_text or normalized_text or ""
            ).strip()

            self._start_text_gemini_chat(
                conversation_message
            )

            return

        # =================================================
        # 10. CODE AGENT
        # =================================================
        # Typed Python/Java requests use the same background worker
        # as voice programming requests.
        # =================================================

        if intent == "code_agent":

            self._start_code_agent_route(
                original_text
            )

            return

        # =================================================
        # 11. NORMAL AUTOMATION COMMAND
        # =================================================

        self._process_text_command(

            text=normalized_text,

            original_text=original_text,

            intent=intent

        )

    # =====================================================
    # Start Gemini Text Conversation
    # =====================================================

    def _start_text_gemini_chat(
        self,
        text
    ):
        """
        Start Gemini conversation from the text panel.

        Gemini runs inside ChatWorker so the Qt GUI thread
        remains responsive.
        """

        if self._closing:
            return

        text = str(
            text or ""
        ).strip()

        if not text:

            try:

                self.conversation_panel.show_error(
                    "Please enter a message."
                )

            except Exception:
                pass

            return

        if self.gemini is None:

            try:
                self.conversation_panel.show_error(
                    "Gemini is not ready yet."
                )
            except Exception:
                pass

            return

        # ------------------------------------------
        # Existing worker check
        # ------------------------------------------

        if self.chat_worker is not None:

            try:

                if self.chat_worker.isRunning():
                    return

            except RuntimeError:

                self.chat_worker = None

        # ------------------------------------------
        # Lock text input
        # ------------------------------------------

        self.chat_processing = True

        try:

            self.conversation_panel.set_input_enabled(
                False
            )

        except Exception as error:

            print(
                f"Conversation Input Lock Error : {error}"
            )

        # ------------------------------------------
        # Status
        # ------------------------------------------

        self.status_label.setText(
            "Status : DHEEPTHI is thinking..."
        )

        try:

            self._set_thinking_state(
                "Thinking"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:
            pass

        # ------------------------------------------
        # Create ChatWorker
        # ------------------------------------------

        self.chat_worker = ChatWorker(
            gemini=self.gemini,
            message=text
        )

        # ------------------------------------------
        # Signals
        # ------------------------------------------

        self.chat_worker.reply_ready.connect(
            self._conversation_reply_ready
        )

        self.chat_worker.error_occurred.connect(
            self._conversation_reply_error
        )

        self.chat_worker.finished.connect(
            self._conversation_worker_finished
        )

        # ------------------------------------------
        # Start
        # ------------------------------------------

        print(
            "\n========== TEXT AI CHAT =========="
        )

        print(
            f"User : {text}"
        )

        print(
            "Gemini Worker Started"
        )

        print(
            "=================================\n"
        )

        self.chat_worker.start()

    # =====================================================
    # Process Text Automation Command
    # =====================================================

    def _process_text_command(
        self,
        text,
        original_text,
        intent
    ):
        """
        Process a text command using the SAME:

            IntentDetector
            EntityExtractor
            TextExtractor
            CommandDispatcher

        backend used by ASTRA voice commands.

        This method intentionally does not call
        process_command() because process_command() owns
        microphone/TTS/wake-word lifecycle.
        """

        try:

            # =================================================
            # Typing Mode
            # =================================================

            if (
                intent == "type_text"
                and self.typing_mode
            ):

                self.keyboard_controller.type_text(
                    text
                )

                reply = "Typed successfully."

                try:

                    self.conversation_panel.show_ai_response(
                        reply
                    )

                except Exception:
                    pass

                self.status_label.setText(
                    "Status : Typed"
                )

                return

            # =================================================
            # Extract Entity
            # =================================================

            entity = None

            # -----------------------------------------------
            # Percentage Commands
            # -----------------------------------------------

            if intent in {
                "set_volume",
                "set_brightness"
            }:

                entity = (
                    self.entity_extractor
                    .extract_percentage(
                        text
                    )
                )

            # -----------------------------------------------
            # Commands without Entity
            # -----------------------------------------------

            elif intent in {

                "volume_up",
                "volume_down",
                "mute",

                "lock_screen",

                "take_screenshot",

                "open_task_manager",

                "open_file_explorer",

                "brightness_up",
                "brightness_down",

                "shutdown",
                "restart",
                "sleep",
                "sign_out",

                "open_settings",
                "open_cmd",
                "open_powershell",
                "open_control_panel",

                "open_camera",
                "capture_photo",

                "start_screen_recording",
                "stop_screen_recording",

            }:

                entity = None

            # -----------------------------------------------
            # File Commands
            # -----------------------------------------------

            elif intent in {

                "open_file",
                "create_file",
                "delete_file",

            }:

                entity = (
                    self.entity_extractor
                    .extract_file_query(
                        text
                    )
                )

            elif intent == "compress_file":

                entity = (
                    self.entity_extractor
                    .extract_compress_file(
                        text
                    )
                )

            elif intent == "extract_zip":

                entity = (
                    self.entity_extractor
                    .extract_extract_zip(
                        text
                    )
                )

            elif intent == "rename_file":

                entity = (
                    self.entity_extractor
                    .extract_rename_file(
                        text
                    )
                )

            elif intent == "copy_file":

                entity = (
                    self.entity_extractor
                    .extract_copy_file(
                        text
                    )
                )

            elif intent == "move_file":

                entity = (
                    self.entity_extractor
                    .extract_move_file(
                        text
                    )
                )

            elif intent == "search_extension":

                entity = (
                    self.entity_extractor
                    .extract_search_extension(
                        text
                    )
                )

            elif intent == "search_size":

                entity = (
                    self.entity_extractor
                    .extract_search_size(
                        text
                    )
                )

            elif intent == "search_date":

                entity = (
                    self.entity_extractor
                    .extract_search_date(
                        text
                    )
                )

            # -----------------------------------------------
            # Browser / Application Commands
            # -----------------------------------------------

            elif intent in {

                "launch_application",

                "create_word_document",

                "create_excel_workbook",

                "create_powerpoint_presentation",

                "open_website",

                "open_google",

                "open_youtube",

                "google_search",

                "youtube_search",

                "play_youtube",

                "new_tab",

                "close_tab",

                "next_tab",

                "previous_tab",

                "refresh",

                "browser_downloads",

                "browser_history",

                "browser_bookmarks",

                "bookmark_page",

                "address_bar",

                "browser_back",

                "browser_forward",

                "private_window",

                "open_chrome_profile",

            }:

                if intent in {

                    "launch_application",

                    "create_word_document",

                    "create_excel_workbook",

                    "create_powerpoint_presentation",

                }:

                    entity = (
                        self.entity_extractor
                        .extract_application(
                            text
                        )
                    )

                elif intent == "open_website":

                    entity = (
                        self.entity_extractor
                        .extract_website(
                            text
                        )
                    )

                elif intent == "open_google":

                    entity = "google.com"

                elif intent == "open_youtube":

                    entity = "youtube.com"

                elif intent == "google_search":

                    entity = (
                        self.entity_extractor
                        .extract_search_query(
                            text
                        )
                    )

                elif intent in {
                    "youtube_search",
                    "play_youtube",
                }:

                    entity = (
                        self.entity_extractor
                        .extract_youtube_query(
                            text
                        )
                    )

                else:

                    entity = None

            # -----------------------------------------------
            # Folder Commands
            # -----------------------------------------------

            elif intent == "rename_folder":

                entity = (
                    self.entity_extractor
                    .extract_rename_folder(
                        text
                    )
                )

            elif intent == "copy_folder":

                entity = (
                    self.entity_extractor
                    .extract_copy_folder(
                        text
                    )
                )

            elif intent == "move_folder":

                entity = (
                    self.entity_extractor
                    .extract_move_folder(
                        text
                    )
                )

            elif intent in {

                "open_folder",
                "create_folder",
                "delete_folder",

            }:

                entity = (
                    self.entity_extractor
                    .extract_folder(
                        text
                    )
                )

            elif intent == "empty_recycle_bin":

                entity = None

            # -----------------------------------------------
            # Default Application Extraction
            # -----------------------------------------------

            else:

                entity = (
                    self.entity_extractor
                    .extract_application(
                        text
                    )
                )

            # =================================================
            # Additional Extraction
            # =================================================

            typed_text = (
                self.text_extractor.extract_text(
                    text
                )
            )

            browser = (
                self.entity_extractor.extract_browser(
                    text
                )
            )

            website = (
                self.entity_extractor.extract_website(
                    text
                )
            )

            # -----------------------------------------------
            # Search Query
            # -----------------------------------------------

            search_query = None

            if intent == "google_search":

                search_query = (
                    self.entity_extractor
                    .extract_search_query(
                        text
                    )
                )

            elif intent in {

                "youtube_search",
                "play_youtube",

            }:

                search_query = (
                    self.entity_extractor
                    .extract_youtube_query(
                        text
                    )
                )

            # -----------------------------------------------
            # Chrome Profile
            # -----------------------------------------------

            profile = (
                self.entity_extractor.extract_profile(
                    text
                )
            )

            # =================================================
            # Debug
            # =================================================

            print(
                "\n========== TEXT COMMAND DATA =========="
            )

            print(
                f"Text         : {text}"
            )

            print(
                f"Intent       : {intent}"
            )

            print(
                f"Entity       : {entity}"
            )

            print(
                f"Typed Text   : {typed_text}"
            )

            print(
                f"Browser      : {browser}"
            )

            print(
                f"Website      : {website}"
            )

            print(
                f"Search Query : {search_query}"
            )

            print(
                f"Profile      : {profile}"
            )

            print(
                "=======================================\n"
            )

            # =================================================
            # Update UI
            # =================================================

            self.status_label.setText(
                "Status : Executing..."
            )

            try:

                self.left_panel.set_listening(
                    "Text Command"
                )

                self._set_thinking_state(
                    "Executing"
                )

                self.left_panel.set_speaking(
                    "Silent"
                )

            except Exception:
                pass

            # =================================================
            # Dispatcher
            # =================================================

            self._code_agent_processing = (
                intent == "code_agent"
                or intent == "generate_code"
                or intent == "write_code"
                or intent == "create_code"
                or intent == "programming"
            )

            result = self.dispatcher.dispatch(

                intent=intent,

                entity=entity,

                typed_text=typed_text,

                browser=browser,

                website=website,

                search_query=search_query,

                profile=profile,

                user_text=original_text

            )

            # =================================================
            # Handle Result
            # =================================================

            self._handle_text_dispatch_result(

                result=result,

                text=original_text,

                intent=intent,

                entity=entity,

            )

        except Exception as error:

            print(
                f"\nTEXT COMMAND ERROR : {error}\n"
            )

            self.status_label.setText(
                "Status : Text Command Error"
            )

            message = (
                "Sorry, I could not complete that command."
            )

            try:

                self.conversation_panel.show_error(
                    message
                )

            except Exception:
                pass

            try:

                self._set_thinking_state(
                    "Inactive"
                )

            except Exception:
                pass

    # =====================================================
    # Text Dispatcher Result
    # =====================================================

    def _handle_code_agent_result(
        self,
        result,
        text,
    ):
        """
        Handle a DHEEPTHI Code Agent result.

        CommandDispatcher owns:
            generation -> same-file rewrite -> compile ->
            automatic retry (maximum 3) -> run.

        MainWindow owns:
            UI presentation -> status/avatar -> microphone lifecycle.

        No confirmation is requested for Code Agent retries.
        """
        result = result or {}

        if not result.get("code_agent"):
            return False

        self._code_agent_processing = False

        success = bool(result.get("success", False))
        status = result.get(
            "status",
            "Status : Code Agent Completed"
            if success
            else "Status : Code Agent Failed",
        )

        # Dispatcher already speaks the user-facing message.
        # MainWindow must not speak it a second time.
        message = str(
            result.get(
                "message",
                result.get(
                    "assistant_reply",
                    "Code Agent completed the request."
                    if success
                    else "Code Agent could not complete the request.",
                ),
            )
            or ""
        ).strip()

        if success:
            execution = result.get("execution")
            if not isinstance(execution, dict):
                execution = {}

            terminal_opened = bool(
                execution.get("terminal_opened", False)
            )

            execution_mode = str(
                execution.get("execution_mode") or ""
            ).strip()

            if not message:
                if terminal_opened:
                    message = (
                        "Program compiled successfully and is running "
                        "in the new terminal."
                    )
                else:
                    output = str(
                        result.get("output")
                        or execution.get("output")
                        or ""
                    ).strip()
                    message = (
                        output
                        or "Program executed successfully."
                    )

            try:
                self.conversation_panel.show_ai_response(message)
            except Exception:
                pass

            self.status_label.setText(status)

            try:
                self.mic_widget.update_ai_message(message)
            except Exception:
                pass

            if terminal_opened:
                terminal_detail = (
                    "Program launched in a separate terminal."
                )

                if execution_mode:
                    terminal_detail += (
                        f"\nExecution Mode: {execution_mode}"
                    )

                output_detail = (
                    "Program output is displayed in that terminal."
                )
            else:
                terminal_detail = (
                    "Program execution completed."
                )
                output_detail = (
                    "No captured output was returned."
                )

            self.conversation_label.setText(
                "Code Agent Completed\n\n"
                f"Request:\n{text}\n\n"
                f"File:\n{result.get('file_path', '')}\n\n"
                f"Compile Attempts: {result.get('compile_attempts', 0)}\n\n"
                f"{terminal_detail}\n"
                f"{output_detail}"
            )

            try:
                self.left_panel.set_listening("Idle")
                self._set_thinking_state("Inactive")
                self.left_panel.set_speaking("Speaking")
                self.right_panel.update_system_metrics()
            except Exception:
                pass

            self._set_avatar_state("success")

            self._unlock_after_speech(
                restart_wake=True,
                terminal_avatar_state="success",
            )

            QTimer.singleShot(
                1400,
                lambda: self.left_panel.set_speaking("Silent"),
            )

            return True

        # Failure: after the third compile failure the dispatcher has
        # already cleared the same source file and stopped the task.
        try:
            self.conversation_panel.show_error(message)
        except Exception:
            pass

        try:
            self.mic_widget.update_ai_message(message)
        except Exception:
            pass

        attempts = result.get("compile_attempts", 0)

        if result.get("stopped_after_max_attempts"):
            status = "Status : Code Agent Stopped"
            detail = (
                "Code Agent stopped automatically after "
                f"{attempts or 3} compile attempts."
            )
        else:
            detail = (
                f"Compile attempts: {attempts}"
                if attempts
                else ""
            )

        self.status_label.setText(status)

        self.conversation_label.setText(
            "Code Agent Failed\n\n"
            f"Request:\n{text}\n\n"
            f"File:\n{result.get('file_path', '')}\n\n"
            f"{detail}\n\n"
            f"Error:\n"
            f"{result.get('compile_error') or result.get('error') or message}"
        )

        try:
            self.left_panel.set_listening("Idle")
            self._set_thinking_state("Inactive")
            self.left_panel.set_speaking("Speaking")
        except Exception:
            pass

        self._set_avatar_state("error")

        self._unlock_after_speech(
            restart_wake=True,
            terminal_avatar_state="error",
        )

        QTimer.singleShot(
            1400,
            lambda: self.left_panel.set_speaking("Silent"),
        )

        return True

    def _handle_text_dispatch_result(
        self,
        result,
        text,
        intent=None,
        entity=None,
    ):
        """
        Handle CommandDispatcher result for text commands.

        Reuses the existing MainWindow selection and
        confirmation flows.
        """

        result = result or {}

        # Code Agent has its own complete generation/compile/run
        # lifecycle. Present its result before generic branches.
        if self._handle_code_agent_result(result, text):
            return

        # =================================================
        # Word Information Required - FIRST
        # =================================================
        if result.get("requires_information") or (
            result.get("requires_clarification")
            and result.get("word_action")
        ):

            self._begin_word_clarification(
                result,
                text,
                intent,
                entity,
            )

            return

        # =================================================
        # File Selection - MUST BE FIRST
        # =================================================

        # =================================================
        # File Selection - FIRST PRIORITY
        # =================================================

        if result.get(
            "requires_selection"
        ):

            candidates = result.get(
                "candidates",
                []
            )

            if not candidates:

                message = (
                    "I could not find any selectable files."
                )

                try:

                    self.conversation_panel.show_error(
                        message
                    )

                except Exception as error:

                    print(
                        f"File Selection Error UI Error : {error}"
                    )

                self.status_label.setText(
                    "Status : File Selection Failed"
                )

                try:

                    self.tts.speak(
                        message
                    )

                except Exception as error:

                    print(
                        f"File Selection TTS Error : {error}"
                    )

                self._unlock_after_speech(
                    restart_wake=True
                )

                return


            # ---------------------------------------------
            # A new selection request must clear any old
            # confirmation state.
            # ---------------------------------------------

            self._pending_confirmation = None


            # ---------------------------------------------
            # Preserve dispatcher payload
            # ---------------------------------------------

            pending_payload = result.get(
                "pending_payload"
            )

            if not isinstance(
                pending_payload,
                dict
            ):

                pending_payload = {

                    "intent": intent,

                    "entity": entity,

                    "typed_text": result.get(
                        "typed_text"
                    ),

                    "browser": result.get(
                        "browser"
                    ),

                    "website": result.get(
                        "website"
                    ),

                    "search_query": result.get(
                        "search_query"
                    ),

                    "profile": result.get(
                        "profile"
                    ),

                    "user_text": text,

                    "multi_command": False,

                }

            else:

                pending_payload = dict(
                    pending_payload
                )


            # ---------------------------------------------
            # Ensure current command context exists
            # ---------------------------------------------

            pending_payload.setdefault(
                "intent",
                intent
            )

            pending_payload.setdefault(
                "entity",
                entity
            )

            pending_payload.setdefault(
                "user_text",
                text
            )


            # ---------------------------------------------
            # Resolve operation name
            # ---------------------------------------------

            operation = result.get(
                "pending_action"
            )

            if not operation:

                operation = intent or "file"


            # ---------------------------------------------
            # Store pending selection state
            # ---------------------------------------------

            self._pending_file_selection = {

                "payload": pending_payload,

                "candidates": candidates,

                "operation": operation,

            }


            # ---------------------------------------------
            # Show selection panel
            # ---------------------------------------------

            self.show_file_selection(
                candidates,
                operation=operation
            )


            # ---------------------------------------------
            # UI message
            # ---------------------------------------------

            message = (
                f"I found {len(candidates)} matching "
                f"items. Please choose a number."
            )

            try:

                self.conversation_panel.show_ai_response(
                    message
                )

            except Exception as error:

                print(
                    f"File Selection UI Error : {error}"
                )


            # ---------------------------------------------
            # Update status
            # ---------------------------------------------

            self.status_label.setText(
                "Status : Waiting for File Selection"
            )


            try:

                self.left_panel.set_listening(
                    "Waiting for File Number"
                )

                self._set_thinking_state(
                    "Select a File"
                )

                self.left_panel.set_speaking(
                    "Speaking"
                )

            except Exception as error:

                print(
                    f"File Selection Panel Error : {error}"
                )


            # ---------------------------------------------
            # Speak prompt
            # ---------------------------------------------

            try:

                self.tts.speak(
                    message
                )

            except Exception as error:

                print(
                    f"File Selection Prompt Error : {error}"
                )


            # ---------------------------------------------
            # Start selection microphone after TTS
            # ---------------------------------------------

            self._wait_for_speech_then_start_selection()

            return


        # =================================================
        # Confirmation - SECOND PRIORITY
        # =================================================

        if (
            result.get(
                "requires_confirmation"
            )
            or
            result.get(
                "confirmation_required"
            )
        ):

            # Selection is complete.
            # Clear it before waiting for YES / NO.

            self._pending_file_selection = None


            self._begin_confirmation_flow(
                result
            )

            return

        # =================================================
        # Success
        # =================================================

        if result.get(
            "success",
            False
        ):

            reply = result.get(
                "assistant_reply"
            )

            if not reply:

                reply = result.get(
                    "message"
                )

            if not reply:

                reply = result.get(
                    "status",
                    "Done."
                )

            reply = str(
                reply or "Done."
            ).strip()

            try:

                self.conversation_panel.show_ai_response(
                    reply
                )

            except Exception as error:

                print(
                    f"Text Command Reply UI Error : {error}"
                )

            self.status_label.setText(
                result.get(
                    "status",
                    "Status : Completed"
                )
            )

            self.conversation_label.setText(
                f"Executed Successfully\n\n{text}"
            )

            # ---------------------------------------------
            # Preserve existing application tracking
            # ---------------------------------------------

            if (
                intent == "launch_application"
                and entity
            ):

                self.last_application = self._entity_text(entity)

                entity_name = self._entity_text(entity).lower()

                if (
                    "notepad" in entity_name
                    or "word" in entity_name
                ):

                    self.typing_mode = True

            try:

                self._set_thinking_state(
                    "Inactive"
                )

                self.left_panel.set_speaking(
                    "Silent"
                )

                self.right_panel.update_system_metrics()

            except Exception:
                pass

            return

        # =================================================
        # Failed
        # =================================================

        failure_reply = result.get(
            "message",
            "Sorry, I could not complete that request."
        )

        failure_reply = str(
            failure_reply
        ).strip()

        try:

            self.conversation_panel.show_error(
                failure_reply
            )

        except Exception:
            pass

        self.status_label.setText(
            result.get(
                "status",
                "Status : No Action"
            )
        )

        try:

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:
            pass

    # =====================================================
    # Text Confirmation Response
    # =====================================================

    def _handle_text_confirmation_response(
        self,
        text
    ):
        """
        Handle YES/NO confirmation typed in the
        ConversationPanel.
        """

        if not self._pending_confirmation:
            return

        answer = self._parse_confirmation(
            text
        )

        # ------------------------------------------
        # Unclear
        # ------------------------------------------

        if answer is None:

            message = (
                "Please answer yes or no."
            )

            try:

                self.conversation_panel.show_error(
                    message
                )

            except Exception:
                pass

            return

        # ------------------------------------------
        # NO
        # ------------------------------------------

        if answer is False:

            self._pending_confirmation = None

            self.status_label.setText(
                "Status : Cancelled"
            )

            try:

                self.conversation_panel.show_ai_response(
                    "Operation cancelled."
                )

            except Exception:
                pass

            try:

                self._set_thinking_state(
                    "Inactive"
                )

            except Exception:
                pass

            return

        # ------------------------------------------
        # YES
        # ------------------------------------------

        pending = self._pending_confirmation

        self._pending_confirmation = None

        payload = dict(
            pending.get(
                "payload",
                {}
            )
        )

        action = pending.get(
            "action"
        )

        try:

            result = (
                self.dispatcher
                .execute_confirmed_action(
                    action,
                    payload
                )
            )

        except Exception as error:

            print(
                f"Text Confirmed Action Error : {error}"
            )

            result = {

                "success": False,

                "status": (
                    "Status : Confirmation Execution Failed"
                ),

                "message": (
                    "I could not complete the confirmed action."
                ),

            }

        self._handle_text_dispatch_result(

            result=result,

            text=payload.get(
                "user_text",
                text
            ),

            intent=payload.get(
                "intent",
                action
            ),

            entity=payload.get(
                "entity"
            ),

        )

    # =====================================================
    # Clickable Gemini Website Links
    # =====================================================

    @staticmethod
    def _gemini_reply_to_link_html(
        reply: str
    ) -> str:
        """
        Convert Gemini website references into safe clickable HTML.

        Supported forms:
            https://example.com
            http://example.com
            www.example.com
            example.com
            [Official Website](https://example.com)
            [Official Website](www.example.com)

        Gemini is allowed to return a website either as a complete URL or
        as a normal domain name.  Both forms must work in the conversation
        panel without changing the existing ConversationPanel API.
        """

        text = str(reply or "").strip()

        if not text:
            return ""

        # Escape Gemini output first.  Only the anchors created below are
        # allowed to introduce HTML.
        escaped = html.escape(text)

        # --------------------------------------------------------------
        # 1. Markdown links
        # --------------------------------------------------------------

        markdown_pattern = re.compile(
            r"\[([^\]]+)\]\((https?://[^\s)<>]+|www\.[^\s)<>]+|(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.)+[a-z]{2,}(?:[/?:#][^\s)]*)?)\)",
            flags=re.IGNORECASE,
        )

        def replace_markdown(match):
            label = match.group(1)
            raw_url = match.group(2)
            url = raw_url.strip()

            if not re.match(r"^https?://", url, flags=re.IGNORECASE):
                url = "https://" + url

            return (
                f'<a href="{html.escape(url, quote=True)}">'
                f'{label}</a>'
            )

        escaped = markdown_pattern.sub(
            replace_markdown,
            escaped,
        )

        # --------------------------------------------------------------
        # 2. Bare URLs / domains
        # --------------------------------------------------------------
        #
        # This is intentionally broader than an http(s) URL matcher.
        # Gemini frequently answers with a domain such as
        # "sonatech.ac.in" or "www.sonatech.ac.in".
        #
        # The negative look-behinds prevent matching domains inside an
        # existing href attribute or email address.
        # --------------------------------------------------------------

        website_pattern = re.compile(
            r"(?<![\w@/=\"'])"
            r"(?:https?://|www\.)?"
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
            r"[a-z]{2,63}"
            r"(?:[/:?#][^\s<>]*)?",
            flags=re.IGNORECASE,
        )

        def replace_website(match):
            raw = match.group(0)

            # Do not touch an already-generated anchor.
            if raw.lower().startswith((
                "http://",
                "https://",
                "www.",
            )):
                url = raw
            else:
                url = raw

            trailing = ""

            # Punctuation commonly follows a URL in normal prose.
            while url and url[-1] in ".,!?;:)]}\"'":
                trailing = url[-1] + trailing
                url = url[:-1]

            if not url:
                return raw

            href = url

            if not re.match(
                r"^https?://",
                href,
                flags=re.IGNORECASE,
            ):
                href = "https://" + href

            return (
                f'<a href="{html.escape(href, quote=True)}">'
                f'{html.escape(url)}</a>'
                f'{trailing}'
            )

        escaped = website_pattern.sub(
            replace_website,
            escaped,
        )

        # Preserve normal line breaks in QLabel rich text.
        return escaped.replace(
            "\n",
            "<br>"
        )

    def _open_gemini_website_link(
        self,
        url: str
    ):
        """
        Open a website clicked inside a Gemini response.

        ASTRA first uses its existing BrowserController so the link opens
        through the same browser automation path as other website commands.
        If that controller is unavailable or cannot open the URL, Qt's
        desktop URL handler is used as a safe compatibility fallback.
        """

        if self._closing:
            return

        url = str(url or "").strip()

        if not url:
            return

        if not re.match(
            r"^https?://",
            url,
            flags=re.IGNORECASE,
        ):
            if re.match(
                r"^(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?:[/:?#].*)?$",
                url,
                flags=re.IGNORECASE,
            ):
                url = "https://" + url
            else:
                return

        print(
            f"Gemini Website Link Clicked : {url}"
        )

        success = False

        # --------------------------------------------------------------
        # Existing ASTRA browser automation path
        # --------------------------------------------------------------

        try:
            browser_controller = getattr(
                self,
                "browser_controller",
                None,
            )

            if browser_controller is not None:

                open_current_tab = getattr(
                    browser_controller,
                    "open_url_current_tab",
                    None,
                )

                if callable(open_current_tab):
                    success = bool(
                        open_current_tab(url)
                    )

                if not success:

                    open_website = getattr(
                        browser_controller,
                        "open_website",
                        None,
                    )

                    if callable(open_website):
                        success = bool(
                            open_website(
                                url,
                                browser="chrome",
                            )
                        )

        except Exception as error:
            print(
                f"Gemini Website BrowserController Error : {error}"
            )

        # --------------------------------------------------------------
        # OS/browser fallback
        # --------------------------------------------------------------
        #
        # A Gemini answer must remain useful even when the ASTRA browser
        # controller has not finished initializing.
        # --------------------------------------------------------------

        if not success:

            try:
                success = bool(
                    QDesktopServices.openUrl(
                        QUrl(url)
                    )
                )
            except Exception as error:
                print(
                    f"Gemini Website Desktop Open Error : {error}"
                )

        if success:

            self.status_label.setText(
                "Status : Website Opened"
            )

            try:
                self.mic_widget.update_ai_message(
                    f"Opening website: {url}"
                )
            except Exception:
                pass

        else:

            self.status_label.setText(
                "Status : Website Open Failed"
            )

            try:
                self.conversation_panel.show_error(
                    f"I couldn't open the website:\n{url}"
                )
            except Exception:
                pass

    def _make_latest_gemini_response_clickable(
        self,
        reply: str
    ):
        """
        Upgrade only the latest Gemini response bubble so website links
        become real clickable links.

        This keeps ConversationPanel's existing public API unchanged.
        """

        panel = getattr(
            self,
            "conversation_panel",
            None,
        )

        if panel is None:
            return

        try:
            message_widgets = getattr(
                panel,
                "_message_widgets",
                [],
            )

            if not message_widgets:
                return

            # The list normally ends with the assistant bubble, but keep
            # this lookup defensive so a temporary/welcome widget can never
            # prevent Gemini links from becoming clickable.
            text_label = None

            for bubble in reversed(message_widgets):

                if bubble is None:
                    continue

                try:
                    if bubble.objectName() != "AssistantMessage":
                        continue
                except Exception:
                    pass

                candidate = bubble.findChild(
                    QLabel,
                    "MessageText",
                )

                if candidate is not None:
                    text_label = candidate
                    break

            if text_label is None:
                return

            link_html = self._gemini_reply_to_link_html(
                reply
            )

            # No URL was found. Keep the existing plain-text label.
            if "<a href=" not in link_html:
                return

            # Disconnect an earlier handler if this widget was reused.
            try:
                text_label.linkActivated.disconnect(
                    self._open_gemini_website_link
                )
            except (TypeError, RuntimeError):
                pass

            text_label.setTextFormat(
                Qt.RichText
            )
            text_label.setTextInteractionFlags(
                Qt.TextBrowserInteraction
            )
            text_label.setOpenExternalLinks(
                False
            )
            text_label.linkActivated.connect(
                self._open_gemini_website_link
            )
            text_label.setText(
                link_html
            )

            # Keep links visually obvious without changing the existing
            # ConversationPanel stylesheet.
            text_label.setStyleSheet(
                """
                QLabel#MessageText {
                    color: #1F2937;
                    font-size: 14px;
                    background: transparent;
                }
                QLabel#MessageText a {
                    color: #2563EB;
                    text-decoration: underline;
                }
                """
            )

        except Exception as error:
            print(
                f"Gemini Link UI Error : {error}"
            )

    # =====================================================
    # Gemini Reply
    # =====================================================

    @Slot(str)
    def _conversation_reply_ready(
        self,
        reply
    ):
        """
        Display Gemini response on the LEFT side
        of the conversation panel.

        ConversationPanel handles the actual bubble
        alignment.

        MainWindow only supplies the response.
        """

        if self._closing:

            return

        reply = str(
            reply or ""
        ).strip()

        if not reply:

            reply = (
                "Sorry, I couldn't generate "
                "a response right now."
            )

        # ------------------------------------------
        # Add Gemini / ASTRA response
        # ------------------------------------------

        try:

            self.conversation_panel.show_ai_response(
                reply
            )

            # Gemini can return an official website as a normal URL or
            # as a markdown link. Make that link clickable in ASTRA.
            self._make_latest_gemini_response_clickable(
                reply
            )

            QTimer.singleShot(
                0,
                lambda: self._make_latest_gemini_response_clickable(reply),
            )

            QTimer.singleShot(
                80,
                lambda: self._make_latest_gemini_response_clickable(reply),
            )

        except Exception as error:

            print(
                f"Conversation UI Reply Error : {error}"
            )

        # ------------------------------------------
        # Status
        # ------------------------------------------

        self.status_label.setText(
            "Status : Ready"
        )

        try:

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:

            pass

        print(
            "\n========== DHEEPTHI CONVERSATION =========="
        )

        print(
            f"DHEEPTHI : {reply}"
        )

        print(
            "========================================\n"
        )

    # =====================================================
    # Gemini Conversation Error
    # =====================================================

    @Slot(str)
    def _conversation_reply_error(
        self,
        message
    ):
        """
        Handle Gemini conversation errors without
        crashing the application.
        """

        if self._closing:

            return

        message = str(
            message or
            "Something went wrong."
        ).strip()

        print(
            f"Conversation Error : {message}"
        )

        try:

            self.conversation_panel.show_error(
                message
            )

        except Exception as error:

            print(
                f"Conversation Error UI Failure : {error}"
            )

        self.status_label.setText(
            "Status : Conversation Error"
        )

        try:

            self._set_thinking_state(
                "Inactive"
            )

            self.left_panel.set_speaking(
                "Silent"
            )

        except Exception:

            pass

    # =====================================================
    # Conversation Worker Finished
    # =====================================================

    # =====================================================
    # Conversation Worker Finished
    # =====================================================

    @Slot()
    def _conversation_worker_finished(
        self
    ):
        """
        Unlock ConversationPanel after Gemini finishes.
        """

        self.chat_processing = False

        # ------------------------------------------
        # Re-enable conversation input
        # ------------------------------------------

        if not self._closing:

            try:

                self.conversation_panel.set_input_enabled(
                    True
                )

            except Exception as error:

                print(
                    f"Conversation Input Unlock Error : {error}"
                )

        # ------------------------------------------
        # Worker cleanup
        # ------------------------------------------

        worker = self.chat_worker

        self.chat_worker = None

        if worker is not None:

            try:

                worker.deleteLater()

            except Exception as error:

                print(
                    f"Conversation Worker Cleanup Error : {error}"
                )

        # ------------------------------------------
        # Final UI state
        # ------------------------------------------

        if not self._closing:

            self.status_label.setText(
                "Status : Ready"
            )

            try:

                self._set_thinking_state(
                    "Inactive"
                )

                self.left_panel.set_speaking(
                    "Silent"
                )

            except Exception:
                pass

    # --------------------------------------------------
    # Conversation Panel Geometry
    # --------------------------------------------------

    def _position_conversation_panel(self):
        """
        Keep the ConversationPanel in the exact same
        position and size as the existing RightPanel.

        IMPORTANT:
            This method only synchronizes the final geometry.
            During animation we animate only the panel position,
            which is much lighter than continuously animating
            the complete geometry rectangle.
        """

        panel = getattr(
            self,
            "conversation_panel",
            None
        )

        right_panel = getattr(
            self,
            "right_panel",
            None
        )

        if panel is None or right_panel is None:
            return

        try:

            # ----------------------------------------------
            # Get RightPanel position in MainWindow coords
            # ----------------------------------------------

            top_left = right_panel.mapTo(
                self,
                right_panel.rect().topLeft()
            )

            geometry = right_panel.geometry()

            geometry.moveTopLeft(
                top_left
            )

            # ----------------------------------------------
            # Exact same size + position
            # ----------------------------------------------

            panel.setGeometry(
                geometry
            )

            panel.raise_()

        except RuntimeError:

            return

        except Exception as error:

            print(
                "Conversation Panel Position Error:",
                error
            )

    # --------------------------------------------------
    # Open Conversation Panel
    # --------------------------------------------------

    def open_conversation_panel(self):
        """
        Open ConversationPanel over the existing RightPanel.

        Lightweight animation:
            RIGHT -> LEFT

        The panel starts just outside the right edge and
        slides into the exact RightPanel position.

        Only the position is animated. This avoids the extra
        repaint/layout work caused by animating QRect geometry.
        """

        if self._closing:
            return

        panel = getattr(
            self,
            "conversation_panel",
            None
        )

        right_panel = getattr(
            self,
            "right_panel",
            None
        )

        if panel is None or right_panel is None:
            return

        # ----------------------------------------------
        # Already open / currently animating
        # ----------------------------------------------

        if self.conversation_panel_open:
            return

        if self.conversation_animating:
            return

        # ----------------------------------------------
        # Stop previous animation safely
        # ----------------------------------------------

        if self.conversation_animation is not None:

            try:
                self.conversation_animation.stop()

            except Exception:
                pass

            self.conversation_animation = None

        # ----------------------------------------------
        # Calculate exact final position
        # ----------------------------------------------

        try:

            top_left = right_panel.mapTo(
                self,
                right_panel.rect().topLeft()
            )

            final_geometry = right_panel.geometry()

            final_geometry.moveTopLeft(
                top_left
            )

        except Exception as error:

            print(
                "Conversation Geometry Error:",
                error
            )

            self._position_conversation_panel()

            final_geometry = panel.geometry()

        # ----------------------------------------------
        # Start position
        #
        # Same Y position as RightPanel.
        # Only X is outside the window.
        # ----------------------------------------------

        final_pos = final_geometry.topLeft()

        start_pos = QPoint(
            self.width() + 8,
            final_pos.y()
        )

        # ----------------------------------------------
        # Set exact size first
        # ----------------------------------------------

        panel.setGeometry(
            final_geometry
        )

        panel.move(
            start_pos
        )

        # ----------------------------------------------
        # Show panel
        # ----------------------------------------------

        panel.show()

        panel.raise_()

        # ----------------------------------------------
        # Hide existing RightPanel quickly
        # ----------------------------------------------

        try:

            right_panel.fade_out(
                duration=180
            )

        except Exception as error:

            print(
                "RightPanel Fade Out Error:",
                error
            )

        # ----------------------------------------------
        # Animation state
        # ----------------------------------------------

        self.conversation_animating = True

        self.conversation_animation_mode = "open"

        # ----------------------------------------------
        # Lightweight POSITION animation
        # ----------------------------------------------

        animation = QPropertyAnimation(
            panel,
            b"pos",
            self
        )

        animation.setDuration(
            220
        )

        animation.setStartValue(
            start_pos
        )

        animation.setEndValue(
            final_pos
        )

        animation.setEasingCurve(
            QEasingCurve.OutCubic
        )

        animation.finished.connect(
            self._conversation_open_finished
        )

        self.conversation_animation = animation

        self.conversation_panel_open = True

        animation.start()

    # --------------------------------------------------
    # Conversation Open Finished
    # --------------------------------------------------

    def _conversation_open_finished(self):
        """
        Finalize conversation panel opening.

        The final position is synchronized once after the
        animation completes.
        """

        panel = getattr(
            self,
            "conversation_panel",
            None
        )

        if panel is None:
            return

        try:

            # ----------------------------------------------
            # One final alignment pass
            # ----------------------------------------------

            self._position_conversation_panel()

            panel.raise_()

        except Exception as error:

            print(
                "Conversation Open Finish Error:",
                error
            )

        finally:

            self.conversation_animating = False

            self.conversation_animation_mode = None

            self.conversation_animation = None

    # --------------------------------------------------
    # Close Conversation Panel
    # --------------------------------------------------

    def close_conversation_panel(self):
        """
        Close the ConversationPanel.

        Lightweight animation:
            LEFT -> RIGHT

        Only the panel position is animated.
        """

        if self._closing:
            return

        panel = getattr(
            self,
            "conversation_panel",
            None
        )

        if panel is None:
            return

        if not self.conversation_panel_open:
            return

        # ----------------------------------------------
        # Prevent repeated close clicks
        # ----------------------------------------------

        if self.conversation_animating:
            return

        # ----------------------------------------------
        # Stop previous animation safely
        # ----------------------------------------------

        if self.conversation_animation is not None:

            try:
                self.conversation_animation.stop()

            except Exception:
                pass

            self.conversation_animation = None

        # ----------------------------------------------
        # Current position
        # ----------------------------------------------

        current_pos = panel.pos()

        # ----------------------------------------------
        # Move only horizontally outside the window
        # ----------------------------------------------

        end_pos = QPoint(
            self.width() + 8,
            current_pos.y()
        )

        # ----------------------------------------------
        # Animation state
        # ----------------------------------------------

        self.conversation_animating = True

        self.conversation_animation_mode = "close"

        # ----------------------------------------------
        # Lightweight POSITION animation
        # ----------------------------------------------

        animation = QPropertyAnimation(
            panel,
            b"pos",
            self
        )

        animation.setDuration(
            220
        )

        animation.setStartValue(
            current_pos
        )

        animation.setEndValue(
            end_pos
        )

        animation.setEasingCurve(
            QEasingCurve.InCubic
        )

        animation.finished.connect(
            self._conversation_close_finished
        )

        self.conversation_animation = animation

        # ----------------------------------------------
        # Bring RightPanel back immediately but softly
        # ----------------------------------------------

        if self.right_panel is not None:

            try:

                self.right_panel.fade_in(
                    duration=180
                )

            except Exception as error:

                print(
                    "RightPanel Fade In Error:",
                    error
                )

        animation.start()

    # --------------------------------------------------
    # Conversation Close Finished
    # --------------------------------------------------

    def _conversation_close_finished(self):
        """
        Finalize conversation panel closing.
        """

        panel = getattr(
            self,
            "conversation_panel",
            None
        )

        if panel is None:
            return

        try:

            panel.hide()

            # ----------------------------------------------
            # Restore exact RightPanel alignment
            # ----------------------------------------------

            self._position_conversation_panel()

        except Exception as error:

            print(
                "Conversation Close Finish Error:",
                error
            )

        finally:

            self.conversation_panel_open = False

            self.conversation_animating = False

            self.conversation_animation_mode = None

            self.conversation_animation = None

    # --------------------------------------------------
    # Toggle Conversation Panel
    # --------------------------------------------------

    def toggle_conversation_panel(self):
        """
        Header conversation button callback.

        Closed:
            -> Open

        Open:
            -> Close

        While animation is running:
            -> Ignore additional clicks

        This prevents animation stacking and keeps the UI
        responsive on lower-spec systems.
        """

        if self._closing:
            return

        # ----------------------------------------------
        # Ignore repeated clicks during animation
        # ----------------------------------------------

        if self.conversation_animating:
            return

        if self.conversation_panel_open:

            self.close_conversation_panel()

        else:

            self.open_conversation_panel()

    # --------------------------------------------------
    # Resize Event
    # --------------------------------------------------

    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )

        # --------------------------------------------------
        # Custom title bar
        # --------------------------------------------------

        title_bar = getattr(
            self,
            "application_title_bar",
            None
        )

        if title_bar is not None:

            try:

                title_bar.setGeometry(
                    0,
                    0,
                    self.width(),
                    ApplicationTitleBar.HEIGHT
                )

                title_bar.raise_()

            except RuntimeError:

                self.application_title_bar = None

        # --------------------------------------------------
        # Loading overlay
        # --------------------------------------------------

        overlay = getattr(
            self,
            "loading_overlay",
            None
        )

        if overlay is not None:

            try:

                if overlay.isVisible():

                    overlay.setGeometry(
                        self.rect()
                    )

            except RuntimeError:

                self.loading_overlay = None

        # --------------------------------------------------
        # Conversation Panel
        # --------------------------------------------------

        conversation_panel = getattr(
            self,
            "conversation_panel",
            None
        )

        if conversation_panel is not None:

            try:

                if conversation_panel.isVisible():

                    # ------------------------------------------
                    # Never disturb an active animation.
                    # ------------------------------------------

                    if not self.conversation_animating:

                        self._position_conversation_panel()

            except RuntimeError:

                pass

        # --------------------------------------------------
        # File Selection Panel
        # --------------------------------------------------

        panel = getattr(
            self,
            "file_selection_panel",
            None
        )

        if panel is not None:

            try:

                if panel.isVisible():

                    QTimer.singleShot(
                        0,
                        self._position_file_selection_panel
                    )

                    QTimer.singleShot(
                        80,
                        self._position_file_selection_panel
                    )

            except RuntimeError:

                pass

    # --------------------------------------------------
    # Initialize Application
    # --------------------------------------------------

    def initialize_application(self):
        """
        Initialize ASTRA.

        Environment variables are loaded at module startup so the
        backend objects created by MainWindow inherit the same
        project-level configuration.
        """

        self.enable_premium_background()

        # Chain backend creation -> InitializationWorker startup so the two
        # independent startup timers can never race each other.
        QTimer.singleShot(
            50,
            self._create_backend_then_initialize
        )

    def _create_backend_then_initialize(self):
        """Create backend first, then start the background initializer."""

        if self._closing or self._backend_initialization_started:
            return

        if not self.create_backend():
            self.initialization_failed(
                "Backend initialization failed. Check the ASTRA-AI console for details."
            )
            return

        self.start_initialization()

    # --------------------------------------------------
    # Okii, byee! See youu soon 🫶 Shutdown
    # --------------------------------------------------

    def _speak_then_close(self, message):
        """
        Speak ``message`` and close the MainWindow immediately after
        the TTS request finishes.

        No fixed shutdown delay is used. The TextToSpeech manager emits
        ``speech_finished(bool)`` only after the active speech provider
        has completed, so that signal is the source of truth.
        """

        tts = getattr(self, "tts", None)

        if tts is None:

            print(
                "[DHEEPTHI SHUTDOWN] TTS object is unavailable. "
                "Closing immediately."
            )

            self._finish_goodbye_shutdown()
            return False

        try:

            speech_finished_signal = getattr(
                tts,
                "speech_finished",
                None,
            )

            # Connect before speak() so a very short speech cannot finish
            # before MainWindow starts listening for the completion signal.
            if (
                speech_finished_signal is not None
                and hasattr(speech_finished_signal, "connect")
            ):

                if not self._goodbye_tts_signal_connected:

                    speech_finished_signal.connect(
                        self._on_goodbye_tts_finished
                    )

                    self._goodbye_tts_signal_connected = True

                    print(
                        "[DHEEPTHI SHUTDOWN] TTS completion signal connected."
                    )

                print(
                    "[DHEEPTHI SHUTDOWN] Speaking goodbye..."
                )

                result = tts.speak(message)

                if result is not None:

                    print(
                        "[DHEEPTHI SHUTDOWN] Goodbye TTS started. "
                        "Waiting for speech_finished."
                    )

                    return True

                print(
                    "[DHEEPTHI SHUTDOWN] Goodbye TTS did not start. "
                    "Closing immediately."
                )

                self._finish_goodbye_shutdown()
                return False

            # Compatibility fallback for a TTS implementation that does
            # not expose speech_finished. Poll the actual speaking state;
            # this is not a fixed shutdown delay.
            print(
                "[DHEEPTHI SHUTDOWN] speech_finished signal unavailable. "
                "Using speaking-state completion fallback."
            )

            result = tts.speak(message)

            if result is None:

                self._finish_goodbye_shutdown()
                return False

            self._wait_for_goodbye_tts_completion()
            return True

        except Exception as error:

            print(
                f"[DHEEPTHI SHUTDOWN] Goodbye TTS error: {error}"
            )

            self._finish_goodbye_shutdown()
            return False

    def _wait_for_goodbye_tts_completion(self):
        """
        Compatibility fallback when TTS has no speech_finished signal.

        The check follows the real TTS speaking state rather than waiting
        for an arbitrary number of milliseconds.
        """

        if getattr(self, "_shutdown_finalizing", False):
            return

        tts = getattr(self, "tts", None)

        if tts is None:
            self._finish_goodbye_shutdown()
            return

        try:

            speaking_method = getattr(
                tts,
                "speaking",
                None,
            )

            if callable(speaking_method):

                if speaking_method():

                    QTimer.singleShot(
                        50,
                        self._wait_for_goodbye_tts_completion
                    )
                    return

                self._finish_goodbye_shutdown()
                return

            # If there is no way to query completion, fail safe instead of
            # leaving the application open forever.
            self._finish_goodbye_shutdown()

        except Exception as error:

            print(
                f"[DHEEPTHI SHUTDOWN] TTS completion check error: {error}"
            )

            self._finish_goodbye_shutdown()

    def _begin_goodbye_shutdown(self, event=None):
        """
        Start the goodbye sequence without destroying the window.

        The MainWindow remains alive until TTS reports completion.
        There is no fixed shutdown timer.
        """

        if getattr(self, "_shutdown_finalizing", False):
            if event is not None:
                event.ignore()
            return False

        if getattr(self, "_shutdown_goodbye_started", False):
            if event is not None:
                event.ignore()
            return True

        self._shutdown_goodbye_started = True
        self._closing = True
        self._goodbye_tts_finished = False

        # ----------------------------------------------
        # Lock microphone for the entire goodbye lifecycle.
        # It stays locked while the goodbye avatar and TTS run.
        # ----------------------------------------------

        try:

            self.lock_microphone()

            print(
                "[DHEEPTHI SHUTDOWN] Microphone locked for goodbye."
            )

        except Exception as error:

            print(
                f"[DHEEPTHI SHUTDOWN] Microphone lock error: {error}"
            )

        # Select exactly one closing greeting for this shutdown.
        # The goodbye avatar is shown before TTS starts and remains visible
        # until speech_finished triggers the final close path.
        goodbye_message = random.choice(CLOSE_GREETINGS)

        print(
            f"[DHEEPTHI SHUTDOWN] Selected goodbye : {goodbye_message}"
        )

        print("\n========== DHEEPTHI GOODBYE ==========")
        print(f"DHEEPTHI : {goodbye_message}")

        # ----------------------------------------------
        # Prevent new voice / wake-word work.
        # ----------------------------------------------

        self.manual_listening_requested = False
        self._wake_command_transition_active = False
        self.wake_word_enabled = False
        self.wake_word_running = False
        self.processing_voice = False

        # ----------------------------------------------
        # Stop active voice worker without blocking GUI.
        # ----------------------------------------------

        voice_worker = getattr(self, "voice_worker", None)

        if voice_worker is not None:

            try:

                if voice_worker.isRunning():

                    voice_worker.stop()

                    print(
                        "[DHEEPTHI SHUTDOWN] VoiceWorker stop requested."
                    )

            except Exception as error:

                print(
                    f"[DHEEPTHI SHUTDOWN] VoiceWorker stop error: {error}"
                )

        # ----------------------------------------------
        # Show goodbye avatar.
        # ----------------------------------------------

        avatar_widget = getattr(self, "avatar_widget", None)

        try:

            if avatar_widget is not None:

                if hasattr(avatar_widget, "set_state"):
                    avatar_widget.set_state("goodbye")

                elif hasattr(avatar_widget, "set_avatar_state"):
                    avatar_widget.set_avatar_state("goodbye")

        except Exception as error:

            print(
                f"[DHEEPTHI SHUTDOWN] Goodbye avatar error: {error}"
            )

        # ----------------------------------------------
        # Update visible goodbye UI.
        # ----------------------------------------------

        try:
            self.status_label.setText("Status : Goodbye")
        except Exception:
            pass

        try:
            self.mic_widget.update_ai_message(goodbye_message)
        except Exception:
            pass

        try:
            self.conversation_label.setText(goodbye_message)
        except Exception:
            pass

        try:
            self.left_panel.set_listening("Goodbye")
            self.left_panel.set_thinking("Inactive")
            self.left_panel.set_speaking("Speaking")
        except Exception:
            pass

        QApplication.processEvents()

        # ----------------------------------------------
        # TTS owns the exact completion point.
        # ----------------------------------------------

        self._speak_then_close(goodbye_message)

        if event is not None:
            event.ignore()

        return True

    def _on_goodbye_tts_finished(self, success=True):
        """
        Close the MainWindow immediately when the goodbye TTS finishes.
        """

        if getattr(self, "_shutdown_finalizing", False):
            return

        if not getattr(self, "_shutdown_goodbye_started", False):
            return

        if getattr(self, "_goodbye_tts_finished", False):
            return

        self._goodbye_tts_finished = True

        print(
            "[DHEEPTHI SHUTDOWN] Goodbye TTS finished. "
            f"Success : {bool(success)}"
        )

        # TTS completion is the ONLY normal trigger for final shutdown.
        # _finish_goodbye_shutdown() marks the final-close state and then
        # re-enters closeEvent(), where the existing cleanup is preserved.
        self._finish_goodbye_shutdown()

    def _finish_goodbye_shutdown(self):
        """
        Transition immediately from completed goodbye TTS to final cleanup.
        """

        if getattr(self, "_shutdown_finalizing", False):
            return

        if not getattr(self, "_shutdown_goodbye_started", False):
            return

        print(
            "[DHEEPTHI SHUTDOWN] Goodbye complete. "
            "Starting final cleanup."
        )

        self._shutdown_finalizing = True

        # No artificial delay. This immediately re-enters closeEvent()
        # so the existing worker/backend cleanup remains intact.
        self.close()

    # --------------------------------------------------
    # Close Event
    # --------------------------------------------------

    def closeEvent(
        self,
        event
    ):
        """
        Safely shut down all background workers and backend resources.

        First close request:
            X
              ↓
            Goodbye avatar + TTS
              ↓
            final shutdown
              ↓
            close application

        If VoiceWorker is still running:
            close event is temporarily ignored
            VoiceWorker finishes
            shutdown continuation is triggered
            self.close() starts the final close pass
        """

        # ==================================================
        # FIRST CLOSE REQUEST
        # ==================================================

        if not self._shutdown_finalizing:

            self._begin_goodbye_shutdown(
                event
            )

            # IMPORTANT:
            # Do not let Qt destroy the window while
            # goodbye avatar/TTS is still running.
            event.ignore()

            return

        # ==================================================
        # FINAL CLOSE PASS
        # ==================================================

        self._closing = True

        print(
            "\n========== DHEEPTHI SHUTDOWN =========="
        )

        # ==================================================
        # DISABLE FUTURE VOICE RESTARTS
        # ==================================================

        self.manual_listening_requested = False
        self.wake_word_enabled = False
        self.wake_word_running = False

        # ==================================================
        # PROCESS PENDING QT EVENTS
        # ==================================================

        try:

            QCoreApplication.processEvents()

        except Exception:

            pass

        # ==================================================
        # GEMINI CHAT WORKER
        # ==================================================

        chat_worker = getattr(
            self,
            "chat_worker",
            None
        )

        if chat_worker is not None:

            try:

                if chat_worker.isRunning():

                    print(
                        "Stopping ChatWorker..."
                    )

                    chat_worker.requestInterruption()

                    if chat_worker.wait(1500):

                        print(
                            "ChatWorker stopped successfully."
                        )

                    else:

                        print(
                            "ChatWorker is still finishing."
                        )

                self.chat_worker = None

            except Exception as error:

                print(
                    f"ChatWorker Cleanup Error : {error}"
                )

            self.chat_processing = False

        # ==================================================
        # VOICE WORKER
        # ==================================================

        voice_worker = getattr(
            self,
            "voice_worker",
            None
        )

        if voice_worker is not None:

            try:

                if voice_worker.isRunning():

                    print(
                        "Stopping VoiceWorker..."
                    )

                    # --------------------------------------------------
                    # Ask recognizer / worker to stop.
                    # --------------------------------------------------

                    voice_worker.stop()

                    # --------------------------------------------------
                    # Give it a short opportunity to finish.
                    # --------------------------------------------------

                    if voice_worker.wait(250):

                        print(
                            "VoiceWorker stopped successfully."
                        )

                        self.voice_worker = None

                    else:

                        # --------------------------------------------------
                        # IMPORTANT:
                        #
                        # DO NOT destroy the QThread here.
                        #
                        # Wake-word recording may still be inside
                        # sounddevice / Faster-Whisper.
                        # --------------------------------------------------

                        print(
                            "VoiceWorker is still stopping; "
                            "waiting for finished signal."
                        )

                        try:

                            voice_worker.finished.connect(
                                self._on_voice_worker_shutdown_finished,
                                Qt.QueuedConnection
                            )

                        except (
                            TypeError,
                            RuntimeError
                        ):

                            try:

                                voice_worker.finished.connect(
                                    self._on_voice_worker_shutdown_finished
                                )

                            except Exception:

                                pass

                        # --------------------------------------------------
                        # Keep the close event alive.
                        # Qt must NOT destroy the window/thread yet.
                        # --------------------------------------------------

                        event.ignore()

                        return

                else:

                    self.voice_worker = None

            except Exception as error:

                print(
                    f"VoiceWorker Cleanup Error : {error}"
                )

        # ==================================================
        # ==================================================
        # VISION WORKER
        # ==================================================

        vision_worker = getattr(
            self,
            "vision_worker",
            None
        )

        if vision_worker is not None:

            try:

                if vision_worker.isRunning():

                    print(
                        "Stopping VisionWorker..."
                    )

                    if vision_worker.wait(250):

                        print(
                            "VisionWorker stopped successfully."
                        )

                        self.vision_worker = None

                    else:

                        print(
                            "VisionWorker is still finishing."
                        )

                        try:
                            vision_worker.finished.connect(
                                self._on_vision_worker_shutdown_finished,
                                Qt.QueuedConnection
                            )
                        except (TypeError, RuntimeError):

                            try:
                                vision_worker.finished.connect(
                                    self._on_vision_worker_shutdown_finished
                                )
                            except Exception:
                                pass

                        event.ignore()
                        return

                else:

                    self.vision_worker = None

            except Exception as error:

                print(
                    f"VisionWorker Cleanup Error : {error}"
                )

        # ==================================================
        # VISION ENGINE
        # ==================================================

        try:

            vision = getattr(
                self,
                "vision",
                None
            )

            if vision is not None:

                print(
                    "Closing VisionEngine..."
                )

                vision.close()

                self.vision = None

                print(
                    "VisionEngine closed successfully."
                )

        except Exception as error:

            print(
                f"VisionEngine Cleanup Error : {error}"
            )

        # INITIALIZATION WORKER
        # ==================================================

        initialization_worker = getattr(
            self,
            "worker",
            None
        )

        if initialization_worker is not None:

            try:

                if initialization_worker.isRunning():

                    print(
                        "Stopping InitializationWorker..."
                    )

                    initialization_worker.stop()

                    initialization_worker.requestInterruption()

                    if not initialization_worker.wait(
                        5000
                    ):

                        print(
                            "InitializationWorker did not stop "
                            "within 5 seconds."
                        )

                    else:

                        print(
                            "InitializationWorker stopped successfully."
                        )

                self.worker = None

            except Exception as error:

                print(
                    f"InitializationWorker Cleanup Error : {error}"
                )

        # ==================================================
        # LIVE FILE MONITOR
        # ==================================================

        file_monitor = getattr(
            self,
            "file_monitor",
            None
        )

        if file_monitor is not None:

            try:

                print(
                    "Stopping Live File Monitor..."
                )

                file_monitor.close()

                self.file_monitor = None

                print(
                    "Live File Monitor stopped successfully."
                )

            except Exception as error:

                print(
                    f"File Monitor Cleanup Error : {error}"
                )

        # ==================================================
        # PRODUCTION DHEEPTHI WAKE DETECTOR
        # ==================================================

        wake_detector = getattr(
            self,
            "wake_word_detector",
            None
        )

        if wake_detector is not None:

            try:
                print(
                    "Closing production DHEEPTHI wake detector..."
                )

                wake_detector.close()

                self.wake_word_detector = None

                print(
                    "Production DHEEPTHI wake detector closed."
                )

            except Exception as error:

                print(
                    f"Wake detector cleanup error: {error}"
                )

        # ==================================================
        # GEMINI
        # ==================================================

        try:

            gemini = getattr(
                self,
                "gemini",
                None
            )

            if gemini:

                gemini.close()

        except Exception as error:

            print(
                f"Gemini Cleanup Error : {error}"
            )

        # ==================================================
        # TEXT TO SPEECH
        # ==================================================

        try:

            tts = getattr(
                self,
                "tts",
                None
            )

            if tts:

                tts.close()

        except Exception as error:

            print(
                f"TTS Cleanup Error : {error}"
            )

        # ==================================================
        # BROWSER
        # ==================================================

        try:

            browser_controller = getattr(
                self,
                "browser_controller",
                None
            )

            if browser_controller:

                browser_controller.close()

        except Exception as error:

            print(
                f"Browser Cleanup Error : {error}"
            )

        # ==================================================
        # FINAL SHUTDOWN
        # ==================================================

        print(
            "========== DHEEPTHI SHUTDOWN COMPLETE ==========\n"
        )

        # --------------------------------------------------
        # IMPORTANT:
        #
        # event is ONLY accepted here, after every worker
        # that must be stopped has finished.
        # --------------------------------------------------

        event.accept()

        super().closeEvent(
            event
        )

    # ==================================================
    # ==================================================
    # VISION WORKER SHUTDOWN CONTINUATION
    # ==================================================

    def _on_vision_worker_shutdown_finished(
        self
    ):
        """Continue shutdown after VisionWorker has fully finished."""

        if not getattr(
            self,
            "_shutdown_finalizing",
            False
        ):
            return

        worker = getattr(
            self,
            "vision_worker",
            None
        )

        if worker is not None:

            try:

                if worker.isRunning():
                    return

            except RuntimeError:
                pass

        self.vision_worker = None

        print(
            "VisionWorker stopped asynchronously; "
            "continuing final shutdown."
        )

        QTimer.singleShot(
            0,
            self.close
        )

    # VOICE WORKER SHUTDOWN CONTINUATION
    # ==================================================

    def _on_voice_worker_shutdown_finished(
        self
    ):
        """
        Continue final application shutdown after the
        VoiceWorker QThread has completely finished.
        """

        if not getattr(
            self,
            "_shutdown_finalizing",
            False
        ):

            return

        voice_worker = getattr(
            self,
            "voice_worker",
            None
        )

        if voice_worker is not None:

            try:

                if voice_worker.isRunning():

                    return

            except RuntimeError:

                pass

        # --------------------------------------------------
        # QThread has finished.
        # It is now safe to release our reference.
        # --------------------------------------------------

        self.voice_worker = None

        print(
            "VoiceWorker stopped asynchronously; "
            "continuing final shutdown."
        )

        # --------------------------------------------------
        # Re-enter closeEvent().
        # This time _shutdown_finalizing is already True,
        # so the FINAL CLOSE PASS will execute.
        # --------------------------------------------------

        QTimer.singleShot(
            0,
            self.close
        )

