# Runtime Flows — DHEEPTHI-AI

This document provides an end-to-end trace of runtime execution flows in DHEEPTHI-AI V1, detailing function calls, data models, thread boundaries, and state transitions across subsystems.

---

## 1. Application Startup & Shutdown Lifecycles

### 1.1 Startup Lifecycle
1. **Entry Point Execution (`app/main.py`):**
   - Invokes `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ASTRA.AI.Desktop.v1")`.
   - Calls `qInstallMessageHandler(dheepthi_qt_message_handler)` to suppress harmless title-bar hover QFont point-size warnings.
   - Instantiates `QApplication` and loads application icon `ui/assets/dheepthi.ico`.
   - Creates `MainWindow` (`ui/main_window.py:MainWindow.__init__()`).
   - Displays maximized window via `window.showMaximized()`.
   - Schedules `QTimer.singleShot(0, window.initialize_application)`.
2. **Asynchronous Initialization Worker (`workers/initialization_worker.py`):**
   - `MainWindow.initialize_application()` instantiates `SplashScreen` (`ui/splash_screen.py`) with canvas particle animation.
   - Spawns `InitializationWorker` (`QThread`):
     - Phase 1: Executes `ApplicationScanner.scan_installed_applications()` querying `winreg` and Start Menu `.lnk` files; inserts records into SQLite table `applications`.
     - Phase 2: Executes `FileIndexer.scan_and_index()` scanning standard user folders (`Desktop`, `Documents`, `Downloads`, `Pictures`, `Videos`, `Music`); inserts records into SQLite table `files`.
   - Upon receiving `finished_success` signal, `MainWindow` executes a cross-dissolve animation hiding the splash screen and presenting the active dashboard.
3. **Audio Subsystem & Live Session Initialization:**
   - Spawns `MicrophoneMuteMonitor` thread (`voice/microphone_monitor.py`) polling Windows Core Audio COM.
   - Creates `GeminiLiveSession` (`ai/gemini_client.py`) connecting to Google GenAI Live endpoint via WebSocket.
   - Starts `GeminiLiveAudioWorker` (`ui/main_window.py`) capturing microphone audio via `sounddevice.InputStream`.

### 1.2 Shutdown Lifecycle
1. **Close Event Interception:**
   - User triggers window close button or speaks shutdown command; `MainWindow.closeEvent()` is invoked.
2. **Audio & WebSocket Teardown:**
   - Stops `GeminiLiveAudioWorker`; shuts down audio streams cleanly.
   - Invokes `GeminiLiveSession.stop()`; cancels `_receive_loop` and `_audio_send_loop` tasks; closes WebSocket connection.
   - Halts `MicrophoneMuteMonitor` thread.
3. **Database & Memory Flush:**
   - Flushes pending in-memory context; executes SQLite `PRAGMA wal_checkpoint(TRUNCATE)`; closes database connections via `DatabaseManager`.
4. **Process Exit:**
   - Qt event loop terminates via `app.quit()`; Python interpreter exits cleanly.

---

## 2. Voice-Input-to-Response Lifecycle

```text
[User Speech] -> [Physical Mic] -> [sounddevice 16kHz PCM] -> [MicrophoneMuteMonitor]
                                                                        |
                                                     Muted? (No) <------+------> (Yes: Disarm Uplink)
                                                                 |
                                                                 v
                                             [GeminiLiveSession._audio_send_loop]
                                                                 |
                                                      (WebSocket Uplink)
                                                                 v
                                                 [Google GenAI Cloud Server]
                                                                 |
                                            (Server VAD: 600ms Silence Detected)
                                                                 |
                                                                 v
                                             [GeminiLiveSession._receive_loop]
                                                                 |
                                        +------------------------+------------------------+
                                        | (24kHz Audio Downlink)                          | (Text Transcript)
                                        v                                                 v
                     [GeminiLiveAudioWorker.enqueue_output]                  [MainWindow HUD Update]
                                        |                                                 |
                                        v                                                 v
                           [sounddevice Playback Out]                         [UserSpeechPanel Display]
```

### Barge-In Interruption Flow:
1. While `sounddevice` playback is actively outputting downlink audio chunks, the user begins speaking.
2. The Google GenAI server VAD detects speech onset and sends a `voice_activity(START)` or `vad_signal(START)` event over the WebSocket.
3. `GeminiLiveSession._receive_loop()` intercepts this event and calls `interrupt_current_response()`.
4. The signal triggers `GeminiLiveAudioWorker.interrupt_and_flush()`:
   - Sets internal playback stop event.
   - Flushes the audio chunk queue (`self._output_queue.clear()`).
   - Zeroes the active audio buffer in sub-millisecond time.
   - Increments active response generation ID, ensuring subsequent late-arriving cloud packets from the interrupted turn are discarded (`[LIVE STALE] enqueue_rejected`).

---

## 3. Semantic Command Planning & Execution

```text
[Output Transcript] 
        |
        v
[Contains <ACTION> Tag?] 
        |
        +---> (No)  -> Pure conversation; audio playback completes.
        |
        +---> (Yes) -> [MainWindow._extract_action_command()]
                             |
                             v
                       [Filter <ACTION> from UserSpeechPanel HUD]
                             |
                             v
                       [SemanticCommandPlanner.plan_command()]
                             |
                             v
                       [ActionPlan: ActionStep(action, params)]
                             |
                             v
                       [CommandDispatcher.dispatch()]
                             |
                             +---> "launch_application"  -> [AppLauncher.launch()]
                             +---> "close_application"   -> [AppCloser.close_app()]
                             +---> "copy_file"           -> [FileFolderAgent.execute()]
                             +---> "create_document"     -> [WordAgent.create_document()]
                             +---> "play_youtube"        -> [BrowserController.play_youtube()]
                             +---> "set_volume"          -> [SystemController.set_volume()]
                             +---> "code_agent"          -> [CodeAgent.generate_and_execute()]
```

---

## 4. Filesystem Safety & Verification Flow

1. **Pre-flight Check (`ff_agent/safety.py`):**
   - `SafetyManager.is_safe_path(target_path)` checks path against blacklisted system roots (`C:\Windows`, `C:\Windows\System32`, `C:\Program Files`, root volumes `C:\`).
   - If blocked, raises `SafetyViolationError` and aborts execution.
2. **Disambiguation & Candidate Resolution (`ff_agent/context_resolver.py`):**
   - Queries `FileFinder.find_files(query)`.
   - If 0 matches: Returns `FileNotFound` status.
   - If 1 match: Resolves absolute canonical path.
   - If $>1$ matches: Populates `FileSelectionPanel` in GUI, awaiting user click or spoken ordinal selection.
3. **Execution & Recycle Bin Safeguard (`automation/file_manager.py`):**
   - Non-destructive actions (copy, rename, zip) execute via standard Python `shutil` / `os`.
   - Destructive deletions invoke `Send2Trash.send2trash(path)` to ensure files are recoverable from the Windows Recycle Bin.
4. **Post-Action Verification (`ff_agent/verifier.py`):**
   - `ExecutionVerifier.verify()` checks that the created/copied file exists on disk and is non-zero in size, or that the deleted file no longer exists.

---

## 5. Memory Persistence & Affective State Lifecycle

1. **Turn Persistence (`ai/memory_manager.py`):**
   - Upon turn completion, `MemoryManager` receives `(user_command, assistant_response)`.
   - Scans text against `CREDENTIAL_PATTERNS` regex rules; scrubs passwords, API keys, tokens, and credit cards.
   - Inserts record into SQLite table `conversation_context`.
2. **Fact & Entity Extraction:**
   - Extracts structured facts (e.g., college, degree, workplace, relationship entities) using regex pattern matchers.
   - Upserts into tables `personal_memories`, `user_context`, and `people`.
3. **Dynamic Prompt Synthesis (`ai/personality_context_builder.py`):**
   - Queries `DatabaseManager` for active profile facts and emotional mood state.
   - Formats a compact context block (~250–300 tokens):
     ```text
     23. ACTIVE CONTEXT & VERIFIED MEMORY:
     - User prefers to be addressed as: Naresh
     - Education: MCA second year at Sona College of Technology
     - Mood directive: Natural, warm, friendly Tanglish.
     ```
   - Injected into Gemini Live system instruction.
4. **Affective Mood Decay:**
   - `EmotionEngine._apply_inactivity_decay()` checks elapsed time. If $>15$ minutes have passed, extreme negative moods (*hurt*, *annoyed*) are reset to *neutral*.

---

## 6. Multi-Tier Error Recovery & Fallbacks

| Failure Event | Intercepting Module | Recovery / Fallback Behavior |
|:---|:---|:---|
| **Gemini Live Connection Timeout / Drop** | `GeminiLiveSession` | Reconnects WebSocket; falls back to Groq STT (`whisper-large-v3-turbo`) and text chat |
| **Gemini API Key Quota Exhaustion (HTTP 429)** | `GeminiClient` | Invokes `rotate_api_key()`, switching to next key in pool (`GEMINI_API_KEY_1..4`) |
| **Model Name Deprecation / Error** | `GeminiClient` | Cascades through planner hierarchy: `gemini-3.8-flash` $\rightarrow$ `gemini-3.6-flash` $\rightarrow$ `gemini-3.5-flash` $\rightarrow$ Groq |
| **Cloud TTS Synthesis Failure** | `voice/text_to_speech.py` | Cascades: Edge-TTS $\rightarrow$ Local Piper ONNX $\rightarrow$ Windows SAPI5 (`pyttsx3`) |
| **Groq SDK Cloudflare Blocking (HTTP 403)** | `voice/groq_recognizer.py` | Uses direct `httpx` multipart requests with browser user-agent |
| **Generated Code Compilation Failure** | `code_agent/agent.py` | Feeds compiler error trace back into Groq LLM; retries up to 3 attempts |
| **Hardware Microphone Mute Activated** | `voice/microphone_monitor.py` | Disarms audio streaming to cloud; switches UI to `MUTED` state |
