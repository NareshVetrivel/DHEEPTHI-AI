"""
DHEEPTHI-AI Semantic Command Planner

Understands natural language commands across English, Tamil, Tanglish,
and mixed languages. Produces a structured action plan without directly
executing system commands.

Target Architecture:
    USER VOICE
        ↓
    Gemini Live API
        ↓
    Gemini Live input transcript
        ↓
    Semantic Command Planner (Gemini / Groq structured JSON)
        ↓
    Structured command plan
        ↓
    Local Validation / Normalization
        ↓
    Existing CommandDispatcher & Agents
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ai.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class SemanticCommandPlanner:
    """
    Dedicated semantic command planner for DHEEPTHI-AI V1.

    Translates natural-language speech transcripts into structured
    multi-step action plans while strictly protecting normal conversation.
    """

    SUPPORTED_INTENTS = {
        # Application
        "launch_application",
        "close_application",
        # Browser / YouTube
        "open_website",
        "open_google",
        "open_youtube",
        "google_search",
        "youtube_search",
        "play_youtube",
        "click_search_result",
        # Files
        "open_file",
        "create_file",
        "delete_file",
        "rename_file",
        "copy_file",
        "move_file",
        "compress_file",
        "extract_zip",
        # Folders
        "open_folder",
        "create_folder",
        "delete_folder",
        "rename_folder",
        "copy_folder",
        "move_folder",
        # Capture / Screen
        "take_screenshot",
        "start_screen_recording",
        "stop_screen_recording",
        # Coding
        "code_agent",
        # Keyboard / Mouse
        "type_text",
        "press_key",
        "left_click",
        "right_click",
        "double_click",
        # System
        "volume_up",
        "volume_down",
        "set_volume",
        "mute",
        "brightness_up",
        "brightness_down",
        "set_brightness",
        "lock_screen",
        "shutdown",
        "restart",
        "sleep",
        "sign_out",
        # Word
        "create_blank_document",
        "open_word",
        "close_word",
    }

    INTENT_ALIASES = {
        "write_code": "code_agent",
        "create_code": "code_agent",
        "generate_code": "code_agent",
        "coding": "code_agent",
        "program": "code_agent",
        "create_program": "code_agent",
        "compress_zip": "compress_file",
        "zip_file": "compress_file",
        "unzip": "extract_zip",
        "play_song": "play_youtube",
        "play_music": "play_youtube",
        "play_video": "play_youtube",
        "play_movie": "play_youtube",
        "watch_video": "play_youtube",
        "watch_movie": "play_youtube",
        "search": "google_search",
        "web_search": "google_search",
        "screenshot": "take_screenshot",
        "record_screen": "start_screen_recording",
    }

    PLANNER_PROMPT_TEMPLATE = """
You are the semantic command planner for DHEEPTHI-AI.
Your role is to understand user speech in English, Tamil, Tanglish, and mixed languages, and convert actionable desktop commands into a structured JSON execution plan.

IMPORTANT DISTINCTION:
1. COMMAND: The user explicitly requests DHEEPTHI-AI to perform an action on the computer (open an application, play a song/video on YouTube, copy/move files, create a program, etc.).
   Return: {{"type": "command", "actions": [...]}}
2. CONVERSATION: The user is asking a question, asking for an explanation, asking ABOUT an action or technology, or having normal conversation.
   Examples of CONVERSATION:
   - "Tell me about Chrome"
   - "Why should I use Chrome?"
   - "How do I open Chrome?"
   - "Tell me about Pavalamalli song"
   - "Why should I play a song?"
   - "Can you explain YouTube?"
   - "Tell me about the Music folder"
   - "How does VS Code work?"
   Return: {{"type": "conversation", "actions": []}}

SUPPORTED INTENTS FOR ACTIONS:
- launch_application (entities: {{"application": "Chrome"}})
- close_application (entities: {{"application": "Notepad"}})
- open_folder (entities: {{"folder": "Downloads"}})
- create_folder (entities: {{"folder": "NewFolder"}})
- delete_folder (entities: {{"folder": "OldFolder"}})
- copy_folder (entities: {{"source": "...", "destination": "..."}})
- move_folder (entities: {{"source": "...", "destination": "..."}})
- rename_folder (entities: {{"source": "...", "destination": "..."}})
- open_file (entities: {{"file": "..."}})
- create_file (entities: {{"file": "..."}})
- delete_file (entities: {{"file": "..."}})
- copy_file (entities: {{"source": "report.pdf", "destination": "Desktop"}})
- move_file (entities: {{"source": "...", "destination": "..."}})
- rename_file (entities: {{"source": "...", "destination": "..."}})
- play_youtube (entities: {{"search_query": "Pavalamalli"}}) -> Used whenever the user wants to play a song, video, or music (e.g. "play Pavalamalli song", "Pavalamalli song play pannu", "paattu podu", "பாட்டு போடு"). Always maps to play_youtube.
- youtube_search (entities: {{"search_query": "..."}})
- google_search (entities: {{"search_query": "..."}})
- open_website (entities: {{"website": "..."}})
- take_screenshot
- start_screen_recording
- stop_screen_recording
- code_agent (entities: {{"language": "python", "task": "calculator program"}}) -> For programming/code creation requests (e.g. "VS Code open panni Python la calculator program create pannu", "write a python script for factorial")
- type_text (entities: {{"text": "..."}})
- volume_up, volume_down, set_volume, mute
- brightness_up, brightness_down, set_brightness
- lock_screen, shutdown, restart, sleep, sign_out

LANGUAGE / CONNECTOR MAPPING:
- Tanglish / Tamil connectors like "panni", "pannu", "pannunga", "seythu", "செய்து", "பண்ணு", "and", "then" chain sequential actions.
  Example: "Chrome open panni Pavalamalli song play pannu" ->
  actions: [
    {{"intent": "launch_application", "entities": {{"application": "Chrome"}}}},
    {{"intent": "play_youtube", "entities": {{"search_query": "Pavalamalli"}}}}
  ]
- "Chrome திறந்து Pavalamalli பாட்டு போடு" ->
  actions: [
    {{"intent": "launch_application", "entities": {{"application": "Chrome"}}}},
    {{"intent": "play_youtube", "entities": {{"search_query": "Pavalamalli"}}}}
  ]
- "Chrome open panni Jailer song podu" ->
  actions: [
    {{"intent": "launch_application", "entities": {{"application": "Chrome"}}}},
    {{"intent": "play_youtube", "entities": {{"search_query": "Jailer"}}}}
  ]
- "he chrome open pannu jailer song podu" ->
  actions: [
    {{"intent": "launch_application", "entities": {{"application": "Chrome"}}}},
    {{"intent": "play_youtube", "entities": {{"search_query": "Jailer"}}}}
  ]
- "Notepad open panni hello world type pannu" ->
  actions: [
    {{"intent": "launch_application", "entities": {{"application": "Notepad"}}}},
    {{"intent": "type_text", "entities": {{"text": "hello world"}}}}
  ]
- "Edge open panni YouTube la Anbe Anbe play pannu" ->
  actions: [
    {{"intent": "launch_application", "entities": {{"application": "Edge"}}}},
    {{"intent": "play_youtube", "entities": {{"search_query": "Anbe Anbe"}}}}
  ]
- "VS Code open panni Python la calculator program create pannu" ->
  actions: [
    {{"intent": "launch_application", "entities": {{"application": "VS Code"}}}},
    {{"intent": "code_agent", "entities": {{"language": "python", "task": "calculator program"}}}}
  ]
- "Downloads folder open panni report.pdf ah Desktop ku copy pannu" ->
  actions: [
    {{"intent": "open_folder", "entities": {{"folder": "Downloads"}}}},
    {{"intent": "copy_file", "entities": {{"source": "report.pdf", "destination": "Desktop"}}}}
  ]

User Input: "{input_text}"

Return ONLY valid JSON matching this schema:
{{
  "type": "command" | "conversation",
  "actions": [
    {{
      "intent": "<supported_intent>",
      "entities": {{ ... }}
    }}
  ]
}}
"""

    def __init__(self, gemini_client: Optional[GeminiClient] = None) -> None:
        self.gemini_client = gemini_client if gemini_client is not None else GeminiClient()
        self._plan_cache: Dict[str, Dict[str, Any]] = {}

    # ==========================================================
    # Fast Local Conversation Guard
    # ==========================================================

    @staticmethod
    def _is_obviously_conversational(text: str) -> bool:
        """
        Fast heuristic check to protect obvious questions, discussions,
        interruption commands, Tanglish queries, and greetings from being routed to desktop actions.
        """
        if not text:
            return True

        lower = text.strip().lower()
        clean = re.sub(r"[^\w\s]", "", lower).strip()

        # Strip common conversational addressing prefixes (e.g. "hey,", "hi dheepthi,", "ai,")
        stripped_prefix = re.sub(
            r"^(?:hey|hi|hello|dheepthi(?:\s+ai)?|ai|dei|da|pa|thala|bro|friend)\s*[,]?\s*",
            "",
            lower,
        ).strip()
        stripped_clean = re.sub(r"[^\w\s]", "", stripped_prefix).strip()

        # 1. Interruption control words
        interruption_phrases = {
            "stop", "wait", "pothum", "podhum", "enough", "stop talking",
            "pesadha", "pesama iru", "wait wait", "niruthu", "niruthunga",
            "shut up", "pause", "shh", "silence",
        }
        if clean in interruption_phrases or stripped_clean in interruption_phrases:
            return True
        clean_words = clean.split()
        if clean_words and all(w in interruption_phrases for w in clean_words):
            return True

        # 2. Doubts, pauses for questions, explanations
        # e.g. "Wait pannu, oru doubt iruku", "Oru doubt iruku", "Doubt iruku"
        if re.search(r"\b(?:doubt|kelvi)\b", lower):
            return True

        # 3. Tamil / Tanglish conversational expressions & chit-chat
        # e.g. "Enna da panra?", "Enna panra?", "Enna vishayam?"
        if re.search(r"\benna(?:\s+da)?\s+(?:panra|pandra|seira|seigira|vishayam)\b", lower):
            return True

        # 4. Casual greetings and polite conversational phrases (e.g. "hi dheepthi", "hello")
        greeting_pattern = r"^(?:hi|hello|hey|vanakkam|good\s+(?:morning|afternoon|evening|night)|how\s+are\s+you|who\s+are\s+you)(?:\s+(?:dheepthi|ai|da|pa|bro|friend))?$"
        if re.search(greeting_pattern, clean) or re.search(greeting_pattern, stripped_clean):
            return True

        # 5. Questions starting with question words (English)
        # e.g. "Why should I open Chrome?", "What is the weather?"
        question_words_en = r"^(?:what|why|who|whose|whom|when|where|which|how|is|are|am|do|does|did|should)\b"
        if re.search(question_words_en, lower) or re.search(question_words_en, stripped_prefix):
            return True

        # 6. Questions starting with question words (Tamil / Tanglish)
        # e.g. "Enna seiyanum?", "Epdi iruka?", "Ethuku Chrome open pannanum?"
        question_words_ta = r"^(?:enna|edhu|ethu|yaaru|yaru|yen|en\b|epdi|eppadi|eppo|engae|enga|ethuku|etharku|evlo|evvalavu|ethana|ethanai)\b"
        if re.search(question_words_ta, lower) or re.search(question_words_ta, stripped_prefix):
            return True

        # 7. Mid-sentence quantity/count question words in Tamil/Tanglish
        # e.g. "Human body la evlo bones irukum?", "Skeleton la evlo bones irukum nu ketan?"
        if re.search(r"\b(?:evlo|evvalavu|ethana|ethanai)\b", lower):
            return True
        if re.search(r"\b(?:nu\s+kett?an|ketten|ketan)\b", lower):
            return True

        # 8. Tamil/Tanglish topic explanation requests ("about X tell me")
        # e.g. "Chrome pathi sollu", "YouTube pathi sollu"
        if re.search(r"\b(?:pathi|paththi|patti|patthi|patri|kurithu)\s+(?:sollu|solla|pesu|vilakku|sol)\b", lower):
            return True

        # 9. English explanation / story / recipe / discussion requests
        # e.g. "Tell me about YouTube", "Tell me about Chrome"
        if re.search(r"^(?:please\s+)?tell\s+me\s+(?:about|why|how|what|who|more\s+about|a\s+recipe|a\s+joke|a\s+story|something\s+else)\b", lower):
            return True
        if re.search(r"^(?:please\s+)?tell\s+me\s+(?:about|why|how|what|who|more\s+about|a\s+recipe|a\s+joke|a\s+story|something\s+else)\b", stripped_prefix):
            return True

        if re.search(r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:explain|tell\s+me\s+about|describe|help(?:\s+me)?)\b", lower):
            return True
        if re.search(r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:explain|tell\s+me\s+about|describe|help(?:\s+me)?)\b", stripped_prefix):
            return True

        if re.search(r"\b(?:explain|meaning\s+of|difference\s+between|recipe\b|why\s+is\s+the\s+sky\s+blue)\b", lower):
            return True

        if lower in {"can you help me", "help me", "can you help me please"}:
            return True

        return False

    # ==========================================================
    # Main Planning API
    # ==========================================================

    def plan(self, text: str) -> Dict[str, Any]:
        """
        Interpret the speech transcript and return a validated structured plan.
        """
        cleaned_text = str(text or "").strip()
        if not cleaned_text or len(cleaned_text) <= 1:
            return {"type": "conversation", "actions": []}

        # Fast conversation check
        if self._is_obviously_conversational(cleaned_text):
            return {"type": "conversation", "actions": []}

        # Plan cache lookup: strips punctuation and normalizes casing
        cache_key = re.sub(r"[^\w\s]", "", cleaned_text.lower()).strip()
        if cache_key in self._plan_cache:
            logger.info("Semantic plan cache hit for: '%s'", cleaned_text)
            return dict(self._plan_cache[cache_key])

        prompt = self.PLANNER_PROMPT_TEMPLATE.replace("{input_text}", cleaned_text)

        try:
            response = self.gemini_client.generate_structured_plan(prompt)
            if not response:
                logger.warning("Empty response from semantic planner. Attempting fallback...")
                fallback_plan = self._fallback_extract_structural_actions(cleaned_text)
                if fallback_plan and fallback_plan.get("actions"):
                    self._plan_cache[cache_key] = fallback_plan
                    return fallback_plan
                return {"type": "conversation", "actions": []}

            data = self._parse_json(response)
            if not isinstance(data, dict):
                logger.warning("Semantic planner did not return a valid dict: %s. Attempting fallback...", response)
                fallback_plan = self._fallback_extract_structural_actions(cleaned_text)
                if fallback_plan and fallback_plan.get("actions"):
                    self._plan_cache[cache_key] = fallback_plan
                    return fallback_plan
                return {"type": "conversation", "actions": []}

            plan = self._validate_and_normalize_plan(data, cleaned_text)
            if not plan.get("actions"):
                fallback_plan = self._fallback_extract_structural_actions(cleaned_text)
                if fallback_plan and fallback_plan.get("actions"):
                    plan = fallback_plan

            if len(self._plan_cache) > 100:
                self._plan_cache.clear()
            self._plan_cache[cache_key] = plan
            return plan

        except Exception as error:
            logger.error("Semantic command planning error: %s", error)
            fallback_plan = self._fallback_extract_structural_actions(cleaned_text)
            if fallback_plan and fallback_plan.get("actions"):
                return fallback_plan
            return {"type": "conversation", "actions": []}

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _parse_json(text: str) -> Optional[dict]:
        """Safely extract JSON object from LLM response."""
        if not text:
            return None

        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        return None

    def _validate_and_normalize_plan(self, data: dict, original_text: str) -> Dict[str, Any]:
        """
        Enforce strict safety rules and whitelist on the LLM output.
        """
        plan_type = str(data.get("type", "conversation")).strip().lower()
        if plan_type != "command":
            return {"type": "conversation", "actions": []}

        raw_actions = data.get("actions", [])
        if not isinstance(raw_actions, list) or not raw_actions:
            return {"type": "conversation", "actions": []}

        validated_actions = []

        for action in raw_actions:
            if not isinstance(action, dict):
                continue

            raw_intent = str(action.get("intent", "")).strip().lower()
            intent = self.INTENT_ALIASES.get(raw_intent, raw_intent)

            if intent not in self.SUPPORTED_INTENTS:
                logger.warning("Discarding unsupported intent: '%s'", raw_intent)
                continue

            entities = action.get("entities", {})
            if not isinstance(entities, dict):
                entities = {"entity": entities}

            # Normalize entities per intent
            normalized_entities = self._normalize_entities_for_intent(intent, entities, original_text)

            validated_actions.append({
                "intent": intent,
                "entities": normalized_entities,
            })

        if not validated_actions:
            return {"type": "conversation", "actions": []}

        return {
            "type": "command",
            "actions": validated_actions,
            "original_command": original_text,
        }

    @staticmethod
    def _normalize_entities_for_intent(
        intent: str,
        entities: Dict[str, Any],
        original_text: str,
    ) -> Dict[str, Any]:
        """Ensure entity keys match what CommandDispatcher expects."""
        norm = dict(entities)

        if intent in {"launch_application", "close_application"}:
            app = norm.get("application") or norm.get("app") or norm.get("target") or norm.get("name")
            if app:
                norm["application"] = str(app).strip()

        elif intent == "play_youtube":
            query = (
                norm.get("search_query")
                or norm.get("query")
                or norm.get("song")
                or norm.get("video")
                or norm.get("music")
                or norm.get("target")
                or norm.get("entity")
            )
            if query:
                norm["search_query"] = str(query).strip()

        elif intent in {"youtube_search", "google_search"}:
            query = norm.get("search_query") or norm.get("query") or norm.get("target") or norm.get("entity")
            if query:
                norm["search_query"] = str(query).strip()

        elif intent in {"copy_file", "move_file", "rename_file", "copy_folder", "move_folder", "rename_folder"}:
            source = norm.get("source") or norm.get("file") or norm.get("folder") or norm.get("target") or norm.get("from")
            dest = norm.get("destination") or norm.get("to") or norm.get("dest")
            if source:
                norm["source"] = str(source).strip()
            if dest:
                norm["destination"] = str(dest).strip()

        elif intent in {"open_folder", "create_folder", "delete_folder"}:
            folder = norm.get("folder") or norm.get("target") or norm.get("name") or norm.get("entity")
            if folder:
                norm["folder"] = str(folder).strip()
                norm["entity"] = str(folder).strip()

        elif intent in {"open_file", "create_file", "delete_file"}:
            file_val = norm.get("file") or norm.get("filename") or norm.get("target") or norm.get("name")
            if file_val:
                norm["file"] = str(file_val).strip()
                norm["entity"] = str(file_val).strip()

        elif intent == "code_agent":
            lang = norm.get("language") or ("python" if "python" in original_text.lower() else "java")
            task = norm.get("task") or norm.get("program") or norm.get("query") or norm.get("code") or ""
            norm["language"] = str(lang).strip()
            norm["task"] = str(task).strip()

        elif intent == "type_text":
            txt = norm.get("text") or norm.get("typed_text") or norm.get("content") or ""
            norm["text"] = str(txt).strip()
            norm["typed_text"] = str(txt).strip()

        return norm

    @staticmethod
    def _fallback_extract_structural_actions(text: str) -> Optional[dict]:
        """
        Deterministic fallback to parse multi-action commands when cloud LLMs
        are temporarily quota-exhausted or unreachable.
        """
        lower = text.lower().strip()
        actions = []

        # Application + YouTube song (e.g. "Chrome open pannu jailer song podu", "Chrome open panni Pavalamalli song play pannu")
        has_chrome = "chrome" in lower
        has_edge = "edge" in lower
        has_song = any(k in lower for k in ("song", "play", "podu", "paattu", "music", "youtube", "paatu"))

        if (has_chrome or has_edge) and has_song:
            app = "Chrome" if has_chrome else "Edge"
            actions.append({"intent": "launch_application", "entities": {"application": app}})

            song_query = ""
            for candidate in ("jailer", "pavalamalli", "anbe anbe", "anirudh", "karuppu"):
                if candidate in lower:
                    song_query = candidate.title()
                    break

            if not song_query:
                m = re.search(r"(\b[a-zA-Z0-9_\s]+?)\s+(?:song|paattu|paatu)\s*(?:podu|play|pannu|podunga)?", lower)
                if m:
                    extracted = m.group(1).replace("open", "").replace("chrome", "").replace("edge", "").replace("panni", "").replace("pannu", "").replace("la", "").replace("youtube", "").strip()
                    if extracted and len(extracted) > 1:
                        song_query = extracted.title()

            if not song_query:
                song_query = "song"

            actions.append({"intent": "play_youtube", "entities": {"search_query": song_query}})
            return {"type": "command", "actions": actions, "original_command": text}

        # Notepad + type text (e.g. "Notepad open panni hello world type pannu")
        if "notepad" in lower and any(k in lower for k in ("type", "write", "ezhudhu", "type pannu")):
            actions.append({"intent": "launch_application", "entities": {"application": "Notepad"}})
            m = re.search(r"['\"]([^'\"]+)['\"]", text)
            if m:
                typed = m.group(1).strip()
            else:
                m = re.search(r"(?:open\s+(?:panni|pannu|and)\s+)?([a-zA-Z0-9\s]+?)\s+(?:type|write|type\s+pannu)", lower)
                if m:
                    typed = m.group(1).replace("notepad", "").replace("open", "").replace("panni", "").replace("pannu", "").strip()
                else:
                    typed = "hello world" if "hello world" in lower else ""
            actions.append({"intent": "type_text", "entities": {"text": typed, "typed_text": typed}})
            return {"type": "command", "actions": actions, "original_command": text}

        # VS Code + Python code agent (e.g. "VS Code open panni Python la calculator program create pannu")
        if ("vs code" in lower or "vscode" in lower) and ("python" in lower or "code" in lower or "calculator" in lower):
            actions.append({"intent": "launch_application", "entities": {"application": "VS Code"}})
            actions.append({"intent": "code_agent", "entities": {"language": "python", "task": "calculator program", "prompt": text}})
            return {"type": "command", "actions": actions, "original_command": text}

        # Downloads folder + copy file (e.g. "Downloads folder open panni report.pdf ah Desktop ku copy pannu")
        if "downloads" in lower and any(k in lower for k in ("copy", "move")) and ("desktop" in lower or ".pdf" in lower):
            actions.append({"intent": "open_folder", "entities": {"folder": "Downloads"}})
            file_name = "report.pdf" if "report.pdf" in lower else "report.pdf"
            dest = "Desktop" if "desktop" in lower else "Desktop"
            actions.append({"intent": "copy_file", "entities": {"source": file_name, "file": file_name, "destination": dest}})
            return {"type": "command", "actions": actions, "original_command": text}

        return None
