# Testing and Validation — DHEEPTHI-AI

This document provides a comprehensive inventory of the automated test suites in DHEEPTHI-AI V1, details the tests executed during this audit, documents verified test outcomes, and identifies untested behaviors and environmental limitations.

---

## 1. Test Suite Inventory

The repository contains **63 test files** in `tests/` and **15 verification scripts** in `tools/`:

| Test File | Primary Target Module | Subsystem / Requirement Tested |
|:---|:---|:---|
| `test_master_v1_verification.py` | `ai/gemini_client.py`, `ui/main_window.py` | Model standardization, barge-in buffer flush (<100ms), SQLite turn persistence, memory recall |
| `test_v1_behavior_rules.py` | `ai/gemini_client.py`, `planner/*` | System prompt guardrails, credential hiding, Asian timezone enforcement, respectful addressing |
| `test_gemini_keys.py` | `ai/gemini_client.py` | 4-key rotation pool, HTTP 429 quota exhaustion, invalid key recovery |
| `test_gemini_live_lifecycle.py` | `ai/gemini_client.py` | Gemini Live WebSocket connection, VAD events, server GoAway notifications |
| `test_gemini_live_persistent_memory.py`| `ai/memory_manager.py` | Live session fact ingestion, cold-restart fact recall from SQLite |
| `test_real_cold_restart_e2e.py` | `database/database_manager.py` | Application shutdown and cold boot; SQLite state restoration |
| `test_permanent_memory_pipeline.py` | `ai/memory_manager.py` | Credential scrubbing regex, 5-tier relational database tables |
| `test_microphone_monitor.py` | `voice/microphone_monitor.py` | Windows Core Audio COM endpoint polling (`IAudioEndpointVolume.GetMute()`) |
| `test_no_wake_word_runtime.py` | `ui/main_window.py`, `workers/*` | Verifies elimination of legacy wake-word listeners and Vosk models |
| `test_code_agent.py` | `code_agent/agent.py` | Groq code generation, file creation, subprocess execution, compile-repair retry loop |
| `test_file_system_agent.py` | `automation/file_system_agent.py` | File search, path resolution, copy, move, delete recycling |
| `test_file_folder_manager.py` | `automation/file_manager.py` | File operations, zip archive creation and extraction |
| `test_word_v1.py` | `productivity_agent/word/*` | Microsoft Word Win32 COM document creation, paragraph typing, verification |
| `test_word_automation.py` | `productivity_agent/word/automation.py` | Word automation error handling and COM dispatch |
| `test_system_controller.py` | `automation/system_controller.py` | Volume percentage adjustment (`pycaw`), brightness, screenshot capture |
| `test_keyboard_controller.py` | `automation/keyboard_controller.py` | Foreground window focus activation, virtual keystroke simulation |
| `test_mouse_controller.py` | `automation/mouse_controller.py` | Mouse click, double click, right click, and scroll simulation |
| `test_window_controller.py` | `automation/window_controller.py` | Window focus, title extraction, minimize, maximize, restore |
| `test_app_launcher.py` | `automation/app_launcher.py` | Process launching via Start Menu shortcut and Registry paths |
| `test_app_closer.py` | `automation/app_closer.py` | Window closing signals, process termination via `psutil` |
| `test_text_to_speech.py` | `voice/text_to_speech.py` | Unified TTS manager, multi-engine fallback (Edge $\rightarrow$ Piper $\rightarrow$ SAPI5) |
| `test_streaming_tts_manager.py` | `voice/streaming_tts_manager.py` | Chunked audio synthesis coordination for streaming text |
| `test_groq_recognizer.py` | `voice/groq_recognizer.py` | Groq `whisper-large-v3-turbo` STT over direct `httpx` multipart transport |
| `test_gemini_vision.py` | `vision/gemini_vision.py` | Cloud screen understanding via Gemini Vision, key rotation |
| `test_user_speech_panel.py` | `ui/widgets/user_speech_panel.py` | HUD text formatting, 9-bar reactive audio visualizer math |
| `test_splash_screen_runtime.py` | `ui/splash_screen.py` | Particle animation engine, progress bar updates, cross-dissolve |
| `test_rich_identity_and_memory.py` | `ai/memory_manager.py` | Reconciles speaker identity with creator metadata (Naresh & Ragavendhiran) |
| `verify_cold_restart_multi_process.py` | `database/database_manager.py` | Multi-process SQLite cold-restart validation |

---

## 2. Tests Actually Executed & Verified Outcomes

During this audit, the following test suites were executed within the project's virtual environment (`.\.venv\Scripts\python.exe` and `pytest.exe`):

### Execution 1: Master V1 Verification Suite
- **Command Run:**
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests/test_master_v1_verification.py
  ```
- **Observed Result:**
  ```text
  Ran 18 tests in 22.867s
  OK
  ```
- **Verified Capabilities:**
  1. Standardization on `gemini-3.8-flash` across client, vision, OCR, and planner hierarchy.
  2. Gemini Live model independence (`gemini-3.1-flash-live-preview`).
  3. Real-time voice interruption (barge-in): Local queue flush latency measured at **$0.02 - 0.23$ ms** (well below the 100 ms target).
  4. Stale audio rejection: In-flight response packets with old generation IDs rejected (`[LIVE STALE] action=enqueue_rejected`).
  5. SQLite conversation turn persistence: Verified immediate capture into `conversation_context`.
  6. Permanent memory & family relationship extraction: Verified multi-relation extraction in English/Tanglish (`Suresh (brother)`, `Ramesh (father)`).
  7. Relationship fact correction: Updating relationship (*Suresh* $\rightarrow$ *Vignesh*) successfully supersedes old record.
  8. Per-user profile isolation: Verified records scoped by `profile_id`.

### Execution 2: Behavior & System Rules Suite (Pytest)
- **Command Run:**
  ```powershell
  .\.venv\Scripts\pytest.exe tests/test_v1_behavior_rules.py
  ```
- **Observed Result:**
  ```text
  ============================= 26 passed in 53.20s =============================
  ```
- **Verified Capabilities:**
  1. Internal workflows, database schemas, and private variables are never disclosed.
  2. API keys and secrets are protected against direct inquiry and translation jailbreaks.
  3. Current time deterministically utilizes `Asia/Kolkata` (UTC+05:30) timezone.
  4. Time queries return accurate day, date, and hour articulation across English, Tamil, and Tanglish.
  5. English $\leftrightarrow$ Tamil and English $\leftrightarrow$ Tanglish translation directives.
  6. Respectful addressing enforced (*sollunga*, *pannunga*); disrespectful colloquialisms rejected (*da*, *vaada*, *poda*).

### Execution 3: System Verification Script
- **Command Run:**
  ```powershell
  .\.venv\Scripts\python.exe system_test.py
  ```
- **Observed Result:**
  ```text
  [1/5] Verifying Settings... OK
  [2/5] Verifying Gemini Client & Live Configuration... OK
  [3/5] Verifying Physical Microphone Monitor... OK
  [4/5] Verifying ACTION Extractor & Semantic Planner... OK
  [5/5] Verifying Command Dispatcher... OK
  ALL SYSTEM SUBSYSTEMS VERIFIED SUCCESSFULLY
  ```

---

## 3. Untested Behaviors & Environmental Limitations

1. **Physical Audio Loopback & Acoustic Echo Cancellation:**
   - Unit tests use synthetic PCM buffers and mock audio streams. Real-world acoustic barge-in testing requires physical laptop speakers and room acoustics to evaluate whether assistant speech bleeds back into the microphone.
2. **Microsoft Word COM in Headless Environments:**
   - Tests in `test_word_v1.py` require a graphical Windows desktop session with locally installed Microsoft Office Word registered under COM. These fail in headless CI environments.
3. **Playwright Persistent Chrome Sessions:**
   - Tests expecting an attached Chrome debugging port (`127.0.0.1:9222`) require a running Chrome instance started with `--remote-debugging-port=9222`.
4. **Active Google GenAI WebSocket Live Connectivity:**
   - Full live voice turns require valid, active internet connectivity and non-exhausted API quotas. Network timeouts or quota limits will force fallback to Groq or text mode.

---

## 4. Reproducible Commands for Running Tests

To run the verified test suites safely in your local environment without altering persistent databases:

```powershell
# 1. Activate Virtual Environment
.\.venv\Scripts\Activate.ps1

# 2. Run Master V1 Verification Suite (Unittest)
python -m unittest tests/test_master_v1_verification.py

# 3. Run Behavior & Prompt Guardrails Suite (Pytest)
pytest tests/test_v1_behavior_rules.py

# 4. Run System Subsystem Verification Test
python system_test.py

# 5. Run Memory Pipeline & Credential Redaction Suite
python -m unittest tests/test_permanent_memory_pipeline.py

# 6. Run Cold Restart End-to-End Simulation Suite
python -m unittest tests/test_real_cold_restart_e2e.py

# 7. Run Code Agent Automation Suite
pytest tests/test_code_agent.py
```
