from pathlib import Path
import tempfile

import win32com.client


def main():
    word = None
    document = None

    output_path = Path(tempfile.gettempdir()) / "astra_word_test.docx"

    try:
        print("Starting Microsoft Word...")

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False

        print(f"Word Version: {word.Version}")

        # Create a new document
        document = word.Documents.Add()
        print("SUCCESS: New Word document created.")

        # Add content
        content = (
            "ASTRA-AI Word Productivity-Agent Test\n"
            "This document was created automatically by ASTRA-AI."
        )

        document.Content.Text = content
        print("SUCCESS: Text added to document.")

        # Save as DOCX
        document.SaveAs2(
            str(output_path),
            FileFormat=16,  # wdFormatDocumentDefault (.docx)
        )

        print(f"SUCCESS: Document saved to: {output_path}")

        # Verify file exists
        if output_path.exists():
            print("SUCCESS: File verification passed.")
        else:
            raise RuntimeError("Saved file was not found.")

        # Close document
        document.Close(SaveChanges=False)
        document = None

        print("SUCCESS: Document closed.")

        # Close Word
        word.Quit()
        word = None

        print("SUCCESS: Word closed.")
        print("\nALL WORD BASIC OPERATIONS PASSED.")

    except Exception as exc:
        print("\nFAILED: Word operation test failed.")
        print(f"ERROR: {exc}")

        if document is not None:
            try:
                document.Close(SaveChanges=False)
            except Exception:
                pass

        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass

        raise


if __name__ == "__main__":
    main()