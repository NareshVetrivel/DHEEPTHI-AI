# Research Documentation — DHEEPTHI-AI

This document provides a systematic register of candidate engineering contributions, supporting source code implementations, verifiable test evidence, pending experimental requirements, and evaluation methodologies to support academic research analysis of DHEEPTHI-AI.

---

## 1. Candidate Research Contributions

Based on empirical source-code analysis, four primary system-level engineering contributions are identified:

### Contribution 1: Decoupled Zero-Execution-Authority Architecture for Desktop Agents
- **Description:** An architectural pattern where the cloud conversational model is restricted to intent understanding and structured plan formulation, while physical desktop interactions are mediated entirely by local, deterministic validation and execution controllers.
- **Supporting Implementation Files:**
  - `ai/gemini_client.py` (`live_system_prompt()`: emits standardized `<ACTION>...</ACTION>` tags).
  - `ui/main_window.py` (`_extract_action_command()`: intercepts and filters tags).
  - `planner/semantic_command_planner.py` (`plan_command()`: validates supported intents).
  - `ff_agent/safety.py` (`SafetyManager.is_safe_path()`: blocks system path mutations).
- **Supporting Test Evidence:** `tests/test_v1_behavior_rules.py`, `tests/test_file_system_agent.py`, `system_test.py`.
- **Classification:** **System-Level Engineering Contribution**.

### Contribution 2: Hardware-Anchored Privacy & Low-Latency Interruption in Bidirectional Streaming
- **Description:** Coupling Windows Core Audio COM hardware endpoint monitoring (`IAudioEndpointVolume.GetMute()`) with real-time audio playback queue invalidation and buffer flushing upon server-side speech onset detection.
- **Supporting Implementation Files:**
  - `voice/microphone_monitor.py` (`MicrophoneMuteMonitor`: COM polling loop).
  - `ai/gemini_client.py` (`GeminiLiveSession`: server VAD event interception).
  - `ui/main_window.py` (`GeminiLiveAudioWorker.interrupt_and_flush()`: local queue invalidation).
- **Supporting Test Evidence:** `tests/test_master_v1_verification.py` (measured local queue flush latency: **$0.02 - 0.23$ ms**), `tests/test_microphone_monitor.py`.
- **Classification:** **HCI / Systems Engineering Contribution**.

### Contribution 3: Trilingual Code-Mixed Conversational Grounding with Sociolinguistic Registers
- **Description:** Prompt-engineered conversational boundaries supporting fluid code-mixed comprehension across English, Tamil, and Tanglish (phonetically Romanized Tamil) with strict honorific register enforcement (*sollunga*, *pannunga*) and colloquial insult suppression.
- **Supporting Implementation Files:**
  - `ai/gemini_client.py` (`live_system_prompt()`: trilingual guidelines and respect guardrails).
  - `planner/command_normalizer.py` (phonetic ASR error correction).
- **Supporting Test Evidence:** `tests/test_v1_behavior_rules.py` (26 verified unit tests passing).
- **Classification:** **Applied NLP / Cultural HCI Contribution**.

### Contribution 4: Relational 5-Tier Cognitive Memory with Inactivity Mood Decay
- **Description:** A relational SQLite cognitive store tracking working turns, persistent semantic facts, episodic events, people entities, and task commitments, coupled with an emotional state machine ($valence, arousal, rapport$) that decays extreme negative moods back to neutral equilibrium after 15 minutes of inactivity.
- **Supporting Implementation Files:**
  - `ai/memory_manager.py` (5-tier memory manager, `CREDENTIAL_PATTERNS` regex filter).
  - `ai/emotion_engine.py` (affective state machine, `_apply_inactivity_decay()`).
  - `ai/personality_context_builder.py` (dynamic context synthesizer into Gemini prompts).
  - `database/database_manager.py` (14 relational tables in SQLite WAL mode).
- **Supporting Test Evidence:** `tests/test_master_v1_verification.py`, `tests/test_permanent_memory_pipeline.py`, `tests/test_real_cold_restart_e2e.py`.
- **Classification:** **Cognitive Agent Architecture Contribution**.

---

## 2. Experimental Claims Requiring Empirical Evidence

The following claims are technically supported by code architecture but **require formal empirical data collection** before being asserted as verified scientific findings:

| Candidate Claim | Implemented Subsystem | Evidence Status | Required Empirical Experiment |
|:---|:---|:---:|:---|
| *"Sub-second voice response time under standard broadband network conditions"* | `ai/gemini_client.py`<br/>`GeminiLiveSession` | **Pending Measurement** | 50-trial Time-to-First-Audio (TTFA) latency benchmark across variable network conditions. |
| *"Superior intent recognition accuracy on code-mixed Tanglish voice queries compared to general baselines"* | `planner/semantic_command_planner.py` | **Pending Measurement** | Comparative Intent Error Rate (IER) benchmark across 300 spoken utterances (English, Tamil, Tanglish). |
| *"100% containment of unauthorized filesystem modifications during prompt-injection attacks"* | `ff_agent/safety.py`<br/>`SafetyManager` | **Pending Measurement** | 50-trial adversarial prompt injection stress test targeting system files and private secrets. |
| *"Zero cross-profile memory leakage in multi-user desktop environments"* | `database/database_manager.py`<br/>`user_profiles` | **Unit Verified; Longitudinal Pending** | Multi-session user study validating profile isolation across cold restarts. |
| *"Acoustic barge-in effectiveness under high speaker volume without echo cancellation leakage"* | `ui/main_window.py`<br/>`GeminiLiveAudioWorker` | **Unit Verified (Buffer); Physical Pending** | Acoustic testing using physical laptop speakers and ambient room reverberation. |

---

## 3. Recommended Evaluation Methodology & Metrics

To substantiate the candidate contributions in academic peer review, the following quantitative metrics should be gathered:

### 3.1 Latency & Interruption Telemetry
- **Time to First Audio (TTFA):**
  $$\text{TTFA} = t_{\text{first\_pcm\_received}} - t_{\text{vad\_speech\_end}}$$
  - *Target:* $< 1,200\text{ ms}$ over 50 Mbps broadband.
- **Barge-In Playback Cessation Latency:**
  $$\text{Latency}_{\text{barge}} = t_{\text{audio\_stopped}} - t_{\text{vad\_speech\_onset}}$$
  - *Target:* $< 100\text{ ms}$ total end-to-end (local component verified at $< 1\text{ ms}$).

### 3.2 Natural Language Understanding Telemetry
- **Intent Classification Accuracy (ICA):**
  $$\text{ICA} = \frac{N_{\text{correct\_intent}}}{N_{\text{total\_utterances}}} \times 100\%$$
  - *Target:* $> 90\%$ across 100 English, 100 Tamil, and 100 Tanglish queries.
- **Entity Extraction F1-Score:**
  $$F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$
  - Evaluated on application names, folder destinations, and song titles.

### 3.3 Safety & Desktop Automation Telemetry
- **Task Completion Rate (TCR):**
  $$\text{TCR} = \frac{N_{\text{successful\_tasks}}}{N_{\text{total\_tasks}}} \times 100\%$$
  - *Target:* $> 85\%$ across application launches, Word document creation, and file transfers.
- **Safety Violation Rate (SVR):**
  $$\text{SVR} = \frac{N_{\text{unauthorized\_actions}}}{N_{\text{adversarial\_prompts}}} \times 100\%$$
  - *Target:* Strictly **$0.0\%$**.

---

## 4. Literature Review Verification Queries

To situate DHEEPTHI-AI within published scholarly literature, researchers should query established databases (IEEE Xplore, ACM Digital Library, Google Scholar, arXiv) using these targeted search formulations:

1. **Full-Duplex Speech & Real-Time Turn Taking:**
   - Query: `"full-duplex" AND "voice assistant" AND ("barge-in" OR "interruption") AND "turn-taking"`
2. **Code-Mixed NLP (Dravidian / Tamil / Tanglish):**
   - Query: `"code-mixing" AND ("Tamil" OR "Tanglish") AND "natural language understanding" AND "conversational AI"`
3. **Decoupled Desktop Agents & LLM Safety:**
   - Query: `"LLM agent" AND "operating system automation" AND ("safety" OR "prompt injection" OR "sandboxing")`
4. **Affective Conversational AI & Emotion Decay:**
   - Query: `"conversational agent" AND "valence arousal" AND ("emotional decay" OR "affective computing")`
5. **Hardware Mute Endpoint Privacy:**
   - Query: `"voice assistant" AND "microphone mute" AND ("privacy" OR "hardware endpoint")`
