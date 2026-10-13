# Functional Requirements — DHEEPTHI-AI

This document details the functional requirements (FR) implemented in DHEEPTHI-AI V1. Each requirement specifies its operational behavior, source code references, inputs/outputs, implementation status, and verification evidence.

---

## 1. Voice Ingestion & Audio Streaming

### FR-001: Continuous Zero-Wake-Word PCM Ingestion
- **Description:** The system shall capture continuous mono microphone audio at 16,000 Hz, 16-bit PCM format without requiring manual push-to-talk button activation or offline wake-word listener models.
- **Source Modules:** `ui/main_window.py` (`GeminiLiveAudioWorker`), `voice/microphone_monitor.py`.
- **Input:** Physical microphone audio stream.
- **Output:** Raw PCM byte chunks transmitted via WebSocket to Gemini Live.
- **Status:** **Implemented & Verified** (Verified via `tests/test_no_wake_word_runtime.py`).

### FR-002: Server-Side Voice Activity Detection (VAD)
- **Description:** Turn-taking shall be governed by Google GenAI server-side VAD configured with `START_SENSITIVITY_HIGH`, `END_SENSITIVITY_HIGH`, and a 600 ms silence duration window.
- **Source Modules:** `ai/gemini_client.py` (`GeminiLiveSession._run()`), `config/settings.py`.
- **Input:** Streaming audio uplink.
- **Output:** Server-emitted turn-completion events, interim transcripts, and finalized text transcripts.
- **Status:** **Implemented & Verified** (Verified via `tests/test_gemini_live_lifecycle.py`).

### FR-003: Real-Time Playback Interruption (Barge-In)
- **Description:** When the user begins speaking while the assistant is synthesizing audio, the client shall intercept the server VAD speech onset signal (`voice_activity(START)` or `vad_signal(START)`), immediately terminate local playback, flush output queues, and drop stale response packets in under 100 ms.
- **Source Modules:** `ai/gemini_client.py` (`interrupt_current_response()`), `ui/main_window.py` (`GeminiLiveAudioWorker.interrupt_and_flush()`).
- **Input:** Real-time VAD detection event.
- **Output:** Immediate cessation of speaker output; local latency $< 1$ ms observed in tests.
- **Status:** **Implemented & Verified** (Verified in `tests/test_master_v1_verification.py` — Phase 3).

### FR-004: Windows Hardware Microphone Mute Enforcement
- **Description:** The system shall poll the Windows Default Capture Endpoint (`IAudioEndpointVolume.GetMute()`) every 250 ms. Activating the laptop's physical mute key shall disarm audio streaming to the cloud and switch UI state to `MUTED`.
- **Source Modules:** `voice/microphone_monitor.py` (`MicrophoneMuteMonitor`).
- **Input:** Windows Core Audio COM endpoint state.
- **Output:** Qt signal `mute_changed(bool)`; gating audio transmission.
- **Status:** **Implemented & Verified** (Verified via `tests/test_microphone_monitor.py`).

---

## 2. Natural Language Understanding & Planning

### FR-005: Trilingual & Code-Mixed Understanding
- **Description:** The system shall interpret spoken natural language in English, Tamil, and Tanglish (Latin-scripted Tamil), including mixed-code sentences (e.g., *"Chrome open panni Pavalamalli song play pannu"*).
- **Source Modules:** `ai/gemini_client.py` (`live_system_prompt()`), `planner/semantic_command_planner.py`.
- **Input:** User voice transcript.
- **Output:** Context-aware Tanglish/English conversational reply and standardized action blocks.
- **Status:** **Implemented & Verified** (Verified in `tests/test_v1_behavior_rules.py`).

### FR-006: Sociolinguistic Respectful Addressing
- **Description:** The assistant shall strictly utilize polite honorific forms (*sollunga*, *pannunga*, *vaanga*) and suppress disrespectful colloquialisms (*da*, *vaada*, *poda*) across all conversational outputs.
- **Source Modules:** `ai/gemini_client.py` (`live_system_prompt()`).
- **Input:** Conversational generation request.
- **Output:** Sanitized, respectful dialogue.
- **Status:** **Implemented & Verified** (Verified in `tests/test_v1_behavior_rules.py`).

### FR-007: Standardized `<ACTION>` Tag Extraction
- **Description:** Actionable desktop commands generated during conversation shall be wrapped inside an inline tag: `<ACTION>standardized command</ACTION>`. The client shall extract the command, forward it to the planner, and filter the tag from user-facing transcripts.
- **Source Modules:** `ui/main_window.py` (`_extract_action_command()`), `planner/semantic_command_planner.py`.
- **Input:** Gemini Live output transcript.
- **Output:** Isolated English command string; filtered user speech panel display.
- **Status:** **Implemented & Verified** (Verified in `system_test.py`).

### FR-008: Semantic Intent Detection & Planning
- **Description:** Spoken commands shall be classified into over 40 supported intents, distinguishing actionable commands from informational questions. Multi-step requests shall be decomposed into sequential `ActionPlan` structures.
- **Source Modules:** `planner/semantic_command_planner.py`, `planner/intent_detector.py`, `planner/multi_command_planner.py`.
- **Input:** Extracted command string.
- **Output:** Structured `ActionPlan` containing typed `ActionStep` entries.
- **Status:** **Implemented & Verified** (Verified in `tests/test_natural_language_semantic_routing.py`).

---

## 3. Operating System Desktop Automation

### FR-009: Application Lifecycle Management
- **Description:** The system shall launch applications by natural title or alias by querying indexed Start Menu shortcuts and Registry keys (`AppLauncher`). Applications shall be closed gracefully by window signals, falling back to process termination via `psutil` (`AppCloser`).
- **Source Modules:** `automation/app_launcher.py`, `automation/app_closer.py`, `automation/application_scanner.py`.
- **Input:** Spoken application name or alias (e.g., *"Notepad"*, *"Calculator"*, *"Chrome"*).
- **Output:** Process launched or terminated; window brought to foreground.
- **Status:** **Implemented & Verified** (Verified in `tests/test_app_launcher.py`, `test_app_closer.py`).

### FR-010: Safe Filesystem Operations & Disambiguation
- **Description:** The filesystem agent shall perform file/folder search, copy, move, delete, rename, compression, and extraction. If multiple candidate files match, the system shall prompt the user via `FileSelectionPanel` before taking action. Deletions shall recycle via `Send2Trash`.
- **Source Modules:** `ff_agent/agent.py`, `automation/file_system_agent.py`, `automation/file_manager.py`, `ff_agent/safety.py`.
- **Input:** Target file/folder name and destination directory.
- **Output:** File operation executed; filesystem verification confirmed.
- **Status:** **Implemented & Verified** (Verified in `tests/test_file_system_agent.py`, `test_file_folder_manager.py`).

### FR-011: Web Browser & YouTube Automation
- **Description:** The browser controller shall launch Google Chrome or Microsoft Edge, navigate to specified URLs, conduct Google web searches, and initiate YouTube video playback.
- **Source Modules:** `automation/browser_controller.py`, `automation/playwright_controller.py`.
- **Input:** Search query or video song title (e.g., *"Play Pavalamalli song on YouTube"*).
- **Output:** Browser navigation, search execution, and direct media playback.
- **Status:** **Implemented & Verified** (Verified in `tests/test_automation_pipeline.py`).

### FR-012: Microsoft Word COM Automation
- **Description:** The productivity agent shall automate Microsoft Word via Win32 COM, creating blank documents, typing formatted titles and body paragraphs, saving files, and verifying document status.
- **Source Modules:** `productivity_agent/word/agent.py`, `productivity_agent/word/automation.py`, `productivity_agent/word/verifier.py`.
- **Input:** Spoken document creation or text typing request.
- **Output:** Active Word document created and populated with formatted text.
- **Status:** **Implemented & Verified** (Verified in `tests/test_word_v1.py`).

### FR-013: System Peripherals & Audio Telemetry Control
- **Description:** The system controller shall set master volume to exact percentages or step increments (`pycaw`), adjust screen brightness (`screen_brightness_control`), lock the workstation, take screenshots, record the screen (`mss` + OpenCV), and capture webcam photos.
- **Source Modules:** `automation/system_controller.py`, `automation/screen_recorder.py`.
- **Input:** Spoken system command (e.g., *"Volume 70 percent set pannu"*, *"Take screenshot"*).
- **Output:** Volume/brightness altered; media saved to local storage.
- **Status:** **Implemented & Verified** (Verified in `tests/test_system_controller.py`).

---

## 4. Autonomous Coding Agent

### FR-014: Program Synthesis & Self-Repair Execution Loop
- **Description:** The system shall accept coding requests in natural language, generate complete Python or Java source code via Groq (`openai/gpt-oss-20b`), save the source file to `Desktop/DHEEPTHI_program/`, execute it via subprocess (30s timeout), and automatically repair syntax/runtime errors using compiler stderr feedback up to 3 attempts.
- **Source Modules:** `code_agent/agent.py`, `planner/command_dispatcher.py`.
- **Input:** Spoken coding task (e.g., *"Write a python program for fibonacci"*).
- **Output:** Executable file written and executed; terminal output returned to user.
- **Status:** **Implemented & Verified** (Verified in `tests/test_code_agent.py`).

---

## 5. Cognitive Memory & Affective State

### FR-015: 5-Tier Persistent SQLite Memory
- **Description:** The system shall persist conversation turns, semantic profile facts, personal relationship entities, episodic interaction summaries, and tasks in a local SQLite database (`database/astra.db`).
- **Source Modules:** `ai/memory_manager.py`, `database/database_manager.py`.
- **Input:** User utterances and assistant responses.
- **Output:** Relational records inserted across 14 tables; verified across cold restarts.
- **Status:** **Implemented & Verified** (Verified in `tests/test_master_v1_verification.py`, `test_real_cold_restart_e2e.py`).

### FR-016: Automatic Credential Redaction
- **Description:** Before committing conversation turns to durable storage, regex safety filters shall detect and redact passwords, OTP codes, API tokens, and credit card patterns.
- **Source Modules:** `ai/memory_manager.py` (`CREDENTIAL_PATTERNS`).
- **Input:** User utterance text.
- **Output:** Redacted utterance stored in database.
- **Status:** **Implemented & Verified** (Verified in `tests/test_permanent_memory_pipeline.py`).

### FR-017: Emotional State Machine with Inactivity Decay
- **Description:** The system shall model emotional valence, arousal, and rapport across moods (*neutral*, *happy*, *caring*, *hurt*, *annoyed*, *playful*). If 15 minutes elapse without interaction, extreme negative emotions shall decay back to neutral equilibrium.
- **Source Modules:** `ai/emotion_engine.py`.
- **Input:** Utterance sentiment and elapsed time since last interaction.
- **Output:** Updated emotional vector; prompt tone directives.
- **Status:** **Implemented & Verified** (Verified in `tests/test_emotion_and_memory.py`).

---

## 6. Multi-Engine Fallback Cascades

### FR-018: Multi-Provider Speech Synthesis Fallback
- **Description:** If Gemini Live audio synthesis is unavailable, speech output shall cascade sequentially through Microsoft Edge Neural TTS $\rightarrow$ Local Piper ONNX (`en_US-hfc_female-medium`) $\rightarrow$ Windows SAPI5 (`pyttsx3`).
- **Source Modules:** `voice/text_to_speech.py`, `voice/edge_tts_engine.py`, `voice/piper_tts_engine.py`, `voice/pyttsx3_tts_engine.py`.
- **Input:** Response text string.
- **Output:** Audio playback via available engine.
- **Status:** **Implemented & Verified** (Verified in `tests/test_text_to_speech.py`).

### FR-019: API Key Rotation Pool
- **Description:** `GeminiClient` shall maintain a pool of up to four Gemini API keys (`GEMINI_API_KEY_1..4`). Upon encountering HTTP 429 quota exhaustion or HTTP 403 invalid key errors, the client shall automatically rotate to the next key without crashing.
- **Source Modules:** `ai/gemini_client.py` (`rotate_api_key()`).
- **Input:** Google GenAI error response.
- **Output:** Switched active API key; retried request.
- **Status:** **Implemented & Verified** (Verified in `tests/test_gemini_keys.py`).