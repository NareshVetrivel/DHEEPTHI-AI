# Module Design — DHEEPTHI-AI

This document provides a detailed module-by-module design specification for DHEEPTHI-AI V1, describing real source directories, files, class structures, responsibilities, and dependencies.

---

## 1. `app/` — Application Bootstrap & Runtime Entry

- **Module Purpose:** Application initialization, global exception handling, Qt message filtering, and window lifecycle bootstrap.
- **Files:**
  - `app/main.py`: Main entry point. Configures Windows AppUserModelID (`ASTRA.AI.Desktop.v1`), installs Qt message handler (`dheepthi_qt_message_handler`), sets window icons, instantiates `MainWindow`, and starts the Qt event loop (`app.exec()`).
- **Key Classes / Functions:** `main()`, `dheepthi_qt_message_handler()`.
- **Dependencies:** `PySide6.QtWidgets`, `PySide6.QtCore`, `ctypes`, `ui.main_window.MainWindow`.
- **Implementation Status:** **Implemented & Verified**.

---

## 2. `config/` — Configuration & Environment Settings

- **Module Purpose:** Centralized application configuration loaded from environment variables (`.env`).
- **Files:**
  - `config/settings.py`: Defines default model configurations, API keys, VAD sensitivity parameters, window geometry defaults, and indexing directories.
- **Key Settings:**
  - `GEMINI_MODEL = "gemini-3.8-flash"`
  - `GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"`
  - `GEMINI_LIVE_VOICE = "Aoede"`
  - `GEMINI_LIVE_SILENCE_DURATION_MS = 600`
  - `GEMINI_PLANNER_PRIMARY_MODEL = "gemini-3.8-flash"`
  - `GEMINI_API_KEY_1..4`
- **Dependencies:** `python-dotenv`, `os`.
- **Implementation Status:** **Implemented & Verified**.

---

## 3. `ai/` — Cloud Intelligence, Live Audio Session, & Memory

- **Module Purpose:** Manages real-time bidirectional WebSocket sessions, conversational text completions, cognitive memory hierarchy, and affective state modeling.
- **Files:**
  - `ai/gemini_client.py`: Implements `GeminiLiveSession` (asynchronous WebSocket worker managing bidirectional PCM streaming, server VAD events, and barge-in interruptions) and `GeminiClient` (multi-key rotation pool for 4 keys, fallback planning, prompt building, and conversation history).
  - `ai/memory_manager.py`: Coordinates 5-tiered memory hierarchy; executes regex-based credential scrubbing (`CREDENTIAL_PATTERNS`); extracts facts across education, work, family, and tasks.
  - `ai/emotion_engine.py`: Affective state machine tracking valence, arousal, and rapport across moods (*neutral*, *happy*, *caring*, *hurt*, *annoyed*, *playful*); applies 15-minute inactivity decay.
  - `ai/personality_context_builder.py`: Synthesizes dynamic context blocks (~250–300 tokens) injecting emotional directives and verified user facts into Gemini prompts.
- **Key Classes:** `GeminiLiveSession`, `GeminiClient`, `MemoryManager`, `EmotionEngine`, `PersonalityContextBuilder`.
- **Dependencies:** `google.genai`, `groq`, `database.database_manager`, `asyncio`, `threading`, `re`.
- **Implementation Status:** **Implemented & Verified**.

---

## 4. `database/` — Relational SQLite Persistence

- **Module Purpose:** Thread-safe SQLite persistence for indexed applications, indexed files, conversation history, user profiles, memories, and emotional logs.
- **Files:**
  - `database/database_manager.py`: Encapsulates all SQLite interactions. Configures connection with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`. Manages schema migration and 14 relational tables:
    - `applications`, `aliases`, `files`, `folders`, `conversation_context`, `user_context`, `command_history`, `emotional_state`, `emotion_logs`, `memory_episodes`, `people`, `personal_memories`, `user_profiles`, `tasks`.
- **Key Classes:** `DatabaseManager`, `CommandRow`.
- **Dependencies:** `sqlite3`, `pathlib.Path`, `threading.RLock`.
- **Implementation Status:** **Implemented & Verified**.

---

## 5. `planner/` — Semantic Planning & Command Dispatch

- **Module Purpose:** Converts natural language speech transcripts into structured action plans and routes validated commands to local automation controllers.
- **Files:**
  - `planner/semantic_command_planner.py`: Dedicated planner mapping transcripts into structured JSON plans. Distinguishes commands from conversation. Implements `extract_action_command()`.
  - `planner/command_dispatcher.py`: Central routing hub forwarding validated intents to controllers. Coordinates streaming TTS fallbacks.
  - `planner/intent_detector.py`: Fast local regex and fuzzy matching intent classifier (`RapidFuzz`).
  - `planner/entity_extractor.py`: Extracts target applications, file names, URLs, and numbers.
  - `planner/multi_command_planner.py`: Decomposes chained spoken requests into sequential execution steps.
  - `planner/multi_command_executor.py`: Executes sequential plans with status tracking.
  - `planner/action_models.py`: Dataclass models (`ActionStep`, `ActionPlan`, `ActionStatus`).
  - `planner/command_normalizer.py`: Normalizes spoken entities and corrects phonetic ASR errors.
- **Key Classes:** `SemanticCommandPlanner`, `CommandDispatcher`, `IntentDetector`, `EntityExtractor`, `MultiCommandPlanner`, `MultiCommandExecutor`.
- **Dependencies:** `RapidFuzz`, `re`, `automation.*`, `productivity_agent.*`, `code_agent.*`.
- **Implementation Status:** **Implemented & Verified**.

---

## 6. `automation/` — Windows Operating System Automation

- **Module Purpose:** Deterministic interaction with Windows OS, processes, windows, files, and peripherals.
- **Files:**
  - `automation/app_launcher.py`: Launches Windows executables via Start Menu shortcuts, Registry paths, or system commands.
  - `automation/app_closer.py`: Graceful window close via Win32 messages; fallback process kill via `psutil`.
  - `automation/application_scanner.py`: Background scanner indexing Start Menu directories and Registry uninstall keys.
  - `automation/application_finder.py`: Fuzzy matching spoken application names against indexed records (`RapidFuzz`).
  - `automation/browser_controller.py`: Browser navigation, Google searches, and YouTube playback via Chrome/Edge.
  - `automation/playwright_controller.py`: Persistent Chromium automation via Playwright CDP debugging port.
  - `automation/file_system_agent.py`: Central filesystem orchestrator handling search, selection, and confirmed execution.
  - `automation/file_finder.py`: Searches local SQLite file index and disk directories.
  - `automation/file_indexer.py`: Background thread indexing user directories (Desktop, Documents, Downloads, etc.).
  - `automation/file_manager.py`: Performs copy, move, delete (`Send2Trash`), rename, compression, and extraction.
  - `automation/folder_manager.py`: Directory creation, deletion, and Windows Explorer shell opening.
  - `automation/keyboard_controller.py`: Virtual keyboard typing and key simulation with window focus verification (`pywinauto`, `pyautogui`).
  - `automation/mouse_controller.py`: Mouse click, right-click, double-click, and scroll automation (`pyautogui`).
  - `automation/window_controller.py`: Window focus, minimization, maximization, restoration, and title extraction (`win32gui`, `pywinauto`).
  - `automation/system_controller.py`: Master volume control (`pycaw`), brightness control, lock screen, shutdown/restart, screenshots, and webcam capture.
  - `automation/screen_recorder.py`: Screen video recording using MSS and OpenCV (`cv2`).
- **Dependencies:** `pyautogui`, `pywinauto`, `pywin32`, `pycaw`, `screen_brightness_control`, `psutil`, `Send2Trash`, `mss`, `cv2`.
- **Implementation Status:** **Implemented & Verified**.

---

## 7. `ff_agent/` — Safe File & Folder Agent

- **Module Purpose:** High-level filesystem workflow coordinator enforcing candidate disambiguation and path safety.
- **Files:**
  - `ff_agent/agent.py`: Implements `FileFolderAgent`; coordinates flow: context $\rightarrow$ candidate selection $\rightarrow$ path resolution $\rightarrow$ confirmation $\rightarrow$ execution $\rightarrow$ verification.
  - `ff_agent/safety.py`: Enforces path safety boundaries (`SafetyManager`); blocks changes to `C:\Windows`, `System32`, root drives.
  - `ff_agent/context_resolver.py`: Resolves ambiguous filenames and ordinal references ("the second file").
  - `ff_agent/planner.py`: Plans filesystem modification sequences.
  - `ff_agent/verifier.py`: Verifies post-execution state (file exists at target, deleted file removed).
  - `ff_agent/models.py`: Data definitions (`AgentResult`, `AgentContext`, `AgentStatus`).
- **Key Classes:** `FileFolderAgent`, `SafetyManager`, `ContextResolver`, `ExecutionVerifier`.
- **Implementation Status:** **Implemented & Verified**.

---

## 8. `productivity_agent/` — Microsoft Word COM Automation

- **Module Purpose:** Dedicated automation suite for Microsoft Word document generation and editing.
- **Files:**
  - `productivity_agent/word/agent.py`: High-level orchestration layer (`WordAgent`); converts commands to structured operations.
  - `productivity_agent/word/automation.py`: Direct Win32 COM automation (`WordAutomation`); uses `win32com.client.Dispatch("Word.Application")`.
  - `productivity_agent/word/verifier.py`: Document state verifier (`WordVerifier`); validates active document status and page count.
  - `productivity_agent/word/commands.py`: Command constants and argument signatures.
- **Key Classes:** `WordAgent`, `WordAutomation`, `WordVerifier`.
- **Dependencies:** `win32com.client`, `comtypes`.
- **Implementation Status:** **Implemented & Verified**.

---

## 9. `code_agent/` — Autonomous Programming Agent

- **Module Purpose:** Cloud-assisted source code generation and local execution with self-repair feedback loops.
- **Files:**
  - `code_agent/agent.py`: Implements `CodeAgent`; queries Groq (`openai/gpt-oss-20b`); saves source files to `Desktop/DHEEPTHI_program/Python` or `Desktop/DHEEPTHI_program/Java`; runs programs via `subprocess` (30s timeout); re-prompts with compiler stderr on failure up to 3 attempts.
- **Key Classes:** `CodeAgent`.
- **Dependencies:** `groq`, `subprocess`, `pathlib.Path`.
- **Implementation Status:** **Implemented & Verified**.

---

## 10. `voice/` — Audio I/O, Hardware Mute, & Multi-Engine TTS

- **Module Purpose:** Manages physical microphone mute monitoring, local speech fallback engines, and unified TTS synthesis.
- **Files:**
  - `voice/microphone_monitor.py`: Queries Windows Core Audio COM (`IAudioEndpointVolume.GetMute()`) every 250 ms.
  - `voice/text_to_speech.py`: Unified TTS manager with cancellation and request tracking; orchestrates fallback cascade.
  - `voice/edge_tts_engine.py`: Cloud neural TTS using Microsoft Edge (`edge-tts`).
  - `voice/piper_tts_engine.py`: Fully offline neural TTS using local Piper ONNX model (`models/piper/en_US-hfc_female-medium.onnx`).
  - `voice/pyttsx3_tts_engine.py`: Windows SAPI5 TTS fallback.
  - `voice/streaming_tts_manager.py`: Coordinates chunked speech playback for streaming responses.
  - `voice/groq_recognizer.py`: Cloud STT fallback using Groq `whisper-large-v3-turbo` over direct `httpx` multipart transport.
  - `voice/speech_recognition.py`: *Empty stub (0 bytes)* — legacy listener removed in favor of Gemini Live.
- **Key Classes:** `MicrophoneMuteMonitor`, `TextToSpeech`, `EdgeTTSEngine`, `PiperTTSEngine`, `Pyttsx3TTSEngine`, `GroqRecognizer`.
- **Dependencies:** `comtypes`, `sounddevice`, `edge-tts`, `piper-tts`, `onnxruntime`, `pyttsx3`, `pygame`, `httpx`.
- **Implementation Status:** **Implemented & Verified**.

---

## 11. `vision/` — Screen Understanding & Cloud OCR

- **Module Purpose:** Screen understanding, visual element identification, and OCR text extraction using Gemini Cloud Vision.
- **Files:**
  - `vision/gemini_vision.py`: Implements `GeminiVision`; captures screenshots and sends images to Gemini Vision with multi-key rotation.
  - `vision/ocr.py`: Implements `OCREngine`; uses Gemini Vision cloud API to extract text lines and search keywords.
- **Key Classes:** `GeminiVision`, `OCREngine`.
- **Dependencies:** `google.genai`, `config.settings`.
- **Implementation Status:** **Implemented & Verified**.

---

## 12. `ui/` — PySide6 Graphical User Interface

- **Module Purpose:** Desktop HUD presentation, particle animations, audio waveform visualizer, and user telemetry.
- **Files:**
  - `ui/main_window.py`: Central window controller (15,700+ lines); coordinates `VoiceWorker`, `ChatWorker`, `CodeAgentWorker`, `GeminiLiveAudioWorker`, and UI updates.
  - `ui/splash_screen.py`: Startup splash screen with canvas particle twinkles and smooth cross-dissolve transition.
  - `ui/widgets/user_speech_panel.py`: Translucent glassmorphic HUD panel displaying real-time user speech transcripts and 9-bar reactive audio waveform.
  - `ui/widgets/avatar_widget.py`: Animated avatar reflecting emotional states and speaking/listening modes.
  - `ui/widgets/system_osd.py`: On-screen display overlay for volume and brightness notifications.
  - `ui/widgets/conversation_panel.py`: Scrollable chat turn bubble list.
  - `ui/widgets/file_selection_panel.py`: Interactive candidate list for ambiguous file search results.
  - `ui/widgets/status_tile.py`: Real-time hardware and network status tiles.
  - `ui/widgets/status_metric_tile.py`: Metric tiles displaying indexed file counts and memory turn numbers.
  - `ui/widgets/mic_widget.py`: Interactive microphone status button.
  - `ui/styles/theme.py`: Cyberpunk/glassmorphism dark palette constants and stylesheets.
- **Dependencies:** `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`, `sounddevice`.
- **Implementation Status:** **Implemented & Verified**.

---

## 13. `workers/` — Background Startup Worker

- **Module Purpose:** Asynchronous application startup tasks.
- **Files:**
  - `workers/initialization_worker.py`: Implements `InitializationWorker` (`QThread`); scans Start Menu applications and synchronizes the local filesystem index while reporting progress to the splash screen.
- **Key Classes:** `InitializationWorker`.
- **Dependencies:** `PySide6.QtCore.QThread`, `automation.application_scanner`, `automation.file_indexer`.
- **Implementation Status:** **Implemented & Verified**.