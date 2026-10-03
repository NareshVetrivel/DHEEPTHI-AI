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
        "open_application": "launch_application",
        "open_app": "launch_application",
        "launch_app": "launch_application",
        "close_app": "close_application",
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
        "search_web": "google_search",
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
    # ACTION Tag Extraction Layer
    # ==========================================================

    @staticmethod
    def extract_action_command(text: str) -> Optional[str]:
        """
        Extract standardized English automation command from <ACTION>...</ACTION> tag.
        Returns None if no complete, non-empty ACTION tag is present, or if any tag is malformed/unclosed.
        """
        if not text or not isinstance(text, str):
            return None

        # Check for unclosed or mismatched tags
        open_tags = len(re.findall(r"<ACTION\b", text, flags=re.IGNORECASE))
        close_tags = len(re.findall(r"</ACTION>", text, flags=re.IGNORECASE))
        if open_tags == 0 or open_tags != close_tags:
            return None

        # Find all complete <ACTION>...</ACTION> tags (case-insensitive, multiline DOTALL)
        matches = re.findall(r"<ACTION>\s*([\s\S]*?)\s*</ACTION>", text, flags=re.IGNORECASE)
        if not matches:
            return None

        valid_actions = []
        for m in matches:
            m_clean = m.strip()
            if not m_clean or "<action" in m_clean.lower() or "</action" in m_clean.lower():
                return None
            valid_actions.append(m_clean)

        if not valid_actions:
            return None

        # Return normalized command (joined with ' and ' if multiple tags)
        return " and ".join(valid_actions)

    @staticmethod
    def has_action_command(text: str) -> bool:
        """Check whether input contains a valid, complete <ACTION>...</ACTION> tag."""
        return SemanticCommandPlanner.extract_action_command(text) is not None

    # ==========================================================
    # Language Detection & Fast Local Conversation Guard
    # ==========================================================

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect whether input is English, Tamil, Tanglish, or Mixed.
        """
        if not text:
            return "English"
        # Check Tamil script
        if re.search(r"[\u0b80-\u0bff]", text):
            if re.search(r"[a-zA-Z]{2,}", text):
                return "Mixed (Tamil + English)"
            return "Tamil"

        # Check Tanglish marker words
        tanglish_words = {
            "panni", "pannitu", "pannittu", "pannu", "pannunga", "panra", "pandra",
            "seythu", "seithu", "seyi", "seyyunga", "podu", "podunga", "pottu",
            "thira", "thiranthu", "thoraku", "moodu", "eduthu", "anuppu", "ezhudhu",
            "la", "ku", "kku", "ah", "ai", "nu", "da", "pa", "oru", "enna",
            "iruku", "irukum", "sollu", "solla", "pesu", "pathi", "paththi",
            "evlo", "evvalavu", "ethana", "ethanai", "apram", "appuram", "aduthu",
            "kooda", "koodave", "paattu", "paatu", "thedu", "theda", "azhichu",
            "azhichidu", "uruvakku", "kekkanum", "ketka", "dheepthi", "dei", "thala"
        }
        words = set(re.findall(r"[a-zA-Z]+", text.lower()))
        matched_tanglish = words.intersection(tanglish_words)

        has_english_app_or_verb = any(
            w in words for w in {
                "chrome", "edge", "notepad", "vs", "code", "vscode", "word", "excel",
                "calculator", "calc", "downloads", "desktop", "documents", "folder",
                "file", "open", "close", "play", "type", "copy", "move", "delete",
                "search", "create", "screenshot", "youtube", "google", "song", "python"
            }
        )

        if matched_tanglish and has_english_app_or_verb:
            return "Mixed (English + Tanglish)"
        elif matched_tanglish:
            return "Tanglish"
        else:
            return "English"

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

    APP_NAME_MAP = {
        "chrome": "Chrome",
        "google chrome": "Chrome",
        "edge": "Edge",
        "ms edge": "Edge",
        "microsoft edge": "Edge",
        "notepad": "Notepad",
        "note pad": "Notepad",
        "vs code": "VS Code",
        "vscode": "VS Code",
        "visual studio code": "VS Code",
        "word": "Word",
        "ms word": "Word",
        "microsoft word": "Word",
        "excel": "Excel",
        "ms excel": "Excel",
        "microsoft excel": "Excel",
        "powerpoint": "PowerPoint",
        "ppt": "PowerPoint",
        "calculator": "Calculator",
        "calc": "Calculator",
        "paint": "Paint",
        "file explorer": "File Explorer",
        "explorer": "File Explorer",
        "firefox": "Firefox",
        "terminal": "Terminal",
        "cmd": "Command Prompt",
        "powershell": "PowerShell",
    }

    FOLDER_NAME_MAP = {
        "downloads": "Downloads",
        "desktop": "Desktop",
        "documents": "Documents",
        "pictures": "Pictures",
        "photos": "Pictures",
        "videos": "Videos",
        "music": "Music",
        "this pc": "This PC",
        "my computer": "This PC",
        "recycle bin": "Recycle Bin",
    }

    # ==========================================================
    # Main Planning API
    # ==========================================================

    def plan(self, text: str) -> Dict[str, Any]:
        """
        Interpret the speech transcript and return a validated structured plan.
        """
        cleaned_text = str(text or "").strip()

        # Check and extract <ACTION> wrapper if present
        action_cmd = self.extract_action_command(cleaned_text)
        if action_cmd:
            cleaned_text = action_cmd

        detected_lang = self.detect_language(cleaned_text)

        if not cleaned_text or len(cleaned_text) <= 1:
            print(f"[SEMANTIC] Input: {cleaned_text}")
            print(f"[SEMANTIC] Language: {detected_lang}")
            print("[SEMANTIC] Type: CONVERSATION (OS automation bypassed)")
            return {"type": "conversation", "actions": [], "language": detected_lang}

        # Fast conversation check
        if self._is_obviously_conversational(cleaned_text):
            print(f"[SEMANTIC] Input: {cleaned_text}")
            print(f"[SEMANTIC] Language: {detected_lang}")
            print("[SEMANTIC] Type: CONVERSATION (OS automation bypassed)")
            return {"type": "conversation", "actions": [], "language": detected_lang}

        # Plan cache lookup: strips punctuation and normalizes casing
        cache_key = re.sub(r"[^\w\s]", "", cleaned_text.lower()).strip()
        if cache_key in self._plan_cache:
            logger.info("Semantic plan cache hit for: '%s'", cleaned_text)
            cached_plan = dict(self._plan_cache[cache_key])
            cached_plan["language"] = detected_lang
            self._log_plan_details(cleaned_text, detected_lang, cached_plan)
            return cached_plan

        plan = None
        prompt = self.PLANNER_PROMPT_TEMPLATE.replace("{input_text}", cleaned_text)

        try:
            response = self.gemini_client.generate_structured_plan(prompt)
            if response:
                data = self._parse_json(response)
                if isinstance(data, dict):
                    plan = self._validate_and_normalize_plan(data, cleaned_text)
        except Exception as error:
            logger.error("Semantic command planning error: %s", error)
            plan = None

        if not plan or not plan.get("actions"):
            fallback_plan = self._fallback_extract_structural_actions(cleaned_text)
            if fallback_plan and fallback_plan.get("actions"):
                plan = fallback_plan

        if not plan:
            plan = {"type": "conversation", "actions": []}

        plan["language"] = detected_lang
        plan["original_command"] = cleaned_text

        if len(self._plan_cache) > 100:
            self._plan_cache.clear()
        self._plan_cache[cache_key] = plan

        self._log_plan_details(cleaned_text, detected_lang, plan)
        return plan

    @classmethod
    def _log_plan_details(cls, input_text: str, language: str, plan: dict) -> None:
        """Print required semantic debugging logs."""
        print(f"[SEMANTIC] Input: {input_text}")
        print(f"[SEMANTIC] Language: {language}")
        if plan.get("type") == "command" and plan.get("actions"):
            actions = plan["actions"]
            intents = [a.get("intent", "") for a in actions]
            intents_str = ", ".join(intents)
            entities_str = ", ".join(str(a.get("entities", {})) for a in actions)
            cmds_str = ", ".join(f"{i}. {a.get('intent')}({a.get('entities')})" for i, a in enumerate(actions, 1))
            print(f"[SEMANTIC] Intent: {intents_str}")
            print(f"[SEMANTIC] Entities: {entities_str}")
            print(f"[SEMANTIC] Commands: {cmds_str}")
            for a in actions:
                print(f"[SEMANTIC] Dispatch: {a.get('intent')} -> {a.get('entities')}")
        else:
            print("[SEMANTIC] Type: CONVERSATION (OS automation bypassed)")

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

            # Normalize and validate entities per intent
            normalized_entities = self._normalize_entities_for_intent(intent, entities, original_text)
            if normalized_entities is None:
                logger.warning("Discarding intent %s due to missing or invalid required entities", intent)
                continue

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

    @classmethod
    def _normalize_entities_for_intent(
        cls,
        intent: str,
        entities: Dict[str, Any],
        original_text: str,
    ) -> Optional[Dict[str, Any]]:
        """Ensure entity keys match what CommandDispatcher expects, and validate required entities."""
        norm = dict(entities)

        if intent in {"launch_application", "close_application"}:
            app = norm.get("application") or norm.get("app") or norm.get("target") or norm.get("name") or norm.get("entity")
            if not app:
                return None
            app_clean = str(app).strip()
            norm["application"] = cls.APP_NAME_MAP.get(app_clean.lower(), app_clean)

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
            query_str = str(query or "").strip()
            if not query_str:
                query_str = "song"
            # Strip trailing/leading quotes
            query_str = re.sub(r"^['\"]|['\"]$", "", query_str).strip()
            norm["search_query"] = query_str
            norm["query"] = query_str

        elif intent in {"youtube_search", "google_search"}:
            query = norm.get("search_query") or norm.get("query") or norm.get("target") or norm.get("entity")
            if not query:
                return None
            norm["search_query"] = str(query).strip()

        elif intent in {"copy_file", "move_file", "rename_file"}:
            source = norm.get("source") or norm.get("file") or norm.get("filename") or norm.get("target") or norm.get("from")
            dest = norm.get("destination") or norm.get("to") or norm.get("dest")
            # Safety: reject incomplete commands instead of guessing or hallucinating missing entities!
            if not source or not dest:
                return None
            src_str = str(source).strip()
            dest_str = str(dest).strip()
            dest_norm = cls.FOLDER_NAME_MAP.get(dest_str.lower(), dest_str)
            norm["source"] = src_str
            norm["file"] = src_str
            norm["destination"] = dest_norm

        elif intent in {"copy_folder", "move_folder", "rename_folder"}:
            source = norm.get("source") or norm.get("folder") or norm.get("from")
            dest = norm.get("destination") or norm.get("to") or norm.get("dest")
            if not source or not dest:
                return None
            norm["source"] = cls.FOLDER_NAME_MAP.get(str(source).strip().lower(), str(source).strip())
            norm["destination"] = cls.FOLDER_NAME_MAP.get(str(dest).strip().lower(), str(dest).strip())

        elif intent in {"open_folder", "create_folder", "delete_folder"}:
            folder = norm.get("folder") or norm.get("target") or norm.get("name") or norm.get("entity")
            if not folder:
                return None
            f_clean = str(folder).strip()
            norm_folder = cls.FOLDER_NAME_MAP.get(f_clean.lower(), f_clean)
            norm["folder"] = norm_folder
            norm["entity"] = norm_folder

        elif intent in {"open_file", "create_file", "delete_file"}:
            file_val = norm.get("file") or norm.get("filename") or norm.get("target") or norm.get("name") or norm.get("entity")
            if not file_val:
                return None
            norm["file"] = str(file_val).strip()
            norm["entity"] = str(file_val).strip()

        elif intent == "code_agent":
            lang = norm.get("language") or ("python" if "python" in original_text.lower() else "java")
            task = norm.get("task") or norm.get("program") or norm.get("query") or norm.get("code") or norm.get("description") or ""
            norm["language"] = str(lang).strip()
            norm["task"] = str(task).strip()
            norm["description"] = str(task).strip()

        elif intent == "type_text":
            txt = norm.get("text") or norm.get("typed_text") or norm.get("content") or ""
            if not txt:
                return None
            norm["text"] = str(txt).strip()
            norm["typed_text"] = str(txt).strip()

        return norm

    @classmethod
    def _fallback_parse_single_clause(cls, clause: str) -> Optional[dict]:
        """Parse a single atomic clause generically into intent and entities."""
        c = clause.strip()
        if not c:
            return None
        lower = c.lower()

        # 1. Media play (YouTube / song)
        if any(k in lower for k in ["play", "podu", "paattu", "paatu", "song", "music", "youtube"]) and not any(k in lower for k in ["type", "copy", "move", "code", "create"]):
            q = c
            q = re.sub(r"\b(?:on\s+youtube|in\s+youtube|youtube\s+la|youtube|song|songs|paattu|paatu|track|music|play\s+pannu|play\s+pannunga|play|podu|podunga|pannu|la|ah|nu)\b", "", q, flags=re.I)
            q = re.sub(r"\s+", " ", q).strip()
            if not q or len(q) < 2:
                q = "song"
            return {"intent": "play_youtube", "entities": {"search_query": q, "query": q}}

        # 2. Type text
        if any(k in lower for k in ["type", "ezhudhu", "write"]) and not any(k in lower for k in ["code", "program", "script"]):
            m_q = re.search(r"['\"]([^'\"]+)['\"]", c)
            if m_q:
                txt = m_q.group(1).strip()
            else:
                m_nu = re.search(r"(.+?)\s+nu\s+(?:type|write|ezhudhu)", c, flags=re.I)
                if m_nu:
                    txt = m_nu.group(1).strip()
                else:
                    txt = re.sub(r"\b(?:type\s+pannu|type\s+pannitu|type\s+pannunga|type|write|ezhudhu|pannu|nu|da|pa)\b", "", c, flags=re.I).strip()
            if txt:
                return {"intent": "type_text", "entities": {"text": txt, "typed_text": txt}}
            return None

        # 3. Code agent / programming
        if any(k in lower for k in ["program", "code", "calculator", "coding"]) and any(k in lower for k in ["create", "write", "generate", "make", "panni", "pannu"]):
            lang = "python"
            for candidate_lang in ["python", "java", "c++", "cpp", "javascript", "c", "c#", "html"]:
                if candidate_lang in lower:
                    lang = candidate_lang
                    break
            task = c
            task = re.sub(r"\b(?:create\s+pannu|create|write|generate|pannu|la|nu)\b", "", task, flags=re.I)
            task = re.sub(r"\b" + lang + r"\b", "", task, flags=re.I)
            task = re.sub(r"\s+", " ", task).strip()
            if "program" not in task.lower() and "code" not in task.lower():
                task = f"{task} program".strip()
            return {"intent": "code_agent", "entities": {"language": lang, "task": task, "description": task}}

        # 4. Copy / Move / Delete file
        if any(k in lower for k in ["copy", "move", "transfer"]):
            act = "copy_file" if any(k in lower for k in ["copy", "transfer"]) else "move_file"
            m_file = re.search(r"([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)\s*(?:ah|ai|-a)?\s+(?:to\s+)?([a-zA-Z0-9_\-\s]+?)\s*(?:ku|kku|to|\s+folder)?\s*(?:copy|move|transfer|$)", c, flags=re.I)
            if m_file:
                src = m_file.group(1).strip()
                dst = cls.FOLDER_NAME_MAP.get(m_file.group(2).strip().lower().replace("folder", "").strip(), m_file.group(2).strip())
                return {"intent": act, "entities": {"source": src, "file": src, "destination": dst}}
            m_en = re.search(r"(?:copy|move|transfer)\s+([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)\s+to\s+([a-zA-Z0-9_\-\s]+)", c, flags=re.I)
            if m_en:
                src = m_en.group(1).strip()
                dst_raw = m_en.group(2).strip().replace("folder", "").strip()
                dst = cls.FOLDER_NAME_MAP.get(dst_raw.lower(), dst_raw)
                return {"intent": act, "entities": {"source": src, "file": src, "destination": dst}}
            return None

        if any(k in lower for k in ["delete", "remove", "azhichu", "azhi"]):
            m_del = re.search(r"([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)", c)
            if m_del:
                return {"intent": "delete_file", "entities": {"file": m_del.group(1).strip()}}
            return None

        # 5. Open folder
        if any(f in lower for f in ["downloads", "desktop", "documents", "pictures", "videos", "music"]) and any(k in lower for k in ["open", "thira", "thoraku"]):
            m_fol = re.search(r"\b(downloads|desktop|documents|pictures|videos|music)\b", lower)
            if m_fol:
                folder = cls.FOLDER_NAME_MAP.get(m_fol.group(1).lower(), m_fol.group(1).title())
                return {"intent": "open_folder", "entities": {"folder": folder, "entity": folder}}

        # 6. Web / Google search
        if any(k in lower for k in ["search", "thedu"]) and not any(k in lower for k in ["play", "song"]):
            q = c
            q = re.sub(r"\b(?:google\s+la|google|search\s+pannu|search\s+pannunga|search|thedu|pannu|la|nu)\b", "", q, flags=re.I)
            q = re.sub(r"\s+", " ", q).strip()
            if q:
                return {"intent": "google_search", "entities": {"search_query": q}}

        # 7. Screenshot
        if any(k in lower for k in ["screenshot", "screen shot"]):
            return {"intent": "take_screenshot", "entities": {}}

        # 8. Launch / Close application
        apps = [
            ("visual studio code", "VS Code"),
            ("vs code", "VS Code"),
            ("vscode", "VS Code"),
            ("google chrome", "Chrome"),
            ("chrome", "Chrome"),
            ("microsoft edge", "Edge"),
            ("ms edge", "Edge"),
            ("edge", "Edge"),
            ("notepad", "Notepad"),
            ("calculator", "Calculator"),
            ("calc", "Calculator"),
            ("word", "Word"),
            ("excel", "Excel"),
            ("paint", "Paint"),
            ("firefox", "Firefox"),
            ("terminal", "Terminal"),
            ("cmd", "Command Prompt"),
            ("powershell", "PowerShell"),
            ("file explorer", "File Explorer"),
        ]
        for pattern_name, canonical_name in apps:
            if pattern_name in lower:
                if any(k in lower for k in ["close", "exit", "quit", "moodu"]):
                    return {"intent": "close_application", "entities": {"application": canonical_name}}
                if any(k in lower for k in ["open", "launch", "start", "run", "thira", "thiranthu"]):
                    return {"intent": "launch_application", "entities": {"application": canonical_name}}

        return None

    @classmethod
    def _fallback_extract_structural_actions(cls, text: str) -> Optional[dict]:
        """
        Generic, deterministic fallback to decompose and parse multi-action commands
        across English, Tamil, Tanglish, and mixed languages.
        """
        if cls._is_obviously_conversational(text):
            return {"type": "conversation", "actions": []}

        cleaned = re.sub(r"^(?:hey|hi|hello|dheepthi(?:\s+ai)?|ai|dei|da|pa|thala|bro|friend)\s*[,]?\s*", "", text.strip(), flags=re.I).strip()
        connectors = r"(?:\s+panni\s+|\s+pannitu\s+|\s+pannittu\s+|\s+seythu\s+|\s+seithu\s+|\s+and\s+then\s+|\s+after\s+that\s+|\s+apram\s+|\s+appuram\s+|\s+aduthu\s+|\s+and\s+(?=(?:play|type|copy|move|create|open|close|search|run|start))\b|,\s*)"
        raw_clauses = re.split(connectors, cleaned, flags=re.I)

        if len(raw_clauses) == 1:
            m_dual = re.match(r"^(.+?\b(?:open|close|launch))\s+(?:pannu|pannunga|panra)?\s+(.+)$", cleaned, flags=re.I)
            if m_dual:
                raw_clauses = [m_dual.group(1), m_dual.group(2)]

        actions = []
        for clause in raw_clauses:
            clause_str = clause.strip()
            if not clause_str:
                continue
            if any(clause_str.lower().startswith(app) for app in ["chrome", "edge", "notepad", "vs code", "vscode"]) and "open" not in clause_str.lower():
                clause_str = clause_str + " open"
            act = cls._fallback_parse_single_clause(clause_str)
            if act:
                actions.append(act)

        if actions:
            return {"type": "command", "actions": actions, "original_command": text}
        return {"type": "conversation", "actions": []}


extract_action_command = SemanticCommandPlanner.extract_action_command
has_action_command = SemanticCommandPlanner.has_action_command

