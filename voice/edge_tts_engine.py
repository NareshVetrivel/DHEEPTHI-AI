"""
voice/edge_tts_engine.py

ASTRA-AI
Premium Microsoft Edge Neural TTS Engine

Streaming/cancellation compatible Edge TTS provider.

Provider responsibilities
-------------------------
* Generate Edge Neural TTS audio.
* Play one request at a time.
* Invalidate stale requests immediately on stop/new request.
* Expose blocking and non-blocking APIs.
* Keep temporary audio files isolated per request.
* Allow TextToSpeech / StreamingTTSManager to cancel playback safely.

Note:
Edge TTS generation itself produces an audio file before pygame playback.
Sentence-level streaming is therefore handled by StreamingTTSManager,
which sends small completed text units to this engine one at a time.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading

import edge_tts
import pygame


class EdgeTTSEngine:

    def __init__(self):
        self.voice = "en-IN-NeerjaNeural"
        self.rate = 0
        self.volume = 100

        self.lock = threading.RLock()
        self.current_thread = None

        self.is_speaking = False
        self._closed = False

        # Monotonically increasing ownership generation.
        self._generation = 0
        self._current_filename = None

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception as error:
            print(f"Edge TTS Mixer Init Error : {error}")

    # ========================================================
    # GENERATION / OWNERSHIP
    # ========================================================

    def _next_generation(self) -> int:
        with self.lock:
            self._generation += 1
            return self._generation

    def _is_generation_active(self, generation: int) -> bool:
        if self._closed:
            return False

        with self.lock:
            return generation == self._generation

    # ========================================================
    # FORMAT SETTINGS
    # ========================================================

    def _get_edge_rate(self) -> str:
        try:
            rate = int(self.rate)
        except (TypeError, ValueError):
            rate = 0

        rate = max(-100, min(100, rate))
        return f"+{rate}%" if rate >= 0 else f"{rate}%"

    def _get_edge_volume(self) -> str:
        try:
            volume = int(self.volume)
        except (TypeError, ValueError):
            volume = 100

        volume = max(0, min(200, volume))
        edge_volume = volume - 100
        return f"+{edge_volume}%" if edge_volume >= 0 else f"{edge_volume}%"

    # ========================================================
    # GENERATION
    # ========================================================

    async def _generate(self, text: str, filename: str):
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self._get_edge_rate(),
            volume=self._get_edge_volume(),
        )
        await communicate.save(filename)

    # ========================================================
    # BLOCKING SPEECH
    # ========================================================

    def speak_blocking(self, text):
        """
        Generate and play one Edge TTS segment.

        Returns True only when the complete segment was generated
        and played by the request that still owns the generation.
        """
        if self._closed or text is None:
            return False

        text = str(text).strip()
        if not text:
            return False

        generation = self._next_generation()
        filename = None
        loop = None
        playback_started = False

        try:
            if not self._is_generation_active(generation):
                return False

            with self.lock:
                if not self._is_generation_active(generation):
                    return False
                self.is_speaking = True

            temp = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".mp3",
            )
            filename = temp.name
            temp.close()

            with self.lock:
                if self._is_generation_active(generation):
                    self._current_filename = filename

            # -----------------------------------------------
            # Generate audio
            # -----------------------------------------------
            loop = asyncio.new_event_loop()

            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self._generate(text, filename)
                )
            except Exception as error:
                print(f"Edge TTS Generate Error : {error}")
                return False
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
                loop = None
                try:
                    asyncio.set_event_loop(None)
                except Exception:
                    pass

            if not self._is_generation_active(generation):
                return False

            if not os.path.exists(filename):
                print(
                    "Edge TTS Error : Generated audio file not found."
                )
                return False

            try:
                if os.path.getsize(filename) == 0:
                    print(
                        "Edge TTS Error : Generated audio file is empty."
                    )
                    return False
            except OSError:
                return False

            # -----------------------------------------------
            # Playback
            # -----------------------------------------------
            try:
                if not self._is_generation_active(generation):
                    return False

                pygame.mixer.music.load(filename)

                if not self._is_generation_active(generation):
                    try:
                        pygame.mixer.music.stop()
                    except Exception:
                        pass
                    return False

                pygame.mixer.music.play()
                playback_started = True

            except Exception as error:
                print(f"Edge TTS Playback Error : {error}")
                return False

            # -----------------------------------------------
            # Wait until this segment finishes or is cancelled.
            # -----------------------------------------------
            while True:
                if not self._is_generation_active(generation):
                    return False

                try:
                    if not pygame.mixer.music.get_busy():
                        break
                except Exception:
                    return False

                # Short polling interval keeps cancellation responsive.
                pygame.time.wait(8)

            return self._is_generation_active(generation)

        except Exception as error:
            print(f"Edge TTS Error : {error}")
            return False

        finally:
            is_active = self._is_generation_active(generation)

            # Only the current owner may touch shared playback state.
            if is_active:
                try:
                    if playback_started:
                        pygame.mixer.music.stop()
                except Exception:
                    pass

                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass

            if filename:
                try:
                    if os.path.exists(filename):
                        os.remove(filename)
                except Exception:
                    pass

            with self.lock:
                if generation == self._generation:
                    if self._current_filename == filename:
                        self._current_filename = None
                    self.is_speaking = False

    # ========================================================
    # NON-BLOCKING SPEECH
    # ========================================================

    def speak(self, text):
        """
        Start one asynchronous Edge TTS segment.

        TextToSpeech normally owns request-level cancellation, so
        this method also invalidates any older Edge request.
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
            name="ASTRA-Edge-TTS",
        )

        with self.lock:
            self.current_thread = worker

        worker.start()
        return worker

    # ========================================================
    # STOP / CANCEL
    # ========================================================

    def stop(self):
        """
        Invalidate the current request before stopping playback.

        This ordering prevents an old worker from becoming valid again.
        """
        with self.lock:
            self._generation += 1
            self.is_speaking = False
            self._current_filename = None

        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.unload()
        except Exception:
            pass

    cancel = stop

    # ========================================================
    # SETTINGS
    # ========================================================

    def set_voice(self, voice):
        if voice:
            self.voice = str(voice).strip()

    def set_rate(self, rate):
        try:
            self.rate = int(rate)
        except (TypeError, ValueError):
            self.rate = 0

    def set_volume(self, volume):
        try:
            self.volume = int(volume)
        except (TypeError, ValueError):
            self.volume = 100

    # ========================================================
    # STATUS
    # ========================================================

    def speaking(self):
        with self.lock:
            if self.is_speaking:
                return True

        try:
            if (
                pygame.mixer.get_init()
                and pygame.mixer.music.get_busy()
            ):
                return True
        except Exception:
            pass

        return False

    def wait_until_done(self, timeout=None):
        """
        Wait for current Edge playback to finish.

        Returns True when no active playback remains, False on timeout.
        """
        start = __import__("time").monotonic()

        while self.speaking():
            if self._closed:
                return True

            if timeout is not None:
                try:
                    if (__import__("time").monotonic() - start) >= float(timeout):
                        return False
                except (TypeError, ValueError):
                    pass

            __import__("time").sleep(0.01)

        return True

    # ========================================================
    # CLEANUP
    # ========================================================

    def close(self):
        if self._closed:
            return

        # Invalidate and stop before marking the object closed so the
        # active worker observes the generation change.
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
            self._current_filename = None
            self.is_speaking = False

        print("Edge TTS Engine shutdown completed.")
