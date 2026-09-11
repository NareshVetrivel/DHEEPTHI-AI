dai ithula eppadi da repo name ah changes pannurathu???
Today 1:33 PM
DHEEPTHI-AI.zip
Zip Archive
dai intha zip file la full la analyze panni report generate pannuda @Deep research 


ithu vachi namma after readme file la ready pannuvom da nanba seriya???
DHEEPTHI-AI.zip
Zip Archive
@Deep research dai intha zip file full la analyze panni oru report generate pannuda 

ithu vachi namma after readme file la ready pannuvom da ?????
README.md
File
dai ennaku ippo ne analyze pannala athu base ennaku readme file la update panni kududa

ennaku oru downloadable file la kududa ??

Aama da nanba ❤️ analyze pannina findings base panni README update panniten. Un existing README structure-um preserve panni, unsupported details invent pannama clean-ah update pannirukken.

📄 Download

⬇️ Download the updated DHEEPTHI-AI README.md

Validation: PASSED ✅
Old ASTRA-AI README heading: removed
New project name: DHEEPTHI-AI
Run command: python -m app.main
GitHub repo: NareshVetrivel/DHEEPTHI-AI

Idha direct-ah un project root-la README.md replace pannalaam da. 🔥 

DHEEPTHI-AI_README.md
Document

DHEEPTHI-AI_README.md
DHEEPTHI-AI

DHEEPTHI-AI is an Adaptive Context-Aware Natural Language Voice Assistant for Personalized Desktop Automation.

Project Status

🚧 Under Development

Overview

DHEEPTHI-AI is a Python-based Windows desktop voice-assistant and automation project designed to understand natural-language commands and perform computer operations through a modular application architecture.

The project combines a graphical user interface, voice interaction, natural-language processing components, desktop automation, computer-vision capabilities, background initialization, and local data storage.

The main application is launched through the app.main module.

Current Features
Voice Recognition
Intent Detection
Entity Extraction
GUI Interface
Application Launch Automation
AI/language-model agent components
Computer-vision functionality
YOLO-based object detection
Local SQLite data storage
Background initialization worker
Modular UI components
Custom application title bar
Splash-screen startup experience

Implementation note: Feature descriptions are based on the supplied project materials and project analysis. Some capabilities are still under development.

Technology Stack
Python — Core programming language
PySide6 — Desktop graphical user interface
SQLite — Local database storage
PyAutoGUI — Desktop/input automation
PyWinAuto — Windows UI automation
SpeechRecognition — Speech/voice input
YOLO model (yolo11n.pt) — Computer-vision/object-detection component
Architecture

The project is organized into separate modules for application startup, UI, background workers, AI/code-agent functionality, computer vision, database storage, and testing.

DHEEPTHI-AI/
├── app/
│   └── main.py
├── code_agent/
├── database/
│   └── astra.db
├── ui/
│   ├── components/
│   │   └── header.py
│   ├── assets/
│   │   ├── dheepthi_logo-1.png
│   │   └── dheepthi_logo-2.png
│   ├── main_window.py
│   └── splash_screen.py
├── vision/
├── workers/
│   └── initialization_worker.py
├── tests/
│   ├── results/
│   ├── vision_samples/
│   ├── vision_click_output.txt
│   └── vision_output.txt
└── yolo11n.pt
Main Modules
Module	Responsibility
app/	Application startup and entry-point logic
ui/	Main desktop interface and UI components
ui/components/	Reusable interface components
ui/assets/	Application logos and visual assets
code_agent/	AI/language-model agent functionality
vision/	Computer-vision related functionality
workers/	Background initialization and worker processes
database/	Local SQLite data storage
tests/	Test data and vision-related test outputs
Application Entry Point

The application is started from the project root with:

python -m app.main

The app.main module initializes the desktop application and starts the main DHEEPTHI-AI window.

UI

The graphical interface is implemented with PySide6.

The UI includes:

Main application window
Custom title bar
Application branding and icons
Splash screen
Header component
Status/progress presentation
Desktop-oriented controls and interface components

The project uses assets from:

ui/assets/
Voice and Natural-Language Processing

The project is designed around natural-language voice interaction.

The current implementation includes components for:

Voice recognition
Intent detection
Entity extraction
Command interpretation
Desktop action execution

This allows the system to move from a spoken natural-language request toward an application or computer action.

Desktop Automation

DHEEPTHI-AI includes Windows desktop automation functionality using:

PyAutoGUI
PyWinAuto

These components support interaction with desktop applications and user-interface elements.

Application launch automation is included in the current feature set.

Computer Vision

The project contains a dedicated vision/ module and includes the YOLO model:

yolo11n.pt

Vision-related test samples and outputs are also present under:

tests/vision_samples/
tests/results/
tests/vision_output.txt
tests/vision_click_output.txt

The vision subsystem supports the project's computer-vision and automation workflow.

Data Storage

The project contains a local SQLite database:

database/astra.db

The database is part of the application's local data/storage layer.

The supplied project materials did not expose a separate SQL schema/documentation file, so the exact database schema is not specified in this README.

Dependencies

The supplied project materials do not contain a dedicated requirements.txt or pyproject.toml file.

The documented/current technology stack includes:

Python
PySide6
SQLite
PyAutoGUI
PyWinAuto
SpeechRecognition
YOLO / computer-vision model

For reproducible installation, an explicit dependency file should match the actual Python imports used by the current source tree.

Installation

Clone the repository:

git clone https://github.com/NareshVetrivel/DHEEPTHI-AI.git
cd DHEEPTHI-AI

Create and activate a virtual environment:

python -m venv .venv
.\.venv\Scripts\Activate.ps1

Install the project's required Python packages according to the dependency configuration used by the current development environment.

Running DHEEPTHI-AI

From the project root:

python -m app.main

The application starts through the app.main entry point.

Testing

The repository contains vision-related test samples and generated outputs:

tests/
├── results/
├── vision_samples/
├── vision_click_output.txt
└── vision_output.txt

These files are part of the project's current testing and validation workflow.

Project Development

DHEEPTHI-AI is currently under active development as a modular desktop AI assistant.

The major development areas include:

Natural-language voice interaction
Intent and entity processing
Desktop automation
AI agent integration
Computer vision
GUI-based interaction
Local data management
Background initialization
Repository

GitHub repository:

https://github.com/NareshVetrivel/DHEEPTHI-AI

Author

Naresh Vetrivel

Note: DHEEPTHI-AI is a work in progress. Features, architecture, models, and implementation details may change as development continues.