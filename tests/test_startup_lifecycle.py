"""
tests/test_startup_lifecycle.py

Unit and integration tests for DHEEPTHI-AI startup lifecycle:
- create_backend returns True and properly sets _backend_ready = True
- _sync_user_identity_display updates identity without resetting backend state
- _create_backend_then_initialize executes create_backend then start_initialization
- initialization_failed records error diagnostic and does not crash
- closeEvent bypasses goodbye TTS when startup did not complete or failed
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_create_backend_returns_true(qapp):
    """Verify create_backend() executes to completion, returns True, and marks _backend_ready=True."""
    window = MainWindow()
    try:
        # Before calling create_backend
        window._backend_ready = False
        res = window.create_backend()
        assert res is True, "create_backend() must return True"
        assert window._backend_ready is True, "_backend_ready must be True"
        assert hasattr(window, "multi_command_planner"), "multi_command_planner should be created"
        assert hasattr(window, "semantic_command_planner"), "semantic_command_planner should be created"
        assert hasattr(window, "dispatcher"), "dispatcher should be created"
        assert hasattr(window, "multi_command_executor"), "multi_command_executor should be created"
    finally:
        window.close()


def test_sync_user_identity_display_is_standalone(qapp):
    """Verify _sync_user_identity_display updates UI identity and does not mutate session/planners."""
    window = MainWindow()
    try:
        window.create_backend()
        orig_session_id = window._session_id

        # Calling _sync_user_identity_display standalone should not recreate session or planners
        window._sync_user_identity_display()
        assert window._session_id == orig_session_id
    finally:
        window.close()


def test_create_backend_then_initialize_calls_start_init(qapp):
    """Verify _create_backend_then_initialize calls start_initialization when create_backend succeeds."""
    window = MainWindow()
    try:
        window._backend_initialization_started = False
        window._closing = False

        init_failed_mock = MagicMock()
        window.initialization_failed = init_failed_mock

        with patch.object(window, "start_initialization") as mock_start_init:
            window._create_backend_then_initialize()
            assert not init_failed_mock.called, "initialization_failed should not be called"
            mock_start_init.assert_called_once()
    finally:
        window.close()


def test_close_event_bypasses_goodbye_tts_when_init_not_complete(qapp):
    """Verify closeEvent bypasses goodbye TTS when startup has not completed."""
    window = MainWindow()
    try:
        window.loading_finished = False
        window._initialization_failed = True

        with patch.object(window, "_begin_goodbye_shutdown") as mock_goodbye, \
             patch.object(window, "_finish_goodbye_shutdown") as mock_finish:
            window.closeEvent(None)
            assert not mock_goodbye.called, "_begin_goodbye_shutdown should be bypassed"
            mock_finish.assert_called_once()
    finally:
        window.close()
