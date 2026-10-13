# Setup and Operations Guide — DHEEPTHI-AI

This document provides setup, configuration, operation, and troubleshooting instructions for DHEEPTHI-AI V1 based on the verified codebase.

---

## 1. System Requirements

### 1.1 Operating System
- **Supported:** Microsoft Windows 10 (Build 19041+) or Windows 11 (64-bit).
- **Unsupported:** Linux and macOS (due to direct dependencies on Windows Core Audio COM, `pywinauto`, `pycaw`, Win32 COM, and Windows Registry APIs).

### 1.2 Python Runtime
- **Python Version:** Python 3.10 through Python 3.13 (64-bit).

### 1.3 Hardware Requirements
- **Audio Capture:** Working microphone configured as the Windows Default Audio Input device.
- **Audio Output:** Functioning speakers or headphones set as the Default Audio Output device.
- **Processor:** Dual-core x86_64 CPU or higher (quad-core recommended for ONNX neural TTS inference).
- **Memory:** Minimum 4 GB RAM (8 GB recommended).
- **Storage:** Minimum 1 GB free disk space for dependencies and offline Piper neural models.

### 1.4 Optional Software Dependencies
- **Microsoft Word Automation:** Requires Microsoft Office Word installed locally with Win32 COM registered.
- **Chrome Automation:** Google Chrome or Microsoft Edge installed in default program locations.

---

## 2. Installation & Dependency Setup

### Step 1: Clone Repository
```powershell
git clone https://github.com/NareshVetrivel/DHEEPTHI-AI.git
cd DHEEPTHI-AI
```

### Step 2: Create and Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Core Dependencies
Install the pinned dependencies from `requirements.txt`:
```powershell
pip install -r requirements.txt
```

*Key Packages Installed:*
- AI & LLM: `google-genai==2.17.0`, `groq==1.7.0`, `httpx==0.28.1`, `pydantic==2.13.4`, `websockets==16.1.1`
- UI: `PySide6==6.11.1`, `pillow==12.3.0`
- Audio & TTS: `sounddevice==0.5.5`, `edge-tts==7.2.8`, `piper-tts==1.6.1`, `onnxruntime==1.27.0`, `pyttsx3==2.99`, `pygame==2.6.1`
- OS Automation: `comtypes==1.4.16`, `pycaw==20251023`, `pywin32==312`, `pywinauto==0.6.9`, `PyAutoGUI==0.9.54`, `screen_brightness_control==0.27.2`, `psutil==7.2.2`, `Send2Trash==2.1.0`
- Browser: `playwright==1.61.0`
- Vision & Media: `mss==10.2.0`, `opencv-python==5.0.0.93`, `numpy==2.5.1`
- Utilities: `watchdog==6.0.0`, `python-dotenv==1.2.2`, `RapidFuzz==3.14.5`, `pathvalidate==3.3.1`

---

## 3. Configuration & Environment Variables

Copy the template [`.env.example`](../.env.example) to `.env`:
```powershell
cp .env.example .env
```

Open `.env` in an editor and configure the necessary variables (do not commit `.env` to version control):

| Environment Variable | Description | Default Value | Required? |
|:---|:---|:---|:---:|
| `GEMINI_API_KEY_1` | Primary Google GenAI API key for Gemini Live and Gemini Flash | `""` | **Yes** |
| `GEMINI_API_KEY_2` | Secondary backup key for automatic quota rotation | `""` | No |
| `GEMINI_API_KEY_3` | Tertiary backup key for automatic quota rotation | `""` | No |
| `GEMINI_API_KEY_4` | Quaternary backup key for automatic quota rotation | `""` | No |
| `GEMINI_MODEL` | Default conversational model | `gemini-3.8-flash` | No |
| `GEMINI_PLANNER_PRIMARY_MODEL` | Primary model for semantic planning | `gemini-3.8-flash` | No |
| `GEMINI_PLANNER_FALLBACK_1` | First fallback planner model | `gemini-3.6-flash` | No |
| `GEMINI_PLANNER_FALLBACK_2` | Second fallback planner model | `gemini-3.5-flash` | No |
| `GEMINI_LIVE_MODEL` | Bidirectional audio streaming model | `gemini-3.1-flash-live-preview` | No |
| `GEMINI_LIVE_VOICE` | Prebuilt voice persona (`Aoede`, `Kore`, `Puck`, `Charon`, `Fenrir`) | `Aoede` | No |
| `GEMINI_LIVE_START_SENSITIVITY` | VAD start of speech sensitivity | `START_SENSITIVITY_HIGH` | No |
| `GEMINI_LIVE_END_SENSITIVITY` | VAD end of speech sensitivity | `END_SENSITIVITY_HIGH` | No |
| `GEMINI_LIVE_SILENCE_DURATION_MS` | VAD silence duration threshold (ms) | `600` | No |
| `GROQ_API_KEY` | Groq Cloud STT fallback key (`whisper-large-v3-turbo`) | `""` | No |
| `GROQ_API_KEY_CODE_AGENT` | Dedicated Groq key for autonomous code generation | `""` | No |
| `GEMINI_VISION_API_KEY` | Dedicated key for screen vision & Cloud OCR | `""` | No |
| `DEBUG` | Enable verbose diagnostic logging | `false` | No |
| `DEBUG_AUDIO_VERBOSE` | Enable detailed audio streaming packet logs | `false` | No |

---

## 4. Application Operations

### Launching the Application
Launch the assistant from the project root:
```powershell
python -m app.main
```

### Operational Lifecycle:
1. **Startup:** The particle-animated splash screen appears. Background workers scan Start Menu applications and index user documents into SQLite.
2. **Dashboard Ready:** The maximized main window cross-dissolves into view, displaying the Avatar widget, status tiles, and User Speech Panel HUD.
3. **Voice Interaction:** Speak into the microphone in English, Tamil, or Tanglish.
4. **Physical Mute:** Pressing the laptop's physical microphone mute key immediately transitions the UI state to `MUTED` and halts audio streaming.
5. **Shutdown:** Click the top-right `[X]` button or speak "Shutdown" / "Exit".

---

## 5. Troubleshooting & Diagnostic Guide

### Problem 1: Qt QFont Warning on Hover
- **Symptom:** Warning in console: `QFont::setPointSize: Point size <= 0 (-1), must be greater than 0`.
- **Cause:** Qt rendering artifact triggered when hovering over custom title-bar controls.
- **Resolution:** This warning is automatically suppressed by `dheepthi_qt_message_handler()` in `app/main.py`. It is non-fatal.

### Problem 2: Gemini Live Session Connection Timeout
- **Symptom:** Application reports `Timed out while connecting to Gemini Live API`.
- **Cause:** Network firewall, invalid `GEMINI_API_KEY_1`, or temporary preview endpoint unavailability.
- **Resolution:** 
  1. Confirm internet connectivity.
  2. Verify that `GEMINI_API_KEY_1` in `.env` is valid and has Google GenAI preview access.
  3. Ensure secondary keys (`GEMINI_API_KEY_2..4`) are configured for automatic fallback.

### Problem 3: Microsoft Word Automation Fails
- **Symptom:** Spoken Word command reports `Word automation unavailable`.
- **Cause:** Microsoft Office Word is not installed locally or COM registration is corrupted.
- **Resolution:** Ensure desktop Microsoft Office is installed. Run Word once manually to verify that Windows COM registration completes.

### Problem 4: Physical Microphone Stays in MUTED State
- **Symptom:** UI displays `MUTED` and does not accept speech input.
- **Cause:** Windows Default Capture Endpoint is physically muted or toggled in Windows Sound Settings.
- **Resolution:** Press the physical laptop microphone mute button or open Windows Sound Settings and unmute the default capture device.
