"""
DHEEPTHI-AI
DHEEPTHI Gemini Client

Features
--------
✓ Gemini Flash model
✓ Four API key support
✓ Automatic API key rotation
✓ Quota-aware fallback
✓ Invalid-key fallback
✓ Temporary server-error fallback
✓ Network-error fallback
✓ Groq cloud planner fallback
✓ Conversation memory
✓ Temporary in-memory conversation
✓ Context-aware replies
✓ Active topic continuity
✓ Previous entity / follow-up resolution
✓ New topic detection
✓ Tanglish-only conversational replies
✓ Current time / date / day awareness
✓ Thread safe
✓ Clean API-key logging
✓ Production-ready error handling

IMPORTANT
---------
Conversation history exists only in RAM.

It is NOT saved to SQLite or any permanent storage.

When the application closes:

    GeminiClient.close()
        ↓
    history.clear()
        ↓
    temporary conversation is erased.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Dict, List

from google import genai
from google.genai import types

from config import settings

try:
    from groq import Groq
except ImportError:
    Groq = None


# ==========================================================
# Gemini Live Conversation Session
# ==========================================================

class GeminiLiveSession:
    """
    Background-thread wrapper around the Gemini Live API.

    The Live API is intentionally isolated from the existing text Gemini
    methods.  Existing generate_response() and generate_response_stream()
    callers continue to work unchanged.

    Audio input expected by Live API
        Raw PCM, 16-bit, mono, 16 kHz.

    Audio output produced by Live API
        Raw PCM, 16-bit, mono, 24 kHz.

    Callbacks are optional and are invoked from the Live API worker thread:

        on_connected()
        on_audio(audio_bytes)
        on_input_transcript(text)
        on_output_transcript(text)
        on_interrupted()
        on_turn_complete(user_text, assistant_text)
        on_error(exception)
        on_closed()
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        system_instruction: str,
        on_connected=None,
        on_audio=None,
        on_input_transcript=None,
        on_output_transcript=None,
        on_interrupted=None,
        on_turn_complete=None,
        on_error=None,
        on_closed=None,
    ):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.system_instruction = str(system_instruction or "").strip()

        self.on_connected = on_connected
        self.on_audio = on_audio
        self.on_input_transcript = on_input_transcript
        self.on_output_transcript = on_output_transcript
        self.on_interrupted = on_interrupted
        self.on_turn_complete = on_turn_complete
        self.on_error = on_error
        self.on_closed = on_closed

        self._thread = None
        self._loop = None
        self._session = None
        self._audio_queue = None
        self._stop_event = None
        self._ready_event = threading.Event()
        self._closed_event = threading.Event()
        self._closing = threading.Event()
        self._started = False
        self._start_error = None

        self._current_user_transcript = ""
        self._current_output_transcript = ""
        self._transcript_lock = threading.RLock()

    # ------------------------------------------------------
    # Start
    # ------------------------------------------------------

    def start(self, timeout: float = 15.0) -> bool:
        if self._started:
            return self._start_error is None

        if not self.api_key:
            self._start_error = RuntimeError(
                "Gemini Live API key is not configured."
            )
            return False

        if not self.model:
            self._start_error = RuntimeError(
                "Gemini Live API model is not configured."
            )
            return False

        self._closing.clear()
        self._ready_event.clear()
        self._closed_event.clear()
        self._start_error = None

        self._thread = threading.Thread(
            target=self._thread_main,
            name="GeminiLiveSession",
            daemon=True,
        )
        self._started = True
        self._thread.start()

        if not self._ready_event.wait(timeout=max(0.1, float(timeout))):
            self._start_error = TimeoutError(
                "Timed out while connecting to Gemini Live API."
            )
            self.stop(timeout=3.0)
            return False

        return self._start_error is None

    # ------------------------------------------------------
    # Thread Main
    # ------------------------------------------------------

    def _thread_main(self):
        try:
            asyncio.run(self._run())
        except Exception as error:
            self._start_error = error
            self._safe_callback(self.on_error, error)
            self._ready_event.set()
        finally:
            self._closed_event.set()
            self._safe_callback(self.on_closed)

    # ------------------------------------------------------
    # Async Session
    # ------------------------------------------------------

    async def _run(self):
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self._audio_queue = asyncio.Queue(maxsize=64)

        config = {
            "response_modalities": ["AUDIO"],
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "system_instruction": self.system_instruction,
        }

        receive_task = None
        audio_task = None

        try:
            client = genai.Client(api_key=self.api_key)

            async with client.aio.live.connect(
                model=self.model,
                config=config,
            ) as session:
                self._session = session
                self._ready_event.set()
                self._safe_callback(self.on_connected)

                receive_task = asyncio.create_task(
                    self._receive_loop(session)
                )
                audio_task = asyncio.create_task(
                    self._audio_send_loop(session)
                )

                await self._stop_event.wait()

        except Exception as error:
            self._start_error = error
            self._safe_callback(self.on_error, error)
            self._ready_event.set()

        finally:
            for task in (receive_task, audio_task):
                if task is not None and not task.done():
                    task.cancel()

            for task in (receive_task, audio_task):
                if task is not None:
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

            self._session = None
            self._loop = None
            self._stop_event = None
            self._audio_queue = None

    # ------------------------------------------------------
    # Receive Loop
    # ------------------------------------------------------

    async def _receive_loop(self, session):
        try:
            async for response in session.receive():
                if self._closing.is_set():
                    break

                server_content = getattr(
                    response,
                    "server_content",
                    None,
                )

                if server_content is None:
                    continue

                input_transcription = getattr(
                    server_content,
                    "input_transcription",
                    None,
                )

                if input_transcription is not None:
                    text = str(
                        getattr(
                            input_transcription,
                            "text",
                            "",
                        )
                        or ""
                    ).strip()

                    if text:
                        with self._transcript_lock:
                            self._current_user_transcript = text

                        self._safe_callback(
                            self.on_input_transcript,
                            text,
                        )

                output_transcription = getattr(
                    server_content,
                    "output_transcription",
                    None,
                )

                if output_transcription is not None:
                    text = str(
                        getattr(
                            output_transcription,
                            "text",
                            "",
                        )
                        or ""
                    ).strip()

                    if text:
                        with self._transcript_lock:
                            self._current_output_transcript += text

                        self._safe_callback(
                            self.on_output_transcript,
                            text,
                        )

                interrupted = bool(
                    getattr(
                        server_content,
                        "interrupted",
                        False,
                    )
                )

                if interrupted:
                    self._safe_callback(
                        self.on_interrupted
                    )

                model_turn = getattr(
                    server_content,
                    "model_turn",
                    None,
                )

                if model_turn is not None:
                    parts = getattr(
                        model_turn,
                        "parts",
                        None,
                    ) or []

                    for part in parts:
                        inline_data = getattr(
                            part,
                            "inline_data",
                            None,
                        )

                        if inline_data is None:
                            continue

                        audio_data = getattr(
                            inline_data,
                            "data",
                            None,
                        )

                        if audio_data:
                            self._safe_callback(
                                self.on_audio,
                                bytes(audio_data),
                            )

                turn_complete = bool(
                    getattr(
                        server_content,
                        "turn_complete",
                        False,
                    )
                )

                if turn_complete:
                    with self._transcript_lock:
                        user_text = self._current_user_transcript.strip()
                        assistant_text = self._current_output_transcript.strip()
                        self._current_user_transcript = ""
                        self._current_output_transcript = ""

                    self._safe_callback(
                        self.on_turn_complete,
                        user_text,
                        assistant_text,
                    )

        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self._closing.is_set():
                self._safe_callback(
                    self.on_error,
                    error,
                )

    # ------------------------------------------------------
    # Audio Send Loop
    # ------------------------------------------------------

    async def _audio_send_loop(self, session):
        while not self._closing.is_set():
            audio_data = await self._audio_queue.get()

            if audio_data is None:
                return

            await session.send_realtime_input(
                audio=types.Blob(
                    data=audio_data,
                    mime_type="audio/pcm;rate=16000",
                )
            )

    # ------------------------------------------------------
    # Send Audio
    # ------------------------------------------------------

    def send_audio(self, audio_data: bytes) -> bool:
        if not audio_data or self._closing.is_set():
            return False

        loop = self._loop
        queue = self._audio_queue

        if loop is None or queue is None or loop.is_closed():
            return False

        data = bytes(audio_data)

        def enqueue():
            if self._closing.is_set():
                return

            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                # Drop the oldest queued chunk so microphone capture does not
                # block behind network backpressure.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass

        try:
            loop.call_soon_threadsafe(enqueue)
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------
    # Send Text
    # ------------------------------------------------------

    def send_text(self, text: str) -> bool:
        text = str(text or "").strip()

        if not text or self._closing.is_set():
            return False

        loop = self._loop
        session = self._session

        if loop is None or session is None or loop.is_closed():
            return False

        async def send():
            await session.send_realtime_input(
                text=text
            )

        try:
            asyncio.run_coroutine_threadsafe(
                send(),
                loop,
            )
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------
    # End Audio Stream
    # ------------------------------------------------------

    def end_audio_stream(self) -> bool:
        if self._closing.is_set():
            return False

        loop = self._loop
        session = self._session

        if loop is None or session is None or loop.is_closed():
            return False

        async def end_stream():
            await session.send_realtime_input(
                audio_stream_end=True
            )

        try:
            asyncio.run_coroutine_threadsafe(
                end_stream(),
                loop,
            )
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------
    # Stop
    # ------------------------------------------------------

    def stop(self, timeout: float = 5.0):
        self._closing.set()

        loop = self._loop
        stop_event = self._stop_event
        queue = self._audio_queue

        if loop is not None and not loop.is_closed():
            def request_stop():
                if queue is not None:
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        pass

                if stop_event is not None:
                    stop_event.set()

            try:
                loop.call_soon_threadsafe(request_stop)
            except RuntimeError:
                pass

        thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=max(0.1, float(timeout)))

        self._thread = None
        self._started = False

    # ------------------------------------------------------
    # Status
    # ------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return bool(
            self._thread is not None
            and self._thread.is_alive()
            and not self._closing.is_set()
        )

    @property
    def start_error(self):
        return self._start_error

    # ------------------------------------------------------
    # Callback Safety
    # ------------------------------------------------------

    @staticmethod
    def _safe_callback(callback, *args):
        if not callable(callback):
            return

        try:
            callback(*args)
        except Exception as error:
            print(
                "Gemini Live callback error:",
                error,
            )


# ==========================================================
# Gemini Client
# ==========================================================

class GeminiClient:
    """
    Central Gemini AI client used by DHEEPTHI.

    Responsibilities
    ----------------
    - Gemini API communication
    - Gemini API key rotation
    - Groq cloud fallback for structured planning
    - Temporary conversation memory
    - Context-aware conversation
    - Active topic continuity
    - Follow-up resolution
    - Tanglish-only conversational responses
    - Structured action-plan generation

    This class does NOT execute desktop commands.
    """

    # ------------------------------------------------------
    # Initialize
    # ------------------------------------------------------

    def __init__(self):

        # ------------------------------------------
        # Gemini API Keys
        # ------------------------------------------

        self.api_keys: List[str] = []

        for index in range(1, 5):

            key = getattr(
                settings,
                f"GEMINI_API_KEY_{index}",
                None
            )

            if key:

                key = str(key).strip()

                if key and key not in self.api_keys:

                    self.api_keys.append(key)

        if not self.api_keys:

            raise RuntimeError(
                "No Gemini API Keys configured."
            )

        # ------------------------------------------
        # Runtime
        # ------------------------------------------

        self.current_key_index = 0

        self.model = getattr(
            settings,
            "GEMINI_MODEL",
            "models/gemini-3.5-flash"
        )

        # ------------------------------------------
        # Gemini Live API
        # ------------------------------------------

        # The Live API model is configurable because availability can
        # differ by API account and Google can change preview model names.
        # The attached Google quickstart used gemini-3.1-flash-live-preview.
        self.live_model = (
            getattr(
                settings,
                "GEMINI_LIVE_MODEL",
                os.getenv(
                    "GEMINI_LIVE_MODEL",
                    "gemini-3.1-flash-live-preview"
                )
            )
            or "gemini-3.1-flash-live-preview"
        ).strip()

        self.live_session = None

        # ------------------------------------------
        # Groq Planner Fallback
        # ------------------------------------------
        #
        # IMPORTANT:
        # GROQ_API_KEY is NOT used here.
        #
        # GROQ_API_KEY is reserved for the existing
        # speech-to-text pipeline.
        #
        # This fallback exclusively uses:
        #
        #     GROQ_API_KEY_CODE_AGENT
        #
        # so the existing STT configuration remains
        # completely independent.
        # ------------------------------------------

        self.groq_planner_api_key = (
            os.getenv(
                "GROQ_API_KEY_CODE_AGENT",
                ""
            )
            .strip()
        )

        self.groq_planner_model = (
            os.getenv(
                "GROQ_CODE_AGENT_MODEL",
                "openai/gpt-oss-20b"
            )
            .strip()
        )

        self.groq_planner_client = None

        # ------------------------------------------
        # Temporary Conversation Memory
        # ------------------------------------------

        self.history: List[Dict[str, str]] = []

        self.max_history_messages = 40

        self.context_messages = 12

        # ------------------------------------------
        # Retry Configuration
        # ------------------------------------------

        self.retry_delay_seconds = 0.5

        # ------------------------------------------
        # Thread Lock
        # ------------------------------------------

        self.lock = threading.RLock()

        # ------------------------------------------
        # Gemini Client
        # ------------------------------------------

        self.client = None

        self._closing = False

        self._create_client()

        print(
            f"Gemini Client Ready | "
            f"Model : {self.model} | "
            f"Keys : {len(self.api_keys)}"
        )

        # ------------------------------------------
        # Groq Planner Status
        # ------------------------------------------

        if self.groq_planner_api_key:

            print(
                "Groq Planner Fallback : CONFIGURED"
            )

            print(
                f"Groq Planner Model : "
                f"{self.groq_planner_model}"
            )

        else:

            print(
                "Groq Planner Fallback : NOT CONFIGURED"
            )

    # ------------------------------------------------------
    # Create Gemini Client
    # ------------------------------------------------------

    def _create_client(self):
        """
        Create Gemini client using the currently
        selected API key.
        """

        if self._closing:
            return

        api_key = self.api_keys[
            self.current_key_index
        ]

        print(
            "\nCreating Gemini Client..."
        )

        print(
            f"Model : {self.model}"
        )

        print(
            f"API Key : "
            f"{self._masked_key(api_key)}"
        )

        self.client = genai.Client(
            api_key=api_key
        )

    # ------------------------------------------------------
    # Create Groq Planner Client
    # ------------------------------------------------------

    def _create_groq_planner_client(self):
        """
        Lazily create the dedicated Groq planner client.

        This client uses GROQ_API_KEY_CODE_AGENT only.

        The existing GROQ_API_KEY used by STT is never
        accessed by this method.
        """

        if self._closing:
            return None

        if not self.groq_planner_api_key:
            return None

        if Groq is None:
            print(
                "Groq Planner Fallback Error : "
                "groq package is not installed."
            )
            return None

        if self.groq_planner_client is not None:
            return self.groq_planner_client

        print(
            "\nCreating Groq Planner Fallback Client..."
        )

        print(
            f"Groq Planner Model : "
            f"{self.groq_planner_model}"
        )

        print(
            "Groq Planner API Key : CONFIGURED"
        )

        self.groq_planner_client = Groq(
            api_key=self.groq_planner_api_key
        )

        return self.groq_planner_client

    # ------------------------------------------------------
    # Mask API Key
    # ------------------------------------------------------

    @staticmethod
    def _masked_key(
        api_key: str
    ) -> str:
        """
        Safely display API key without exposing
        the actual secret.
        """

        if not api_key:
            return "Unavailable"

        if len(api_key) <= 8:
            return "********"

        return (
            api_key[:4]
            + "..."
            + api_key[-4:]
        )

    # ------------------------------------------------------
    # Rotate API Key
    # ------------------------------------------------------

    def rotate_api_key(self):
        """
        Switch to the next available Gemini API key.

        Returns
        -------
        bool
            True if another key is available.
        """

        with self.lock:

            if len(self.api_keys) <= 1:

                print(
                    "No alternate Gemini API key available."
                )

                return False

            old_index = self.current_key_index

            self.current_key_index = (
                self.current_key_index + 1
            ) % len(self.api_keys)

            if (
                self.current_key_index
                == old_index
            ):

                return False

            self._create_client()

            print(
                f"Switched to Gemini API Key "
                f"{self.current_key_index + 1}/"
                f"{len(self.api_keys)}"
            )

            return True

    # ------------------------------------------------------
    # System Prompt
    # ------------------------------------------------------

    def system_prompt(self):
        """
        DHEEPTHI identity, personality and
        conversation rules.
        """

        return """
You are DHEEPTHI.

Always follow the rules below.

==================================================
1. DHEEPTHI IDENTITY
==================================================

Your name is:

DHEEPTHI

Your role is:

your personal desktop assistant

IMPORTANT:

DHEEPTHI is the only assistant identity you should
use when introducing yourself.

If the user asks:

"What is your name?"

Answer exactly:

"I am DHEEPTHI, your personal desktop assistant."

If the user asks:

"What's your name?"

Answer exactly:

"I am DHEEPTHI, your personal desktop assistant."

If the user asks:

"Who are you?"

Answer naturally in Tanglish:

"Naan DHEEPTHI, your personal desktop assistant da."

If the user asks you to introduce yourself, answer
naturally while clearly identifying yourself as:

DHEEPTHI, your personal desktop assistant.

Never mention any version number as part of your name.

Never say:

• DHEEPTHI-A-I
• DHEEPTHI-AI Version-2.O
• DHEEPTHI-AI Version 2.0
• Version two point zero
• Version 2 point zero
• Version two zero
• Any other version number as part of your identity

Always maintain the identity:

DHEEPTHI

Never mention any application/company identity
unless the user explicitly asks about it.

==================================================
2. CREATOR IDENTITY
==================================================

DHEEPTHI was created by:

• Naresh
• Ragavendhiran

If the user asks who created you, answer naturally:

"Enna Naresh um Ragavendhiran um create pannanga da."

Do not invent or mention any other creator.

==================================================
3. TANGLISH-ONLY COMMUNICATION
==================================================

Always respond in natural conversational Tanglish.

Tanglish means Tamil written using English letters,
naturally mixed with commonly used English and
technical words.

Do not reply fully in English except when the user
explicitly requires an exact English response, such
as the exact DHEEPTHI identity sentence.

Do not reply using Tamil script.

Do not automatically switch to another language.

Even if the user asks the question fully in English,
reply in natural Tanglish unless an exact English
response is explicitly required by these rules.

Examples:

User:
"What is Python?"

Good:
"Python oru programming language da."

Bad:
"Python is a programming language."

Bad:
"பைதான் ஒரு நிரலாக்க மொழி."

For technical topics, use English technical terms
naturally where appropriate.

Keep the overall conversational response in Tanglish.

You may naturally use words such as:

• da
• nanba
• seri
• okay
• sure

when appropriate.

Do not overuse them in every sentence.

Do not sound robotic or overly formal.

==================================================
4. CONVERSATION CONTEXT AWARENESS
==================================================

You are having an ongoing conversation with the user.

Before answering every user message:

1. Read the recent conversation context.
2. Identify information relevant to the current message.
3. Use earlier messages when they help determine
   the user's intended meaning.

Do not behave as if every message is a completely
new and unrelated conversation.

The user does not need to repeat the full subject
in every message.

Use recent conversation history whenever it is
relevant to the current question.

Do not repeat questions or information unnecessarily
when the required information already exists in the
conversation history.

Conversation memory is temporary and exists only
during the current application session.

==================================================
5. ACTIVE TOPIC CONTINUITY
==================================================

Before answering, identify the current active topic
from the recent conversation.

Determine whether the current user message:

A. Continues the active topic.
B. Asks a follow-up question.
C. Refers to an entity mentioned earlier.
D. Clearly starts a new topic.

If the current message can reasonably be understood
as a continuation of the active topic, prefer the
context-aware interpretation instead of treating the
message as a completely standalone question.

Example:

Previous conversation:

User:
"Salem-la best MCA colleges enna?"

Current user message:

"Admission epdi?"

Interpret the meaning as:

"Previously discussed Salem MCA colleges-oda
admission process epdi?"

Do not automatically give generic MCA admission
information if the previous context clearly identifies
the subject.

==================================================
6. PREVIOUS ENTITY / FOLLOW-UP RESOLUTION
==================================================

Resolve incomplete questions and references using
recent conversation context whenever possible.

This includes words or phrases such as:

• that
• it
• this
• there
• he
• she
• previous one
• same one
• that college
• what I said
• what you said
• earlier
• before
• continue
• explain more
• tell me more
• why
• how
• when
• then
• admission
• fees
• eligibility
• apply

Examples:

Previous topic:
ABC College

User:
"Fees?"

Interpret as:

"ABC College fees?"

User:
"Eligibility?"

Interpret as:

"ABC College eligibility?"

User:
"Admission epdi?"

Interpret as:

"ABC College admission process epdi?"

User:
"Then?"

Interpret it using the immediately relevant
previous conversation.

User:
"Why?"

Use the previous answer or topic to understand
what the user is asking about.

Do not respond with:

"Enakku puriyala."

unless the recent conversation genuinely does not
contain enough information to resolve the meaning.

==================================================
7. NEW TOPIC DETECTION
==================================================

Do not force old conversation context into every
new user message.

If the user clearly introduces a new and unrelated
topic, treat it as a new topic.

Example:

Previous topic:
Salem MCA college admission.

New user message:
"Python-la class epdi create pannuvanga?"

This is a new topic.

Do not connect the Python question with the previous
college discussion.

Use previous context only when it is genuinely
relevant.

==================================================
8. THIRD-PARTY AI IDENTITY PROTECTION
==================================================

The user is interacting with DHEEPTHI.

Do not unnecessarily introduce yourself as or
mention underlying AI systems such as:

• Gemini
• Google AI
• ChatGPT
• OpenAI
• Claude
• Anthropic
• Grok
• Copilot
• any other third-party AI system

Never describe yourself as a Large Language Model
unless the user explicitly asks a question that
requires such a technical explanation.

Never unnecessarily reveal or redirect the user to
the underlying AI provider.

However, if the user explicitly asks about a specific
third-party AI, company, model, or technology,
answer the question normally and factually.

Do not falsely deny technical facts when directly
asked.

Maintain DHEEPTHI identity throughout the response.

==================================================
9. CURRENT TIME / DATE / DAY
==================================================

When the user asks about:

• current time
• current date
• today's date
• current day
• today
• yesterday
• tomorrow

Answer directly using reliable current date/time
information available to DHEEPTHI.

Never tell the user to check:

• system clock
• screen
• taskbar
• top corner
• bottom corner
• another application

If exact live time is available, provide the exact time.

If current date is requested, provide the current date.

If current day is requested, provide the correct day
of the week.

For relative date questions:

• today
• yesterday
• tomorrow

resolve them using the current date available
to DHEEPTHI.

Never invent an exact time or date.

If exact live time information is unavailable,
clearly say that the exact live time is not currently
available instead of guessing.

Always answer naturally in Tanglish.

==================================================
10. SIMPLE VS COMPLEX RESPONSE LENGTH
==================================================

Match the response length to the complexity of the
user's question.

Simple question:

Give a short, direct and complete answer.

Moderate question:

Give a clear answer with enough explanation.

Complex question:

Give a detailed but well-organized explanation.

For questions involving:

• why
• how
• explain
• compare
• teach
• difference
• examples

provide useful explanation and examples when needed.

Do not give unnecessarily huge answers to simple
questions.

Do not give vague, incomplete or one-line answers
to genuinely complex questions.

Answer the user's actual question first.

Avoid unnecessary introductions, repeated information
and filler.

==================================================
11. AMBIGUITY + TRUTH + NO FAKE ACTION RULES
==================================================

If the recent conversation does not provide enough
information to reliably understand the user's meaning,
ask one short and clear clarification question.

Do not invent missing context.

Do not pretend to remember information that was
never provided.

Never invent facts just to provide an answer.

Never claim that an action was completed unless the
backend actually confirms that the action was
successfully completed.

Do not falsely claim that:

• an application was opened
• an application was closed
• a file was created
• a file was deleted
• a command was executed
• a search was completed
• an email was sent
• automation was performed

unless the backend confirms successful completion.

Be honest about limitations and execution status.

==================================================
GENERAL RESPONSE BEHAVIOR
==================================================

Be:

• Friendly
• Natural
• Helpful
• Warm
• Clear
• Direct
• Professional when necessary

Never intentionally truncate a response.

Never stop a sentence halfway.

Do not give a one-word response unless the user's
question genuinely requires one.

For greetings, keep the response short and natural.

Always answer as DHEEPTHI.

Always communicate in natural Tanglish.

Always use relevant conversation context.

Always distinguish between:

• continuing the current topic
and
• starting a genuinely new topic.
"""

    # ------------------------------------------------------
    # Add User Message
    # ------------------------------------------------------

    def add_user_message(
        self,
        text: str
    ):

        text = str(
            text
        ).strip()

        if not text:
            return

        with self.lock:

            self.history.append(
                {
                    "role": "user",
                    "text": text
                }
            )

            self._trim_history()

    # ------------------------------------------------------
    # Add Assistant Message
    # ------------------------------------------------------

    def add_assistant_message(
        self,
        text: str
    ):

        text = str(
            text
        ).strip()

        if not text:
            return

        with self.lock:

            self.history.append(
                {
                    "role": "assistant",
                    "text": text
                }
            )

            self._trim_history()

    # ------------------------------------------------------
    # Trim History
    # ------------------------------------------------------

    def _trim_history(self):

        if len(
            self.history
        ) > self.max_history_messages:

            self.history = self.history[
                -self.max_history_messages:
            ]

    # ------------------------------------------------------
    # Build Conversation Context
    # ------------------------------------------------------

    def _build_conversation_context(
        self
    ) -> str:

        if not self.history:
            return ""

        recent_history = self.history[
            -self.context_messages:
        ]

        context_parts = []

        for message in recent_history:

            role = message.get(
                "role",
                ""
            )

            text = message.get(
                "text",
                ""
            ).strip()

            if not text:
                continue

            if role == "user":

                context_parts.append(
                    f"User: {text}"
                )

            elif role == "assistant":

                context_parts.append(
                    f"DHEEPTHI: {text}"
                )

        if not context_parts:
            return ""

        return "\n".join(
            context_parts
        )

    # ------------------------------------------------------
    # Build Conversation Prompt
    # ------------------------------------------------------

    def build_prompt(
        self,
        user_message: str
    ):

        user_message = str(
            user_message
        ).strip()

        prompt_parts = [
            self.system_prompt()
        ]

        historical_messages = self.history[:-1]

        recent_history = historical_messages[
            -self.context_messages:
        ]

        if recent_history:

            prompt_parts.append(
                "==================================================\n"
                "RECENT CONVERSATION\n"
                "=================================================="
            )

            for message in recent_history:

                role = message.get(
                    "role",
                    ""
                )

                text = message.get(
                    "text",
                    ""
                ).strip()

                if not text:
                    continue

                if role == "user":

                    prompt_parts.append(
                        f"User: {text}"
                    )

                elif role == "assistant":

                    prompt_parts.append(
                        f"DHEEPTHI: {text}"
                    )

        prompt_parts.append(
            "==================================================\n"
            "CURRENT USER MESSAGE\n"
            "=================================================="
        )

        prompt_parts.append(
            f"User: {user_message}"
        )

        prompt_parts.append(
            "DHEEPTHI:"
        )

        return "\n\n".join(
            prompt_parts
        )

    # ------------------------------------------------------
    # Build Simple Prompt
    # ------------------------------------------------------

    def build_simple_prompt(
        self,
        user_message: str
    ):

        user_message = str(
            user_message
        ).strip()

        prompt_parts = [
            self.system_prompt()
        ]

        historical_messages = self.history[:-1]

        recent_history = historical_messages[
            -self.context_messages:
        ]

        if recent_history:

            prompt_parts.append(
                "==================================================\n"
                "RECENT CONVERSATION\n"
                "=================================================="
            )

            for message in recent_history:

                role = message.get(
                    "role",
                    ""
                )

                text = message.get(
                    "text",
                    ""
                ).strip()

                if not text:
                    continue

                if role == "user":

                    prompt_parts.append(
                        f"User: {text}"
                    )

                elif role == "assistant":

                    prompt_parts.append(
                        f"DHEEPTHI: {text}"
                    )

        prompt_parts.append(
            "==================================================\n"
            "CURRENT USER MESSAGE\n"
            "=================================================="
        )

        prompt_parts.append(
            f"User: {user_message}"
        )

        prompt_parts.append(
            "DHEEPTHI:"
        )

        return "\n\n".join(
            prompt_parts
        )

    # ------------------------------------------------------
    # Is Retryable Error
    # ------------------------------------------------------

    @staticmethod
    def _is_retryable_error(
        error
    ):
        """
        Detect errors where another Gemini key/request
        attempt should be attempted.
        """

        error_text = str(
            error
        ).lower()

        retry_keywords = (
            "429",
            "quota",
            "resource_exhausted",
            "rate limit",
            "rate_limit",
            "too many requests",

            "401",
            "403",
            "unauthorized",
            "permission denied",
            "api key",
            "invalid api key",
            "expired api key",
            "authentication",

            "500",
            "502",
            "503",
            "504",
            "internal server error",
            "bad gateway",
            "gateway timeout",
            "service unavailable",
            "temporarily unavailable",
            "unavailable",
            "internal",

            "timeout",
            "timed out",
            "connection reset",
            "connection aborted",
            "connection error",
            "network error",
        )

        return any(
            keyword in error_text
            for keyword in retry_keywords
        )

    # ------------------------------------------------------
    # Retry Delay
    # ------------------------------------------------------

    def _retry_delay(self):

        if self.retry_delay_seconds <= 0:
            return

        time.sleep(
            self.retry_delay_seconds
        )

    # ------------------------------------------------------
    # Clean Response
    # ------------------------------------------------------

    @staticmethod
    def _clean_response(
        text: str
    ) -> str:

        if not text:
            return ""

        text = str(
            text
        ).strip()

        replacements = (
            ("DHEEPTHI:", ""),
            ("Assistant:", ""),
            ("AI:", ""),
        )

        for old, new in replacements:

            text = text.replace(
                old,
                new
            )

        text = (
            text
            .replace("**", "")
            .replace("__", "")
            .replace("`", "")
            .strip()
        )

        return text

    # ------------------------------------------------------
    # Generate Response
    # ------------------------------------------------------

    def generate_response(
        self,
        user_message: str
    ) -> str:

        if self._closing:

            return (
                "DHEEPTHI is shutting down."
            )

        user_message = str(
            user_message
        ).strip()

        if not user_message:

            return (
                "Please say something."
            )

        with self.lock:

            self.add_user_message(
                user_message
            )

            if len(
                user_message
            ) < 150:

                prompt = (
                    self.build_simple_prompt(
                        user_message
                    )
                )

            else:

                prompt = (
                    self.build_prompt(
                        user_message
                    )
                )

        with self.lock:

            total_keys = len(
                self.api_keys
            )

            attempted_keys = set()

            for _ in range(
                total_keys
            ):

                if self._closing:

                    return (
                        "DHEEPTHI is shutting down."
                    )

                current_index = (
                    self.current_key_index
                )

                if current_index in attempted_keys:
                    break

                attempted_keys.add(
                    current_index
                )

                try:

                    print(
                        f"Using Gemini Key "
                        f"{current_index + 1}/"
                        f"{total_keys}"
                    )

                    print(
                        f"Using Model : "
                        f"{self.model}"
                    )

                    response = (
                        self.client.models.generate_content(
                            model=self.model,
                            contents=prompt,
                            config=(
                                types.GenerateContentConfig(
                                    temperature=0.55,
                                    top_p=0.90,
                                    top_k=40,
                                    max_output_tokens=2048,
                                    candidate_count=1
                                )
                            )
                        )
                    )

                    text = ""

                    if response is not None:

                        if hasattr(
                            response,
                            "text"
                        ):

                            text = (
                                response.text
                                or ""
                            ).strip()

                    text = self._clean_response(
                        text
                    )

                    print(
                        "\n========== DHEEPTHI RESPONSE =========="
                    )

                    print(
                        text
                    )

                    print(
                        "Length :",
                        len(text)
                    )

                    print(
                        "Key Used :",
                        current_index + 1
                    )

                    print(
                        "=======================================\n"
                    )

                    if not text:

                        text = (
                            "Sorry da, response generate "
                            "panna mudila."
                        )

                    self.add_assistant_message(
                        text
                    )

                    return text

                except Exception as error:

                    print(
                        "\nGemini Error :",
                        error
                    )

                    if self._is_retryable_error(
                        error
                    ):

                        print(
                            "Retryable Gemini error detected."
                        )

                        print(
                            "Trying another Gemini API key..."
                        )

                        self._retry_delay()

                        if self.rotate_api_key():
                            continue

                    print(
                        "Gemini request failed."
                    )

                    return (
                        "Sorry da, ippo connection "
                        "problem irukku."
                    )

        return (
            "Sorry da, ippo ellaa AI API keys-um "
            "available illa."
        )

    # ------------------------------------------------------
    # Generate Streaming Response
    # ------------------------------------------------------

    def generate_response_stream(
        self,
        user_message: str,
        cancel_event=None,
    ):
        """Yield a Gemini response as text arrives.

        This deliberately leaves ``generate_response()`` unchanged for
        existing callers.  A streamed turn is committed to conversation
        history only after its source stream finishes normally; cancelled,
        empty, and failed turns leave history untouched.
        """

        if self._closing:
            return

        user_message = str(
            user_message
        ).strip()

        if not user_message:
            return

        def is_cancelled():
            return (
                self._closing
                or (
                    cancel_event is not None
                    and cancel_event.is_set()
                )
            )

        if is_cancelled():
            return

        # The existing prompt builders expect the current user message to
        # be the final item in history. Build that exact prompt without
        # persisting a half-finished conversation turn.
        with self.lock:

            original_history = self.history

            try:

                temporary_history = list(
                    original_history
                )

                temporary_history.append(
                    {
                        "role": "user",
                        "text": user_message,
                    }
                )

                if len(temporary_history) > self.max_history_messages:

                    temporary_history = temporary_history[
                        -self.max_history_messages:
                    ]

                self.history = temporary_history

                if len(user_message) < 150:

                    prompt = self.build_simple_prompt(
                        user_message
                    )

                else:

                    prompt = self.build_prompt(
                        user_message
                    )

            finally:

                self.history = original_history

        with self.lock:

            total_keys = len(
                self.api_keys
            )

            attempted_keys = set()

            for _ in range(total_keys):

                if is_cancelled():
                    return

                current_index = self.current_key_index

                if current_index in attempted_keys:
                    break

                attempted_keys.add(current_index)

                yielded_text = False
                collected_chunks = []
                stream = None

                try:

                    print(
                        f"Using Gemini Key "
                        f"{current_index + 1}/"
                        f"{total_keys} for streaming"
                    )

                    stream = self.client.models.generate_content_stream(
                        model=self.model,
                        contents=prompt,
                        config=(
                            types.GenerateContentConfig(
                                temperature=0.55,
                                top_p=0.90,
                                top_k=40,
                                max_output_tokens=2048,
                                candidate_count=1,
                            )
                        ),
                    )

                    for chunk in stream:

                        if is_cancelled():
                            return

                        text = getattr(
                            chunk,
                            "text",
                            "",
                        )

                        if text is None:
                            continue

                        text = str(text)

                        if not text.strip():
                            continue

                        yielded_text = True
                        collected_chunks.append(text)

                        yield text

                    if is_cancelled():
                        return

                    response_text = self._clean_response(
                        "".join(collected_chunks)
                    )

                    if not response_text:

                        print(
                            "Gemini streaming request returned "
                            "no usable text."
                        )

                        return

                    with self.lock:

                        if is_cancelled():
                            return

                        self.add_user_message(user_message)
                        self.add_assistant_message(response_text)

                    return

                except Exception as error:

                    print(
                        "\nGemini Streaming Error:",
                        error,
                    )

                    # Retrying after visible content would duplicate or
                    # contradict what the caller has already received.
                    if yielded_text or is_cancelled():
                        return

                    if self._is_retryable_error(error):

                        print(
                            "Retryable Gemini streaming error detected."
                        )

                        self._retry_delay()

                        if is_cancelled():
                            return

                        if self.rotate_api_key():
                            continue

                    return

                finally:

                    if stream is not None and is_cancelled():

                        close_stream = getattr(
                            stream,
                            "close",
                            None,
                        )

                        if callable(close_stream):

                            try:
                                close_stream()
                            except Exception:
                                pass

    # ------------------------------------------------------
    # Normalize Structured Planner Response
    # ------------------------------------------------------

    @staticmethod
    def _normalize_structured_plan_response(
        text: str
    ) -> str:
        """
        Normalize a cloud planner response into the raw
        JSON string expected by MultiCommandPlanner.

        This deliberately does not parse/rewrite the JSON.
        It only removes accidental Markdown code fences.
        """

        if not text:
            return ""

        text = str(
            text
        ).strip()

        if text.startswith("```"):

            lines = text.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(
                lines
            ).strip()

        if (
            text.startswith("json\n")
            or text.startswith("JSON\n")
        ):

            text = text.split(
                "\n",
                1
            )[1].strip()

        return text

    # ------------------------------------------------------
    # Generate Groq Structured Action Plan
    # ------------------------------------------------------

    def _generate_groq_structured_plan(
        self,
        prompt: str
    ) -> str:
        """
        Generate the same machine-readable action plan
        using the dedicated Groq Code Agent API key.

        IMPORTANT:
        This method is a planner fallback only.

        It does NOT execute commands and does NOT replace
        the existing CodeAgent execution workflow.
        """

        if self._closing:
            return ""

        client = (
            self._create_groq_planner_client()
        )

        if client is None:

            print(
                "Groq Planner Fallback : "
                "Unavailable."
            )

            return ""

        try:

            print(
                "\n========== GROQ PLANNER FALLBACK =========="
            )

            print(
                "Provider : Groq"
            )

            print(
                f"Model : {self.groq_planner_model}"
            )

            print(
                "API Key : GROQ_API_KEY_CODE_AGENT"
            )

            response = (
                client.chat.completions.create(
                    model=self.groq_planner_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are DHEEPTHI's desktop "
                                "action planner.\n\n"
                                "Return ONLY valid JSON.\n"
                                "Do not use Markdown.\n"
                                "Do not add explanations.\n"
                                "Follow the exact action-plan "
                                "schema contained in the user prompt.\n"
                                "Do not execute actions.\n"
                                "Do not invent unsupported actions."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=0.10,
                    max_tokens=4096,
                    response_format={
                        "type": "json_object"
                    },
                )
            )

            text = ""

            if response is not None:

                choices = getattr(
                    response,
                    "choices",
                    None
                )

                if choices:

                    message = getattr(
                        choices[0],
                        "message",
                        None
                    )

                    if message is not None:

                        text = (
                            getattr(
                                message,
                                "content",
                                ""
                            )
                            or ""
                        ).strip()

            text = (
                self._normalize_structured_plan_response(
                    text
                )
            )

            if not text:

                print(
                    "Groq Planner Fallback : "
                    "Empty response."
                )

                return ""

            print(
                "\n========== GROQ ACTION PLAN =========="
            )

            print(
                text
            )

            print(
                "Length :",
                len(text)
            )

            print(
                "Provider : Groq"
            )

            print(
                "=======================================\n"
            )

            return text

        except Exception as error:

            print(
                "\nGroq Planner Fallback Error :",
                error
            )

            print(
                "Groq planner fallback failed."
            )

            return ""

    # ------------------------------------------------------
    # Generate Structured Action Plan
    # ------------------------------------------------------

    def generate_structured_plan(
        self,
        prompt: str
    ) -> str:
        """
        Generate a structured JSON action plan.

        Primary provider:
            Gemini using configured API keys.

        Secondary provider:
            Groq using GROQ_API_KEY_CODE_AGENT.

        Fallback order:
            Gemini Key 1
                ↓
            Gemini Key 2
                ↓
            Gemini Key 3
                ↓
            Gemini Key 4
                ↓
            Groq planner fallback
                ↓
            empty string if all providers fail

        The existing Gemini key rotation is preserved.
        The existing GROQ_API_KEY used by STT is never used.
        """

        if self._closing:
            return ""

        prompt = str(
            prompt
        ).strip()

        if not prompt:
            return ""

        # ------------------------------------------
        # Gemini Attempts
        # ------------------------------------------

        with self.lock:

            total_keys = len(
                self.api_keys
            )

            attempted_keys = set()

            for _ in range(
                total_keys
            ):

                if self._closing:
                    return ""

                current_index = (
                    self.current_key_index
                )

                if current_index in attempted_keys:
                    break

                attempted_keys.add(
                    current_index
                )

                try:

                    print(
                        f"Using Gemini Planner Key "
                        f"{current_index + 1}/"
                        f"{total_keys}"
                    )

                    print(
                        f"Using Model : "
                        f"{self.model}"
                    )

                    response = (
                        self.client.models.generate_content(
                            model=self.model,
                            contents=prompt,
                            config=(
                                types.GenerateContentConfig(
                                    temperature=0.10,
                                    top_p=0.90,
                                    top_k=20,
                                    max_output_tokens=4096,
                                    candidate_count=1,
                                    response_mime_type=(
                                        "application/json"
                                    )
                                )
                            )
                        )
                    )

                    text = ""

                    if response is not None:

                        if hasattr(
                            response,
                            "text"
                        ):

                            text = (
                                response.text
                                or ""
                            ).strip()

                    if not text:

                        raise RuntimeError(
                            "Gemini returned an empty "
                            "structured-plan response."
                        )

                    print(
                        "\n========== GEMINI ACTION PLAN =========="
                    )

                    print(
                        text
                    )

                    print(
                        "Length :",
                        len(text)
                    )

                    print(
                        "Key Used :",
                        current_index + 1
                    )

                    print(
                        "Provider : Gemini"
                    )

                    print(
                        "========================================\n"
                    )

                    return text

                except Exception as error:

                    print(
                        "\nGemini Planner Error :",
                        error
                    )

                    if self._is_retryable_error(
                        error
                    ):

                        print(
                            "Retryable Gemini planner "
                            "error detected."
                        )

                        print(
                            "Trying another Gemini API key..."
                        )

                        self._retry_delay()

                        if self.rotate_api_key():
                            continue

                    else:

                        print(
                            "Non-retryable Gemini planner "
                            "error detected."
                        )

                        break

            # --------------------------------------
            # All Gemini keys exhausted
            # --------------------------------------

            print(
                "\n=================================================="
            )

            print(
                "All Gemini planner attempts failed."
            )

            print(
                "Activating Groq planner fallback..."
            )

            print(
                "=================================================="
            )

            if self._closing:
                return ""

            # --------------------------------------
            # Groq fallback
            # --------------------------------------
            #
            # Keep the Groq network request inside the
            # existing lock so only one planner request
            # manipulates provider state at a time.
            # --------------------------------------

            groq_result = (
                self._generate_groq_structured_plan(
                    prompt
                )
            )

            if groq_result:

                print(
                    "Planner Provider : Groq Fallback"
                )

                return groq_result

        print(
            "All Gemini and Groq planner providers failed."
        )

        return ""

    # ------------------------------------------------------
    # Gemini Live API Session
    # ------------------------------------------------------

    def create_live_session(
        self,
        on_connected=None,
        on_audio=None,
        on_input_transcript=None,
        on_output_transcript=None,
        on_interrupted=None,
        on_turn_complete=None,
        on_error=None,
        on_closed=None,
        auto_start=True,
    ):
        """
        Create the low-latency Gemini Live conversation session.

        The Live API owns the conversation audio path.  Existing text
        Gemini methods are untouched and remain available for commands,
        planner work, and non-live conversation callers.

        Returns
        -------
        GeminiLiveSession | None
            A running session when ``auto_start`` is True and connection
            succeeds; otherwise the created session object or None when
            DHEEPTHI is shutting down.
        """

        if self._closing:
            return None

        # Stop an older live conversation before replacing it.  Do this
        # outside the client lock so a callback from the old session cannot
        # wait on the same lock while the session is shutting down.
        self.close_live_session()

        with self.lock:

            if self._closing:
                return None

            session = GeminiLiveSession(
                api_key=self.current_api_key(),
                model=self.live_model,
                system_instruction=self.system_prompt(),
                on_connected=on_connected,
                on_audio=on_audio,
                on_input_transcript=on_input_transcript,
                on_output_transcript=on_output_transcript,
                on_interrupted=on_interrupted,
                on_turn_complete=on_turn_complete,
                on_error=on_error,
                on_closed=on_closed,
            )

            self.live_session = session

        if auto_start:
            if not session.start():
                print(
                    "Gemini Live session failed to start:",
                    session.start_error,
                )
                self.close_live_session()
                return None

        return session

    # ------------------------------------------------------
    # Close Live Session
    # ------------------------------------------------------

    def close_live_session(self):
        with self.lock:
            session = self.live_session
            self.live_session = None

        if session is not None:
            try:
                session.stop()
            except Exception as error:
                print(
                    "Gemini Live session shutdown error:",
                    error,
                )

    # ------------------------------------------------------
    # Current API Key
    # ------------------------------------------------------

    def current_api_key(self):

        return self.api_keys[
            self.current_key_index
        ]

    # ------------------------------------------------------
    # Current API Key Number
    # ------------------------------------------------------

    def current_api_key_number(self):

        return (
            self.current_key_index + 1
        )

    # ------------------------------------------------------
    # Total API Keys
    # ------------------------------------------------------

    def total_api_keys(self):

        return len(
            self.api_keys
        )

    # ------------------------------------------------------
    # Conversation History
    # ------------------------------------------------------

    def get_history(self):

        with self.lock:

            return [
                message.copy()
                for message in self.history
            ]

    # ------------------------------------------------------
    # History Count
    # ------------------------------------------------------

    def history_count(self):

        with self.lock:

            return len(
                self.history
            )

    # ------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------

    def close(self):
        """
        Cleanup Gemini/Groq resources.

        Conversation history is intentionally cleared here.
        """

        with self.lock:

            self._closing = True

            live_session = self.live_session
            self.live_session = None

            self.history.clear()

            self.client = None

            self.groq_planner_client = None

        if live_session is not None:
            try:
                live_session.stop()
            except Exception as error:
                print(
                    "Gemini Live session shutdown error:",
                    error,
                )

        print(
            "Gemini Client shutdown completed."
        )
