"""
Application settings for ASTRA-AI.
"""

import os

from dotenv import load_dotenv


# ==========================================================
# Load Environment Variables
# ==========================================================

load_dotenv()


# ==========================================================
# Application Information
# ==========================================================

APP_NAME = "ASTRA-AI"

APP_VERSION = "0.1.0"

APP_AUTHOR = "Naresh"


# ==========================================================
# Window Settings
# ==========================================================

WINDOW_WIDTH = 700

WINDOW_HEIGHT = 500

WINDOW_TITLE = APP_NAME


# ==========================================================
# UI Settings
# ==========================================================

DEFAULT_STATUS = "Ready"

WELCOME_MESSAGE = (
    "Welcome to ASTRA-AI"
)


# ==========================================================
# File Indexing Settings
# ==========================================================

INDEX_USER_FOLDERS = [

    "Desktop",

    "Documents",

    "Downloads",

    "Pictures",

    "Videos",

    "Music",

]


# ==========================================================
# Custom Folders Outside User Profile
# ==========================================================

# Example:
#
# r"E:\College"
#
# r"E:\Projects"
#
# r"E:\TANCET"

INDEX_CUSTOM_FOLDERS = [

]


# ==========================================================
# Microphone
# ==========================================================

MIC_BUTTON_TEXT = "🎤"


# ==========================================================
# Gemini API Configuration
# ==========================================================

# ----------------------------------------------------------
# Gemini API Key 1
# ----------------------------------------------------------

GEMINI_API_KEY_1 = os.getenv(
    "GEMINI_API_KEY_1",
    ""
).strip()


# ----------------------------------------------------------
# Gemini API Key 2
# ----------------------------------------------------------

GEMINI_API_KEY_2 = os.getenv(
    "GEMINI_API_KEY_2",
    ""
).strip()


# ----------------------------------------------------------
# Gemini API Key 3
# ----------------------------------------------------------

GEMINI_API_KEY_3 = os.getenv(
    "GEMINI_API_KEY_3",
    ""
).strip()


# ----------------------------------------------------------
# Gemini API Key 4
# ----------------------------------------------------------

GEMINI_API_KEY_4 = os.getenv(
    "GEMINI_API_KEY_4",
    ""
).strip()


# ----------------------------------------------------------
# Gemini Model
# ----------------------------------------------------------

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "models/gemini-3.5-flash"
).strip()

# ----------------------------------------------------------
# Gemini Semantic Planner Model Hierarchy
# ----------------------------------------------------------

GEMINI_PLANNER_PRIMARY_MODEL = os.getenv(
    "GEMINI_PLANNER_PRIMARY_MODEL",
    "gemini-3.8-flash"
).strip()

GEMINI_PLANNER_FALLBACK_1 = os.getenv(
    "GEMINI_PLANNER_FALLBACK_1",
    "gemini-3.7-flash"
).strip()

GEMINI_PLANNER_FALLBACK_2 = os.getenv(
    "GEMINI_PLANNER_FALLBACK_2",
    "gemini-3.6-flash"
).strip()


# ==========================================================
# Debug Configuration
# ==========================================================

DEBUG = (

    os.getenv(
        "DEBUG",
        "False"
    ).strip().lower()

    == "true"

)