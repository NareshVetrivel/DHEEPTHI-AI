"""Focused tests for queue-backed streamed text-to-speech orchestration."""

from __future__ import annotations

import threading

import pytest

from voice.streaming_tts_manager import StreamingTTSManager


class RecordingTTS:
    def __init__(self):
        self.spoken = []
        self.started = threading.Event()
        self.stop_calls = 0

    def speak(self, text):
        self.spoken.append(text)
        self.started.set()
        return None

    def speaking(self):
        return False

    def stop(self):
        self.stop_calls += 1


class BlockingTTS(RecordingTTS):
    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def speak(self, text):
        self.spoken.append(text)
        self.started.set()
        worker = threading.Thread(
            target=self.release.wait,
            daemon=True,
        )
        worker.start()
        return worker

    def stop(self):
        super().stop()
        self.release.set()


@pytest.fixture
def manager():
    instance = StreamingTTSManager(RecordingTTS(), max_buffer_chars=40)
    yield instance
    instance.close()


def test_first_complete_sentence_speaks_before_stream_completion(manager):
    session = manager.start_session()

    manager.add_chunk("First sentence.", session)

    assert manager.tts.started.wait(1)
    assert manager.tts.spoken == ["First sentence."]

    manager.add_chunk(" Later sentence.", session)
    manager.finish(session)

    assert manager.wait_until_idle(1)
    assert manager.tts.spoken == ["First sentence.", "Later sentence."]


def test_multiple_sentences_preserve_order_without_duplication(manager):
    session = manager.start_session()

    manager.add_chunk("One. Two! Three?", session)
    manager.finish(session)

    assert manager.wait_until_idle(1)
    assert manager.tts.spoken == ["One.", "Two!", "Three?"]


def test_tiny_chunks_are_combined_and_empty_chunks_are_ignored(manager):
    session = manager.start_session()

    assert not manager.add_chunk("", session)
    assert not manager.add_chunk("   ", session)

    for chunk in ("Hel", "lo ", "there", "."):
        assert manager.add_chunk(chunk, session)

    manager.finish(session)

    assert manager.wait_until_idle(1)
    assert manager.tts.spoken == ["Hello there."]


def test_partial_text_is_flushed_when_the_stream_finishes(manager):
    session = manager.start_session()

    manager.add_chunk("An unfinished final thought", session)
    manager.finish(session)

    assert manager.wait_until_idle(1)
    assert manager.tts.spoken == ["An unfinished final thought"]


def test_long_clause_is_emitted_without_sentence_punctuation():
    tts = RecordingTTS()
    manager = StreamingTTSManager(tts, max_buffer_chars=24)

    try:
        session = manager.start_session()
        manager.add_chunk("one two three four five six", session)

        assert tts.started.wait(1)
        assert tts.spoken == ["one two three four five"]

        manager.finish(session)
        assert manager.wait_until_idle(1)
        assert tts.spoken == ["one two three four five", "six"]
    finally:
        manager.close()


def test_cancellation_clears_pending_speech():
    tts = BlockingTTS()
    manager = StreamingTTSManager(tts, max_buffer_chars=40)

    try:
        session = manager.start_session()
        manager.add_chunk("First. Second.", session)

        assert tts.started.wait(1)
        manager.cancel()

        assert manager.wait_until_idle(1)
        assert tts.spoken == ["First."]
        assert tts.stop_calls >= 1
    finally:
        manager.close()


def test_stale_session_text_is_never_spoken_after_a_new_session():
    tts = BlockingTTS()
    manager = StreamingTTSManager(tts, max_buffer_chars=40)

    try:
        first_session = manager.start_session()
        manager.add_chunk("Old first. Old queued.", first_session)

        assert tts.started.wait(1)
        second_session = manager.start_session()

        assert not manager.add_chunk("Ignored.", first_session)
        assert manager.add_chunk("New response.", second_session)
        manager.finish(second_session)

        assert manager.wait_until_idle(1)
        assert tts.spoken == ["Old first.", "New response."]
    finally:
        manager.close()


def test_consume_stream_feeds_chunks_without_waiting_for_each_playback(manager):
    session = manager.consume_stream(["One.", " Two."])

    assert session is not None
    assert manager.wait_until_idle(1)
    assert manager.tts.spoken == ["One.", "Two."]
