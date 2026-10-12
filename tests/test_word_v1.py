"""
test_word_v1.py

Comprehensive functional test suite for ASTRA-AI Word Productivity Agent V1.

This test validates the real Microsoft Word COM state after operations.
It does NOT modify the existing Word Agent implementation.

Test flow:
    WordAgent
        |
        +--> WordAutomation
        |
        +--> Microsoft Word COM
        |
        +--> Actual document state verification

Requirements:
    - Windows
    - Microsoft Word installed
    - pywin32 available
    - ASTRA-AI project root as parent of this file

Run:
    python tests/test_word_v1.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# Project root
# ----------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from productivity_agent.word.agent import WordAgent, WordAgentStatus
from productivity_agent.word.automation import WordAutomation
from productivity_agent.word.verifier import WordVerifier
from productivity_agent.word import commands as cmd


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def separator(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def assert_condition(
    label: str,
    condition: bool,
    detail: str = "",
) -> bool:
    if condition:
        print(f"  [PASS] {label}")
        return True

    message = f"  [FAIL] {label}"

    if detail:
        message += f" -- {detail}"

    print(message)
    return False


def result_ok(result: Any) -> bool:
    return bool(result.success)


def get_text(agent: WordAgent) -> str:
    result = agent.execute(cmd.READ_DOCUMENT)

    if not result.success:
        raise RuntimeError(
            f"Could not read document: {result.message}"
        )

    return str(result.data.get("text", ""))


def check_agent_result(
    label: str,
    result: Any,
) -> bool:
    return assert_condition(
        label,
        result.success,
        (
            f"status={result.status}, "
            f"message={result.message}, "
            f"error={result.error}"
        ),
    )


# ----------------------------------------------------------------------
# Main test suite
# ----------------------------------------------------------------------

def run_tests() -> int:
    temp_dir = Path(
        tempfile.mkdtemp(prefix="astra_word_v1_")
    )

    docx_path = temp_dir / "astra_word_v1_test.docx"
    pdf_path = temp_dir / "astra_word_v1_test.pdf"
    reopened_docx_path = temp_dir / "astra_word_v1_reopened.docx"

    agent = WordAgent(visible=False)
    verifier = WordVerifier()

    passed = 0
    failed = 0

    def check(
        label: str,
        condition: bool,
        detail: str = "",
    ) -> None:
        nonlocal passed, failed

        if assert_condition(label, condition, detail):
            passed += 1
        else:
            failed += 1

    try:
        # ==============================================================
        # 1. APPLICATION / DOCUMENT LIFECYCLE
        # ==============================================================

        separator("1. APPLICATION & DOCUMENT LIFECYCLE")

        result = agent.execute(cmd.OPEN_WORD)

        check(
            "Word application started",
            result.success,
            result.message,
        )

        result = agent.execute(cmd.CREATE_BLANK_DOCUMENT)

        check(
            "Blank document created",
            result.success,
            result.message,
        )

        check(
            "WordAgent status is COMPLETED",
            result.status == WordAgentStatus.COMPLETED,
            str(result.status),
        )

        # ==============================================================
        # 2. CONTENT
        # ==============================================================

        separator("2. CONTENT OPERATIONS")

        initial_text = (
            "ASTRA-AI Word Productivity Agent V1\n"
            "This document validates Word automation.\n"
            "Automation testing is important.\n"
        )

        result = agent.execute(
            cmd.TYPE_TEXT,
            {"text": initial_text},
        )

        check(
            "type_text",
            result.success,
            result.message,
        )

        content = get_text(agent)

        check(
            "Typed text exists in document",
            "ASTRA-AI Word Productivity Agent V1" in content,
            repr(content),
        )

        check(
            "Second paragraph exists",
            "This document validates Word automation." in content,
            repr(content),
        )

        # Replace complete content
        replacement_text = (
            "ASTRA-AI Replacement Test\n"
            "Content was successfully replaced."
        )

        result = agent.execute(
            cmd.REPLACE_CONTENT,
            {"text": replacement_text},
        )

        check(
            "replace_content",
            result.success,
            result.message,
        )

        content = get_text(agent)

        check(
            "Replacement content exists",
            "Content was successfully replaced." in content,
            repr(content),
        )

        check(
            "Old content removed",
            "Automation testing is important." not in content,
            repr(content),
        )

        # Add text at cursor
        result = agent.execute(
            cmd.ADD_TEXT_AT_CURSOR,
            {"text": "\nASTRA-AI cursor insertion test."},
        )

        check(
            "add_text_at_cursor",
            result.success,
            result.message,
        )

        content = get_text(agent)

        check(
            "Cursor text exists",
            "ASTRA-AI cursor insertion test." in content,
            repr(content),
        )

        # Clear and rebuild document for formatting tests
        result = agent.execute(cmd.CLEAR_DOCUMENT)

        check(
            "clear_document",
            result.success,
            result.message,
        )

        formatting_text = (
            "Bold Test\n"
            "Italic Test\n"
            "Underline Test\n"
            "Strike Test\n"
            "Font Test\n"
            "Paragraph Test\n"
        )

        result = agent.execute(
            cmd.TYPE_TEXT,
            {"text": formatting_text},
        )

        check(
            "Rebuild test document",
            result.success,
            result.message,
        )

        # ==============================================================
        # 3. FORMATTING
        # ==============================================================

        separator("3. FORMATTING OPERATIONS")

        automation = agent._automation
        document = automation.document
        selection = automation.selection

        # Select first paragraph
        first_para = document.Paragraphs(1).Range
        first_para.Select()

        result = agent.execute(
            cmd.BOLD,
            {"enabled": True},
        )

        check(
            "Bold enabled",
            result.success,
            result.message,
        )

        check(
            "Actual Word Bold state is True",
            bool(selection.Font.Bold) is True,
            f"value={selection.Font.Bold}",
        )

        # Italic
        first_para.Select()

        result = agent.execute(
            cmd.ITALIC,
            {"enabled": True},
        )

        check(
            "Italic enabled",
            result.success,
            result.message,
        )

        check(
            "Actual Word Italic state is True",
            bool(selection.Font.Italic) is True,
            f"value={selection.Font.Italic}",
        )

        # Underline
        first_para.Select()

        result = agent.execute(
            cmd.UNDERLINE,
            {"enabled": True},
        )

        check(
            "Underline enabled",
            result.success,
            result.message,
        )

        check(
            "Actual Word Underline state is enabled",
            int(selection.Font.Underline) != 0,
            f"value={selection.Font.Underline}",
        )

        # Strikethrough
        first_para.Select()

        result = agent.execute(
            cmd.STRIKETHROUGH,
            {"enabled": True},
        )

        check(
            "Strikethrough enabled",
            result.success,
            result.message,
        )

        check(
            "Actual Word StrikeThrough state is True",
            bool(selection.Font.StrikeThrough) is True,
            f"value={selection.Font.StrikeThrough}",
        )

        # Font
        first_para.Select()

        result = agent.execute(
            cmd.FONT,
            {"name": "Arial"},
        )

        check(
            "Font changed to Arial",
            result.success,
            result.message,
        )

        check(
            "Actual Word font is Arial",
            str(selection.Font.Name).lower() == "arial",
            f"value={selection.Font.Name}",
        )

        # Font size
        first_para.Select()

        result = agent.execute(
            cmd.FONT_SIZE,
            {"size": 16},
        )

        check(
            "Font size changed to 16",
            result.success,
            result.message,
        )

        check(
            "Actual Word font size is 16",
            abs(float(selection.Font.Size) - 16.0) < 0.1,
            f"value={selection.Font.Size}",
        )

        # Text color
        first_para.Select()

        result = agent.execute(
            cmd.TEXT_COLOR,
            {"r": 255, "g": 0, "b": 0},
        )

        check(
            "Text color operation completed",
            result.success,
            result.message,
        )

        expected_color = 255

        check(
            "Actual Word text color is red",
            int(selection.Font.Color) == expected_color,
            f"value={selection.Font.Color}",
        )

        # Highlight
        first_para.Select()

        result = agent.execute(
            cmd.HIGHLIGHT,
            {"color_index": 7},
        )

        check(
            "Highlight applied",
            result.success,
            result.message,
        )

        check(
            "Actual Word highlight is applied",
            int(selection.Range.HighlightColorIndex) == 7,
            f"value={selection.Range.HighlightColorIndex}",
        )

        # ==============================================================
        # 4. ALIGNMENT
        # ==============================================================

        separator("4. ALIGNMENT")

        first_para.Select()

        result = agent.execute(cmd.ALIGN_LEFT)

        check(
            "Align left",
            result.success,
            result.message,
        )

        check(
            "Actual alignment is left",
            int(selection.ParagraphFormat.Alignment) == 0,
            f"value={selection.ParagraphFormat.Alignment}",
        )

        first_para.Select()

        result = agent.execute(cmd.ALIGN_CENTER)

        check(
            "Align center",
            result.success,
            result.message,
        )

        check(
            "Actual alignment is center",
            int(selection.ParagraphFormat.Alignment) == 1,
            f"value={selection.ParagraphFormat.Alignment}",
        )

        first_para.Select()

        result = agent.execute(cmd.ALIGN_RIGHT)

        check(
            "Align right",
            result.success,
            result.message,
        )

        check(
            "Actual alignment is right",
            int(selection.ParagraphFormat.Alignment) == 2,
            f"value={selection.ParagraphFormat.Alignment}",
        )

        first_para.Select()

        result = agent.execute(cmd.JUSTIFY)

        check(
            "Justify",
            result.success,
            result.message,
        )

        check(
            "Actual alignment is justify",
            int(selection.ParagraphFormat.Alignment) == 3,
            f"value={selection.ParagraphFormat.Alignment}",
        )

        # ==============================================================
        # 5. PARAGRAPH OPERATIONS
        # ==============================================================

        separator("5. PARAGRAPH OPERATIONS")

        first_para.Select()

        result = agent.execute(
            cmd.LINE_SPACING,
            {"value": 1.5},
        )

        check(
            "Line spacing 1.5",
            result.success,
            result.message,
        )

        first_para.Select()

        result = agent.execute(
            cmd.PARAGRAPH_SPACING,
            {
                "before": 6,
                "after": 8,
            },
        )

        check(
            "Paragraph spacing",
            result.success,
            result.message,
        )

        first_para.Select()

        result = agent.execute(
            cmd.INDENTATION,
            {
                "left": 10,
                "right": 5,
                "first_line": 4,
            },
        )

        check(
            "Indentation",
            result.success,
            result.message,
        )

        # ==============================================================
        # 6. STYLES
        # ==============================================================

        separator("6. STYLE OPERATIONS")

        first_para.Select()

        result = agent.execute(cmd.TITLE)

        check(
            "Title style",
            result.success,
            result.message,
        )

        check(
            "Actual style is Title",
            "title" in str(selection.Style).lower(),
            f"value={selection.Style}",
        )

        first_para.Select()

        result = agent.execute(cmd.HEADING_1)

        check(
            "Heading 1 style",
            result.success,
            result.message,
        )

        check(
            "Actual style is Heading 1",
            "heading 1" in str(selection.Style).lower(),
            f"value={selection.Style}",
        )

        first_para.Select()

        result = agent.execute(cmd.NORMAL)

        check(
            "Normal style",
            result.success,
            result.message,
        )

        check(
            "Actual style is Normal",
            "normal" in str(selection.Style).lower(),
            f"value={selection.Style}",
        )

        # ==============================================================
        # 7. BULLETS / NUMBERING
        # ==============================================================

        separator("7. BULLETS & NUMBERING")

        # Add bullet test paragraphs
        selection.EndKey(Unit=6, Extend=0)
        selection.TypeParagraph()
        selection.TypeText("Bullet Item 1")
        selection.TypeParagraph()
        selection.TypeText("Bullet Item 2")

        # Select last two paragraphs
        paragraph_count = document.Paragraphs.Count

        bullet_start = document.Paragraphs(paragraph_count - 1).Range.Start
        bullet_end = document.Paragraphs(paragraph_count).Range.End

        bullet_range = document.Range(
            Start=bullet_start,
            End=bullet_end,
        )

        bullet_range.Select()

        result = agent.execute(cmd.BULLETS)

        check(
            "Bullets applied",
            result.success,
            result.message,
        )

        # Numbering on a fresh paragraph
        selection.EndKey(Unit=6, Extend=0)
        selection.TypeParagraph()
        selection.TypeText("Number Item 1")
        selection.TypeParagraph()
        selection.TypeText("Number Item 2")

        paragraph_count = document.Paragraphs.Count

        number_start = document.Paragraphs(paragraph_count - 1).Range.Start
        number_end = document.Paragraphs(paragraph_count).Range.End

        number_range = document.Range(
            Start=number_start,
            End=number_end,
        )

        number_range.Select()

        result = agent.execute(cmd.NUMBERING)

        check(
            "Numbering applied",
            result.success,
            result.message,
        )

        # ==============================================================
        # 8. TABLES
        # ==============================================================

        separator("8. TABLE OPERATIONS")

        selection.EndKey(Unit=6, Extend=0)
        selection.TypeParagraph()

        result = agent.execute(
            cmd.CREATE_TABLE,
            {
                "rows": 3,
                "columns": 2,
            },
        )

        check(
            "3x2 table created",
            result.success,
            result.message,
        )

        check(
            "Document contains table",
            document.Tables.Count >= 1,
            f"table_count={document.Tables.Count}",
        )

        table = document.Tables(document.Tables.Count)

        check(
            "Table has 3 rows",
            int(table.Rows.Count) == 3,
            f"rows={table.Rows.Count}",
        )

        check(
            "Table has 2 columns",
            int(table.Columns.Count) == 2,
            f"columns={table.Columns.Count}",
        )

        # Fill table
        table.Cell(1, 1).Range.Text = "Name"
        table.Cell(1, 2).Range.Text = "Role"
        table.Cell(2, 1).Range.Text = "ASTRA"
        table.Cell(2, 2).Range.Text = "AI Assistant"
        table.Cell(3, 1).Range.Text = "Word Agent"
        table.Cell(3, 2).Range.Text = "Productivity"

        result = agent.execute(
            cmd.READ_TABLE_DATA,
            {"table_index": document.Tables.Count},
        )

        check(
            "Read table data",
            result.success,
            result.message,
        )

        table_data = result.data.get("table_data", [])

        check(
            "Table data contains Name",
            any(
                row and row[0] == "Name"
                for row in table_data
            ),
            repr(table_data),
        )

        check(
            "Table data contains ASTRA",
            any(
                row and row[0] == "ASTRA"
                for row in table_data
            ),
            repr(table_data),
        )

        # ==============================================================
        # 9. FIND / REPLACE
        # ==============================================================

        separator("9. FIND / REPLACE")

        selection.EndKey(Unit=6, Extend=0)
        selection.TypeParagraph()
        selection.TypeText(
            "ASTRA_FIND_TEST original_value"
        )

        result = agent.execute(
            cmd.FIND,
            {"text": "ASTRA_FIND_TEST"},
        )

        check(
            "Find existing text",
            result.success and result.data.get("found") is True,
            result.message,
        )

        result = agent.execute(
            cmd.FIND,
            {"text": "TEXT_THAT_DOES_NOT_EXIST"},
        )

        check(
            "Find missing text returns success=false-found",
            result.success and result.data.get("found") is False,
            result.message,
        )

        result = agent.execute(
            cmd.REPLACE,
            {
                "find_text": "original_value",
                "replace_text": "replacement_value",
            },
        )

        check(
            "Find and replace operation",
            result.success,
            result.message,
        )

        content = get_text(agent)

        check(
            "Replacement text exists",
            "replacement_value" in content,
            repr(content),
        )

        check(
            "Original replacement text removed",
            "original_value" not in content,
            repr(content),
        )

        # ==============================================================
        # 10. IMAGE
        # ==============================================================

        separator("10. IMAGE INSERTION")

        # Minimal valid 1x1 PNG generated from raw bytes.
        image_path = temp_dir / "astra_test_image.png"

        png_bytes = bytes.fromhex(
            "89504E470D0A1A0A"
            "0000000D49484452"
            "0000000100000001"
            "08060000001F15C489"
            "0000000D49444154"
            "789C6360000000020001"
            "E221BC330000000049454E44"
            "AE426082"
        )

        image_path.write_bytes(png_bytes)

        selection.EndKey(Unit=6, Extend=0)
        selection.TypeParagraph()

        before_shapes = document.InlineShapes.Count

        result = agent.execute(
            cmd.IMAGE,
            {"path": str(image_path)},
        )

        check(
            "Image insertion operation",
            result.success,
            result.message,
        )

        check(
            "Inline image added",
            document.InlineShapes.Count == before_shapes + 1,
            (
                f"before={before_shapes}, "
                f"after={document.InlineShapes.Count}"
            ),
        )

        # ==============================================================
        # 11. HYPERLINK
        # ==============================================================

        separator("11. HYPERLINK")

        selection.EndKey(Unit=6, Extend=0)
        selection.TypeParagraph()

        before_links = document.Hyperlinks.Count

        result = agent.execute(
            cmd.HYPERLINK,
            {
                "url": "https://example.com",
                "text": "ASTRA Test Link",
            },
        )

        check(
            "Hyperlink insertion",
            result.success,
            result.message,
        )

        check(
            "Hyperlink count increased",
            document.Hyperlinks.Count == before_links + 1,
            (
                f"before={before_links}, "
                f"after={document.Hyperlinks.Count}"
            ),
        )

        # ==============================================================
        # 12. PAGE BREAK
        # ==============================================================

        separator("12. PAGE BREAK")

        before_pages = document.ComputeStatistics(2)

        selection.EndKey(Unit=6, Extend=0)

        result = agent.execute(cmd.PAGE_BREAK)

        check(
            "Page break inserted",
            result.success,
            result.message,
        )

        after_pages = document.ComputeStatistics(2)

        check(
            "Document page count increased or stayed valid",
            int(after_pages) >= int(before_pages),
            f"before={before_pages}, after={after_pages}",
        )

        # ==============================================================
        # 13. HEADER / FOOTER
        # ==============================================================

        separator("13. HEADER / FOOTER")

        result = agent.execute(
            cmd.HEADER,
            {"text": "ASTRA-AI Test Header"},
        )

        check(
            "Header set",
            result.success,
            result.message,
        )

        header_text = str(
            document.Sections(1)
            .Headers(1)
            .Range.Text
        )

        check(
            "Header contains expected text",
            "ASTRA-AI Test Header" in header_text,
            repr(header_text),
        )

        result = agent.execute(
            cmd.FOOTER,
            {"text": "ASTRA-AI Test Footer"},
        )

        check(
            "Footer set",
            result.success,
            result.message,
        )

        footer_text = str(
            document.Sections(1)
            .Footers(1)
            .Range.Text
        )

        check(
            "Footer contains expected text",
            "ASTRA-AI Test Footer" in footer_text,
            repr(footer_text),
        )

        # ==============================================================
        # 14. PAGE NUMBER
        # ==============================================================

        separator("14. PAGE NUMBER")

        before_page_numbers = (
            document.Sections(1)
            .Footers(1)
            .PageNumbers.Count
        )

        result = agent.execute(cmd.PAGE_NUMBER)

        check(
            "Page number operation",
            result.success,
            result.message,
        )

        after_page_numbers = (
            document.Sections(1)
            .Footers(1)
            .PageNumbers.Count
        )

        check(
            "Page number field added",
            int(after_page_numbers) >= int(before_page_numbers) + 1,
            (
                f"before={before_page_numbers}, "
                f"after={after_page_numbers}"
            ),
        )

        # ==============================================================
        # 15. MARGINS
        # ==============================================================

        separator("15. PAGE MARGINS")

        result = agent.execute(
            cmd.MARGINS,
            {
                "top": 72,
                "bottom": 72,
                "left": 72,
                "right": 72,
            },
        )

        check(
            "Margins updated",
            result.success,
            result.message,
        )

        page_setup = document.PageSetup

        check(
            "Top margin is 72pt",
            abs(float(page_setup.TopMargin) - 72.0) < 0.1,
            f"value={page_setup.TopMargin}",
        )

        check(
            "Bottom margin is 72pt",
            abs(float(page_setup.BottomMargin) - 72.0) < 0.1,
            f"value={page_setup.BottomMargin}",
        )

        check(
            "Left margin is 72pt",
            abs(float(page_setup.LeftMargin) - 72.0) < 0.1,
            f"value={page_setup.LeftMargin}",
        )

        check(
            "Right margin is 72pt",
            abs(float(page_setup.RightMargin) - 72.0) < 0.1,
            f"value={page_setup.RightMargin}",
        )

        # ==============================================================
        # 16. SELECT / COPY / CUT / PASTE
        # ==============================================================

        separator("16. SELECT / COPY / CUT / PASTE")

        selection.EndKey(Unit=6, Extend=0)
        selection.TypeParagraph()
        selection.TypeText("Clipboard Test")

        last_para = document.Paragraphs(document.Paragraphs.Count).Range
        last_para.Select()

        result = agent.execute(cmd.COPY)

        check(
            "Copy operation",
            result.success,
            result.message,
        )

        result = agent.execute(cmd.CUT)

        check(
            "Cut operation",
            result.success,
            result.message,
        )

        result = agent.execute(cmd.PASTE)

        check(
            "Paste operation",
            result.success,
            result.message,
        )

        content = get_text(agent)

        check(
            "Pasted clipboard content exists",
            "Clipboard Test" in content,
            repr(content),
        )

        # ==============================================================
        # 17. SAVE DOCX
        # ==============================================================

        separator("17. DOCX SAVE")

        result = agent.execute(
            cmd.SAVE_DOCX,
            {"path": str(docx_path)},
        )

        check(
            "DOCX save operation",
            result.success,
            result.message,
        )

        check(
            "DOCX exists",
            verifier.docx_exists(docx_path),
            str(docx_path),
        )

        check(
            "DOCX is non-empty",
            verifier.verify_file_not_empty(docx_path),
            str(docx_path),
        )

        # ==============================================================
        # 18. SAVE PDF
        # ==============================================================

        separator("18. PDF EXPORT")

        result = agent.execute(
            cmd.SAVE_PDF,
            {"path": str(pdf_path)},
        )

        check(
            "PDF export operation",
            result.success,
            result.message,
        )

        check(
            "PDF exists",
            verifier.pdf_exists(pdf_path),
            str(pdf_path),
        )

        check(
            "PDF is non-empty",
            verifier.verify_file_not_empty(pdf_path),
            str(pdf_path),
        )

        # ==============================================================
        # 19. CLOSE + REOPEN DOCX
        # ==============================================================

        separator("19. CLOSE / REOPEN DOCX")

        result = agent.execute(cmd.CLOSE_CURRENT_DOCUMENT)

        check(
            "Current document closed",
            result.success,
            result.message,
        )

        result = agent.execute(
            cmd.OPEN_DOCX,
            {"path": str(docx_path)},
        )

        check(
            "DOCX reopened",
            result.success,
            result.message,
        )

        reopened_content = get_text(agent)

        check(
            "Reopened document contains saved content",
            (
                "ASTRA_FIND_TEST replacement_value" in reopened_content
                and "Clipboard Test" in reopened_content
            ),
            repr(reopened_content),
        )

        # ==============================================================
        # 20. SAVE AS
        # ==============================================================

        separator("20. SAVE AS")

        result = agent.execute(
            cmd.SAVE_AS,
            {"path": str(reopened_docx_path)},
        )

        check(
            "Save As operation",
            result.success,
            result.message,
        )

        check(
            "Save As file exists",
            verifier.docx_exists(reopened_docx_path),
            str(reopened_docx_path),
        )

        # ==============================================================
        # 21. CREATE SPECIFIED FILENAME
        # ==============================================================

        separator("21. CREATE SPECIFIED FILENAME")

        specified_path = temp_dir / "astra_specified_filename.docx"

        result = agent.execute(
            cmd.CREATE_SPECIFIED_FILENAME,
            {"path": str(specified_path)},
        )

        check(
            "Create specified filename",
            result.success,
            result.message,
        )

        check(
            "Specified DOCX exists",
            verifier.docx_exists(specified_path),
            str(specified_path),
        )

        # ==============================================================
        # 22. READ EXISTING DOCUMENT
        # ==============================================================

        separator("22. READ EXISTING DOCUMENT")

        result = agent.execute(
            cmd.READ_EXISTING_DOCUMENT,
            {"path": str(docx_path)},
        )

        check(
            "Read existing document",
            result.success,
            result.message,
        )

        read_existing_text = str(
            result.data.get("text", "")
        )

        check(
            "Existing document content returned",
            bool(read_existing_text.strip()),
            repr(read_existing_text),
        )

        # ==============================================================
        # 23. VALIDATION
        # ==============================================================

        separator("23. VALIDATION & ERROR HANDLING")

        result = agent.execute(
            cmd.TYPE_TEXT,
            {},
        )

        check(
            "Missing text requires clarification",
            (
                result.status
                == WordAgentStatus.CLARIFICATION_REQUIRED
                and "text" in result.missing_parameters
            ),
            result.message,
        )

        result = agent.execute(
            cmd.FONT_SIZE,
            {"size": "invalid"},
        )

        check(
            "Invalid font size rejected",
            not result.success,
            result.message,
        )

        result = agent.execute(
            cmd.CREATE_TABLE,
            {
                "rows": 0,
                "columns": 2,
            },
        )

        check(
            "Invalid table dimensions rejected",
            not result.success,
            result.message,
        )

        result = agent.execute(
            "astra_fake_word_operation",
        )

        check(
            "Unsupported operation rejected",
            result.status == WordAgentStatus.UNSUPPORTED,
            result.message,
        )

        result = agent.execute(
            cmd.OPEN_EXISTING_DOCUMENT,
            {
                "path": str(
                    temp_dir / "does_not_exist.docx"
                )
            },
        )

        check(
            "Nonexistent document rejected",
            not result.success,
            result.message,
        )

        # ==============================================================
        # 24. FINAL DOCUMENT STATE
        # ==============================================================

        separator("24. FINAL DOCUMENT STATE")

        check(
            "Word is currently running",
            agent._automation._word is not None,
        )

        check(
            "Document is currently open",
            agent._automation._document is not None,
        )

        active_path = verifier.get_active_document_path(
            agent._automation._word
        )

        check(
            "Active document path is available",
            bool(active_path),
            str(active_path),
        )

        # ==============================================================
        # CLEANUP
        # ==============================================================

    except Exception as exc:
        failed += 1

        print()
        print("=" * 70)
        print("  [ERROR] UNEXPECTED TEST ERROR")
        print("=" * 70)
        print(f"  {type(exc).__name__}: {exc}")

        import traceback

        traceback.print_exc()

    finally:
        separator("CLEANUP")

        try:
            agent._automation.close_document()
            print("  [PASS] Document cleanup completed")
        except Exception as exc:
            print(f"  [WARN] Document cleanup failed: {exc}")

        try:
            agent._automation.close_word()
            print("  [PASS] Word application cleanup completed")
        except Exception as exc:
            print(f"  [WARN] Word cleanup failed: {exc}")

        # Remove temporary files.
        temporary_files = [
            docx_path,
            pdf_path,
            reopened_docx_path,
            temp_dir / "astra_specified_filename.docx",
            temp_dir / "astra_test_image.png",
        ]

        for file_path in temporary_files:
            try:
                file_path.unlink(missing_ok=True)
            except Exception as exc:
                print(
                    f"  [WARN] Could not remove "
                    f"{file_path}: {exc}"
                )

        try:
            temp_dir.rmdir()
        except Exception as exc:
            print(
                f"  [WARN] Could not remove temporary "
                f"directory {temp_dir}: {exc}"
            )

    # ==============================================================
    # SUMMARY
    # ==============================================================

    separator("WORD V1 TEST SUMMARY")

    total = passed + failed

    print(f"  Total  : {total}")
    print(f"  Passed : {passed}")
    print(f"  Failed : {failed}")

    if failed == 0:
        print()
        print("  ================================================")
        print("       ASTRA-AI WORD V1 TESTS PASSED")
        print("  ================================================")
        print()
        print("  Word Productivity Agent V1 is functionally")
        print("  validated at the automation/agent layer.")
        print()
        return 0

    print()
    print("  ================================================")
    print("       ASTRA-AI WORD V1 TESTS FAILED")
    print("  ================================================")
    print()
    print("  Fix the failed operations before moving")
    print("  to voice-command integration.")
    print()

    return 1


if __name__ == "__main__":
    raise SystemExit(run_tests())