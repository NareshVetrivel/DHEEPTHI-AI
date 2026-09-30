"""
voice/text_to_speech.py

ASTRA-AI
Premium Multi-Provider Text To Speech Manager

Streaming/cancellation-aware provider manager.

Provider order
--------------
1. Microsoft Edge Neural TTS
2. Piper Offline TTS
3. Windows SAPI / pyttsx3

The existing provider engines remain unchanged. This manager adds
request-generation cancellation, explicit stop state, safe sequential
provider fallback, and short-lived worker cleanup so it can be used by
StreamingTTSManager without allowing stale chunks to take control.
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal

from voice.edge_tts_engine import EdgeTTSEngine


class TextToSpeech(QObject):
    """Central, cancellation-aware TTS manager."""

    speech_started = Signal(str)
    speech_finished = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.edge_engine = EdgeTTSEngine()
        self.piper_engine = None
        self.pyttsx3_engine = None
        self._load_fallback_engines()

        # Backward compatibility for callers that use ``engine``.
        self.engine = self.edge_engine

        self.enabled = True
        self._closing = False
        self.lock = threading.RLock()
        self.current_thread = None
        self._speaking = False
        self._stop_event = threading.Event()
        self._request_id = 0

    # ======================================================
    # PROVIDERS
    # ======================================================

    def _load_fallback_engines(self):
        try:
            from voice.piper_tts_engine import PiperTTSEngine
            self.piper_engine = PiperTTSEngine()
            print("Piper TTS Engine Ready.")
        except Exception as error:
            self.piper_engine = None
            print(f"Piper TTS Engine Unavailable : {error}")

        try:
            from voice.pyttsx3_tts_engine import Pyttsx3TTSEngine
            self.pyttsx3_engine = Pyttsx3TTSEngine()
            print("pyttsx3 TTS Engine Ready.")
        except Exception as error:
            self.pyttsx3_engine = None
            print(f"pyttsx3 TTS Engine Unavailable : {error}")

    def _providers(self):
        return (
            ("Edge TTS", self.edge_engine),
            ("Piper TTS", self.piper_engine),
            ("Windows pyttsx3", self.pyttsx3_engine),
        )

    # ======================================================
    # REQUEST LIFETIME
    # ======================================================

    def _is_request_active(self, request_id: int) -> bool:
        if self._closing or self._stop_event.is_set():
            return False
        with self.lock:
            return request_id == self._request_id

    def _invalidate_request(self, stop_providers=True):
        with self.lock:
            self._request_id += 1
            self._stop_event.set()
            self._speaking = False

        if stop_providers:
            self._stop_all_providers()

    def _stop_all_providers(self):
        for _name, engine in self._providers():
            try:
                if engine is not None and hasattr(engine, "stop"):
                    engine.stop()
            except Exception:
                pass

    # ======================================================
    # SPEAK
    # ======================================================

    def speak(self, text: str):
        """Start one asynchronous speech request.

        Starting a new request immediately invalidates and stops the
        previous request. This is important for streamed sentence chunks:
        the StreamingTTSManager serializes normal playback, while this
        method still provides a hard cancellation boundary for barge-in.
        """
        if self._closing or not self.enabled:
            return None
        if text is None:
            return None

        text = str(text).strip()
        if not text:
            return None

        with self.lock:
            self._request_id += 1
            request_id = self._request_id
            self._stop_event.set()

        # Stop old provider audio outside the lock. Provider stop methods
        # may perform I/O or wait for their own worker to exit.
        self._stop_all_providers()

        with self.lock:
            if self._closing or request_id != self._request_id:
                return None

            self._stop_event.clear()
            self._speaking = True

            worker = threading.Thread(
                target=self._speak_worker,
                args=(request_id, text),
                daemon=True,
                name=f"ASTRA-TTS-{request_id}",
            )
            self.current_thread = worker

        worker.start()
        return worker

    def _speak_worker(self, request_id: int, text: str):
        completed_successfully = False
        started_emitted = False

        try:
            if not self._is_request_active(request_id):
                return

            self.speech_started.emit(text)
            started_emitted = True
            print("[TTS] Speech started.")

            for provider_name, engine in self._providers():
                if not self._is_request_active(request_id):
                    return
                if engine is None:
                    continue

                print(f"\nTTS Provider : {provider_name}")

                try:
                    speak_blocking = getattr(engine, "speak_blocking", None)
                    if not callable(speak_blocking):
                        print(f"{provider_name} has no speak_blocking().")
                        continue

                    success = bool(speak_blocking(text))

                    if not self._is_request_active(request_id):
                        return

                    if success:
                        completed_successfully = True
                        print(f"TTS Success : {provider_name}")
                        return

                    print(
                        f"{provider_name} failed. "
                        "Trying next TTS provider..."
                    )

                except Exception as error:
                    if self._is_request_active(request_id):
                        print(f"{provider_name} Error : {error}")

            if self._is_request_active(request_id):
                print("\nTTS Error : All TTS providers failed.")

        finally:
            should_emit_finished = False

            with self.lock:
                if request_id == self._request_id:
                    self._speaking = False
                    if self.current_thread is threading.current_thread():
                        self.current_thread = None
                    should_emit_finished = (
                        started_emitted and not self._closing
                    )

            if should_emit_finished:
                self.speech_finished.emit(completed_successfully)
                print(
                    "[TTS] Speech finished. "
                    f"Success : {completed_successfully}"
                )

    # ======================================================
    # STOP / CANCELLATION
    # ======================================================

    def stop(self):
        """Immediately invalidate the current request and stop audio."""
        self._invalidate_request(stop_providers=True)

    def cancel(self):
        """Alias used by streaming/cancellation callers."""
        self.stop()

    # ======================================================
    # ENABLE / STATUS
    # ======================================================

    def set_enabled(self, enabled=True):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop()

    def speaking(self):
        with self.lock:
            if self._speaking:
                return True

        for _name, engine in self._providers():
            try:
                if (
                    engine is not None
                    and hasattr(engine, "speaking")
                    and engine.speaking()
                ):
                    return True
            except Exception:
                continue
        return False

    def wait_until_done(self):
        while self.speaking():
            if self._closing:
                break
            time.sleep(0.02)

    def wait_until_idle(self, timeout=None):
        """Wait for current TTS playback to become idle.

        Returns True when idle, False when the timeout expires.
        """
        deadline = None
        if timeout is not None:
            deadline = time.monotonic() + max(0.0, float(timeout))

        while self.speaking():
            if self._closing:
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.02)
        return True

    # ======================================================
    # VOICE / RATE / VOLUME
    # ======================================================

    def set_voice(self, voice):
        for _name, engine in self._providers():
            try:
                if engine is not None and hasattr(engine, "set_voice"):
                    engine.set_voice(voice)
            except Exception:
                continue

    def set_rate(self, rate):
        for _name, engine in self._providers():
            try:
                if engine is not None and hasattr(engine, "set_rate"):
                    engine.set_rate(rate)
            except Exception:
                continue

    def set_volume(self, volume):
        for _name, engine in self._providers():
            try:
                if engine is not None and hasattr(engine, "set_volume"):
                    engine.set_volume(volume)
            except Exception:
                continue

    # ======================================================
    # CLEANUP
    # ======================================================

    def close(self):
        with self.lock:
            if self._closing:
                return
            self._closing = True
            self._request_id += 1
            self._stop_event.set()
            self._speaking = False

        self._stop_all_providers()

        worker = self.current_thread
        if (
            worker is not None
            and worker.is_alive()
            and worker is not threading.current_thread()
        ):
            try:
                worker.join(timeout=1.0)
            except Exception:
                pass

        for _name, engine in self._providers():
            try:
                if engine is not None and hasattr(engine, "close"):
                    engine.close()
            except Exception:
                pass

        with self.lock:
            self.edge_engine = None
            self.piper_engine = None
            self.pyttsx3_engine = None
            self.engine = None
            self.current_thread = None
            self._speaking = False

        print("TextToSpeech shutdown completed.")
