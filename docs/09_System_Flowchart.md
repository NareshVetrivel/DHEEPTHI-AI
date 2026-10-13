# System Flowcharts — DHEEPTHI-AI

This document provides comprehensive flowcharts detailing the primary runtime lifecycles and decision processes of DHEEPTHI-AI V1.

---

## 1. Application Startup & Background Initialization Lifecycle

```mermaid
flowchart TD
    START([Launch: python -m app.main]) --> APP_INIT[Initialize QApplication & Set AppUserModelID]
    APP_INIT --> HNDLR[Install Global Qt Message Handler]
    HNDLR --> WIN_CREATE[Instantiate MainWindow & Load Assets]
    WIN_CREATE --> SHOW_SPLASH[Display SplashScreen with Particle Animation]
    SHOW_SPLASH --> WORKER_START[Spawn Background InitializationWorker]
    
    subgraph Background_Worker ["Background Worker Thread"]
        WORKER_START --> SCAN_APPS[ApplicationScanner: Scan Start Menu & Registry]
        SCAN_APPS --> UPDATE_P1[Emit Progress: 0% -> 50%]
        UPDATE_P1 --> INDEX_FILES[FileIndexer: Scan User Folders & Index to SQLite]
        INDEX_FILES --> UPDATE_P2[Emit Progress: 50% -> 100%]
        UPDATE_P2 --> WORKER_DONE([Finished Success Signal])
    end

    WORKER_DONE --> CROSS_DISSOLVE[Cross-Dissolve Transition: Fade Splash]
    CROSS_DISSOLVE --> WIN_MAX[Show MainWindow Maximized]
    WIN_MAX --> CONNECT_COM[Start MicrophoneMuteMonitor Thread]
    CONNECT_COM --> CONNECT_LIVE[Spawn GeminiLiveSession Background Loop]
    CONNECT_LIVE --> READY([Application Ready: Listening])
```

---

## 2. Full-Duplex Voice Streaming & Barge-In Interruption Flow

```mermaid
flowchart TD
    MIC_IN[User Speaks into Physical Microphone] --> COM_CHECK{MicrophoneMuteMonitor: Is Endpoint Muted?}
    COM_CHECK -- Yes --> DISARM[Disarm Uplink & Switch UI to MUTED]
    COM_CHECK -- No --> CAPTURE[sounddevice: 16 kHz Mono PCM Capture]
    
    CAPTURE --> STREAM_UP[Send PCM Uplink to Gemini Live WebSocket]
    STREAM_UP --> VAD_EVAL{Server VAD: Silence >= 600ms?}
    VAD_EVAL -- No --> STREAM_UP
    VAD_EVAL -- Yes --> GEN_DOWN[Generate 24 kHz Aoede Downlink Audio & Transcript]
    
    GEN_DOWN --> PLAY_START[Enqueue PCM Chunk to Output Buffer & Play]
    
    subgraph Playback_And_Barge_In ["Playback & Barge-In Detection"]
        PLAY_START --> PLAYING[Audio Playing through Speakers]
        PLAYING --> CHECK_INTERRUPT{User Speaks Mid-Playback?}
        CHECK_INTERRUPT -- No --> PLAY_DONE[Playback Completes Normally]
        CHECK_INTERRUPT -- Yes --> VAD_START[Server VAD Emits START Event]
        VAD_START --> FLUSH[GeminiLiveAudioWorker.interrupt_and_flush]
        FLUSH --> STOP_SPEAKER[Cease Speaker Output (< 1ms)]
        STOP_SPEAKER --> CLEAR_QUEUE[Flush Local Queue & Invalidate Response ID]
        CLEAR_QUEUE --> DROP_STALE[Drop In-Flight Stale Cloud Packets]
        DROP_STALE --> NEW_TURN[Transition to USER SPEAKING State]
    end
```

---

## 3. Spoken Command Dispatch & Local Execution Flow

```mermaid
flowchart TD
    RX_TRANSCRIPT[Receive Finalized Assistant Output Transcript] --> TAG_CHECK{Contains inline <ACTION>...</ACTION>?}
    
    TAG_CHECK -- No --> CONV_ONLY[Pure Conversational Reply: Audio Played to User]
    
    TAG_CHECK -- Yes --> EXTRACT[MainWindow._extract_action_command]
    EXTRACT --> HIDE_UI[Filter <ACTION> Tag from UserSpeechPanel HUD]
    HIDE_UI --> SCP_PLAN[SemanticCommandPlanner.plan_command]
    
    SCP_PLAN --> INTENT_MATCH{Match Intent Type}
    
    INTENT_MATCH -- Application --> APP_ROUTE[AppLauncher / AppCloser]
    INTENT_MATCH -- Browser / YouTube --> BROWSER_ROUTE[BrowserController / Playwright]
    INTENT_MATCH -- Filesystem --> FS_ROUTE[FileFolderAgent Disambiguation Flow]
    INTENT_MATCH -- Word Document --> WORD_ROUTE[WordAgent Win32 COM Automation]
    INTENT_MATCH -- System Setting --> SYS_ROUTE[SystemController: Volume / Brightness]
    INTENT_MATCH -- Coding Request --> CODE_ROUTE[CodeAgent Self-Repair Loop]
    
    APP_ROUTE --> EXEC_DONE[Execute Deterministic Action]
    BROWSER_ROUTE --> EXEC_DONE
    FS_ROUTE --> EXEC_DONE
    WORD_ROUTE --> EXEC_DONE
    SYS_ROUTE --> EXEC_DONE
    CODE_ROUTE --> EXEC_DONE
    
    EXEC_DONE --> LOG_DB[Log to SQLite: conversation_context & command_history]
    LOG_DB --> UPDATE_HUD[Update SystemOSD & UI Telemetry Tiles]
```

---

## 4. Filesystem Disambiguation & Safety Flow

```mermaid
flowchart TD
    CMD_IN[Spoken Filesystem Operation: e.g. 'Delete report.pdf'] --> SAFE_CHECK{SafetyManager: Is Target Protected?}
    
    SAFE_CHECK -- Yes (C:\Windows, System32, Root) --> BLOCK[Block Execution & Raise Security Warning]
    
    SAFE_CHECK -- No --> SEARCH[FileFinder: Search Indexed Files in SQLite & Disk]
    SEARCH --> COUNT_CHECK{Candidate Count Matching Query}
    
    COUNT_CHECK -- 0 Candidates --> NOT_FOUND[Report File Not Found via Voice]
    COUNT_CHECK -- 1 Exact Match --> CONFIRM_REQ{Is Operation Destructive?}
    COUNT_CHECK -- >1 Multiple Matches --> SHOW_PANEL[Display FileSelectionPanel in UI]
    
    SHOW_PANEL --> USER_CHOOSE[User Selects Candidate via Click or Voice]
    USER_CHOOSE --> CONFIRM_REQ
    
    CONFIRM_REQ -- Non-Destructive (Open/Copy) --> DO_EXEC[Execute via FileSystemAgent]
    CONFIRM_REQ -- Destructive (Delete/Move) --> MODAL_PROMPT[Prompt User Confirmation]
    
    MODAL_PROMPT -- User Cancels --> ABORT[Operation Cancelled Safely]
    MODAL_PROMPT -- User Confirms --> RECYCLE[Send2Trash: Recycle Target File]
    
    RECYCLE --> VERIFY[ExecutionVerifier: Confirm File Removed]
    DO_EXEC --> VERIFY
    VERIFY --> CONFIRM_VOICE[Vocal Confirmation to User]
```

---

## 5. Autonomous Code Agent Self-Repair Flow

```mermaid
flowchart TD
    CODE_REQ[Spoken Coding Request: Language & Task Description] --> GEN_PROMPT[CodeAgent: Build Prompt for Groq]
    GEN_PROMPT --> GROQ_CALL[Call Groq ChatCompletion: openai/gpt-oss-20b]
    GROQ_CALL --> WRITE_DISK[Write Code to ~/Desktop/DHEEPTHI_program/]
    
    WRITE_DISK --> SUBPROC[subprocess.run: Execute with 30s Timeout]
    SUBPROC --> RET_CHECK{Return Code == 0?}
    
    RET_CHECK -- Yes (Success) --> SUCCESS_OUT[Capture stdout & Return Execution Result]
    
    RET_CHECK -- No (Error) --> ATTEMPT_CHECK{Attempt Count < 3?}
    ATTEMPT_CHECK -- No (Max Retries) --> FAIL_OUT[Return Stderr Trace & Execution Failure]
    
    ATTEMPT_CHECK -- Yes --> CAPTURE_ERR[Capture Compiler Traceback / Stderr]
    CAPTURE_ERR --> REPROMPT[Build Repair Prompt: Original Task + Error Trace]
    REPROMPT --> GROQ_CALL
```

---

## 6. Cognitive Memory Extraction & Inactivity Mood Decay Flow

```mermaid
flowchart TD
    TURN_END[Completed Conversational Turn] --> SCRUB[MemoryManager: Regex Credential Filter]
    SCRUB --> CHECK_CREDS{Credentials Detected?}
    CHECK_CREDS -- Yes --> REDACT[Scrub Passwords, Tokens, API Keys]
    CHECK_CREDS -- No --> EXTRACT_FACTS[Extract Structured Facts: Education, Work, Family]
    REDACT --> EXTRACT_FACTS
    
    EXTRACT_FACTS --> COMMIT_SQLITE[Insert Records to SQLite database/astra.db]
    
    subgraph Emotion_Engine_Decay ["Affective Emotion Decay Flow"]
        STIMULUS[Detect Utterance Stimulus / Politeness] --> UPDATE_VECTOR[Update Valence, Arousal, Rapport]
        UPDATE_VECTOR --> LOG_EMOTION[Save State to emotional_state & emotion_logs]
        
        APP_IDLE[Application Idle or Restarted] --> CHECK_TIME{Elapsed Time >= 15 Minutes?}
        CHECK_TIME -- No --> KEEP_MOOD[Maintain Active Emotional State]
        CHECK_TIME -- Yes --> RESET_EQUILIBRIUM[Decay Negative Moods: Reset to Neutral Baseline]
    end
```