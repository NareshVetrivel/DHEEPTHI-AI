# DHEEPTHI-AI

**DHEEPTHI-AI** is a context-aware Windows desktop AI voice assistant engineered for low-latency realtime conversation, trilingual understanding, and native laptop automation.

Built with PySide6 and the Google GenAI SDK, DHEEPTHI connects directly to **Gemini Live** for persistent, bidirectional audio streaming with server-side voice activity detection. It natively understands and speaks English, Tamil, and Tanglish, while securely delegating desktop automation tasks—such as application management, deep filesystem operations, browser navigation, Microsoft Word document synthesis, and system settings—to specialized local automation controllers.

---

## Architecture at a Glance

```text
                           ┌────────────────────────┐
                           │   User Voice Input     │
                           │  (Microphone Stream)   │
                           └───────────┬────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │     Windows Core Audio COM        │
                     │  (Hardware Mute Enforcement)      │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │        Gemini Live Session        │
                     │  (Persistent Bidirectional PCM)   │
                     └─────────────────┬─────────────────┘
                                       │
                   ┌───────────────────┴───────────────────┐
                   ▼                                       ▼
     ┌───────────────────────────┐           ┌───────────────────────────┐
     │   Conversational Turn     │           │   Action Command Stream   │
     │  (Streamed Aoede Voice)   │           │    (Realtime Transcript)  │
     └───────────────────────────┘           └─────────────┬─────────────┘
                                                           │
                                                           ▼
                                             ┌───────────────────────────┐
                                             │ Semantic Command Planner  │
                                             │ (Intent & Entity Parsing) │
                                             └─────────────┬─────────────┘
                                                           │
                                                           ▼
                                             ┌───────────────────────────┐
                                             │ Local Validation Layer    │
                                             │ (Path & Safety Checks)    │
                                             └─────────────┬─────────────┘
                                                           │
                                                           ▼
                                             ┌───────────────────────────┐
                                             │    CommandDispatcher      │
                                             └─────────────┬─────────────┘
                                                           │
                   ┌───────────────────┬───────────────────┼───────────────────┐
                   ▼                   ▼                   ▼                   ▼
         ┌───────────────────┐ ┌───────────────┐ ┌───────────────────┐ ┌───────────────┐
         │    AppLauncher    │ │ FileFolderAgent│ │ BrowserController │ │ System & Word │
         │ & WindowController│ │& FileSystemAg.│ │   & Playwright    │ │  Controllers  │
         └─────────┬─────────┘ └───────┬───────┘ └─────────┬─────────┘ └───────┬───────┘
                   │                   │                   │                   │
                   └───────────────────┴─────────┬─────────┴───────────────────┘
                                                 ▼
                                     ┌───────────────────────┐
                                     │ Windows OS Execution  │
                                     └───────────────────────┘
```

> **Decoupled Security Model:** The cloud LLM is responsible solely for natural language understanding and multi-step action planning. It possesses **no direct OS execution authority**. All physical laptop interactions are validated, sanitized, and performed locally by deterministic Python automation modules.

---

## Key Features

### 🎙️ Persistent Gemini Live Voice Interaction
- **Zero-Wake-Word Realtime Audio:** Operates through a continuous bidirectional streaming session via Google GenAI (`gemini-3.1-flash-live-preview`), eliminating manual push-to-talk delays and sluggish wake-word listeners.
- **Natural Voice Persona (Aoede):** Employs the warm, conversational `Aoede` prebuilt voice for expressive speech synthesis.
- **Dynamic Interruption & Barge-In:** Realtime streaming allows the user to speak over the assistant at any point. Gemini Live automatically senses speech onset, truncates assistant playback, and adapts immediately.
- **Server-Side Voice Activity Detection (VAD):** Employs server-side speech onset and offset thresholds with calibrated 600ms silence detection for crisp turn-taking.
- **Resilient Key Rotation Pool:** Includes a multi-key manager (`GEMINI_API_KEY_1..4`) that monitors quota limits and automatically rotates across available keys.

### 🌐 Trilingual & Mixed-Language Understanding
- **English, Tamil & Tanglish:** Fluent comprehension across pure English, Tamil, Tanglish (Tamil expressed phonetically in Latin script), and natural code-mixed phrasing.
- **Bidirectional Translation:** Instant voice translation between English ↔ Tamil and English ↔ Tanglish on demand.
- **Respectful Conversational Persona:** Enforces polite, respectful addressing across all languages (e.g., *sollunga*, *pannunga*, *vaanga*) and strictly avoids informal or disrespectful colloquialisms (*da*, *vaada*, *poda*).

### 💻 Comprehensive Desktop Automation
- **Application Management:** Launch, bring to foreground, or gracefully terminate installed Windows applications by natural title or common alias (`AppLauncher`, `AppCloser`, `ApplicationScanner`).
- **Intelligent File & Folder Agent:** Deep indexing across standard user directories (Desktop, Documents, Downloads, Pictures, Videos, Music) and custom drives. Features fast search, path resolution, candidate selection prompts for ambiguous matches, and native Explorer opening (`FileFolderAgent`, `FileSystemAgent`).
- **Browser Automation:** Seamless browser control for Google Chrome and Microsoft Edge, supporting web queries, direct URL navigation, and YouTube video playback via Playwright (`BrowserController`).
- **Productivity Agent (Microsoft Word):** Dedicated COM automation layer for Microsoft Word that creates documents, writes formatted text, saves files, and coordinates workspace drafting (`WordAgent`).
- **System Controls:** Adjust master volume by step or exact percentage, toggle audio mute, adjust screen brightness, lock the desktop, capture screenshots, and record the screen (`SystemController`, `WindowController`, `ScreenRecorder`).

### 🛡️ Physical Microphone Mute Authority
- **Windows Core Audio COM Endpoint:** Directly polls the Windows Default Capture Endpoint (`IAudioEndpointVolume.GetMute()`) via Windows COM APIs.
- **Hardware Priority:** Pressing the laptop's physical microphone mute key immediately disarms audio ingestion, stops microphone packets from reaching the cloud, and updates the UI into the `MUTED` state. Live listening resumes seamlessly upon unmuting.

### 🎨 Modern Futuristic User Interface
- **Realtime User Speech Panel:** Translucent glassmorphism HUD displaying live user transcripts with zero text overflow.
- **9-Bar Voice Waveform:** Audio-reactive 9-bar visualizer animated directly by incoming microphone PCM amplitude.
- **Synchronized Visual States:** Realtime state orchestration across `IDLE`, `LISTENING`, `USER SPEAKING`, `SPEAKING`, and `MUTED`.
- **Animated Startup Experience:** Hardware-accelerated splash screen with drifting canvas particle twinkles, glowing progress synchronization, and a smooth cross-dissolve transition into the main dashboard.

### 🧠 Persistent SQLite Memory & Multi-Profile Architecture
- **5-Tier Persistent Memory System:** Conversation turns, structured user facts, personal memories (relationships, education, work), commitments, and emotional history are persisted in a local SQLite database (`database/astra.db`).
- **Profile Isolation & Provenance:** Facts and conversation turns are tracked by `profile_id`, preventing cross-profile leakage, with full provenance timestamps and status flags (`active`, `archived`, `corrected`).
- **Real-Time Context Synthesis:** `MemoryManager` and `PersonalityContextBuilder` dynamically inject canonical facts into both standard Gemini and Gemini Live system prompts, with automatic cold-restart recovery.
- **Sensitive Credential Redaction:** Sensitive credentials (passwords, tokens, API keys) are detected and redacted before durable storage.
- **Prompt & Secret Guardrails:** Strict behavioral boundaries prevent disclosure of hidden system prompts, API keys, private schemas, or internal agent workflows, including resistance against translation-based jailbreak attempts.
- **India Standard Time (IST) Compliance:** Time queries deterministically pull the local system clock locked to the `Asia/Kolkata` (UTC+05:30) timezone, returning accurate day, date, and hour articulation.

---

## Conversation vs. Automation Flow

DHEEPTHI cleanly separates everyday conversational dialogue from actionable laptop operations:

| Request Type | User Input Example | Execution Pipeline | User Experience |
|---|---|---|---|
| **Conversation** | *"Explain how neural networks learn."* | Gemini Live Stream → Direct Audio Output | Instant vocal explanation in natural Tanglish/English. |
| **Translation** | *"Idha English-la translate pannunga."* | Gemini Live Translator → Speech & Transcript | Fast, accurate bidirectional language translation. |
| **Application Launch** | *"Open Chrome and Notepad"* | Gemini Transcript → MultiCommandPlanner → AppLauncher | Both applications launch in sequence; state updates on screen. |
| **Media Playback** | *"Chrome open panni Pavalamalli song play pannu"* | Semantic Planner → BrowserController → YouTube Search | Chrome opens, navigates to YouTube, and plays the requested song. |
| **File Operations** | *"Downloads folder-la irundhu report.pdf-ah Desktop-ku copy pannu"* | FileFolderAgent → Context Resolution → FileSystemAgent | Finds the file, verifies target path, performs file copy, and confirms via voice. |
| **Word Automation** | *"Word open panni meeting notes create pannu"* | WordAgent → WordAutomation (COM) → WordVerifier | Opens Microsoft Word, formats title and notes body, verifies document readiness. |
| **System Settings** | *"Volume 70 percent veiyunga"* | IntentDetector → SystemController → pycaw | Master audio level changes immediately to 70%. |

---

## Natural Language Command Examples

DHEEPTHI uses semantic parsing rather than brittle keyword matching, allowing users to speak comfortably and naturally:

### Application & Window Control
- *"Open Google Chrome"*
- *"Close Notepad"*
- *"Calculator open pannunga"*
- *"Minimize the current window"*

### Chained Multi-Step Workflows
- *"Open Chrome then search Sona College"*
- *"Chrome open panni Pavalamalli song play pannu"*
- *"Notepad open panni Hello World type pannu"*
- *"Downloads folder open panni latest file-ah Desktop-ku copy pannu"*

### Productivity & Word Synthesis
- *"Open Microsoft Word"*
- *"Word-la new document create panni Project Summary type pannu"*

### System & Media Controls
- *"Volume increase pannunga"*
- *"Volume-ah 50 percent set pannu"*
- *"Mute audio"*
- *"Take a screenshot"*
- *"Screen record start pannu"*

### Time & Locale Queries
- *"What is the time?"*
- *"Indian time enna?"*
- *"Ippo date enna?"*

---

## User Interface Highlights

The application interface is crafted with PySide6:

- **User Speech Panel:** Positioned prominently to give immediate visual feedback. It parses live speech transcripts, displays real-time linguistic feedback, and houses the voice-reactive 9-bar audio waveform.
- **Visual State Indicator:** Transitions dynamically between:
  - `IDLE`: Resting state, waiting for user speech.
  - `LISTENING`: Microphone is open, server VAD active.
  - `USER SPEAKING`: Realtime speech detected and being ingested.
  - `SPEAKING`: Assistant is generating and vocalizing a response.
  - `MUTED`: Physical microphone endpoint is muted via hardware switch.
- **Left & Right Telemetry Panels:** Display real-time status tiles for network connectivity, active Gemini model, audio subsystems, and file index counters.
- **Interactive Avatar:** Animated visual avatar that expresses conversational feedback, thinking states, and success indicators.

---

## Technology Stack

| Component | Technologies & Libraries | Purpose |
|---|---|---|
| **GUI Framework** | **PySide6** (Qt 6.11) | Desktop user interface, custom title bar, glassmorphic HUD, particle animations |
| **Core AI & Realtime Voice** | **Google GenAI SDK** (`google-genai`) | Gemini Live (`gemini-3.1-flash-live-preview`), Gemini Flash (`gemini-3.8-flash`) |
| **Fallback Intelligence** | **Groq Cloud SDK** (`groq`) | Fallback planning and code generation |
| **Audio I/O & Streaming** | **PyAudio**, **sounddevice**, **soundfile** | 16 kHz capture & 24 kHz playback PCM streaming |
| **Hardware Mute Detection** | **comtypes**, **pycaw** | Windows Core Audio COM endpoint monitoring (`IAudioEndpointVolume`) |
| **Windows OS Automation** | **pywinauto**, **pywin32**, **PyAutoGUI** | Window focus, desktop input automation, system controls |
| **Browser Automation** | **Playwright**, **subprocess** | Chrome/Edge persistent sessions, web searching, YouTube automation |
| **Productivity Automation** | **pywin32** (`win32com.client`) | Microsoft Word COM automation |
| **Local Data Storage** | **SQLite3** | Local index cache for applications, aliases, and scanned files |
| **Fuzzy Matching & Strings** | **RapidFuzz**, **pathvalidate** | Fast, tolerant matching of spoken app and file names |

---

## Repository Structure

The core application codebase is organized into clean functional modules:

```text
DHEEPTHI-AI/
├── app/
│   ├── __init__.py
│   └── main.py                     # Main application entry point & bootstrap
├── ai/
│   ├── __init__.py
│   ├── gemini_client.py            # Gemini Live audio session, multi-key pool & system prompt
│   ├── memory_manager.py           # SQLite conversation turns, facts & episodic memory manager
│   ├── emotion_engine.py           # Emotional state tracking & sentiment reactivity
│   └── personality_context_builder.py # Real-time prompt context synthesizer with verified memory
├── automation/
│   ├── __init__.py
│   ├── app_launcher.py             # Application launcher
│   ├── app_closer.py               # Process termination & graceful window closer
│   ├── application_scanner.py      # Start Menu & Registry app scanner
│   ├── browser_controller.py       # Browser and YouTube automation
│   ├── file_finder.py              # Indexed file search engine
│   ├── file_indexer.py             # Filesystem indexing background worker
│   ├── file_manager.py             # File operations (copy, move, delete)
│   ├── folder_manager.py           # Directory navigation & Explorer controller
│   ├── keyboard_controller.py      # Virtual keyboard automation
│   ├── mouse_controller.py         # Mouse input automation
│   ├── playwright_controller.py    # Playwright browser integration
│   ├── screen_recorder.py          # Screen video recorder
│   ├── system_controller.py        # Master volume, brightness & power controls
│   └── window_controller.py        # Win32 & pywinauto window management
├── code_agent/
│   ├── __init__.py
│   └── agent.py                    # Local Python/Java code synthesis agent
├── config/
│   ├── __init__.py
│   └── settings.py                 # Central settings & environment variable defaults
├── core/
│   ├── __init__.py
│   └── context_manager.py          # Context continuity & entity tracker
├── database/
│   ├── __init__.py
│   └── database_manager.py         # SQLite schema initialization and query manager
├── ff_agent/                       # Intelligent File & Folder Agent
│   ├── __init__.py
│   ├── agent.py                    # Multi-step file/folder execution coordinator
│   ├── context_resolver.py         # Disambiguation and candidate resolution
│   ├── models.py                   # Dataclasses and result schemas
│   ├── planner.py                  # Step planner for filesystem changes
│   ├── safety.py                   # Path validation and deletion safeguards
│   └── verifier.py                 # Post-action verification
├── models/
│   └── piper/                      # Offline fallback TTS model files
├── planner/
│   ├── __init__.py
│   ├── action_models.py            # Structured plan data definitions
│   ├── command_dispatcher.py       # Central controller routing and execution hub
│   ├── command_normalizer.py       # Entity and query string normalizer
│   ├── entity_extractor.py         # Regex and keyword entity parser
│   ├── intent_detector.py          # Intent classification engine
│   ├── multi_command_executor.py   # Sequential multi-step executor
│   ├── multi_command_planner.py    # Multi-action planning coordinator
│   ├── semantic_command_planner.py # LLM-driven natural language plan generator
│   └── text_extractor.py           # Text payload extractor
├── productivity_agent/             # Microsoft Word automation suite
│   ├── __init__.py
│   └── word/
│       ├── __init__.py
│       ├── agent.py                # Word agent orchestration layer
│       ├── automation.py           # Win32 COM Word operations
│       ├── commands.py             # Word command definitions
│       └── verifier.py             # Document state verification
├── ui/
│   ├── __init__.py
│   ├── main_window.py              # Main dashboard window & lifecycle controller
│   ├── splash_screen.py            # Startup splash screen with particle engine
│   ├── assets/                     # Brand logos, avatars, icons, themes
│   ├── components/                 # UI panels (header, left panel, center, right)
│   ├── styles/theme.py             # Color palette and stylesheet definitions
│   └── widgets/                    # UserSpeechPanel, AvatarWidget, SystemOSD
├── utils/
│   ├── __init__.py
│   └── logger.py                   # Logging utilities
├── vision/
│   ├── __init__.py
│   ├── gemini_vision.py            # Vision analysis helper
│   └── ocr.py                      # Local screen OCR
├── voice/
│   ├── __init__.py
│   ├── edge_tts_engine.py          # Edge-TTS fallback synthesis
│   ├── groq_recognizer.py          # Cloud STT fallback
│   ├── microphone_monitor.py       # Windows Core Audio COM physical mute monitor
│   ├── piper_tts_engine.py         # Local offline Piper TTS engine
│   ├── pyttsx3_tts_engine.py       # SAPI5 TTS fallback
│   ├── speech_recognition.py       # Speech input utilities
│   ├── streaming_tts_manager.py    # Chunked streaming TTS coordinator
│   └── text_to_speech.py           # Unified TTS interface
├── workers/
│   └── initialization_worker.py    # Background startup worker
├── .env.example                    # Sanitized public environment template
├── .gitignore                      # Git exclusion rules
├── requirements.txt                # Project dependency specifications
└── README.md                       # Project documentation
```

---

## Installation & Setup

### Prerequisites
- **Operating System:** Windows 10 or Windows 11 (64-bit)
- **Python:** Python 3.10 through 3.13
- **Hardware:** Working microphone and speakers / headphones

### 1. Clone the Repository
```powershell
git clone https://github.com/NareshVetrivel/DHEEPTHI-AI.git
cd DHEEPTHI-AI
```

### 2. Set Up a Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template [`.env.example`](.env.example) to `.env`:
```powershell
cp .env.example .env
```

Open `.env` and configure your API keys:
```env
# Primary Gemini API Key (Required for Gemini Live)
GEMINI_API_KEY_1=your_gemini_api_key_here

# Optional: Backup keys for automatic quota rotation
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=

# Gemini Live Voice Configuration
GEMINI_LIVE_VOICE=Aoede
GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview

# Optional: Cloud STT fallback
GROQ_API_KEY=
```

---

## Running DHEEPTHI-AI

Launch the assistant from the project root:

```powershell
python -m app.main
```

1. **Startup Sequence:** The animated splash screen appears while the background worker initializes the local application cache and file index.
2. **Dashboard Ready:** The main window opens with the interactive Avatar, System Status Tiles, and the Realtime User Speech Panel.
3. **Voice Interaction:** Speak naturally into your microphone in English, Tamil, or Tanglish to execute laptop commands or engage in conversational dialogue.

---

## Running Safe Automated Tests

Automated regression and memory tests utilize isolated synthetic databases and mock network/audio where appropriate to guarantee safety and prevent modifying the production database (`database/astra.db`):

```powershell
# Run the Master V1 Verification Suite (models, interruption, persistence, isolation)
python -m unittest tests/test_master_v1_verification.py

# Run Persistent Memory & Education Recall Suite
python -m unittest tests/test_gemini_live_persistent_memory.py

# Run Cold-Restart End-to-End Simulation Suite
python -m unittest tests/test_real_cold_restart_e2e.py

# Run Comprehensive Memory & Behavior Rules
python -m unittest tests/test_comprehensive_memory_v1.py
python -m unittest tests/test_v1_behavior_rules.py

# Run Multi-Process Cold-Restart Verification
python tests/verify_cold_restart_multi_process.py

# Run Code Agent Automation Suite (pytest)
pytest tests/test_code_agent.py
pytest tests/test_lifelong_conversational_memory.py
```

> **Note:** Tests that instantiate the full desktop GUI or bind to physical audio devices require a display session and should not be run in headless/CI environments.

---

## Live Demonstration Guide (College Staff Presentation)

Follow this structured demonstration flow during staff review:

### Pre-Flight Verification
1. Ensure your laptop is connected to stable internet.
2. Verify `.env` contains a valid `GEMINI_API_KEY_1` with Google GenAI access.
3. Confirm your microphone is set as the Windows Default Audio Input device.
4. Launch from project root:
   ```powershell
   python -m app.main
   ```

### Demonstration Steps
| Step | Action | Expected Behavior | Subsystem Verified |
|---|---|---|---|
| **1. Startup Experience** | Launch `python -m app.main` | Particle-animated splash screen smoothly cross-dissolves to main maximized dashboard | `SplashScreen`, `MainWindow`, `InitializationWorker` |
| **2. Natural Voice Interaction** | Say: *"Hello Dheepthi, how are you today?"* | Visualizer displays audio waveform; assistant responds naturally with `Aoede` voice | `GeminiLiveAudioWorker`, `UserSpeechPanel` |
| **3. Trilingual Understanding** | Say: *"Enna panra? Today weather pathi sollu."* | Fluent comprehension in conversational Tanglish; natural conversational response | Trilingual NLU, Tanglish Prompt Guardrails |
| **4. Ingest Personal Fact** | Say: *"Naan Sona College of Technology-la MCA second year padikiren."* | Assistant confirms receipt; commits education facts to SQLite with active status | `MemoryManager`, SQLite `personal_memories` |
| **5. Query Immediate Recall** | Ask: *"Naan endha college-la padikkiren?"* | Correctly states *"Sona College of Technology"* without hallucinating or guessing | `PersonalityContextBuilder`, Fact Extraction |
| **6. Cold Restart Verification** | Close the application completely. Re-run `python -m app.main`. Ask: *"En course enna?"* | Correctly recalls *"MCA second year"* restored directly from SQLite storage across cold boot | Cold-Restart Persistence, SQLite DB integrity |
| **7. Laptop Automation** | Say: *"Open Notepad and Calculator"* | Both applications launch in sequence; status tiles update in real time | `MultiCommandPlanner`, `AppLauncher` |
| **8. Hardware Mute Authority** | Press physical laptop mic mute key (or toggle mute in Windows) | UI switches immediately to `MUTED`; microphone stream to cloud is disarmed | `MicrophoneMonitor`, Windows Core Audio COM |

---

## Verified Limitations & Troubleshooting

- **Operating System Requirement:** DHEEPTHI-AI V1 is strictly built for Windows 10 and Windows 11 (64-bit). Linux and macOS environments are not supported due to direct dependencies on Windows Core Audio COM (`IAudioEndpointVolume`), `pywinauto`, and Win32 COM interfaces.
- **Gemini Live Availability:** Realtime voice streaming relies on Google GenAI preview endpoint availability (`gemini-3.1-flash-live-preview`). In the event of network disruption or quota exhaustion, configure fallback keys (`GEMINI_API_KEY_2..4`) or utilize the Groq fallback planner.
- **Physical Audio Hardware:** Real voice input requires physical microphone capture. If running in a virtual machine or remote terminal without audio redirection, voice interaction cannot record input.
- **Microsoft Word Requirement:** Document drafting via `WordAgent` requires locally installed Microsoft Office Word with COM automation registered (`win32com.client`).
- **Database Privacy Notice:** `database/astra.db` contains local user state and must remain excluded from public Git repositories via `.gitignore`. If historical commits contain early development databases, do not publish repository history publicly without running a history cleaner (e.g., `git-filter-repo`).

---

## Privacy & Security

- **Strict Isolation of Credentials:** API keys and environment variables are read exclusively from the local `.env` file and are never logged or exposed in chat transcripts.
- **Local SQLite Persistence:** Conversation turns, structured user facts, personal memories, and file index records reside inside your local SQLite database (`database/astra.db`). The database is strictly excluded from version control to guarantee user privacy.
- **Automatic Redaction:** Passwords, API tokens, and secret patterns are scrubbed from conversational turns prior to persistence.
- **Hardware Endpoint Protection:** The hardware mute monitor ensures that muting your physical laptop microphone immediately suppresses all outbound audio at the Windows endpoint level.

---

## Author

**Naresh Vetrivel**<br>
GitHub: [@NareshVetrivel](https://github.com/NareshVetrivel)
