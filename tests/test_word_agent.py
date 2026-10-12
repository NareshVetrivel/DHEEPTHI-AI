"""
test_word_agent -- Automated tests for the WordAgent orchestration layer.

Uses temporary directories so no permanent files are left behind.
Cleanup runs even when assertions or exceptions occur.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from productivity_agent.word.agent import WordAgent, WordAgentStatus
from productivity_agent.word import commands


def _sep(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def run_tests() -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="astra_wordagent_test_"))
    docx_path = tmp_dir / "agent_test.docx"
    pdf_path = tmp_dir / "agent_test.pdf"

    agent = WordAgent(visible=False)

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {label}")
        else:
            failed += 1
            msg = f"  [FAIL] {label}"
            if detail:
                msg += f"  --  {detail}"
            print(msg)

    try:
        # ==============================================================
        # FUNCTIONAL TESTS
        # ==============================================================

        # 1. Create WordAgent
        _sep("1. WordAgent creation")
        check("WordAgent instance created", agent is not None)

        # 2. Create blank document (auto-starts Word)
        _sep("2. Create blank document")
        result = agent.execute(commands.CREATE_BLANK_DOCUMENT)
        check("create_blank_document succeeded", result.success, result.message)
        check(
            "Status is COMPLETED",
            result.status == WordAgentStatus.COMPLETED,
            str(result.status),
        )

        # 3. Type text
        _sep("3. Type text")
        result = agent.execute(
            commands.TYPE_TEXT,
            {"text": "ASTRA-AI WordAgent Test"},
        )
        check("type_text succeeded", result.success, result.message)

        # 4. Read document
        _sep("4. Read document")
        result = agent.execute(commands.READ_DOCUMENT)
        check("read_document succeeded", result.success, result.message)

        text = ""
        if isinstance(result.data, dict):
            text = str(result.data.get("text", ""))

        check(
            "Text matches",
            "ASTRA-AI WordAgent Test" in text,
            repr(text)[:120],
        )

        # 5. Save DOCX
        _sep("5. Save DOCX")
        result = agent.execute(
            commands.SAVE_DOCX,
            {"path": str(docx_path)},
        )
        check("save_docx succeeded", result.success, result.message)

        # 6. Verify DOCX
        _sep("6. Verify DOCX exists")
        check(
            "DOCX file on disk",
            docx_path.exists() and docx_path.stat().st_size > 0,
            str(docx_path),
        )

        # 7. Save PDF
        _sep("7. Save PDF")
        result = agent.execute(
            commands.SAVE_PDF,
            {"path": str(pdf_path)},
        )
        check("save_pdf succeeded", result.success, result.message)

        # 8. Verify PDF
        _sep("8. Verify PDF exists")
        check(
            "PDF file on disk",
            pdf_path.exists() and pdf_path.stat().st_size > 0,
            str(pdf_path),
        )

        # 9. Close document
        _sep("9. Close document")
        result = agent.execute(commands.CLOSE_CURRENT_DOCUMENT)
        check("close_current_document succeeded", result.success, result.message)

        # 10. Close Word
        _sep("10. Close Word")
        result = agent.execute(commands.CLOSE_WORD)
        check("close_word succeeded", result.success, result.message)

        # ==============================================================
        # VALIDATION / ERROR TESTS
        # ==============================================================

        _sep("11. Validation: missing text")
        result = agent.execute(commands.TYPE_TEXT, {})
        check(
            "Clarification required for missing text",
            result.status == WordAgentStatus.CLARIFICATION_REQUIRED,
            result.message,
        )
        check(
            "missing_parameters includes 'text'",
            "text" in result.missing_parameters,
            str(result.missing_parameters),
        )

        _sep("12. Validation: missing path")
        result = agent.execute(commands.SAVE_DOCX, {})
        check(
            "Clarification required for missing path",
            result.status == WordAgentStatus.CLARIFICATION_REQUIRED,
            result.message,
        )

        _sep("13. Validation: invalid table dimensions")
        # Start Word and create a document for this test.
        result = agent.execute(commands.OPEN_WORD)
        check("Word started for validation test", result.success, result.message)

        result = agent.execute(commands.CREATE_BLANK_DOCUMENT)
        check(
            "Validation document created",
            result.success,
            result.message,
        )

        result = agent.execute(
            commands.CREATE_TABLE,
            {"rows": 0, "columns": 3},
        )
        check(
            "Failure for invalid table (0 rows)",
            not result.success,
            result.message,
        )

        _sep("14. Validation: unsupported action")
        result = agent.execute("totally_fake_action")
        check(
            "Unsupported action result",
            result.status == WordAgentStatus.UNSUPPORTED,
            result.message,
        )

        _sep("15. Validation: nonexistent document path")
        result = agent.execute(
            commands.OPEN_EXISTING_DOCUMENT,
            {"path": "C:/nonexistent/fake.docx"},
        )
        check(
            "Failure for nonexistent path",
            not result.success,
            result.message,
        )

        _sep("16. Validation: missing table params")
        result = agent.execute(commands.CREATE_TABLE, {})
        check(
            "Clarification for missing rows/columns",
            result.status == WordAgentStatus.CLARIFICATION_REQUIRED,
            result.message,
        )

        _sep("17. Validation: missing find text")
        result = agent.execute(commands.FIND, {})
        check(
            "Clarification for missing find text",
            result.status == WordAgentStatus.CLARIFICATION_REQUIRED,
            result.message,
        )

        _sep("18. Validation: missing replace params")
        result = agent.execute(commands.REPLACE, {})
        check(
            "Clarification for missing replace params",
            result.status == WordAgentStatus.CLARIFICATION_REQUIRED,
            result.message,
        )

        _sep("19. Validation: invalid font size")
        result = agent.execute(
            commands.FONT_SIZE,
            {"size": "abc"},
        )
        check(
            "Failure for non-numeric font size",
            not result.success,
            result.message,
        )

        _sep("20. Validation: missing font name")
        result = agent.execute(commands.FONT, {})
        check(
            "Clarification for missing font name",
            result.status == WordAgentStatus.CLARIFICATION_REQUIRED,
            result.message,
        )

    except Exception as exc:
        failed += 1
        print(f"\n[ERROR] UNEXPECTED ERROR: {exc}")
        import traceback

        traceback.print_exc()

    finally:
        # Always attempt to close the document and Word application.
        try:
            agent._automation.close_document()
        except Exception as exc:
            print(f"[CLEANUP WARNING] Could not close Word document: {exc}")

        try:
            agent._automation.close_word()
        except Exception as exc:
            print(f"[CLEANUP WARNING] Could not close Word application: {exc}")

        # Remove temporary files.
        for path in (docx_path, pdf_path):
            try:
                path.unlink(missing_ok=True)
            except Exception as exc:
                print(f"[CLEANUP WARNING] Could not remove {path}: {exc}")

        try:
            tmp_dir.rmdir()
        except Exception as exc:
            print(f"[CLEANUP WARNING] Could not remove temp directory {tmp_dir}: {exc}")

    # ==============================================================
    # SUMMARY
    # ==============================================================

    _sep("SUMMARY")
    total = passed + failed
    print(f"  Total : {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")

    if failed == 0:
        print("\nALL TESTS PASSED.")
    else:
        print(f"\n{failed} test(s) FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
