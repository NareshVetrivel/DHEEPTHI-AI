"""Focused unit tests for GeminiClient streaming conversation replies."""

from __future__ import annotations

import threading

import pytest

from ai.gemini_client import GeminiClient


class FakeChunk:
    def __init__(self, text):
        self.text = text


class FailingStream:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error
        yield  # pragma: no cover


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content_stream(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


class FakeGeminiAPI:
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)


def make_client(*outcomes):
    """Build a GeminiClient instance without credentials or network I/O."""

    client = GeminiClient.__new__(GeminiClient)
    client.api_keys = ["key-one", "key-two"]
    client.current_key_index = 0
    client.model = "fake-model"
    client.history = []
    client.max_history_messages = 40
    client.context_messages = 12
    client.retry_delay_seconds = 0
    client.lock = threading.RLock()
    client.client = FakeGeminiAPI(outcomes)
    client._closing = False
    client._create_client = lambda: None

    return client


def test_stream_yields_chunks_in_order_and_commits_final_history():
    client = make_client(
        [FakeChunk("Vanakkam "), FakeChunk("da!")]
    )

    chunks = list(client.generate_response_stream("hello"))

    assert chunks == ["Vanakkam ", "da!"]
    assert client.get_history() == [
        {"role": "user", "text": "hello"},
        {"role": "assistant", "text": "Vanakkam da!"},
    ]


def test_stream_ignores_empty_chunks():
    client = make_client(
        [FakeChunk(""), FakeChunk("  "), FakeChunk("Useful reply")]
    )

    assert list(client.generate_response_stream("question")) == [
        "Useful reply"
    ]
    assert client.get_history()[-1] == {
        "role": "assistant",
        "text": "Useful reply",
    }


def test_cancellation_stops_further_yields_and_does_not_commit_history():
    cancel_event = threading.Event()

    def cancelling_stream():
        yield FakeChunk("First chunk")
        cancel_event.set()
        yield FakeChunk("Second chunk")

    client = make_client(cancelling_stream())

    assert list(
        client.generate_response_stream("interrupt me", cancel_event)
    ) == ["First chunk"]
    assert client.get_history() == []


def test_retryable_failure_rotates_key_before_any_text(monkeypatch):
    client = make_client(
        RuntimeError("429 quota exhausted"),
        [FakeChunk("Recovered")],
    )
    monkeypatch.setattr(client, "_retry_delay", lambda: None)

    assert list(client.generate_response_stream("retry please")) == [
        "Recovered"
    ]
    assert client.current_key_index == 1
    assert len(client.client.models.calls) == 2
    assert client.get_history() == [
        {"role": "user", "text": "retry please"},
        {"role": "assistant", "text": "Recovered"},
    ]


def test_stream_failure_does_not_commit_history():
    client = make_client(FailingStream(RuntimeError("bad request")))

    assert list(client.generate_response_stream("will fail")) == []
    assert client.get_history() == []


def test_stream_with_no_usable_text_does_not_commit_history():
    client = make_client([FakeChunk(""), FakeChunk("  ")])

    assert list(client.generate_response_stream("empty stream")) == []
    assert client.get_history() == []
