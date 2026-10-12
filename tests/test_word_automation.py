"""
test_word_automation — Automated tests for the Word COM automation foundation.

Uses temporary directories so no permanent files are left behind.
Cleanup runs even when assertions or exceptions occur.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# ── Ensure project root is importable ─────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from productivity_agent.word.automation import WordAutomation, WordAutomationError
from productivity_agent.word.verifier import WordVerifier


def _separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def run_tests() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="astra_word_test_")
    docx_path = Path(tmp_dir) / "test_document.docx"
    pdf_path = Path(tmp_dir) / "test_document.pdf"
    wa = WordAutomation(visible=False)
    verifier = WordVerifier()

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
        # ── 1. Start / connect Word ──────────────────────────────────
        _separator("1. Start Word")
        wa.start_word()
        check("Word application started", wa._word is not None)

        # ── 2. Create document ───────────────────────────────────────
        _separator("2. Create document")
        wa.create_document()
        check("Document created", wa._document is not None)

        # ── 3. Insert text ───────────────────────────────────────────
        _separator("3. Insert text")
        test_text = "ASTRA-AI Word Automation Test"
        wa.type_text(test_text)
        check("Text typed without error", True)

        # ── 4. Read text ─────────────────────────────────────────────
        _separator("4. Read document text")
        content = wa.read_document()
        found = test_text in content
        check("Inserted text is readable", found, f"got: {content!r:.120}")

        # ── 5. Save DOCX ─────────────────────────────────────────────
        _separator("5. Save as DOCX")
        wa.save_as_docx(docx_path)
        check("save_as_docx() completed", True)

        # ── 6. Verify DOCX exists ────────────────────────────────────
        _separator("6. Verify DOCX exists")
        docx_ok = verifier.docx_exists(docx_path)
        check("DOCX file exists on disk", docx_ok, str(docx_path))
        docx_notempty = verifier.verify_file_not_empty(docx_path)
        check("DOCX file is non-empty", docx_notempty)

        # ── 7. Save / export PDF ─────────────────────────────────────
        _separator("7. Export as PDF")
        wa.save_as_pdf(pdf_path)
        check("save_as_pdf() completed", True)

        # ── 8. Verify PDF exists ─────────────────────────────────────
        _separator("8. Verify PDF exists")
        pdf_ok = verifier.pdf_exists(pdf_path)
        check("PDF file exists on disk", pdf_ok, str(pdf_path))
        pdf_notempty = verifier.verify_file_not_empty(pdf_path)
        check("PDF file is non-empty", pdf_notempty)

        # ── 9. Close document ────────────────────────────────────────
        _separator("9. Close document")
        wa.close_document()
        check("Document closed", wa._document is None)

        # ── 10. Close Word ───────────────────────────────────────────
        _separator("10. Close Word")
        wa.close_word()
        check("Word application closed", wa._word is None)

    except Exception as exc:
        failed += 1
        print(f"\n[ERROR] UNEXPECTED ERROR: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        # ── Cleanup: make sure Word is closed ─────────────────────────
        try:
            wa.close_document()
        except Exception:
            pass
        try:
            wa.close_word()
        except Exception:
            pass

        # ── Cleanup: remove temp files ────────────────────────────────
        for f in [docx_path, pdf_path]:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            Path(tmp_dir).rmdir()
        except Exception:
            pass

    # ── Summary ───────────────────────────────────────────────────────
    _separator("SUMMARY")
    print(f"  Total : {passed + failed}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    if failed == 0:
        print("\nALL TESTS PASSED.")
    else:
        print(f"\n{failed} test(s) FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
