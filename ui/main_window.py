import os
import re
import html
import random
import queue
import threading
import math
import struct
import time
from pathlib import Path

from dotenv import load_dotenv

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    from voice.microphone_monitor import MicrophoneMuteMonitor
except Exception:
    MicrophoneMuteMonitor = None


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
    QImage,
    QPainter,
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
from ui.widgets.user_speech_panel import UserSpeechPanel
from ui.widgets.file_selection_panel import FileSelectionPanel
from ui.widgets.system_osd import SystemOSD

from voice.text_to_speech import TextToSpeech
from voice.streaming_tts_manager import StreamingTTSManager


from planner.intent_detector import IntentDetector
from planner.entity_extractor import EntityExtractor
from planner.text_extractor import TextExtractor
from planner.command_normalizer import CommandNormalizer
from planner.command_dispatcher import CommandDispatcher
from ai.gemini_client import GeminiClient
from planner.multi_command_planner import MultiCommandPlanner
from planner.multi_command_executor import MultiCommandExecutor
from planner.semantic_command_planner import SemanticCommandPlanner

from automation.keyboard_controller import KeyboardController
from automation.mouse_controller import MouseController
from automation.window_controller import WindowController
from automation.system_controller import SystemController
from automation.screen_recorder import ScreenRecorder
from automation.app_launcher import AppLauncher
from automation.app_closer import AppCloser
from automation.file_finder import FileFinder
from automation.folder_manager import FolderManager
from automation.file_manager import FileManager
from automation.browser_controller import BrowserController
from automation.file_monitor import FileMonitor

from workers.initialization_worker import InitializationWorker
from vision.gemini_vision import GeminiVision
from vision.ocr import OCREngine


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



# =====================================================
# Gemini Live Audio Worker
# =====================================================

class VoiceWorker(QThread):
    """Background worker for existing manual command STT.

    IMPORTANT:
        This legacy worker is retained for compatibility with existing
        command/selection flows. Normal V1 voice interaction is handled
        directly by Gemini Live; no wake-word listener is used.
    """

    command_ready = Signal(str)
    finished = Signal()
    audio_level = Signal(float)

    def __init__(self, recognizer=None, tts=None):
        super().__init__()
        self.recognizer = recognizer
        self.tts = tts
        self._stop = False
        self._command_emitted = False
        self.timed_out = False
        self.command_captured = False

        try:
            if self.recognizer is not None:
                self.recognizer.level_callback = self.audio_level.emit
        except Exception as error:
            print(f"VoiceWorker Audio Callback Error : {error}")

    def run(self):
        """
        Capture exactly one manual voice command.

        A silent microphone timeout is treated as a normal cancelled
        listening session. It is NOT an application shutdown condition.
        """

        try:

            if (
                self._stop
                or self.isInterruptionRequested()
            ):
                return

            # Give the GUI/TTS transition a short moment to settle before
            # opening the command microphone.
            self.msleep(180)

            if (
                self._stop
                or self.isInterruptionRequested()
            ):
                return

            command = self.recognizer.listen(
                timeout=5,
                phrase_time_limit=20,
                calibrate=False,
            )

            if (
                self._stop
                or self.isInterruptionRequested()
            ):
                return

            if command:

                command = str(
                    command
                ).strip()

                if (
                    command
                    and not self._command_emitted
                ):

                    self._command_emitted = True
                    self.command_captured = True
                    self.timed_out = False

                    print(
                        f"Command Ready : {command}"
                    )

                    self.command_ready.emit(
                        command
                    )

            else:

                self.timed_out = True
                self.command_captured = False

                print(
                    "Voice command capture timed out."
                )

        except TypeError as error:

            print(
                f"VoiceWorker API Error : {error}"
            )

        except Exception as error:

            print(
                f"VoiceWorker Error : {error}"
            )

            error_text = str(
                error
            ).lower()

            if (
                "timeout" in error_text
                or "timed out" in error_text
                or "wait timed out" in error_text
            ):

                self.timed_out = True
                self.command_captured = False

                print(
                    "Voice command capture timed out."
                )

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


class VisionWorker(QThread):
    """Run cloud Gemini Vision analysis outside the Qt GUI thread."""

    analysis_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, vision_engine, screenshot_path):
        super().__init__()
        self.vision_engine = vision_engine
        self.screenshot_path = str(screenshot_path)

    def run(self):
        try:
            if self.vision_engine is None:
                self.error_occurred.emit(
                    "Vision is not available right now."
                )
                return

            analysis = self.vision_engine.analyze_image(
                self.screenshot_path,
                """
Look at the complete visible desktop screenshot and describe what is
actually visible in simple natural language.

Identify the main application or window and mention only the most important
visible text, buttons, or objects. Keep the response short, clear, and
conversational, normally 2 to 4 sentences.

Do not use Markdown, headings, bullet points, asterisks, hash symbols,
backticks, tables, coordinates, confidence values, or special formatting.
Do not invent anything that is not visible. This is visual understanding
only; do not perform or suggest automation actions.
""".strip()
            )

            self.analysis_ready.emit({
                "success": True,
                "description": str(analysis or "").strip(),
                "objects": [],
                "ocr_words": [],
                "ocr_text": str(analysis or "").strip(),
                "provider": "gemini",
                "model": getattr(
                    self.vision_engine,
                    "model",
                    "",
                ),
            })

        except Exception as error:
            print(
                f"Vision Worker Error : {error}"
            )
            self.error_occurred.emit(
                f"I could not analyze the current screen: {error}"
            )


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


class GeminiLiveAudioWorker(QThread):
    """Bridge the physical microphone/speaker to Gemini Live."""

    connected = Signal()
    failed = Signal(str)
    finished_audio = Signal()

    INPUT_RATE = 16000
    OUTPUT_RATE = 24000
    CHANNELS = 1
    DTYPE = "int16"
    BLOCKSIZE = 512  # 512 samples = 1024 bytes = 32 ms @ 16 kHz mono int16.
    CHUNK_BYTES = 1024

    def __init__(self, live_session, parent=None):
        super().__init__(parent)
        self.live_session = live_session
        self.worker_id = hex(id(self))
        self.generation = 0
        self._stop_requested = False
        self._input_enabled = True
        self._packets_sent = 0
        self._current_audio_level = 0.0

        # Diagnostics & counters for 1011 investigation
        self.captured_packets = 0
        self.valid_pcm_packets = 0
        self.queued_packets = 0
        self.sent_packets = 0
        self.dropped_packets = 0
        self.bytes_captured = 0
        self.bytes_queued = 0
        self.bytes_sent = 0

        # Pacing intervals
        self._last_capture_time = None
        self._last_queue_time = None

        # PCM accumulator to normalize PortAudio callbacks into exact 1024-byte chunks
        self._input_byte_buffer = bytearray()
        self._input_lock = threading.Lock()

        self._output_queue = queue.Queue(maxsize=128)
        self._output_buffer = bytearray()
        self._output_lock = threading.RLock()
        self._input_stream = None
        self._output_stream = None
        self._is_speaker_playing = False
        self._active_response_id = 0
        self._speaking_response_id = 0
        self._invalidated_response_ids = set()
        self._suppress_upcoming_response = False
        print(f"[LIVE DEBUG] worker_id={self.worker_id} worker created")

    def run(self):
        if sd is None:
            self.failed.emit("sounddevice is not available.")
            return

        try:
            if self.live_session is None:
                raise RuntimeError("Gemini Live session is not available.")

            print(f"[LIVE DEBUG] worker_id={self.worker_id} Connecting Gemini Live session...")

            if not self.live_session.start(timeout=15.0):
                error = getattr(self.live_session, "start_error", None)
                raise RuntimeError(
                    str(error or "Gemini Live session failed to start.")
                )

            print(f"[LIVE DEBUG] worker_id={self.worker_id} Gemini Live session connected.")
            self.connected.emit()

            self._input_stream = sd.RawInputStream(
                samplerate=self.INPUT_RATE,
                blocksize=self.BLOCKSIZE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                callback=self._input_callback,
            )

            self._output_stream = sd.RawOutputStream(
                samplerate=self.OUTPUT_RATE,
                blocksize=768,  # 768 samples = 32ms @ 24kHz mono (eliminates OS playback buffer lag)
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                callback=self._output_callback,
            )

            with self._output_stream:
                with self._input_stream:
                    print(f"[LIVE DEBUG] worker_id={self.worker_id} Microphone + speaker streams active.")
                    while not self._stop_requested and not self.isInterruptionRequested():
                        self.msleep(20)

        except Exception as error:
            if not self._stop_requested:
                print(f"[LIVE AUDIO] Runtime error: {error}")
                self.failed.emit(str(error))

        finally:
            self._close_streams()
            print(f"[LIVE DEBUG] worker_id={self.worker_id} worker stopped. audio_packets_sent={self._packets_sent}")
            self.finished_audio.emit()

    def _input_callback(self, indata, frames, time_info, status):
        if self._stop_requested or not self._input_enabled:
            return

        now = time.monotonic()
        dt_capture = (now - self._last_capture_time) if self._last_capture_time else 0.032
        self._last_capture_time = now

        if status:
            pass  # Do not drop audio buffers on benign PortAudio driver flags

        try:
            raw_bytes = bytes(indata)
            if not raw_bytes:
                return

            with self._input_lock:
                self._input_byte_buffer.extend(raw_bytes)
                while len(self._input_byte_buffer) >= self.CHUNK_BYTES:
                    chunk = bytes(self._input_byte_buffer[:self.CHUNK_BYTES])
                    del self._input_byte_buffer[:self.CHUNK_BYTES]

                    self.captured_packets += 1
                    self.bytes_captured += len(chunk)

                    # PCM Validation (Stage 2): mono 16-bit little-endian, exactly 512 samples
                    try:
                        samples = struct.unpack("<512h", chunk)
                        min_sample = min(samples)
                        max_sample = max(samples)
                        zero_count = sum(1 for s in samples if s == 0)
                        zero_pct = (zero_count / 512.0) * 100.0
                        sum_sq = sum(s * s for s in samples)
                        rms = math.sqrt(sum_sq / 512.0)
                        self.valid_pcm_packets += 1

                        # Realtime amplitude calculation for UserSpeechPanel waveform
                        # Speech RMS typically ~500 to ~8000; silence < 200.
                        raw_level = max(0.0, (rms - 120.0) / 4500.0)
                        self._current_audio_level = min(1.0, raw_level)
                    except Exception as val_err:
                        self.dropped_packets += 1
                        print(f"[LIVE ERROR STAGE 2: PCM validation] {val_err}")
                        continue

                    # Queue Enqueue (Stage 3)
                    send_chunk = chunk
                    q_start = time.monotonic()
                    if self.live_session is not None and getattr(self.live_session, "is_connected", False):
                        if self.live_session.send_audio(send_chunk):
                            self.queued_packets += 1
                            self.bytes_queued += len(send_chunk)
                            self._packets_sent += 1
                            self.sent_packets = self._packets_sent
                            self.bytes_sent += len(send_chunk)
                            dt_queue = time.monotonic() - q_start

                            # Diagnostic logging for representative chunks
                            if self.captured_packets in (1, 10, 50) or self.captured_packets % 100 == 0:
                                queue_depth = getattr(getattr(self.live_session, "_audio_queue", None), "qsize", lambda: 0)()
                                session_send_cnt = getattr(self.live_session, "send_packet_count", 0)
                                session_rx_cnt = getattr(self.live_session, "receive_event_count", 0)
                                session_drop_cnt = getattr(self.live_session, "dropped_packet_count", 0)
                                print(
                                    f"[PCM DIAGNOSTIC] packet={self.captured_packets} bytes={len(send_chunk)} exp={self.CHUNK_BYTES} "
                                    f"samples=512 RMS={rms:.2f} min={min_sample} max={max_sample} zeros={zero_pct:.1f}% "
                                    f"cap_int={dt_capture*1000:.1f}ms queue_int={dt_queue*1000:.2f}ms qdepth={queue_depth} speaker_playing={getattr(self, '_is_speaker_playing', False)}"
                                )
                                session_id = getattr(self.live_session, "session_id", "unknown")
                                print(
                                    f"[PCM STATS] session_id={session_id} worker_id={self.worker_id} "
                                    f"captured={self.captured_packets} valid={self.valid_pcm_packets} "
                                    f"queued={self.queued_packets} sent={self.sent_packets} dropped={self.dropped_packets} "
                                    f"bytes_sent={self.bytes_sent} session_sent={session_send_cnt} session_rx={session_rx_cnt} session_dropped={session_drop_cnt} receive_loop_active={getattr(self.live_session, 'is_running', False)}"
                                )
                        else:
                            self.dropped_packets += 1
                    else:
                        self.dropped_packets += 1

        except Exception as error:
            print(f"[LIVE ERROR STAGE 1: PortAudio capture] {error}")

    def _output_callback(self, outdata, frames, time_info, status):
        if status:
            pass

        needed = len(outdata)

        try:
            with self._output_lock:
                while len(self._output_buffer) < needed:
                    try:
                        item = self._output_queue.get_nowait()
                    except queue.Empty:
                        break
                    if item:
                        if isinstance(item, tuple):
                            resp_id, chunk = item
                        else:
                            resp_id, chunk = 0, item

                        if (resp_id > 0 and resp_id in self._invalidated_response_ids) or (resp_id > 0 and resp_id < self._active_response_id):
                            print(f"[LIVE] STALE AUDIO DROPPED: {resp_id}")
                            continue

                        self._output_buffer.extend(chunk)
                        if resp_id > 0:
                            self._speaking_response_id = resp_id

                available = min(len(self._output_buffer), needed)

                if available:
                    outdata[:available] = self._output_buffer[:available]
                    del self._output_buffer[:available]
                    self._is_speaker_playing = True

                if available < needed:
                    outdata[available:needed] = b"\x00" * (needed - available)
                    if available == 0 and self._output_queue.empty():
                        self._is_speaker_playing = False
                        self._speaking_response_id = 0

        except Exception as error:
            print(f"[LIVE AUDIO] Output callback error: {error}")
            try:
                outdata[:] = b"\x00" * needed
            except Exception:
                pass

    def is_output_playing(self) -> bool:
        with self._output_lock:
            return bool(
                getattr(self, "_is_speaker_playing", False)
                or len(self._output_buffer) > 0
                or not self._output_queue.empty()
            )

    def clear_input_buffer(self):
        with self._input_lock:
            self._input_byte_buffer.clear()

    def set_input_enabled(self, enabled: bool):
        """Enable/disable microphone upload without tearing down Live."""
        prev = self._input_enabled
        self._input_enabled = bool(enabled)
        if not self._input_enabled:
            self._current_audio_level = 0.0
            self.clear_input_meter = True
            with self._input_lock:
                self._input_byte_buffer.clear()
            if self.live_session is not None:
                try:
                    self.live_session.clear_pending_audio()
                except Exception:
                    pass
        if prev != self._input_enabled:
            session_id = getattr(self.live_session, "session_id", "unknown") if self.live_session else "none"
            print(
                f"[LIVE DEBUG] session_id={session_id} worker_id={self.worker_id} "
                f"input_enabled={self._input_enabled} input gate {'enabled' if self._input_enabled else 'disabled'}"
            )

    def input_enabled(self) -> bool:
        return bool(self._input_enabled)

    def get_audio_level(self) -> float:
        """Return current normalized microphone amplitude (0.0 to 1.0)."""
        if not self._input_enabled or self._stop_requested:
            return 0.0
        return float(getattr(self, "_current_audio_level", 0.0))

    def enqueue_output(self, audio_data: bytes, response_id: int = 0):
        if self._stop_requested or not audio_data:
            return

        session_id = getattr(self.live_session, "session_id", "unknown") if self.live_session else "unknown"
        with self._output_lock:
            if getattr(self, "_suppress_upcoming_response", False):
                if response_id > 0:
                    self._invalidated_response_ids.add(response_id)
            if response_id > 0 and (response_id in self._invalidated_response_ids or response_id < self._active_response_id):
                print(f"[LIVE STALE] session={session_id} response={response_id} action=enqueue_rejected")
                print(f"[LIVE] STALE AUDIO DROPPED: {response_id}")
                return
            if response_id > self._active_response_id:
                self._active_response_id = response_id

        data = bytes(audio_data)
        item = (response_id, data)
        try:
            self._output_queue.put_nowait(item)
            q_cnt = self._output_queue.qsize()
            print(f"[LIVE PLAYBACK] session={session_id} response={response_id} queued={q_cnt}")
        except queue.Full:
            try:
                self._output_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._output_queue.put_nowait(item)
                q_cnt = self._output_queue.qsize()
                print(f"[LIVE PLAYBACK] session={session_id} response={response_id} queued={q_cnt}")
            except queue.Full:
                pass

    def interrupt_and_flush(self, response_id: int = 0):
        """Immediately discard buffered model audio, stop speaker, and invalidate response."""
        t_detect = time.time()
        with self._output_lock:
            target_id = response_id or self._speaking_response_id
            if target_id > 0:
                self._invalidated_response_ids.add(target_id)
            if target_id > 0 and self._active_response_id <= target_id:
                self._active_response_id = target_id + 1
            while self._active_response_id in self._invalidated_response_ids:
                self._active_response_id += 1
            print(f"[LIVE] STOPPING PLAYBACK")
            print(f"[LIVE] FLUSHING PLAYBACK QUEUE (target_id={target_id})")
            self._output_buffer.clear()
            self._is_speaker_playing = False
            self._speaking_response_id = 0

            while True:
                try:
                    self._output_queue.get_nowait()
                except queue.Empty:
                    break

            print(f"[LIVE] PLAYBACK QUEUE CLEARED")
            t_stop = time.time()
            lat_ms = (t_stop - t_detect) * 1000.0
            print(f"[LIVE INTERRUPT] response={target_id} detected_ms={t_detect*1000:.1f} playback_stop_ms={t_stop*1000:.1f} stop_latency_ms={lat_ms:.2f}")

    def suppress_active_and_next_response(self):
        """Immediately discard buffered model audio, stop speaker, and invalidate upcoming response."""
        with self._output_lock:
            self._suppress_upcoming_response = True
            target_id = self._active_response_id
            if target_id > 0:
                self._invalidated_response_ids.add(target_id)
            if self._active_response_id <= target_id:
                self._active_response_id = target_id + 1
            while self._active_response_id in self._invalidated_response_ids:
                self._active_response_id += 1
            self.interrupt_and_flush(target_id)
        if self.live_session is not None:
            try:
                self.live_session.suppress_active_and_next_response()
            except Exception:
                pass

    def reset_suppression(self):
        """Clear output suppression for future turns without un-invalidating past responses."""
        with self._output_lock:
            self._suppress_upcoming_response = False
            print(f"[LIVE] Suppression state reset on worker {self.worker_id}")

    def set_active_response_id(self, resp_id: int):
        """Set the active response ID and ensure it is not an invalidated response."""
        with self._output_lock:
            target = int(resp_id)
            self._invalidated_response_ids.discard(target)
            self._active_response_id = max(self._active_response_id, target)
            self._suppress_upcoming_response = False

    def clear_output(self):
        """Immediately discard buffered model audio for barge-in without invalidating response IDs."""
        with self._output_lock:
            self._output_buffer.clear()
            self._is_speaker_playing = False
            self._speaking_response_id = 0
            while True:
                try:
                    self._output_queue.get_nowait()
                except queue.Empty:
                    break

    def stop_playback(self):
        """Immediately stop speaker and flush output queue without invalidating response IDs."""
        self.clear_output()

    def clear_pending_audio(self):
        """Alias for clearing pending model audio queue without invalidating response IDs."""
        self.clear_output()

    def stop(self):
        self._stop_requested = True
        self.requestInterruption()
        self.clear_output()

        try:
            if self.live_session is not None:
                self.live_session.stop(timeout=3.0)
        except Exception as error:
            print(f"[LIVE AUDIO] Session stop error: {error}")
        # Notice: self._close_streams() is deliberately NOT called here from the
        # main GUI thread. The worker thread's run() loop terminates upon
        # _stop_requested and cleanly exits the `with stream:` context managers.

    def _close_streams(self):
        self._current_audio_level = 0.0
        for stream_name in ("_input_stream", "_output_stream"):
            stream = getattr(self, stream_name, None)
            if stream is None:
                continue
            setattr(self, stream_name, None)
            try:
                stream.abort()
            except Exception:
                pass
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass


# =====================================================
# Main Window
# =====================================================

class MainWindow(QMainWindow):
    """
    ASTRA-AI Main Window
    """

    gemini_live_input_signal = Signal(str)
    gemini_live_output_signal = Signal(str)
    gemini_live_interrupted_signal = Signal()
    gemini_live_turn_complete_signal = Signal(str, str)
    gemini_live_error_signal = Signal(str)
    gemini_live_closed_signal = Signal()
    gemini_live_go_away_signal = Signal(str)

    def __init__(self):

        super().__init__()

        self._closing = False
        self.shutdown_started = False
        self.gemini_live_audio_worker = None
        self.gemini_live_session = None
        self.gemini_live_active = False
        self.gemini_live_command_handoff = False
        self.gemini_live_mic_enabled = False
        self.gemini_live_output_transcript = ""
        self.gemini_live_user_transcript = ""
        self.gemini_live_last_command = ""

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
        # Realtime voice lifecycle guard
        # ----------------------------------

        # Safety timeout only. Normal unlock happens from the real
        # TTS completion signal or the speaking-state fallback.
        self._startup_unlock_watchdog_ms = 30000
        self._startup_min_fallback_wait_ms = 7000

        # ----------------------------------
        # Backend
        # ----------------------------------

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

        self.semantic_command_planner = None

        self.app_launcher = None

        self.app_closer = None

        self.keyboard_controller = None

        self.mouse_controller = None

        self.window_controller = None

        self.system_controller = None

        # ----------------------------------
        # Screenshot / Screen Recording V1
        # ----------------------------------
        # SystemController owns screenshot capture. ScreenRecorder owns
        # recording. MainWindow owns the voice routing and OSD lifecycle.
        self.screen_recorder = None
        self.system_osd = None

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
        # Gemini Live Voice State
        # ----------------------------------

        self.current_voice_mode = "gemini_live"
        self.manual_listening_requested = False
        self._gemini_live_pending_start = False
        self.gemini_live_mic_enabled = True
        # Continuous Gemini Live guard. This timer only repairs the input
        # path if a turn completion or an unexpected worker state leaves
        # the microphone bridge disabled while the Live session is still
        # healthy. It does not create a new Live session for normal turns.
        self._gemini_live_input_watchdog = None

        # ----------------------------------
        # Physical Laptop Microphone Mute
        # ----------------------------------
        self.physical_microphone_muted = False
        self.microphone_mute_monitor = None
        self._physical_microphone_monitor_started = False
        self.gemini_live_session = None
        self.gemini_live_audio_worker = None
        self.gemini_live_active = False
        self._gemini_live_pending_start = False
        self.gemini_live_command_handoff = False
        self._gemini_live_output_suppressed = False
        self._live_generation = 0
        self._goaway_replacement_in_progress = False
        self._live_recovery_timer = None
        self._live_reconnect_attempts = 0

        # Prevent duplicate command/voice transitions.
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

        # ----------------------------------
        # Capture OSD / Recorder
        # ----------------------------------
        # Keep the OSD independent from the main content layout. It is a
        # top-level Windows-style overlay and must never push UI widgets.
        self.system_osd = SystemOSD(self)
        self.system_osd.hide_osd()

        self.gemini_live_input_signal.connect(
            self._handle_gemini_live_input_transcript
        )
        self.gemini_live_output_signal.connect(
            self._handle_gemini_live_output_transcript
        )
        self.gemini_live_interrupted_signal.connect(
            self._handle_gemini_live_interrupted
        )
        self.gemini_live_turn_complete_signal.connect(
            self._handle_gemini_live_turn_complete
        )
        self.gemini_live_error_signal.connect(
            self._handle_gemini_live_error
        )
        self.gemini_live_closed_signal.connect(
            self._handle_gemini_live_closed
        )
        self.gemini_live_go_away_signal.connect(
            self._handle_gemini_live_go_away
        )

        # Prepare the physical laptop microphone monitor. It starts only
        # after the startup greeting has completed.
        self._initialize_physical_microphone_monitor()

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
        # Center User Speech Panel (Replaces Old Center Microphone)
        # --------------------------------------------------

        self.user_speech_panel = UserSpeechPanel(parent=self.center_container)
        self.mic_widget = self.user_speech_panel

        self.center_layout.addWidget(
            self.user_speech_panel,
            alignment=Qt.AlignBottom | Qt.AlignHCenter
        )

        # The speech panel must remain visually in front of the
        # avatar layer whenever their paint areas overlap.
        self.user_speech_panel.raise_()

        self.center_layout.addSpacing(
            16
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

        # Old center microphone button is removed from the dashboard presentation.
        # self.microphone_button retains a dummy hidden reference for compatibility.
        self.microphone_button = self.user_speech_panel.button()

        # Realtime audio amplitude polling timer (30ms / ~33 FPS) to animate speech waveform
        self._speech_level_timer = QTimer(self)
        self._speech_level_timer.setInterval(30)
        self._speech_level_timer.timeout.connect(self._poll_live_audio_level)
        self._speech_level_timer.start()

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
                32,
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
                14
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

        print("Realtime microphone : Gemini Live (persistent)")

        # ------------------------------------------
        # Voice
        # ------------------------------------------

        self.tts = TextToSpeech()

        # Streaming conversational TTS.  This sits on top of the existing
        # TextToSpeech provider chain and only affects the conversational
        # Gemini voice path.  Command/automation speech remains unchanged.
        self.streaming_tts_manager = StreamingTTSManager(
            self.tts
        )

        # ------------------------------------------
        # Gemini Live Conversation Runtime
        # ------------------------------------------
        self.gemini_live_session = None
        self.gemini_live_audio_worker = None
        self.gemini_live_active = False
        self.gemini_live_command_handoff = False
        # Suppress any model audio that may still arrive after a local
        # laptop command has been recognized.  Gemini Live can begin a
        # response before the input-transcript callback reaches Qt, so
        # clearing the speaker queue alone is not sufficient.
        self._gemini_live_output_suppressed = False
        self.gemini_live_last_command = ""
        self.gemini_live_user_transcript = ""
        self.gemini_live_output_transcript = ""
        self._live_generation = 0
        self._goaway_replacement_in_progress = False
        self._live_recovery_timer = None
        self._live_reconnect_attempts = 0
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

        # Screenshot and recording backends are local and lightweight.
        # They are created once and reused by voice/text command routing.
        self.screen_recorder = ScreenRecorder()

        self.file_finder = FileFinder()

        self.folder_manager = FolderManager()

        self.file_manager = FileManager(
            whisper=None
        )

        self.browser_controller = BrowserController()

        # ------------------------------------------
        # Cloud Vision + OCR Engines
        # ------------------------------------------
        #
        # Vision processing is cloud-based. No local OCR, OpenCV,
        # YOLO, or Vision mouse automation is initialized here.
        # The existing MouseController remains untouched and is still
        # passed to CommandDispatcher for normal mouse commands.
        # ------------------------------------------

        try:

            self.vision = GeminiVision()
            self.ocr = OCREngine(
                language="eng"
            )

            print(
                "Cloud Gemini Vision Engine Ready."
            )

            print(
                f"Vision API Keys : "
                f"{self.vision.total_api_keys()}"
            )

            print(
                f"OCR API Keys : "
                f"{self.ocr.total_api_keys()}"
            )

        except Exception as error:

            self.vision = None
            self.ocr = None

            print(
                f"Cloud Vision/OCR Initialization Error : {error}"
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

        self.semantic_command_planner = SemanticCommandPlanner(
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

            whisper=None,

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
        restart_live=True,
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

            # In direct Gemini Live mode, every completed local command
            # returns control to the persistent realtime voice experience.
            # The old realtime voice restart path is intentionally gone.
            if not self._closing:
                QTimer.singleShot(
                    350,
                    self._restart_gemini_live_after_command
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

        self.ensure_gemini_live_input()

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
                restart_live=True
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
            lambda: self.ensure_gemini_live_input()
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
            restart_live=True
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
            restart_live=True,
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
                restart_live=True,
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
                    restart_live=True
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
                restart_live=True,
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
            restart_live=True,
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
        """Detect natural-language requests to inspect the current screen."""

        cleaned = re.sub(
            r"\s+",
            " ",
            str(text or "").strip().lower(),
        )

        if not cleaned:
            return False

        phrases = (
            "what is on screen",
            "what's on screen",
            "what is on my screen",
            "what's on my screen",
            "what is in my screen",
            "what's in my screen",
            "what is in the screen",
            "what's in the screen",
            "tell me what is on screen",
            "tell me what's on screen",
            "tell me what is on my screen",
            "tell me what's on my screen",
            "tell me what is in my screen",
            "tell me what's in my screen",
            "describe the screen",
            "describe my screen",
            "describe screen",
            "analyze the screen",
            "analyze my screen",
            "analyze screen",
            "analyse the screen",
            "analyse my screen",
            "analyse screen",
            "what do you see on screen",
            "what do you see on my screen",
            "what do you see in my screen",
            "what can you see on screen",
            "what can you see on my screen",
            "what can you see in my screen",
            "look at the screen",
            "look at my screen",
            "read the screen",
            "read my screen",
            "screen-la enna irukku",
            "screen la enna irukku",
            "screen-la enna iruku",
            "screen la enna iruku",
            "screen-la enna irukku nu sollu",
            "screen la enna irukku nu sollu",
            "screen-la enna iruku nu sollu",
            "screen la enna iruku nu sollu",
            "screen ah paaru",
            "screen-a paaru",
            "screen paaru",
            "my screen paaru",
            "my screen la enna irukku",
            "my screen la enna iruku",
        )

        if any(phrase in cleaned for phrase in phrases):
            return True

        # Flexible fallback for natural requests such as
        # "tell me what is visible on my desktop".
        screen_terms = (
            "screen",
            "display",
            "desktop",
            "monitor",
        )

        request_terms = (
            "what is",
            "what's",
            "what do you see",
            "what can you see",
            "tell me",
            "describe",
            "analyze",
            "analyse",
            "look at",
            "read",
        )

        return (
            any(term in cleaned for term in screen_terms)
            and any(term in cleaned for term in request_terms)
        )

    @staticmethod
    def _format_vision_response(analysis):
        """Return concise, human-readable Vision output."""

        analysis = analysis or {}
        description = str(
            analysis.get("description", "") or ""
        ).strip()

        if not description:
            return (
                "I could not identify what is visible on the screen right now."
            )

        return MainWindow._clean_vision_response_for_tts(
            description
        )

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
                "Please check the cloud Gemini Vision setup."
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
                    self.tts.speak(
                        self._clean_vision_response_for_tts(message)
                    )
                    self._unlock_after_speech(
                        restart_live=True,
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

        # --------------------------------------------------------------
        # Capture the current desktop once before starting the cloud worker.
        # The screenshot capture itself is local and lightweight; Gemini
        # processing happens entirely in the background QThread.
        # --------------------------------------------------------------

        screenshot_path = None

        try:
            import tempfile

            # ----------------------------------------------------------
            # Capture the current Windows desktop.
            #
            # IMPORTANT: ImageGrab.grab() returns a PIL Image, whose
            # save() method returns None on success.  The previous code
            # treated that return value as a boolean, so a successful PIL
            # save could be reported as:
            #     Unable to save the current desktop capture.
            #
            # Keep PIL and Qt save handling separate and verify the actual
            # file instead of relying on PIL Image.save()'s return value.
            # ----------------------------------------------------------

            screenshot_image = None
            capture_method = None

            # 1. Preferred: complete Windows virtual desktop.
            try:
                from PIL import ImageGrab

                screenshot_image = ImageGrab.grab(
                    all_screens=True
                )

                if screenshot_image is not None:
                    capture_method = "PIL ImageGrab / all screens"
                    print(
                        "Vision Capture : Full Windows virtual desktop"
                    )

            except Exception as capture_error:
                print(
                    f"Full desktop capture fallback : {capture_error}"
                )

            # 2. PIL primary-screen fallback.  Some Windows display / DPI
            # configurations can reject all_screens=True while normal
            # ImageGrab still works.
            if screenshot_image is None:
                try:
                    from PIL import ImageGrab

                    screenshot_image = ImageGrab.grab()

                    if screenshot_image is not None:
                        capture_method = "PIL ImageGrab / primary screen"
                        print(
                            "Vision Capture : Primary Windows screen fallback"
                        )

                except Exception as capture_error:
                    print(
                        f"Primary screen capture fallback : {capture_error}"
                    )

            # 3. Qt fallback.
            if screenshot_image is None:
                screens = QApplication.screens()

                if not screens:
                    raise RuntimeError(
                        "No display screen is available."
                    )

                geometries = [
                    screen.geometry()
                    for screen in screens
                ]

                left = min(
                    geometry.left()
                    for geometry in geometries
                )
                top = min(
                    geometry.top()
                    for geometry in geometries
                )
                right = max(
                    geometry.right()
                    for geometry in geometries
                )
                bottom = max(
                    geometry.bottom()
                    for geometry in geometries
                )

                width = right - left + 1
                height = bottom - top + 1

                if width <= 0 or height <= 0:
                    raise RuntimeError(
                        f"Invalid desktop geometry: {width}x{height}."
                    )

                screenshot_image = QImage(
                    width,
                    height,
                    QImage.Format.Format_RGB32,
                )

                if screenshot_image.isNull():
                    raise RuntimeError(
                        "Qt could not allocate the desktop capture image."
                    )

                screenshot_image.fill(Qt.black)

                painter = QPainter(screenshot_image)

                try:
                    captured_screen = False

                    for screen, geometry in zip(
                        screens,
                        geometries,
                    ):
                        pixmap = screen.grabWindow(0)

                        if pixmap.isNull():
                            print(
                                f"Vision Capture : Could not grab screen {screen.name()}"
                            )
                            continue

                        painter.drawPixmap(
                            geometry.left() - left,
                            geometry.top() - top,
                            pixmap,
                        )
                        captured_screen = True

                finally:
                    painter.end()

                if not captured_screen:
                    raise RuntimeError(
                        "Qt could not capture any display screen."
                    )

                capture_method = "Qt QScreen fallback"
                print(
                    "Vision Capture : Qt desktop fallback"
                )

            # ----------------------------------------------------------
            # Create a unique destination path.
            # ----------------------------------------------------------

            temp_file = tempfile.NamedTemporaryFile(
                prefix="dheepthi_vision_",
                suffix=".png",
                delete=False,
            )

            screenshot_path = temp_file.name
            temp_file.close()

            screenshot_file = Path(
                screenshot_path
            )

            # ----------------------------------------------------------
            # Save according to the actual image type.
            # PIL Image.save() returns None on success, so NEVER use
            # `if not image.save(...)` for a PIL image.
            # ----------------------------------------------------------

            if hasattr(screenshot_image, "save"):

                if screenshot_image.__class__.__module__.startswith("PIL"):
                    screenshot_image.save(
                        screenshot_path,
                        format="PNG",
                    )
                else:
                    saved = screenshot_image.save(
                        screenshot_path,
                        "PNG",
                    )

                    if saved is False:
                        raise RuntimeError(
                            "Qt could not save the current desktop capture as PNG."
                        )

            else:
                raise RuntimeError(
                    "Desktop capture returned an unsupported image type."
                )

            # ----------------------------------------------------------
            # Validate the physical file before handing it to VisionWorker.
            # This catches silent / partial capture failures early.
            # ----------------------------------------------------------

            if (
                not screenshot_file.exists()
                or screenshot_file.stat().st_size <= 0
            ):
                raise RuntimeError(
                    "Desktop capture file was not created or is empty."
                )

            print(
                f"Vision Capture Saved : {screenshot_path}"
            )
            print(
                f"Vision Capture Size : {screenshot_file.stat().st_size} bytes"
            )
            print(
                f"Vision Capture Method : {capture_method}"
            )

        except Exception as error:
            self.vision_processing = False

            if screenshot_path:
                try:
                    Path(screenshot_path).unlink(
                        missing_ok=True
                    )
                except Exception:
                    pass

            self._on_vision_analysis_error(
                f"I could not capture the current screen: {error}"
            )
            return True

        self.vision_worker = VisionWorker(
            self.vision,
            screenshot_path,
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


    @staticmethod
    def _clean_vision_response_for_tts(message):
        """Remove Markdown/formatting before text reaches TTS."""

        text = str(message or "").strip()

        if not text:
            return ""

        # Markdown links: speak only the human-readable label.
        text = re.sub(
            r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)",
            r"\1",
            text,
        )

        # Fenced and inline code markers.
        text = re.sub(
            r"```[A-Za-z0-9_+.-]*",
            "",
            text,
        )
        text = text.replace(
            "```",
            "",
        )
        text = text.replace(
            "`",
            "",
        )

        # Markdown headings, blockquotes, bullets and numbered lists.
        text = re.sub(
            r"(?m)^\s*#{1,6}\s*",
            "",
            text,
        )
        text = re.sub(
            r"(?m)^\s*>\s?",
            "",
            text,
        )
        text = re.sub(
            r"(?m)^\s*[-+*]\s+",
            "",
            text,
        )
        text = re.sub(
            r"(?m)^\s*\d+[.)]\s+",
            "",
            text,
        )

        # Markdown table formatting.
        text = re.sub(
            r"(?m)^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$",
            "",
            text,
        )
        text = text.replace(
            "|",
            " ",
        )

        # Bold, italic and strike delimiters.
        text = text.replace(
            "**",
            "",
        )
        text = text.replace(
            "__",
            "",
        )
        text = text.replace(
            "~~",
            "",
        )
        text = text.replace(
            "*",
            " ",
        )

        # Standalone underscores are formatting markers. Do not strip
        # underscores inside normal words such as file_name.
        text = text.replace(
            "_",
            " ",
        )
        text = re.sub(
            r"(?<!\w)#+(?!\w)",
            " ",
            text,
        )

        # Final protection against heading markers reaching TTS.
        text = re.sub(
            r"(?m)^\s*#+\s*",
            "",
            text,
        )

        lines = []
        for line in text.splitlines():
            line = re.sub(
                r"[ \t]+",
                " ",
                line,
            ).strip()

            if line:
                lines.append(line)

        text = " ".join(lines)
        text = re.sub(
            r"\s+([,.!?;:])",
            r"\1",
            text,
        )
        text = re.sub(
            r"\s{2,}",
            " ",
            text,
        ).strip()

        return text

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
                speech_message = self._clean_vision_response_for_tts(
                    message
                )

                self.tts.speak(
                    speech_message
                )

                self._unlock_after_speech(
                    restart_live=True,
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
                    self._clean_vision_response_for_tts(error_message)
                )

                self._unlock_after_speech(
                    restart_live=True,
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

        worker_path = None

        if worker is not None:
            worker_path = getattr(
                worker,
                "screenshot_path",
                None,
            )

        self.vision_worker = None

        if worker_path:
            try:
                Path(worker_path).unlink(
                    missing_ok=True
                )
            except Exception as error:
                print(
                    f"Vision screenshot cleanup error : {error}"
                )

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
            restart_live=True,
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

    # =====================================================
    # Screenshot / Screen Recording Voice Routes
    # =====================================================

    @staticmethod
    def _normalized_capture_command(text):
        """Return a lowercase command suitable for local capture routing."""

        return re.sub(
            r"\s+",
            " ",
            str(text or "").strip().lower(),
        )

    def _is_screenshot_command(self, text):
        """Detect explicit screenshot commands before generic AI routing."""

        cleaned = self._normalized_capture_command(text)

        if not cleaned:
            return False

        screenshot_patterns = (
            r"\btake (?:a )?screenshot\b",
            r"\bcapture (?:a )?screenshot\b",
            r"\bscreenshot (?:this|the screen|screen)\b",
            r"\bcapture (?:this|the )?screen\b",
            r"\btake (?:a )?screen ?shot\b",
            r"\bscreen ?shot\b",
        )

        return any(
            re.search(pattern, cleaned)
            for pattern in screenshot_patterns
        )

    def _is_start_recording_command(self, text):
        """Detect explicit screen-recording start commands."""

        cleaned = self._normalized_capture_command(text)

        if not cleaned:
            return False

        patterns = (
            r"\bstart (?:a )?(?:screen )?record(?:ing)?\b",
            r"\bbegin (?:a )?(?:screen )?record(?:ing)?\b",
            r"\brecord (?:the )?(?:screen|desktop)\b",
            r"\bstart screen capture\b",
            r"\bstart capturing (?:the )?(?:screen|desktop)\b",
        )

        return any(
            re.search(pattern, cleaned)
            for pattern in patterns
        )

    def _is_stop_recording_command(self, text):
        """Detect explicit screen-recording stop commands."""

        cleaned = self._normalized_capture_command(text)

        if not cleaned:
            return False

        patterns = (
            r"\bstop (?:the )?(?:screen )?record(?:ing)?\b",
            r"\bend (?:the )?(?:screen )?record(?:ing)?\b",
            r"\bfinish (?:the )?(?:screen )?record(?:ing)?\b",
            r"\bstop screen capture\b",
            r"\bstop capturing (?:the )?(?:screen|desktop)\b",
        )

        return any(
            re.search(pattern, cleaned)
            for pattern in patterns
        )

    def _show_capture_error(self, title, detail):
        """Show a short capture error through the DHEEPTHI OSD and TTS."""

        try:
            if self.system_osd is not None:
                self.system_osd.show_message(
                    title=title,
                    detail=detail,
                    icon="⚠️",
                    duration_ms=2600,
                )
        except Exception as error:
            print(
                f"Capture OSD Error : {error}"
            )

        try:
            self.mic_widget.update_ai_message(detail)
        except Exception:
            pass

        try:
            self.conversation_panel.show_error(detail)
        except Exception:
            pass

        try:
            self.status_label.setText(
                f"Status : {title}"
            )
        except Exception:
            pass

    def _show_capture_osd(self, method_name, *args, **kwargs):
        """Show the capture OSD reliably above the DHEEPTHI window.

        The OSD is a separate top-level Qt tool window.  Keep its presentation
        on the GUI thread and schedule one additional raise/show pass so that
        the Windows-style overlay cannot remain behind the frameless MainWindow
        when a capture command is completed.
        """

        osd = getattr(self, "system_osd", None)

        if osd is None:
            print("Capture OSD Error : SystemOSD is unavailable")
            return False

        try:
            method = getattr(osd, method_name)
            method(*args, **kwargs)

            # The capture handlers always run on the Qt GUI thread.  Process
            # the first paint immediately, then perform a second raise after
            # the current event has completed.
            QApplication.processEvents()

            if osd.isVisible():
                osd.raise_()

            QTimer.singleShot(0, self._raise_capture_osd)
            return True

        except Exception as error:
            print(
                f"Capture OSD Error : {error}"
            )
            return False

    def _raise_capture_osd(self):
        """Raise the capture OSD without activating or stealing focus."""

        if self._closing:
            return

        osd = getattr(self, "system_osd", None)

        if osd is None:
            return

        try:
            if osd.isVisible():
                osd.raise_()
        except RuntimeError:
            self.system_osd = None

    def _handle_screenshot_command(self, text):
        """
        Execute a real screenshot and immediately show the custom OSD.

        Returns True when the command was consumed by this local route.
        """

        if self._closing:
            return True

        print(
            "\n========== DHEEPTHI SCREENSHOT ROUTE =========="
        )
        print(
            f"Voice/Text Command : {text}"
        )
        print(
            "===============================================\n"
        )

        try:
            self.status_label.setText(
                "Status : Taking Screenshot..."
            )
            self.mic_widget.show_conversation(
                text,
                "Taking screenshot..."
            )
            self._set_thinking_state(
                "Screenshot"
            )
            self._set_avatar_state(
                "thinking_laptop"
            )
        except Exception:
            pass

        screenshot_path = None

        try:
            screenshot_path = (
                self.system_controller.take_screenshot()
                if self.system_controller is not None
                else None
            )
        except Exception as error:
            print(
                f"Screenshot Capture Error : {error}"
            )

        if not screenshot_path:
            message = (
                "I could not take the screenshot."
            )

            self._show_capture_error(
                "Screenshot Failed",
                message,
            )

            try:
                self.tts.speak(message)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="error",
            )

            return True

        screenshot_file = Path(
            screenshot_path
        )

        if (
            not screenshot_file.exists()
            or screenshot_file.stat().st_size <= 0
        ):
            message = (
                "The screenshot could not be saved correctly."
            )

            self._show_capture_error(
                "Screenshot Failed",
                message,
            )

            try:
                self.tts.speak(message)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="error",
            )

            return True

        filename = screenshot_file.name

        self._show_capture_osd(
            "show_screenshot",
            filename,
        )

        message = (
            f"Screenshot taken and saved as {filename}."
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

        try:
            self.conversation_label.setText(
                "Screenshot Taken\n\n"
                f"File:\n{filename}\n\n"
                f"Saved to:\n{screenshot_file.parent}"
            )
            self.status_label.setText(
                "Status : Screenshot Taken"
            )
            self._set_avatar_state(
                "success"
            )
            self._set_thinking_state(
                "Inactive"
            )
            self.left_panel.set_speaking(
                "Speaking"
            )
        except Exception:
            pass

        print(
            f"Screenshot Saved : {screenshot_file}"
        )

        try:
            self.tts.speak(
                "Screenshot taken successfully."
            )
        except Exception:
            pass

        self._unlock_after_speech(
            restart_live=True,
            terminal_avatar_state="success",
        )

        return True

    def _handle_start_recording_command(self, text):
        """Start the real screen recorder and keep the recording OSD visible."""

        if self._closing:
            return True

        if self.screen_recorder is None:
            message = (
                "Screen recording is not available."
            )
            self._show_capture_error(
                "Recording Unavailable",
                message,
            )
            try:
                self.tts.speak(message)
            except Exception:
                pass
            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="error",
            )
            return True

        if self.screen_recorder.is_recording():
            message = (
                "Screen recording is already running."
            )

            self._show_capture_osd(
                "start_recording"
            )

            try:
                self.mic_widget.update_ai_message(
                    message
                )
                self.status_label.setText(
                    "Status : Recording"
                )
            except Exception:
                pass

            try:
                self.tts.speak(message)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="success",
            )

            return True

        print(
            "\n========== DHEEPTHI RECORDING START =========="
        )
        print(
            f"Voice/Text Command : {text}"
        )
        print(
            "==============================================\n"
        )

        try:
            self.status_label.setText(
                "Status : Starting Recording..."
            )
            self.mic_widget.show_conversation(
                text,
                "Starting screen recording..."
            )
            self._set_thinking_state(
                "Recording"
            )
            self._set_avatar_state(
                "thinking_laptop"
            )
        except Exception:
            pass

        try:
            output_path = (
                self.screen_recorder.start_recording()
            )
        except Exception as error:
            print(
                f"Screen Recording Start Error : {error}"
            )
            output_path = None

        if not output_path:
            message = (
                "I could not start screen recording."
            )

            self._show_capture_error(
                "Recording Failed",
                message,
            )

            try:
                self.tts.speak(message)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="error",
            )

            return True

        self._show_capture_osd(
            "start_recording"
        )

        filename = Path(
            output_path
        ).name

        message = (
            "Screen recording started."
        )

        try:
            self.mic_widget.update_ai_message(
                message
            )
            self.conversation_panel.show_ai_response(
                message
            )
            self.conversation_label.setText(
                "Recording\n\n"
                f"File:\n{filename}\n\n"
                "Recording is currently active."
            )
            self.status_label.setText(
                "Status : Recording"
            )
            self._set_thinking_state(
                "Inactive"
            )
            self._set_avatar_state(
                "success"
            )
            self.left_panel.set_speaking(
                "Speaking"
            )
        except Exception:
            pass

        print(
            f"Screen Recording Started : {output_path}"
        )

        try:
            self.tts.speak(
                "Screen recording started."
            )
        except Exception:
            pass

        self._unlock_after_speech(
            restart_live=True,
            terminal_avatar_state="success",
        )

        return True

    def _handle_stop_recording_command(self, text):
        """Stop the real recorder and show the saved-recording OSD."""

        if self._closing:
            return True

        if self.screen_recorder is None:
            message = (
                "Screen recording is not available."
            )
            self._show_capture_error(
                "Recording Unavailable",
                message,
            )
            try:
                self.tts.speak(message)
            except Exception:
                pass
            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="error",
            )
            return True

        if not self.screen_recorder.is_recording():
            message = (
                "There is no active screen recording."
            )

            self._show_capture_osd(
                "show_message",
                title="No Active Recording",
                detail=message,
                icon="ℹ️",
                duration_ms=2400,
            )

            try:
                self.mic_widget.update_ai_message(
                    message
                )
                self.status_label.setText(
                    "Status : No Active Recording"
                )
            except Exception:
                pass

            try:
                self.tts.speak(message)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="idle",
            )

            return True

        print(
            "\n========== DHEEPTHI RECORDING STOP =========="
        )
        print(
            f"Voice/Text Command : {text}"
        )
        print(
            "============================================\n"
        )

        try:
            self.status_label.setText(
                "Status : Stopping Recording..."
            )
            self.mic_widget.update_ai_message(
                "Stopping screen recording..."
            )
            self._set_thinking_state(
                "Saving Recording"
            )
            self._set_avatar_state(
                "thinking_laptop"
            )
        except Exception:
            pass

        try:
            elapsed_seconds = (
                self.screen_recorder.get_recording_elapsed_seconds()
            )
        except Exception:
            elapsed_seconds = 0

        try:
            output_path = (
                self.screen_recorder.stop_recording()
            )
        except Exception as error:
            print(
                f"Screen Recording Stop Error : {error}"
            )
            output_path = None

        self._show_capture_osd(
            "stop_recording",
            Path(output_path).name
            if output_path
            else "",
        )

        if not output_path:
            message = (
                "I could not save the screen recording."
            )

            self._show_capture_error(
                "Recording Failed",
                message,
            )

            try:
                self.tts.speak(message)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="error",
            )

            return True

        output_file = Path(
            output_path
        )

        if (
            not output_file.exists()
            or output_file.stat().st_size <= 0
        ):
            message = (
                "The recording file was not saved correctly."
            )

            self._show_capture_error(
                "Recording Failed",
                message,
            )

            try:
                self.tts.speak(message)
            except Exception:
                pass

            self._unlock_after_speech(
                restart_live=True,
                terminal_avatar_state="error",
            )

            return True

        filename = output_file.name

        try:
            duration = self._format_capture_duration(
                elapsed_seconds
            )
        except Exception:
            duration = "00:00"

        message = (
            "Screen recording saved successfully."
        )

        try:
            self.mic_widget.update_ai_message(
                message
            )
            self.conversation_panel.show_ai_response(
                message
            )
            self.conversation_label.setText(
                "Recording Saved\n\n"
                f"File:\n{filename}\n\n"
                f"Duration:\n{duration}\n\n"
                f"Saved to:\n{output_file.parent}"
            )
            self.status_label.setText(
                "Status : Recording Saved"
            )
            self._set_thinking_state(
                "Inactive"
            )
            self._set_avatar_state(
                "success"
            )
            self.left_panel.set_speaking(
                "Speaking"
            )
        except Exception:
            pass

        print(
            f"Screen Recording Saved : {output_file}"
        )
        print(
            f"Recording Duration      : {duration}"
        )

        try:
            self.tts.speak(
                f"Screen recording saved successfully. Duration {duration}."
            )
        except Exception:
            pass

        self._unlock_after_speech(
            restart_live=True,
            terminal_avatar_state="success",
        )

        return True

    @staticmethod
    def _format_capture_duration(seconds):
        """Format a capture duration for the visible MainWindow status."""

        total_seconds = max(
            0,
            int(seconds or 0),
        )

        hours, remainder = divmod(
            total_seconds,
            3600,
        )
        minutes, seconds = divmod(
            remainder,
            60,
        )

        if hours:
            return (
                f"{hours:02d}:"
                f"{minutes:02d}:"
                f"{seconds:02d}"
            )

        return (
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

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

        action_cmd = self._extract_action_command(text)
        if action_cmd:
            text = action_cmd

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
        # Local Screenshot / Recording Commands
        # ------------------------------------------
        # These explicit commands must be consumed locally before
        # multi-command planning, Gemini chat, or generic dispatcher
        # routing. Voice and typed commands therefore use the exact
        # same capture implementation.

        if self._is_stop_recording_command(text):
            self._handle_stop_recording_command(
                original_text
            )
            return

        if self._is_start_recording_command(text):
            self._handle_start_recording_command(
                original_text
            )
            return

        if self._is_screenshot_command(text):
            self._handle_screenshot_command(
                original_text
            )
            return

        # ------------------------------------------
        # Vision Command
        # ------------------------------------------
        # Full screen analysis: readable text + detected objects
        # + coordinates. Existing screenshot commands are untouched.
        # ------------------------------------------

        if self._is_vision_command(text):

            print(
                f"VISION ROUTE SELECTED : {text}"
            )

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

        if not is_multi_command and hasattr(self, "_is_semantic_command_candidate"):
            try:
                chaining_markers = r"\b(?:panni|pannitu|pannittu|seythu|seidu|seithu|thiranthu|eduthu|and\s+then|then|after\s+that|apram|appuram|aduthu)\b"
                if re.search(chaining_markers, text, re.I) and self._is_semantic_command_candidate(text):
                    is_multi_command = True
            except Exception:
                pass

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

                # --------------------------------------------------
                # Force Qt to paint thinking_laptop before the
                # synchronous planner starts. Otherwise the avatar
                # state is requested correctly but the GUI repaint is
                # delayed until planning/execution has completed.
                # --------------------------------------------------
                try:
                    QApplication.processEvents()
                except Exception:
                    pass

                # Prefer SemanticCommandPlanner for multi-step & natural language commands
                if hasattr(self, "semantic_command_planner") and self.semantic_command_planner is not None:
                    semantic_plan = self.semantic_command_planner.plan(text)
                    if semantic_plan and semantic_plan.get("type") == "command" and semantic_plan.get("actions"):
                        self._execute_semantic_plan(semantic_plan, text)
                        return

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

                # Keep the automation avatar explicitly locked to
                # thinking_laptop while the executor is running.
                self._thinking_avatar_mode = "thinking_laptop"
                self._set_avatar_state("thinking_laptop")
                try:
                    QApplication.processEvents()
                except Exception:
                    pass

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
                        restart_live=True,
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
                    # unlock + Gemini Live restart.

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
                    restart_live=True,
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
                    restart_live=True,
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
                restart_live=True,
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
                    restart_live=True
                )

                return

            self.lock_microphone()

            # One session belongs to exactly one conversational voice turn.
            # Starting a new session invalidates any stale queued chunks from
            # a previous turn and keeps the TTS pipeline isolated.
            streaming_session = self.streaming_tts_manager.start_session()

            try:
                if streaming_session is None:
                    raise RuntimeError(
                        "Streaming TTS manager could not start a session"
                    )

                # Gemini now yields text as it arrives.  The StreamingTTSManager
                # consumes those chunks immediately and its dedicated consumer
                # thread starts TTS as soon as a meaningful sentence/clause is
                # available.  This means Gemini generation and TTS playback run
                # in parallel instead of waiting for the complete answer.
                response_chunks = []

                for chunk in self.gemini.generate_response_stream(
                    conversation_message
                ):
                    if chunk is None:
                        continue

                    chunk = str(chunk)
                    if not chunk.strip():
                        continue

                    response_chunks.append(chunk)

                    # Preserve the existing UI behaviour while allowing the
                    # speech pipeline to begin before Gemini finishes.
                    current_reply = "".join(response_chunks).strip()
                    if current_reply:
                        self.mic_widget.update_ai_message(
                            current_reply
                        )

                    try:
                        self._set_thinking_state("Inactive")
                        self.left_panel.set_speaking("Speaking")
                    except Exception:
                        pass

                    self._set_avatar_state("speaking")

                    # Clean only the text being handed to TTS.  The original
                    # streamed text is retained for the conversation UI.
                    speech_chunk = self._clean_vision_response_for_tts(
                        chunk
                    )

                    if speech_chunk:
                        self.streaming_tts_manager.add_chunk(
                            speech_chunk,
                            streaming_session,
                        )

                ai_reply = "".join(response_chunks).strip()

                if not ai_reply:
                    self.streaming_tts_manager.stop()
                    raise RuntimeError(
                        "Gemini returned an empty streaming response"
                    )

                # Flush the final partial sentence.  This only enqueues the
                # remaining text; it does not wait for playback, so the final
                # TTS request continues through the existing provider chain.
                if not self.streaming_tts_manager.finish(
                    streaming_session
                ):
                    raise RuntimeError(
                        "Streaming TTS session became inactive"
                    )

                self._unlock_after_speech(
                    restart_live=True,
                    terminal_avatar_state="success"
                )

                self.status_label.setText(
                    "Status : Gemini AI Completed"
                )

            except Exception as error:

                # Prevent any already-buffered response from leaking into a
                # later conversational turn.  Existing TextToSpeech.stop()
                # also invalidates the active provider request.
                try:
                    self.streaming_tts_manager.stop()
                except Exception:
                    pass

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
                    restart_live=True,
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

            anchor_widget = getattr(self, "user_speech_panel", None)
            if anchor_widget is None or not anchor_widget.isVisible():
                anchor_widget = mic_button

            mic_top_left = anchor_widget.mapTo(
                center,
                QPoint(0, 0)
            )

            mic_x = mic_top_left.x()

            mic_y = mic_top_left.y()

            mic_width = anchor_widget.width()

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
            restart_live=True
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

        self.worker = InitializationWorker()

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
            Gemini Live direct listening
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

        # Start Gemini Live directly after the startup greeting.
        if not getattr(self, "_closing", False):
            QTimer.singleShot(250, self._start_gemini_live_after_startup)
            print(
                "[STARTUP] Gemini Live scheduled AFTER MIC UNLOCK."
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

    def _start_gemini_live_after_startup(self):
        """Start the realtime Gemini Live session after the greeting."""
        if self._closing or getattr(self, "_startup_greeting_active", False):
            return
        if not getattr(self, "_startup_sequence_complete", False):
            QTimer.singleShot(250, self._start_gemini_live_after_startup)
            return

        try:
            self.unlock_microphone()
        except Exception:
            pass

        self._start_physical_microphone_monitor()

        # The physical laptop microphone key is authoritative. If Windows
        # reports the capture endpoint muted, remain in IDLE and wait for the
        # hardware key to be unmuted instead of opening Gemini Live input.
        if self.physical_microphone_muted:
            print("[STARTUP] Physical microphone is muted; keeping DHEEPTHI IDLE.")
            self._set_gemini_live_input_from_physical_mic(False)
            return

        self.gemini_live_mic_enabled = True
        self._gemini_live_pending_start = True
        self.manual_listening_requested = False
        self.processing_voice = False

        print("[STARTUP] Startup gate OPEN | starting Gemini Live directly.")
        QTimer.singleShot(0, self._start_gemini_live_conversation)

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

        # The physical laptop microphone key is authoritative.  Never let
        # a command/TTS completion accidentally unlock the UI while Windows
        # still reports the capture endpoint as muted.
        if getattr(self, "physical_microphone_muted", False):
            self.processing_voice = False
            try:
                self.lock_microphone()
            except Exception:
                pass
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
                    should_listen = bool(
                        getattr(self, "gemini_live_active", False)
                        and not getattr(self, "physical_microphone_muted", False)
                    )
                    set_listening(
                        should_listen
                    )

                mic_widget.update()

        except Exception as error:

            print(
                f"[MIC] MicWidget unlock error | {error}"
            )

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
    # Physical Laptop Microphone Monitor
    # --------------------------------------------------

    def _initialize_physical_microphone_monitor(self):
        """Create the Windows physical microphone mute monitor."""
        if self.microphone_mute_monitor is not None:
            return

        if MicrophoneMuteMonitor is None:
            print(
                "[MIC MONITOR] voice.microphone_monitor is not available; "
                "physical microphone-key monitoring is disabled."
            )
            return

        try:
            monitor = MicrophoneMuteMonitor(
                interval_ms=250,
                parent=self,
            )
            monitor.mute_changed.connect(
                self._handle_physical_microphone_mute_changed
            )
            if hasattr(monitor, "error"):
                monitor.error.connect(
                    self._handle_physical_microphone_monitor_error
                )

            self.microphone_mute_monitor = monitor
            print("[MIC MONITOR] Physical laptop microphone monitor created.")
        except Exception as error:
            self.microphone_mute_monitor = None
            print(f"[MIC MONITOR] Initialization error: {error}")

    def _start_physical_microphone_monitor(self):
        """Start monitoring the physical/default Windows microphone mute state."""
        if self._closing:
            return

        self._initialize_physical_microphone_monitor()
        monitor = self.microphone_mute_monitor
        if monitor is None:
            return

        try:
            if not monitor.isRunning():
                monitor.start()
            self._physical_microphone_monitor_started = True
            print("[MIC MONITOR] Physical laptop microphone monitor started.")

            # Explicitly synchronize the initial endpoint state after the
            # worker has had time to initialize. This prevents a microphone
            # already muted before startup from leaving the UI in LISTENING.
            QTimer.singleShot(400, self._sync_physical_microphone_state)
        except Exception as error:
            print(f"[MIC MONITOR] Start error: {error}")

    @Slot(bool)
    def _handle_physical_microphone_mute_changed(self, muted):
        """Synchronize Gemini Live and the UI with the physical mic mute key."""
        if self._closing:
            return

        muted = bool(muted)

        # Do not discard the first state emitted by the monitor. MainWindow
        # starts with False as a safe default, but Windows may already report
        # the physical microphone as muted when DHEEPTHI starts.
        state_changed = muted != bool(self.physical_microphone_muted)
        self.physical_microphone_muted = muted

        if muted:
            print("[MIC MONITOR] Physical microphone MUTED -> DHEEPTHI IDLE.")
            self._set_gemini_live_input_from_physical_mic(False)
        else:
            if state_changed:
                print("[MIC MONITOR] Physical microphone UNMUTED -> Gemini Live LISTENING.")
            self._set_gemini_live_input_from_physical_mic(True)

    def _sync_physical_microphone_state(self):
        """Apply the monitor's current endpoint mute state on the GUI thread."""
        if self._closing:
            return

        monitor = self.microphone_mute_monitor
        if monitor is None:
            return

        try:
            current = getattr(monitor, "current_muted", None)
            if current is not None:
                self._handle_physical_microphone_mute_changed(bool(current))
        except Exception as error:
            print(f"[MIC MONITOR] Initial state sync error: {error}")

    @Slot(str)
    def _handle_physical_microphone_monitor_error(self, message):
        if self._closing:
            return
        print(f"[MIC MONITOR] {message}")

    def _set_gemini_live_input_from_physical_mic(self, enabled):
        """Apply physical mic state without destroying the Live session."""
        enabled = bool(enabled) and not self.physical_microphone_muted
        self.gemini_live_mic_enabled = enabled

        worker = getattr(self, "gemini_live_audio_worker", None)
        if worker is not None:
            try:
                worker.set_input_enabled(enabled)
            except Exception as error:
                print(f"[MIC MONITOR] Live input gate error: {error}")

        if not enabled:
            # Physical microphone MUTE is the authoritative idle state.
            # Keep Gemini Live alive, but stop uploading microphone audio.
            # Also discard/suppress already-generated speaker audio so the
            # UI remains genuinely idle while the hardware key is muted.
            self._gemini_live_output_suppressed = True
            session = getattr(self, "gemini_live_session", None)
            if session is not None:
                try:
                    session.clear_pending_audio()
                except Exception:
                    pass
            try:
                if worker is not None:
                    worker.clear_input_meter = True
                    worker.clear_output()
            except Exception:
                pass

            session_id = getattr(session, "session_id", "none") if session else "none"
            worker_id = getattr(worker, "worker_id", "none") if worker else "none"
            print(f"[LIVE DEBUG] session_id={session_id} worker_id={worker_id} physical_mic_muted=True input_enabled=False")

            try:
                self.status_label.setText("Status : Microphone Muted")
                self.left_panel.set_listening("Mic Muted")
                self.left_panel.set_speaking("Silent")
                self._set_thinking_state("Inactive")
                self._set_avatar_state("idle")
                self.mic_widget.update_audio_level(0.0)
                if hasattr(self, "user_speech_panel"):
                    self.user_speech_panel.set_state("muted")
            except Exception:
                pass

            # IMPORTANT: do not call MicWidget.set_listening(False) here.
            # In the existing MicWidget implementation that state is not the
            # physical-key lock state. Use the MainWindow's existing lock API
            # so the visible microphone button becomes LOCKED without editing
            # ui/widgets/mic_widget.py.
            try:
                self.lock_microphone()
            except Exception as error:
                print(f"[MIC MONITOR] Mic UI lock error: {error}")
            return

        # Physical mic has just been UNMUTED. If a local laptop command is
        # currently executing, keep Live input gated until that command/TTS
        # lifecycle completes. This prevents a hardware-key change from
        # injecting audio into the automation flow.
        if self.gemini_live_command_handoff:
            try:
                if worker is not None:
                    worker.set_input_enabled(False)
                self.status_label.setText("Status : Command Processing")
                self._set_avatar_state("thinking")
            except Exception:
                pass
            try:
                self.lock_microphone()
            except Exception:
                pass
            return

        # Physical mic has just been UNMUTED. If Live is already connected,
        # open only the microphone input gate; the Live session itself stays
        # alive. The existing MainWindow unlock API controls the button state.
        if self.gemini_live_active and worker is not None:
            try:
                self._gemini_live_output_suppressed = False
                worker.reset_suppression()
                session = self.gemini_live_session
                if session is not None:
                    session.reset_suppression()
                worker.set_input_enabled(True)
                session_id = getattr(session, "session_id", "none") if session else "none"
                worker_id = getattr(worker, "worker_id", "none") if worker else "none"
                print(f"[LIVE DEBUG] session_id={session_id} worker_id={worker_id} physical_mic_muted=False input_enabled=True")
            except Exception as error:
                print(f"[MIC MONITOR] Live resume error: {error}")

            try:
                self.status_label.setText("Status : Gemini Live Listening")
                self.left_panel.set_listening("Listening")
                self.left_panel.set_speaking("Silent")
                self._set_thinking_state("Inactive")
                self._set_avatar_state("listening")
                if hasattr(self, "user_speech_panel"):
                    self.user_speech_panel.set_state("listening")
            except Exception:
                pass

            # IMPORTANT: this is the physical-key -> UI transition.
            # Do not change MicWidget's implementation. MainWindow's existing
            # unlock_microphone() keeps the button visually/interactively
            # UNLOCKED.
            try:
                self.unlock_microphone()
            except Exception as error:
                print(f"[MIC MONITOR] Mic UI unlock error: {error}")
            return

        if self._startup_sequence_complete and not self._startup_greeting_active:
            self._gemini_live_pending_start = True
            QTimer.singleShot(0, self._start_gemini_live_conversation)

    def _stop_physical_microphone_monitor(self):
        """Stop and release the physical microphone monitor."""
        monitor = self.microphone_mute_monitor
        self.microphone_mute_monitor = None
        self._physical_microphone_monitor_started = False

        if monitor is None:
            return

        try:
            monitor.stop()
        except Exception as error:
            print(f"[MIC MONITOR] Stop error: {error}")

        try:
            if monitor.isRunning() and monitor is not QThread.currentThread():
                monitor.wait(1500)
        except Exception:
            pass

        try:
            monitor.deleteLater()
        except Exception:
            pass

    # --------------------------------------------------
    # Start Listening
    # --------------------------------------------------

    def start_listening(self):
        """Toggle the Gemini Live microphone on/off.

        The microphone button is no longer push-to-talk and no longer
        starts a one-shot STT worker. Gemini Live remains the realtime
        conversation engine for the whole session.
        """
        if self._closing or getattr(self, "_startup_greeting_active", False):
            return

        if self.physical_microphone_muted:
            print("[MIC] UI toggle ignored because physical laptop microphone is muted.")
            self._set_gemini_live_input_from_physical_mic(False)
            return

        if not self.gemini_live_active:
            print("[MIC] Gemini Live is not active; starting Live session.")
            self._gemini_live_pending_start = True
            self.gemini_live_mic_enabled = True
            self.processing_voice = False
            QTimer.singleShot(0, self._start_gemini_live_conversation)
            return

        self._toggle_gemini_live_microphone()

    def _toggle_gemini_live_microphone(self):
        """Toggle microphone upload while keeping Gemini Live connected."""
        worker = self.gemini_live_audio_worker
        if worker is None:
            self._gemini_live_pending_start = True
            self.gemini_live_mic_enabled = True
            QTimer.singleShot(0, self._start_gemini_live_conversation)
            return

        self.gemini_live_mic_enabled = not self.gemini_live_mic_enabled
        try:
            worker.set_input_enabled(self.gemini_live_mic_enabled)
        except Exception as error:
            print(f"[MIC] Live microphone toggle error: {error}")

        try:
            if self.gemini_live_mic_enabled:
                self.status_label.setText("Status : Gemini Live Listening")
                self._set_avatar_state("listening")
                self.left_panel.set_listening("Listening")
                self.left_panel.set_speaking("Silent")
                self._set_thinking_state("Inactive")
                self.mic_widget.show_listening()
                self.mic_widget.set_listening(True)
                print("[MIC] Gemini Live microphone ON.")
            else:
                self.status_label.setText("Status : Microphone Off")
                self.left_panel.set_listening("Mic Off")
                self.left_panel.set_speaking("Silent")
                self._set_avatar_state("idle")
                self.mic_widget.set_listening(False)
                self.mic_widget.update_audio_level(0.0)
                print("[MIC] Gemini Live microphone OFF.")
        except Exception:
            pass

    def ensure_gemini_live_input(self):
        """Ensure Gemini Live input is available without overriding the physical mic key."""
        if self._closing:
            return

        self.manual_listening_requested = False

        # The physical laptop microphone key is authoritative. Never reopen
        # the Gemini Live input gate while Windows reports the capture endpoint
        # as muted. The Live session itself remains alive.
        if self.physical_microphone_muted:
            self.gemini_live_mic_enabled = False
            self._set_gemini_live_input_from_physical_mic(False)
            return

        self.gemini_live_mic_enabled = True

        if self.gemini_live_active and self.gemini_live_audio_worker is not None:
            try:
                self.gemini_live_audio_worker.set_input_enabled(True)
            except Exception:
                pass
            self.status_label.setText("Status : Gemini Live Listening")
            try:
                self.mic_widget.show_listening()
                self.mic_widget.set_listening(True)
                self.left_panel.set_listening("Listening")
            except Exception:
                pass
            return

        self._gemini_live_pending_start = True
        QTimer.singleShot(0, self._start_gemini_live_conversation)

    # --------------------------------------------------
    # Gemini Live Conversation
    # --------------------------------------------------

    def _start_gemini_live_input_watchdog(self):
        """Keep the existing Gemini Live microphone bridge armed between turns."""
        if self._closing:
            return
        timer = self._gemini_live_input_watchdog
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(750)
            timer.timeout.connect(self._ensure_gemini_live_input_ready)
            self._gemini_live_input_watchdog = timer
        if not timer.isActive():
            timer.start()

    def _stop_gemini_live_input_watchdog(self):
        timer = self._gemini_live_input_watchdog
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass

    def _ensure_gemini_live_input_ready(self):
        """Re-arm input for the next turn without recreating the Live session."""
        if self._closing or not self.gemini_live_active:
            return
        if self.physical_microphone_muted or self.gemini_live_command_handoff:
            return

        worker = self.gemini_live_audio_worker
        session = self.gemini_live_session
        if worker is None or session is None:
            return

        try:
            # The normal state must remain armed for VAD-driven subsequent
            # turns. Never call end_audio_stream() here; doing so would end
            # the continuous input stream needed for the next utterance.
            if not worker.input_enabled():
                worker.set_input_enabled(True)
                self.gemini_live_mic_enabled = True
                print("[LIVE] Input bridge re-armed for next turn.")

            # If the session exposes is_running(), use it only as a health
            # check. A healthy session is deliberately not restarted.
            is_running = getattr(session, "is_running", None)
            if callable(is_running):
                try:
                    if not bool(is_running()):
                        print("[LIVE] Gemini Live session is no longer running; recovery will be handled by the error/close path.")
                except Exception:
                    pass
        except Exception as error:
            print(f"[LIVE] Continuous input watchdog error: {error}")

    def _start_gemini_live_conversation(self):
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return

        if not self._gemini_live_pending_start:
            return

        # Cancel any pending recovery timer
        if getattr(self, "_live_recovery_timer", None) is not None:
            try:
                self._live_recovery_timer.stop()
            except Exception:
                pass
            self._live_recovery_timer = None

        self._gemini_live_pending_start = False
        self.gemini_live_mic_enabled = not self.physical_microphone_muted
        self.gemini_live_command_handoff = False
        self.gemini_live_last_command = ""
        self.gemini_live_user_transcript = ""
        self.gemini_live_output_transcript = ""
        # CRITICAL: Always reset output suppression on new/recovered session!
        self._gemini_live_output_suppressed = False

        self._stop_gemini_live_conversation(clear_audio=True, restart_live=False)

        try:
            self._live_generation += 1
            gen = self._live_generation
            print(f"[LIVE SESSION] generation={gen} state=starting")

            session = self.gemini.create_live_session(
                voice=getattr(settings, "GEMINI_LIVE_VOICE", "Aoede"),
                on_connected=lambda: self._on_gemini_live_connected(gen),
                on_audio=lambda data, resp_id=0: self._on_gemini_live_audio(data, resp_id, gen),
                on_input_transcript=lambda text: self._on_gemini_live_input_transcript(text, gen),
                on_output_transcript=lambda text, resp_id=0: self._on_gemini_live_output_transcript(text, resp_id, gen),
                on_interrupted=lambda resp_id=0: self._on_gemini_live_interrupted(resp_id, gen),
                on_turn_complete=lambda u, a: self._on_gemini_live_turn_complete(u, a, gen),
                on_error=lambda err: self._on_gemini_live_error(err, gen),
                on_closed=lambda: self._on_gemini_live_closed(gen),
                on_go_away=lambda tl="": self._on_gemini_live_go_away(tl, gen),
                auto_start=False,
            )

            if session is None:
                raise RuntimeError("Gemini Live session could not be created.")

            session.generation = gen
            self.gemini_live_session = session
            self.gemini_live_active = True

            worker = GeminiLiveAudioWorker(session, self)
            worker.generation = gen
            worker.connected.connect(lambda w=worker: self._on_gemini_live_audio_worker_connected(w))
            worker.failed.connect(lambda msg, w=worker: self._on_gemini_live_audio_worker_failed(msg, w))
            worker.finished_audio.connect(lambda w=worker: self._on_gemini_live_audio_worker_finished(w))
            self.gemini_live_audio_worker = worker
            worker.start()
            self._start_gemini_live_input_watchdog()

            session_id = getattr(session, "session_id", hex(id(session)))
            worker_id = getattr(worker, "worker_id", hex(id(worker)))
            print(f"[LIVE DEBUG] session_id={session_id} worker_id={worker_id} physical_mic_muted={self.physical_microphone_muted} Live session created")
            self.status_label.setText("Status : Gemini Live Listening")
            print("[LIVE] Gemini Live conversation started.")

        except Exception as error:
            print(f"[LIVE] Start error: {error}")
            self._goaway_replacement_in_progress = False
            self._handle_gemini_live_error(str(error))

    def _on_gemini_live_audio_worker_connected(self, worker=None):
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False) or not self.gemini_live_active:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return
        if worker is not None and worker is not self.gemini_live_audio_worker:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        if worker is not None and hasattr(worker, "generation") and worker.generation != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return

        self._cancel_live_recovery_timer()
        self._live_reconnect_attempts = 0
        gen = getattr(worker, "generation", self._live_generation)
        print(f"[LIVE SESSION] generation={gen} state=connected")
        if getattr(self, "_goaway_replacement_in_progress", False):
            print("[LIVE LIFECYCLE] Replacement Live session connected")
            print("[LIVE LIFECYCLE] Replacement worker is authoritative")
            self._goaway_replacement_in_progress = False
            print("[LIVE LIFECYCLE] Replacement complete")
        else:
            print("[LIVE LIFECYCLE] Replacement worker is authoritative")

        try:
            input_enabled = not self.physical_microphone_muted
            if self.gemini_live_audio_worker is not None:
                self.gemini_live_audio_worker.set_input_enabled(input_enabled)
            self._gemini_live_output_suppressed = not input_enabled
            self.gemini_live_mic_enabled = input_enabled
            if input_enabled:
                self._start_gemini_live_input_watchdog()
            self.microphone_button.setEnabled(True)
            self.mic_widget.setEnabled(True)
            if input_enabled:
                self.status_label.setText("Status : Listening")
                self._set_avatar_state("listening")
                self.left_panel.set_listening("Listening")
                self.left_panel.set_speaking("Silent")
                self._set_thinking_state("Inactive")
                self.mic_widget.show_listening()
                self.mic_widget.set_listening(True)
                if hasattr(self, "user_speech_panel"):
                    self.user_speech_panel.set_state("listening")
            else:
                self.status_label.setText("Status : Microphone Muted")
                self._set_avatar_state("idle")
                self.left_panel.set_listening("Mic Muted")
                self.left_panel.set_speaking("Silent")
                self._set_thinking_state("Inactive")
                self.microphone_button.setEnabled(False)
                self.mic_widget.setEnabled(True)
                self.mic_widget.set_listening(False)
                if hasattr(self, "user_speech_panel"):
                    self.user_speech_panel.set_state("muted")
        except Exception:
            pass

    def _on_gemini_live_audio_worker_failed(self, message, worker=None):
        if getattr(self, "_closing", False) or getattr(self, "shutdown_started", False):
            return
        if worker is not None and worker is not self.gemini_live_audio_worker:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        if worker is not None and hasattr(worker, "generation") and worker.generation != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        self._goaway_replacement_in_progress = False
        self.gemini_live_error_signal.emit(str(message or "Gemini Live audio failed."))

    def _on_gemini_live_audio_worker_finished(self, worker=None):
        if getattr(self, "_closing", False) or getattr(self, "shutdown_started", False):
            return
        if worker is not None and worker is not self.gemini_live_audio_worker:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        if worker is not None and hasattr(worker, "generation") and worker.generation != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        print("[LIVE] Audio bridge finished.")
        # Do not tear down a healthy Live session merely because the Qt audio
        # bridge emitted finished. The error/closed handlers own full-session
        # recovery.

    INTERRUPTION_PHRASES = {
        "stop",
        "wait",
        "wait wait",
        "wait pannu",
        "wait pannuda",
        "wait pannunga",
        "wait pa",
        "iru",
        "irunga",
        "konjam iru",
        "konjam irunga",
        "one minute",
        "one min",
        "oru nimisham",
        "oru nimisham iru",
        "oru minute",
        "hold on",
        "pothum",
        "podhum",
        "enough",
        "stop talking",
        "pesadha",
        "pesatha",
        "pesama iru",
        "pesama irunga",
        "niruthu",
        "niruthunga",
        "shut up",
        "pause",
        "shh",
        "silence",
    }

    @classmethod
    def _is_interruption_phrase(cls, text: str) -> bool:
        if not text:
            return False
        clean = re.sub(r"[^\w\s]", "", text.strip().lower()).strip()
        if not clean:
            return False
        if clean in cls.INTERRUPTION_PHRASES:
            return True
        words = clean.split()
        if words and all(w in cls.INTERRUPTION_PHRASES for w in words):
            return True
        # Check prefix/short phrase matching (e.g., "dheepthi wait", "hey wait pannu", "stop please")
        if len(words) <= 4:
            trimmed = re.sub(r"^(?:hey|hi|hello|dheepthi|deepti|deepthi)\s+", "", clean).strip()
            trimmed = re.sub(r"\s+(?:please|pa|da|ma)$", "", trimmed).strip()
            if trimmed in cls.INTERRUPTION_PHRASES:
                return True
        return False

    def _is_semantic_command_candidate(self, text: str) -> bool:
        if not text or len(text.strip()) <= 1:
            return False

        clean = text.strip()

        # Check 1: If interruption phrase -> NOT a command candidate
        if self._is_interruption_phrase(clean):
            return False

        # Check 2: Check obvious conversation guard from SemanticCommandPlanner
        if hasattr(self, "semantic_command_planner") and self.semantic_command_planner is not None:
            try:
                if self.semantic_command_planner._is_obviously_conversational(clean):
                    return False
            except Exception:
                pass
        else:
            try:
                from planner.semantic_command_planner import SemanticCommandPlanner
                if SemanticCommandPlanner._is_obviously_conversational(clean):
                    return False
            except Exception:
                pass

        # Check 3: Deterministic local intent check
        if hasattr(self, "intent_detector") and self.intent_detector is not None:
            try:
                local_intent = self.intent_detector.detect_local_intent_only(clean)
                if local_intent not in (None, "ai_chat"):
                    return True
            except Exception:
                pass

        # Check 4: Structural Action Evidence:
        # A valid candidate MUST have an action verb + application/file/media/system target
        lower = clean.lower()

        # 4A. Application + action verb
        app_names_pattern = (
            r"\b(?:chrome|edge|firefox|notepad|calculator|calc|vs\s*code|vscode|"
            r"visual\s*studio\s*code|word|excel|powerpoint|power\s*pnt|explorer|"
            r"file\s*explorer|whatsapp|spotify|discord|teams|terminal|cmd|"
            r"command\s*prompt|paint)\b"
        )
        app_action_pattern = (
            r"\b(?:open|start|launch|run|close|exit|quit|kill|thiranthu|moodu|"
            r"திறந்து|மூடு)\b"
        )
        if re.search(app_names_pattern, lower) and re.search(app_action_pattern, lower):
            return True

        # 4B. Media play structure (song, music, video, artist, YouTube)
        # e.g. "Pavalamalli song play pannu", "play Pavalamalli song", "podu Pavalamalli song"
        media_terms_pattern = r"\b(?:song|songs|video|music|paatu|paattu|track|youtube)\b"
        media_action_pattern = r"\b(?:play|podu|போடு|paadu|பாட்டு|kekkanum|ketka)\b"
        if re.search(media_terms_pattern, lower) and re.search(media_action_pattern, lower):
            return True
        if re.search(r"^(?:play|podu)\s+.+", lower):
            return True

        # 4C. File / folder operations
        # e.g. "Downloads folder open panni report.pdf ah Desktop ku copy pannu"
        file_target_pattern = r"\b(?:folder|file|desktop|downloads|documents|document|pdf|txt|py|doc|docx|csv|report)\b"
        file_action_pattern = r"\b(?:copy|move|delete|create|make|rename|remove|azhi|uruvakku)\b"
        if re.search(file_target_pattern, lower) and re.search(file_action_pattern, lower):
            return True

        # 4D. System control actions
        system_action_pattern = (
            r"\b(?:screenshot|screen\s*shot|screen\s*record|record\s*screen|"
            r"mute|unmute|brightness|volume|shutdown|shut\s*down|restart|"
            r"lock\s*screen)\b"
        )
        if re.search(system_action_pattern, lower):
            return True

        # 4E. Multi-action Tanglish connector with action verbs
        # Must have connector (panni/pannitu/seythu) AND at least one executable action verb
        tanglish_connector = r"\b(?:panni|pannitu|seythu|seithu|செய்து)\b"
        executable_actions = r"\b(?:open|play|copy|create|move|delete|launch|write|type|thiranthu|podu)\b"
        if re.search(tanglish_connector, lower) and re.search(executable_actions, lower):
            return True

        return False

    def _on_gemini_live_connected(self, gen=None):
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
            return
        if gen is not None and gen != self._live_generation:
            print("[LIVE LIFECYCLE] Ignoring stale worker callback")
            return
        print("[LIVE] Gemini Live API connected.")

    def _on_gemini_live_audio(self, audio_data, response_id=0, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                print("[LIVE TURN] Blocked because shutdown_started=True")
                return
            if gen is not None and gen != self._live_generation:
                print(f"[LIVE STALE] session=gen{gen} response={response_id} action=callback_rejected_stale_generation")
                print("[LIVE TURN] Ignoring stale response callback")
                return
            session = self.gemini_live_session
            worker = self.gemini_live_audio_worker

            if (
                getattr(self, "_gemini_live_output_suppressed", False)
                or getattr(self, "gemini_live_command_handoff", False)
                or getattr(self, "processing_voice", False)
                or (session and response_id > 0 and response_id in getattr(session, "_invalidated_response_ids", set()))
                or (worker and response_id > 0 and response_id in getattr(worker, "_invalidated_response_ids", set()))
                or (worker and response_id > 0 and response_id < getattr(worker, "_active_response_id", 0))
            ):
                print(f"[LIVE STALE] session=gen{gen} response={response_id} action=callback_rejected_suppressed")
                print("[LIVE TURN] Ignoring stale response callback")
                return

            now = time.time()
            chunk_len = len(audio_data) if audio_data else 0
            q_depth = worker._output_queue.qsize() if worker else 0
            print(f"[DIAG UI AUDIO CHUNK] t={now:.3f} bytes={chunk_len} qdepth={q_depth} resp_id={response_id}")

            if worker is not None and self.gemini_live_active:
                worker.enqueue_output(audio_data, response_id=response_id)
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_audio: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _on_gemini_live_input_transcript(self, text, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                return
            if gen is not None and gen != self._live_generation:
                return
            now = time.time()
            text_str = str(text or "").strip()
            if not text_str:
                return

            print(f"[PERF] COMMAND_RECEIVED t={now:.3f} text='{text_str}'")
            print(f"[DIAG UI INPUT_TRANSCRIPT] t={now:.3f} text='{text}'")

            worker = self.gemini_live_audio_worker
            session = self.gemini_live_session

            # BARGE-IN INTERRUPTION CHECK:
            # If user speaks an interruption phrase or speaks while model is speaking:
            is_interrupt = self._is_interruption_phrase(text_str)
            is_speaking = False
            if worker and worker.is_output_playing():
                is_speaking = True
            if session and getattr(session, "_is_model_speaking", False):
                is_speaking = True

            if is_interrupt:
                t_detect = time.time()
                print(f"[LIVE] USER INTERRUPTION DETECTED VIA VOICE COMMAND: '{text_str}'")
                interrupted_id = 0
                if session is not None:
                    interrupted_id = session.interrupt_current_response()
                if worker is not None:
                    worker.interrupt_and_flush(response_id=interrupted_id)
                t_stop = time.time()
                lat_ms = (t_stop - t_detect) * 1000.0
                print(f"[LIVE INTERRUPT] response={interrupted_id} detected_ms={t_detect*1000:.1f} playback_stop_ms={t_stop*1000:.1f} stop_latency_ms={lat_ms:.2f}")
                self.gemini_live_interrupted_signal.emit()
                self.gemini_live_input_signal.emit(text_str)
                return

            if is_speaking:
                t_detect = time.time()
                print(f"[LIVE] BARGE-IN DETECTED: User spoke '{text_str}' while model was speaking")
                interrupted_id = 0
                if session is not None:
                    interrupted_id = session.interrupt_current_response()
                if worker is not None:
                    worker.interrupt_and_flush(response_id=interrupted_id)
                t_stop = time.time()
                lat_ms = (t_stop - t_detect) * 1000.0
                print(f"[LIVE INTERRUPT] response={interrupted_id} detected_ms={t_detect*1000:.1f} playback_stop_ms={t_stop*1000:.1f} stop_latency_ms={lat_ms:.2f}")
                self.gemini_live_interrupted_signal.emit()

            # FAST LOCAL DETERMINISTIC COMMAND SUPPRESSION:
            # Only exact single English commands (e.g., "Open Chrome", "Close Notepad")
            # execute locally and should be pre-suppressed. Tanglish, mixed language,
            # and natural requests MUST stream to Gemini Live so it can generate
            # semantic <ACTION> tags or normal conversation without audio interruption.
            is_fast_local_command = False
            if hasattr(self, "intent_detector") and self.intent_detector is not None:
                try:
                    local_intent = self.intent_detector.detect_local_intent_only(text_str)
                    if local_intent not in (None, "ai_chat"):
                        is_multi = False
                        has_tanglish = bool(re.search(r"\b(?:panni|pannu|pannidu|kooda|serthu|apparam|apram|nu|la\b|ah\b|ku\b)\b", text_str, re.I))
                        if hasattr(self, "semantic_command_planner") and self.semantic_command_planner is not None:
                            is_multi = self.semantic_command_planner._is_multi_command(text_str)
                        if not is_multi and not has_tanglish:
                            is_fast_local_command = True
                except Exception as error:
                    print(f"[LIVE RACESAFE] Intent check error: {error}")

            if is_fast_local_command:
                self._gemini_live_output_suppressed = True
                if session is not None:
                    try:
                        session.suppress_active_and_next_response()
                    except Exception as err:
                        print(f"[LIVE] Error suppressing session response: {err}")
                if worker is not None:
                    try:
                        worker.suppress_active_and_next_response()
                    except Exception as err:
                        print(f"[LIVE] Error suppressing worker response: {err}")
                print(f"[LIVE RACESAFE] Deterministic local command detected: '{text_str}' -> Gemini model output suppressed.")

            self.gemini_live_input_signal.emit(text_str)

        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_input_transcript: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _on_gemini_live_output_transcript(self, text, response_id=0, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                print("[LIVE TURN] Blocked because shutdown_started=True")
                return
            if gen is not None and gen != self._live_generation:
                print(f"[LIVE STALE] session=gen{gen} response={response_id} action=callback_rejected_stale_generation")
                print("[LIVE TURN] Ignoring stale response callback")
                return
            session = self.gemini_live_session
            worker = self.gemini_live_audio_worker
            if (
                getattr(self, "_gemini_live_output_suppressed", False)
                or getattr(self, "gemini_live_command_handoff", False)
                or getattr(self, "processing_voice", False)
                or (session and response_id > 0 and response_id in getattr(session, "_invalidated_response_ids", set()))
                or (worker and response_id > 0 and response_id in getattr(worker, "_invalidated_response_ids", set()))
                or (worker and response_id > 0 and response_id < getattr(worker, "_active_response_id", 0))
            ):
                print(f"[LIVE STALE] session=gen{gen} response={response_id} action=callback_rejected_suppressed")
                print("[LIVE TURN] Ignoring stale response callback")
                print(f"[LIVE] DROPPED SUPPRESSED OUTPUT TRANSCRIPT: '{text}' resp_id={response_id}")
                return

            now = time.time()
            print(f"[DIAG UI OUTPUT_TRANSCRIPT] t={now:.3f} text='{text}' resp_id={response_id}")
            self.gemini_live_output_signal.emit(str(text or ""))
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_output_transcript: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _on_gemini_live_interrupted(self, response_id=0, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                return
            if gen is not None and gen != self._live_generation:
                return
            now = time.time()
            worker = self.gemini_live_audio_worker
            playing = worker.is_output_playing() if worker else False
            print(f"[DIAG UI INTERRUPTED CALLBACK] t={now:.3f} source=GeminiServer speaker_playing={playing} resp_id={response_id}")

            # IMMEDIATE SYNCHRONOUS CANCELLATION ON CALLBACK THREAD
            if worker is not None:
                worker.interrupt_and_flush(response_id=response_id or 0)

            self.gemini_live_interrupted_signal.emit()
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_interrupted: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _on_gemini_live_turn_complete(self, user_text, assistant_text, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                return
            if gen is not None and gen != self._live_generation:
                return
            now = time.time()
            print(f"[DIAG UI TURN_COMPLETE] t={now:.3f} user='{user_text}' assistant='{assistant_text}'")
            self.gemini_live_turn_complete_signal.emit(
                str(user_text or ""),
                str(assistant_text or ""),
            )
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_turn_complete: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _on_gemini_live_error(self, error, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                return
            if gen is not None and gen != self._live_generation:
                print("[LIVE LIFECYCLE] Ignoring stale worker callback")
                return
            self.gemini_live_error_signal.emit(str(error or "Gemini Live error."))
        except Exception as err:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_error: {err}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _on_gemini_live_closed(self, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                return
            if gen is not None and gen != self._live_generation:
                print("[LIVE LIFECYCLE] Ignoring stale worker callback")
                return
            self.gemini_live_closed_signal.emit()
        except Exception as err:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_closed: {err}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _on_gemini_live_go_away(self, time_left=None, gen=None):
        try:
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
                return
            if gen is not None and gen != self._live_generation:
                print("[LIVE LIFECYCLE] Ignoring stale worker callback")
                return
            self.gemini_live_go_away_signal.emit(str(time_left or ""))
        except Exception as err:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _on_gemini_live_go_away: {err}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    def _filter_user_speech_display_transcript(self, text: str) -> str:
        """Filter transcript for visual display on UserSpeechPanel only (English, Tamil, Tanglish)."""
        try:
            from ui.widgets.user_speech_panel import filter_user_speech_display_transcript
            return filter_user_speech_display_transcript(text)
        except Exception:
            return str(text or "")

    @Slot(str)
    def _handle_gemini_live_input_transcript(self, text):
        t_cmd_start = time.time()
        try:
            text = str(text or "").strip()
            if not text:
                return

            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                print("[LIVE TURN] Blocked because shutdown_started=True")
                return

            if not self.gemini_live_active:
                print("[LIVE TURN] Suppressed reason=live_inactive")
                return

            print(f"[PERF] TRANSCRIPT_READY t={t_cmd_start:.3f} text='{text}'")

            # If user spoke an interruption word, it was handled by barge-in logic.
            # Do NOT invoke SemanticCommandPlanner!
            if self._is_interruption_phrase(text):
                print(f"[SEMANTIC] PLANNER SKIPPED: CONVERSATION (Interruption '{text}')")
                if hasattr(self, "user_speech_panel"):
                    display_text = self._filter_user_speech_display_transcript(text)
                    self.user_speech_panel.set_transcript(display_text)
                return

            # Gating: If a command is actively executing, ignore subsequent streaming transcript chunks
            if getattr(self, "gemini_live_command_handoff", False) or getattr(self, "processing_voice", False):
                print(f"[LIVE] Gated transcript chunk '{text}' during active command execution.")
                print("[LIVE TURN] Suppressed reason=command_in_progress")
                return

            # Deduplicate identical consecutive transcripts
            if text == getattr(self, "gemini_live_last_command", ""):
                return

            self.gemini_live_user_transcript = text

            try:
                display_text = self._filter_user_speech_display_transcript(text)
                if hasattr(self, "user_speech_panel"):
                    self.user_speech_panel.set_transcript(display_text)
                elif hasattr(self, "mic_widget"):
                    self.mic_widget.update_user_message(display_text)
            except Exception:
                pass

            t_route_start = time.time()
            print(f"[PERF] ROUTING_START t={t_route_start:.3f}")

            # -----------------------------------------------------------------
            # 1. FAST LOCAL DETERMINISTIC PATH:
            # If the command is a deterministic single laptop command:
            # ("Open Chrome", "Open Notepad", "Open Downloads", "Close Notepad",
            #  "Take a screenshot", "Open VS Code", etc.)
            # Check if IntentDetector resolves a deterministic action WITHOUT connectors/Tanglish chaining.
            # -----------------------------------------------------------------
            is_multi_or_tanglish = False
            if hasattr(self, "multi_command_planner") and self.multi_command_planner is not None:
                try:
                    if self.multi_command_planner.is_multi_command(text):
                        is_multi_or_tanglish = True
                except Exception:
                    pass

            if not is_multi_or_tanglish:
                chaining_pattern = (
                    r"\b(?:panni|pannitu|pannittu|seythu|seidu|seithu|thiranthu|ezhuthu|eduthu|maatru|anuppu|apram|appuram|aduthu)\b|"
                    r"\b(?:செய்து|பண்ணி|திறந்து|எடுத்து)\b"
                )
                if re.search(chaining_pattern, text, re.IGNORECASE):
                    is_multi_or_tanglish = True

            local_intent = None
            if hasattr(self, "intent_detector") and self.intent_detector is not None:
                try:
                    local_intent = self.intent_detector.detect_local_intent_only(text)
                except Exception as error:
                    print(f"[LIVE] Local intent check error: {error}")
                    local_intent = None

            # FAST LOCAL MATCH:
            if local_intent not in (None, "ai_chat") and not is_multi_or_tanglish:
                t_route_end = time.time()
                detected_lang = "English"
                if hasattr(self, "semantic_command_planner") and self.semantic_command_planner is not None:
                    detected_lang = self.semantic_command_planner.detect_language(text)
                elif hasattr(SemanticCommandPlanner, "detect_language"):
                    detected_lang = SemanticCommandPlanner.detect_language(text)

                print(f"[PERF] ROUTING_END ROUTE=LOCAL_DETERMINISTIC INTENT={local_intent} ({t_route_end - t_route_start:.3f}s)")
                print(f"[ROUTING] ROUTE=LOCAL_DETERMINISTIC")
                print(f"[LIVE TURN] Suppressed reason=local_deterministic_action")
                print(f"[SEMANTIC] Input: {text}")
                print(f"[SEMANTIC] Language: {detected_lang}")
                print(f"[SEMANTIC] Intent: {local_intent}")
                print(f"[SEMANTIC] Commands: 1. {local_intent}")
                print(f"[SEMANTIC] Dispatch: {local_intent} [FAST LOCAL PATH]")

                self.gemini_live_last_command = text
                self.gemini_live_command_handoff = True
                self._gemini_live_output_suppressed = True

                print("\n========== LIVE -> FAST LOCAL COMMAND ROUTE ==========")
                print(f"Recognized command : {text}")
                print(f"Local intent       : {local_intent}")
                print("=======================================================\n")


                self.processing_voice = True

                worker = self.gemini_live_audio_worker
                if worker is not None:
                    try:
                        worker.clear_output()
                        worker.set_input_enabled(False)
                    except Exception as error:
                        print(f"[LIVE -> COMMAND] Failed to gate Live audio input: {error}")

                self.gemini_live_mic_enabled = False

                t_dispatch_start = time.time()
                print(f"[PERF] DISPATCH_START t={t_dispatch_start:.3f}")
                self.process_command(text)
                t_dispatch_end = time.time()
                print(f"[PERF] DISPATCH_END t={t_dispatch_end:.3f} ({t_dispatch_end - t_dispatch_start:.3f}s)")
                print(f"[PERF] EXECUTION_COMPLETE ROUTE=LOCAL_DETERMINISTIC TOTAL_COMMAND_TIME={t_dispatch_end - t_cmd_start:.3f}s\n")
                return

            # -----------------------------------------------------------------
            # 2. GEMINI LIVE SEMANTIC UNDERSTANDING ROUTE:
            # Let Gemini Live understand the natural / mixed / Tanglish speech.
            # Gemini Live will emit <ACTION>...</ACTION> for automation requests,
            # or a normal conversational response for conversation.
            # -----------------------------------------------------------------
            t_route_end = time.time()
            self._gemini_live_output_suppressed = False
            worker = self.gemini_live_audio_worker
            if worker is not None:
                worker.reset_suppression()
            session = self.gemini_live_session
            if session is not None:
                session.reset_suppression()

            print(f"[PERF] ROUTING_END ROUTE=GEMINI_LIVE ({t_route_end - t_route_start:.3f}s)")
            print(f"[ROUTING] ROUTE=GEMINI_LIVE")
            print(f"[LIVE] User Turn : {text}")
            print(f"[SEMANTIC] Input transcript: {text}")
            try:
                self.status_label.setText("Status : DHEEPTHI Listening")
                self._set_avatar_state("listening")
                self.left_panel.set_listening("Listening")
            except Exception:
                pass

            # SUBMIT USER TURN TO ACTIVE LIVE SESSION
            session_id = getattr(session, "session_id", "none") if session else "none"
            print("[LIVE TURN] New user turn started")
            print(f"[LIVE TURN] Active session={session_id}")

            if session is not None and getattr(session, "_started", False) and not getattr(session, "_closing", threading.Event()).is_set():
                new_resp_id = session.start_user_turn(text)
                if worker is not None:
                    worker.set_active_response_id(new_resp_id)
                print(f"[LIVE TURN] User turn processed (audio-driven, resp_id={new_resp_id})")
                print("[LIVE TURN] Awaiting model response")
            else:
                print("[LIVE TURN] Suppressed reason=no_active_session")
            return


        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _handle_gemini_live_input_transcript: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")
            try:
                if not self._closing and self.gemini_live_active and not self.gemini_live_command_handoff:
                    self.status_label.setText("Status : Listening")
                    self._set_avatar_state("listening")
            except Exception:
                pass

    def _build_dispatch_kwargs_for_semantic_action(
        self,
        intent: str,
        entities: dict,
        raw_text: str,
        is_multi: bool,
    ) -> dict:
        """Translate semantic plan entities to CommandDispatcher kwargs."""
        kwargs = {}
        if intent in {"launch_application", "close_application"}:
            app = (
                entities.get("application")
                or entities.get("app")
                or entities.get("target")
                or entities.get("name")
                or entities.get("entity")
            )
            kwargs["entity"] = app
            kwargs["browser"] = entities.get("browser")
            kwargs["website"] = entities.get("website")
            kwargs["profile"] = entities.get("profile")

        elif intent == "play_youtube":
            query = (
                entities.get("search_query")
                or entities.get("query")
                or entities.get("song")
                or entities.get("video")
                or entities.get("music")
                or entities.get("target")
                or entities.get("entity")
            )
            kwargs["search_query"] = query
            kwargs["entity"] = query
            kwargs["browser"] = entities.get("browser") or "chrome"
            kwargs["profile"] = entities.get("profile")

        elif intent in {"youtube_search", "google_search"}:
            query = (
                entities.get("search_query")
                or entities.get("query")
                or entities.get("target")
                or entities.get("entity")
            )
            kwargs["search_query"] = query
            kwargs["entity"] = query
            kwargs["browser"] = entities.get("browser") or "chrome"
            kwargs["profile"] = entities.get("profile")

        elif intent == "open_website":
            site = (
                entities.get("website")
                or entities.get("url")
                or entities.get("target")
            )
            kwargs["website"] = site
            kwargs["entity"] = site
            kwargs["browser"] = entities.get("browser")

        elif intent in {"open_folder", "create_folder", "delete_folder"}:
            folder = (
                entities.get("folder")
                or entities.get("target")
                or entities.get("name")
                or entities.get("entity")
            )
            kwargs["entity"] = folder

        elif intent in {"copy_folder", "move_folder", "rename_folder"}:
            if "destination" in entities or "to" in entities or "source" in entities:
                kwargs["entity"] = entities
            else:
                kwargs["entity"] = (
                    entities.get("folder")
                    or entities.get("target")
                    or entities.get("name")
                )

        elif intent in {"open_file", "create_file", "delete_file"}:
            f = (
                entities.get("file")
                or entities.get("filename")
                or entities.get("target")
                or entities.get("name")
                or entities.get("entity")
            )
            kwargs["entity"] = f

        elif intent in {"copy_file", "move_file", "rename_file"}:
            if "destination" in entities or "to" in entities or "source" in entities:
                kwargs["entity"] = entities
            else:
                kwargs["entity"] = (
                    entities.get("file")
                    or entities.get("filename")
                    or entities.get("target")
                )

        elif intent in {"code_agent", "write_code"}:
            lang = entities.get("language") or ("python" if "python" in raw_text.lower() else "java")
            task = (
                entities.get("task")
                or entities.get("query")
                or entities.get("description")
                or entities.get("code")
                or ""
            )
            req = f"{lang} program for {task}" if task else raw_text
            kwargs["entity"] = entities
            kwargs["user_text"] = req

        elif intent == "type_text":
            txt = (
                entities.get("text")
                or entities.get("typed_text")
                or entities.get("content")
                or ""
            )
            kwargs["typed_text"] = txt

        elif intent == "press_key":
            kwargs["entity"] = (
                entities.get("key")
                or entities.get("target")
                or ""
            )

        else:
            kwargs["entity"] = (
                entities.get("entity")
                or entities.get("target")
                or entities
            )

        return kwargs

    def _execute_semantic_plan(self, plan: dict, raw_text: str, t_cmd_start: float = None):
        """Execute a validated semantic action plan from SemanticCommandPlanner."""
        actions = plan.get("actions", [])
        if not actions:
            print("[SEMANTIC] COMMAND FAILED")
            print("[SEMANTIC] ERROR: No actions in plan.")
            self._unlock_after_speech(restart_live=True)
            return

        total_actions = len(actions)
        print("\n[SEMANTIC] PLAN RECEIVED")
        print(f"Command       : {raw_text}")
        print(f"Total Actions : {total_actions}")
        for idx, act in enumerate(actions, 1):
            act_intent = act.get('intent', '')
            act_entity = act.get('entities', {}).get('application') or act.get('entities', {}).get('target') or act.get('entities', {}).get('song') or act.get('entities', {}).get('query') or ''
            print(f"  Step {idx}: intent={act.get('intent')} entities={act.get('entities')}")
            print(f"[SEMANTIC PLAN] ACTION {idx}: {act_intent} {act_entity}".strip())
        print()

        self.processing_voice = True
        self.gemini_live_command_handoff = True
        self._gemini_live_output_suppressed = True
        self.lock_microphone()

        # Special case: single code_agent request
        if total_actions == 1 and actions[0].get("intent") in {"code_agent", "write_code"}:
            act = actions[0]
            entities = act.get("entities", {})
            lang = entities.get("language") or "python"
            task = entities.get("task") or ""
            code_req = f"{lang} program for {task}" if task else raw_text
            print("\n[SEMANTIC] ACTION 1/1")
            print("[SEMANTIC] DISPATCHING code_agent")
            print(f"[SEMANTIC] ENTITIES: {entities}")
            self.mic_widget.show_conversation(raw_text, "Generating code...")
            print(f"[SEMANTIC] Starting CodeAgent route for: {code_req}")
            t_exec_end = time.time()
            print(f"[PERF] DISPATCH_END t={t_exec_end:.3f}")
            total_time = (t_exec_end - t_cmd_start) if t_cmd_start else 0.0
            print(f"[PERF] EXECUTION_COMPLETE ROUTE=SEMANTIC_PLANNER TOTAL_COMMAND_TIME={total_time:.3f}s\n")
            self._start_code_agent_route(code_req)
            return

        self.mic_widget.show_conversation(
            raw_text,
            "Executing command..." if total_actions == 1 else "Executing multi-step command..."
        )

        all_success = True
        last_result = None
        failed_info = None

        for idx, action in enumerate(actions, 1):
            intent = action.get("intent")
            entities = action.get("entities", {})

            print(f"\n[SEMANTIC] ACTION {idx}/{total_actions}")
            print(f"[SEMANTIC] DISPATCHING {intent}")
            print(f"[SEMANTIC] ENTITIES: {entities}")
            print(f"[SEMANTIC] Dispatch: Step {idx}/{total_actions} -> {intent} entities={entities}")


            # Visual state updates
            thinking_avatar = self._set_thinking_avatar_for_intent(intent)
            try:
                self.left_panel.set_listening("Idle")
                self._set_thinking_state("Thinking", avatar_state=thinking_avatar)
                self.left_panel.set_speaking("Silent")
                self.status_label.setText(f"Status : Executing {intent}...")
                QApplication.processEvents()
            except Exception:
                pass

            is_multi = (total_actions > 1)
            dispatch_kwargs = self._build_dispatch_kwargs_for_semantic_action(
                intent, entities, raw_text, is_multi
            )

            try:
                result = self.dispatcher.dispatch(
                    intent=intent,
                    multi_command=is_multi,
                    **dispatch_kwargs
                )
                print(f"[SEMANTIC] DISPATCH RESULT: {result}")
            except Exception as exc:
                print("[SEMANTIC] COMMAND FAILED")
                print(f"[SEMANTIC] INTENT: {intent}")
                print(f"[SEMANTIC] ENTITIES: {entities}")
                print(f"[SEMANTIC] ERROR: {exc}")
                all_success = False
                failed_info = (intent, entities, str(exc))
                break

            last_result = result
            success = bool(result.get("success", False)) if isinstance(result, dict) else bool(result)
            if not success:
                err_msg = (
                    result.get("message")
                    or result.get("status")
                    or "Action failed"
                    if isinstance(result, dict)
                    else "Action failed"
                )
                print("[SEMANTIC] COMMAND FAILED")
                print(f"[SEMANTIC] INTENT: {intent}")
                print(f"[SEMANTIC] ENTITIES: {entities}")
                print(f"[SEMANTIC] ERROR: {err_msg}")
                all_success = False
                failed_info = (intent, entities, err_msg)
                break

            print(f"[EXECUTION] ACTION {idx} SUCCESS")

            # If launch_application was executed and next action is a browser action, pause briefly
            if idx < total_actions and intent == "launch_application":
                next_intent = actions[idx].get("intent")
                if next_intent in {"play_youtube", "youtube_search", "open_website", "google_search"}:
                    print("[SEMANTIC] Pausing 1.0s for browser session to be ready...")
                    pause_end = time.time() + 1.0
                    while time.time() < pause_end:
                        try:
                            QApplication.processEvents()
                        except Exception:
                            pass
                        time.sleep(0.05)

        t_exec_end = time.time()
        print(f"[PERF] DISPATCH_END t={t_exec_end:.3f}")
        total_time = (t_exec_end - t_cmd_start) if t_cmd_start else 0.0
        print(f"[PERF] EXECUTION_COMPLETE ROUTE=SEMANTIC_PLANNER TOTAL_COMMAND_TIME={total_time:.3f}s\n")

        if all_success:
            print("[SEMANTIC] COMMAND COMPLETE\n")
            if total_actions == 1:
                status_text = (
                    last_result.get("status_text", "Command Completed")
                    if isinstance(last_result, dict)
                    else "Command Completed"
                )
                message = (
                    last_result.get("message", "Done")
                    if isinstance(last_result, dict)
                    else "Done"
                )
                self.status_label.setText(f"Status : {status_text}")
                self.mic_widget.update_ai_message(message)
                self._set_avatar_state("success")
                self._unlock_after_speech(restart_live=True, terminal_avatar_state="success")
            else:
                reply = f"Completed all {total_actions} steps successfully."
                self.mic_widget.update_ai_message(reply)
                self.status_label.setText("Status : Multi-Command Completed")
                self._set_avatar_state("success")
                self.tts.speak(reply)
                self._unlock_after_speech(restart_live=True, terminal_avatar_state="success")
        else:
            fail_intent, fail_ent, fail_err = failed_info or ("unknown", {}, "Action failed")
            error_msg = f"I could not complete {fail_intent}."
            self.mic_widget.update_ai_message(error_msg)
            self.status_label.setText("Status : Command Failed")
            self._set_avatar_state("error")
            self.tts.speak(error_msg)
            self._unlock_after_speech(restart_live=True, terminal_avatar_state="error")

    def _extract_action_command(self, text: str):
        """Extract standardized English automation command from <ACTION>...</ACTION> tag."""
        if hasattr(self, "semantic_command_planner") and self.semantic_command_planner is not None:
            return self.semantic_command_planner.extract_action_command(text)
        from planner.semantic_command_planner import extract_action_command
        return extract_action_command(text)

    def _route_action_command_to_semantic_pipeline(self, action_cmd: str):
        """
        Send extracted standardized English command to existing semantic understanding
        and execution pipeline:
        action_cmd -> semantic_command_planner.plan() -> _execute_semantic_plan() -> CommandDispatcher
        """
        print(f"[SEMANTIC] Routing extracted command to semantic planner: '{action_cmd}'")
        semantic_plan = None
        if hasattr(self, "semantic_command_planner") and self.semantic_command_planner is not None:
            try:
                semantic_plan = self.semantic_command_planner.plan(action_cmd)
            except Exception as error:
                print(f"[SEMANTIC] Planner error for action command: {error}")
                semantic_plan = None

        if semantic_plan and semantic_plan.get("type") == "command" and semantic_plan.get("actions"):
            self._execute_semantic_plan(semantic_plan, action_cmd)
        else:
            self.process_command(action_cmd)

    @Slot(str)
    def _handle_gemini_live_output_transcript(self, text):
        try:
            if getattr(self, "shutdown_started", False) or self._closing or not text:
                return

            if (
                getattr(self, "_gemini_live_output_suppressed", False)
                or getattr(self, "gemini_live_command_handoff", False)
                or getattr(self, "processing_voice", False)
            ):
                return

            self.gemini_live_output_transcript += text

            # Application-side ACTION extraction layer
            action_cmd = self._extract_action_command(self.gemini_live_output_transcript)
            if action_cmd:
                print(f"[SEMANTIC] Gemini output: {self.gemini_live_output_transcript.strip()}")
                print("[SEMANTIC] ACTION detected")
                print(f"[SEMANTIC] Normalized command: {action_cmd}")

                # Immediately suppress Gemini live audio so it doesn't speak raw action tag
                self.gemini_live_command_handoff = True
                self._gemini_live_output_suppressed = True
                worker = self.gemini_live_audio_worker
                if worker is not None:
                    try:
                        worker.clear_output()
                        worker.set_input_enabled(False)
                    except Exception as error:
                        print(f"[LIVE -> COMMAND] Failed to gate Live audio: {error}")
                self.gemini_live_mic_enabled = False
                self.processing_voice = True

                # Do not display raw <ACTION> tag to user
                try:
                    self.mic_widget.update_ai_message(f"Executing: {action_cmd}")
                except Exception:
                    pass

                self.gemini_live_output_transcript = ""
                self._route_action_command_to_semantic_pipeline(action_cmd)
                return

            if self.physical_microphone_muted:
                return

            try:
                # Do not show incomplete <ACTION> tag in user-facing message
                clean_display = re.sub(r"<ACTION\b[\s\S]*", "", self.gemini_live_output_transcript, flags=re.IGNORECASE).strip()
                if clean_display:
                    self.mic_widget.update_ai_message(clean_display)
                if hasattr(self, "user_speech_panel"):
                    self.user_speech_panel.set_state("speaking")
                self.status_label.setText("Status : DHEEPTHI Speaking")
                self._set_avatar_state("speaking")
                self.left_panel.set_speaking("Speaking")
                self._set_thinking_state("Inactive")
            except Exception:
                pass
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _handle_gemini_live_output_transcript: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    @Slot()
    def _handle_gemini_live_interrupted(self):
        try:
            if getattr(self, "shutdown_started", False) or self._closing:
                return

            worker = self.gemini_live_audio_worker
            playing = worker.is_output_playing() if worker else False
            print(f"[DIAG UI HANDLE INTERRUPTED] t={time.time():.3f} speaker_playing={playing} mic_enabled={self.gemini_live_mic_enabled}")
            if worker is not None:
                worker.clear_output()
                worker.reset_suppression()

            session = self.gemini_live_session
            if session is not None:
                session.reset_suppression()

            self._gemini_live_output_suppressed = False

            if not self.gemini_live_active:
                return

            # Do not disrupt an active desktop automation flow
            if (
                getattr(self, "gemini_live_command_handoff", False)
                or getattr(self, "processing_voice", False)
            ):
                print("[LIVE] Interruption ignored during active command handoff.")
                return

            if self.physical_microphone_muted:
                self._set_gemini_live_input_from_physical_mic(False)
                return

            print("[LIVE] Model response interrupted by user speech.")
            self.gemini_live_output_transcript = ""
            self.status_label.setText("Status : Listening")
            self._set_avatar_state("listening")
            self.left_panel.set_listening("Listening")
            self.left_panel.set_speaking("Silent")
            self.microphone_button.setEnabled(True)
            self.mic_widget.setEnabled(True)
            self.mic_widget.set_listening(True)
            if hasattr(self, "user_speech_panel"):
                self.user_speech_panel.set_state("listening")
            print("[LIVE] LISTENING READY")
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _handle_gemini_live_interrupted: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")
            try:
                self.status_label.setText("Status : Listening")
                self._set_avatar_state("listening")
            except Exception:
                pass

    @Slot(str, str)
    def _handle_gemini_live_turn_complete(self, user_text, assistant_text):
        try:
            if getattr(self, "shutdown_started", False) or self._closing:
                return

            # Do not disrupt an active desktop automation flow
            if (
                getattr(self, "gemini_live_command_handoff", False)
                or getattr(self, "processing_voice", False)
            ):
                print("[LIVE] Turn complete ignored during active command handoff.")
                return

            if user_text:
                self.gemini_live_user_transcript = user_text

            target_assistant_text = assistant_text or self.gemini_live_output_transcript

            # Application-side ACTION extraction check on completed turn
            action_cmd = self._extract_action_command(target_assistant_text)
            if action_cmd:
                print(f"[SEMANTIC] Gemini output: {target_assistant_text.strip()}")
                print("[SEMANTIC] ACTION detected")
                print(f"[SEMANTIC] Normalized command: {action_cmd}")

                self.gemini_live_command_handoff = True
                self._gemini_live_output_suppressed = True
                worker = self.gemini_live_audio_worker
                if worker is not None:
                    try:
                        worker.clear_output()
                        worker.set_input_enabled(False)
                    except Exception as error:
                        print(f"[LIVE -> COMMAND] Failed to gate Live audio: {error}")
                self.gemini_live_mic_enabled = False
                self.processing_voice = True

                try:
                    self.mic_widget.update_ai_message(f"Executing: {action_cmd}")
                except Exception:
                    pass

                self.gemini_live_output_transcript = ""
                self._route_action_command_to_semantic_pipeline(action_cmd)
                return

            # NON-ACTION OUTPUT:
            # Treat as normal conversation. Do not send to automation planner.
            # Do not execute any OS action.
            print(f"[SEMANTIC] Gemini output: {target_assistant_text.strip()}")
            print("[SEMANTIC] Conversation response")

            if target_assistant_text and not getattr(self, "_gemini_live_output_suppressed", False):
                self.gemini_live_output_transcript = target_assistant_text
                try:
                    self.mic_widget.update_ai_message(target_assistant_text)
                except Exception:
                    pass

            if (
                self.gemini_live_active
                and not self.physical_microphone_muted
                and not self.gemini_live_command_handoff
            ):
                # Turn completion must return directly to an armed microphone.
                # Do not stop/recreate the Live session here: Gemini VAD should
                # receive the next utterance on the same bidirectional session.
                worker = self.gemini_live_audio_worker
                if worker is not None:
                    try:
                        self._gemini_live_output_suppressed = False
                        worker.reset_suppression()
                        session = self.gemini_live_session
                        if session is not None:
                            session.reset_suppression()
                        worker.set_input_enabled(True)
                    except Exception as error:
                        print(f"[LIVE] Failed to re-arm input after turn completion: {error}")
                self.gemini_live_mic_enabled = True
                self._start_gemini_live_input_watchdog()
                try:
                    self.status_label.setText("Status : Listening")
                    self._set_avatar_state("listening")
                    self.left_panel.set_listening("Listening")
                    self.left_panel.set_speaking("Silent")
                    self.microphone_button.setEnabled(True)
                    self.mic_widget.setEnabled(True)
                    self.mic_widget.set_listening(True)
                    if hasattr(self, "user_speech_panel"):
                        self.user_speech_panel.set_state("listening")
                    print("[LIVE] LISTENING READY")
                except Exception:
                    pass

            self.gemini_live_output_transcript = ""

        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _handle_gemini_live_turn_complete: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")
            try:
                self.status_label.setText("Status : Listening")
                self._set_avatar_state("listening")
            except Exception:
                pass

    def _cancel_live_recovery_timer(self):
        """Cancel and clean up any pending Live recovery timer."""
        timer = getattr(self, "_live_recovery_timer", None)
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass
            self._live_recovery_timer = None
        self._recovery_timer_pending = False

    def _schedule_live_recovery_timer(self):
        """Schedule controlled retry with exponential backoff and max attempts."""
        if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return
        if getattr(self, "_goaway_replacement_in_progress", False):
            print("[LIVE LIFECYCLE] Reconnect timer suppressed: GoAway replacement in progress")
            return
        if getattr(self, "_recovery_timer_pending", False) or getattr(self, "_live_recovery_timer", None) is not None:
            print("[LIVE LIFECYCLE] Recovery timer already pending, ignoring duplicate request")
            return

        max_attempts = 5
        if self._live_reconnect_attempts >= max_attempts:
            print(f"[LIVE LIFECYCLE] Max recovery attempts ({max_attempts}) reached. Stopping reconnect loop.")
            try:
                self.mic_widget.update_ai_message("Gemini Live connection could not be restored. Please check your network.")
                self._set_avatar_state("error")
                self.status_label.setText("Status : Connection Failed")
            except Exception:
                pass
            return

        self._live_reconnect_attempts += 1
        delays = [1500, 3000, 5000, 8000, 10000]
        delay_ms = delays[min(self._live_reconnect_attempts - 1, len(delays) - 1)]

        self._recovery_timer_pending = True
        print(f"[LIVE DEBUG] Recovery timer scheduled ({delay_ms}ms, attempt {self._live_reconnect_attempts}/{max_attempts})...")

        timer = QTimer(self)
        timer.setSingleShot(True)

        def _on_timeout():
            self._live_recovery_timer = None
            self._recovery_timer_pending = False
            if getattr(self, "shutdown_started", False) or getattr(self, "_closing", False):
                print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
                return
            if getattr(self, "_goaway_replacement_in_progress", False):
                print("[LIVE LIFECYCLE] Reconnect suppressed: GoAway replacement in progress")
                return
            self._gemini_live_pending_start = True
            self._start_gemini_live_conversation()

        timer.timeout.connect(_on_timeout)
        self._live_recovery_timer = timer
        timer.start(delay_ms)

    @Slot(str)
    def _handle_gemini_live_error(self, message):
        try:
            if getattr(self, "shutdown_started", False) or self._closing:
                print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
                return

            if getattr(self, "_goaway_replacement_in_progress", False):
                print("[LIVE LIFECYCLE] Live error ignored: GoAway replacement in progress")
                return

            print(f"[LIVE] Gemini Live error: {message}")
            handoff = self.gemini_live_command_handoff
            self.gemini_live_active = False
            self._stop_gemini_live_conversation(clear_audio=True, restart_live=False)

            if handoff:
                return

            try:
                self.mic_widget.update_ai_message(
                    "Sorry, Gemini Live is unavailable right now."
                )
                self._set_avatar_state("error")
                self.status_label.setText("Status : Gemini Live Error")
            except Exception:
                pass

            if getattr(self, "shutdown_started", False) or self._closing:
                print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
                return

            # Rotate key on 1011 / quota / internal errors so recovery does not loop on an exhausted key
            if hasattr(self, "gemini") and self.gemini is not None:
                err_str = str(message or "").lower()
                if "1011" in err_str or "quota" in err_str or "resource" in err_str or "internal" in err_str:
                    print("[LIVE] Rotating Gemini API key on error recovery...")
                    self.gemini.rotate_api_key()

            if not self.physical_microphone_muted:
                self._schedule_live_recovery_timer()
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _handle_gemini_live_error: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

    @Slot()
    def _handle_gemini_live_closed(self):
        try:
            if getattr(self, "shutdown_started", False) or self._closing:
                print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
                return

            if getattr(self, "_goaway_replacement_in_progress", False):
                print("[LIVE LIFECYCLE] Live closed ignored: GoAway replacement in progress")
                return

            if not self.gemini_live_command_handoff:
                print("[LIVE] Gemini Live session closed.")
        except Exception as error:
            import traceback
            print(f"[CRITICAL LIVE ERROR] In _handle_gemini_live_closed: {error}")
            print(f"[CRITICAL LIVE TRACEBACK]\n{traceback.format_exc()}")

        self.processing_voice = False
        self.manual_listening_requested = False
        self.gemini_live_mic_enabled = not self.physical_microphone_muted
        self.unlock_microphone()

        if getattr(self, "shutdown_started", False) or self._closing:
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return

        if getattr(self, "_goaway_replacement_in_progress", False):
            return

        if not self._closing:
            self._gemini_live_output_suppressed = False
            self._schedule_live_recovery_timer()

    @Slot(str)
    def _handle_gemini_live_go_away(self, time_left=""):
        if getattr(self, "shutdown_started", False) or self._closing:
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            return

        if getattr(self, "_goaway_replacement_in_progress", False):
            print("[LIVE LIFECYCLE] Replacement already in progress")
            return

        print(f"[LIVE LIFECYCLE] GoAway detected (time_left={time_left})")
        print(f"[LIVE SESSION] generation={self._live_generation} state=replacing")
        print("[LIVE LIFECYCLE] Starting controlled replacement")
        self._goaway_replacement_in_progress = True

        # Prevent recovery timers from racing
        self._cancel_live_recovery_timer()

        print("[LIVE LIFECYCLE] Waiting for old worker/session to stop")
        self._stop_gemini_live_conversation(clear_audio=True, restart_live=False)
        print("[LIVE LIFECYCLE] Old worker/session fully stopped")

        if getattr(self, "shutdown_started", False) or self._closing:
            print("[LIVE LIFECYCLE] Reconnect suppressed because shutdown_started=True")
            self._goaway_replacement_in_progress = False
            return

        print("[LIVE LIFECYCLE] Starting replacement Live session")
        self._gemini_live_pending_start = True
        self._start_gemini_live_conversation()

    def _stop_gemini_live_conversation(self, clear_audio=True, restart_live=False):
        """Stop the current Live session; restart_live is kept for compatibility and ignored."""
        self._stop_gemini_live_input_watchdog()
        self._live_generation += 1
        print(f"[LIVE SESSION] generation={self._live_generation} state=stopped")
        worker = self.gemini_live_audio_worker
        session = self.gemini_live_session
        self.gemini_live_active = False
        self.gemini_live_audio_worker = None
        self.gemini_live_session = None

        if worker is not None:
            try:
                # Disconnect signals to prevent stale callbacks from reaching MainWindow
                for sig in (worker.connected, worker.failed, worker.finished_audio):
                    try:
                        sig.disconnect()
                    except Exception:
                        pass

                if clear_audio:
                    worker.clear_output()
                worker.stop()
                if worker.isRunning() and worker is not QThread.currentThread():
                    worker.wait(3000)
            except Exception as error:
                print(f"[LIVE] Audio worker stop error: {error}")

        if session is not None:
            try:
                session.on_connected = None
                session.on_audio = None
                session.on_input_transcript = None
                session.on_output_transcript = None
                session.on_interrupted = None
                session.on_turn_complete = None
                session.on_error = None
                session.on_closed = None
                session.on_go_away = None
                session.stop(timeout=3.0)
            except Exception as error:
                print(f"[LIVE] Session stop error: {error}")

        try:
            if self.gemini is not None:
                self.gemini.close_live_session()
        except Exception as error:
            print(f"[LIVE] Gemini client Live cleanup error: {error}")

    def _restart_gemini_live_after_command(self):
        """
        Return to realtime conversation after the existing local command/TTS
        flow completes.  A healthy Gemini Live session is NEVER recreated
        here; only its microphone input gate is re-enabled.
        """
        if getattr(self, "shutdown_started", False) or self._closing or getattr(self, "_startup_greeting_active", False):
            return

        self.processing_voice = False
        self.manual_listening_requested = False

        # The physical laptop mute state remains authoritative.
        if self.physical_microphone_muted:
            self.gemini_live_command_handoff = False
            self._gemini_live_output_suppressed = True
            self.gemini_live_mic_enabled = False
            self._set_gemini_live_input_from_physical_mic(False)
            return

        worker = self.gemini_live_audio_worker
        session = self.gemini_live_session

        # Preferred path: keep the existing Live session + audio bridge.
        if (
            self.gemini_live_active
            and worker is not None
            and session is not None
            and worker.isRunning()
        ):
            try:
                worker.clear_output()
                worker.reset_suppression()
                session = self.gemini_live_session
                if session is not None:
                    session.reset_suppression()
                worker.set_input_enabled(True)
                self._gemini_live_output_suppressed = False
                self.gemini_live_command_handoff = False
                self.gemini_live_mic_enabled = True
                self._gemini_live_pending_start = False

                self.unlock_microphone()
                self.status_label.setText("Status : Gemini Live Listening")
                self._set_avatar_state("listening")
                self.left_panel.set_listening("Listening")
                self.left_panel.set_speaking("Silent")
                self._set_thinking_state("Inactive")
                self.microphone_button.setEnabled(True)
                self.mic_widget.setEnabled(True)
                self.mic_widget.show_listening()
                self.mic_widget.set_listening(True)
                self._start_gemini_live_input_watchdog()

                print("[COMMAND -> LIVE] Existing Gemini Live session resumed; no reconnect.")
                return
            except Exception as error:
                # Only recover by creating a new Live session if the existing
                # bridge is genuinely unavailable.  This fallback does not
                # change the command execution path.
                print(f"[COMMAND -> LIVE] Failed to resume existing Live session: {error}")

        # Recovery path for an actually closed/failed Live session.
        self.gemini_live_command_handoff = False
        self._gemini_live_output_suppressed = False
        self.gemini_live_mic_enabled = True
        self._gemini_live_pending_start = True
        self.unlock_microphone()
        print("[COMMAND -> LIVE] Gemini Live session unavailable; starting recovery session.")
        QTimer.singleShot(0, self._start_gemini_live_conversation)

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
            if hasattr(self, "user_speech_panel"):
                self.user_speech_panel.update_audio_level(level)

        except Exception:

            pass

    def _poll_live_audio_level(self):
        """Thread-safe UI poll for Gemini Live microphone PCM audio level."""
        if getattr(self, "_closing", False) or getattr(self, "shutdown_started", False):
            return
        worker = getattr(self, "gemini_live_audio_worker", None)
        panel = getattr(self, "user_speech_panel", None)
        if panel is None:
            return
        if worker is not None and getattr(worker, "_input_enabled", False):
            level = worker.get_audio_level()
            panel.update_audio_level(level)
        else:
            panel.update_audio_level(0.0)

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
        microphone/TTS/Live lifecycle.
        """

        try:

            # =================================================
            # Local Screenshot / Recording Commands
            # =================================================
            # Conversation-panel commands must use the exact same local
            # capture route as voice commands.  Do this before entity
            # extraction or CommandDispatcher so recording/screenshot
            # actions cannot fall through to launch_application or CodeAgent.

            if intent == "take_screenshot":
                self._handle_screenshot_command(
                    original_text
                )
                return

            if intent == "start_screen_recording":
                self._handle_start_recording_command(
                    original_text
                )
                return

            if intent == "stop_screen_recording":
                self._handle_stop_recording_command(
                    original_text
                )
                return

            # Also keep a defensive phrase check here. This protects the
            # conversation panel if an older/cached detector returns a
            # generic intent for an explicit capture phrase.

            if self._is_stop_recording_command(text):
                self._handle_stop_recording_command(
                    original_text
                )
                return

            if self._is_start_recording_command(text):
                self._handle_start_recording_command(
                    original_text
                )
                return

            if self._is_screenshot_command(text):
                self._handle_screenshot_command(
                    original_text
                )
                return

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
                restart_live=True,
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
            restart_live=True,
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
                    restart_live=True
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

    def _shutdown_gemini_live_synchronously(self):
        """
        Synchronously and sequentially shut down Gemini Live before goodbye Edge TTS starts.
        Zero Gemini Live audio, transcripts, or callbacks may occur after this begins.
        """
        self.shutdown_started = True
        self._closing = True
        self._live_generation = getattr(self, "_live_generation", 0) + 1
        self._cancel_live_recovery_timer()
        self._goaway_replacement_in_progress = False
        self.gemini_live_active = False
        self._gemini_live_pending_start = False
        self.gemini_live_command_handoff = True
        self._gemini_live_output_suppressed = True

        if hasattr(self, "_speech_level_timer"):
            try:
                self._speech_level_timer.stop()
            except Exception:
                pass

        # 1. Input disabled
        worker = getattr(self, "gemini_live_audio_worker", None)
        session = getattr(self, "gemini_live_session", None)
        if worker is not None:
            try:
                worker.set_input_enabled(False)
            except Exception:
                pass
        self._stop_gemini_live_input_watchdog()
        print("[LIVE SHUTDOWN] Input disabled")

        # 2. New transcripts blocked
        if session is not None:
            try:
                session.on_input_transcript = None
                session.on_output_transcript = None
                session.on_turn_complete = None
            except Exception:
                pass
        print("[LIVE SHUTDOWN] New transcripts blocked")

        # 3. Active response invalidated
        if session is not None:
            try:
                session.interrupt_current_response()
            except Exception:
                pass
        print("[LIVE SHUTDOWN] Active response invalidated")

        # 4. Playback stopped
        if worker is not None:
            try:
                worker.stop_playback()
            except Exception:
                pass
        print("[LIVE SHUTDOWN] Playback stopped")

        # 5. Playback queue flushed
        if worker is not None:
            try:
                worker.clear_output()
            except Exception:
                pass
        print("[LIVE SHUTDOWN] Playback queue flushed")

        # 6. Receive loop stopping
        print("[LIVE SHUTDOWN] Receive loop stopping")

        # 7. Live session closing
        print("[LIVE SHUTDOWN] Live session closing")
        if session is not None:
            try:
                session.on_connected = None
                session.on_audio = None
                session.on_interrupted = None
                session.on_go_away = None
                session.on_error = None
                session.on_closed = None
                session.stop(timeout=2.0)
            except Exception as error:
                print(f"[LIVE SHUTDOWN] Session stop error: {error}")
            self.gemini_live_session = None

        try:
            if getattr(self, "gemini", None) is not None:
                self.gemini.close_live_session()
        except Exception as error:
            print(f"[LIVE SHUTDOWN] Gemini client close error: {error}")

        # 8. Worker stopping
        print("[LIVE SHUTDOWN] Worker stopping")
        if worker is not None:
            try:
                try:
                    worker.connected.disconnect()
                except Exception:
                    pass
                try:
                    worker.failed.disconnect()
                except Exception:
                    pass
                try:
                    worker.finished_audio.disconnect()
                except Exception:
                    pass
                worker.stop()
                if worker.isRunning() and worker is not QThread.currentThread():
                    worker.wait(2000)
            except Exception as error:
                print(f"[LIVE SHUTDOWN] Audio worker stop error: {error}")
            self.gemini_live_audio_worker = None

        # 9. Worker stopped
        print("[LIVE SHUTDOWN] Worker stopped")

        # 10. Live session fully stopped
        print("[LIVE SHUTDOWN] Live session fully stopped")

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

        print("[DHEEPTHI SHUTDOWN] Starting goodbye TTS")

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
        # Prevent new voice work.
        # ----------------------------------------------

        self.manual_listening_requested = False
        self.processing_voice = False


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

            # Idempotency check: if shutdown is already started, ignore subsequent close attempts
            if getattr(self, "shutdown_started", False):
                if event is not None:
                    event.ignore()
                return

            self.shutdown_started = True
            self._closing = True
            print("[DHEEPTHI SHUTDOWN] shutdown_started=True")

            if hasattr(self, "_speech_level_timer"):
                try:
                    self._speech_level_timer.stop()
                except Exception:
                    pass

            # Synchronously and sequentially tear down Gemini Live BEFORE goodbye TTS
            self._shutdown_gemini_live_synchronously()

            self._begin_goodbye_shutdown(
                event
            )

            # IMPORTANT:
            # Do not let Qt destroy the window while
            # goodbye avatar/TTS is still running.
            if event is not None:
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
                    "Closing Cloud Vision Engine..."
                )

                vision.close()

                self.vision = None

                print(
                    "Cloud Vision Engine closed successfully."
                )

        except Exception as error:

            print(
                f"Cloud Vision Engine Cleanup Error : {error}"
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
        # PHYSICAL MICROPHONE MONITOR
        # ==================================================

        try:
            self._stop_physical_microphone_monitor()
        except Exception as error:
            print(f"Physical microphone monitor cleanup error : {error}")

        # ==================================================
        # GEMINI LIVE CONVERSATION
        # ==================================================

        try:
            self._gemini_live_pending_start = False
            self.gemini_live_command_handoff = True
            self._stop_gemini_live_conversation(
                clear_audio=True,
                restart_live=False,
            )
        except Exception as error:
            print(
                f"Gemini Live Cleanup Error : {error}"
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
        # SCREEN RECORDING / OSD
        # ==================================================

        try:
            screen_recorder = getattr(
                self,
                "screen_recorder",
                None,
            )

            if screen_recorder is not None:
                if screen_recorder.is_recording():
                    print(
                        "Stopping active screen recording..."
                    )
                    screen_recorder.stop_recording()

            system_osd = getattr(
                self,
                "system_osd",
                None,
            )

            if system_osd is not None:
                system_osd.hide_osd()
                system_osd.close()

        except Exception as error:
            print(
                f"Capture OSD/Recorder Cleanup Error : {error}"
            )

        # ==================================================
        # TEXT TO SPEECH
        # ==================================================

        try:

            streaming_tts_manager = getattr(
                self,
                "streaming_tts_manager",
                None
            )

            if streaming_tts_manager is not None:
                streaming_tts_manager.close()

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

        worker_path = getattr(
            worker,
            "screenshot_path",
            None,
        ) if worker is not None else None

        self.vision_worker = None

        if worker_path:
            try:
                Path(worker_path).unlink(
                    missing_ok=True
                )
            except Exception as error:
                print(
                    f"Vision screenshot cleanup error : {error}"
                )

        print(
            "VisionWorker stopped asynchronously; "
            "continuing final shutdown."
        )

        QTimer.singleShot(
            0,
            self.close
        )

