"""
DHEEPTHI-AI
Gemini Structured Plan Fallback Tests

Tests the structured planning fallback chain:

    Gemini Key 1
        ↓
    Gemini Key 2
        ↓
    Gemini Key 3
        ↓
    Gemini Key 4
        ↓
    GROQ_API_KEY_CODE_AGENT
        ↓
    Structured JSON plan

These tests intentionally DO NOT call real Gemini or Groq APIs.
All cloud responses are mocked so API quota is not consumed.
"""

from __future__ import annotations

# ============================================================
# Project Root Import Fix
# ============================================================

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Standard Imports
# ============================================================

import json

import pytest

from ai.gemini_client import GeminiClient
from planner.action_models import ActionPlan
from planner.multi_command_planner import MultiCommandPlanner


# ============================================================
# Test Data
# ============================================================

VALID_PLAN = {
    "original_command": "open chrome then search Sona College",
    "description": "Open Chrome and search for Sona College",
    "steps": [
        {
            "step_id": "step_1",
            "action": "launch_application",
            "parameters": {
                "application": "chrome",
            },
            "description": "Open Chrome",
        },
        {
            "step_id": "step_2",
            "action": "google_search",
            "parameters": {
                "query": "Sona College",
            },
            "description": "Search for Sona College",
        },
    ],
}


# ============================================================
# Fake Gemini Response Objects
# ============================================================


class FakeGeminiResponse:
    """
    Minimal fake Gemini response.

    Matches the part of google-genai response used by
    GeminiClient.generate_structured_plan().
    """

    def __init__(self, text: str):
        self.text = text


class FakeGeminiModels:
    """
    Fake Gemini models interface.

    This replaces:

        client.client.models.generate_content()

    so no real Gemini request can happen.
    """

    def __init__(
        self,
        responses=None,
        error: Exception | None = None,
    ):
        self.responses = list(
            responses or []
        )

        self.error = error

        self.calls = 0

        self.prompts = []

        self.models = []

    def generate_content(
        self,
        *,
        model,
        contents,
        config,
    ):
        self.calls += 1

        self.models.append(
            model
        )

        self.prompts.append(
            contents
        )

        if self.error is not None:
            raise self.error

        if not self.responses:
            raise RuntimeError(
                "Fake Gemini has no configured response."
            )

        response = self.responses.pop(
            0
        )

        if isinstance(
            response,
            Exception,
        ):
            raise response

        return FakeGeminiResponse(
            response
        )


class FakeGeminiAPI:
    """
    Fake top-level Gemini API client.
    """

    def __init__(
        self,
        responses=None,
        error: Exception | None = None,
    ):
        self.models = FakeGeminiModels(
            responses=responses,
            error=error,
        )


# ============================================================
# Fake Groq Response Objects
# ============================================================


class FakeGroqCompletion:
    """
    Fake Groq completion response.
    """

    class Message:
        def __init__(
            self,
            content: str,
        ):
            self.content = content

    class Choice:
        def __init__(
            self,
            content: str,
        ):
            self.message = (
                FakeGroqCompletion.Message(
                    content
                )
            )

    def __init__(
        self,
        content: str,
    ):
        self.choices = [
            self.Choice(
                content
            )
        ]


class FakeGroqCompletions:
    """
    Fake chat.completions interface.
    """

    def __init__(
        self,
        response: str,
    ):
        self.response = response

        self.calls = 0

        self.kwargs_history = []

    def create(
        self,
        **kwargs,
    ):
        self.calls += 1

        self.kwargs_history.append(
            kwargs
        )

        return FakeGroqCompletion(
            self.response
        )


class FakeGroqChat:
    """
    Fake Groq chat interface.
    """

    def __init__(
        self,
        response: str,
    ):
        self.completions = (
            FakeGroqCompletions(
                response
            )
        )


class FakeGroqClient:
    """
    Fake Groq client.

    Captures request details so tests can verify:

        GROQ_API_KEY_CODE_AGENT
        GROQ_CODE_AGENT_MODEL
    """

    def __init__(
        self,
        response: str,
    ):
        self.chat = FakeGroqChat(
            response
        )


# ============================================================
# Fake MultiCommandPlanner Gemini Client
# ============================================================


class FakePlannerGeminiClient:
    """
    Minimal fake GeminiClient used only for testing
    MultiCommandPlanner.

    No external API calls are possible.
    """

    def __init__(
        self,
        response: str,
    ):
        self.response = response
        self.calls = 0
        self.prompts = []

    def generate_structured_plan(
        self,
        prompt: str,
    ) -> str:

        self.calls += 1

        self.prompts.append(
            prompt
        )

        return self.response


# ============================================================
# Helpers
# ============================================================


def create_client() -> GeminiClient:
    """
    Create a GeminiClient instance.

    The real Gemini API client is immediately replaced by
    a fake object before any network request can happen.
    """

    client = GeminiClient()

    return client


def install_fake_gemini(
    client: GeminiClient,
    *,
    responses=None,
    error: Exception | None = None,
) -> FakeGeminiAPI:
    """
    Replace the internal Gemini API client with a fake.

    This is important because the actual implementation calls:

        self.client.models.generate_content(...)

    directly.
    """

    fake_api = FakeGeminiAPI(
        responses=responses,
        error=error,
    )

    client.client = fake_api

    return fake_api


def disable_gemini_retry_delay(
    monkeypatch,
    client: GeminiClient,
) -> None:
    """
    Disable retry sleeps during unit tests.
    """

    if hasattr(
        client,
        "_retry_delay",
    ):
        monkeypatch.setattr(
            client,
            "_retry_delay",
            lambda *args, **kwargs: None,
        )


# ============================================================
# 1. Gemini Success Must Not Use Groq
# ============================================================


def test_gemini_success_does_not_use_groq(
    monkeypatch,
):
    """
    When Gemini succeeds, the Groq fallback must not execute.
    """

    client = create_client()

    disable_gemini_retry_delay(
        monkeypatch,
        client,
    )

    gemini_response = json.dumps(
        VALID_PLAN
    )

    fake_gemini = install_fake_gemini(
        client,
        responses=[
            gemini_response,
        ],
    )

    groq_calls = {
        "count": 0,
    }

    def fake_groq_generation(
        *args,
        **kwargs,
    ):
        groq_calls["count"] += 1

        raise AssertionError(
            "Groq fallback was called "
            "even though Gemini succeeded."
        )

    monkeypatch.setattr(
        client,
        "_generate_groq_structured_plan",
        fake_groq_generation,
    )

    result = client.generate_structured_plan(
        "Create a plan to open Chrome "
        "and search Sona College."
    )

    assert result

    assert json.loads(
        result
    ) == VALID_PLAN

    assert (
        fake_gemini.models.calls
        == 1
    )

    assert (
        groq_calls["count"]
        == 0
    )


# ============================================================
# 2. All Gemini Keys Fail -> Groq Fallback
# ============================================================


def test_all_gemini_keys_fail_then_groq_fallback(
    monkeypatch,
):
    """
    Simulate all Gemini keys failing.

    Expected:

        Gemini 1 -> fail
        Gemini 2 -> fail
        Gemini 3 -> fail
        Gemini 4 -> fail
        Groq Code Agent -> success
    """

    client = create_client()

    disable_gemini_retry_delay(
        monkeypatch,
        client,
    )

    # --------------------------------------------------------
    # Gemini always fails with a retryable 429 error.
    # --------------------------------------------------------

    fake_gemini = install_fake_gemini(
        client,
        error=RuntimeError(
            "429 RESOURCE_EXHAUSTED "
            "simulated Gemini quota failure"
        ),
    )

    # --------------------------------------------------------
    # Track Gemini client recreation during key rotation.
    # --------------------------------------------------------

    original_create_client = (
        client._create_client
    )

    create_client_calls = {
        "count": 0,
    }

    def fake_create_client():
        create_client_calls["count"] += 1

        # Do NOT create a real Google client.
        #
        # Keep using the fake Gemini client so every
        # rotated key also fails safely.
        client.client = fake_gemini

    monkeypatch.setattr(
        client,
        "_create_client",
        fake_create_client,
    )

    # --------------------------------------------------------
    # Groq succeeds.
    # --------------------------------------------------------

    groq_response = json.dumps(
        VALID_PLAN
    )

    groq_calls = {
        "count": 0,
    }

    def fake_groq_generation(
        prompt,
    ):
        groq_calls["count"] += 1

        return groq_response

    monkeypatch.setattr(
        client,
        "_generate_groq_structured_plan",
        fake_groq_generation,
    )

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    result = client.generate_structured_plan(
        "Open Chrome and search Sona College."
    )

    assert result

    parsed = json.loads(
        result
    )

    assert parsed == VALID_PLAN

    # Four configured Gemini keys should be attempted.
    assert (
        fake_gemini.models.calls
        == len(client.api_keys)
    )

    assert (
        len(client.api_keys)
        >= 1
    )

    # Key rotation should recreate the Gemini client
    # between failed attempts.
    if len(client.api_keys) > 1:
        assert (
            create_client_calls["count"]
            >= len(client.api_keys) - 1
        )

    # Groq fallback must execute exactly once.
    assert (
        groq_calls["count"]
        == 1
    )


# ============================================================
# 3. Groq Fallback Must Return Valid JSON
# ============================================================


def test_groq_fallback_returns_valid_json(
    monkeypatch,
):
    """
    Verify that the Groq fallback result is valid JSON and
    contains the expected ActionPlan schema.
    """

    client = create_client()

    disable_gemini_retry_delay(
        monkeypatch,
        client,
    )

    # Force every Gemini request to fail.
    install_fake_gemini(
        client,
        error=RuntimeError(
            "429 RESOURCE_EXHAUSTED "
            "simulated Gemini failure"
        ),
    )

    # Prevent real Gemini client creation during rotation.
    def fake_create_client():
        client.client = client.client

    monkeypatch.setattr(
        client,
        "_create_client",
        fake_create_client,
    )

    groq_response = json.dumps(
        VALID_PLAN
    )

    monkeypatch.setattr(
        client,
        "_generate_groq_structured_plan",
        lambda prompt: groq_response,
    )

    result = client.generate_structured_plan(
        "Open Chrome then search Sona College."
    )

    assert result

    data = json.loads(
        result
    )

    assert isinstance(
        data,
        dict,
    )

    assert "steps" in data

    assert isinstance(
        data["steps"],
        list,
    )

    assert len(
        data["steps"]
    ) == 2


# ============================================================
# 4. Fallback JSON -> ActionPlan
# ============================================================


def test_groq_fallback_plan_is_accepted_by_action_models():
    """
    Verify the complete conversion:

        Structured JSON
            ↓
        MultiCommandPlanner
            ↓
        ActionPlan
            ↓
        ActionStep
    """

    response = json.dumps(
        VALID_PLAN
    )

    fake_gemini = (
        FakePlannerGeminiClient(
            response=response
        )
    )

    planner = MultiCommandPlanner(
        gemini_client=fake_gemini
    )

    plan = planner.create_plan(
        "open chrome then search Sona College"
    )

    assert isinstance(
        plan,
        ActionPlan,
    )

    assert (
        plan.total_steps
        == 2
    )

    assert (
        plan.original_command
        == "open chrome then search Sona College"
    )

    assert (
        plan.steps[0].action
        == "launch_application"
    )

    assert (
        plan.steps[0].parameters[
            "application"
        ]
        == "chrome"
    )

    assert (
        plan.steps[1].action
        == "google_search"
    )

    assert (
        plan.steps[1].parameters[
            "query"
        ]
        == "Sona College"
    )

    assert (
        fake_gemini.calls
        == 1
    )


# ============================================================
# 5. Dedicated Code Agent Key Must Be Used
# ============================================================


def test_groq_fallback_uses_dedicated_code_agent_key(
    monkeypatch,
):
    """
    Verify that the fallback configuration uses:

        GROQ_API_KEY_CODE_AGENT

    and NOT:

        GROQ_API_KEY

    The actual API request is never performed.
    """

    monkeypatch.setenv(
        "GROQ_API_KEY_CODE_AGENT",
        "code-agent-test-key",
    )

    monkeypatch.setenv(
        "GROQ_API_KEY",
        "stt-test-key",
    )

    client = create_client()

    assert (
        client.groq_planner_api_key
        == "code-agent-test-key"
    )

    assert (
        client.groq_planner_api_key
        != "stt-test-key"
    )


# ============================================================
# 6. Dedicated Groq Model Configuration
# ============================================================


def test_groq_fallback_uses_code_agent_model(
    monkeypatch,
):
    """
    Verify that the structured fallback uses:

        GROQ_CODE_AGENT_MODEL
    """

    monkeypatch.setenv(
        "GROQ_CODE_AGENT_MODEL",
        "openai/gpt-oss-20b",
    )

    client = create_client()

    assert (
        client.groq_planner_model
        == "openai/gpt-oss-20b"
    )


# ============================================================
# 7. Missing Dedicated Groq Key
# ============================================================


def test_missing_groq_code_agent_key_returns_empty_result(
    monkeypatch,
):
    """
    When Gemini fails and the dedicated Groq key is missing,
    structured planning should fail gracefully.
    """

    client = create_client()

    disable_gemini_retry_delay(
        monkeypatch,
        client,
    )

    # Explicitly clear the runtime configuration.
    #
    # This is stronger and more deterministic than relying only
    # on monkeypatch.delenv(), because GeminiClient may have
    # already loaded configuration during initialization.
    client.groq_planner_api_key = ""

    client.groq_planner_client = None

    # Force all Gemini attempts to fail.
    install_fake_gemini(
        client,
        error=RuntimeError(
            "429 RESOURCE_EXHAUSTED "
            "simulated Gemini failure"
        ),
    )

    # Prevent real Gemini client recreation.
    def fake_create_client():
        client.client = client.client

    monkeypatch.setattr(
        client,
        "_create_client",
        fake_create_client,
    )

    result = client.generate_structured_plan(
        "Open Chrome and search Sona College."
    )

    assert result in {
        "",
        None,
    }


# ============================================================
# 8. Planner Uses generate_structured_plan()
# ============================================================


def test_multi_command_planner_uses_structured_plan_api():
    """
    Verify that MultiCommandPlanner depends on the public:

        generate_structured_plan()

    interface.

    This confirms the Gemini -> Groq fallback remains
    transparent to the planner.
    """

    response = json.dumps(
        VALID_PLAN
    )

    fake_gemini = (
        FakePlannerGeminiClient(
            response=response
        )
    )

    planner = MultiCommandPlanner(
        gemini_client=fake_gemini
    )

    plan = planner.create_plan(
        "open chrome and search Sona College"
    )

    assert isinstance(
        plan,
        ActionPlan,
    )

    assert (
        plan.total_steps
        == 2
    )

    assert (
        fake_gemini.calls
        == 1
    )


# ============================================================
# 9. Invalid Groq JSON Must Not Become a Valid Plan
# ============================================================


def test_invalid_groq_json_is_rejected(
    monkeypatch,
):
    """
    A malformed Groq fallback response must not silently
    become an ActionPlan.
    """

    client = create_client()

    disable_gemini_retry_delay(
        monkeypatch,
        client,
    )

    invalid_response = (
        "this is not valid JSON"
    )

    # Force Gemini failure.
    install_fake_gemini(
        client,
        error=RuntimeError(
            "429 RESOURCE_EXHAUSTED "
            "simulated Gemini failure"
        ),
    )

    # Prevent real Gemini client recreation.
    def fake_create_client():
        client.client = client.client

    monkeypatch.setattr(
        client,
        "_create_client",
        fake_create_client,
    )

    # Groq returns malformed JSON.
    monkeypatch.setattr(
        client,
        "_generate_groq_structured_plan",
        lambda prompt: invalid_response,
    )

    result = client.generate_structured_plan(
        "Open Chrome and search Sona College."
    )

    # GeminiClient returns the fallback text.
    assert (
        result
        == invalid_response
    )

    # MultiCommandPlanner must reject it.
    fake_planner_gemini = (
        FakePlannerGeminiClient(
            response=result
        )
    )

    planner = MultiCommandPlanner(
        gemini_client=fake_planner_gemini
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to create action plan",
    ):
        planner.create_plan(
            "open chrome and search Sona College"
        )


# ============================================================
# 10. Supported Action Validation
# ============================================================


def test_fallback_plan_rejects_unsupported_action():
    """
    ActionPlan itself accepts arbitrary action names, but
    MultiCommandPlanner validation must reject actions that
    are not part of SUPPORTED_ACTIONS.
    """

    invalid_plan = {
        "original_command": "do something",
        "description": "Invalid test plan",
        "steps": [
            {
                "step_id": "step_1",
                "action": "unsupported_fake_action",
                "parameters": {},
                "description": "Invalid action",
            }
        ],
    }

    fake_gemini = (
        FakePlannerGeminiClient(
            response=json.dumps(
                invalid_plan
            )
        )
    )

    planner = MultiCommandPlanner(
        gemini_client=fake_gemini
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to create action plan",
    ):
        planner.create_plan(
            "do something"
        )


# ============================================================
# 11. Groq Fallback Request Uses Dedicated Model
# ============================================================


def test_groq_fallback_request_uses_configured_model(
    monkeypatch,
):
    """
    Verify that _generate_groq_structured_plan() sends the
    configured GROQ_CODE_AGENT_MODEL to the Groq API client.

    The request itself is fully mocked.
    """

    monkeypatch.setenv(
        "GROQ_API_KEY_CODE_AGENT",
        "code-agent-test-key",
    )

    monkeypatch.setenv(
        "GROQ_CODE_AGENT_MODEL",
        "openai/gpt-oss-20b",
    )

    client = create_client()

    fake_groq = FakeGroqClient(
        response=json.dumps(
            VALID_PLAN
        )
    )

    client.groq_planner_client = (
        fake_groq
    )

    result = (
        client._generate_groq_structured_plan(
            "Open Chrome and search Sona College."
        )
    )

    assert result

    assert json.loads(
        result
    ) == VALID_PLAN

    completions = (
        fake_groq.chat.completions
    )

    assert (
        completions.calls
        == 1
    )

    assert (
        completions.kwargs_history[0][
            "model"
        ]
        == "openai/gpt-oss-20b"
    )


# ============================================================
# 12. Groq Fallback Does Not Use STT Key
# ============================================================


def test_groq_fallback_request_does_not_use_stt_key(
    monkeypatch,
):
    """
    Verify the planner fallback is configured with:

        GROQ_API_KEY_CODE_AGENT

    and does not fall back to:

        GROQ_API_KEY
    """

    monkeypatch.setenv(
        "GROQ_API_KEY_CODE_AGENT",
        "dedicated-code-agent-key",
    )

    monkeypatch.setenv(
        "GROQ_API_KEY",
        "stt-key-must-not-be-used",
    )

    client = create_client()

    assert (
        client.groq_planner_api_key
        == "dedicated-code-agent-key"
    )

    assert (
        client.groq_planner_api_key
        != "stt-key-must-not-be-used"
    )

    # Inject a fake Groq client so no real API request occurs.
    fake_groq = FakeGroqClient(
        response=json.dumps(
            VALID_PLAN
        )
    )

    client.groq_planner_client = (
        fake_groq
    )

    result = (
        client._generate_groq_structured_plan(
            "Open Chrome and search Sona College."
        )
    )

    assert result

    assert json.loads(
        result
    ) == VALID_PLAN