"""
voice/pyttsx3_tts_engine.py

ASTRA-AI
Windows Offline Text-To-Speech Engine

Provider
--------
Windows SAPI through pyttsx3

Fallback position
-----------------
1. Edge TTS
2. Piper TTS
3. pyttsx3 / Windows SAPI

Cancellation-safe implementation compatible with TextToSpeech
and StreamingTTSManager.
"""

from __future__ import annotations

import threading
import time

import pyttsx3


class Pyttsx3TTSEngine:
    """
    Windows SAPI based TTS engine.

    This is the final offline fallback provider.
    """

    def __init__(self):
        self.lock = threading.RLock()
        self.current_thread = None

        # Each blocking request gets a generation. A new request or
        # stop() invalidates older workers.
        self._generation = 0
        self.stop_event = threading.Event()

        self.is_speaking = False
        self._closed = False

        self.voice = None
        self.rate = 170
        self.volume = 1.0

        self.voices = []
        self.engine = None

        try:
            self.engine = pyttsx3.init()
            self.voices = self.engine.getProperty("voices") or []

            print(
                f"pyttsx3 voices detected : {len(self.voices)}"
            )

            selected_voice = self._find_female_voice()

            if selected_voice is not None:
                self.voice = selected_voice
                self.engine.setProperty("voice", selected_voice)
                print("pyttsx3 female voice selected.")
            elif self.voices:
                self.voice = self.voices[0].id
                self.engine.setProperty("voice", self.voice)
                print(
                    "pyttsx3 female voice not detected. "
                    "Using first available voice."
                )

            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)

        except Exception as error:
            self.engine = None
            self.voices = []
            print(f"pyttsx3 initialization error : {error}")

    # ======================================================
    # GENERATION / OWNERSHIP
    # ======================================================

    def _next_generation(self) -> int:
        with self.lock:
            self._generation += 1
            return self._generation

    def _is_generation_active(self, generation: int) -> bool:
        if self._closed:
            return False

        with self.lock:
            return generation == self._generation

    # ======================================================
    # FIND FEMALE VOICE
    # ======================================================

    def _find_female_voice(self):
        if not self.voices:
            return None

        female_keywords = [
            "female",
            "zira",
            "samantha",
            "hazel",
            "heera",
            "kalpana",
            "susan",
            "aria",
            "jenny",
            "neerja",
        ]

        for voice in self.voices:
            try:
                voice_id = str(
                    getattr(voice, "id", "")
                ).lower()

                voice_name = str(
                    getattr(voice, "name", "")
                ).lower()

                voice_description = str(
                    getattr(voice, "languages", "")
                ).lower()

                combined = (
                    voice_id
                    + " "
                    + voice_name
                    + " "
                    + voice_description
                )

                if any(
                    keyword in combined
                    for keyword in female_keywords
                ):
                    return voice.id

            except Exception:
                continue

        for voice in self.voices:
            try:
                gender = str(
                    getattr(voice, "gender", "")
                ).lower()

                if "female" in gender:
                    return voice.id

            except Exception:
                continue

        return None

    # ======================================================
    # BLOCKING SPEAK
    # ======================================================

    def speak_blocking(self, text):
        """
        Speak one text segment synchronously.

        Returns True only when the active generation completes
        normally. Cancellation/stale generations return False.
        """
        if self._closed or self.engine is None:
            return False

        if text is None:
            return False

        text = str(text).strip()

        if not text:
            return False

        generation = self._next_generation()

        with self.lock:
            self.stop_event.clear()
            self.is_speaking = True

        success = False

        try:
            if not self._is_generation_active(generation):
                return False

            if self.stop_event.is_set():
                return False

            # Apply settings for this request.
            if self.voice:
                self.engine.setProperty("voice", self.voice)

            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)

            self.engine.say(text)

            if (
                not self._is_generation_active(generation)
                or self.stop_event.is_set()
            ):
                try:
                    self.engine.stop()
                except Exception:
                    pass
                return False

            self.engine.runAndWait()

            if (
                not self._is_generation_active(generation)
                or self.stop_event.is_set()
            ):
                try:
                    self.engine.stop()
                except Exception:
                    pass
                return False

            success = True
            return True

        except Exception as error:
            print(f"pyttsx3 TTS Error : {error}")
            return False

        finally:
            with self.lock:
                if generation == self._generation:
                    self.is_speaking = False

    # ======================================================
    # NON-BLOCKING SPEAK
    # ======================================================

    def speak(self, text):
        """
        Start one asynchronous Windows SAPI speech request.
        """
        if self._closed or text is None:
            return None

        text = str(text).strip()

        if not text:
            return None

        self.stop()

        worker = threading.Thread(
            target=self.speak_blocking,
            args=(text,),
            daemon=True,
            name="ASTRA-pyttsx3-TTS",
        )

        with self.lock:
            self.current_thread = worker

        worker.start()
        return worker

    # ======================================================
    # STOP / CANCEL
    # ======================================================

    def stop(self):
        """
        Invalidate the current request before stopping SAPI.

        This prevents an older worker from becoming valid again
        after a new request clears a shared event.
        """
        with self.lock:
            self._generation += 1
            self.stop_event.set()
            self.is_speaking = False

        try:
            if self.engine is not None:
                self.engine.stop()
        except Exception:
            pass

    cancel = stop

    # ======================================================
    # SETTINGS
    # ======================================================

    def set_voice(self, voice):
        if not voice or not self.voices:
            return

        requested = str(voice)

        for available_voice in self.voices:
            try:
                available_id = str(
                    getattr(available_voice, "id", "")
                )

                if available_id == requested:
                    self.voice = available_voice.id

                    if self.engine is not None:
                        self.engine.setProperty(
                            "voice",
                            self.voice,
                        )
                    return

            except Exception:
                continue

    def set_rate(self, rate):
        try:
            self.rate = int(rate)
        except (TypeError, ValueError):
            self.rate = 170

        if self.engine is not None:
            try:
                self.engine.setProperty("rate", self.rate)
            except Exception:
                pass

    def set_volume(self, volume):
        try:
            value = float(volume)

            # Support both 0.0-1.0 and 0-100.
            if value > 1.0:
                value /= 100.0

            self.volume = max(0.0, min(value, 1.0))

        except (TypeError, ValueError):
            self.volume = 1.0

        if self.engine is not None:
            try:
                self.engine.setProperty(
                    "volume",
                    self.volume,
                )
            except Exception:
                pass

    # ======================================================
    # VOICES
    # ======================================================

    def get_voices(self):
        result = []

        for voice in self.voices:
            try:
                result.append(
                    {
                        "id": getattr(voice, "id", ""),
                        "name": getattr(voice, "name", ""),
                        "languages": getattr(
                            voice,
                            "languages",
                            [],
                        ),
                    }
                )
            except Exception:
                continue

        return result

    # ======================================================
    # STATUS
    # ======================================================

    def speaking(self):
        with self.lock:
            return bool(self.is_speaking)

    def wait_until_done(self, timeout=None):
        start = time.monotonic()

        while self.speaking():
            if self._closed:
                return True

            if timeout is not None:
                try:
                    if (
                        time.monotonic() - start
                        >= float(timeout)
                    ):
                        return False
                except (TypeError, ValueError):
                    pass

            time.sleep(0.01)

        return True

    # ======================================================
    # CLEANUP
    # ======================================================

    def close(self):
        if self._closed:
            return

        self.stop()
        self._closed = True

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

        with self.lock:
            self.current_thread = None
            self.engine = None
            self.voices = []
            self.is_speaking = False

        print(
            "pyttsx3 TTS Engine shutdown completed."
        )
