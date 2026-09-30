"""Queue-backed orchestration for speaking incrementally generated text."""

from __future__ import annotations

import queue
import threading
import time


class StreamingTTSManager:
    """Turn streamed text into ordered, sentence-sized TTS requests.

    The producer may call :meth:`add_chunk` as quickly as an LLM yields
    text. A dedicated consumer thread serializes requests to the existing
    ``TextToSpeech`` object, whose ``speak()`` method intentionally cancels
    any currently speaking request.
    """

    _STOP = object()

    def __init__(
        self,
        tts,
        *,
        max_buffer_chars=160,
    ):
        self.tts = tts
        self.max_buffer_chars = max(20, int(max_buffer_chars))

        self._lock = threading.RLock()
        self._idle_condition = threading.Condition(self._lock)
        self._queue = queue.Queue()
        self._generation = 0
        self._active_generation = None
        self._buffer = ""
        self._speaking_generation = None
        self._closed = False

        self._consumer = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="DHEEPTHI-Streaming-TTS",
        )
        self._consumer.start()

    def start_session(self):
        """Start and return a new streaming speech session identifier."""

        with self._lock:
            has_active_session = self._active_generation is not None

        if has_active_session:
            self.stop()

        with self._lock:
            if self._closed:
                return None

            self._generation += 1
            self._active_generation = self._generation
            self._buffer = ""
            return self._active_generation

    def add_chunk(
        self,
        text,
        session_id=None,
    ):
        """Accept an incremental text chunk for the active session.

        Returns ``False`` when the chunk belongs to a cancelled or stale
        session. The method never waits for TTS playback.
        """

        if text is None:
            return False

        text = str(text)

        if not text.strip():
            return False

        with self._lock:
            generation = (
                self._active_generation
                if session_id is None
                else session_id
            )

            if (
                self._closed
                or generation is None
                or generation != self._active_generation
            ):
                return False

            self._buffer += text
            sentences, self._buffer = self._extract_ready_text(
                self._buffer,
                flush=False,
            )

            for sentence in sentences:
                self._queue.put((generation, sentence))

            self._idle_condition.notify_all()

        return True

    def finish(
        self,
        session_id=None,
    ):
        """Flush a session's final partial sentence without waiting for it."""

        with self._lock:
            generation = (
                self._active_generation
                if session_id is None
                else session_id
            )

            if (
                self._closed
                or generation is None
                or generation != self._active_generation
            ):
                return False

            sentences, self._buffer = self._extract_ready_text(
                self._buffer,
                flush=True,
            )

            for sentence in sentences:
                self._queue.put((generation, sentence))

            self._idle_condition.notify_all()

        return True

    def consume_stream(
        self,
        chunks,
        session_id=None,
    ):
        """Feed an iterable such as ``GeminiClient.generate_response_stream``.

        This helper does not wait for queued speech, so generation and
        playback remain pipelined. It returns the active session ID.
        """

        if session_id is None:
            session_id = self.start_session()

        if session_id is None:
            return None

        for chunk in chunks:
            if not self.add_chunk(chunk, session_id):
                break

        self.finish(session_id)
        return session_id

    def stop(self):
        """Cancel the active session and stop existing TTS playback."""

        with self._lock:
            self._generation += 1
            self._active_generation = None
            self._buffer = ""
            self._clear_queue()
            self._idle_condition.notify_all()

        try:
            self.tts.stop()
        except Exception:
            pass

    cancel = stop

    def wait_until_idle(self, timeout=None):
        """Wait for queued speech to finish; primarily useful to tests."""

        deadline = (
            None
            if timeout is None
            else time.monotonic() + max(0, timeout)
        )

        with self._idle_condition:
            while (
                self._queue.unfinished_tasks > 0
                or self._speaking_generation is not None
            ):
                if deadline is None:
                    self._idle_condition.wait()
                    continue

                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    return False

                self._idle_condition.wait(remaining)

        return True

    def close(self):
        """Stop playback and terminate the private consumer thread."""

        with self._lock:
            if self._closed:
                return

            self._closed = True

        self.stop()
        self._queue.put(self._STOP)

        if self._consumer is not threading.current_thread():
            self._consumer.join(timeout=2)

    def _consume_loop(self):
        while True:
            item = self._queue.get()

            try:
                if item is self._STOP:
                    return

                generation, text = item

                with self._lock:
                    if (
                        self._closed
                        or generation != self._active_generation
                    ):
                        continue

                    self._speaking_generation = generation
                    playback = self.tts.speak(text)

                self._wait_for_playback(generation, playback)

            finally:
                self._queue.task_done()

                with self._idle_condition:
                    self._speaking_generation = None
                    self._idle_condition.notify_all()

    def _wait_for_playback(
        self,
        generation,
        playback,
    ):
        """Wait for one existing TextToSpeech request without blocking feeds."""

        if playback is not None and hasattr(playback, "join"):
            while playback.is_alive():
                playback.join(timeout=0.05)

                if not self._is_active(generation):
                    return

            return

        while self._is_active(generation):
            try:
                speaking = self.tts.speaking()
            except Exception:
                return

            if not speaking:
                return

            time.sleep(0.02)

    def _is_active(self, generation):
        with self._lock:
            return (
                not self._closed
                and generation == self._active_generation
            )

    def _clear_queue(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return
            else:
                self._queue.task_done()

    def _extract_ready_text(
        self,
        buffer,
        *,
        flush,
    ):
        sentences = []

        while buffer:
            boundary = self._find_boundary(buffer)

            if boundary is not None:
                end, consume = boundary
                sentence = buffer[:end].strip()
                buffer = buffer[consume:]

                if sentence:
                    sentences.append(sentence)

                continue

            if len(buffer.strip()) >= self.max_buffer_chars:
                split_at = self._find_clause_split(buffer)

                if split_at is not None:
                    sentence = buffer[:split_at].strip()
                    buffer = buffer[split_at:]

                    if sentence:
                        sentences.append(sentence)

                    continue

            break

        if flush:
            sentence = buffer.strip()

            if sentence:
                sentences.append(sentence)

            buffer = ""

        return sentences, buffer

    @staticmethod
    def _find_boundary(text):
        for index, character in enumerate(text):
            if character in ".!?…":
                next_index = index + 1

                if (
                    next_index == len(text)
                    or text[next_index].isspace()
                ):
                    return next_index, next_index

            if character == "\n":
                return index, index + 1

        return None

    def _find_clause_split(self, text):
        limit = min(len(text), self.max_buffer_chars)
        split_at = text.rfind(" ", 0, limit + 1)

        if split_at > 0:
            return split_at

        if len(text) >= self.max_buffer_chars:
            return self.max_buffer_chars

        return None
