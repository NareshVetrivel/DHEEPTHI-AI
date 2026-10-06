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

### 🔒 Built-in Privacy & Safety Rules
- **RAM-Only Conversation Memory:** Chat context is maintained strictly in volatile RAM for the duration of the active session and is wiped upon application closure. Transcripts are never persisted to disk.
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
│   └── gemini_client.py            # Gemini Live audio session, multi-key pool & system prompt
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

## Privacy & Security

- **Strict Isolation of Credentials:** API keys and environment variables are read exclusively from the local `.env` file and are never logged or exposed in chat transcripts.
- **Transient Conversation Context:** Chat context is held exclusively in memory during the active session. Once the application is closed, session history is permanently erased.
- **Local Index Storage:** File indexing records and application metadata remain inside your local SQLite database (`database/astra.db`), which is strictly excluded from version control.
- **Hardware Endpoint Protection:** The hardware mute monitor ensures that muting your physical laptop microphone immediately suppresses all outbound audio at the Windows endpoint level.

---

## Author

**Naresh Vetrivel**<br>
GitHub: [@NareshVetrivel](https://github.com/NareshVetrivel)
