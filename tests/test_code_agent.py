
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ================================================================
# MAKE PROJECT ROOT IMPORTABLE
# ================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from code_agent.agent import CodeAgent


# ================================================================
# BASIC TESTS
# ================================================================

def test_code_agent_import():
    """
    Verify that DHEEPTHI-AI CodeAgent can be imported successfully.
    """

    agent = CodeAgent()

    assert agent is not None
    assert isinstance(agent, CodeAgent)


def test_code_agent_cloud_configuration():
    """
    Verify that the Code Agent is configured for Groq Cloud.
    """

    agent = CodeAgent()

    assert agent.GROQ_API_KEY_ENV == "GROQ_API_KEY_CODE_AGENT"
    assert agent.GROQ_MODEL
    assert hasattr(agent, "client")
    assert agent.client is None


def test_code_agent_api_key_configuration(monkeypatch):
    """
    Verify that CodeAgent reads the dedicated Groq API key.
    """

    test_key = "test-code-agent-key"

    monkeypatch.setenv(
        "GROQ_API_KEY_CODE_AGENT",
        test_key,
    )

    agent = CodeAgent()

    assert agent.get_api_key() == test_key


def test_missing_code_agent_api_key(monkeypatch):
    """
    Verify that a clear error is raised when the dedicated
    Code Agent Groq API key is missing.
    """

    monkeypatch.delenv(
        "GROQ_API_KEY_CODE_AGENT",
        raising=False,
    )

    agent = CodeAgent()

    with pytest.raises(RuntimeError):
        agent.get_api_key()


# ================================================================
# CLOUD CLIENT TEST
# ================================================================

def test_load_model_creates_groq_client(monkeypatch):
    """
    Verify that load_model() creates the Groq cloud client.

    This test does not make a real API request.
    """

    monkeypatch.setenv(
        "GROQ_API_KEY_CODE_AGENT",
        "test-code-agent-key",
    )

    agent = CodeAgent()

    client = agent.load_model()

    assert client is not None
    assert agent.client is client
    assert agent.model_loaded is True


def test_load_model_is_cached(monkeypatch):
    """
    Verify that the Groq client is initialized only once.
    """

    monkeypatch.setenv(
        "GROQ_API_KEY_CODE_AGENT",
        "test-code-agent-key",
    )

    agent = CodeAgent()

    first_client = agent.load_model()
    second_client = agent.load_model()

    assert first_client is second_client


# ================================================================
# LANGUAGE DETECTION
# ================================================================

@pytest.mark.parametrize(
    "command, expected",
    [
        ("write a python code for bfs", "python"),
        ("write a python program for stack", "python"),
        ("create a java program for stack and queue", "java"),
        ("write java code for binary search", "java"),
        ("create python program for factorial", "python"),
        ("create java program for palindrome", "java"),
        ("write py code for calculator", "python"),
    ],
)
def test_detect_language(
    command: str,
    expected: str,
):
    """
    Verify Python and Java language detection.
    """

    agent = CodeAgent()

    result = agent.detect_language(command)

    assert result == expected


def test_detect_unsupported_language():
    """
    Verify that unsupported languages return None.
    """

    agent = CodeAgent()

    result = agent.detect_language(
        "write a C++ program for bfs"
    )

    assert result is None


def test_detect_empty_language():
    """
    Verify that an empty command returns None.
    """

    agent = CodeAgent()

    assert agent.detect_language("") is None


# ================================================================
# FILENAME DETECTION
# ================================================================

def test_detect_python_filename():
    """
    Verify Python filename detection.
    """

    agent = CodeAgent()

    filename = agent.detect_filename(
        "write a python code named bfs",
        "python",
    )

    assert filename == "bfs.py"


def test_detect_java_filename():
    """
    Verify Java filename detection.
    """

    agent = CodeAgent()

    filename = agent.detect_filename(
        "write java code named StackQueue",
        "java",
    )

    assert filename == "StackQueue.java"


def test_default_python_filename():
    """
    Verify default Python filename.
    """

    agent = CodeAgent()

    filename = agent.detect_filename(
        "write python code for bfs",
        "python",
    )

    assert filename == "program.py"


def test_default_java_filename():
    """
    Verify default Java filename.
    """

    agent = CodeAgent()

    filename = agent.detect_filename(
        "write a java program for stack",
        "java",
    )

    assert filename == "Main.java"


def test_filename_does_not_duplicate_extension():
    """
    Verify that an existing extension is not duplicated.
    """

    agent = CodeAgent()

    python_filename = agent.detect_filename(
        "write python code named bfs.py",
        "python",
    )

    java_filename = agent.detect_filename(
        "write java code named Main.java",
        "java",
    )

    assert python_filename == "bfs.py"
    assert java_filename == "Main.java"


# ================================================================
# CODE EXTRACTION
# ================================================================

def test_extract_python_code():
    """
    Verify Python code extraction from markdown fence.
    """

    agent = CodeAgent()

    response = """```python
from collections import deque

def bfs(graph, start):
    visited = set()
    queue = deque([start])
    visited.add(start)

    while queue:
        node = queue.popleft()
        print(node)

        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)
```"""

    code = agent.extract_code(
        response,
        "python",
    )

    assert "def bfs" in code
    assert "deque" in code
    assert "```" not in code


def test_extract_java_code():
    """
    Verify Java code extraction from markdown fence.
    """

    agent = CodeAgent()

    response = """```java
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello World");
    }
}
```"""

    code = agent.extract_code(
        response,
        "java",
    )

    assert "public class Main" in code
    assert 'System.out.println("Hello World")' in code
    assert "```" not in code


def test_extract_plain_code():
    """
    Verify extraction when the model returns plain source code.
    """

    agent = CodeAgent()

    response = 'print("Hello World")'

    code = agent.extract_code(
        response,
        "python",
    )

    assert code == response


def test_extract_empty_response():
    """
    Verify empty model responses are handled safely.
    """

    agent = CodeAgent()

    assert agent.extract_code("", "python") == ""


# ================================================================
# PROMPT GENERATION
# ================================================================

def test_build_generation_prompt_python():
    """
    Verify the Groq generation prompt for Python.
    """

    agent = CodeAgent()

    messages = agent.build_generation_prompt(
        "write a python program for factorial",
        "python",
    )

    assert isinstance(messages, list)
    assert len(messages) == 2

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    assert "Python" in messages[0]["content"]
    assert (
        "write a python program for factorial"
        in messages[1]["content"]
    )


def test_build_generation_prompt_java():
    """
    Verify the Groq generation prompt for Java.
    """

    agent = CodeAgent()

    messages = agent.build_generation_prompt(
        "write a java program for palindrome",
        "java",
    )

    assert isinstance(messages, list)
    assert len(messages) == 2

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    assert "Java" in messages[0]["content"]
    assert (
        "write a java program for palindrome"
        in messages[1]["content"]
    )


# ================================================================
# SAVE CODE
# ================================================================

def test_save_python_code(tmp_path):
    """
    Verify Python source code is saved correctly.
    """

    agent = CodeAgent()

    agent.base_path = (
        tmp_path / "DHEEPTHI_program"
    )

    code = """from collections import deque

def bfs(graph, start):
    visited = set([start])
    queue = deque([start])

    while queue:
        node = queue.popleft()
        print(node)

        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)
"""

    file_path = agent.save_code(
        language="python",
        filename="bfs.py",
        code=code,
    )

    assert file_path.exists()
    assert file_path.is_file()
    assert file_path.suffix == ".py"

    saved_code = file_path.read_text(
        encoding="utf-8"
    )

    assert saved_code == code


def test_save_java_code(tmp_path):
    """
    Verify Java source code is saved correctly.
    """

    agent = CodeAgent()

    agent.base_path = (
        tmp_path / "DHEEPTHI_program"
    )

    code = """public class Main {
    public static void main(String[] args) {
        System.out.println("Hello World");
    }
}"""

    file_path = agent.save_code(
        language="java",
        filename="Main.java",
        code=code,
    )

    assert file_path.exists()
    assert file_path.is_file()
    assert file_path.suffix == ".java"

    saved_code = file_path.read_text(
        encoding="utf-8"
    )

    assert saved_code == code


def test_save_code_adds_missing_extension(tmp_path):
    """
    Verify that save_code() adds the correct source extension.
    """

    agent = CodeAgent()

    agent.base_path = (
        tmp_path / "DHEEPTHI_program"
    )

    python_path = agent.save_code(
        language="python",
        filename="bfs",
        code='print("BFS")',
    )

    java_path = agent.save_code(
        language="java",
        filename="Main",
        code="public class Main {}",
    )

    assert python_path.name == "bfs.py"
    assert java_path.name == "Main.java"


def test_save_code_removes_path_components(tmp_path):
    """
    Verify that arbitrary path components are removed from filenames.
    """

    agent = CodeAgent()

    agent.base_path = (
        tmp_path / "DHEEPTHI_program"
    )

    file_path = agent.save_code(
        language="python",
        filename="../unsafe.py",
        code='print("safe")',
    )

    assert file_path.name == "unsafe.py"
    assert file_path.parent == (
        tmp_path / "DHEEPTHI_program" / "Python"
    )


# ================================================================
# EXECUTION TESTS
# ================================================================

def test_run_python(tmp_path):
    """
    Verify that a Python program can be executed.
    """

    agent = CodeAgent()

    file_path = tmp_path / "hello.py"

    file_path.write_text(
        'print("Hello World")',
        encoding="utf-8",
    )

    result = agent.run_python(file_path)

    assert result["success"] is True
    assert result["output"] == "Hello World"
    assert result["return_code"] == 0


def test_execute_unsupported_language(tmp_path):
    """
    Verify unsupported execution languages return an error.
    """

    agent = CodeAgent()

    file_path = tmp_path / "program.txt"

    file_path.write_text(
        "test",
        encoding="utf-8",
    )

    result = agent.execute(
        "cpp",
        file_path,
    )

    assert result["success"] is False
    assert result["return_code"] == -1
    assert "Unsupported language" in result["error"]


# ================================================================
# GENERATION VALIDATION TESTS
# ================================================================

def test_generate_code_rejects_empty_command():
    """
    Verify empty generation requests fail before contacting Groq.
    """

    agent = CodeAgent()

    result = agent.generate_code("")

    assert result["success"] is False
    assert result["code"] == ""
    assert "Empty command" in result["error"]


def test_generate_code_rejects_unsupported_language():
    """
    Verify unsupported languages are rejected before contacting Groq.
    """

    agent = CodeAgent()

    result = agent.generate_code(
        command="write a C++ program for bfs",
        language="cpp",
    )

    assert result["success"] is False
    assert result["language"] == "cpp"
    assert result["code"] == ""
    assert "Supported languages" in result["error"]


# ================================================================
# REAL GROQ CLOUD INTERACTIVE TEST
# ================================================================
#
# Run from project root:
#
#     python tests/test_code_agent.py
#
# This starts the real Groq Cloud Code Agent.
#
# Examples:
#
#     write a python code for bfs
#     write a python program for factorial
#     write a python code for binary search
#     write a python program for stack
#     write a java program for stack and queue
#     write java code for palindrome
#
# The generated source code is printed directly in the same terminal.
#
# Type "exit" or "quit" to stop.
# ================================================================

def run_interactive_test():
    """
    Run the real DHEEPTHI-AI Code Agent interactively.

    This sends the user's command to Groq Cloud and prints the
    generated source code.
    """

    agent = CodeAgent()

    print()
    print("=" * 70)
    print("DHEEPTHI-AI CODE AGENT - GROQ CLOUD TEST")
    print("=" * 70)
    print()

    print("Supported languages : Python, Java")
    print("Generation provider : Groq Cloud")
    print(
        f"Model                : {agent.GROQ_MODEL}"
    )
    print(
        "API key variable      : GROQ_API_KEY_CODE_AGENT"
    )

    print()
    print("Examples:")
    print("  write a python code for bfs")
    print("  write a python program for factorial")
    print("  write a python code for binary search")
    print("  write a python program for stack")
    print("  write a java program for stack and queue")
    print("  write java code for palindrome")

    print()
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 70)

    while True:

        try:
            command = input(
                "DHEEPTHI-AI > "
            ).strip()

        except (
            KeyboardInterrupt,
            EOFError,
        ):

            print()
            print(
                "Exiting Code Agent test."
            )
            break

        if not command:
            continue

        if command.lower() in {
            "exit",
            "quit",
        }:

            print()
            print(
                "Exiting Code Agent test."
            )
            break

        language = agent.detect_language(
            command
        )

        if language is None:

            print()
            print(
                "ERROR: Only Python and Java are supported."
            )
            print(
                "Please mention Python or Java in the command."
            )
            print()

            continue

        print()
        print("-" * 70)
        print("REQUEST")
        print("-" * 70)
        print(
            f"Language : {language}"
        )
        print(
            f"Command  : {command}"
        )
        print("-" * 70)

        print(
            "Generating with Groq Cloud..."
        )

        print()

        result = agent.generate_code(
            command=command,
            language=language,
            max_new_tokens=1024,
        )

        print("-" * 70)
        print("GENERATED CODE")
        print("-" * 70)

        if result.get("success"):

            print(
                result["code"]
            )

            print()
            print(
                f"Model : {result.get('model', agent.GROQ_MODEL)}"
            )

        else:

            print(
                "Code generation failed."
            )

            print()
            print("Error:")

            print(
                result.get(
                    "error",
                    "Unknown error.",
                )
            )

        print("-" * 70)
        print()


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    run_interactive_test()
