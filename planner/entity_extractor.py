"""
DHEEPTHI-AI
Entity Extractor - V1

EntityExtractor answers:
    WHAT object/value should the detected intent operate on?

This module is intentionally separate from planner.intent_detector.
It performs deterministic local entity extraction only and never
executes desktop actions.
"""

from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import process, fuzz


class EntityExtractor:
    """
    Advanced V1 entity extractor for DHEEPTHI-AI.

    IntentDetector answers:
        WHAT should DHEEPTHI do?

    EntityExtractor answers:
        WHAT object/value should that action use?

    This implementation is intentionally deterministic and local.
    It understands natural English request wrappers, common STT/Whisper
    variations, application aliases, websites, file queries, transfer
    commands, search constraints, browser/profile values, and screen
    capture actions.

    Important:
        Entity extraction never executes an action.
    """

    def __init__(self):
        self.application_aliases = {
            "google chrome": "chrome",
            "chrome": "chrome",
            "chrome browser": "chrome",
            "the chrome browser": "chrome",
            "microsoft edge": "msedge",
            "ms edge": "msedge",
            "edge browser": "msedge",
            "edge": "msedge",
            "firefox browser": "firefox",
            "firefox": "firefox",
            "mozilla firefox": "firefox",
            "notepad": "notepad",
            "note pad": "notepad",
            "node pad": "notepad",
            "windows notepad": "notepad",
            "paint": "mspaint",
            "microsoft paint": "mspaint",
            "paint app": "mspaint",
            "calculator": "calc",
            "calculator app": "calc",
            "calc": "calc",
            "command prompt": "cmd",
            "cmd": "cmd",
            "windows command prompt": "cmd",
            "powershell": "powershell",
            "power shell": "powershell",
            "windows powershell": "powershell",
            "explorer": "explorer",
            "file explorer": "explorer",
            "windows explorer": "explorer",
            "word": "winword",
            "ms word": "winword",
            "microsoft word": "winword",
            "word application": "winword",
            "word app": "winword",
            "excel": "excel",
            "ms excel": "excel",
            "microsoft excel": "excel",
            "excel application": "excel",
            "powerpoint": "powerpnt",
            "power point": "powerpnt",
            "microsoft powerpoint": "powerpnt",
            "ppt": "powerpnt",
            "ppt app": "powerpnt",
            "visual studio code": "code",
            "vs code": "code",
            "vscode": "code",
            "visual studio": "code",
            "pycharm": "pycharm64",
            "pycharm community": "pycharm64",
            "pycharm professional": "pycharm64",
        }

        self.browser_aliases = {
            "google chrome": "chrome",
            "chrome browser": "chrome",
            "chrome": "chrome",
            "microsoft edge": "edge",
            "ms edge": "edge",
            "edge browser": "edge",
            "edge": "edge",
            "mozilla firefox": "firefox",
            "firefox browser": "firefox",
            "firefox": "firefox",
        }

        self.website_aliases = {
            "google": "google.com",
            "google search": "google.com",
            "youtube": "youtube.com",
            "gmail": "gmail.com",
            "google mail": "gmail.com",
            "github": "github.com",
            "stackoverflow": "stackoverflow.com",
            "stack overflow": "stackoverflow.com",
            "chatgpt": "chatgpt.com",
            "chat gpt": "chatgpt.com",
            "wikipedia": "wikipedia.org",
            "amazon": "amazon.in",
            "amazon india": "amazon.in",
            "flipkart": "flipkart.com",
            "linkedin": "linkedin.com",
            "instagram": "instagram.com",
            "facebook": "facebook.com",
            "twitter": "x.com",
        }

        self.folder_aliases = {
            "desktop": "Desktop",
            "my desktop": "Desktop",
            "the desktop": "Desktop",
            "documents": "Documents",
            "my documents": "Documents",
            "the documents folder": "Documents",
            "downloads": "Downloads",
            "my downloads": "Downloads",
            "the downloads folder": "Downloads",
            "pictures": "Pictures",
            "photos": "Pictures",
            "my pictures": "Pictures",
            "videos": "Videos",
            "my videos": "Videos",
            "music": "Music",
            "my music": "Music",
            "this pc": "This PC",
            "my computer": "This PC",
            "computer": "This PC",
            "recycle bin": "Recycle Bin",
            "trash": "Recycle Bin",
            "c drive": "C:",
            "c:": "C:",
            "d drive": "D:",
            "d:": "D:",
            "e drive": "E:",
            "e:": "E:",
        }

        self.extension_aliases = {
            "pdf": ".pdf",
            "pdf file": ".pdf",
            "pdf files": ".pdf",
            "portable document": ".pdf",
            "portable document format": ".pdf",
            "doc": ".doc",
            "doc file": ".doc",
            "doc files": ".doc",
            "docx": ".docx",
            "docx file": ".docx",
            "docx files": ".docx",
            "word": ".docx",
            "word file": ".docx",
            "word files": ".docx",
            "word document": ".docx",
            "word documents": ".docx",
            "text": ".txt",
            "txt": ".txt",
            "text file": ".txt",
            "text files": ".txt",
            "plain text": ".txt",
            "ppt": ".ppt",
            "ppt file": ".ppt",
            "ppt files": ".ppt",
            "pptx": ".pptx",
            "pptx file": ".pptx",
            "pptx files": ".pptx",
            "powerpoint": ".pptx",
            "powerpoint file": ".pptx",
            "powerpoint files": ".pptx",
            "presentation": ".pptx",
            "presentations": ".pptx",
            "xls": ".xls",
            "xls file": ".xls",
            "xlsx": ".xlsx",
            "xlsx file": ".xlsx",
            "excel": ".xlsx",
            "excel file": ".xlsx",
            "excel files": ".xlsx",
            "spreadsheet": ".xlsx",
            "spreadsheets": ".xlsx",
            "csv": ".csv",
            "csv file": ".csv",
            "csv files": ".csv",
            "jpg": ".jpg",
            "jpeg": ".jpeg",
            "png": ".png",
            "gif": ".gif",
            "image": ".png",
            "images": ".png",
            "image file": ".png",
            "photo": ".jpg",
            "photos": ".jpg",
            "mp3": ".mp3",
            "wav": ".wav",
            "audio": ".mp3",
            "audio file": ".mp3",
            "audio files": ".mp3",
            "mp4": ".mp4",
            "mkv": ".mkv",
            "avi": ".avi",
            "video": ".mp4",
            "videos": ".mp4",
            "video file": ".mp4",
            "video files": ".mp4",
            "zip": ".zip",
            "archive": ".zip",
            "python": ".py",
            "python file": ".py",
            "python files": ".py",
            "py": ".py",
            "javascript": ".js",
            "javascript file": ".js",
            "javascript files": ".js",
            "js": ".js",
            "typescript": ".ts",
            "typescript file": ".ts",
            "typescript files": ".ts",
            "ts": ".ts",
            "java": ".java",
            "java file": ".java",
            "java files": ".java",
            "c plus plus": ".cpp",
            "c++": ".cpp",
            "cpp": ".cpp",
            "cpp file": ".cpp",
            "cpp files": ".cpp",
            "c sharp": ".cs",
            "c#": ".cs",
            "cs": ".cs",
            "html": ".html",
            "html file": ".html",
            "css": ".css",
            "css file": ".css",
            "sql": ".sql",
            "sql file": ".sql",
        }

        self._known_extensions = {
            ".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx",
            ".xls", ".xlsx", ".csv", ".jpg", ".jpeg", ".png",
            ".gif", ".mp3", ".wav", ".mp4", ".mkv", ".avi",
            ".zip", ".py", ".js", ".ts", ".java", ".cpp", ".cs",
            ".html", ".css", ".sql",
        }

    # ==========================================================
    # NATURAL ENGLISH NORMALIZATION
    # ==========================================================

    @staticmethod
    def _strip_english_command_wrappers(value: str) -> str:
        """
        Convert polite/casual English requests into their command core.

        Examples:
            "can you please open Chrome"
                -> "open chrome"

            "would you mind taking a screenshot for me"
                -> "take a screenshot"

            "I want you to search YouTube for Python"
                -> "search youtube for python"

            "I'd like you to move the file to Desktop"
                -> "move the file to desktop"

        The old implementation contained the dangerous replacement
        "you to" -> "youtube".  That is deliberately NOT used here.
        """

        value = value.strip()
        if not value:
            return value

        # Normalize common contractions before wrapper matching.
        contractions = (
            (r"\bi'd\b", "i would"),
            (r"\bi'll\b", "i will"),
            (r"\bi've\b", "i have"),
            (r"\bi'm\b", "i am"),
            (r"\byou're\b", "you are"),
            (r"\bwe're\b", "we are"),
            (r"\bcan't\b", "cannot"),
            (r"\bwon't\b", "will not"),
        )
        for pattern, replacement in contractions:
            value = re.sub(pattern, replacement, value)

        # Longest/specific wrappers first.
        wrappers = (
            r"^i\s+would\s+like\s+you\s+to\s+",
            r"^i\s+would\s+love\s+you\s+to\s+",
            r"^i\s+need\s+you\s+to\s+",
            r"^i\s+want\s+you\s+to\s+",
            r"^i\s+would\s+like\s+to\s+",
            r"^i\s+would\s+love\s+to\s+",
            r"^i\s+need\s+to\s+",
            r"^i\s+want\s+to\s+",
            r"^would\s+you\s+mind\s+",
            r"^would\s+you\s+be\s+able\s+to\s+",
            r"^could\s+you\s+possibly\s+",
            r"^could\s+you\s+maybe\s+",
            r"^could\s+you\s+please\s+",
            r"^could\s+you\s+",
            r"^can\s+you\s+possibly\s+",
            r"^can\s+you\s+maybe\s+",
            r"^can\s+you\s+please\s+",
            r"^can\s+you\s+",
            r"^would\s+you\s+please\s+",
            r"^would\s+you\s+",
            r"^will\s+you\s+please\s+",
            r"^will\s+you\s+",
            r"^please\s+can\s+you\s+",
            r"^please\s+could\s+you\s+",
            r"^please\s+would\s+you\s+",
            r"^please\s+",
            r"^kindly\s+",
            r"^if\s+you\s+could\s+",
            r"^if\s+you\s+would\s+",
            r"^when\s+you\s+can\s+",
            r"^help\s+me\s+to\s+",
            r"^help\s+me\s+",
            r"^go\s+ahead\s+and\s+",
            r"^just\s+",
        )

        # A wrapper can itself contain another polite wrapper.
        for _ in range(7):
            changed = False
            for pattern in wrappers:
                updated = re.sub(
                    pattern,
                    "",
                    value,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if updated != value:
                    value = updated.strip()
                    changed = True
                    break
            if not changed:
                break

        # Natural gerunds commonly produced by speech:
        # "opening Chrome", "taking a screenshot", etc.
        gerund_roots = (
            ("opening", "open"),
            ("launching", "launch"),
            ("starting", "start"),
            ("running", "run"),
            ("executing", "execute"),
            ("closing", "close"),
            ("exiting", "exit"),
            ("quitting", "quit"),
            ("terminating", "terminate"),
            ("typing", "type"),
            ("writing", "write"),
            ("copying", "copy"),
            ("pasting", "paste"),
            ("cutting", "cut"),
            ("clicking", "click"),
            ("double-clicking", "double click"),
            ("scrolling", "scroll"),
            ("minimizing", "minimize"),
            ("maximizing", "maximize"),
            ("restoring", "restore"),
            ("taking", "take"),
            ("capturing", "capture"),
            ("recording", "record"),
            ("stopping", "stop"),
            ("pressing", "press"),
            ("selecting", "select"),
            ("saving", "save"),
            ("printing", "print"),
            ("searching", "search"),
            ("playing", "play"),
            ("bookmarking", "bookmark"),
            ("refreshing", "refresh"),
            ("reloading", "reload"),
            ("creating", "create"),
            ("making", "make"),
            ("deleting", "delete"),
            ("removing", "remove"),
            ("renaming", "rename"),
            ("moving", "move"),
            ("compressing", "compress"),
            ("extracting", "extract"),
            ("unpacking", "unpack"),
            ("inserting", "insert"),
            ("replacing", "replace"),
            ("clearing", "clear"),
            ("applying", "apply"),
            ("changing", "change"),
            ("increasing", "increase"),
            ("decreasing", "decrease"),
            ("raising", "raise"),
            ("lowering", "lower"),
            ("muting", "mute"),
            ("locking", "lock"),
            ("shutting", "shut"),
        )
        for gerund, root in gerund_roots:
            value = re.sub(
                rf"^{re.escape(gerund)}\b",
                root,
                value,
                count=1,
                flags=re.IGNORECASE,
            )

        # Remove common polite tails without eating meaningful entities.
        value = re.sub(
            r"\s+(?:please|kindly|now|for\s+me|for\s+me\s+please)$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        # Natural "up" variants:
        # "open up Chrome", "bring up Chrome", "fire up Chrome".
        value = re.sub(
            r"^(?:bring|fire|pull)\s+up\s+",
            "open ",
            value,
            count=1,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"^open\s+up\s+",
            "open ",
            value,
            count=1,
            flags=re.IGNORECASE,
        )

        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _normalize(text: str) -> str:
        if text is None:
            return ""

        value = str(text).lower().strip()
        if not value:
            return ""

        # Preserve meaningful punctuation used by filenames, domains and
        # Windows paths (report.pdf, github.com, C:\Users\..., etc.).
        # Only remove punctuation when it is clearly sentence-level noise.
        value = re.sub(r"[!?]+", " ", value)
        value = re.sub(r"^[,;:]+|[,;:]+$", " ", value)
        value = re.sub(r"\s+", " ", value).strip()

        value = EntityExtractor._strip_english_command_wrappers(value)

        # Common STT / Whisper variants.
        replacements = (
            ("you tube", "youtube"),
            ("u tube", "youtube"),
            ("utube", "youtube"),
            ("you too", "youtube"),
            ("g mail", "gmail"),
            ("google mail", "gmail"),
            ("power point presentation", "powerpoint"),
            ("power point", "powerpoint"),
            ("note pad", "notepad"),
            ("node pad", "notepad"),
            ("fire fox", "firefox"),
            ("visual studio code", "vscode"),
            ("vs code", "vscode"),
            ("command promt", "command prompt"),
            ("command promptt", "command prompt"),
            ("power shell", "powershell"),
            ("microsoft word", "word"),
            ("ms word", "word"),
            ("m s word", "word"),
            ("microsoft excel", "excel"),
            ("ms excel", "excel"),
            ("m s excel", "excel"),
            ("microsoft edge", "edge"),
            ("ms edge", "edge"),
            ("google chrome browser", "chrome"),
            ("chrome browser", "chrome"),
            ("c plus plus", "c++"),
            ("c sharp", "c#"),
        )
        for old, new in replacements:
            # Word/phrase boundaries prevent "utube" from matching the
            # substring inside the already-correct word "youtube".
            value = re.sub(
                rf"(?<!\w){re.escape(old)}(?!\w)",
                new,
                value,
            )

        # Tanglish command normalization. Longest phrases first.
        tanglish = (
            ("open pannu", "open"),
            ("close pannu", "close"),
            ("start pannu", "start"),
            ("stop pannu", "stop"),
            ("copy pannu", "copy"),
            ("paste pannu", "paste"),
            ("screenshot edu", "take screenshot"),
            ("photo edu", "take photo"),
            ("thorakka", "open"),
            ("thorak", "open"),
            ("thirakka", "open"),
            ("thirak", "open"),
            ("moodu", "close"),
            ("mudu", "close"),
            ("theda", "search"),
            ("thedu", "search"),
            ("thedi", "search"),
            ("uruvakku", "create"),
            ("uruvaku", "create"),
            ("azhichidu", "delete"),
            ("azhichu", "delete"),
            ("maathu", "rename"),
            ("mathu", "rename"),
            ("nagarthu", "move"),
            ("kaatu", "show"),
            ("podu", "play"),
        )
        for old, new in sorted(
            tanglish,
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            value = value.replace(old, new)

        return re.sub(r"\s+", " ", value).strip()

    # ==========================================================
    # HELPERS
    # ==========================================================

    @staticmethod
    def _remove_prefixes(text: str, prefixes) -> str:
        """Backward-compatible helper for prefix stripping."""
        value = (text or "").strip()
        changed = True
        while changed:
            changed = False
            for prefix in sorted(prefixes, key=len, reverse=True):
                if value.startswith(prefix):
                    value = value[len(prefix):].strip()
                    changed = True
                    break
        return value

    @staticmethod
    def _clean_entity(value: Optional[str]):
        if value is None:
            return None
        value = str(value).strip()
        value = value.strip("\"'`.,;:!? ")
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    @staticmethod
    def _remove_leading_articles(value: str) -> str:
        return re.sub(
            r"^(?:the|a|an)\s+",
            "",
            value.strip(),
            count=1,
            flags=re.IGNORECASE,
        ).strip()

    @staticmethod
    def _remove_command_prefix(value: str) -> str:
        return re.sub(
            r"^(?:open|launch|start|run|execute|close|exit|quit|terminate|"
            r"create|make|new|delete|remove|rename|move|copy|compress|zip|"
            r"archive|extract|unzip|search|find|show|list|locate|play|"
            r"visit|go\s+to|navigate\s+to)\s+",
            "",
            value.strip(),
            count=1,
            flags=re.IGNORECASE,
        ).strip()

    @staticmethod
    def _normalize_spoken_number(value: str):
        words = {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
            "thirteen": 13,
            "fourteen": 14,
            "fifteen": 15,
            "sixteen": 16,
            "seventeen": 17,
            "eighteen": 18,
            "nineteen": 19,
            "twenty": 20,
            "thirty": 30,
            "forty": 40,
            "fifty": 50,
            "sixty": 60,
            "seventy": 70,
            "eighty": 80,
            "ninety": 90,
            "hundred": 100,
        }
        if value in words:
            return words[value]
        if value.isdigit():
            return int(value)
        return None

    # ==========================================================
    # PERCENTAGE / NUMERIC VALUE
    # ==========================================================

    def extract_percentage(self, text: str) -> Optional[int]:
        value = self._normalize(text)
        if not value:
            return None

        match = re.search(r"\b(\d{1,3})\s*%", value)
        if not match:
            match = re.search(r"\b(\d{1,3})\s*percent\b", value)
        if not match:
            match = re.search(
                r"\b(?:to|at|level)\s+(\d{1,3})\b",
                value,
            )
        if match:
            number = int(match.group(1))
            return max(0, min(100, number))

        spoken = re.search(
            r"\b(?:to|at|level)\s+"
            r"(zero|one|two|three|four|five|six|seven|eight|nine|"
            r"ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b",
            value,
        )
        if spoken:
            number = self._normalize_spoken_number(spoken.group(1))
            if number is not None:
                return max(0, min(100, number))

        # Only infer a bare number for brightness/volume style commands.
        if any(
            term in value
            for term in ("brightness", "volume")
        ):
            numbers = re.findall(r"\b\d{1,3}\b", value)
            if numbers:
                return max(0, min(100, int(numbers[-1])))

        return None

    # ==========================================================
    # APPLICATION
    # ==========================================================

    def extract_application(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        aliases = sorted(
            self.application_aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        # Exact alias anywhere in the normalized command.
        for name, executable in aliases:
            if re.search(
                rf"\b{re.escape(name)}\b",
                value,
            ):
                return executable

        candidate = self._remove_command_prefix(value)
        candidate = self._remove_leading_articles(candidate)

        # "the browser called Chrome", "app called Calculator".
        named = re.search(
            r"\b(?:called|named)\s+(.+?)(?:\s+app|\s+application)?$",
            candidate,
            re.IGNORECASE,
        )
        if named:
            candidate = named.group(1).strip()

        for name, executable in aliases:
            if candidate == name:
                return executable

        # Natural variants.
        candidate = re.sub(
            r"^(?:up|the)\s+",
            "",
            candidate,
            count=1,
        ).strip()

        for name, executable in aliases:
            if candidate == name:
                return executable

        # Fuzzy matching only for a short application-like candidate.
        if len(candidate.split()) <= 5:
            names = list(self.application_aliases.keys())
            result = process.extractOne(
                candidate,
                names,
                scorer=fuzz.ratio,
            )
            if result:
                name, score, _ = result
                if score >= 90:
                    return self.application_aliases[name]

        return None

    # ==========================================================
    # FILE QUERY / FILE NAME
    # ==========================================================

    def extract_file_query(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        # Explicit quoted filename/path.
        quoted = re.search(
            r"""["']([^"']+)["']""",
            value,
        )
        if quoted and (
            "." in quoted.group(1)
            or "\\" in quoted.group(1)
            or "/" in quoted.group(1)
        ):
            return self._clean_entity(quoted.group(1))

        # Windows path.
        windows_path = re.search(
            r"\b[A-Za-z]:\\[^ ]+",
            value,
        )
        if windows_path:
            return self._clean_entity(windows_path.group(0))

        # A filename with a known extension.
        filename = re.search(
            r"\b[\w .()_-]+\.(?:pdf|doc|docx|txt|ppt|pptx|xls|xlsx|csv|"
            r"jpg|jpeg|png|gif|mp3|wav|mp4|mkv|avi|zip|py|js|ts|java|"
            r"cpp|cs|html|css|sql)\b",
            value,
            re.IGNORECASE,
        )
        if filename:
            return self._clean_entity(filename.group(0))

        patterns = (
            r"^(?:open|create|make|new|delete|remove)\s+"
            r"(?:the\s+)?file\s+(.+)$",
            r"^(?:open|create|make|new|delete|remove)\s+"
            r"(?:the\s+)?document\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                return self._clean_entity(match.group(1))

        # Website/navigation requests are not file requests.
        if re.match(
            r"^(?:visit|go\s+to|navigate\s+to|open\s+(?:website|site|url))\b",
            value,
            re.IGNORECASE,
        ):
            return None

        # Search requests are handled by the dedicated search extractors.
        # Do not accidentally expose "for large files" or "python files"
        # as a filename entity here.
        if re.match(
            r"^(?:find|search|show|list|locate)\b",
            value,
            re.IGNORECASE,
        ):
            return None

        # "open report" / "delete report.pdf" are file-like requests.
        candidate = self._remove_command_prefix(value)
        candidate = self._remove_leading_articles(candidate)
        if candidate and (
            "." in candidate
            or "file" in value
            or "document" in value
        ):
            candidate = re.sub(
                r"\s+(?:please|for me|now)$",
                "",
                candidate,
                flags=re.IGNORECASE,
            )
            return self._clean_entity(candidate)

        return None

    # ==========================================================
    # COMPRESS / ZIP
    # ==========================================================

    def extract_compress_file(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        patterns = (
            r"^(?:compress|zip|archive)\s+"
            r"(?:the\s+)?(?:file\s+)?(.+)$",
            r"^(?:create|make)\s+(?:a\s+)?zip\s+"
            r"(?:of\s+)?(.+)$",
            r"^(?:compress|zip|archive)\s+(?:this|that)\s+"
            r"(?:file|folder)$",
        )
        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                entity = self._clean_entity(match.group(1))
                if entity:
                    return entity

        return self.extract_file_query(value)

    def extract_extract_zip(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        patterns = (
            r"^(?:extract|unzip|unpack)\s+"
            r"(?:the\s+)?(?:zip|archive|file)?\s*(.+)$",
            r"^open\s+zip\s+(.+)$",
            r"^open\s+(.+\.zip)$",
        )
        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                entity = self._clean_entity(match.group(1))
                if entity:
                    return entity

        match = re.search(
            r"\b[\w .()_-]+\.zip\b",
            value,
            re.IGNORECASE,
        )
        if match:
            return self._clean_entity(match.group(0))

        return None

    # ==========================================================
    # TRANSFER PARSING
    # ==========================================================

    @staticmethod
    def _extract_transfer_parts(
        value: str,
        operation: str,
        item_word: str,
    ):
        """
        Return source/destination for natural transfer phrases.

        Supports:
            copy report from Downloads to Desktop
            copy the file from Downloads into Desktop
            move report to Desktop
            move report into Documents
            rename report as final_report
        """

        working = value.strip()

        working = re.sub(
            rf"^{re.escape(operation)}\b\s*",
            "",
            working,
            count=1,
            flags=re.IGNORECASE,
        )
        working = re.sub(
            rf"^(?:the|a|an)\s+",
            "",
            working,
            count=1,
            flags=re.IGNORECASE,
        )
        working = re.sub(
            rf"^{re.escape(item_word)}\b\s+",
            "",
            working,
            count=1,
            flags=re.IGNORECASE,
        )
        working = re.sub(
            rf"^(?:the|a|an)\s+",
            "",
            working,
            count=1,
            flags=re.IGNORECASE,
        ).strip()

        # "from X to Y" without an explicit filename.
        match = re.search(
            r"^from\s+(.+?)\s+(?:to|into)\s+(.+)$",
            working,
            re.IGNORECASE,
        )
        if match:
            return {
                "source": EntityExtractor._clean_entity(match.group(1)),
                "destination": EntityExtractor._clean_entity(match.group(2)),
            }

        # "report from X to Y".
        match = re.search(
            r"^(.+?)\s+from\s+(.+?)\s+(?:to|into)\s+(.+)$",
            working,
            re.IGNORECASE,
        )
        if match:
            return {
                "item": EntityExtractor._clean_entity(match.group(1)),
                "source": EntityExtractor._clean_entity(match.group(2)),
                "destination": EntityExtractor._clean_entity(match.group(3)),
            }

        # "report to Desktop" / "report into Desktop".
        match = re.search(
            r"^(.+?)\s+(?:to|into|toward|towards|2|ku|kku)\s+(.+)$",
            working,
            re.IGNORECASE,
        )
        if match:
            return {
                "source": EntityExtractor._clean_entity(match.group(1)),
                "destination": EntityExtractor._clean_entity(match.group(2)),
            }

        # Rename is naturally expressed with "as".
        match = re.search(
            r"^(.+?)\s+(?:as|to)\s+(.+)$",
            working,
            re.IGNORECASE,
        )
        if match:
            return {
                "source": EntityExtractor._clean_entity(match.group(1)),
                "destination": EntityExtractor._clean_entity(match.group(2)),
            }

        return EntityExtractor._clean_entity(working)

    def _extract_transfer(self, text: str, operation: str, item_word: str):
        value = self._normalize(text)
        if not value:
            return None

        # Never let extract_copy_file()/extract_move_file()/extract_rename_file()
        # return an entity for a different operation. This matters when
        # extract_all() is used for diagnostics.
        operation_pattern = rf"^(?:{re.escape(operation)})\b"
        if not re.search(operation_pattern, value, re.IGNORECASE):
            return None

        return self._extract_transfer_parts(
            value,
            operation,
            item_word,
        )

    def extract_rename_file(self, text: str):
        return self._extract_transfer(text, "rename", "file")

    def extract_copy_file(self, text: str):
        return self._extract_transfer(text, "copy", "file")

    def extract_move_file(self, text: str):
        return self._extract_transfer(text, "move", "file")

    # ==========================================================
    # SEARCH EXTENSION
    # ==========================================================

    def extract_search_extension(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        # YouTube media search is not local file-extension search.
        if "youtube" in value and not re.search(
            r"\b(?:file|files|extension|extensions)\b",
            value,
        ):
            return None

        # Explicit ".py", ".pdf", etc.
        match = re.search(
            r"(?<![\w])\.([a-z0-9]{1,12})\b",
            value,
            re.IGNORECASE,
        )
        if match:
            extension = "." + match.group(1).lower()
            if extension in self._known_extensions:
                return extension

        # "py extension", "extension py", "python extension".
        match = re.search(
            r"\b([a-z0-9+#]{1,12})\s+extension\b",
            value,
            re.IGNORECASE,
        )
        if match:
            token = match.group(1).lower()
            if token in self.extension_aliases:
                return self.extension_aliases[token]
            if "." + token in self._known_extensions:
                return "." + token

        match = re.search(
            r"\bextension\s+([a-z0-9+#]{1,12})\b",
            value,
            re.IGNORECASE,
        )
        if match:
            token = match.group(1).lower()
            if token in self.extension_aliases:
                return self.extension_aliases[token]
            if "." + token in self._known_extensions:
                return "." + token

        # Semantic types. Longest aliases first to avoid "word" beating
        # "word files" in future additions.
        for alias, extension in sorted(
            self.extension_aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if re.search(
                rf"(?<!\w){re.escape(alias)}(?!\w)",
                value,
                re.IGNORECASE,
            ):
                # Only classify semantic aliases as a file search when
                # the command actually looks like a search/list request,
                # unless an explicit extension phrase was used.
                if any(
                    token in value
                    for token in (
                        "find", "search", "show", "list", "locate",
                        "files", "file", "extension", "extensions",
                    )
                ):
                    return extension

        return None

    # ==========================================================
    # SEARCH SIZE
    # ==========================================================

    def extract_search_size(self, text: str):
        value = self._normalize(text)
        if not value:
            return None

        operator = None

        if any(
            phrase in value
            for phrase in (
                "larger than", "bigger than", "greater than",
                "above", "over", "more than", "at least",
            )
        ):
            operator = "greater_than"
        elif any(
            phrase in value
            for phrase in (
                "smaller than", "less than", "under",
                "below", "lesser than", "at most",
            )
        ):
            operator = "less_than"
        elif any(
            phrase in value
            for phrase in (
                "equal to", "exactly", "same size as",
            )
        ):
            operator = "equal"

        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*"
            r"(bytes?|kb|kib|mb|mib|gb|gib|tb|tib)\b",
            value,
            re.IGNORECASE,
        )
        if match:
            number = float(match.group(1))
            if number.is_integer():
                number = int(number)

            unit = match.group(2).upper()
            if unit == "BYTES":
                unit = "BYTES"

            return {
                "operator": operator or "greater_than",
                "value": number,
                "unit": unit,
            }

        # Spoken/simple semantic sizes.
        semantic = re.search(
            r"\b(large|larger|big|bigger|huge|massive|"
            r"small|smaller|tiny)\s+files?\b",
            value,
            re.IGNORECASE,
        )
        if semantic:
            word = semantic.group(1).lower()
            return {
                "operator": (
                    "less_than"
                    if word in {"small", "smaller", "tiny"}
                    else "greater_than"
                ),
                "value": None,
                "unit": None,
                "semantic": word,
            }

        return None

    # ==========================================================
    # SEARCH DATE
    # ==========================================================

    def extract_search_date(self, text: str):
        value = self._normalize(text)
        if not value:
            return None

        periods = (
            "today",
            "yesterday",
            "tomorrow",
            "last week",
            "last month",
            "this week",
            "this month",
            "this year",
            "last year",
            "recent",
            "recently",
            "earlier today",
            "earlier this week",
            "past week",
            "past month",
            "this morning",
            "yesterday morning",
        )

        for period in periods:
            if period in value:
                return {"period": period}

        date_action = re.search(
            r"\b(?:created|modified|changed|updated|accessed|"
            r"downloaded|saved)\s+"
            r"(today|yesterday|tomorrow|recently|last week|last month|"
            r"this week|this month)\b",
            value,
            re.IGNORECASE,
        )
        if date_action:
            return {
                "period": date_action.group(1).lower(),
                "operation": date_action.group(0).split()[0].lower(),
            }

        # "on 2026-09-16" / "created on 2026-09-16".
        match = re.search(
            r"\b(\d{4}-\d{2}-\d{2})\b",
            value,
        )
        if match:
            return {"date": match.group(1)}

        # Common dd/mm/yyyy and dd-mm-yyyy forms.
        match = re.search(
            r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
            value,
        )
        if match:
            return {
                "date": (
                    f"{int(match.group(1)):02d}-"
                    f"{int(match.group(2)):02d}-"
                    f"{match.group(3)}"
                ),
            }

        return None

    # ==========================================================
    # WEBSITE
    # ==========================================================

    def extract_website(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        url = re.search(
            r"(?:https?://|www\.)[^\s]+",
            value,
            re.IGNORECASE,
        )
        if url:
            return self._clean_entity(url.group(0))

        # Bare domain.
        domain = re.search(
            r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b",
            value,
            re.IGNORECASE,
        )
        if domain:
            candidate = domain.group(0).lower()
            if any(
                candidate.endswith(tld)
                for tld in (
                    ".com", ".in", ".org", ".net", ".io",
                    ".ai", ".dev", ".co", ".app",
                )
            ):
                return candidate

        for name, site in sorted(
            self.website_aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if re.search(
                rf"(?<!\w){re.escape(name)}(?!\w)",
                value,
                re.IGNORECASE,
            ):
                return site

        return None

    # ==========================================================
    # GOOGLE SEARCH
    # ==========================================================

    def extract_search_query(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        # Do not turn a pure YouTube request into Google query.
        patterns = (
            r"^(?:google\s+search)\s+(?:for\s+)?(.+)$",
            r"^(?:search\s+google)\s+(?:for\s+)?(.+)$",
            r"^(?:search\s+on\s+google)\s+(?:for\s+)?(.+)$",
            r"^(?:search)\s+(?:for\s+)?(.+)$",
            r"^(?:google)\s+(?:search\s+for\s+)?(.+)$",
        )

        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                query = self._clean_entity(match.group(1))
                if query and query not in {"google", "youtube"}:
                    return query

        return None

    # ==========================================================
    # YOUTUBE QUERY
    # ==========================================================

    def extract_youtube_query(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        patterns = (
            r"^youtube\s+search\s+(?:for\s+)?(.+)$",
            r"^search\s+youtube\s+(?:for\s+)?(.+)$",
            r"^search\s+on\s+youtube\s+(?:for\s+)?(.+)$",
            r"^find\s+(?:on\s+)?youtube\s+(?:for\s+)?(.+)$",
            r"^look\s+up\s+(?:on\s+)?youtube\s+(?:for\s+)?(.+)$",
            r"^play\s+(.+?)\s+on\s+youtube$",
            r"^play\s+(?:a\s+)?song\s+(.+)$",
            r"^play\s+(?:some\s+)?music\s+(.+)$",
            r"^play\s+(?:a\s+)?video\s+(.+)$",
            r"^youtube\s+(.+)$",
            r"^play\s+(.+)$",
        )

        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                query = self._clean_entity(match.group(1))
                if query and query not in {"youtube", "search"}:
                    return query

        return None

    # ==========================================================
    # FOLDER
    # ==========================================================

    def extract_folder(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        for alias, folder in sorted(
            self.folder_aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if re.search(
                rf"(?<!\w){re.escape(alias)}(?!\w)",
                value,
                re.IGNORECASE,
            ):
                return folder

        patterns = (
            r"^(?:open|create|make|new|delete|remove)\s+"
            r"(?:the\s+)?folder\s+(.+)$",
            r"^(?:open|create|make|new|delete|remove)\s+"
            r"(.+?)\s+folder$",
            r"^folder\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                entity = self._clean_entity(match.group(1))
                if entity:
                    return entity

        return None

    def extract_rename_folder(self, text: str):
        return self._extract_transfer(text, "rename", "folder")

    def extract_copy_folder(self, text: str):
        return self._extract_transfer(text, "copy", "folder")

    def extract_move_folder(self, text: str):
        return self._extract_transfer(text, "move", "folder")

    # ==========================================================
    # BROWSER
    # ==========================================================

    def extract_browser(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        for alias, browser in sorted(
            self.browser_aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if re.search(
                rf"(?<!\w){re.escape(alias)}(?!\w)",
                value,
                re.IGNORECASE,
            ):
                return browser

        if self.extract_website(value):
            return "chrome"

        return None

    # ==========================================================
    # CHROME PROFILE
    # ==========================================================

    def extract_profile(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        match = re.search(
            r"\bprofile\s+(?:number\s+)?(\d+)\b",
            value,
            re.IGNORECASE,
        )
        if match:
            return f"Profile {match.group(1)}"

        for phrase, result in (
            ("default profile", "Default"),
            ("guest profile", "Guest Profile"),
        ):
            if phrase in value:
                return result

        match = re.search(
            r"\bprofile\s+(?:named\s+|called\s+)?([a-z][a-z0-9 _-]*)$",
            value,
            re.IGNORECASE,
        )
        if match:
            return self._clean_entity(match.group(1))

        return None

    # ==========================================================
    # SCREENSHOT / RECORDING
    # ==========================================================

    def extract_capture_action(self, text: str) -> Optional[str]:
        value = self._normalize(text)
        if not value:
            return None

        # Stop must be checked before start because "stop recording"
        # contains the generic word "recording".
        stop_patterns = (
            "stop screen recording",
            "stop screen record",
            "stop recording the screen",
            "stop recording screen",
            "stop my screen recording",
            "stop my screen record",
            "end screen recording",
            "end screen record",
            "finish screen recording",
            "finish screen record",
            "stop recording",
            "end recording",
            "finish recording",
            "stop screen capture",
            "end screen capture",
        )
        if any(pattern in value for pattern in stop_patterns):
            return "stop_screen_recording"

        start_patterns = (
            "start screen recording",
            "start screen record",
            "start the screen recording",
            "start the screen record",
            "start recording the screen",
            "start recording screen",
            "start my screen recording",
            "start my screen record",
            "begin screen recording",
            "begin screen record",
            "begin recording the screen",
            "record screen",
            "record my screen",
            "record the screen",
            "start screen capture",
            "start recording",
            "begin recording",
        )
        if any(pattern in value for pattern in start_patterns):
            return "start_screen_recording"

        screenshot_patterns = (
            "take screenshot",
            "take a screenshot",
            "take the screenshot",
            "take screen shot",
            "take a screen shot",
            "capture screen",
            "capture the screen",
            "capture my screen",
            "capture this screen",
            "screenshot this screen",
            "screenshot this window",
            "screen shot this window",
            "take screenshot this window",
            "take a screenshot of this window",
            "capture this window",
            "take a screen capture",
        )
        if any(pattern in value for pattern in screenshot_patterns):
            return "take_screenshot"

        return None

    def extract_screen_capture(self, text: str) -> Optional[str]:
        """Backward-compatible alias."""
        return self.extract_capture_action(text)

    # ==========================================================
    # GENERAL ENTITY DISPATCH
    # ==========================================================

    def extract_by_intent(
        self,
        text: str,
        intent: Optional[str] = None,
    ):
        """
        Return the entity most relevant to a known intent.

        This helper is useful for CommandDispatcher-style integrations
        that already know the detected intent.
        """

        mapping = {
            "launch_application": self.extract_application,
            "close_application": self.extract_application,
            "open_word": self.extract_application,
            "open_folder": self.extract_folder,
            "create_folder": self.extract_folder,
            "delete_folder": self.extract_folder,
            "rename_folder": self.extract_rename_folder,
            "copy_folder": self.extract_copy_folder,
            "move_folder": self.extract_move_folder,
            "open_file": self.extract_file_query,
            "create_file": self.extract_file_query,
            "delete_file": self.extract_file_query,
            "rename_file": self.extract_rename_file,
            "copy_file": self.extract_copy_file,
            "move_file": self.extract_move_file,
            "compress_file": self.extract_compress_file,
            "extract_zip": self.extract_extract_zip,
            "search_extension": self.extract_search_extension,
            "search_size": self.extract_search_size,
            "search_date": self.extract_search_date,
            "google_search": self.extract_search_query,
            "youtube_search": self.extract_youtube_query,
            "play_youtube": self.extract_youtube_query,
            "open_website": self.extract_website,
            "open_google": self.extract_website,
            "open_youtube": self.extract_website,
            "open_chrome_profile": self.extract_profile,
            "take_screenshot": self.extract_capture_action,
            "start_screen_recording": self.extract_capture_action,
            "stop_screen_recording": self.extract_capture_action,
            "set_brightness": self.extract_percentage,
            "set_volume": self.extract_percentage,
        }

        extractor = mapping.get(intent)
        if extractor is None:
            return None
        return extractor(text)

    # ==========================================================
    # DEBUG / COMPLETE EXTRACTION
    # ==========================================================

    def extract_all(self, text: str) -> dict:
        return {
            "original_text": text,
            "normalized_text": self._normalize(text),

            "capture_action": self.extract_capture_action(text),
            "screen_capture": self.extract_screen_capture(text),

            "percentage": self.extract_percentage(text),
            "application": self.extract_application(text),

            "file_query": self.extract_file_query(text),
            "compress_file": self.extract_compress_file(text),
            "extract_zip": self.extract_extract_zip(text),

            "rename_file": self.extract_rename_file(text),
            "copy_file": self.extract_copy_file(text),
            "move_file": self.extract_move_file(text),

            "search_extension": self.extract_search_extension(text),
            "search_size": self.extract_search_size(text),
            "search_date": self.extract_search_date(text),

            "website": self.extract_website(text),
            "search_query": self.extract_search_query(text),
            "youtube_query": self.extract_youtube_query(text),

            "folder": self.extract_folder(text),
            "rename_folder": self.extract_rename_folder(text),
            "copy_folder": self.extract_copy_folder(text),
            "move_folder": self.extract_move_folder(text),

            "browser": self.extract_browser(text),
            "profile": self.extract_profile(text),
        }
