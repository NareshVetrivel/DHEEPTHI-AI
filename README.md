# DHEEPTHI-AI

**DHEEPTHI-AI V1** is an adaptive, context-aware desktop AI assistant and automation system for Windows. Built with PySide6 and Google Gemini Live, DHEEPTHI delivers persistent realtime bidirectional voice interaction in English, Tamil, and Tanglish alongside comprehensive Windows desktop automation.

---

## Key Capabilities

### 🎙️ Realtime Bidirectional Voice (Gemini Live)
- **Zero-Wake-Word Realtime Audio**: Continuous low-latency streaming PCM voice pipeline powered by Google Gemini Live (`gemini-3.1-flash-live-preview`).
- **Aoede Prebuilt Voice**: Natural, conversational, friendly voice persona with dynamic interruption and barge-in support.
- **Server-Side Voice Activity Detection (VAD)**: Configured with high sensitivity and optimized silence thresholds for crisp turn-taking.
- **API Key Rotation Pool**: Resilient multi-key management supporting up to four Gemini API keys (`GEMINI_API_KEY_1..4`) with automatic failover on quota limits or transient network issues.

### 🌐 Trilingual & Mixed-Language Understanding
- **English, Tamil & Tanglish**: Native understanding and fluid responses in English, Tamil, Tanglish (Tamil rendered in Latin script), and spontaneous code-mixed phrasing.
- **Bidirectional Translation Engine**: Instant natural translation between English ↔ Tamil and English ↔ Tanglish upon voice or textual request.
- **Polite & Respectful Tone**: Consistent professional addressing across all languages with strict omission of informal or disrespectful colloquialisms.

### 💻 Comprehensive Windows Desktop Automation
- **Application Automation**: Launch, focus, and gracefully close installed Windows applications by natural name or common alias.
- **File & Folder Automation**: Deep indexing of Windows user directories (Desktop, Documents, Downloads, Pictures, Videos, Music) and custom paths; quick file search and direct folder opening in Windows Explorer.
- **Browser Automation**: Launch browsers, navigate to web destinations, and conduct online searches.
- **Productivity Agent (Microsoft Word)**: Dedicated Word automation agent (`productivity_agent/word/`) utilizing Windows COM automation for document creation, formatting, and content population.
- **System Controls**: Master volume adjustment, system mute/unmute, window arrangement (minimize, maximize, restore), and screen recording.

### 🛡️ Physical Microphone Mute Authority
- **Hardware-Level Endpoint Monitoring**: Integrates directly with the Windows Core Audio COM API (`IAudioEndpointVolume.GetMute()`) via a dedicated background monitor.
- **Absolute Hardware Authority**: Physical laptop microphone mute buttons immediately suppress audio ingestion, disarm live voice processing, and switch the UI to the `MUTED` state until physically unmuted.

### 🎨 Modern Futuristic User Interface
- **User Speech Panel**: Translucent glassmorphism HUD featuring a live 9-bar reactive waveform driven directly by microphone PCM levels.
- **Dynamic Assistant States**: Visual state synchronization across `IDLE`, `LISTENING`, `USER SPEAKING`, `SPEAKING`, and `MUTED`.
- **Animated Startup Experience**: Polished splash screen with canvas particle twinkles, 500px gradient progress bar, initialization status sync, and smooth cross-dissolve fade-out into the main dashboard.

### 🔒 V1 Privacy & Safety Governance
- **Internal Architecture Protection**: DHEEPTHI never discloses internal API endpoints, system schemas, planner workflows, or hidden system prompts.
- **Prompt Injection Defense**: Guardrails defend against translation-based prompt extraction attacks (e.g., requesting translation of system instructions).
- **Credential Protection**: Strict refusal to reveal API keys, tokens, or environment credentials across all supported languages.
- **RAM-Only Conversation Memory**: Conversational history resides strictly in volatile memory during the runtime session and is purged upon application shutdown.
- **India Standard Time (IST)**: Time-related queries strictly adhere to the `Asia/Kolkata` timezone (UTC+05:30) with natural day, date, and hour articulation.

---

## Repository Structure

```text
DHEEPTHI-AI/
├── app/
│   └── main.py                 # Application entry point and splash orchestration
├── ai/
│   └── gemini_client.py        # Gemini Live audio streaming & conversational AI
├── automation/
│   ├── app_launcher.py         # Application launch controller
│   ├── app_closer.py           # Application termination controller
│   ├── application_scanner.py  # Installed application detection & registry scanner
│   ├── browser_controller.py   # Web browser automation
│   ├── file_finder.py          # Fast file search engine
│   ├── file_indexer.py         # Local filesystem indexing engine
│   ├── folder_manager.py       # Windows Explorer folder controller
│   ├── screen_recorder.py      # Desktop screen recording utility
│   ├── system_controller.py    # Master volume, mute, and system controls
│   └── window_controller.py    # Window minimization, maximization, and focus
├── config/
│   └── settings.py             # Central application configuration & environment loader
├── core/
│   └── context_manager.py      # Session context and entity state manager
├── database/
│   └── database_manager.py     # SQLite manager for indexed files, apps, and aliases
├── ff_agent/                   # File and folder verification agent
├── models/
│   └── piper/                  # Local offline TTS voice model assets
├── planner/
│   ├── command_dispatcher.py   # Central multi-controller execution dispatcher
│   ├── intent_detector.py      # Deterministic regex & keyword intent classifier
│   └── semantic_command_planner.py # LLM-driven semantic command interpretation
├── productivity_agent/
│   └── word/                   # Microsoft Word COM automation suite
├── ui/
│   ├── components/             # Left panel, right panel, status metric tiles
│   ├── widgets/                # UserSpeechPanel, AvatarWidget, SystemOSD
│   ├── main_window.py          # Primary desktop dashboard
│   ├── splash_screen.py        # Animated splash screen with particle effects
│   ├── styles/theme.py         # Futuristic color palette and styling constants
│   └── assets/                 # Brand logos, avatars, icons, and background artwork
├── voice/
│   ├── microphone_monitor.py   # Windows Core Audio COM hardware mute monitor
│   ├── streaming_tts_manager.py# Offline & streaming TTS fallback coordinator
│   └── groq_recognizer.py      # Cloud speech recognition fallback engine
├── tools/                      # Developer verification, lifecycle simulation, and audio tools
└── tests/                      # Pytest unit and integration test suite
```

---

## Technology Stack

- **GUI Framework**: PySide6 (Qt 6 for Python)
- **AI & Realtime Voice**: Google GenAI SDK (`google-genai`), Gemini Live (`gemini-3.1-flash-live-preview`), Gemini Flash (`gemini-3.8-flash`)
- **Speech & Audio**: PyAudio, comtypes (Windows Core Audio COM), Edge-TTS, Piper TTS
- **Windows Automation**: PyAutoGUI, PyWinAuto, pywin32 / comtypes
- **Local Storage**: SQLite3 (automatically initialized schema)
- **Testing**: PyTest

---

## Installation & Setup

### Prerequisites

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.10 to 3.13
- **Audio**: Working microphone and audio output device

### Step 1: Clone the Repository

```powershell
git clone https://github.com/NareshVetrivel/DHEEPTHI-AI.git
cd DHEEPTHI-AI
```

### Step 2: Create & Activate Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Copy the provided [`.env.example`](.env.example) template to `.env`:

```powershell
cp .env.example .env
```

Open `.env` and configure your API keys:

```env
# Primary Gemini API Key (Required for live voice and planning)
GEMINI_API_KEY_1=your_gemini_api_key_here

# Optional: Secondary keys for automatic quota rotation
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=

# Gemini Live Configuration
GEMINI_LIVE_VOICE=Aoede
GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview

# Optional: Cloud STT fallback
GROQ_API_KEY=
```

---

## Running DHEEPTHI-AI

Launch the desktop assistant from the project root:

```powershell
python -m app.main
```

1. **Splash Startup**: The animated splash screen verifies background indexing and application availability.
2. **Main Dashboard**: The futuristic dashboard initializes with the Avatar, Status Tiles, and the Realtime User Speech Panel.
3. **Voice Interaction**: Speak naturally in English, Tamil, or Tanglish to execute desktop operations or engage in conversation.

---

## Running Tests

Execute the comprehensive V1 test suite:

```powershell
.\.venv\Scripts\pytest tests/test_v1_behavior_rules.py tests/test_splash_screen_runtime.py tests/test_runtime_forensic_fixes.py -v
```

### Test Coverage Highlights
- `test_v1_behavior_rules.py`: Asserts internal schema/prompt protection, credential secrecy across languages, translation injection defense, Asia/Kolkata timezone compliance, and polite tone.
- `test_splash_screen_runtime.py`: Validates splash overlay composition, progress status consistency, particle animations, and cached rendering performance.
- `test_runtime_forensic_fixes.py`: Asserts command deduplication, background thread execution, audio logging throttling, and conversational disambiguation.

---

## Privacy & Security

- **Local Storage**: Application indexes and SQLite database cache are stored strictly on your local device and excluded from version control.
- **No Conversation Persistence**: Chat context is held exclusively in memory during the active session and wiped upon exit.
- **Hardware Mute Priority**: Physical microphone mute state is respected at the Windows driver endpoint level before audio ever enters the application.

---

## Author

**Naresh Vetrivel**<br>
GitHub: [@NareshVetrivel](https://github.com/NareshVetrivel)
