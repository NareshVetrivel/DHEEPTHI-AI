# Non-Functional Requirements — DHEEPTHI-AI

This document specifies the non-functional requirements (NFR) governing the performance, reliability, security, maintainability, and compatibility of DHEEPTHI-AI V1.

---

## 1. Performance Requirements

### NFR-PERF-01: Low-Latency Speech Interruption (Barge-In)
- **Specification:** When the user interrupts the assistant while audio playback is active, the system shall cease speaker output, flush local audio queues, and invalidate response generation IDs within **$< 100$ milliseconds** of speech onset detection.
- **Implementation Reality:** Local buffer flush and queue invalidation take $< 1$ millisecond (`tests/test_master_v1_verification.py` observed $0.02 - 0.23$ ms local processing latency). Network detection is bounded by server-side VAD packet delivery.
- **Verification:** Unit tested in `tests/test_master_v1_verification.py`.

### NFR-PERF-02: Conversational Prompt Token Budgeting
- **Specification:** The dynamic context block synthesized by `PersonalityContextBuilder` (injecting emotional state, active profile facts, and relationship directives) shall not exceed **250 to 300 tokens** to prevent context window bloat and minimize TTFB latency in streaming sessions.
- **Implementation Reality:** Injected context strings average 1,500 to 1,800 characters (~300 tokens) with filtering rules that eliminate conflicting historical names.
- **Verification:** Tested in `tests/test_gemini_prompt_size.py`.

### NFR-PERF-03: Startup Initialization Asynchrony
- **Specification:** The graphical user interface shall become visible and responsive within **$< 2$ seconds** of process launch. Heavy initialization operations (such as Start Menu application scanning and filesystem directory indexing) must execute asynchronously in background worker threads without freezing the Qt main event loop.
- **Implementation Reality:** `MainWindow` renders immediately and schedules background indexing through `InitializationWorker` (`workers/initialization_worker.py`).
- **Verification:** Tested in `tests/test_startup_lifecycle.py` and `tests/test_splash_screen_runtime.py`.

---

## 2. Reliability & Availability Requirements

### NFR-REL-01: Multi-Provider Speech Synthesis Cascade
- **Specification:** The system shall guarantee spoken feedback even during upstream network failure or API disconnection by cascading across at least three distinct TTS engines:
  1. Primary Cloud: Gemini Live prebuilt `Aoede` voice.
  2. Secondary Cloud: Microsoft Edge Neural TTS (`edge-tts`).
  3. Tertiary Offline: Local Piper ONNX engine (`en_US-hfc_female-medium`).
  4. Quaternary OS Fallback: Windows SAPI5 (`pyttsx3`).
- **Implementation Reality:** Implemented in `voice/text_to_speech.py` with thread-safe request ID tracking and cancellation.
- **Verification:** Verified via `tests/test_text_to_speech.py`.

### NFR-REL-02: Automatic API Key Rotation Pool
- **Specification:** The system shall prevent service interruption caused by API rate limits (HTTP 429) or quota exhaustion by maintaining a pool of up to four Gemini API keys (`GEMINI_API_KEY_1..4`) and automatically rotating to the next active key upon encountering retryable errors.
- **Implementation Reality:** Implemented in `ai/gemini_client.py` (`rotate_api_key()`).
- **Verification:** Verified via `tests/test_gemini_keys.py`.

### NFR-REL-03: Offline Operation Boundary
- **Specification:** Core desktop automation tasks (launching installed apps, searching indexed local files, system volume/brightness control, and local Piper TTS playback) must remain functional when external internet access is severed, using cached SQLite indexes and local regex intent matching.
- **Implementation Reality:** Verified via local index lookups in `automation/file_finder.py` and `automation/application_finder.py`. Cloud features (Gemini Live, Groq STT) gracefully report disconnection without crashing.

---

## 3. Security, Safety, & Privacy Requirements

### NFR-SEC-01: Decoupled Zero-Execution-Authority Architecture
- **Specification:** The cloud Large Language Model shall possess **zero direct operating system execution authority**. The cloud model must never receive direct shell access (`subprocess`, `cmd.exe`, `powershell.exe`). All physical laptop interactions must be mediated by deterministic local Python controllers after parsing and validating structured action tags (`<ACTION>`).
- **Implementation Reality:** Strictly enforced in `ui/main_window.py` and `planner/command_dispatcher.py`.

### NFR-SEC-02: Filesystem Safety Boundaries
- **Specification:** The filesystem automation layer shall reject any modification, movement, or deletion request targeting protected operating system directories, including `C:\Windows`, `System32`, root drive partitions, and hidden system files.
- **Implementation Reality:** Implemented in `ff_agent/safety.py` (`SafetyManager.is_safe_path()`).
- **Verification:** Verified via `tests/test_file_system_agent.py`.

### NFR-SEC-03: Pre-Persistence Credential Scrubbing
- **Specification:** The memory persistence pipeline must intercept and scrub sensitive credential patterns—including passwords, OTP codes, high-entropy API tokens, and credit card numbers—before committing conversation records to durable SQLite storage.
- **Implementation Reality:** Regex filter `CREDENTIAL_PATTERNS` in `ai/memory_manager.py` sanitizes text before writing to `conversation_context` or `user_context`.
- **Verification:** Verified via `tests/test_permanent_memory_pipeline.py`.

### NFR-SEC-04: Hardware Endpoint Microphone Isolation
- **Specification:** Pressing the laptop's physical microphone mute key must immediately sever outbound audio streaming at the operating system capture endpoint level, preventing unauthorized audio transmission to third-party cloud servers.
- **Implementation Reality:** Implemented via continuous polling of `IAudioEndpointVolume.GetMute()` in `voice/microphone_monitor.py`.
- **Verification:** Verified via `tests/test_microphone_monitor.py`.

### NFR-SEC-05: Non-Disclosure of System Prompts & Secrets
- **Specification:** The assistant must refuse user requests attempting to reveal hidden system prompts, internal variables, database schemas, or API keys, even when framed as roleplay or translation jailbreaks.
- **Implementation Reality:** System prompt guardrails enforce secret protection; verified by test cases in `tests/test_v1_behavior_rules.py`.

---

## 4. Usability & Human-Computer Interaction Requirements

### NFR-USA-01: Trilingual Conversational Grounding
- **Specification:** The assistant must converse fluently in English, Tamil, and Tanglish (phonetically Latin-scripted Tamil), maintaining contextually appropriate vocabulary without forcing unnatural formal literary Tamil script during spoken voice output.
- **Implementation Reality:** System prompts instruct Gemini Live to reply in conversational Tanglish or English matching user language choice.
- **Verification:** Verified in `tests/test_v1_behavior_rules.py`.

### NFR-USA-02: Sociolinguistic Honorific Enforcement
- **Specification:** The assistant must maintain respectful conversational addressing (*sollunga*, *pannunga*, *vaanga*) and strictly avoid derogatory colloquialisms (*da*, *vaada*, *poda*).
- **Implementation Reality:** Prompt behavioral rules explicitly ban informal suffixes and disrespectful colloquialisms.
- **Verification:** Verified in `tests/test_v1_behavior_rules.py`.

### NFR-USA-03: Visual Telemetry & HUD Responsiveness
- **Specification:** The user interface must provide immediate visual feedback regarding system state (`IDLE`, `LISTENING`, `USER SPEAKING`, `SPEAKING`, `MUTED`), displaying an audio-reactive 9-bar visualizer animated by microphone amplitude.
- **Implementation Reality:** Implemented in `ui/widgets/user_speech_panel.py` and `ui/widgets/avatar_widget.py`.
- **Verification:** Verified in `tests/test_user_speech_panel.py`.

---

## 5. Compatibility & Software Architecture Requirements

### NFR-COMP-01: Operating System Target
- **Specification:** The application must run natively on 64-bit editions of Microsoft Windows 10 (Build 19041+) and Windows 11.
- **Rationale:** Hard dependencies on Windows Core Audio COM, `pywinauto`, `pycaw`, Win32 COM (`win32com.client`), and `screen_brightness_control`.

### NFR-COMP-02: Thread Safety and Concurrency
- **Specification:** All database interactions, audio I/O streaming, and long-running automation actions must execute in dedicated worker threads (`QThread` / `threading.Thread`) synchronized via recursive locks (`RLock`) to prevent UI freezes and race conditions.
- **Implementation Reality:** `DatabaseManager`, `ContextManager`, `GeminiLiveSession`, and `BrowserController` all encapsulate internal `threading.RLock` instances.
- **Verification:** Verified across cold restart and concurrency tests in `tests/verify_cold_restart_multi_process.py`.