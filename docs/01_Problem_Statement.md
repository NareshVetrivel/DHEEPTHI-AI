# Problem Statement — DHEEPTHI-AI

## 1. Background

Mainstream conversational voice assistants (e.g., Apple Siri, Google Assistant, Amazon Alexa, Microsoft Cortana) were fundamentally architected for cloud-tethered mobile ecosystems, ambient smart-home appliances, and simple information retrieval. While effective for setting alarms, querying weather forecasts, and basic web lookups, these systems exhibit major architectural and functional deficiencies when deployed as desktop productivity companions on personal computers:

1. **Lack of Native Operating System Automation:** Conventional assistants operate within tightly sandboxed mobile runtime environments with negligible integration into host desktop operating systems (such as Microsoft Windows). They cannot manage running processes, inspect local filesystems, automate desktop productivity suites (such as Microsoft Word via COM automation), or configure hardware peripherals.
2. **Turn-Based Latency and Rigid Half-Duplex Interaction:** Traditional assistants rely on rigid, half-duplex cascading pipelines: Push-to-Talk / Wake-Word Detection $\rightarrow$ Speech-to-Text (STT) $\rightarrow$ Cloud Large Language Model (LLM) $\rightarrow$ Text-to-Speech (TTS). This introduces significant end-to-end latency (typically 2.5 to 5+ seconds) and precludes natural conversational dynamics such as real-time barge-in, immediate interruption, and bidirectional continuous streaming.
3. **Linguistic and Cultural Inflexibility in Code-Mixed Contexts:** Existing voice agents struggle with multilingual code-switching and code-mixing—specifically English, Tamil, and Tanglish (Tamil expressed phonetically in Latin script). Spoken interactions often collapse into either rigid formal literary Tamil (which sounds unnatural when synthesized) or fail entirely to interpret phonetic vernacular commands common across bilingual users.
4. **Weak Memory and Context Continuity:** General-purpose assistants possess ephemeral session memory or broad, uncurated cloud profiles that lack local ownership. They cannot reliably maintain persistent multi-tiered memory (user facts, family relationships, commitments, and emotional rapport) across application restarts without leaking private credentials.
5. **Security Dilemma in Agentic Automation:** When emerging LLM-based autonomous agents are granted operating system access, they frequently rely on dangerous execution paradigms—such as allowing the cloud model to generate and directly execute arbitrary shell commands or Python scripts. This creates extreme vulnerability to prompt-injection attacks, unintended file deletion, and data destruction.

## 2. Problem Definition

Desktop users routinely perform complex, repetitive workflows on Windows workstations: navigating directory hierarchies, managing running applications, synthesizing formatted documents, searching media, and configuring system settings. Currently, there is no desktop assistant that simultaneously achieves:

- **Low-Latency, Full-Duplex Voice Dialogue:** Continuous bidirectional audio streaming with sub-second response times and immediate speech interruption (barge-in).
- **Trilingual Comprehension:** Fluent, culturally respectful understanding across English, Tamil, and Tanglish without dialectal breakdown.
- **Safe, Decoupled Desktop Task Execution:** Translating natural language requests into complex multi-step operating system actions while strictly denying the cloud LLM direct shell execution authority.
- **Hardware-Anchored Endpoint Privacy:** Ensuring that when physical hardware microphone switches are engaged, audio streaming to third-party cloud endpoints is deterministically severed at the operating system root.
- **Durable Local Cognitive State:** Maintaining a structured, privacy-preserving local relational memory that survives cold restarts and adapts conversational tone based on affective state.

## 3. The Research and Engineering Gap

| Dimension | Existing Commercial Assistants | Academic Agentic Frameworks (AutoGPT, OpenInterpreter) | DHEEPTHI-AI Target Architecture |
|:---|:---|:---|:---|
| **Voice Interaction** | Half-duplex, wake-word triggered, turn-based cascade (2–5s latency) | Primarily text-based terminal interfaces; voice added as slow external wrapper | Full-duplex persistent bidirectional PCM streaming via Gemini Live with server-side VAD |
| **Barge-In Interruption** | Poor or absent; requires speaking over output or waiting for turn end | Not supported | Sub-millisecond local playback buffer flushing and stale audio packet rejection |
| **OS Automation** | Web/API services only; minimal local OS control | Unrestricted shell execution (`bash`/`cmd`), high prompt-injection risk | **Decoupled Security Model:** LLM outputs structured action plans; local deterministic controllers execute with safety checks |
| **Language Support** | Separate monolingual models; failure on phonetic code-mixing | English-centric; poor vernacular code-mixed understanding | Native trilingual understanding across English, Tamil, and phonetic Tanglish with social register boundaries |
| **Memory Architecture** | Opaque cloud profile; vendor lock-in | In-memory context window or vector store prone to hallucination | 5-tier relational SQLite store with automated credential regex scrubbing and profile isolation |
| **Hardware Privacy** | Software mute toggle; client often continues processing | Relies on OS microphone permissions | Windows Core Audio COM polling (`IAudioEndpointVolume.GetMute()`) disarming stream at endpoint level |

## 4. Proposed Solution

**DHEEPTHI-AI** addresses this gap by implementing an intelligent, context-aware Windows desktop assistant that decouples high-level cognitive reasoning from local physical execution.

The architecture combines:
1. **Google GenAI Live Streaming:** Bidirectional WebSocket audio streaming (`gemini-3.1-flash-live-preview`) with server-side voice activity detection calibrated at 600 ms silence duration and prebuilt voice synthesis (`Aoede`).
2. **Decoupled Action Tag Dispatch:** The cloud conversational model emits standardized action blocks (`<ACTION>...</ACTION>`) embedded within natural dialogue. The desktop client intercepts and sanitizes these tags, routing them through deterministic planners (`SemanticCommandPlanner`) and validation gates (`SafetyManager`) before reaching local Python automation controllers (`AppLauncher`, `FileFolderAgent`, `WordAgent`, `BrowserController`, `SystemController`, `CodeAgent`).
3. **Core Audio COM Hardware Interceptor:** Direct polling of the Windows default capture endpoint to respect laptop physical mute switches.
4. **Relational SQLite Cognitive Hierarchy:** A local database (`database/astra.db`) housing working memory, semantic user facts, personal memories, task commitments, and an affective state machine (`EmotionEngine`) with time-based decay.
5. **PySide6 Real-Time HUD Dashboard:** A translucent glassmorphic interface featuring a live user transcript display, a 9-bar audio-reactive visualizer, and system telemetry tiles.