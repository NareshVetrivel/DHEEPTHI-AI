# Project Objectives — DHEEPTHI-AI

## 1. Primary Objective

To design, engineer, and validate an adaptive, context-aware full-duplex desktop AI voice assistant for Microsoft Windows that integrates low-latency bidirectional cloud speech streaming with a decoupled, zero-execution-authority local operating system automation architecture, trilingual conversational comprehension (English, Tamil, Tanglish), and durable relational memory.

---

## 2. Specific Technical Objectives

The project is structured around twelve measurable engineering and architectural objectives:

### 2.1 Persistent Full-Duplex Voice Interaction
- Implement persistent, bidirectional audio streaming between the Windows desktop client and the **Google GenAI Live API** (`gemini-3.1-flash-live-preview`), streaming raw 16 kHz mono 16-bit PCM uplink and playing 24 kHz mono PCM downlink.
- Leverage server-side Voice Activity Detection (VAD) configured with high start/end sensitivity thresholds and a calibrated 600 ms silence duration to eliminate manual push-to-talk delays and wake-word listener overhead.
- Engineer a dynamic barge-in interruption engine capable of truncating active assistant playback in sub-millisecond local processing time upon detecting user speech onset, invalidating in-flight generation IDs and discarding stale audio chunks.

### 2.2 Trilingual & Code-Mixed Understanding
- Provide fluent natural language comprehension across pure English, pure Tamil, and Tanglish (phonetically Latin-scripted Tamil) within a unified conversational turn.
- Support real-time, bidirectional voice translation between English $\leftrightarrow$ Tamil and English $\leftrightarrow$ Tanglish.
- Enforce strict sociolinguistic behavioral guardrails ensuring polite, respectful address forms (*sollunga*, *pannunga*, *vaanga*) and deterministically suppressing informal or disrespectful colloquialisms (*da*, *vaada*, *poda*).

### 2.3 Decoupled Desktop Automation Architecture
- Design and enforce a **zero-authority security boundary** where cloud models possess no direct OS command execution permissions.
- Structure conversational output so that actionable requests produce standardized `<ACTION>command</ACTION>` tags or structured JSON plans.
- Route extracted action directives through local deterministic Python automation controllers:
  - **Process Management:** Launch, switch, and gracefully close applications via Start Menu and Registry scanning (`AppLauncher`, `AppCloser`, `ApplicationScanner`).
  - **Filesystem Operations:** Safe multi-step file and folder navigation, fuzzy searching, candidate disambiguation, and verified file operations (`FileFolderAgent`, `FileSystemAgent`).
  - **Browser Automation:** Automated navigation, web queries, and YouTube video streaming via Chrome/Edge sessions (`BrowserController`, `PlaywrightController`).
  - **Productivity Synthesis:** Programmatic Microsoft Word document generation and text formatting via Win32 COM automation (`WordAgent`, `WordAutomation`).
  - **System Controls:** Master audio endpoint control via `pycaw`, display brightness management, screen recording, and screenshot capture (`SystemController`).

### 2.4 Autonomous Code Generation & Self-Repair
- Provide an integrated autonomous programming agent (`CodeAgent`) utilizing dedicated cloud models (`openai/gpt-oss-20b` via Groq) to synthesize Python and Java source code.
- Implement an automated compile, execute, and repair feedback loop that captures standard error outputs and retries code generation up to three attempts before reporting status.

### 2.5 Hardware-Anchored Endpoint Privacy
- Monitor the Windows Default Audio Capture Endpoint (`IAudioEndpointVolume.GetMute()`) directly via Windows Core Audio COM APIs (`comtypes`).
- Ensure that activating the laptop's physical microphone mute key immediately disarms cloud audio streaming at the operating system root and updates the UI state to `MUTED`.

### 2.6 Durable 5-Tier Relational Memory & Cognitive State
- Establish a local SQLite relational database (`database/astra.db`) configured with Write-Ahead Logging (`WAL`) mode to store:
  - Working conversation turns (`conversation_context`).
  - Persistent user preferences and semantic profile facts (`user_context`).
  - Significant interaction milestones (`memory_episodes`).
  - Interpersonal relationship entities (`people`).
  - Task commitments and pending directives (`tasks`).
- Implement automated regex-based credential scrubbing prior to storage to block accidental exposure of passwords, API keys, tokens, and credit card numbers.
- Provide user profile isolation (`user_profiles`) and reconcile user identity with static creator metadata (`Naresh` and `Ragavendhiran`).

### 2.7 Affective State Modeling with Inactivity Decay
- Implement an affective computing state machine (`EmotionEngine`) tracking emotional valence, arousal, and rapport levels across supported moods (*neutral*, *happy*, *caring*, *hurt*, *annoyed*, *playful*).
- Formulate a 15-minute inactivity decay mechanism that smoothly resets extreme negative emotions back to baseline equilibrium upon prolonged user absence or cold restart.
- Restrict emotional state influences strictly to conversational tone modulation, ensuring zero modification of desktop automation parameters.

### 2.8 Resilient Multi-Provider Fallback Hierarchies
- Provide automated fallback cascades across all critical subsystems:
  - **LLM Reasoning:** `gemini-3.8-flash` $\rightarrow$ `gemini-3.6-flash` $\rightarrow$ `gemini-3.5-flash` $\rightarrow$ Groq cloud planner.
  - **Speech Synthesis:** Gemini Live `Aoede` voice $\rightarrow$ Microsoft Edge Neural TTS $\rightarrow$ Local Piper ONNX (`en_US-hfc_female-medium`) $\rightarrow$ Windows SAPI5 (`pyttsx3`).
  - **API Key Quota:** Dynamic rotation across a pool of four keys (`GEMINI_API_KEY_1..4`) upon encountering HTTP 429 quota limits.
  - **Speech-to-Text Fallback:** Direct `httpx` multipart transport for Groq `whisper-large-v3-turbo` when WebSocket streaming is offline.

### 2.9 Modern Futuristic User Interface
- Build an interactive, hardware-accelerated PySide6 interface featuring:
  - Real-time User Speech HUD displaying live speech transcriptions without clipping.
  - Audio-reactive 9-bar visualizer animated by incoming microphone PCM amplitude.
  - Synchronized visual avatar reflecting emotional states and operational modes (`IDLE`, `LISTENING`, `USER SPEAKING`, `SPEAKING`, `MUTED`).
  - Animated startup splash screen with drifting canvas particle twinkles and smooth cross-dissolve window transitions.

---

## 3. Expected Technical Outcomes

Upon complete execution and validation of these objectives, DHEEPTHI-AI demonstrates:
1. **Low Voice Latency:** Responsive spoken dialogue capable of handling mid-sentence user interruptions.
2. **Deterministic OS Safety:** Elimination of unconstrained shell execution risks through validated action dispatch.
3. **Cross-Restart Knowledge Retention:** Restoration of user facts, identity directives, and relationship contexts across application reboot cycles.
4. **Resilience to Network and Quota Disruptions:** Seamless degradation to alternative local/cloud providers without application crashes.