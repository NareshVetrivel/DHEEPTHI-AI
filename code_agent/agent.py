from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from groq import Groq

try:
    from dotenv import load_dotenv

    # Load the project's .env file so the Code Agent can use
    # GROQ_API_KEY_CODE_AGENT without hard-coding secrets.
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    # If python-dotenv is not installed, environment variables
    # already exported in the shell will still work.
    PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CodeAgent:
    """
    DHEEPTHI Code Agent.

    V1 support:
    - Python
    - Java

    Responsibilities:
    - Detect requested programming language
    - Generate code using Groq Cloud
    - Create DHEEPTHI_program directory
    - Save source code
    - Execute generated programs
    - Return generation/execution results

    Cloud model:
    - Groq Chat Completions API
    - Default model: openai/gpt-oss-20b

    API key:
    - GROQ_API_KEY_CODE_AGENT

    The existing GROQ_API_KEY remains available for STT and is not
    used by this agent.
    """

    # ============================================================
    # CONFIGURATION
    # ============================================================

    GROQ_API_KEY_ENV = "GROQ_API_KEY_CODE_AGENT"

    # Current Groq production model suitable for fast general/code
    # generation. It can be overridden through the environment.
    GROQ_MODEL = os.getenv(
        "GROQ_CODE_AGENT_MODEL",
        "openai/gpt-oss-20b",
    )

    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    SHOW_PROGRAM_TERMINAL = True
    MAX_COMPILE_ATTEMPTS = 3
    EXECUTION_TIMEOUT_SECONDS = 30

    SUPPORTED_LANGUAGES = {
        "python": {
            "folder": "Python",
            "extension": ".py",
        },
        "java": {
            "folder": "Java",
            "extension": ".java",
        },
    }

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self):
        self.desktop_path = Path.home() / "Desktop"

        self.base_path = (
            self.desktop_path / "DHEEPTHI_program"
        )

        self.client: Optional[Groq] = None
        self.model_loaded = False

    # ============================================================
    # API KEY
    # ============================================================

    def get_api_key(self) -> str:
        """
        Return the dedicated Groq Code Agent API key.

        This intentionally uses GROQ_API_KEY_CODE_AGENT instead of
        the existing GROQ_API_KEY used by Speech-to-Text.
        """

        api_key = os.getenv(
            self.GROQ_API_KEY_ENV
        )

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY_CODE_AGENT is not configured. "
                "Add the Code Agent Groq API key to the .env file."
            )

        return api_key.strip()

    # ============================================================
    # LOAD CLOUD CLIENT
    # ============================================================

    def load_model(self):
        """
        Initialize the Groq cloud client.

        Kept as load_model() for compatibility with the previous
        CodeAgent interface. No local model is downloaded or loaded.
        """

        if self.client is not None:
            return self.client

        self.client = Groq(
            api_key=self.get_api_key()
        )

        self.model_loaded = True

        return self.client

    # ============================================================
    # BACKWARD-COMPATIBLE MODEL PATH
    # ============================================================

    def get_model_path(self) -> Path:
        """
        Return the old local model path for compatibility.

        The cloud Code Agent does not require this directory.
        This method is retained so older callers do not fail because
        the method disappeared during the cloud migration.
        """

        return (
            self.PROJECT_ROOT
            / "models"
            / "code_agent"
        )

    # ============================================================
    # TOKENIZER COMPATIBILITY
    # ============================================================

    def load_tokenizer(self):
        """
        Compatibility method.

        The Groq API performs tokenization remotely, so DHEEPTHI does
        not need to load a local tokenizer.
        """

        return None

    # ============================================================
    # LANGUAGE DETECTION
    # ============================================================

    def detect_language(
        self,
        command: str,
    ) -> Optional[str]:
        """
        Detect Python or Java from the user's command.

        Examples:
            write a python code for bfs
            create a python program for factorial
            write a java program for stack and queue
            create java code for binary search
        """

        if not command:
            return None

        text = command.lower().strip()

        # Check Java first when explicitly present.
        if re.search(r"\bjava\b", text):
            return "java"

        # Python can be written as "python" or "py".
        if re.search(r"\bpython\b|\bpy\b", text):
            return "python"

        return None

    # ============================================================
    # FILENAME DETECTION
    # ============================================================

    def detect_filename(
        self,
        command: str,
        language: str,
    ) -> str:
        """
        Detect a filename from the command.

        Examples:
            create python program named test
            create python file hello.py
            write java program named Calculator
            write java code called StackQueue
        """

        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {language}"
            )

        extension = self.SUPPORTED_LANGUAGES[
            language
        ]["extension"]

        patterns = [
            r"\bnamed\s+([A-Za-z0-9_.-]+)",
            r"\bname\s+is\s+([A-Za-z0-9_.-]+)",
            r"\bcalled\s+([A-Za-z0-9_.-]+)",
            r"\bfile\s+([A-Za-z0-9_.-]+)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                command,
                re.IGNORECASE,
            )

            if match:
                filename = match.group(1)

                if not filename.lower().endswith(
                    extension
                ):
                    filename += extension

                return filename

        if language == "python":
            return "program.py"

        if language == "java":
            return "Main.java"

        return f"program{extension}"

    # ============================================================
    # CREATE PROJECT FOLDER
    # ============================================================

    def create_project_folder(
        self,
        language: str,
    ) -> Path:
        """
        Create:

        Desktop/
            DHEEPTHI_program/
                Python/
                Java/
        """

        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {language}"
            )

        language_folder = (
            self.base_path
            / self.SUPPORTED_LANGUAGES[
                language
            ]["folder"]
        )

        language_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        return language_folder

    # ============================================================
    # SAVE CODE
    # ============================================================

    def save_code(
        self,
        language: str,
        filename: str,
        code: str,
    ) -> Path:
        """
        Save generated source code.
        """

        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {language}"
            )

        folder = self.create_project_folder(
            language
        )

        extension = self.SUPPORTED_LANGUAGES[
            language
        ]["extension"]

        if not filename.lower().endswith(
            extension
        ):
            filename += extension

        # Prevent path traversal / nested arbitrary paths.
        filename = Path(filename).name

        file_path = folder / filename

        file_path.write_text(
            code,
            encoding="utf-8",
        )

        return file_path

    # ============================================================
    # EXTRACT CODE
    # ============================================================

    def extract_code(
        self,
        response: str,
        language: str,
    ) -> str:
        """
        Extract source code from a Groq model response.

        Handles:
            ```python
            print("Hello")
            ```

        and:
            ```java
            ...
            ```

        It also cleans common accidental response prefixes/suffixes
        when the model does not follow the source-only instruction.
        """

        if not response:
            return ""

        text = response.strip()

        # --------------------------------------------------------
        # Language-specific fenced block
        # --------------------------------------------------------

        pattern = (
            r"```(?:"
            + re.escape(language)
            + r")?\s*"
            r"(.*?)"
            r"```"
        )

        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:
            return match.group(1).strip()

        # --------------------------------------------------------
        # Generic fenced block
        # --------------------------------------------------------

        generic_match = re.search(
            r"```\s*(.*?)\s*```",
            text,
            re.DOTALL,
        )

        if generic_match:
            code = generic_match.group(1).strip()

            # Remove an accidental language marker.
            if language == "python" and code.lower().startswith(
                "python\n"
            ):
                code = code[7:].lstrip()

            if language == "java" and code.lower().startswith(
                "java\n"
            ):
                code = code[5:].lstrip()

            return code

        # --------------------------------------------------------
        # Remove common code-only prefixes
        # --------------------------------------------------------

        lines = text.splitlines()

        while lines and not lines[0].strip():
            lines.pop(0)

        if lines:
            first = lines[0].strip().lower()

            prefixes = (
                "here is the python code:",
                "here is the python code",
                "here's the python code:",
                "here's the python code",
                "here is the java code:",
                "here is the java code",
                "here's the java code:",
                "here's the java code",
            )

            if first in prefixes:
                lines.pop(0)

        return "\n".join(lines).strip()

    # ============================================================
    # BUILD MODEL PROMPT
    # ============================================================

    def build_generation_prompt(
        self,
        command: str,
        language: str,
        compile_error: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """Build a strict cloud code-generation prompt."""

        language_name = (
            "Python"
            if language == "python"
            else "Java"
        )

        filename_instruction = ""

        if language == "java" and filename:
            class_name = Path(filename).stem
            filename_instruction = f"""
14. The Java source filename is {filename}.
15. The public Java class name MUST be exactly {class_name}.
16. Include a public static void main(String[] args) entry point
    unless the user explicitly requests a different structure.
"""

        system_prompt = f"""
You are DHEEPTHI Code Agent, a professional programming
code-generation assistant.

The requested language is {language_name}.

Generate the complete source code that directly satisfies the user's
programming request.

STRICT RULES:
1. Return ONLY {language_name} source code.
2. Do NOT explain the solution.
3. Do NOT use Markdown code fences.
4. Do NOT write "Here is the code".
5. Do NOT output headings before the code.
6. Follow the user's exact programming request.
7. Generate complete, runnable code.
8. Include all required imports.
9. Do not invent unrelated features.
10. If the request asks for an algorithm or data structure,
    implement that algorithm or data structure completely.
11. For Python, use valid Python 3 syntax.
12. For Java, generate a complete compilable Java program.
13. Prefer a simple runnable example when the user does not
    specify input/output requirements.
{filename_instruction}
"""

        if compile_error:
            system_prompt += f"""
IMPORTANT RETRY INSTRUCTION:

The previous generated program failed compilation.

Compiler error:
{compile_error}

Generate the COMPLETE corrected source code from the beginning.
Do NOT return a patch.
Do NOT return only changed lines.
Do NOT explain the error.
Return ONLY the corrected runnable source code.
Preserve the original requested functionality.
"""

        return [
            {
                "role": "system",
                "content": system_prompt.strip(),
            },
            {
                "role": "user",
                "content": command.strip(),
            },
        ]

    # ============================================================
    # GENERATE CODE USING GROQ
    # ============================================================

    def generate_code(
        self,
        command: str,
        language: Optional[str] = None,
        max_new_tokens: int = 32768,
        compile_error: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> dict:
        """
        Generate Python or Java source code using Groq Cloud.

        Returns:

        {
            "success": True,
            "language": "python",
            "code": "...",
            "raw_response": "...",
            "model": "openai/gpt-oss-20b"
        }
        """

        if not command or not command.strip():
            return {
                "success": False,
                "language": language,
                "code": "",
                "raw_response": "",
                "model": self.GROQ_MODEL,
                "error": "Empty command.",
            }

        # --------------------------------------------------------
        # Detect language
        # --------------------------------------------------------

        if language is None:
            language = self.detect_language(
                command
            )

        if language not in self.SUPPORTED_LANGUAGES:
            return {
                "success": False,
                "language": language,
                "code": "",
                "raw_response": "",
                "model": self.GROQ_MODEL,
                "error": (
                    "Unable to detect supported programming "
                    "language. Supported languages: Python, Java."
                ),
            }

        try:
            # ----------------------------------------------------
            # Initialize Groq client
            # ----------------------------------------------------

            client = self.load_model()

            # ----------------------------------------------------
            # Build messages
            # ----------------------------------------------------

            messages = self.build_generation_prompt(
                command=command,
                language=language,
                compile_error=compile_error,
                filename=filename,
            )

            # ----------------------------------------------------
            # Groq Chat Completion
            # ----------------------------------------------------

            completion = (
                client.chat.completions.create(
                    model=self.GROQ_MODEL,
                    messages=messages,
                    temperature=0.1,
                    max_completion_tokens=max_new_tokens,
                )
            )

            # ----------------------------------------------------
            # Read response
            # ----------------------------------------------------

            raw_response = ""

            if completion.choices:
                message = completion.choices[0].message
                raw_response = (
                    message.content or ""
                )

            # ----------------------------------------------------
            # Extract source code
            # ----------------------------------------------------

            code = self.extract_code(
                raw_response,
                language,
            )

            if not code:
                return {
                    "success": False,
                    "language": language,
                    "code": "",
                    "raw_response": raw_response,
                    "model": self.GROQ_MODEL,
                    "error": (
                        "Groq returned an empty code response."
                    ),
                }

            return {
                "success": True,
                "language": language,
                "code": code,
                "raw_response": raw_response,
                "model": self.GROQ_MODEL,
                "error": "",
            }

        except Exception as error:
            return {
                "success": False,
                "language": language,
                "code": "",
                "raw_response": "",
                "model": self.GROQ_MODEL,
                "error": str(error),
            }

    # ============================================================
    # GENERATE + SAVE
    # ============================================================

    def generate_and_save(
        self,
        command: str,
        language: Optional[str] = None,
        filename: Optional[str] = None,
        max_new_tokens: int = 32768,
    ) -> dict:
        """Generate code and save it to Desktop/DHEEPTHI_program."""

        detected_language = language or self.detect_language(command)

        if detected_language not in self.SUPPORTED_LANGUAGES:
            return self.generate_code(
                command=command,
                language=detected_language,
                max_new_tokens=max_new_tokens,
                filename=filename,
            )

        if filename is None:
            filename = self.detect_filename(
                command,
                detected_language,
            )

        result = self.generate_code(
            command=command,
            language=detected_language,
            max_new_tokens=max_new_tokens,
            filename=filename,
        )

        if not result["success"]:
            return result

        try:
            file_path = self.save_code(
                language=detected_language,
                filename=filename,
                code=result["code"],
            )

            result["language"] = detected_language
            result["file_path"] = str(file_path)
            result["saved"] = True

            return result

        except Exception as error:
            result["saved"] = False
            result["file_path"] = ""
            result["error"] = str(error)

            return result

    # ============================================================
    # COMPILATION
    # ============================================================

    def compile_python(self, file_path: Path) -> dict:
        """Syntax-check Python without displaying compiler output."""

        path = Path(file_path)

        try:
            python_command = sys.executable

            result = subprocess.run(
                [
                    python_command,
                    "-m",
                    "py_compile",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=self.EXECUTION_TIMEOUT_SECONDS,
                cwd=str(path.parent),
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "return_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Python compilation timed out.",
                "return_code": -1,
            }

        except Exception as error:
            return {
                "success": False,
                "output": "",
                "error": str(error),
                "return_code": -1,
            }

    def compile_java(self, file_path: Path) -> dict:
        """Compile Java and return only compiler diagnostics."""

        path = Path(file_path)

        try:
            javac = self._resolve_java_tool("javac")

            if javac is None:
                return {
                    "success": False,
                    "output": "",
                    "error": (
                        "javac was not found. Install a JDK and set "
                        "JAVA_HOME or add the JDK bin folder to PATH."
                    ),
                    "return_code": -1,
                }

            result = subprocess.run(
                [
                    str(javac),
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=self.EXECUTION_TIMEOUT_SECONDS,
                cwd=str(path.parent),
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "return_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Java compilation timed out.",
                "return_code": -1,
            }

        except Exception as error:
            return {
                "success": False,
                "output": "",
                "error": str(error),
                "return_code": -1,
            }

    def compile(self, language: str, file_path: Path) -> dict:
        """Compile/syntax-check source code according to language."""

        if language == "python":
            return self.compile_python(file_path)

        if language == "java":
            return self.compile_java(file_path)

        return {
            "success": False,
            "output": "",
            "error": f"Unsupported language: {language}",
            "return_code": -1,
        }

    # ============================================================
    # EXECUTION
    # ============================================================

    def run_python(self, file_path: Path) -> dict:
        """Launch Python in a dedicated visible Windows console."""

        path = Path(file_path)

        if not path.exists():
            return {
                "success": False,
                "output": "",
                "error": f"Python file not found: {path}",
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        try:
            python_command = sys.executable

            if os.name == "nt" and self.SHOW_PROGRAM_TERMINAL:
                return self._launch_program_terminal(
                    executable=python_command,
                    arguments=[str(path)],
                    working_directory=path.parent,
                    title=f"DHEEPTHI - Python - {path.name}",
                )

            # Non-Windows fallback.  Output is intentionally not exposed
            # to the DHEEPTHI UI by the caller.
            result = subprocess.run(
                [python_command, str(path)],
                capture_output=True,
                text=True,
                timeout=self.EXECUTION_TIMEOUT_SECONDS,
                cwd=str(path.parent),
            )

            return {
                "success": result.returncode == 0,
                "output": "",
                "error": result.stderr.strip(),
                "return_code": result.returncode,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Python program execution timed out.",
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        except Exception as error:
            return {
                "success": False,
                "output": "",
                "error": str(error),
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

    def run_java(
        self,
        file_path: Path,
        already_compiled: bool = False,
    ) -> dict:
        """Execute Java after compilation, using a separate Windows console."""

        path = Path(file_path)

        if not path.exists():
            return {
                "success": False,
                "output": "",
                "error": f"Java file not found: {path}",
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        try:
            compile_result = None

            if not already_compiled:
                compile_result = self.compile_java(path)

                if not compile_result["success"]:
                    compile_error = (
                        compile_result["error"]
                        or compile_result["output"]
                        or "Java compilation failed."
                    )

                    return {
                        "success": False,
                        "output": "",
                        "error": compile_error,
                        "return_code": compile_result["return_code"],
                        "terminal_opened": False,
                        "displayed_in_terminal": False,
                        "compile_error": compile_error,
                    }

            java_command = self._resolve_java_tool("java")

            if java_command is None:
                return {
                    "success": False,
                    "output": "",
                    "error": (
                        "java runtime was not found. Install a JDK/JRE and "
                        "set JAVA_HOME or add its bin folder to PATH."
                    ),
                    "return_code": -1,
                    "terminal_opened": False,
                    "displayed_in_terminal": False,
                }

            class_name = path.stem

            if os.name == "nt" and self.SHOW_PROGRAM_TERMINAL:
                result = self._launch_program_terminal(
                    executable=str(java_command),
                    arguments=[
                        "-cp",
                        str(path.parent),
                        class_name,
                    ],
                    working_directory=path.parent,
                    title=f"DHEEPTHI - Java - {class_name}",
                )

                if compile_result is not None:
                    result["compile_return_code"] = compile_result["return_code"]

                return result

            run_result = subprocess.run(
                [
                    str(java_command),
                    "-cp",
                    str(path.parent),
                    class_name,
                ],
                capture_output=True,
                text=True,
                timeout=self.EXECUTION_TIMEOUT_SECONDS,
                cwd=str(path.parent),
            )

            result = {
                "success": run_result.returncode == 0,
                "output": "",
                "error": run_result.stderr.strip(),
                "return_code": run_result.returncode,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

            if compile_result is not None:
                result["compile_return_code"] = compile_result["return_code"]

            return result

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Java program execution timed out.",
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        except Exception as error:
            return {
                "success": False,
                "output": "",
                "error": str(error),
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

    def execute(
        self,
        language: str,
        file_path: Path,
        already_compiled: bool = False,
    ) -> dict:
        """Execute source code according to language."""

        if language == "python":
            return self.run_python(file_path)

        if language == "java":
            return self.run_java(
                file_path,
                already_compiled=already_compiled,
            )

        return {
            "success": False,
            "output": "",
            "error": f"Unsupported language: {language}",
            "return_code": -1,
            "terminal_opened": False,
            "displayed_in_terminal": False,
        }

    @staticmethod
    def _resolve_executable(
        executable: str,
        fallback: str,
    ) -> str:
        """Resolve an executable from PATH without hard-coding installation paths."""

        resolved = shutil.which(executable)
        if resolved:
            return resolved

        resolved = shutil.which(fallback)
        if resolved:
            return resolved

        return executable

    @staticmethod
    def _resolve_java_tool(tool_name: str) -> Optional[Path]:
        """Resolve java/javac from PATH, JAVA_HOME, and common Windows JDK locations."""

        candidates: list[Path] = []

        found = shutil.which(tool_name)
        if found:
            candidates.append(Path(found))

        java_home_value = os.environ.get("JAVA_HOME", "").strip()
        if java_home_value:
            java_home = Path(java_home_value)
            candidates.extend(
                [
                    java_home / "bin" / f"{tool_name}.exe",
                    java_home / "bin" / tool_name,
                ]
            )

        for root in (
            Path("C:/Program Files/Java"),
            Path("C:/Program Files/Eclipse Adoptium"),
            Path("C:/Program Files/Microsoft"),
        ):
            if not root.exists():
                continue

            try:
                for child in root.iterdir():
                    if child.is_dir():
                        candidates.extend(
                            [
                                child / "bin" / f"{tool_name}.exe",
                                child / "bin" / tool_name,
                            ]
                        )
            except (OSError, PermissionError):
                continue

        for candidate in candidates:
            try:
                if candidate.is_file():
                    return candidate
            except OSError:
                continue

        return None

    def _launch_program_terminal(
        self,
        executable: str,
        arguments: list[str],
        working_directory: Path,
        title: str,
    ) -> dict:
        """Open a NEW visible Windows console and attach program I/O to it."""

        if os.name != "nt":
            return {
                "success": False,
                "output": "",
                "error": "Dedicated program terminal is only available on Windows.",
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
                "terminal_command": "",
                "terminal_path": str(working_directory),
                "terminal_title": title,
            }

        try:
            command_line = subprocess.list2cmdline(
                [str(executable), *[str(arg) for arg in arguments]]
            )

            # cmd.exe /K keeps the program console open after execution and
            # CREATE_NEW_CONSOLE prevents the generated program from using the
            # PowerShell window that launched DHEEPTHI-AI.
            cmd_command = f'cmd.exe /D /K "{command_line}"'

            creation_flags = (
                getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )

            process = subprocess.Popen(
                cmd_command,
                cwd=str(working_directory),
                creationflags=creation_flags,
                stdin=None,
                stdout=None,
                stderr=None,
                close_fds=False,
            )

            print("\n========== CODE AGENT TERMINAL ==========")
            print(f"Terminal Title : {title}")
            print(f"Working Dir   : {working_directory}")
            print(f"Command       : {command_line}")
            print(f"Terminal PID  : {process.pid}")
            print("Output        : NEW VISIBLE CONSOLE")
            print("==========================================\n")

            return {
                "success": True,
                "output": "",
                "error": "",
                "return_code": 0,
                "terminal_opened": True,
                "displayed_in_terminal": True,
                "execution_mode": "new_visible_console",
                "terminal_command": command_line,
                "terminal_path": str(working_directory),
                "pid": process.pid,
                "terminal_title": title,
            }

        except Exception as error:
            return {
                "success": False,
                "output": "",
                "error": f"Unable to open program terminal: {error}",
                "return_code": -1,
                "terminal_opened": False,
                "displayed_in_terminal": False,
                "terminal_command": "",
                "terminal_path": str(working_directory),
                "terminal_title": title,
            }

    # ============================================================
    # COMPLETE V1 WORKFLOW
    # ============================================================

    def generate_save_execute(
        self,
        command: str,
        language: Optional[str] = None,
        filename: Optional[str] = None,
        max_new_tokens: int = 32768,
    ) -> dict:
        """Generate -> save -> compile -> retry -> execute in a separate terminal."""

        if not command or not command.strip():
            return {
                "success": False,
                "language": language,
                "code": "",
                "raw_response": "",
                "model": self.GROQ_MODEL,
                "error": "Empty command.",
                "compile_attempts": 0,
                "executed": False,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        detected_language = language or self.detect_language(command)

        if detected_language not in self.SUPPORTED_LANGUAGES:
            return {
                "success": False,
                "language": detected_language,
                "code": "",
                "raw_response": "",
                "model": self.GROQ_MODEL,
                "error": (
                    "Unable to detect supported programming language. "
                    "Supported languages: Python, Java."
                ),
                "compile_attempts": 0,
                "executed": False,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        if filename is None:
            filename = self.detect_filename(
                command,
                detected_language,
            )

        extension = self.SUPPORTED_LANGUAGES[detected_language]["extension"]
        if not filename.lower().endswith(extension):
            filename += extension
        filename = Path(filename).name

        try:
            language_folder = self.create_project_folder(detected_language)
            file_path = language_folder / filename
        except Exception as error:
            return {
                "success": False,
                "language": detected_language,
                "code": "",
                "raw_response": "",
                "model": self.GROQ_MODEL,
                "error": str(error),
                "compile_attempts": 0,
                "executed": False,
                "terminal_opened": False,
                "displayed_in_terminal": False,
            }

        compile_history: list[dict] = []
        compile_error: Optional[str] = None
        last_generation_result: Optional[dict] = None

        for attempt in range(1, self.MAX_COMPILE_ATTEMPTS + 1):
            try:
                # Always clear the SAME source file before rewriting it.
                self._clear_code_file(file_path)

                generation_result = self.generate_code(
                    command=command,
                    language=detected_language,
                    max_new_tokens=max_new_tokens,
                    compile_error=compile_error,
                    filename=filename,
                )
                last_generation_result = generation_result

                if not generation_result.get("success"):
                    return {
                        **generation_result,
                        "file_path": str(file_path),
                        "saved": False,
                        "compiled": False,
                        "compile_attempts": attempt - 1,
                        "compile_history": compile_history,
                        "execution": None,
                        "executed": False,
                        "terminal_opened": False,
                        "displayed_in_terminal": False,
                    }

                code = generation_result.get("code", "")
                file_path.write_text(code, encoding="utf-8")

                compile_result = self.compile(
                    detected_language,
                    file_path,
                )

                compile_error = (
                    compile_result.get("error")
                    or compile_result.get("output")
                    or "Compilation failed."
                )

                compile_history.append(
                    {
                        "attempt": attempt,
                        "success": bool(compile_result.get("success")),
                        "error": compile_result.get("error", ""),
                        "return_code": compile_result.get("return_code", -1),
                    }
                )

                if not compile_result.get("success"):
                    if attempt < self.MAX_COMPILE_ATTEMPTS:
                        # Loop continues automatically.  The next generation
                        # receives the previous compiler diagnostics.
                        continue

                    # Requirement: after 3 failed compile attempts, clear the
                    # same source file and stop.
                    self._clear_code_file(file_path)

                    return {
                        "success": False,
                        "language": detected_language,
                        "code": code,
                        "raw_response": generation_result.get("raw_response", ""),
                        "model": generation_result.get("model", self.GROQ_MODEL),
                        "error": (
                            "This program could not be compiled after "
                            "3 attempts."
                        ),
                        "compile_error": compile_error,
                        "file_path": str(file_path),
                        "saved": True,
                        "compiled": False,
                        "compile_attempts": attempt,
                        "compile_history": compile_history,
                        "execution": None,
                        "executed": False,
                        "terminal_opened": False,
                        "displayed_in_terminal": False,
                        "program_output": "",
                        "program_output_displayed": False,
                        "stopped_after_max_attempts": True,
                        "requests_used": generation_result.get("requests_used", 0),
                    }

                # Compilation succeeded.  Do not compile again before launch.
                execution_result = self.execute(
                    detected_language,
                    file_path,
                    already_compiled=True,
                )

                terminal_opened = bool(
                    execution_result.get("terminal_opened", False)
                )
                displayed_in_terminal = bool(
                    execution_result.get("displayed_in_terminal", False)
                )

                return {
                    "success": bool(execution_result.get("success", False)),
                    "language": detected_language,
                    "code": code,
                    "raw_response": generation_result.get("raw_response", ""),
                    "model": generation_result.get("model", self.GROQ_MODEL),
                    "error": execution_result.get("error", ""),
                    "file_path": str(file_path),
                    "saved": True,
                    "compiled": True,
                    "compile_attempts": attempt,
                    "compile_history": compile_history,
                    "compile_result": compile_result,
                    "execution": execution_result,
                    "executed": True,
                    "terminal_opened": terminal_opened,
                    "displayed_in_terminal": displayed_in_terminal,
                    # Never expose generated-program stdout through this
                    # response.  The separate terminal owns that output.
                    "program_output": "",
                    "program_output_displayed": displayed_in_terminal,
                    "user_message": (
                        "Program generated, compiled and opened in a separate terminal."
                    ),
                    "requests_used": generation_result.get("requests_used", 0),
                }

            except Exception as error:
                return {
                    "success": False,
                    "language": detected_language,
                    "code": (
                        last_generation_result.get("code", "")
                        if last_generation_result
                        else ""
                    ),
                    "raw_response": (
                        last_generation_result.get("raw_response", "")
                        if last_generation_result
                        else ""
                    ),
                    "model": self.GROQ_MODEL,
                    "error": str(error),
                    "file_path": str(file_path),
                    "saved": file_path.exists(),
                    "compiled": False,
                    "compile_attempts": attempt - 1,
                    "compile_history": compile_history,
                    "execution": None,
                    "executed": False,
                    "terminal_opened": False,
                    "displayed_in_terminal": False,
                }

        return {
            "success": False,
            "language": detected_language,
            "code": (
                last_generation_result.get("code", "")
                if last_generation_result
                else ""
            ),
            "raw_response": (
                last_generation_result.get("raw_response", "")
                if last_generation_result
                else ""
            ),
            "model": self.GROQ_MODEL,
            "error": "Code Agent stopped unexpectedly.",
            "file_path": str(file_path),
            "compile_attempts": len(compile_history),
            "compile_history": compile_history,
            "execution": None,
            "executed": False,
            "terminal_opened": False,
            "displayed_in_terminal": False,
            "program_output": "",
            "program_output_displayed": False,
        }

    def _clear_code_file(self, file_path: Path) -> Path:
        """Clear the existing source file before every generation/retry."""

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return path

