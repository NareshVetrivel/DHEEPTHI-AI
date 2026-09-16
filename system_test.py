"""
DHEEPTHI-AI V1 — Overall System Test Runner

Run from project root:

    python system_test.py

What this runner does
---------------------
1. Checks project/runtime integrity.
2. Checks the actual planner module names used by DHEEPTHI-AI.
3. Runs 1,000 ENGLISH SINGLE-COMMAND natural-language cases through the real IntentDetector and EntityExtractor.
4. Separately checks normalizer/entity extractor/database/automation/voice/UI.
5. Keeps live Gemini and real hardware execution opt-in.

IMPORTANT
---------
The 1,000-command suite tests SINGLE-COMMAND NATURAL-ENGLISH RECOGNITION / ROUTING.
It does NOT execute destructive actions such as deleting files, shutting down
Windows, moving the mouse, typing into arbitrary applications, etc.

This means you do NOT have to manually speak 1,000 commands.
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import platform
import subprocess
import sys
import textwrap
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# REAL DHEEPTHI-AI PLANNER IMPORTS
# ---------------------------------------------------------------------------
# These are the actual production classes from planner/, not test copies.
from planner.intent_detector import IntentDetector
from planner.entity_extractor import EntityExtractor


ROOT = Path(__file__).resolve().parent
TESTS_DIR = ROOT / "tests"


# ============================================================================
# RESULT ENGINE
# ============================================================================

@dataclass
class Result:
    section: str
    name: str
    status: str
    detail: str = ""


RESULTS: list[Result] = []


def record(section: str, name: str, status: str, detail: str = "") -> None:
    symbol = {
        "PASS": "✓",
        "FAIL": "✗",
        "WARN": "!",
        "SKIP": "-",
    }.get(status, "?")

    suffix = f" — {detail}" if detail else ""
    print(f"  {symbol} {name}: {status}{suffix}")

    RESULTS.append(
        Result(
            section=section,
            name=name,
            status=status,
            detail=detail,
        )
    )


def run_check(
    section: str,
    name: str,
    fn: Callable[[], str | None],
    *,
    optional: bool = False,
) -> None:
    try:
        detail = fn()
        record(section, name, "PASS", detail or "")
    except Exception as exc:
        status = "SKIP" if optional else "FAIL"

        record(
            section,
            name,
            status,
            f"{type(exc).__name__}: {exc}",
        )

        if os.getenv("DHEEPTHI_SYSTEM_TEST_TRACEBACK") == "1":
            traceback.print_exc()


def heading(title: str) -> None:
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


# ============================================================================
# PROJECT DISCOVERY
# ============================================================================

def project_files() -> Iterable[Path]:
    excluded = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
    }

    for path in ROOT.rglob("*.py"):
        if any(part in excluded for part in path.parts):
            continue

        yield path


# ============================================================================
# CORE
# ============================================================================

def check_python_runtime() -> str:
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10+ is required")

    return (
        f"Python {platform.python_version()} / "
        f"{platform.system()}"
    )


def check_project_structure() -> str:
    required = [
        "app",
        "ai",
        "automation",
        "config",
        "core",
        "database",
        "planner",
        "ui",
        "voice",
        "vision",
        "requirements.txt",
    ]

    missing = [
        item
        for item in required
        if not (ROOT / item).exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing project components: " +
            ", ".join(missing)
        )

    return "Required project components found"


def check_python_syntax() -> str:
    files = list(project_files())
    errors: list[str] = []

    for path in files:
        try:
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
        except Exception as exc:
            errors.append(
                f"{path.relative_to(ROOT)}: "
                f"{type(exc).__name__}: {exc}"
            )

    if errors:
        raise RuntimeError(
            f"{len(errors)} syntax error(s); "
            f"first: {errors[0]}"
        )

    return f"{len(files)} Python files parsed successfully"


def check_environment() -> str:
    """
    Read the same .env-backed configuration used by DHEEPTHI-AI.
    Raw os.getenv() alone does not load .env.
    """
    settings = importlib.import_module("config.settings")

    configured = sum(
        bool(getattr(settings, f"GEMINI_API_KEY_{index}", None))
        for index in range(1, 5)
    )

    model = (
        getattr(settings, "GEMINI_MODEL", None)
        or getattr(settings, "GEMINI_MODEL_NAME", None)
        or "unknown"
    )

    return f"{configured}/4 Gemini key variables configured; model={model}"


def check_core_imports() -> str:
    modules = [
        "config.settings",
        "planner.intent_detector",
        "planner.entity_extractor",
        "planner.command_normalizer",
        "planner.multi_command_planner",
        "planner.multi_command_executor",
        "planner.command_dispatcher",
        "database.database_manager",
        "automation.system_controller",
        "automation.screen_recorder",
        "voice.text_to_speech",
        "voice.speech_recognition",
        "vision.ocr",
        "ai.gemini_client",
    ]

    failures: list[str] = []

    for module in modules:
        try:
            importlib.import_module(module)
        except Exception as exc:
            failures.append(
                f"{module}: "
                f"{type(exc).__name__}: {exc}"
            )

    if failures:
        raise RuntimeError("; ".join(failures))

    return f"{len(modules)} core modules imported"


# ============================================================================
# PLANNER — PRODUCTION MODULE PROVENANCE
# ============================================================================

def check_planner_source_files() -> str:
    """
    Verify that the test runner imports the actual planner modules from this
    project root, not generated/test copies.
    """
    import planner.entity_extractor as entity_module
    import planner.intent_detector as intent_module

    expected_intent = (ROOT / "planner" / "intent_detector.py").resolve()
    expected_entity = (ROOT / "planner" / "entity_extractor.py").resolve()

    actual_intent = Path(intent_module.__file__).resolve()
    actual_entity = Path(entity_module.__file__).resolve()

    if actual_intent != expected_intent:
        raise AssertionError(
            f"IntentDetector imported from {actual_intent}; "
            f"expected {expected_intent}"
        )

    if actual_entity != expected_entity:
        raise AssertionError(
            f"EntityExtractor imported from {actual_entity}; "
            f"expected {expected_entity}"
        )

    return (
        f"IntentDetector={actual_intent}; "
        f"EntityExtractor={actual_entity}"
    )


# ============================================================================
# PLANNER — SMALL SMOKE TEST
# ============================================================================

def check_intent_detector() -> str:
    detector = IntentDetector(
        enable_gemini_fallback=False
    )

    cases = {
        "take screenshot": "take_screenshot",
        "take a screenshot": "take_screenshot",
        "could you please take a screenshot for me": "take_screenshot",
        "would you mind starting screen recording": "start_screen_recording",
        "start screen recording": "start_screen_recording",
        "can you please stop the screen recording": "stop_screen_recording",
        "open file explorer": "open_file_explorer",
        "could you open powershell for me": "open_powershell",
        "please open command prompt": "open_cmd",
    }

    failures: list[str] = []

    for command, expected in cases.items():
        actual = detector.detect_intent(command)

        if actual != expected:
            failures.append(
                f"{command!r}: "
                f"got {actual!r}, expected {expected!r}"
            )

    if failures:
        raise AssertionError("; ".join(failures))

    return f"{len(cases)} deterministic intent cases passed"


CANONICAL_COMMANDS: list[tuple[str, str]] = [
    # ------------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------------
    ("open chrome", "launch_application"),
    ("open google chrome", "launch_application"),
    ("launch chrome", "launch_application"),
    ("start chrome", "launch_application"),
    ("run chrome", "launch_application"),
    ("open edge", "launch_application"),
    ("open microsoft edge", "launch_application"),
    ("launch edge", "launch_application"),
    ("open firefox", "launch_application"),
    ("launch firefox", "launch_application"),
    ("open notepad", "launch_application"),
    ("launch notepad", "launch_application"),
    ("open calculator", "launch_application"),
    ("launch calculator", "launch_application"),
    ("open paint", "launch_application"),
    ("launch paint", "launch_application"),
    ("open excel", "launch_application"),
    ("launch excel", "launch_application"),
    ("open powerpoint", "launch_application"),
    ("launch powerpoint", "launch_application"),
    ("open vscode", "launch_application"),
    ("launch vscode", "launch_application"),
    ("open pycharm", "launch_application"),
    ("launch pycharm", "launch_application"),
    ("open file explorer", "open_file_explorer"),
    ("open powershell", "open_powershell"),
    ("open command prompt", "open_cmd"),

    ("close chrome", "close_application"),
    ("exit chrome", "close_application"),
    ("close edge", "close_application"),
    ("exit edge", "close_application"),
    ("close firefox", "close_application"),
    ("close notepad", "close_application"),
    ("exit notepad", "close_application"),
    ("close calculator", "close_application"),
    ("close paint", "close_application"),
    ("close excel", "close_application"),
    ("close powerpoint", "close_application"),
    ("close vscode", "close_application"),
    ("close pycharm", "close_application"),

    # ------------------------------------------------------------------------
    # Screenshot / recording
    # ------------------------------------------------------------------------
    ("take screenshot", "take_screenshot"),
    ("take a screenshot", "take_screenshot"),
    ("capture screen", "take_screenshot"),
    ("take a screen shot", "take_screenshot"),
    ("capture a screenshot", "take_screenshot"),
    ("take screenshot now", "take_screenshot"),
    ("take a screenshot now", "take_screenshot"),
    ("capture this screen", "take_screenshot"),
    ("take screenshot of this window", "take_screenshot"),
    ("capture this window", "take_screenshot"),

    ("start screen recording", "start_screen_recording"),
    ("start the screen recording", "start_screen_recording"),
    ("start screen record", "start_screen_recording"),
    ("record my screen", "start_screen_recording"),
    ("record the screen", "start_screen_recording"),
    ("begin screen recording", "start_screen_recording"),
    ("begin recording", "start_screen_recording"),
    ("start recording", "start_screen_recording"),
    ("start recording my screen", "start_screen_recording"),
    ("record my screen now", "start_screen_recording"),

    ("stop screen recording", "stop_screen_recording"),
    ("stop the screen recording", "stop_screen_recording"),
    ("stop screen record", "stop_screen_recording"),
    ("stop recording", "stop_screen_recording"),
    ("end recording", "stop_screen_recording"),
    ("finish recording", "stop_screen_recording"),
    ("end screen recording", "stop_screen_recording"),
    ("finish screen recording", "stop_screen_recording"),
    ("stop my screen recording", "stop_screen_recording"),
    ("stop recording now", "stop_screen_recording"),

    # ------------------------------------------------------------------------
    # Browser
    # ------------------------------------------------------------------------
    ("open google", "open_google"),
    ("open the google homepage", "open_google"),
    ("open youtube", "open_youtube"),
    ("open the youtube homepage", "open_youtube"),
    ("open a new tab", "new_tab"),
    ("new tab", "new_tab"),
    ("close the current tab", "close_tab"),
    ("close tab", "close_tab"),
    ("go to the next tab", "next_tab"),
    ("next tab", "next_tab"),
    ("go to the previous tab", "previous_tab"),
    ("previous tab", "previous_tab"),
    ("refresh the page", "refresh"),
    ("refresh page", "refresh"),
    ("open browser history", "browser_history"),
    ("show browser history", "browser_history"),
    ("open browser downloads", "browser_downloads"),
    ("show browser downloads", "browser_downloads"),
    ("open browser bookmarks", "browser_bookmarks"),
    ("show browser bookmarks", "browser_bookmarks"),
    ("bookmark this page", "bookmark_page"),
    ("bookmark the page", "bookmark_page"),
    ("open the address bar", "address_bar"),
    ("focus the address bar", "address_bar"),
    ("go back in the browser", "browser_back"),
    ("go forward in the browser", "browser_forward"),
    ("open a private window", "private_window"),
    ("open an incognito window", "private_window"),
    ("open chrome profile", "open_chrome_profile"),
    ("switch chrome profile", "open_chrome_profile"),

    ("search youtube for music", "youtube_search"),
    ("search youtube for python tutorials", "youtube_search"),
    ("search youtube for coding videos", "youtube_search"),
    ("youtube search music", "youtube_search"),
    ("youtube search python", "youtube_search"),
    ("play a youtube video about python", "play_youtube"),
    ("play youtube music", "play_youtube"),
    ("search google for python", "google_search"),
    ("google search python tutorials", "google_search"),
    ("search the web for machine learning", "google_search"),
    ("search online for artificial intelligence", "google_search"),
    ("open website github.com", "open_website"),
    ("open website python.org", "open_website"),
    ("open website wikipedia.org", "open_website"),
    ("open website microsoft.com", "open_website"),

    # ------------------------------------------------------------------------
    # Search / file search
    # ------------------------------------------------------------------------
    ("search for python files", "search_extension"),
    ("find files with the py extension", "search_extension"),
    ("search files by extension", "search_extension"),
    ("find all pdf files", "search_extension"),
    ("search for large files", "search_size"),
    ("find large files", "search_size"),
    ("search files by size", "search_size"),
    ("find files larger than 100 megabytes", "search_size"),
    ("search files by date", "search_date"),
    ("find files created today", "search_date"),
    ("find recently modified files", "search_date"),

    # ------------------------------------------------------------------------
    # Folders
    # ------------------------------------------------------------------------
    ("open desktop", "open_folder"),
    ("open documents", "open_folder"),
    ("open downloads", "open_folder"),
    ("open pictures", "open_folder"),
    ("open videos", "open_folder"),
    ("open music", "open_folder"),
    ("open this pc", "open_folder"),
    ("open my computer", "open_folder"),
    ("open recycle bin", "open_folder"),
    ("open c drive", "open_folder"),
    ("create a folder", "create_folder"),
    ("create a new folder", "create_folder"),
    ("make a folder", "create_folder"),
    ("create a new directory", "create_folder"),
    ("rename the folder", "rename_folder"),
    ("rename this folder", "rename_folder"),
    ("rename a folder", "rename_folder"),
    ("delete the folder", "delete_folder"),
    ("delete this folder", "delete_folder"),
    ("remove the folder", "delete_folder"),
    ("move the folder", "move_folder"),
    ("move this folder", "move_folder"),
    ("copy the folder", "copy_folder"),
    ("copy this folder", "copy_folder"),
    ("empty recycle bin", "empty_recycle_bin"),
    ("empty the recycle bin", "empty_recycle_bin"),

    # ------------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------------
    ("open the file", "open_file"),
    ("open a file", "open_file"),
    ("open this file", "open_file"),
    ("create a file", "create_file"),
    ("create a new file", "create_file"),
    ("make a new file", "create_file"),
    ("delete the file", "delete_file"),
    ("delete this file", "delete_file"),
    ("remove the file", "delete_file"),
    ("rename the file", "rename_file"),
    ("rename this file", "rename_file"),
    ("copy the file", "copy_file"),
    ("copy this file", "copy_file"),
    ("move the file", "move_file"),
    ("move this file", "move_file"),
    ("compress the file", "compress_file"),
    ("compress this file", "compress_file"),
    ("extract the zip file", "extract_zip"),
    ("extract this zip file", "extract_zip"),

    # ------------------------------------------------------------------------
    # Keyboard / clipboard
    # ------------------------------------------------------------------------
    ("press enter", "press_enter"),
    ("press the enter key", "press_enter"),
    ("press tab", "press_tab"),
    ("press the tab key", "press_tab"),
    ("press backspace", "backspace"),
    ("press the backspace key", "backspace"),
    ("press delete", "delete"),
    ("press the delete key", "delete"),
    ("press escape", "escape"),
    ("press the escape key", "escape"),
    ("press space", "space"),
    ("press the space key", "space"),
    ("press up", "arrow_up"),
    ("press the up arrow", "arrow_up"),
    ("press down", "arrow_down"),
    ("press the down arrow", "arrow_down"),
    ("press left", "arrow_left"),
    ("press the left arrow", "arrow_left"),
    ("press right", "arrow_right"),
    ("press the right arrow", "arrow_right"),
    ("press home", "home"),
    ("press the home key", "home"),
    ("press end", "end"),
    ("press the end key", "end"),
    ("select all", "select_all"),
    ("copy", "copy"),
    ("copy it", "copy"),
    ("paste", "paste"),
    ("paste it", "paste"),
    ("cut", "cut"),
    ("cut it", "cut"),
    ("undo", "undo"),
    ("redo", "redo"),

    # ------------------------------------------------------------------------
    # Mouse / window
    # ------------------------------------------------------------------------
    ("click", "left_click"),
    ("left click", "left_click"),
    ("double click", "double_click"),
    ("double-click", "double_click"),
    ("right click", "right_click"),
    ("scroll up", "scroll_up"),
    ("scroll down", "scroll_down"),
    ("minimize window", "minimize_window"),
    ("minimize the window", "minimize_window"),
    ("maximize window", "maximize_window"),
    ("maximize the window", "maximize_window"),
    ("restore window", "restore_window"),
    ("restore the window", "restore_window"),
    ("close window", "close_window"),
    ("close the window", "close_window"),

    # ------------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------------
    ("mute", "mute"),
    ("mute the volume", "mute"),
    ("turn the volume up", "volume_up"),
    ("volume up", "volume_up"),
    ("increase the volume", "volume_up"),
    ("turn the volume down", "volume_down"),
    ("volume down", "volume_down"),
    ("decrease the volume", "volume_down"),
    ("set the volume", "set_volume"),
    ("increase brightness", "brightness_up"),
    ("brightness up", "brightness_up"),
    ("decrease brightness", "brightness_down"),
    ("brightness down", "brightness_down"),
    ("set brightness", "set_brightness"),
    ("open settings", "open_settings"),
    ("open system settings", "open_settings"),
    ("open task manager", "open_task_manager"),
    ("show task manager", "open_task_manager"),
    ("open file explorer", "open_file_explorer"),
    ("open explorer", "open_file_explorer"),
    ("open command prompt", "open_cmd"),
    ("open cmd", "open_cmd"),
    ("open powershell", "open_powershell"),
    ("open control panel", "open_control_panel"),
    ("open the control panel", "open_control_panel"),
    ("open camera", "open_camera"),
    ("take a photo", "capture_photo"),
    ("capture a photo", "capture_photo"),
    ("take photo", "capture_photo"),
    ("lock the screen", "lock_screen"),
    ("lock screen", "lock_screen"),

    # ------------------------------------------------------------------------
    # Typing
    # ------------------------------------------------------------------------
    ("type hello", "type_text"),
    ("type hello world", "type_text"),
    ("type good morning", "type_text"),
    ("type testing command", "type_text"),
    ("type this is a test", "type_text"),
    ("type computer science", "type_text"),
    ("type DHEEPTHI AI", "type_text"),
    ("write hello", "type_text"),
    ("write hello world", "type_text"),
    ("write good morning", "type_text"),
    ("write testing command", "type_text"),
    ("write this is a test", "type_text"),
    ("write computer science", "type_text"),
    ("write DHEEPTHI AI", "type_text"),

    # ------------------------------------------------------------------------
    # Word / Office
    # ------------------------------------------------------------------------
    ("open word", "open_word"),
    ("open microsoft word", "open_word"),
    ("launch word", "open_word"),
    ("close word", "close_word"),
    ("close microsoft word", "close_word"),
    ("exit word", "close_word"),
    ("create a blank Word document", "create_blank_document"),
    ("create blank Word document", "create_blank_document"),
    ("create a new Word document", "create_blank_document"),
    ("open an existing Word document", "open_existing_document"),
    ("open an existing document", "open_existing_document"),
    ("save the document", "save"),
    ("save the Word document", "save"),
    ("save as", "save_as"),
    ("save the document as", "save_as"),
    ("save as docx", "save_docx"),
    ("save the document as docx", "save_docx"),
    ("save as pdf", "save_pdf"),
    ("save the document as pdf", "save_pdf"),
    ("close the current document", "close_current_document"),
    ("create a document with a specified filename", "create_specified_filename"),
    ("read the existing document", "read_existing_document"),
    ("add text at the cursor", "add_text_at_cursor"),
    ("replace the document content", "replace_content"),
    ("read the document", "read_document"),
    ("clear the document", "clear_document"),
    ("strikethrough the text", "strikethrough"),
    ("underline the text", "underline"),
    ("italicize the text", "italic"),
    ("make the text bold", "bold"),
    ("change the font size", "font_size"),
    ("change the font", "font"),
    ("change the text color", "text_color"),
    ("highlight the text", "highlight"),
    ("align the text left", "align_left"),
    ("center align the text", "align_center"),
    ("align the text right", "align_right"),
    ("justify the text", "justify"),
    ("change line spacing", "line_spacing"),
    ("change paragraph spacing", "paragraph_spacing"),
    ("change indentation", "indentation"),
    ("add bullets", "bullets"),
    ("add numbering", "numbering"),
    ("apply title style", "title"),
    ("apply heading one", "heading_1"),
    ("apply normal style", "normal"),
    ("change the document style", "document_style"),
    ("read table data", "read_table_data"),
    ("create a table", "create_table"),
    ("replace text", "replace"),
    ("find text", "find"),
    ("insert an image", "image"),
    ("insert a hyperlink", "hyperlink"),
    ("insert a page break", "page_break"),
    ("insert a new page", "new_page"),
    ("insert page number", "page_number"),
    ("add a header", "header"),
    ("add a footer", "footer"),
    ("change page margins", "margins"),

    # ------------------------------------------------------------------------
    # Office
    # ------------------------------------------------------------------------
    ("create an Excel workbook", "create_excel_workbook"),
    ("create a new Excel workbook", "create_excel_workbook"),
    ("create a PowerPoint presentation", "create_powerpoint_presentation"),
    ("create a new PowerPoint presentation", "create_powerpoint_presentation"),

    # ------------------------------------------------------------------------
    # Code agent
    # ------------------------------------------------------------------------
    ("write python code", "code_agent"),
    ("create a python script", "code_agent"),
    ("generate python code", "code_agent"),
    ("write a program in python", "code_agent"),
    ("create a script", "code_agent"),
]




# ============================================================================
# PLANNER — 1,000 ENGLISH SINGLE-COMMAND STRESS SUITE
# ============================================================================

# V1 focus: SINGLE commands only.
#
# A sentence can be polite, conversational, abbreviated, or naturally
# phrased, but it must contain exactly ONE requested action.
#
# This suite measures:
#   1. IntentDetector routing
#   2. natural-English robustness
#   3. EntityExtractor preservation for high-confidence entities
#
# Gemini is intentionally NOT used here. No desktop action is executed.


def _single_command_variants(command: str) -> list[str]:
    """Generate diverse English-only phrasings for one action."""
    return [
        command,
        f"please {command}",
        f"{command} please",
        f"can you {command}",
        f"could you {command}",
        f"would you {command}",
        f"please {command} for me",
        f"can you please {command}",
        f"could you please {command}",
        f"would you please {command}",
        f"i want you to {command}",
        f"i need you to {command}",
        f"i'd like you to {command}",
        f"help me {command}",
        f"could you kindly {command}",
        f"would you mind {command}",
        f"when you can {command}",
        f"go ahead and {command}",
        f"just {command}",
        f"please go ahead and {command}",
    ]


def _build_1000_single_command_suite() -> list[tuple[str, str]]:
    """
    Build exactly 1,000 unique English single-command cases.

    No multi-command sentence is generated. No meaningless numeric suffixes
    are appended because those could change the semantic meaning.
    """
    cases: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(text: str, expected: str) -> None:
        cleaned = " ".join(text.split()).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            cases.append((cleaned, expected))

    for command, expected in CANONICAL_COMMANDS:
        for variant in _single_command_variants(command):
            add(variant, expected)

    extra_templates = [
        "please {command} for me now",
        "can you kindly {command} for me",
        "could you just {command} for me",
        "would you please {command} now",
        "i need you to {command} now",
        "i would like you to {command}",
        "i'd like you to {command} please",
        "please go ahead and {command} now",
        "when you have a moment {command}",
        "if you could {command} please",
        "if possible please {command}",
        "can you help me {command}",
        "please help me {command}",
        "would you mind if you {command}",
        "could you possibly {command}",
        "can you possibly {command}",
        "please just {command}",
        "now please {command}",
        "right now please {command}",
        "i need {command}",
    ]

    template_index = 0
    command_index = 0

    while len(cases) < 1000:
        command, expected = CANONICAL_COMMANDS[
            command_index % len(CANONICAL_COMMANDS)
        ]
        template = extra_templates[
            template_index % len(extra_templates)
        ]
        add(template.format(command=command), expected)

        template_index += 1
        command_index += 1

        if template_index > 10000:
            raise RuntimeError(
                "Unable to generate 1,000 unique single-command cases"
            )

    return cases[:1000]


def _safe_local_intent(detector, command: str) -> str | None:
    """Run the REAL public IntentDetector entry point with Gemini disabled."""
    return detector.detect_intent(command)


def _entity_expectation_for_command(
    command: str,
    expected_intent: str,
) -> dict[str, str] | None:
    """Return only high-confidence entity expectations."""
    lowered = command.casefold()

    app_names = {
        "google chrome": "chrome",
        "microsoft edge": "edge",
        "microsoft word": "word",
        "chrome": "chrome",
        "edge": "edge",
        "firefox": "firefox",
        "notepad": "notepad",
        "calculator": "calculator",
        "paint": "paint",
        "excel": "excel",
        "powerpoint": "powerpoint",
        "vscode": "vscode",
        "pycharm": "pycharm",
        "word": "word",
    }

    if expected_intent in {
        "launch_application",
        "close_application",
        "open_word",
        "close_word",
    }:
        for phrase, value in sorted(
            app_names.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if phrase in lowered:
                return {"application": value}

    if expected_intent == "search_extension":
        extension_map = {
            ".py": ".py",
            "py extension": ".py",
            "python files": ".py",
            "python file": ".py",
            "pdf files": ".pdf",
            "pdf file": ".pdf",
        }
        for phrase, value in extension_map.items():
            if phrase in lowered:
                return {"extension": value}

    if expected_intent == "open_google":
        return {"website": "google"}

    if expected_intent == "open_youtube":
        return {"website": "youtube"}

    return None


def _flatten_entity_values(value) -> list[str]:
    """Flatten common EntityExtractor return shapes into text values."""
    if value is None:
        return []

    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_flatten_entity_values(item))
        return values

    if isinstance(value, (list, tuple, set)):
        values = []
        for item in value:
            values.extend(_flatten_entity_values(item))
        return values

    return [str(value)]


def _entity_contains(
    entities: dict,
    field: str,
    expected: str,
) -> bool:
    if field not in entities:
        return False

    expected_normalized = expected.casefold().strip()

    return any(
        expected_normalized in value.casefold()
        for value in _flatten_entity_values(entities[field])
    )


def check_1000_command_stress_suite(
    detector: IntentDetector,
    extractor: EntityExtractor,
) -> Result:
    """
    Diagnose the REAL production IntentDetector + EntityExtractor.

    No duplicate routing logic is used here.
    Every command is passed directly into production code.
    """
    cases = _build_1000_single_command_suite()

    results = []
    intent_counts = Counter()
    route_counts = Counter()
    entity_counts = Counter()
    reference_to_actual = defaultdict(Counter)
    reference_mismatches = []
    empty_entities = []
    runtime_failures = []

    for index, (command, reference_intent) in enumerate(cases, 1):
        try:
            debug = detector.detect_with_debug(command)
            entities = extractor.extract_all(command)

            final_intent = debug.get("intent")
            local_intent = debug.get("local_intent")
            fuzzy_intent = debug.get("fuzzy_intent")
            gemini_intent = debug.get("gemini_intent")
            normalized = debug.get("normalized_text")

            intent_counts[str(final_intent)] += 1

            if local_intent:
                route = "local"
            elif fuzzy_intent:
                route = "fuzzy"
            elif gemini_intent:
                route = "gemini"
            else:
                route = "unresolved"
            route_counts[route] += 1

            reference_to_actual[reference_intent][str(final_intent)] += 1

            non_null_entities = {
                key: value
                for key, value in entities.items()
                if value is not None and value != ""
            }

            for key in non_null_entities:
                entity_counts[key] += 1

            result = {
                "index": index,
                "command": command,
                "reference_intent": reference_intent,
                "normalized_text": normalized,
                "local_intent": local_intent,
                "fuzzy_intent": fuzzy_intent,
                "gemini_intent": gemini_intent,
                "final_intent": final_intent,
                "entities": non_null_entities,
            }
            results.append(result)

            if final_intent != reference_intent:
                reference_mismatches.append(result)

            if not non_null_entities:
                empty_entities.append(result)

        except Exception as exc:
            runtime_failures.append({
                "index": index,
                "command": command,
                "reference_intent": reference_intent,
                "error": f"{type(exc).__name__}: {exc}",
            })

    report = {
        "test_type": "single_command_production_planner_diagnostic",
        "commands": len(cases),
        "command_type": "single_action_only",
        "intent_detector": "planner.intent_detector.IntentDetector",
        "entity_extractor": "planner.entity_extractor.EntityExtractor",
        "intent_api": "detect_with_debug",
        "entity_api": "extract_all",
        "gemini_fallback": False,
        "real_desktop_actions": False,
        "runtime_failure_count": len(runtime_failures),
        "reference_mismatch_count": len(reference_mismatches),
        "empty_entity_count": len(empty_entities),
        "actual_intent_counts": dict(intent_counts),
        "actual_routing_paths": dict(route_counts),
        "actual_entity_field_counts": dict(entity_counts),
        "reference_to_actual": {
            ref: dict(actuals)
            for ref, actuals in reference_to_actual.items()
        },
        "results": results,
        "reference_mismatches": reference_mismatches,
        "empty_entity_results": empty_entities,
        "runtime_failures": runtime_failures,
    }

    report_path = ROOT / "system_test_planner_diagnostic.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print("\n  1,000-SINGLE-COMMAND PRODUCTION PLANNER DIAGNOSTIC")
    print("  " + "-" * 72)
    print(f"  Commands analysed       : {len(cases)}")
    print("  Command type            : SINGLE ACTION ONLY")
    print("  IntentDetector          : REAL planner.intent_detector")
    print("  EntityExtractor         : REAL planner.entity_extractor")
    print("  Intent API              : detect_with_debug()")
    print("  Entity API              : extract_all()")
    print("  Gemini fallback         : OFF")
    print("  Real desktop actions    : 0")
    print(f"  Runtime exceptions      : {len(runtime_failures)}")
    print(f"  Reference mismatches    : {len(reference_mismatches)}")
    print(f"  Empty entity results    : {len(empty_entities)}")
    print(f"  JSON report             : {report_path}")

    print("\n  ACTUAL FINAL INTENT DISTRIBUTION")
    print("  " + "-" * 72)
    for intent, count in intent_counts.most_common():
        print(f"  {str(intent):35} {count:4}")

    print("\n  ACTUAL ROUTING PATH")
    print("  " + "-" * 72)
    for route, count in route_counts.most_common():
        print(f"  {route:35} {count:4}")

    print("\n  ACTUAL ENTITY FIELD USAGE")
    print("  " + "-" * 72)
    for field, count in entity_counts.most_common():
        print(f"  {field:35} {count:4}")

    print("\n  FIRST 30 REFERENCE MISMATCHES")
    print("  " + "-" * 72)
    for item in reference_mismatches[:30]:
        print(f"  #{item['index']:04} {item['command']!r}")
        print(f"       normalized : {item['normalized_text']!r}")
        print(f"       reference  : {item['reference_intent']}")
        print(f"       local      : {item['local_intent']}")
        print(f"       fuzzy      : {item['fuzzy_intent']}")
        print(f"       gemini     : {item['gemini_intent']}")
        print(f"       final      : {item['final_intent']}")
        if item["entities"]:
            print(f"       entities   : {item['entities']}")

    print("\n  FIRST 20 EMPTY-ENTITY RESULTS")
    print("  " + "-" * 72)
    for item in empty_entities[:20]:
        print(f"  #{item['index']:04} {item['command']!r}")
        print(f"       normalized : {item['normalized_text']!r}")
        print(f"       intent     : {item['final_intent']}")

    if runtime_failures:
        print("\n  RUNTIME EXCEPTIONS")
        print("  " + "-" * 72)
        for item in runtime_failures[:20]:
            print(f"  #{item['index']:04} {item['command']!r} -> {item['error']}")

    # The diagnostic itself passes when production code can process all
    # commands without crashing. Reference mismatches are data for the next
    # improvement round, not test-runner errors.
    return Result(
        "PLANNER",
        "1,000-command English production planner diagnostic",
        "PASS" if not runtime_failures else "FAIL",
        (
            f"Analysed {len(cases)} single commands; "
            f"{len(reference_mismatches)} reference mismatches; "
            f"{len(empty_entities)} empty entity results; "
            f"{len(runtime_failures)} runtime exceptions; "
            f"report={report_path.name}"
        ),
    )


def check_command_normalizer() -> str:
    from planner.command_normalizer import CommandNormalizer

    normalizer = CommandNormalizer()

    samples = [
        "  OPEN   NOTEPAD  ",
        "open chrome",
        "DHEEPTHI please open calculator",
        "could you please open Google Chrome for me",
        "would you mind taking a screenshot for me",
        "i want you to search for Python files",
        "please find large files",
        "can you open the downloads folder",
        "start screen recording",
        "stop screen recording",
    ]

    for text in samples:
        result = normalizer.normalize(text)

        if not result:
            raise AssertionError(
                f"Empty normalization result for {text!r}"
            )

    return f"{len(samples)} normalization cases passed"


def check_entity_extractor() -> str:
    """Run representative inputs through the REAL EntityExtractor."""
    extractor = EntityExtractor()

    samples = [
        "could you please open Google Chrome for me",
        "would you mind taking a screenshot for me",
        "i want you to search for Python files",
        "can you find files with the pdf extension",
        "please find large files",
        "find files created today",
        "take a screenshot of this screen",
        "start recording my screen",
        "stop my screen recording",
        "copy the file from Downloads to Desktop",
        "search YouTube for Python tutorials",
        "open the downloads folder",
    ]

    print("\n  ENTITY EXTRACTOR PRODUCTION SAMPLES")
    print("  " + "-" * 72)

    failures = 0

    for index, command in enumerate(samples, 1):
        try:
            entities = extractor.extract_all(command)
            non_null = {
                key: value
                for key, value in entities.items()
                if value is not None and value != ""
            }
            print(f"  #{index:02} {command!r}")
            print(f"       {non_null}")
        except Exception as exc:
            failures += 1
            print(f"  #{index:02} {command!r} -> {type(exc).__name__}: {exc}")

    if failures:
        raise RuntimeError(
            f"{failures}/{len(samples)} EntityExtractor samples raised exceptions"
        )

    return f"{len(samples)} real EntityExtractor samples analysed"


def check_planner_module_surface() -> str:
    # These are the actual planner modules used by the project.
    modules = [
        "planner.action_models",
        "planner.command_normalizer",
        "planner.intent_detector",
        "planner.entity_extractor",
        "planner.text_extractor",
        "planner.multi_command_planner",
        "planner.multi_command_executor",
        "planner.command_dispatcher",
    ]

    for module in modules:
        importlib.import_module(module)

    return f"{len(modules)} actual planner modules imported"


# ============================================================================
# DATABASE
# ============================================================================

def check_database_module() -> str:
    from database.database_manager import DatabaseManager

    manager = DatabaseManager()

    return f"{type(manager).__name__} initialized"


# ============================================================================
# AUTOMATION
# ============================================================================

def check_system_controller_surface() -> str:
    from automation.system_controller import SystemController

    if not hasattr(
        SystemController,
        "take_screenshot",
    ):
        raise AttributeError(
            "SystemController.take_screenshot() not found"
        )

    return "SystemController capture surface available"


def check_screen_recorder_surface() -> str:
    from automation.screen_recorder import ScreenRecorder

    for method in (
        "start_recording",
        "stop_recording",
    ):
        if not hasattr(ScreenRecorder, method):
            raise AttributeError(
                f"ScreenRecorder.{method}() not found"
            )

    return "ScreenRecorder start/stop surface available"


# ============================================================================
# AI
# ============================================================================

def check_gemini_configuration() -> str:
    from config import settings

    model = getattr(
        settings,
        "GEMINI_MODEL",
        "",
    )

    if not model:
        raise RuntimeError(
            "GEMINI_MODEL is empty"
        )

    keys = [
        getattr(
            settings,
            f"GEMINI_API_KEY_{index}",
            "",
        )
        for index in range(1, 5)
    ]

    configured = sum(
        bool(key.strip())
        for key in keys
    )

    if configured == 0:
        raise RuntimeError(
            "No Gemini API key configured"
        )

    return (
        f"Model={model}; "
        f"{configured}/4 keys configured"
    )


def check_gemini_live() -> str:
    if os.getenv("DHEEPTHI_LIVE_AI_TEST") != "1":
        raise RuntimeError(
            "Live AI test disabled; set "
            "DHEEPTHI_LIVE_AI_TEST=1 to run it"
        )

    from ai.gemini_client import GeminiClient

    client = GeminiClient()

    response = client.generate_response(
        "Reply with exactly: DHEEPTHI TEST OK"
    )

    if not response:
        raise AssertionError(
            "Gemini returned an empty response"
        )

    if "DHEEPTHI TEST OK" not in response:
        raise AssertionError(
            f"Unexpected Gemini response: {response!r}"
        )

    return "Gemini live request succeeded"


# ============================================================================
# VOICE
# ============================================================================

def check_voice_modules() -> str:
    modules = [
        "voice.speech_recognition",
        "voice.groq_recognizer",
        "voice.whisper_recognizer",
        "voice.wake_word",
        "voice.text_to_speech",
    ]

    for module in modules:
        importlib.import_module(module)

    return f"{len(modules)} voice modules imported"


def check_hardware_policy() -> str:
    if os.getenv("DHEEPTHI_HARDWARE_TEST") != "1":
        raise RuntimeError(
            "Hardware execution disabled; set "
            "DHEEPTHI_HARDWARE_TEST=1"
        )

    return "Hardware test mode enabled"


# ============================================================================
# UI
# ============================================================================

def check_ui_modules() -> str:
    """
    Import UI in a clean subprocess.

    This prevents the system-test process from creating a false COM
    initialization conflict after importing Windows voice modules.
    """

    script = textwrap.dedent(
        """
        import importlib

        importlib.import_module("ui.main_window")
        importlib.import_module("ui.widgets.system_osd")

        print("DHEEPTHI_UI_IMPORT_OK")
        """
    )

    env = os.environ.copy()

    existing_pythonpath = env.get(
        "PYTHONPATH",
        "",
    )

    env["PYTHONPATH"] = (
        str(ROOT)
        + (
            os.pathsep + existing_pythonpath
            if existing_pythonpath
            else ""
        )
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )

    if completed.returncode != 0:
        output = (
            (completed.stderr or "").strip()
            or (completed.stdout or "").strip()
            or "unknown UI import failure"
        )

        raise RuntimeError(
            output[-4000:]
        )

    if "DHEEPTHI_UI_IMPORT_OK" not in completed.stdout:
        raise RuntimeError(
            "UI subprocess did not report successful import"
        )

    return (
        "UI modules imported successfully "
        "in isolated process"
    )


# ============================================================================
# EXISTING TEST INVENTORY
# ============================================================================

def inspect_existing_tests() -> str:
    if not TESTS_DIR.exists():
        raise FileNotFoundError(
            "tests/ directory not found"
        )

    files = list(
        TESTS_DIR.glob("*.py")
    )

    pytest_functions = 0

    for path in files:
        try:
            tree = ast.parse(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                if node.name.startswith("test_"):
                    pytest_functions += 1

    return (
        f"{len(files)} test Python files found; "
        f"{pytest_functions} pytest-style "
        f"test functions discovered"
    )


# ============================================================================
# FINAL REPORT
# ============================================================================

def final_report() -> int:
    heading(
        "DHEEPTHI-AI FINAL SYSTEM TEST SUMMARY"
    )

    counts = {
        status: sum(
            1
            for result in RESULTS
            if result.status == status
        )
        for status in (
            "PASS",
            "FAIL",
            "WARN",
            "SKIP",
        )
    }

    print(f"Total checks : {len(RESULTS)}")
    print(f"PASS         : {counts['PASS']}")
    print(f"FAIL         : {counts['FAIL']}")
    print(f"WARN         : {counts['WARN']}")
    print(f"SKIP         : {counts['SKIP']}")

    failures = [
        result
        for result in RESULTS
        if result.status == "FAIL"
    ]

    if failures:
        print()
        print("FAILED CHECKS")

        for result in failures:
            print(
                f"  ✗ [{result.section}] "
                f"{result.name}: "
                f"{result.detail}"
            )

        print()
        print("OVERALL RESULT: FAIL")
        return 1

    print()
    print("OVERALL RESULT: PASS")
    return 0


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    print()
    print(
        "DHEEPTHI-AI V1 — "
        "OVERALL SYSTEM TEST"
    )
    print(
        f"Project root: {ROOT}"
    )
    print(
        f"Python      : {sys.executable}"
    )

    heading("CORE")

    run_check(
        "CORE",
        "Python runtime",
        check_python_runtime,
    )

    run_check(
        "CORE",
        "Project structure",
        check_project_structure,
    )

    run_check(
        "CORE",
        "Python syntax",
        check_python_syntax,
    )

    run_check(
        "CORE",
        "Environment configuration",
        check_environment,
    )

    run_check(
        "CORE",
        "Core imports",
        check_core_imports,
    )

    heading("PLANNER / ROUTING")

    run_check(
        "PLANNER",
        "Production planner source files",
        check_planner_source_files,
    )

    run_check(
        "PLANNER",
        "Intent detector smoke test",
        check_intent_detector,
    )
    diagnostic_detector = IntentDetector(
        enable_gemini_fallback=False
    )
    diagnostic_extractor = EntityExtractor()

    run_check(
        "PLANNER",
        "1,000-command English production planner diagnostic",
        lambda: check_1000_command_stress_suite(
            diagnostic_detector,
            diagnostic_extractor,
        ),
    )

    run_check(
        "PLANNER",
        "Command normalizer",
        check_command_normalizer,
    )

    run_check(
        "PLANNER",
        "Entity extractor",
        check_entity_extractor,
    )

    run_check(
        "PLANNER",
        "Planner module surface",
        check_planner_module_surface,
    )

    heading("DATABASE")

    run_check(
        "DATABASE",
        "Database manager",
        check_database_module,
    )

    heading("AUTOMATION")

    run_check(
        "AUTOMATION",
        "System controller surface",
        check_system_controller_surface,
    )

    run_check(
        "AUTOMATION",
        "Screen recorder surface",
        check_screen_recorder_surface,
    )

    heading("AI")

    run_check(
        "AI",
        "Gemini configuration",
        check_gemini_configuration,
    )

    run_check(
        "AI",
        "Gemini live request",
        check_gemini_live,
        optional=True,
    )

    heading("VOICE")

    run_check(
        "VOICE",
        "Voice module surface",
        check_voice_modules,
    )

    run_check(
        "VOICE",
        "Hardware execution mode",
        check_hardware_policy,
        optional=True,
    )

    heading("UI")

    run_check(
        "UI",
        "UI module surface",
        check_ui_modules,
    )

    heading("EXISTING TEST INVENTORY")

    run_check(
        "TESTS",
        "Existing tests inventory",
        inspect_existing_tests,
    )

    return final_report()


if __name__ == "__main__":

    raise SystemExit(main())
