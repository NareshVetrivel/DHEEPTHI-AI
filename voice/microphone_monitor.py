from __future__ import annotations

"""
DHEEPTHI-AI
Windows Physical Microphone Mute Monitor

Purpose
-------
Monitor the Windows default CAPTURE microphone endpoint and detect
its mute/unmute state.

IMPORTANT
---------
This module does NOT monitor the round microphone button inside
the DHEEPTHI UI.

It monitors the Windows default capture endpoint state.

Typical flow:

    Laptop physical microphone mute key
                |
                v
    Windows microphone endpoint
                |
                v
    IAudioEndpointVolume.GetMute()
                |
                v
    MicrophoneMuteMonitor
                |
        +-------+-------+
        |               |
      MUTED           UNMUTED
        |               |
        v               v
      IDLE          LISTENING
                        |
                        v
                  Gemini Live

Framework
---------
PySide6

Windows API
-----------
Windows Core Audio / MMDevice API

Python dependency
-----------------
comtypes
"""

import sys
import threading

from ctypes import (
    POINTER,
    cast,
    c_float,
    c_int,
    c_uint,
    c_ulong,
    c_void_p,
)

from ctypes.wintypes import BOOL
from typing import Optional


# ============================================================
# PySide6
# ============================================================

try:

    from PySide6.QtCore import QThread, Signal

    _QT_AVAILABLE = True
    _QT_IMPORT_ERROR = None

except Exception as exc:

    QThread = None
    Signal = None

    _QT_AVAILABLE = False
    _QT_IMPORT_ERROR = exc


# ============================================================
# Windows / COM
# ============================================================

if sys.platform == "win32":

    try:

        import comtypes
        import comtypes.client

        from comtypes import (
            COMMETHOD,
            GUID,
            HRESULT,
            IUnknown,
        )

        _COM_AVAILABLE = True
        _COM_IMPORT_ERROR = None

    except Exception as exc:

        _COM_AVAILABLE = False
        _COM_IMPORT_ERROR = exc

else:

    _COM_AVAILABLE = False

    _COM_IMPORT_ERROR = RuntimeError(
        "Windows Core Audio microphone monitoring "
        "is supported only on Windows."
    )


# ============================================================
# Windows Core Audio GUIDs
# ============================================================

# CLSID_MMDeviceEnumerator
_CLSID_MMDEVICE_ENUMERATOR = GUID(
    "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
)

# IID_IMMDeviceEnumerator
_IID_IMMDEVICE_ENUMERATOR = GUID(
    "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
)

# IID_IMMDevice
_IID_IMMDEVICE = GUID(
    "{D666063F-1587-4E43-81F1-B948E807363F}"
)

# IID_IAudioEndpointVolume
_IID_IAUDIO_ENDPOINT_VOLUME = GUID(
    "{5CDF2C82-841E-4546-9722-0CF74078229A}"
)


# ============================================================
# Windows Core Audio constants
# ============================================================

# EDataFlow
_E_RENDER = 0
_E_CAPTURE = 1

# ERole
_ER_CONSOLE = 0
_ER_MULTIMEDIA = 1
_ER_COMMUNICATIONS = 2

# CLSCTX
_CLSCTX_INPROC_SERVER = 0x1
_CLSCTX_INPROC_HANDLER = 0x2
_CLSCTX_LOCAL_SERVER = 0x4

_CLSCTX_ALL = (
    _CLSCTX_INPROC_SERVER
    | _CLSCTX_INPROC_HANDLER
    | _CLSCTX_LOCAL_SERVER
)


# ============================================================
# COM interfaces
# ============================================================

if _COM_AVAILABLE:

    class IMMDevice(IUnknown):
        """
        Windows Core Audio IMMDevice interface.
        """

        _iid_ = _IID_IMMDEVICE

        _methods_ = [

            # ------------------------------------------------
            # IMMDevice::Activate
            #
            # HRESULT Activate(
            #     REFIID iid,
            #     DWORD dwClsCtx,
            #     PROPVARIANT *pActivationParams,
            #     void **ppInterface
            # );
            #
            # The final [out] parameter is returned by
            # comtypes, therefore Activate() receives only
            # the first three arguments from Python.
            # ------------------------------------------------

            COMMETHOD(
                [],
                HRESULT,
                "Activate",
                (
                    ["in"],
                    POINTER(GUID),
                    "iid",
                ),
                (
                    ["in"],
                    c_ulong,
                    "dwClsCtx",
                ),
                (
                    ["in"],
                    c_void_p,
                    "pActivationParams",
                ),
                (
                    ["out"],
                    POINTER(c_void_p),
                    "ppInterface",
                ),
            ),
        ]


    class IMMDeviceEnumerator(IUnknown):
        """
        Windows Core Audio IMMDeviceEnumerator interface.
        """

        _iid_ = _IID_IMMDEVICE_ENUMERATOR

        _methods_ = [

            # ------------------------------------------------
            # EnumAudioEndpoints
            # ------------------------------------------------

            COMMETHOD(
                [],
                HRESULT,
                "EnumAudioEndpoints",
                (
                    ["in"],
                    c_int,
                    "dataFlow",
                ),
                (
                    ["in"],
                    c_ulong,
                    "dwStateMask",
                ),
                (
                    ["out"],
                    POINTER(c_void_p),
                    "ppDevices",
                ),
            ),

            # ------------------------------------------------
            # GetDefaultAudioEndpoint
            #
            # The endpoint is an [out] parameter and is
            # returned by comtypes.
            # ------------------------------------------------

            COMMETHOD(
                [],
                HRESULT,
                "GetDefaultAudioEndpoint",
                (
                    ["in"],
                    c_int,
                    "dataFlow",
                ),
                (
                    ["in"],
                    c_int,
                    "role",
                ),
                (
                    ["out"],
                    POINTER(POINTER(IMMDevice)),
                    "ppEndpoint",
                ),
            ),
        ]


    class IAudioEndpointVolume(IUnknown):
        """
        Windows Core Audio IAudioEndpointVolume interface.

        The method order MUST match the native COM vtable.
        """

        _iid_ = _IID_IAUDIO_ENDPOINT_VOLUME

        _methods_ = [

            # =================================================
            # 1. RegisterControlChangeNotify
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "RegisterControlChangeNotify",
                (
                    ["in"],
                    c_void_p,
                    "pNotify",
                ),
            ),

            # =================================================
            # 2. UnregisterControlChangeNotify
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "UnregisterControlChangeNotify",
                (
                    ["in"],
                    c_void_p,
                    "pNotify",
                ),
            ),

            # =================================================
            # 3. GetChannelCount
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "GetChannelCount",
                (
                    ["out"],
                    POINTER(c_uint),
                    "pnChannelCount",
                ),
            ),

            # =================================================
            # 4. SetMasterVolumeLevel
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "SetMasterVolumeLevel",
                (
                    ["in"],
                    c_float,
                    "fLevelDB",
                ),
                (
                    ["in"],
                    POINTER(GUID),
                    "pguidEventContext",
                ),
            ),

            # =================================================
            # 5. SetMasterVolumeLevelScalar
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "SetMasterVolumeLevelScalar",
                (
                    ["in"],
                    c_float,
                    "fLevel",
                ),
                (
                    ["in"],
                    POINTER(GUID),
                    "pguidEventContext",
                ),
            ),

            # =================================================
            # 6. GetMasterVolumeLevel
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "GetMasterVolumeLevel",
                (
                    ["out"],
                    POINTER(c_float),
                    "pfLevelDB",
                ),
            ),

            # =================================================
            # 7. GetMasterVolumeLevelScalar
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "GetMasterVolumeLevelScalar",
                (
                    ["out"],
                    POINTER(c_float),
                    "pfLevel",
                ),
            ),

            # =================================================
            # 8. SetChannelVolumeLevel
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "SetChannelVolumeLevel",
                (
                    ["in"],
                    c_uint,
                    "nChannel",
                ),
                (
                    ["in"],
                    c_float,
                    "fLevelDB",
                ),
                (
                    ["in"],
                    POINTER(GUID),
                    "pguidEventContext",
                ),
            ),

            # =================================================
            # 9. SetChannelVolumeLevelScalar
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "SetChannelVolumeLevelScalar",
                (
                    ["in"],
                    c_uint,
                    "nChannel",
                ),
                (
                    ["in"],
                    c_float,
                    "fLevel",
                ),
                (
                    ["in"],
                    POINTER(GUID),
                    "pguidEventContext",
                ),
            ),

            # =================================================
            # 10. GetChannelVolumeLevel
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "GetChannelVolumeLevel",
                (
                    ["in"],
                    c_uint,
                    "nChannel",
                ),
                (
                    ["out"],
                    POINTER(c_float),
                    "pfLevelDB",
                ),
            ),

            # =================================================
            # 11. GetChannelVolumeLevelScalar
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "GetChannelVolumeLevelScalar",
                (
                    ["in"],
                    c_uint,
                    "nChannel",
                ),
                (
                    ["out"],
                    POINTER(c_float),
                    "pfLevel",
                ),
            ),

            # =================================================
            # 12. SetMute
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "SetMute",
                (
                    ["in"],
                    BOOL,
                    "bMute",
                ),
                (
                    ["in"],
                    POINTER(GUID),
                    "pguidEventContext",
                ),
            ),

            # =================================================
            # 13. GetMute
            # =================================================

            COMMETHOD(
                [],
                HRESULT,
                "GetMute",
                (
                    ["out"],
                    POINTER(BOOL),
                    "pbMute",
                ),
            ),
        ]


# ============================================================
# Microphone monitor
# ============================================================

if _QT_AVAILABLE:

    class MicrophoneMuteMonitor(QThread):
        """
        Monitor the Windows default capture microphone endpoint.

        Signals
        -------

        mute_changed(bool)

            True
                Windows microphone endpoint is muted.

            False
                Windows microphone endpoint is unmuted.

        error(str)

            Non-fatal monitoring error.
        """

        mute_changed = Signal(bool)

        error = Signal(str)

        def __init__(
            self,
            interval_ms: int = 250,
            parent=None,
        ):
            super().__init__(parent)

            self.interval_ms = max(
                100,
                int(interval_ms),
            )

            self._stop_event = (
                threading.Event()
            )

            self._state_lock = (
                threading.RLock()
            )

            self._last_muted: Optional[bool] = None

            self._enumerator = None

            self._endpoint = None

            self._volume = None

            self._initialized = False

            self._last_error: Optional[str] = None

        # ====================================================
        # Public state
        # ====================================================

        @property
        def current_muted(
            self,
        ) -> Optional[bool]:
            """
            Return the last known Windows microphone
            mute state.
            """

            with self._state_lock:

                return self._last_muted

        @property
        def is_initialized(
            self,
        ) -> bool:
            """
            Return whether the Windows microphone endpoint
            was successfully initialized.
            """

            return bool(
                self._initialized
            )

        # ====================================================
        # Public control
        # ====================================================

        def start_monitoring(
            self,
        ) -> None:
            """
            Start microphone monitoring.
            """

            if self.isRunning():
                return

            self._stop_event.clear()

            self.start()

        def stop_monitoring(
            self,
        ) -> None:
            """
            Stop microphone monitoring.
            """

            self.stop()

        def stop(
            self,
        ) -> None:
            """
            Request worker thread shutdown.
            """

            self._stop_event.set()

        # ====================================================
        # QThread
        # ====================================================

        def run(
            self,
        ) -> None:
            """
            Worker thread entry point.
            """

            print(
                "[MIC MONITOR] "
                "Windows physical microphone monitor started."
            )

            # ------------------------------------------------
            # Windows check
            # ------------------------------------------------

            if sys.platform != "win32":

                self._emit_error(
                    "Physical microphone monitoring is "
                    "supported only on Windows."
                )

                return

            # ------------------------------------------------
            # COM dependency check
            # ------------------------------------------------

            if not _COM_AVAILABLE:

                self._emit_error(
                    "comtypes is unavailable: "
                    f"{_COM_IMPORT_ERROR}"
                )

                return

            com_initialized = False

            try:

                # --------------------------------------------
                # Initialize COM on THIS worker thread.
                # --------------------------------------------

                try:

                    comtypes.CoInitialize()

                    com_initialized = True

                except Exception as exc:

                    self._emit_error(
                        "COM initialization failed: "
                        f"{exc}"
                    )

                    return

                # --------------------------------------------
                # Resolve Windows microphone endpoint.
                # --------------------------------------------

                if not self._initialize_endpoint():

                    return

                # --------------------------------------------
                # Read initial mute state.
                # --------------------------------------------

                initial_state = (
                    self._read_mute_state()
                )

                if initial_state is None:

                    self._emit_error(
                        "Could not read the initial "
                        "microphone mute state."
                    )

                    return

                with self._state_lock:

                    self._last_muted = (
                        initial_state
                    )

                print(
                    "[MIC MONITOR] Initial state : "
                    f"{self._state_text(initial_state)}"
                )

                # Notify listener immediately.

                self.mute_changed.emit(
                    initial_state
                )

                self._initialized = True

                # --------------------------------------------
                # Polling interval.
                # --------------------------------------------

                wait_seconds = (
                    self.interval_ms / 1000.0
                )

                # --------------------------------------------
                # Monitor loop.
                # --------------------------------------------

                while not self._stop_event.is_set():

                    current_state = (
                        self._read_mute_state()
                    )

                    if current_state is not None:

                        changed = False

                        with self._state_lock:

                            if (
                                self._last_muted
                                is None
                            ):

                                self._last_muted = (
                                    current_state
                                )

                                changed = True

                            elif (
                                current_state
                                != self._last_muted
                            ):

                                self._last_muted = (
                                    current_state
                                )

                                changed = True

                        if changed:

                            state_name = (
                                self._state_text(
                                    current_state
                                )
                            )

                            print(
                                "[MIC MONITOR] "
                                "Microphone state changed -> "
                                f"{state_name}"
                            )

                            self.mute_changed.emit(
                                current_state
                            )

                    self._stop_event.wait(
                        timeout=wait_seconds
                    )

            except Exception as exc:

                self._emit_error(
                    "Unexpected microphone monitor error: "
                    f"{exc}"
                )

            finally:

                self._release_endpoint()

                if com_initialized:

                    try:

                        comtypes.CoUninitialize()

                    except Exception:

                        pass

                print(
                    "[MIC MONITOR] "
                    "Windows physical microphone monitor stopped."
                )

        # ====================================================
        # Endpoint initialization
        # ====================================================

        def _initialize_endpoint(
            self,
        ) -> bool:
            """
            Resolve the Windows default CAPTURE endpoint.

            This specifically asks Windows for the default
            microphone endpoint, not the render/speaker endpoint.
            """

            try:

                # --------------------------------------------
                # Create MMDeviceEnumerator.
                # --------------------------------------------

                self._enumerator = (
                    comtypes.client.CreateObject(
                        _CLSID_MMDEVICE_ENUMERATOR,
                        interface=(
                            IMMDeviceEnumerator
                        ),
                    )
                )

                print(
                    "[MIC MONITOR] "
                    "MMDeviceEnumerator created."
                )

                # --------------------------------------------
                # Get default CAPTURE endpoint.
                #
                # IMPORTANT:
                # comtypes returns [out] endpoint directly.
                # --------------------------------------------

                endpoint = (
                    self._enumerator
                    .GetDefaultAudioEndpoint(
                        _E_CAPTURE,
                        _ER_CONSOLE,
                    )
                )

                # --------------------------------------------
                # Console role fallback.
                # --------------------------------------------

                if not endpoint:

                    print(
                        "[MIC MONITOR] "
                        "Console capture endpoint unavailable."
                    )

                    endpoint = (
                        self._enumerator
                        .GetDefaultAudioEndpoint(
                            _E_CAPTURE,
                            _ER_MULTIMEDIA,
                        )
                    )

                if not endpoint:

                    self._emit_error(
                        "Windows could not resolve the "
                        "default capture microphone endpoint."
                    )

                    return False

                self._endpoint = endpoint

                print(
                    "[MIC MONITOR] "
                    "Default Windows capture microphone endpoint resolved."
                )

                # --------------------------------------------
                # Activate IAudioEndpointVolume.
                #
                # IMPORTANT:
                # The [out] interface pointer is returned by
                # comtypes. Do NOT pass a fourth argument.
                # --------------------------------------------

                volume_ptr = (
                    self._endpoint.Activate(
                        _IID_IAUDIO_ENDPOINT_VOLUME,
                        _CLSCTX_ALL,
                        None,
                    )
                )

                if not volume_ptr:

                    self._emit_error(
                        "Windows returned an empty "
                        "IAudioEndpointVolume pointer."
                    )

                    return False

                # --------------------------------------------
                # Wrap returned COM pointer.
                # --------------------------------------------

                self._volume = cast(
                    volume_ptr,
                    POINTER(
                        IAudioEndpointVolume
                    ),
                )

                print(
                    "[MIC MONITOR] "
                    "IAudioEndpointVolume activated."
                )

                return True

            except Exception as exc:

                self._emit_error(
                    "Microphone endpoint initialization failed: "
                    f"{exc}"
                )

                self._enumerator = None

                self._endpoint = None

                self._volume = None

                return False

        # ====================================================
        # Read mute state
        # ====================================================

        def _read_mute_state(
            self,
        ) -> Optional[bool]:
            """
            Read the Windows microphone mute state.

            IMPORTANT:
            GetMute has an [out] parameter, so comtypes returns
            the BOOL directly. No byref() is required.
            """

            if self._volume is None:

                return None

            try:

                muted = (
                    self._volume.GetMute()
                )

                self._last_error = None

                return bool(
                    muted
                )

            except Exception as exc:

                self._emit_error_once(
                    "Microphone mute-state read failed: "
                    f"{exc}"
                )

                return None

        # ====================================================
        # Cleanup
        # ====================================================

        def _release_endpoint(
            self,
        ) -> None:
            """
            Release COM references.
            """

            self._initialized = False

            self._volume = None

            self._endpoint = None

            self._enumerator = None

        # ====================================================
        # Helpers
        # ====================================================

        @staticmethod
        def _state_text(
            muted: bool,
        ) -> str:
            """
            Convert mute state to readable text.
            """

            if muted:

                return "MUTED"

            return "UNMUTED"

        def _emit_error(
            self,
            message: str,
        ) -> None:
            """
            Emit a non-fatal error.
            """

            print(
                f"[MIC MONITOR ERROR] {message}"
            )

            try:

                self.error.emit(
                    str(message)
                )

            except Exception:

                pass

        def _emit_error_once(
            self,
            message: str,
        ) -> None:
            """
            Prevent repeated identical errors from flooding
            the terminal.
            """

            if self._last_error == message:

                return

            self._last_error = message

            self._emit_error(
                message
            )


else:

    class MicrophoneMuteMonitor:
        """
        Import-safe fallback when PySide6 is unavailable.
        """

        def __init__(
            self,
            interval_ms: int = 250,
            parent=None,
        ):

            raise RuntimeError(
                "PySide6 is required for "
                "MicrophoneMuteMonitor."
            )


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "MicrophoneMuteMonitor",
]