"""
DHEEPTHI-AI
System Controller Module

Provides Windows system automation for DHEEPTHI-AI.

Features
--------
- Volume increase/decrease
- Exact volume percentage
- Mute/unmute
- Brightness increase/decrease
- Exact brightness percentage
- Lock screen
- Shutdown
- Restart
- Sleep
- Sign out
- Open Windows Settings
- Open Task Manager
- Open CMD
- Open PowerShell
- Open Control Panel
- Open File Explorer
- Open Camera
- Capture webcam photo
- Screenshot
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
from pathlib import Path

import pyautogui


class SystemController:
    """
    Controls Windows system functions for DHEEPTHI-AI.
    """

    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.2

        self.screenshot_directory = (
            Path.cwd() / "screenshots"
        )

        self.photo_directory = (
            Path.cwd() / "camera_photos"
        )

        self.screenshot_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        self.photo_directory.mkdir(
            parents=True,
            exist_ok=True
        )

    # ==================================================
    # Volume
    # ==================================================

    def _get_volume_interface(self):
        """
        Get Windows master audio endpoint.

        Returns
        -------
        EndpointVolume | None
        """

        try:

            from pycaw.pycaw import (
                AudioUtilities
            )

            speakers = (
                AudioUtilities.GetSpeakers()
            )

            volume = speakers.EndpointVolume

            return volume

        except Exception as error:

            print(
                f"Volume Interface Error : {error}"
            )

            return None

    def get_volume(self):
        """
        Get current system volume.

        Returns
        -------
        int | None
            Volume percentage from 0 to 100.
        """

        try:

            volume = self._get_volume_interface()

            if volume is None:
                return None

            value = (
                volume.GetMasterVolumeLevelScalar()
            )

            return round(value * 100)

        except Exception as error:

            print(
                f"Get Volume Error : {error}"
            )

            return None

    def set_volume(self, percentage: int):
        """
        Set system volume to exact percentage.

        Parameters
        ----------
        percentage : int
            Value from 0 to 100.

        Returns
        -------
        bool
        """

        try:

            percentage = int(percentage)

            if not 0 <= percentage <= 100:
                return False

            volume = self._get_volume_interface()

            if volume is None:
                return False

            volume.SetMasterVolumeLevelScalar(
                percentage / 100.0,
                None
            )

            return True

        except Exception as error:

            print(
                f"Set Volume Error : {error}"
            )

            return False

    def volume_up(self, step: int = 5):
        """
        Increase volume by percentage points.

        Example
        -------
        40 -> 45
        """

        try:

            current = self.get_volume()

            if current is None:
                return False

            target = min(
                100,
                current + int(step)
            )

            return self.set_volume(target)

        except Exception as error:

            print(
                f"Volume Up Error : {error}"
            )

            return False

    def volume_down(self, step: int = 5):
        """
        Decrease volume by percentage points.

        Example
        -------
        40 -> 35
        """

        try:

            current = self.get_volume()

            if current is None:
                return False

            target = max(
                0,
                current - int(step)
            )

            return self.set_volume(target)

        except Exception as error:

            print(
                f"Volume Down Error : {error}"
            )

            return False

    def mute(self):
        """
        Toggle system mute.
        """

        try:

            volume = self._get_volume_interface()

            if volume is None:
                return False

            current_mute = (
                volume.GetMute()
            )

            volume.SetMute(
                not current_mute,
                None
            )

            return True

        except Exception as error:

            print(
                f"Mute Error : {error}"
            )

            return False

    def unmute(self):
        """
        Unmute system audio.
        """

        try:

            volume = self._get_volume_interface()

            if volume is None:
                return False

            volume.SetMute(
                False,
                None
            )

            return True

        except Exception as error:

            print(
                f"Unmute Error : {error}"
            )

            return False

    # ==================================================
    # Brightness
    # ==================================================

    def get_brightness(self):
        """
        Get current primary-monitor brightness.

        Returns
        -------
        int | None
        """

        try:

            import screen_brightness_control as sbc

            brightness = sbc.get_brightness(
                display=0
            )

            if isinstance(brightness, list):

                if not brightness:
                    return None

                return int(brightness[0])

            return int(brightness)

        except Exception as error:

            print(
                f"Get Brightness Error : {error}"
            )

            return None

    def set_brightness(self, percentage: int):
        """
        Set display brightness to exact percentage.

        Parameters
        ----------
        percentage : int
            Value from 0 to 100.

        Returns
        -------
        bool
        """

        try:

            percentage = int(percentage)

            if not 0 <= percentage <= 100:
                return False

            import screen_brightness_control as sbc

            sbc.set_brightness(
                percentage,
                display=0
            )

            return True

        except Exception as error:

            print(
                f"Set Brightness Error : {error}"
            )

            return False

    def brightness_up(self, step: int = 5):
        """
        Increase brightness by percentage points.
        """

        try:

            current = self.get_brightness()

            if current is None:
                return False

            target = min(
                100,
                current + int(step)
            )

            return self.set_brightness(target)

        except Exception as error:

            print(
                f"Brightness Up Error : {error}"
            )

            return False

    def brightness_down(self, step: int = 5):
        """
        Decrease brightness by percentage points.
        """

        try:

            current = self.get_brightness()

            if current is None:
                return False

            target = max(
                0,
                current - int(step)
            )

            return self.set_brightness(target)

        except Exception as error:

            print(
                f"Brightness Down Error : {error}"
            )

            return False

    # ==================================================
    # Power
    # ==================================================

    def lock_screen(self):
        """
        Lock Windows.
        """

        try:

            result = ctypes.windll.user32.LockWorkStation()

            return bool(result)

        except Exception as error:

            print(
                f"Lock Screen Error : {error}"
            )

            return False

    def shutdown(self):
        """
        Shutdown Windows.
        """

        try:

            subprocess.Popen(
                [
                    "shutdown",
                    "/s",
                    "/t",
                    "0"
                ],
                shell=False
            )

            return True

        except Exception as error:

            print(
                f"Shutdown Error : {error}"
            )

            return False

    def restart(self):
        """
        Restart Windows.
        """

        try:

            subprocess.Popen(
                [
                    "shutdown",
                    "/r",
                    "/t",
                    "0"
                ],
                shell=False
            )

            return True

        except Exception as error:

            print(
                f"Restart Error : {error}"
            )

            return False

    def sleep(self):
        """
        Put Windows into sleep mode.
        """

        try:

            ctypes.windll.powrprof.SetSuspendState(
                False,
                True,
                False
            )

            return True

        except Exception as error:

            print(
                f"Sleep Error : {error}"
            )

            return False

    def sign_out(self):
        """
        Sign out the current Windows user.
        """

        try:

            result = ctypes.windll.user32.ExitWindowsEx(
                0,
                0
            )

            return bool(result)

        except Exception as error:

            print(
                f"Sign Out Error : {error}"
            )

            return False

    # ==================================================
    # Windows Applications
    # ==================================================

    def open_settings(self):
        """
        Open Windows Settings.
        """

        try:

            os.startfile(
                "ms-settings:"
            )

            return True

        except Exception as error:

            print(
                f"Settings Error : {error}"
            )

            return False

    def open_task_manager(self):
        """
        Open Windows Task Manager.
        """

        try:

            subprocess.Popen(
                [
                    "taskmgr.exe"
                ],
                shell=False
            )

            return True

        except Exception as error:

            print(
                f"Task Manager Error : {error}"
            )

            return False

    def open_cmd(self):
        """
        Open Command Prompt in a separate visible window.
        """

        try:

            subprocess.Popen(
                [
                    "cmd.exe",
                    "/c",
                    "start",
                    "",
                    "cmd.exe"
                ],
                shell=False
            )

            return True

        except Exception as error:

            print(
                f"CMD Error : {error}"
            )

            return False

    def open_powershell(self):
        """
        Open PowerShell in a separate visible window.
        """

        try:

            subprocess.Popen(
                [
                    "cmd.exe",
                    "/c",
                    "start",
                    "",
                    "powershell.exe"
                ],
                shell=False
            )

            return True

        except Exception as error:

            print(
                f"PowerShell Error : {error}"
            )

            return False

    def open_control_panel(self):
        """
        Open Windows Control Panel.
        """

        try:

            subprocess.Popen(
                [
                    "control.exe"
                ],
                shell=False
            )

            return True

        except Exception as error:

            print(
                f"Control Panel Error : {error}"
            )

            return False

    def open_file_explorer(self):
        """
        Open File Explorer.
        """

        try:

            os.startfile(
                "explorer.exe"
            )

            return True

        except Exception as error:

            print(
                f"Explorer Error : {error}"
            )

            return False

    # ==================================================
    # Camera
    # ==================================================

    def open_camera(self):
        """
        Open the Windows Camera application.
        """

        try:

            subprocess.Popen(
                [
                    "explorer.exe",
                    "microsoft.windows.camera:"
                ],
                shell=False
            )

            return True

        except Exception as error:

            print(
                f"Camera Open Error : {error}"
            )

            return False

    def capture_photo(self):
        """
        Open the Windows Camera application if required,
        capture a new photo, wait until the file is fully
        written, copy it into DHEEPTHI-AI/camera_photos,
        and verify the copied file.

        Returns
        -------
        str | None
            Path of the copied DHEEPTHI photo.
        """

        try:

            import shutil

            from pywinauto import Desktop

            # ---------------------------------
            # Locate Windows Camera Roll
            # ---------------------------------

            camera_roll_candidates = [

                Path.home()
                / "Pictures"
                / "Camera Roll",

                Path.home()
                / "OneDrive"
                / "Pictures"
                / "Camera Roll",

            ]

            camera_roll = None

            for candidate in camera_roll_candidates:

                if candidate.exists():

                    camera_roll = candidate

                    break

            if camera_roll is None:

                print(
                    "Camera Roll Error : "
                    "Camera Roll folder not found."
                )

                return None

            print(
                f"Camera Roll : {camera_roll}"
            )

            # ---------------------------------
            # Existing Photos Snapshot
            # ---------------------------------

            before_files = set()

            for pattern in (
                "*.jpg",
                "*.jpeg",
                "*.png"
            ):

                before_files.update(
                    camera_roll.glob(pattern)
                )

            # ---------------------------------
            # Open Camera App
            # ---------------------------------

            if not self.open_camera():

                print(
                    "Camera Capture Error : "
                    "Unable to open Camera."
                )

                return None

            # ---------------------------------
            # Wait for Camera App
            # ---------------------------------

            time.sleep(3)

            # ---------------------------------
            # Connect To Camera Window
            # ---------------------------------

            camera_window = Desktop(
                backend="uia"
            ).window(
                title_re=".*Camera.*"
            )

            camera_window.wait(
                "visible",
                timeout=10
            )

            camera_window.set_focus()

            # ---------------------------------
            # Find Shutter Button
            # ---------------------------------

            shutter = None

            button_names = [
                "Take photo",
                "Take a photo",
                "Take Photo",
                "Photo",
                "Take Picture",
                "Capture"
            ]

            for name in button_names:

                try:

                    candidate = (
                        camera_window.child_window(
                            title=name,
                            control_type="Button"
                        )
                    )

                    if candidate.exists(
                        timeout=1
                    ):

                        shutter = candidate

                        break

                except Exception:

                    continue

            # ---------------------------------
            # Capture Photo
            # ---------------------------------

            if shutter is not None:

                shutter.click_input()

                print(
                    "Camera : Shutter clicked."
                )

            else:

                print(
                    "Camera : Shutter button not found. "
                    "Using Space shortcut."
                )

                camera_window.set_focus()

                pyautogui.press(
                    "space"
                )

            # ---------------------------------
            # Wait For New Photo
            # ---------------------------------

            new_photo = None

            timeout = 15

            start_time = time.time()

            while (
                time.time() - start_time
                < timeout
            ):

                current_files = set()

                for pattern in (
                    "*.jpg",
                    "*.jpeg",
                    "*.png"
                ):

                    current_files.update(
                        camera_roll.glob(pattern)
                    )

                created_files = (
                    current_files
                    - before_files
                )

                if created_files:

                    new_photo = max(
                        created_files,
                        key=lambda file: (
                            file.stat().st_mtime
                        )
                    )

                    break

                time.sleep(0.5)

            if new_photo is None:

                print(
                    "Camera Capture Error : "
                    "New photo was not detected."
                )

                return None

            print(
                f"Camera Photo Detected : {new_photo}"
            )

            # ---------------------------------
            # Wait Until File Is Fully Written
            # ---------------------------------

            stable_checks = 0

            previous_size = -1

            for _ in range(20):

                try:

                    current_size = (
                        new_photo.stat().st_size
                    )

                except OSError:

                    time.sleep(0.5)

                    continue

                if (
                    current_size > 0
                    and current_size == previous_size
                ):

                    stable_checks += 1

                else:

                    stable_checks = 0

                previous_size = current_size

                if stable_checks >= 2:

                    break

                time.sleep(0.5)

            # ---------------------------------
            # Validate Source Photo
            # ---------------------------------

            if not new_photo.exists():

                print(
                    "Camera Capture Error : "
                    "Captured photo disappeared."
                )

                return None

            if new_photo.stat().st_size <= 0:

                print(
                    "Camera Capture Error : "
                    "Captured photo is empty."
                )

                return None

            # ---------------------------------
            # Prepare Destination
            # ---------------------------------

            self.photo_directory.mkdir(
                parents=True,
                exist_ok=True
            )

            timestamp = time.strftime(
                "%Y%m%d_%H%M%S"
            )

            extension = (
                new_photo.suffix.lower()
            )

            if extension not in (
                ".jpg",
                ".jpeg",
                ".png"
            ):

                extension = ".jpg"

            destination = (
                self.photo_directory
                / f"dheepthi_photo_{timestamp}{extension}"
            )

            # ---------------------------------
            # Copy To DHEEPTHI Camera Folder
            # ---------------------------------

            shutil.copy2(
                new_photo,
                destination
            )

            # ---------------------------------
            # Verify Destination
            # ---------------------------------

            if not destination.exists():

                print(
                    "Camera Capture Error : "
                    "Photo copy verification failed."
                )

                return None

            if destination.stat().st_size <= 0:

                print(
                    "Camera Capture Error : "
                    "Copied photo is empty."
                )

                return None

            print(
                f"Photo Saved Successfully : "
                f"{destination}"
            )

            return str(
                destination
            )

        except Exception as error:

            print(
                f"Camera Capture Error : {error}"
            )

            return None

    # ==================================================
    # Screenshot
    # ==================================================

    def take_screenshot(self):
        """
        Save a full-screen screenshot.

        Returns
        -------
        str | None
            Absolute path of the saved screenshot when successful.
        """

        try:

            timestamp = time.strftime(
                "%Y%m%d_%H%M%S"
            )

            filename = (
                f"dheepthi_screenshot_{timestamp}.png"
            )

            filepath = (
                self.screenshot_directory /
                filename
            )

            screenshot = pyautogui.screenshot()

            screenshot.save(
                str(filepath)
            )

            # ---------------------------------
            # Verify Screenshot
            # ---------------------------------

            if not filepath.exists():

                print(
                    "DHEEPTHI Screenshot Error : "
                    "Screenshot file was not created."
                )

                return None

            if filepath.stat().st_size <= 0:

                print(
                    "DHEEPTHI Screenshot Error : "
                    "Screenshot file is empty."
                )

                return None

            return str(
                filepath
            )

        except Exception as error:

            print(
                f"DHEEPTHI Screenshot Error : {error}"
            )

            return None
