# Software Requirements Specification (SRS) — DHEEPTHI-AI

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) provides a comprehensive description of the functional, non-functional, interface, and operational requirements for **DHEEPTHI-AI V1**. It defines the architectural boundaries, system behaviors, security guardrails, and hardware dependencies governing the desktop assistant.

### 1.2 Scope
DHEEPTHI-AI is an intelligent, full-duplex conversational voice assistant and desktop automation environment engineered specifically for **Microsoft Windows 10 and Windows 11 (64-bit)**. 

**In Scope:**
- Bidirectional PCM audio streaming with server-side Voice Activity Detection via the Google GenAI Live API.
- Sub-millisecond speech interruption (barge-in) and audio queue invalidation.
- Trilingual natural language understanding and bidirectional translation (English, Tamil, Tanglish).
- Standardized action tag (`<ACTION>`) parsing and semantic command planning.
- Deterministic Windows operating system automation:
  - Process lifecycle management (`AppLauncher`, `AppCloser`, `ApplicationScanner`).
  - Safe multi-step filesystem operations with path restrictions (`FileFolderAgent`, `SafetyManager`).
  - Browser navigation and YouTube streaming (`BrowserController`, `PlaywrightController`).
  - Microsoft Word document synthesis via Win32 COM (`WordAgent`, `WordAutomation`).
  - Master volume, display brightness, screen recording, screenshot, and camera capture (`SystemController`).
  - Autonomous Python and Java code generation with self-repair loops (`CodeAgent`).
- Hardware endpoint microphone mute detection via Windows Core Audio COM (`IAudioEndpointVolume`).
- Local relational cognitive memory (5 tiers) stored in SQLite (`database/astra.db`).
- Affective state machine tracking valence, arousal, and rapport with 15-minute inactivity decay (`EmotionEngine`).
- PySide6 graphical dashboard with a real-time HUD and audio-reactive 9-bar waveform.

**Out of Scope:**
- Linux and macOS desktop environments (due to hard dependencies on Win32 COM, `pywinauto`, and Windows Core Audio).
- Unrestricted arbitrary command-line execution by cloud models (strictly prohibited by the zero-authority security model).
- Embedded hardware microcontrollers and smart-home IoT protocols.
- Cloud-hosted web multi-tenant deployment (designed as a local single-workstation desktop application).

### 1.3 Definitions, Acronyms, and Abbreviations
- **ASR:** Automated Speech Recognition.
- **COM:** Component Object Model (Microsoft Windows binary-interface standard).
- **Core Audio COM:** Windows Multimedia Device (MMDevice) and Audio Endpoint API.
- **HUD:** Heads-Up Display.
- **PCM:** Pulse-Code Modulation (uncompressed raw audio samples).
- **Tanglish:** Tamil language expressions phonetically transcribed in Latin (English) script.
- **TTS:** Text-to-Speech synthesis.
- **VAD:** Voice Activity Detection.
- **WAL:** Write-Ahead Logging (SQLite high-concurrency mode).

---

## 2. Overall Description

### 2.1 Product Perspective
DHEEPTHI-AI operates as a desktop client bridging local hardware interfaces with cloud-based intelligence services. The system relies on a **Decoupled Architecture**: the cloud Large Language Model functions purely as an analytical conversationalist and action planner, while all physical execution is mediated by deterministic local Python controllers.

```text
+--------------------------------------------------------------------------+
|                              WORKSTATION                                 |
|                                                                          |
|   +--------------------+     Raw PCM      +--------------------------+   |
|   | Physical Mic / COM | ---------------> | PySide6 Main Application |   |
|   +--------------------+                  +--------------------------+   |
|                                             |           ^                |
|                                    Raw PCM  |           | 24 kHz Audio   |
|                                             v           | & Transcripts  |
|                                   +----------------------------------+   |
|                                   |  Gemini Live WebSocket Session   |   |
|                                   +----------------------------------+   |
|                                             |                            |
+---------------------------------------------|----------------------------+
                                              v (Internet)
                               +-----------------------------+
                               | Google GenAI Cloud Endpoint |
                               +-----------------------------+
```

### 2.2 User Characteristics
The system is designed for students, software engineers, and administrative workstation users who require rapid, hands-free desktop task execution and conversational productivity in multilingual (English, Tamil, Tanglish) workflows.

### 2.3 General Constraints
1. **Operating System:** Microsoft Windows 10 (Build 19041+) or Windows 11 (64-bit).
2. **Python Environment:** Python 3.10 through Python 3.13.
3. **Network Connectivity:** Persistent low-latency broadband internet connection required for Google GenAI Live streaming and Groq cloud services.
4. **Local Hardware:** Functional audio capture device (microphone) and output device (speakers/headphones).
5. **Office Automation:** Microsoft Word document creation requires locally installed Microsoft Office with registered Win32 COM automation.

---

## 3. Specific Subsystem Requirements

### 3.1 Voice Input & Full-Duplex Audio Streaming
- **SR-VOICE-01:** The system shall capture raw mono audio at 16,000 Hz, 16-bit PCM format via `sounddevice`.
- **SR-VOICE-02:** The system shall maintain a persistent bidirectional WebSocket streaming connection to `gemini-3.1-flash-live-preview`.
- **SR-VOICE-03:** The system shall utilize server-side Voice Activity Detection with high start/end sensitivity and a 600 ms silence duration window.
- **SR-VOICE-04:** The system shall play received 24,000 Hz, 16-bit mono PCM downlink audio through `sounddevice`.
- **SR-VOICE-05:** Upon receiving a server-side speech onset event (`voice_activity` or `vad_signal` START), the system shall immediately terminate playback, empty local playback queues, and discard stale response chunks.
- **SR-VOICE-06:** The system shall monitor Windows Core Audio COM (`IAudioEndpointVolume.GetMute()`) every 250 ms. When muted, outgoing audio transmission must halt immediately.

### 3.2 Natural Language Understanding & Planning
- **SR-PLAN-01:** The system shall parse spoken natural language in English, Tamil, and Tanglish into conversational dialogue and actionable commands.
- **SR-PLAN-02:** When an actionable desktop operation is detected, the model shall emit an inline standardized command block formatted as `<ACTION>command text</ACTION>`.
- **SR-PLAN-03:** The user interface shall suppress raw `<ACTION>` tags from user-facing transcripts and text-to-speech output.
- **SR-PLAN-04:** The `SemanticCommandPlanner` shall classify requests into supported intents (`launch_application`, `close_application`, `open_file`, `copy_file`, `play_youtube`, `create_blank_document`, `code_agent`, etc.) and produce structured action plans.
- **SR-PLAN-05:** Chained commands (e.g., "Open Chrome then play song") shall be decomposed into sequential `ActionStep` records.

### 3.3 Operating System Automation & Safety
- **SR-AUTO-01:** Applications shall be launched via Start Menu shortcuts, Registry records, or custom indexed paths (`AppLauncher`).
- **SR-AUTO-02:** Windows applications shall be terminated gracefully by window closing, falling back to process termination via `psutil` if unresponsive (`AppCloser`).
- **SR-AUTO-03:** Filesystem operations (`create`, `copy`, `move`, `delete`, `rename`, `compress`, `extract`) shall be validated against `SafetyManager`. Modifications targeting `C:\Windows`, `System32`, or root system volumes shall be blocked.
- **SR-AUTO-04:** Ambiguous file searches shall trigger candidate selection in `FileSelectionPanel` before execution.
- **SR-AUTO-05:** Permanent file deletions shall use `Send2Trash` to recycle files rather than performing unrecoverable disk erasures.
- **SR-AUTO-06:** Master audio volume shall be adjusted via Windows COM endpoints (`pycaw`), and brightness adjusted via `screen_brightness_control`.
- **SR-AUTO-07:** Microsoft Word documents shall be created and formatted using `win32com.client.Dispatch("Word.Application")`.

### 3.4 Autonomous Code Generation
- **SR-CODE-01:** Spoken programming requests shall route to `CodeAgent` using Groq model `openai/gpt-oss-20b`.
- **SR-CODE-02:** Generated code (Python or Java) shall be saved under `~/Desktop/DHEEPTHI_program/`.
- **SR-CODE-03:** The system shall execute the generated program via subprocess with a 30-second timeout.
- **SR-CODE-04:** If execution fails with syntax or runtime errors, the agent shall automatically feedback the compiler traceback to the model and re-generate up to three attempts.

### 3.5 Memory, Cognitive State, & Persistence
- **SR-MEM-01:** All conversation turns shall be logged to SQLite table `conversation_context` with timestamps and session identifiers.
- **SR-MEM-02:** User profile facts (education, workplace, relationships, preferences) shall be stored in `user_context` and `personal_memories`.
- **SR-MEM-03:** Regex filters shall scrub credit cards, passwords, OTPs, and API keys before database commitment.
- **SR-MEM-04:** Data records shall be scoped by `profile_id` to enforce user isolation.
- **SR-MEM-05:** `EmotionEngine` shall track mood across *neutral*, *happy*, *caring*, *hurt*, *annoyed*, and *playful*. After 15 minutes of inactivity, extreme negative moods shall decay to baseline equilibrium.

### 3.6 Graphical User Interface
- **SR-UI-01:** The application shall provide a customized title bar with drag-to-move, minimize, maximize, and close controls.
- **SR-UI-02:** A translucent glassmorphism `UserSpeechPanel` shall render live user transcripts and an audio-reactive 9-bar waveform.
- **SR-UI-03:** An animated `AvatarWidget` shall reflect current agent moods and conversational states.
- **SR-UI-04:** An asynchronous startup worker (`InitializationWorker`) shall index applications and files while displaying progress on an animated splash screen.