"""
Automated File System Agent Integration Test

ASTRA-AI V1

Tests
-----
• Resolve File
• Resolve Folder
• Create Folder
• Create File
• Rename File
• Copy File
• Move File
• Rename Folder
• Copy Folder
• Move Folder
• Delete File
• Delete Folder
• Generic Execute API

Notes
-----
This test creates an isolated temporary workspace
inside the ASTRA-AI project.

No manual menu interaction is required.
"""

from __future__ import annotations

import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.file_finder import FileFinder
from automation.file_manager import FileManager
from automation.folder_manager import FolderManager
from automation.file_system_agent import FileSystemAgent


# ==========================================================
# TEST WORKSPACE
# ==========================================================

TEST_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "runtime_file_system_agent"
)

SOURCE_FOLDER = (
    TEST_ROOT
    / "source_folder"
)

COPY_FOLDER = (
    TEST_ROOT
    / "copy_destination"
)

MOVE_FOLDER = (
    TEST_ROOT
    / "move_destination"
)

SOURCE_FILE = (
    SOURCE_FOLDER
    / "test_file.txt"
)

RENAMED_FILE = (
    SOURCE_FOLDER
    / "renamed_test_file.txt"
)

COPIED_FILE = (
    COPY_FOLDER
    / "renamed_test_file.txt"
)

MOVED_FILE = (
    MOVE_FOLDER
    / "renamed_test_file.txt"
)

RENAMED_SOURCE_FOLDER = (
    TEST_ROOT
    / "renamed_source_folder"
)

COPIED_SOURCE_FOLDER = (
    COPY_FOLDER
    / "renamed_source_folder"
)

MOVED_SOURCE_FOLDER = (
    MOVE_FOLDER
    / "renamed_source_folder"
)


# ==========================================================
# RESULT TRACKING
# ==========================================================

results = []


def record(
    name: str,
    passed: bool,
    message: str = "",
):
    """
    Record and display one test result.
    """

    status = "PASS" if passed else "FAIL"

    results.append(
        (
            name,
            passed,
            message,
        )
    )

    if message:

        print(
            f"[{status}] {name} -> {message}"
        )

    else:

        print(
            f"[{status}] {name}"
        )


def result_success(result):
    """
    Safely determine whether an agent result succeeded.
    """

    return (
        isinstance(result, dict)
        and result.get("success") is True
    )


def safe_remove_test_workspace():
    """
    Remove the isolated test workspace.
    """

    try:

        if TEST_ROOT.exists():

            shutil.rmtree(
                TEST_ROOT
            )

    except Exception as error:

        print(
            f"\nCleanup Warning : {error}"
        )


def prepare_workspace():
    """
    Create a clean isolated test workspace.
    """

    safe_remove_test_workspace()

    TEST_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    SOURCE_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    COPY_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    MOVE_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )


# ==========================================================
# MAIN TEST
# ==========================================================

def main():

    global results

    results = []

    print()
    print("=" * 60)
    print("ASTRA FILE SYSTEM AGENT")
    print("AUTOMATED INTEGRATION TEST")
    print("=" * 60)

    print(
        f"\nTest Workspace :\n{TEST_ROOT}"
    )

    prepare_workspace()

    agent = FileSystemAgent(
        file_finder=FileFinder(),
        file_manager=FileManager(),
        folder_manager=FolderManager(),
    )

    try:

        # ==================================================
        # 1. CREATE FOLDER
        # ==================================================

        print("\n[01] Create Folder")

        result = agent.execute(
            "create_folder",
            {
                "folder_path": str(
                    SOURCE_FOLDER
                )
            }
        )

        record(
            "Create Folder",
            result_success(result),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 2. CREATE FILE
        # ==================================================

        print("\n[02] Create File")

        result = agent.execute(
            "create_file",
            {
                "file_path": str(
                    SOURCE_FILE
                )
            }
        )

        record(
            "Create File",
            result_success(result)
            and SOURCE_FILE.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 3. RESOLVE FILE
        # ==================================================

        print("\n[03] Resolve File")

        result = agent.resolve_file(
            str(SOURCE_FILE)
        )

        resolved_file = (
            str(result)
            if result
            else None
        )

        record(
            "Resolve File",
            (
                resolved_file is not None
                and Path(resolved_file).exists()
                and Path(resolved_file).is_file()
            ),
            (
                resolved_file
                if resolved_file
                else "File could not be resolved."
            ),
        )

        # ==================================================
        # 4. RESOLVE FOLDER
        # ==================================================

        print("\n[04] Resolve Folder")

        result = agent.resolve_folder(
            str(SOURCE_FOLDER)
        )

        resolved_folder = (
            str(result)
            if result
            else None
        )

        record(
            "Resolve Folder",
            (
                resolved_folder is not None
                and Path(resolved_folder).exists()
                and Path(resolved_folder).is_dir()
            ),
            (
                resolved_folder
                if resolved_folder
                else "Folder could not be resolved."
            ),
        )

        # ==================================================
        # 5. RENAME FILE
        # ==================================================

        print("\n[05] Rename File")

        result = agent.execute(
            "rename_file",
            {
                "source": str(
                    SOURCE_FILE
                ),
                "new_name": RENAMED_FILE.name,
            }
        )

        record(
            "Rename File",
            result_success(result)
            and RENAMED_FILE.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 6. COPY FILE
        # ==================================================

        print("\n[06] Copy File")

        result = agent.execute(
            "copy_file",
            {
                "source": str(
                    RENAMED_FILE
                ),
                "destination": str(
                    COPY_FOLDER
                ),
            }
        )

        record(
            "Copy File",
            result_success(result)
            and COPIED_FILE.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 7. MOVE FILE
        # ==================================================

        print("\n[07] Move File")

        result = agent.execute(
            "move_file",
            {
                "source": str(
                    COPIED_FILE
                ),
                "destination": str(
                    MOVE_FOLDER
                ),
            }
        )

        record(
            "Move File",
            result_success(result)
            and MOVED_FILE.exists()
            and not COPIED_FILE.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 8. RENAME FOLDER
        # ==================================================

        print("\n[08] Rename Folder")

        result = agent.execute(
            "rename_folder",
            {
                "source": str(
                    SOURCE_FOLDER
                ),
                "new_name": RENAMED_SOURCE_FOLDER.name,
            }
        )

        record(
            "Rename Folder",
            result_success(result)
            and RENAMED_SOURCE_FOLDER.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 9. COPY FOLDER
        # ==================================================

        print("\n[09] Copy Folder")

        result = agent.execute(
            "copy_folder",
            {
                "source": str(
                    RENAMED_SOURCE_FOLDER
                ),
                "destination": str(
                    COPY_FOLDER
                ),
            }
        )

        record(
            "Copy Folder",
            result_success(result)
            and COPIED_SOURCE_FOLDER.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 10. MOVE FOLDER
        # ==================================================

        print("\n[10] Move Folder")

        result = agent.execute(
            "move_folder",
            {
                "source": str(
                    COPIED_SOURCE_FOLDER
                ),
                "destination": str(
                    MOVE_FOLDER
                ),
            }
        )

        record(
            "Move Folder",
            result_success(result)
            and MOVED_SOURCE_FOLDER.exists()
            and not COPIED_SOURCE_FOLDER.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 11. DELETE FILE
        # ==================================================

        print("\n[11] Delete File")

        # The agent may ask for confirmation.
        # For automated testing, temporarily provide "yes".

        import builtins

        original_input = builtins.input

        try:

            builtins.input = (
                lambda prompt="": "yes"
            )

            result = agent.execute(
                "delete_file",
                {
                    "source": str(
                        MOVED_FILE
                    )
                }
            )

        finally:

            builtins.input = original_input

        record(
            "Delete File",
            result_success(result)
            and not MOVED_FILE.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

        # ==================================================
        # 12. DELETE FOLDER
        # ==================================================

        print("\n[12] Delete Folder")

        # The copied/moved folder is now inside
        # MOVE_FOLDER. Delete the moved folder.

        import builtins

        original_input = builtins.input

        try:

            builtins.input = (
                lambda prompt="": "yes"
            )

            result = agent.execute(
                "delete_folder",
                {
                    "source": str(
                        MOVED_SOURCE_FOLDER
                    )
                }
            )

        finally:

            builtins.input = original_input

        record(
            "Delete Folder",
            result_success(result)
            and not MOVED_SOURCE_FOLDER.exists(),
            result.get("message", "")
            if isinstance(result, dict)
            else str(result)
        )

    except Exception as error:

        print()
        print(
            f"TEST EXECUTION ERROR : {error}"
        )

        record(
            "Unexpected Test Error",
            False,
            str(error)
        )

    finally:

        agent.close()

        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(
            1
            for _, status, _ in results
            if status
        )

        failed = sum(
            1
            for _, status, _ in results
            if not status
        )

        for name, status, message in results:

            if status:

                print(
                    f"[PASS] {name}"
                )

            else:

                print(
                    f"[FAIL] {name}"
                )

                if message:

                    print(
                        f"       {message}"
                    )

        print("-" * 60)

        print(
            f"Passed : {passed}"
        )

        print(
            f"Failed : {failed}"
        )

        print("-" * 60)

        if failed == 0:

            print(
                "FILE SYSTEM AGENT TEST : PASSED"
            )

        else:

            print(
                "FILE SYSTEM AGENT TEST : FAILED"
            )

        print("=" * 60)

        # ----------------------------------------------
        # Cleanup
        # ----------------------------------------------

        safe_remove_test_workspace()

        print(
            "\nTest workspace cleaned."
        )


if __name__ == "__main__":

    main()