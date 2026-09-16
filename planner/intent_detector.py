"""
DHEEPTHI-AI
DHEEPTHI Intent Detector

Responsibilities
----------------
- Local deterministic intent detection
- Whisper/STT normalization
- Tanglish command normalization
- Application detection
- File/folder detection
- Browser detection
- System automation detection
- Microsoft Word V1 intent detection
- Conversation routing
- RapidFuzz fallback
- Gemini semantic intent fallback
- Safe Gemini intent validation

Design
------
Local detection always gets priority.

Gemini is used only when the local detector cannot
confidently determine an executable intent.

Gemini is NEVER allowed to return arbitrary intents.
Only intents explicitly supported by DHEEPTHI-AI are accepted.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from rapidfuzz import process, fuzz


class IntentDetector:
    """
    Detects user intent using a layered strategy.

    Priority
    --------
    1. Normalization
    2. Explicit conversation protection
    3. Deterministic command detection
    4. Word / productivity detection
    5. Browser / system detection
    6. Exact keyword matching
    7. RapidFuzz matching
    8. Gemini semantic fallback
    9. ai_chat fallback
    """

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(
        self,
        gemini_client=None,
        enable_gemini_fallback: bool = True,
    ):
        """
        Parameters
        ----------
        gemini_client:
            Existing GeminiClient instance.

            Passing the existing application-level client is
            strongly recommended because it already contains
            the four-key rotation/fallback mechanism.

        enable_gemini_fallback:
            Enables semantic Gemini fallback for ambiguous
            commands.
        """

        self.gemini_client = gemini_client
        self.enable_gemini_fallback = bool(
            enable_gemini_fallback
        )

        self._gemini_initialized = (
            gemini_client is not None
        )

        # ------------------------------------------------------
        # Application names
        # ------------------------------------------------------

        self.application_open_keywords = {
            "chrome",
            "google chrome",
            "edge",
            "microsoft edge",
            "ms edge",
            "firefox",
            "notepad",
            "note pad",
            "node pad",
            "paint",
            "calculator",
            "calc",
            "cmd",
            "command prompt",
            "powershell",
            "power shell",
            "explorer",
            "file explorer",
            "word",
            "ms word",
            "m s word",
            "microsoft word",
            "excel",
            "ms excel",
            "m s excel",
            "microsoft excel",
            "powerpoint",
            "power point",
            "ppt",
            "presentation",
            "vscode",
            "vs code",
            "visual studio code",
            "pycharm",
            "internet",
            "browser",
        }

        # ------------------------------------------------------
        # Special folders
        # ------------------------------------------------------

        self.folder_open_keywords = {
            "desktop",
            "documents",
            "downloads",
            "pictures",
            "videos",
            "music",
            "this pc",
            "my computer",
            "computer",
            "recycle bin",
            "trash",
            "c drive",
            "d drive",
            "e drive",
        }

        # ------------------------------------------------------
        # AI / conversational keywords
        # ------------------------------------------------------

        self.ai_keywords = {
            "what",
            "who",
            "why",
            "when",
            "where",
            "which",
            "whose",
            "whom",
            "how",
            "explain",
            "describe",
            "define",
            "compare",
            "difference",
            "meaning",
            "guide",
            "teach",
            "learn",
            "study",
            "example",
            "examples",
            "summary",
            "summarize",
            "tell me",
            "tell",
            "about",
            "say",
            "chat",
            "talk",
            "conversation",
            "question",
            "help",
            "information",
            "details",
            "history",
            "advantages",
            "disadvantages",
            "benefits",
            "uses",
            "purpose",
            "python",
            "java",
            "c++",
            "c#",
            "javascript",
            "html",
            "css",
            "sql",
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "neural network",
            "pathi",
            "pati",
            "enna",
            "enna da",
            "epdi",
            "eppadi",
            "yen",
            "ethuku",
            "etharku",
            "sollu",
            "solunga",
            "sollunga",
            "puriyala",
            "puriya",
            "purinjikanum",
            "vilakkam",
            "explain pannu",
            "explain pannunga",
            "detail ah",
            "full detail",
            "full explain",
            "artham",
            "future",
            "use",
        }

        # ------------------------------------------------------
        # Generic keyword -> intent
        # ------------------------------------------------------

        self.intent_keywords = {
            # Application
            "open": "launch_application",
            "start": "launch_application",
            "run": "launch_application",
            "launch": "launch_application",
            "execute": "launch_application",

            "close": "close_application",
            "exit": "close_application",
            "stop": "close_application",
            "quit": "close_application",
            "terminate": "close_application",

            # Typing
            "type": "type_text",
            "write": "type_text",

            # Clipboard
            "copy": "copy",
            "paste": "paste",
            "cut": "cut",
            "undo": "undo",
            "redo": "redo",

            # Keyboard
            "enter": "press_enter",
            "tab": "press_tab",
            "backspace": "backspace",
            "delete": "delete",
            "escape": "escape",
            "esc": "escape",
            "space": "space",
            "up": "arrow_up",
            "down": "arrow_down",
            "left": "arrow_left",
            "right": "arrow_right",
            "home": "home",
            "end": "end",
            "page": "page_down",

            # Mouse
            "click": "left_click",
            "double": "double_click",
            "scroll": "scroll_down",

            # Window
            "minimize": "minimize_window",
            "maximise": "maximize_window",
            "maximize": "maximize_window",
            "minimise": "minimize_window",
            "restore": "restore_window",

            # Audio
            "mute": "mute",
            "volume": "volume_up",
            "volumeup": "volume_up",
            "volumedown": "volume_down",

            # Display
            "brightness": "set_brightness",

            # Power
            "shutdown": "shutdown",
            "restart": "restart",
            "reboot": "restart",
            "sleep": "sleep",
            "logout": "sign_out",
            "signout": "sign_out",

            # Utilities
            "settings": "open_settings",
            "task": "open_task_manager",
            "explorer": "open_file_explorer",
            "cmd": "open_cmd",
            "powershell": "open_powershell",
            "control": "open_control_panel",

            # Camera
            "camera": "open_camera",
            "photo": "capture_photo",
            "screenshot": "take_screenshot",
            "lock": "lock_screen",

            # File
            "select": "select_all",
            "save": "save_file",
            "print": "print_file",
            "folder": "open_folder",
            "file": "open_file",

            # Recording
            "record": "start_screen_recording",
            "recording": "start_screen_recording",
        }

        # ------------------------------------------------------
        # Tanglish command normalization
        # ------------------------------------------------------

        self.tanglish_command_map = {
            "thorakka": "open",
            "thorak": "open",
            "thirakka": "open",
            "thirak": "open",
            "open pannu": "open",

            "moodu": "close",
            "mudu": "close",
            "close pannu": "close",

            "theda": "search",
            "thedu": "search",
            "thedi": "search",

            "kaatu": "show",

            "podu": "play",

            "uruvakku": "create",
            "uruvaku": "create",

            "azhichidu": "delete",
            "azhichu": "delete",

            "maathu": "rename",
            "mathu": "rename",

            "nagarthu": "move",

            "copy pannu": "copy",
            "paste pannu": "paste",
            "cut pannu": "cut",

            "start pannu": "start",
            "open pannu": "open",
            "close pannu": "close",
            "stop pannu": "stop",

            "screenshot edu": "take screenshot",
            "photo edu": "take photo",
        }

        # ------------------------------------------------------
        # Supported intents
        #
        # Gemini output MUST belong to this set.
        # ------------------------------------------------------

        self.supported_intents = {
            # Conversation
            "ai_chat",

            # Code Agent
            "code_agent",

            # Application
            "launch_application",
            "close_application",

            # Generic keyboard
            "type_text",
            "copy",
            "paste",
            "cut",
            "undo",
            "redo",
            "press_enter",
            "press_tab",
            "backspace",
            "delete",
            "escape",
            "space",
            "arrow_up",
            "arrow_down",
            "arrow_left",
            "arrow_right",
            "home",
            "end",
            "page_down",

            # Mouse
            "left_click",
            "right_click",
            "double_click",
            "scroll_up",
            "scroll_down",

            # Window
            "minimize_window",
            "maximize_window",
            "restore_window",
            "close_window",

            # System
            "mute",
            "volume_up",
            "volume_down",
            "set_volume",
            "brightness_up",
            "brightness_down",
            "set_brightness",
            "shutdown",
            "restart",
            "sleep",
            "sign_out",
            "open_settings",
            "open_task_manager",
            "open_cmd",
            "open_powershell",
            "open_control_panel",
            "open_file_explorer",
            "open_camera",
            "capture_photo",
            "take_screenshot",
            "lock_screen",

            # Files
            "open_file",
            "create_file",
            "delete_file",
            "rename_file",
            "copy_file",
            "move_file",

            # Folders
            "open_folder",
            "create_folder",
            "delete_folder",
            "rename_folder",
            "copy_folder",
            "move_folder",
            "empty_recycle_bin",

            # Search
            "search_extension",
            "search_size",
            "search_date",
            "google_search",

            # Archive
            "compress_file",
            "extract_zip",

            # Browser
            "open_website",
            "open_google",
            "open_youtube",
            "new_tab",
            "close_tab",
            "next_tab",
            "previous_tab",
            "refresh",
            "browser_history",
            "browser_downloads",
            "browser_bookmarks",
            "bookmark_page",
            "address_bar",
            "browser_back",
            "browser_forward",
            "private_window",
            "open_chrome_profile",
            "youtube_search",
            "play_youtube",

            # Recording
            "start_screen_recording",
            "stop_screen_recording",

            # File operations
            "save_file",
            "print_file",
            "select_all",

            # Word
            "open_word",
            "close_word",
            "create_blank_document",
            "open_existing_document",
            "save",
            "save_as",
            "save_docx",
            "save_pdf",
            "close_current_document",
            "create_specified_filename",
            "read_existing_document",
            "add_text_at_cursor",
            "replace_content",
            "read_document",
            "clear_document",
            "strikethrough",
            "underline",
            "italic",
            "bold",
            "font_size",
            "font",
            "text_color",
            "highlight",
            "align_left",
            "align_center",
            "align_right",
            "justify",
            "line_spacing",
            "paragraph_spacing",
            "indentation",
            "bullets",
            "numbering",
            "title",
            "heading_1",
            "normal",
            "document_style",
            "read_table_data",
            "create_table",
            "replace",
            "find",
            "image",
            "hyperlink",
            "page_break",
            "new_page",
            "header",
            "footer",
            "page_number",
            "margins",

            # Legacy Office
            "create_word_document",
            "create_excel_workbook",
            "create_powerpoint_presentation",
        }

    # ==========================================================
    # GEMINI CLIENT
    # ==========================================================

    def set_gemini_client(self, gemini_client):
        """
        Inject an already-created GeminiClient.

        This avoids creating multiple Gemini clients and
        preserves the existing four-key rotation system.
        """

        self.gemini_client = gemini_client
        self._gemini_initialized = (
            gemini_client is not None
        )

    def _get_gemini_client(self):
        """
        Return the configured Gemini client.

        Lazy import is used so the detector can still operate
        completely offline/local when Gemini is unavailable.
        """

        if not self.enable_gemini_fallback:
            return None

        if self.gemini_client is not None:
            return self.gemini_client

        if self._gemini_initialized:
            return None

        self._gemini_initialized = True

        try:
            from ai.gemini_client import GeminiClient

            self.gemini_client = GeminiClient()

            print(
                "IntentDetector : Gemini semantic fallback ready."
            )

            return self.gemini_client

        except Exception as error:
            print(
                "IntentDetector : Gemini fallback unavailable:",
                error,
            )

            self.gemini_client = None

            return None

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    @staticmethod
    def _basic_normalize(text: str) -> str:
        """
        Basic text normalization.
        """

        if text is None:
            return ""

        text = str(text).lower().strip()

        if not text:
            return ""

        # Common punctuation from speech recognition.
        text = re.sub(
            r"[,\.;:!?]+",
            " ",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    def _normalize_text(self, text: str) -> str:
        """
        Normalize recognized speech.

        Includes common Whisper/STT mistakes and Tanglish
        command normalization.
        """

        text = self._basic_normalize(text)

        if not text:
            return ""

        # --------------------------------------------------
        # Filler removal
        # --------------------------------------------------

        fillers = {
            "uh",
            "um",
            "hmm",
            "mmm",
            "ah",
            "oh",
        }

        words = [
            word
            for word in text.split()
            if word not in fillers
        ]

        text = " ".join(words)

        # --------------------------------------------------
        # Common Whisper corrections
        # --------------------------------------------------

        replacements = (
            ("bdf", "pdf"),
            ("estaday", "yesterday"),
            ("yester day", "yesterday"),

            ("you tube", "youtube"),
            ("you to", "youtube"),
            ("u tube", "youtube"),
            ("you too", "youtube"),

            ("g mail", "gmail"),

            ("power point presentation", "powerpoint"),
            ("power point", "powerpoint"),

            ("note pad", "notepad"),
            ("node pad", "notepad"),

            ("command promt", "command prompt"),
            ("command promt", "command prompt"),

            ("vs code", "vscode"),
            ("visual studio code", "vscode"),

            ("chrome browser", "chrome"),
            ("google chrome browser", "chrome"),

            ("excel sheet", "excel"),

            ("c plus plus", "c++"),
            ("c sharp", "c#"),

            ("artificial intelligent", "artificial intelligence"),

            # Common Word/STT confusion.
            ("ms word", "word"),
            ("m s word", "word"),
            ("microsoft word", "word"),

            # Common browser pronunciation variants.
            ("fire fox", "firefox"),

            # Common PowerShell pronunciation.
            ("power shell", "powershell"),
        )

        for old, new in replacements:
            text = text.replace(old, new)

        text = self._basic_normalize(text)

        # --------------------------------------------------
        # Tanglish command normalization
        # --------------------------------------------------

        # Longest phrases first so that:
        #
        # "open pannu"
        #
        # is handled before individual words.
        for old, new in sorted(
            self.tanglish_command_map.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            text = text.replace(old, new)

        text = self._basic_normalize(text)

        return text

    # ==========================================================
    # CONVERSATION PROTECTION
    # ==========================================================

    def _is_explicit_automation_command(
        self,
        text: str,
    ) -> bool:
        """
        Return True only when the message clearly asks
        DHEEPTHI-AI to perform an action.

        This prevents normal questions such as:

            "Why should I open Chrome?"

        from becoming launch_application.
        """

        if not text:
            return False

        text = self._basic_normalize(text)

        explicit_patterns = (
            r"^(open|start|run|launch)\b",
            r"^(close|exit|quit|terminate)\b",
            r"^(type|write|copy|paste|cut|undo|redo)\b",
            r"^(click|double click|right click|scroll)\b",
            r"^(minimize|maximize|restore)\b",

            r"^(mute|lock|shutdown|restart|reboot|sleep|logout|signout)\b",

            r"^(take )?screenshot\b",

            r"^(set|increase|decrease|turn)\s+"
            r"(the\s+)?(volume|brightness)\b",

            r"^(create|make|new|delete|remove|rename|move|copy|"
            r"compress|extract)\b",

            r"^(search|google|youtube|play)\b",

            r"^(new tab|close tab|next tab|previous tab|"
            r"refresh|reload|go back|go forward)\b",

            r"^(press )?"
            r"(enter|tab|backspace|delete|escape|esc|space|home|end)\b",

            r"^(open )?"
            r"(settings|task manager|file explorer|camera|"
            r"control panel|cmd|powershell)\b",

            r"^(start|stop|begin|end|finish)\s+"
            r"((the|my)\s+)?(screen\s+)?record(ing)?\b",

            r"^(record|recording)\s+"
            r"(the\s+)?(screen)\b",

            r"^(screenshot|screen shot)\b",

            # Word formatting/action commands.
            r"^(make|set|apply|change|turn|add|insert|create|"
            r"remove|delete|clear|select|save|read|open|close)\b",
        )

        return any(
            re.search(pattern, text)
            for pattern in explicit_patterns
        )

    def _is_conversational_message(
        self,
        text: str,
    ) -> bool:
        """
        Detect natural conversation and questions.

        Explicit automation commands are excluded by the caller.
        """

        if not text:
            return False

        text = self._basic_normalize(text)

        question_patterns = (
            r"^(what|who|why|when|where|which|whose|whom|how)\b",

            r"^(enna|enna da|ethu|edhu|yaaru|yaru|yen|en|"
            r"epdi|eppadi|eppo|engae|enga|ethuku|etharku)\b",

            r"\b(can|could|would|should|is|are|do|does|did|will)"
            r"\s+(you|i|we|this|that|it)\b",

            r"\b(meaning|difference|compare|explain|describe|"
            r"define|teach|guide|summary|summarize)\b",
        )

        if any(
            re.search(
                pattern,
                text,
            )
            for pattern in question_patterns
        ):
            return True

        temporal_terms = (
            "time",
            "date",
            "day",
            "today",
            "tomorrow",
            "yesterday",
            "kannum",
            "innaiku",
            "innikku",
            "naalai",
            "netru",
        )

        if any(
            term in text
            for term in temporal_terms
        ):
            if any(
                token in text
                for token in (
                    "what",
                    "enna",
                    "ethu",
                    "edhu",
                    "tell",
                    "sollu",
                    "solunga",
                    "sollunga",
                    "current",
                    "now",
                    "ippo",
                    "ippa",
                    "today",
                    "innaiku",
                )
            ):
                return True

        follow_ups = {
            "why",
            "how",
            "then",
            "continue",
            "go on",
            "tell me more",
            "explain more",
            "what about that",
            "what about this",
            "and then",
            "after that",
            "okay then",
            "seri then",
            "appo",
            "aprm",
            "apram",
            "athuku apram",
            "idhu enna",
            "athu enna",
            "adhula enna",
            "idha explain pannu",
            "atha explain pannu",
            "continue da",
        }

        if text in follow_ups:
            return True

        conversational_phrases = (
            "who are you",
            "your name",
            "who created you",
            "creator",
            "astra-ai",
            "dheepthi",
            "hello",
            "hi",
            "thanks",
            "thank you",
            "nandri",
            "pathi",
            "pati",
            "puriyala",
            "puriya",
            "sollu",
            "solunga",
            "sollunga",
            "detail ah",
            "full detail",
            "example",
            "examples",
        )

        return any(
            phrase in text
            for phrase in conversational_phrases
        )

    # ==========================================================
    # HELPERS
    # ==========================================================

    @staticmethod
    def _has_any(
        text: str,
        values,
    ) -> bool:
        return any(
            value in text
            for value in values
        )

    @staticmethod
    def _has_transfer_connector(
        text: str,
    ) -> bool:
        """
        Detect file/folder transfer connectors.

        Supports natural speech variations:

            to
            into
            2
            ku
            kku
        """

        padded = f" {text} "

        return any(
            token in padded
            for token in (
                " to ",
                " into ",
                " 2 ",
                " ku ",
                " kku ",
            )
        )

    # ==========================================================
    # FOLDER INTENTS
    # ==========================================================

    def _detect_folder_intent(
        self,
        text: str,
    ) -> Optional[str]:

        # ------------------------------------------------------
        # Create
        # ------------------------------------------------------

        if (
            (
                text.startswith("create ")
                or text.startswith("make ")
                or text.startswith("new ")
            )
            and "folder" in text
        ):
            return "create_folder"

        # ------------------------------------------------------
        # Rename
        # ------------------------------------------------------

        if (
            "rename" in text
            and "folder" in text
            and self._has_transfer_connector(text)
        ):
            return "rename_folder"

        if any(
            phrase in text
            for phrase in (
                "rename folder",
                "rename a folder",
                "rename the folder",
                "rename your folder",
            )
        ):
            return "rename_folder"

        # ------------------------------------------------------
        # Delete
        # ------------------------------------------------------

        if (
            (
                text.startswith("delete ")
                or text.startswith("remove ")
            )
            and "folder" in text
        ):
            return "delete_folder"

        if any(
            phrase in text
            for phrase in (
                "delete folder",
                "delete a folder",
                "delete the folder",
                "remove folder",
                "remove a folder",
                "remove the folder",
            )
        ):
            return "delete_folder"

        # ------------------------------------------------------
        # Move
        # ------------------------------------------------------

        if (
            text.startswith("move ")
            and "folder" in text
            and self._has_transfer_connector(text)
        ):
            return "move_folder"

        if any(
            phrase in text
            for phrase in (
                "move folder",
                "move a folder",
                "move the folder",
            )
        ):
            return "move_folder"

        # ------------------------------------------------------
        # Copy
        # ------------------------------------------------------

        if (
            text.startswith("copy ")
            and "folder" in text
            and self._has_transfer_connector(text)
        ):
            return "copy_folder"

        if any(
            phrase in text
            for phrase in (
                "copy folder",
                "copy a folder",
                "copy the folder",
            )
        ):
            return "copy_folder"

        # ------------------------------------------------------
        # Recycle bin
        # ------------------------------------------------------

        if (
            "empty recycle bin" in text
            or "clear recycle bin" in text
        ):
            return "empty_recycle_bin"

        # ------------------------------------------------------
        # Generic open folder
        # ------------------------------------------------------

        if any(
            phrase in text
            for phrase in (
                "open folder",
                "open a folder",
                "open the folder",
                "open your folder",
            )
        ):
            return "open_folder"

        # ------------------------------------------------------
        # Special folders
        # ------------------------------------------------------

        for folder in self.folder_open_keywords:

            if folder in text:
                return "open_folder"

        return None

    # ==========================================================
    # FILE INTENTS
    # ==========================================================

    def _detect_file_intent(
        self,
        text: str,
    ) -> Optional[str]:

        # ------------------------------------------------------
        # Rename
        # ------------------------------------------------------

        if (
            text.startswith("rename ")
            and self._has_transfer_connector(text)
            and "folder" not in text
        ):
            return "rename_file"

        if any(
            phrase in text
            for phrase in (
                "rename file",
                "rename a file",
                "rename the file",
            )
        ):
            return "rename_file"

        # ------------------------------------------------------
        # Copy
        # ------------------------------------------------------

        if (
            text.startswith("copy ")
            and self._has_transfer_connector(text)
            and "folder" not in text
        ):
            return "copy_file"

        if any(
            phrase in text
            for phrase in (
                "copy file",
                "copy a file",
                "copy the file",
                "copy this file",
                "copy document",
                "copy pdf",
            )
        ):
            return "copy_file"

        # ------------------------------------------------------
        # Move
        # ------------------------------------------------------

        if (
            text.startswith("move ")
            and self._has_transfer_connector(text)
            and "folder" not in text
        ):
            return "move_file"

        if any(
            phrase in text
            for phrase in (
                "move file",
                "move a file",
                "move the file",
                "move this file",
                "move document",
                "move pdf",
            )
        ):
            return "move_file"

        # ------------------------------------------------------
        # Create
        # ------------------------------------------------------

        if (
            text.startswith(
                (
                    "create ",
                    "make ",
                    "new ",
                )
            )
            and "file" in text.split()
            and "folder" not in text
        ):
            return "create_file"

        if "create file" in text:
            return "create_file"

        # ------------------------------------------------------
        # Delete
        # ------------------------------------------------------

        if (
            (
                text.startswith("delete ")
                or text.startswith("remove ")
            )
            and "file" in text
            and "folder" not in text
        ):
            return "delete_file"

        if (
            "delete file" in text
            and "folder" not in text
        ):
            return "delete_file"

        # ------------------------------------------------------
        # Archive
        # ------------------------------------------------------

        if (
            "extract zip" in text
            or "extract archive" in text
            or "unzip" in text
            or "un zip" in text
            or "open zip" in text
        ):
            return "extract_zip"

        if (
            "compress file" in text
            or "compress " in text
            or text == "compress"
            or "zip file" in text
            or "create zip" in text
            or "zip this file" in text
            or "make zip" in text
            or "archive file" in text
        ):
            return "compress_file"

        return None

    # ==========================================================
    # SCREEN CAPTURE / RECORDING INTENTS
    # ==========================================================

    def _detect_capture_intent(
        self,
        text: str,
    ) -> Optional[str]:
        """
        Detect screenshot and screen-recording commands with
        explicit phrase matching.

        This method is intentionally evaluated before generic
        application detection. Without this priority, commands
        beginning with ``start`` can be incorrectly classified as
        ``launch_application``.

        Stop phrases are checked before start phrases so that a
        command such as ``stop recording`` can never be interpreted
        as a start request.
        """

        if not text:
            return None

        text = self._basic_normalize(text)

        if not text:
            return None

        # ------------------------------------------------------
        # Screenshot
        # ------------------------------------------------------

        screenshot_phrases = (
            "take screenshot",
            "take a screenshot",
            "take screen shot",
            "take a screen shot",
            "capture screenshot",
            "capture a screenshot",
            "capture screen shot",
            "capture a screen shot",
            "capture screen",
            "screenshot this screen",
            "screenshot this window",
            "screenshot window",
            "screen shot this screen",
            "screen shot this window",
            "take screenshot of",
            "take a screenshot of",
            "capture screenshot of",
            "capture a screenshot of",
            "take screenshot from",
            "capture the screen",
            "save screenshot",
            "save a screenshot",
        )

        if any(
            phrase in text
            for phrase in screenshot_phrases
        ):
            return "take_screenshot"

        # Short direct form after normalization.
        if text in {
            "screenshot",
            "screen shot",
        }:
            return "take_screenshot"

        # ------------------------------------------------------
        # Stop recording
        # ------------------------------------------------------

        stop_recording_phrases = (
            "stop screen recording",
            "stop the screen recording",
            "stop screen record",
            "stop the screen record",
            "stop recording screen",
            "stop the recording screen",
            "stop recording",
            "stop the recording",
            "stop this recording",
            "stop current recording",
            "end screen recording",
            "end the screen recording",
            "end screen record",
            "end recording",
            "finish screen recording",
            "finish the screen recording",
            "finish recording",
            "stop screen capture",
            "stop the screen capture",
            "stop capturing screen",
            "stop capturing the screen",
            "screen recording stop",
            "screen recording stop pannu",
            "recording stop pannu",
            "recording niruthu",
            "screen recording niruthu",
            "screen record niruthu",
        )

        if any(
            phrase in text
            for phrase in stop_recording_phrases
        ):
            return "stop_screen_recording"

        # ------------------------------------------------------
        # Start recording
        # ------------------------------------------------------

        start_recording_phrases = (
            "start screen recording",
            "start the screen recording",
            "start screen record",
            "start the screen record",
            "start recording screen",
            "start the recording screen",
            "start recording",
            "start the recording",
            "begin screen recording",
            "begin the screen recording",
            "begin screen record",
            "begin the screen record",
            "begin recording",
            "begin the recording",
            "record screen",
            "record the screen",
            "record my screen",
            "record my computer screen",
            "record this screen",
            "record the current screen",
            "start screen capture",
            "start the screen capture",
            "start capturing screen",
            "start capturing the screen",
            "screen recording start",
            "screen recording start pannu",
            "recording start pannu",
            "recording edu",
            "screen recording edu",
            "screen record edu",
            "screen record start",
        )

        if any(
            phrase in text
            for phrase in start_recording_phrases
        ):
            return "start_screen_recording"

        return None

    # ==========================================================
    # SYSTEM INTENTS
    # ==========================================================

    def _detect_system_intent(
        self,
        text: str,
    ) -> Optional[str]:

        # ------------------------------------------------------
        # Volume
        # ------------------------------------------------------

        if (
            "set volume" in text
            or "volume to" in text
            or "volume at" in text
            or "volume level" in text
        ):
            return "set_volume"

        if (
            "volume up" in text
            or "increase volume" in text
            or "raise volume" in text
            or "turn up volume" in text
        ):
            return "volume_up"

        if (
            "volume down" in text
            or "decrease volume" in text
            or "lower volume" in text
            or "turn down volume" in text
        ):
            return "volume_down"

        if (
            "mute" in text
            or "mute audio" in text
            or "turn off sound" in text
        ):
            return "mute"

        # ------------------------------------------------------
        # Brightness
        # ------------------------------------------------------

        if (
            "brightness up" in text
            or "increase brightness" in text
            or "raise brightness" in text
            or "brighten screen" in text
            or "brighten display" in text
        ):
            return "brightness_up"

        if (
            "brightness down" in text
            or "decrease brightness" in text
            or "lower brightness" in text
            or "dim screen" in text
            or "dim display" in text
        ):
            return "brightness_down"

        if (
            "set brightness" in text
            or "brightness to" in text
            or "brightness at" in text
            or "brightness level" in text
        ):
            return "set_brightness"

        # ------------------------------------------------------
        # Power
        # ------------------------------------------------------

        if (
            "shutdown" in text
            or "shut down" in text
            or "turn off computer" in text
            or "turn off pc" in text
            or "power off computer" in text
            or "power off pc" in text
        ):
            return "shutdown"

        if (
            "restart computer" in text
            or "restart pc" in text
            or "restart system" in text
            or "reboot computer" in text
            or "reboot pc" in text
            or "reboot system" in text
        ):
            return "restart"

        if (
            "sleep computer" in text
            or "sleep pc" in text
            or "sleep system" in text
            or "put computer to sleep" in text
            or "put pc to sleep" in text
            or "put my pc to sleep" in text
        ):
            return "sleep"

        if (
            "sign out" in text
            or "signout" in text
            or "log out" in text
            or "logout" in text
        ):
            return "sign_out"

        # ------------------------------------------------------
        # Utilities
        # ------------------------------------------------------

        if (
            "open settings" in text
            or "open windows settings" in text
            or "windows settings" in text
            or "system settings" in text
        ):
            return "open_settings"

        if "task manager" in text:
            return "open_task_manager"

        if (
            "open cmd" in text
            or "launch cmd" in text
            or "start cmd" in text
            or "open command prompt" in text
            or "launch command prompt" in text
            or "start command prompt" in text
        ):
            return "open_cmd"

        if (
            "open powershell" in text
            or "launch powershell" in text
            or "start powershell" in text
        ):
            return "open_powershell"

        if (
            "open control panel" in text
            or "launch control panel" in text
            or "start control panel" in text
        ):
            return "open_control_panel"

        if (
            "file explorer" in text
            or text == "this pc"
            or "open this pc" in text
            or "my computer" in text
        ):
            return "open_file_explorer"

        # ------------------------------------------------------
        # Camera
        # ------------------------------------------------------

        if (
            "open camera" in text
            or "launch camera" in text
            or "start camera" in text
            or "open webcam" in text
            or "launch webcam" in text
        ):
            return "open_camera"

        if (
            "take photo" in text
            or "take a photo" in text
            or "capture photo" in text
            or "capture a photo" in text
            or "take picture" in text
            or "take a picture" in text
            or "capture picture" in text
            or "capture a picture" in text
            or "take selfie" in text
            or "capture selfie" in text
        ):
            return "capture_photo"

        # ------------------------------------------------------
        # Screenshot
        # ------------------------------------------------------

        if (
            "take screenshot" in text
            or "screen shot" in text
            or "capture screen" in text
            or "take screen shot" in text
        ):
            return "take_screenshot"

        # ------------------------------------------------------
        # Lock
        # ------------------------------------------------------

        if (
            "lock screen" in text
            or "lock computer" in text
            or "lock my pc" in text
            or "lock system" in text
        ):
            return "lock_screen"

        # ------------------------------------------------------
        # Recording
        # ------------------------------------------------------

        if (
            "stop screen recording" in text
            or "stop screen record" in text
            or "end screen recording" in text
            or "finish screen recording" in text
            or "stop recording screen" in text
            or "stop screen capture" in text
        ):
            return "stop_screen_recording"

        if (
            "start screen recording" in text
            or "start screen record" in text
            or "begin screen recording" in text
            or "begin screen record" in text
            or "record screen" in text
            or "record my screen" in text
            or "start recording screen" in text
            or "start screen capture" in text
        ):
            return "start_screen_recording"

        return None

    # ==========================================================
    # BROWSER INTENTS
    # ==========================================================

    def _detect_browser_intent(
        self,
        text: str,
    ) -> Optional[str]:

        if "new tab" in text:
            return "new_tab"

        if "close tab" in text:
            return "close_tab"

        if "next tab" in text:
            return "next_tab"

        if "previous tab" in text:
            return "previous_tab"

        if (
            text == "refresh"
            or "refresh page" in text
            or "reload" in text
            or "reload page" in text
        ):
            return "refresh"

        if (
            text == "history"
            or "open history" in text
            or "browser history" in text
            or "show browser history" in text
        ):
            return "browser_history"

        if (
            text == "downloads"
            or "open downloads" in text
            or "browser downloads" in text
        ):
            return "browser_downloads"

        if (
            "bookmark page" in text
            or "add bookmark" in text
            or "bookmark this page" in text
        ):
            return "bookmark_page"

        if "bookmark" in text:
            return "browser_bookmarks"

        if "address bar" in text:
            return "address_bar"

        if "go back" in text:
            return "browser_back"

        if "go forward" in text:
            return "browser_forward"

        if (
            "private window" in text
            or "incognito" in text
            or "inprivate" in text
        ):
            return "private_window"

        if (
            "profile" in text
            and any(
                word in text
                for word in (
                    "open",
                    "launch",
                    "start",
                    "switch",
                )
            )
        ):
            return "open_chrome_profile"

        if (
            "youtube" in text
            and "search" in text
        ):
            return "youtube_search"

        if (
            text.startswith("play ")
            or "play song" in text
            or "play music" in text
            or "play video" in text
        ):
            return "play_youtube"

        if (
            "open google" in text
            or text == "google"
        ):
            return "open_google"

        if (
            "open youtube" in text
            or text == "youtube"
        ):
            return "open_youtube"

        if (
            "google search" in text
            or "search google" in text
        ):
            return "google_search"

        if (
            "open website" in text
            or "visit website" in text
            or "visit " in text
            or "www." in text
        ):
            return "open_website"

        # ------------------------------------------------------
        # Generic web search
        # ------------------------------------------------------

        if (
            text.startswith("search ")
            and "file" not in text
        ):
            return "google_search"

        return None

    # ==========================================================
    # APPLICATION INTENTS
    # ==========================================================

    def _detect_application_intent(
        self,
        text: str,
    ) -> Optional[str]:

        # ------------------------------------------------------
        # Word lifecycle
        # ------------------------------------------------------

        if text in {
            "word",
            "open word",
            "launch word",
            "start word",
        }:
            return "open_word"

        if any(
            phrase in text
            for phrase in (
                "close word",
                "close ms word",
                "close microsoft word",
                "exit word",
                "quit word",
                "terminate word",
            )
        ):
            return "close_word"

        # ------------------------------------------------------
        # Explicit application close
        # ------------------------------------------------------

        for app in self.application_open_keywords:

            if app not in text:
                continue

            if any(
                command in text
                for command in (
                    "close",
                    "exit",
                    "quit",
                    "terminate",
                    "stop",
                )
            ):
                return "close_application"

        # ------------------------------------------------------
        # Explicit application open
        # ------------------------------------------------------

        for app in self.application_open_keywords:

            if (
                text == app
                or f"open {app}" in text
                or f"launch {app}" in text
                or f"run {app}" in text
                or f"start {app}" in text
            ):
                return "launch_application"

        # ------------------------------------------------------
        # Generic open/launch/run
        # ------------------------------------------------------

        if (
            text.startswith("open ")
            or text.startswith("launch ")
            or text.startswith("run ")
            or text.startswith("start ")
        ):
            if (
                "find " not in text
                and "search " not in text
            ):
                if "file" in text:
                    return "open_file"

                # If website was not detected earlier, generic
                # application launch remains the fallback.
                return "launch_application"

        return None

    # ==========================================================
    # SEARCH INTENTS
    # ==========================================================

    def _detect_search_intent(
        self,
        text: str,
    ) -> Optional[str]:

        # ------------------------------------------------------
        # Extension search
        # ------------------------------------------------------

        extensions = (
            "pdf",
            "doc",
            "docx",
            "txt",
            "ppt",
            "pptx",
            "xls",
            "xlsx",
            "csv",
            "jpg",
            "jpeg",
            "png",
            "mp3",
            "mp4",
            "zip",
        )

        semantic_file_types = (
            "word",
            "excel",
            "powerpoint",
            "ppt",
            "text",
            "image",
            "images",
            "photo",
            "photos",
            "video",
            "videos",
            "music",
            "audio",
        )

        if any(
            extension in text
            for extension in extensions
        ) or any(
            value in text
            for value in semantic_file_types
        ):
            if any(
                keyword in text
                for keyword in (
                    "find",
                    "search",
                    "show",
                    "list",
                    "locate",
                )
            ):
                return "search_extension"

        # ------------------------------------------------------
        # Search by size
        # ------------------------------------------------------

        if any(
            keyword in text
            for keyword in (
                "larger than",
                "bigger than",
                "greater than",
                "above",
                "over",
                "under",
                "less than",
                "smaller than",
                "size",
            )
        ):
            if any(
                keyword in text
                for keyword in (
                    "file",
                    "files",
                    "find",
                    "search",
                    "show",
                )
            ):
                return "search_size"

        # ------------------------------------------------------
        # Search by date
        # ------------------------------------------------------

        if any(
            keyword in text
            for keyword in (
                "today",
                "yesterday",
                "last week",
                "last month",
                "recent",
                "modified",
                "created",
            )
        ):
            if any(
                keyword in text
                for keyword in (
                    "file",
                    "files",
                    "find",
                    "search",
                    "show",
                )
            ):
                return "search_date"

        return None

    # ==========================================================
    # WORD V1 INTENTS
    # ==========================================================

    def _is_word_context(
        self,
        text: str,
    ) -> bool:
        """
        Determine whether the utterance clearly belongs
        to Microsoft Word.

        Important:
        Generic words like "document" are treated as Word
        context only when an actual document operation is
        being requested.
        """

        word_terms = (
            "word",
            "ms word",
            "microsoft word",
            "word document",
            "word file",
            "docx",
        )

        if any(
            term in text
            for term in word_terms
        ):
            return True

        # "document" becomes Word context for explicit
        # document operations.
        if "document" in text:
            return any(
                phrase in text
                for phrase in (
                    "create document",
                    "new document",
                    "blank document",
                    "open document",
                    "save document",
                    "close document",
                    "read document",
                    "clear document",
                    "document content",
                    "document text",
                    "document style",
                    "document table",
                    "document font",
                )
            )

        return False

    def _detect_word_intent(
        self,
        text: str,
    ) -> Optional[str]:

        word_context = self._is_word_context(text)

        if not word_context:
            return None

        # ------------------------------------------------------
        # Lifecycle
        # ------------------------------------------------------

        if text in {
            "word",
            "open word",
            "open ms word",
            "open microsoft word",
            "launch word",
            "launch ms word",
            "launch microsoft word",
            "start word",
            "start ms word",
            "start microsoft word",
        }:
            return "open_word"

        if any(
            phrase in text
            for phrase in (
                "close word",
                "close ms word",
                "close microsoft word",
                "exit word",
                "quit word",
                "terminate word",
            )
        ):
            return "close_word"

        # ------------------------------------------------------
        # Create blank document
        # ------------------------------------------------------

        if any(
            phrase in text
            for phrase in (
                "new document",
                "create document",
                "create a document",
                "create the document",
                "blank document",
                "new word document",
                "create word document",
                "create a word document",
            )
        ):
            return "create_blank_document"

        # ------------------------------------------------------
        # Existing document
        # ------------------------------------------------------

        if any(
            phrase in text
            for phrase in (
                "open existing document",
                "open existing word document",
                "open document",
                "open a document",
                "open the document",
                "open docx",
            )
        ):
            return "open_existing_document"

        # ------------------------------------------------------
        # Save
        # ------------------------------------------------------

        if (
            text in {
                "save",
                "save document",
                "save the document",
                "save word document",
                "save this document",
            }
            or "save current document" in text
        ):
            return "save"

        if (
            "save as" in text
            or "save document as" in text
            or "save the document as" in text
        ):
            return "save_as"

        if (
            "save as docx" in text
            or "save document as docx" in text
            or "save word document as docx" in text
        ):
            return "save_docx"

        if (
            "save as pdf" in text
            or "save document as pdf" in text
            or "export document to pdf" in text
            or "export as pdf" in text
        ):
            return "save_pdf"

        if (
            "close current document" in text
            or "close the current document" in text
            or "close document" in text
            or "close the document" in text
        ):
            return "close_current_document"

        if any(
            phrase in text
            for phrase in (
                "create document named",
                "create document called",
                "create word file named",
                "create word file called",
                "create specified filename",
            )
        ):
            return "create_specified_filename"

        if any(
            phrase in text
            for phrase in (
                "read existing document",
                "read the existing document",
                "read existing word document",
            )
        ):
            return "read_existing_document"

        # ------------------------------------------------------
        # Content
        # ------------------------------------------------------

        if any(
            phrase in text
            for phrase in (
                "add text at cursor",
                "add text to cursor",
                "insert text at cursor",
                "type at cursor",
            )
        ):
            return "add_text_at_cursor"

        if any(
            phrase in text
            for phrase in (
                "replace content",
                "replace the content",
                "replace document content",
                "replace all content",
            )
        ):
            return "replace_content"

        if any(
            phrase in text
            for phrase in (
                "read document",
                "read the document",
                "read word document",
                "read this document",
            )
        ):
            return "read_document"

        if any(
            phrase in text
            for phrase in (
                "clear document",
                "clear the document",
                "clear document content",
                "clear all document content",
            )
        ):
            return "clear_document"

        # ------------------------------------------------------
        # Select/copy/cut/paste
        # ------------------------------------------------------

        if any(
            phrase in text
            for phrase in (
                "select all in word",
                "select all text in word",
                "select all document text",
                "select all in document",
            )
        ):
            return "select_all"

        if (
            "copy text from document" in text
            or "copy selected text in word" in text
        ):
            return "copy"

        if (
            "cut text from document" in text
            or "cut selected text in word" in text
        ):
            return "cut"

        if (
            "paste into document" in text
            or "paste into word" in text
        ):
            return "paste"

        # ------------------------------------------------------
        # Type/write in Word
        # ------------------------------------------------------

        if text.startswith("type "):
            return "type_text"

        if text.startswith("write "):
            return "type_text"

        # ------------------------------------------------------
        # Formatting
        # ------------------------------------------------------

        if (
            "strikethrough" in text
            or "strike through" in text
            or "strike-through" in text
        ):
            return "strikethrough"

        if (
            "underline" in text
            or "underlined" in text
        ):
            return "underline"

        if (
            "italic" in text
            or "italics" in text
        ):
            return "italic"

        if (
            "bold" in text
            or "make it bold" in text
            or "make this bold" in text
            or "make text bold" in text
            or "bold text" in text
        ):
            return "bold"

        if (
            "font size" in text
            or "text size" in text
        ):
            return "font_size"

        if (
            "change font" in text
            or "set font" in text
            or re.search(r"\bfont\b", text)
        ):
            return "font"

        if (
            "text color" in text
            or "font color" in text
            or "change text colour" in text
            or "font colour" in text
        ):
            return "text_color"

        if (
            "highlight" in text
            or "highlight text" in text
        ):
            return "highlight"

        if (
            "align left" in text
            or "left align" in text
        ):
            return "align_left"

        if (
            "align center" in text
            or "align centre" in text
            or "center align" in text
            or "centre align" in text
        ):
            return "align_center"

        if (
            "align right" in text
            or "right align" in text
        ):
            return "align_right"

        if (
            "justify" in text
            or "justify text" in text
        ):
            return "justify"

        if "line spacing" in text:
            return "line_spacing"

        if "paragraph spacing" in text:
            return "paragraph_spacing"

        if (
            "indentation" in text
            or "indent paragraph" in text
            or "indent the paragraph" in text
        ):
            return "indentation"

        if (
            "bullets" in text
            or "bullet list" in text
            or "make bullets" in text
        ):
            return "bullets"

        if (
            "numbering" in text
            or "numbered list" in text
            or "make numbered list" in text
        ):
            return "numbering"

        # ------------------------------------------------------
        # Styles
        # ------------------------------------------------------

        if (
            text == "title"
            or "apply title style" in text
            or "make it title" in text
            or "make this title" in text
        ):
            return "title"

        if (
            "heading 1" in text
            or "heading one" in text
            or "apply heading 1" in text
            or "make it heading 1" in text
        ):
            return "heading_1"

        if (
            text == "normal"
            or "normal style" in text
            or "apply normal style" in text
        ):
            return "normal"

        if (
            "document style" in text
            or "change document style" in text
        ):
            return "document_style"

        # ------------------------------------------------------
        # Tables
        # ------------------------------------------------------

        if (
            "read table data" in text
            or "read the table" in text
            or "read table" in text
        ):
            return "read_table_data"

        if (
            "create table" in text
            or "insert table" in text
            or "make a table" in text
            or "make table" in text
        ):
            return "create_table"

        if (
            re.search(r"\brows?\b", text)
            and re.search(r"\bcolumns?\b", text)
            and "table" in text
        ):
            return "create_table"

        # ------------------------------------------------------
        # Find / replace
        # ------------------------------------------------------

        if (
            "find and replace" in text
            or "find replace" in text
            or "replace text" in text
            or "replace word" in text
        ):
            return "replace"

        if (
            "find text" in text
            or "find in document" in text
            or "find in word" in text
            or "search document" in text
        ):
            return "find"

        # ------------------------------------------------------
        # Insert
        # ------------------------------------------------------

        if (
            "insert image" in text
            or "add image" in text
            or "insert picture" in text
            or "add picture" in text
        ):
            return "image"

        if (
            "insert hyperlink" in text
            or "add hyperlink" in text
            or "insert link" in text
            or "add link to document" in text
        ):
            return "hyperlink"

        # ------------------------------------------------------
        # Document structure
        # ------------------------------------------------------

        if (
            "page break" in text
            or "insert page break" in text
        ):
            return "page_break"

        if (
            "new page" in text
            or "insert new page" in text
        ):
            return "new_page"

        if (
            "page number" in text
            or "insert page number" in text
            or "add page number" in text
        ):
            return "page_number"

        if (
            "header" in text
            or "insert header" in text
        ):
            return "header"

        if (
            "footer" in text
            or "insert footer" in text
        ):
            return "footer"

        if (
            "margin" in text
            or "margins" in text
            or "set margins" in text
        ):
            return "margins"

        return None

    # ==========================================================
    # LEGACY OFFICE INTENTS
    # ==========================================================

    def _detect_office_intent(
        self,
        text: str,
    ) -> Optional[str]:

        if (
            "excel" in text
            and any(
                phrase in text
                for phrase in (
                    "new workbook",
                    "create workbook",
                    "blank workbook",
                    "new sheet",
                )
            )
        ):
            return "create_excel_workbook"

        if (
            (
                "powerpoint" in text
                or "power point" in text
                or "ppt" in text
            )
            and any(
                phrase in text
                for phrase in (
                    "new presentation",
                    "create presentation",
                    "create ppt",
                    "new ppt",
                    "blank presentation",
                )
            )
        ):
            return "create_powerpoint_presentation"

        return None

    # ==========================================================
    # KEYBOARD / MOUSE
    # ==========================================================

    def _detect_keyboard_mouse_intent(
        self,
        text: str,
    ) -> Optional[str]:

        if "select all" in text:
            return "select_all"

        if text.startswith("press "):

            if "enter" in text:
                return "press_enter"

            if "tab" in text:
                return "press_tab"

            if "space" in text:
                return "space"

            if (
                "escape" in text
                or "esc" in text
            ):
                return "escape"

            if "backspace" in text:
                return "backspace"

            if "delete" in text:
                return "delete"

            if "home" in text:
                return "home"

            if "end" in text:
                return "end"

        if (
            "right click" in text
            or "right-click" in text
        ):
            return "right_click"

        if (
            "double click" in text
            or "double-click" in text
        ):
            return "double_click"

        if "left click" in text:
            return "left_click"

        if "scroll up" in text:
            return "scroll_up"

        if "scroll down" in text:
            return "scroll_down"

        if (
            "window" in text
            and "minimize" in text
        ):
            return "minimize_window"

        if (
            "window" in text
            and "maximize" in text
        ):
            return "maximize_window"

        if (
            "window" in text
            and "restore" in text
        ):
            return "restore_window"

        if (
            "window" in text
            and "close" in text
        ):
            return "close_window"

        if "current window" in text:
            return "close_window"

        # ------------------------------------------------------
        # Clipboard
        # ------------------------------------------------------

        if (
            "copy selected" in text
            or "copy the selected" in text
            or "copy selected text" in text
            or "copy text" in text
            or "copy the text" in text
            or text == "copy"
            or text == "copy it"
        ):
            return "copy"

        if (
            "paste text" in text
            or text == "paste"
            or text == "paste it"
        ):
            return "paste"

        if (
            "cut text" in text
            or text == "cut"
            or text == "cut it"
        ):
            return "cut"

        if text == "undo":
            return "undo"

        if text == "redo":
            return "redo"

        return None

    # ==========================================================
    # CODE AGENT INTENT
    # ==========================================================

    def _detect_code_agent_intent(
        self,
        text: str,
    ) -> Optional[str]:
        """
        Detect explicit Python / Java programming requests.

        Code requests are checked before generic typing, file,
        application, and AI keyword detection so commands such as:

            write a python program for bfs
            create python code for factorial
            generate java program for stack
            implement binary search in java

        are routed to the DHEEPTHI Code Agent instead of being
        interpreted as a normal typing action or ai_chat.

        Questions about programming languages remain ai_chat because
        conversation protection runs before this detector.
        """

        if not text:
            return None

        text = self._basic_normalize(text)

        if not text:
            return None

        # ------------------------------------------------------
        # Programming language must be explicit for V1.
        # ------------------------------------------------------

        has_python = bool(
            re.search(r"\bpython\b|\bpy\b", text)
        )

        has_java = bool(
            re.search(r"\bjava\b", text)
        )

        if not (has_python or has_java):
            return None

        # ------------------------------------------------------
        # Explicit code-generation / implementation language.
        # ------------------------------------------------------

        code_action_patterns = (
            r"\b(write|create|generate|make|implement|develop|build)\b",
            r"\b(code|program|programme|source code|script)\b",
            r"\b(algorithm|data structure)\b.*\b(in|using|with)\b",
            r"\b(in|using|with)\b.*\b(python|py|java)\b",
        )

        has_code_action = any(
            re.search(pattern, text)
            for pattern in code_action_patterns
        )

        if not has_code_action:
            return None

        # ------------------------------------------------------
        # Do not classify explanation / learning questions as
        # executable code requests.
        # ------------------------------------------------------

        if self._is_conversational_message(text):
            return None

        return "code_agent"

    # ==========================================================
    # LOCAL INTENT DETECTION
    # ==========================================================

    def _detect_local_intent(
        self,
        text: str,
    ) -> Optional[str]:

        # ------------------------------------------------------
        # IMPORTANT:
        #
        # Conversation protection happens BEFORE generic
        # keyword detection.
        # ------------------------------------------------------

        if not self._is_explicit_automation_command(text):

            if self._is_conversational_message(text):
                return "ai_chat"

        # ------------------------------------------------------
        # SCREEN CAPTURE / RECORDING FIRST
        #
        # These are direct desktop actions. They MUST be checked
        # before generic application detection because phrases such
        # as:
        #
        #   "start the screen recording"
        #   "start recording"
        #
        # otherwise fall through to the generic "start ->
        # launch_application" rule.
        #
        # Screenshot and recording are also intentionally kept
        # local so Gemini cannot reinterpret them as another intent.
        # ------------------------------------------------------

        intent = self._detect_capture_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Code Agent FIRST
        #
        # Programming requests must be routed before generic
        # "write", "create", "run", and file/application intents.
        # ------------------------------------------------------

        intent = self._detect_code_agent_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Word FIRST
        #
        # Word-specific actions need priority over generic
        # "type", "save", "copy", etc.
        # ------------------------------------------------------

        intent = self._detect_word_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Office legacy
        # ------------------------------------------------------

        intent = self._detect_office_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Folder operations BEFORE generic file operations
        # ------------------------------------------------------

        intent = self._detect_folder_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # File operations
        # ------------------------------------------------------

        intent = self._detect_file_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Archive
        # ------------------------------------------------------

        # Already handled inside file detector.
        # Kept here as an additional safeguard.
        if (
            "extract zip" in text
            or "extract archive" in text
            or "unzip" in text
            or "un zip" in text
        ):
            return "extract_zip"

        if (
            "compress file" in text
            or "create zip" in text
            or "zip this file" in text
            or "archive file" in text
        ):
            return "compress_file"

        # ------------------------------------------------------
        # System
        # ------------------------------------------------------

        intent = self._detect_system_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Browser
        # ------------------------------------------------------

        intent = self._detect_browser_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Search
        # ------------------------------------------------------

        intent = self._detect_search_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Keyboard / mouse
        # ------------------------------------------------------

        intent = self._detect_keyboard_mouse_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Application
        # ------------------------------------------------------

        intent = self._detect_application_intent(text)

        if intent:
            return intent

        # ------------------------------------------------------
        # Generic save / print
        # ------------------------------------------------------

        if "save file" in text:
            return "save_file"

        if "print file" in text:
            return "print_file"

        # ------------------------------------------------------
        # Generic open file
        # ------------------------------------------------------

        if (
            text.startswith("open ")
            and "file" in text
        ):
            return "open_file"

        # ------------------------------------------------------
        # Explicit search
        # ------------------------------------------------------

        if (
            text.startswith("google search")
            or text.startswith("search google")
        ):
            return "google_search"

        # ------------------------------------------------------
        # Generic AI questions
        # ------------------------------------------------------

        question_patterns = (
            "what is",
            "who is",
            "where is",
            "when is",
            "why is",
            "how to",
            "how does",
            "tell me",
            "can you explain",
            "please explain",
            "explain",
            "define",
            "difference between",
            "compare",
            "python pathi",
            "java pathi",
            "ai pathi",
            "machine learning pathi",
            "deep learning pathi",
            "enna",
            "epdi",
            "yen",
        )

        if any(
            pattern in text
            for pattern in question_patterns
        ):
            return "ai_chat"

        # ------------------------------------------------------
        # AI keyword fallback
        # ------------------------------------------------------

        words = set(text.split())

        if words.intersection(
            self.ai_keywords
        ):
            return "ai_chat"

        return None

    # ==========================================================
    # FUZZY INTENT
    # ==========================================================

    def _detect_fuzzy_intent(
        self,
        text: str,
    ) -> Optional[str]:

        if not text:
            return None

        # Exact complete command first.
        if text in self.intent_keywords:
            return self.intent_keywords[text]

        # Word-level exact match.
        for word in text.split():

            if word in self.intent_keywords:
                return self.intent_keywords[word]

        # Full text fuzzy match.
        result = process.extractOne(
            text,
            self.intent_keywords.keys(),
            scorer=fuzz.ratio,
        )

        if result:

            keyword, score, _ = result

            if score >= 92:

                print(
                    "Intent Fuzzy Match : "
                    f"{keyword} ({score:.1f}%)"
                )

                return self.intent_keywords[
                    keyword
                ]

        return None

    # ==========================================================
    # GEMINI SEMANTIC INTENT
    # ==========================================================

    def _build_gemini_intent_prompt(
        self,
        original_text: str,
        normalized_text: str,
    ) -> str:
        """
        Build a strict machine-readable semantic classification
        prompt.

        Gemini receives the supported intent list and is forbidden
        from inventing new intent names.
        """

        supported = sorted(
            self.supported_intents
        )

        intent_list = ", ".join(
            supported
        )

        return f"""
You are the semantic intent classifier for DHEEPTHI-AI.

Your job is ONLY to identify what desktop action or
conversation intent the user means.

Do NOT execute anything.

Do NOT explain anything.

Do NOT generate an action plan.

Return ONLY valid JSON.

Required JSON format:

{{
  "intent": "supported_intent_name",
  "confidence": 0.0,
  "reason": "very short reason"
}}

==================================================
SUPPORTED INTENTS
==================================================

{intent_list}

==================================================
IMPORTANT RULES
==================================================

1. You MUST return exactly one intent from the supported
   intent list.

2. NEVER invent a new intent.

3. If the user is asking a normal question, explanation,
   knowledge request or conversation, return:

   "ai_chat"

4. If the user clearly wants DHEEPTHI-AI to perform an action,
   identify the closest supported executable intent.

5. Understand natural language, Tanglish and casual speech.

6. Understand common speech-to-text mistakes.

7. Do NOT confuse:
   - asking about an action
   with
   - requesting the action.

Example:

"Why should I open Chrome?"
=> ai_chat

"Open Chrome"
=> launch_application

8. Word formatting commands should be mapped to Word intents
   even if the user does not say "Word", when the sentence
   clearly describes an active document operation.

Examples:

"make this bold"
=> bold

"make this italic"
=> italic

"underline this"
=> underline

"change the font size to 18"
=> font_size

9. Do not return an intent merely because a word appears
   inside a question.

10. If confidence is below 0.55, return ai_chat.

==================================================
USER INPUT
==================================================

Original speech:

{original_text}

Normalized speech:

{normalized_text}
"""

    @staticmethod
    def _extract_json_from_response(
        response_text: str,
    ) -> Optional[dict]:
        """
        Safely extract JSON from Gemini output.

        Handles accidental markdown fences as well.
        """

        if not response_text:
            return None

        text = str(
            response_text
        ).strip()

        # Remove markdown JSON fences.
        text = re.sub(
            r"^```(?:json)?",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"```$",
            "",
            text,
        )

        text = text.strip()

        try:
            data = json.loads(text)

            if isinstance(data, dict):
                return data

        except Exception:
            pass

        # Try extracting first JSON object.
        match = re.search(
            r"\{.*\}",
            text,
            flags=re.DOTALL,
        )

        if not match:
            return None

        try:
            data = json.loads(
                match.group(0)
            )

            if isinstance(data, dict):
                return data

        except Exception:
            return None

        return None

    def _validate_gemini_intent(
        self,
        data: Optional[dict],
    ) -> Optional[str]:
        """
        Validate Gemini result before allowing it to influence
        command execution.
        """

        if not isinstance(data, dict):
            return None

        raw_intent = data.get(
            "intent"
        )

        if raw_intent is None:
            return None

        intent = str(
            raw_intent
        ).strip().lower()

        confidence = data.get(
            "confidence",
            0.0,
        )

        try:
            confidence = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = 0.0

        if intent not in self.supported_intents:
            print(
                "Gemini Intent Rejected : "
                f"unsupported intent '{intent}'"
            )
            return None

        if confidence < 0.55:
            print(
                "Gemini Intent Rejected : "
                f"low confidence {confidence:.2f}"
            )
            return None

        print(
            "Gemini Semantic Intent : "
            f"{intent} ({confidence:.2f})"
        )

        return intent

    def _detect_gemini_intent(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Optional[str]:
        """
        Semantic fallback.

        Uses the existing GeminiClient structured JSON method.

        Existing four-key rotation remains inside GeminiClient.
        """

        if not self.enable_gemini_fallback:
            return None

        client = self._get_gemini_client()

        if client is None:
            return None

        prompt = self._build_gemini_intent_prompt(
            original_text=original_text,
            normalized_text=normalized_text,
        )

        try:

            response_text = (
                client.generate_structured_plan(
                    prompt
                )
            )

            if not response_text:
                return None

            data = self._extract_json_from_response(
                response_text
            )

            return self._validate_gemini_intent(
                data
            )

        except Exception as error:

            print(
                "Gemini semantic intent error:",
                error,
            )

            return None

    # ==========================================================
    # MAIN DETECTOR
    # ==========================================================

    def detect_intent(
        self,
        text: str,
    ) -> Optional[str]:
        """
        Detect user intent.

        Strategy
        --------
        Local deterministic logic is always attempted first.

        Gemini is called only when local detection cannot
        confidently identify an intent.

        Returns
        -------
        str | None
        """

        if text is None:
            return None

        original_text = str(
            text
        ).strip()

        if not original_text:
            return None

        if len(
            original_text
        ) <= 1:
            return None

        normalized_text = self._normalize_text(
            original_text
        )

        if not normalized_text:
            return None

        # ==================================================
        # STEP 1
        # DHEEPTHI SCREEN CAPTURE PRIORITY
        # ==================================================
        #
        # Screenshot and screen-recording are direct local desktop
        # actions. They must be resolved before conversation,
        # fuzzy matching, Gemini fallback, or the generic
        # "start -> launch_application" rule.
        #
        # This is especially important for natural commands such as:
        #
        #   start the screen recording
        #   start recording
        #   begin the screen recording
        #   stop recording
        #   take a screenshot of this window
        #
        # The capture detector is deterministic and therefore cannot
        # accidentally be reinterpreted as launch_application or
        # another semantic intent.
        # ==================================================

        capture_intent = self._detect_capture_intent(
            normalized_text
        )

        if capture_intent:
            return capture_intent

        # ==================================================
        # STEP 2
        # Explicit conversation protection
        # ==================================================

        if not self._is_explicit_automation_command(
            normalized_text
        ):

            if self._is_conversational_message(
                normalized_text
            ):
                return "ai_chat"

        # ==================================================
        # STEP 2
        # Local deterministic detection
        # ==================================================

        local_intent = self._detect_local_intent(
            normalized_text
        )

        if local_intent:
            return local_intent

        # ==================================================
        # STEP 3
        # RapidFuzz fallback
        # ==================================================

        fuzzy_intent = self._detect_fuzzy_intent(
            normalized_text
        )

        if fuzzy_intent:

            # --------------------------------------------------
            # Important safety:
            #
            # Fuzzy "open" / "close" etc. should not be enough
            # to execute a completely unrelated command when
            # the utterance is long and ambiguous.
            # --------------------------------------------------

            if (
                fuzzy_intent
                not in {
                    "launch_application",
                    "close_application",
                    "type_text",
                }
                or len(
                    normalized_text.split()
                ) <= 3
            ):
                return fuzzy_intent

        # ==================================================
        # STEP 4
        # Gemini semantic fallback
        # ==================================================

        gemini_intent = self._detect_gemini_intent(
            original_text=original_text,
            normalized_text=normalized_text,
        )

        if gemini_intent:

            return gemini_intent

        # ==================================================
        # STEP 5
        # Final AI conversation fallback
        # ==================================================

        if len(
            normalized_text.split()
        ) >= 2:
            return "ai_chat"

        return None

    # ==========================================================
    # DEBUG / EXPLANATION
    # ==========================================================

    def detect_with_debug(
        self,
        text: str,
    ) -> dict:
        """
        Debug helper.

        Useful during development/testing to understand which
        layer produced the final intent.

        This does not execute any action.
        """

        original_text = str(
            text or ""
        ).strip()

        normalized_text = self._normalize_text(
            original_text
        )

        result = {
            "original_text": original_text,
            "normalized_text": normalized_text,
            "explicit_automation": (
                self._is_explicit_automation_command(
                    normalized_text
                )
                if normalized_text
                else False
            ),
            "local_intent": None,
            "fuzzy_intent": None,
            "gemini_intent": None,
            "intent": None,
        }

        if not normalized_text:
            return result

        result["local_intent"] = (
            self._detect_local_intent(
                normalized_text
            )
        )

        if result["local_intent"]:
            result["intent"] = result[
                "local_intent"
            ]
            return result

        result["fuzzy_intent"] = (
            self._detect_fuzzy_intent(
                normalized_text
            )
        )

        if result["fuzzy_intent"]:
            result["intent"] = result[
                "fuzzy_intent"
            ]
            return result

        result["gemini_intent"] = (
            self._detect_gemini_intent(
                original_text,
                normalized_text,
            )
        )

        if result["gemini_intent"]:
            result["intent"] = result[
                "gemini_intent"
            ]
        else:
            result["intent"] = "ai_chat"

        return result

    # ==========================================================
    # GEMINI STATUS
    # ==========================================================

    def gemini_enabled(self) -> bool:
        """
        Return whether semantic Gemini fallback is enabled.
        """

        return bool(
            self.enable_gemini_fallback
        )

    def has_gemini_client(self) -> bool:
        """
        Return whether a Gemini client is currently available.
        """

        return self.gemini_client is not None

    # ==========================================================
    # CLEANUP
    # ==========================================================

    def close(self):
        """
        Release the detector's Gemini reference.

        If the Gemini client is shared with the application,
        this method does NOT close the shared client.
        """

        self.gemini_client = None
        self._gemini_initialized = False