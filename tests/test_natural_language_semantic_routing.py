"""
Pytest Test Suite for DHEEPTHI-AI V1 Natural Language Semantic Routing

Validates all 10 required scenarios:
1. Chrome + YouTube
2. Notepad + typing
3. VS Code + code creation
4. Downloads + file copy
5. Edge + YouTube
6. English deterministic command
7. Tanglish deterministic command
8. Tamil/Tanglish mixed command
9. Normal conversation (zero automation)
10. Multi-command ordering
"""

import json
import pytest
from planner.semantic_command_planner import SemanticCommandPlanner


@pytest.fixture(scope="module")
def planner():
    p = SemanticCommandPlanner()
    # Fast offline deterministic mock fallback so pytest runs instantly without network delays
    real_generate = p.gemini_client.generate_structured_plan
    def fast_mock_generate(prompt):
        if 'User Input: "' in prompt:
            user_text = prompt.split('User Input: "')[1].split('"')[0]
        else:
            user_text = prompt
        fb = p._fallback_extract_structural_actions(user_text)
        if fb:
            return json.dumps(fb)
        return json.dumps({"type": "conversation", "actions": []})
    p.gemini_client.generate_structured_plan = fast_mock_generate
    return p


def test_1_chrome_youtube(planner):
    inp = "Chrome open panni Pavalamalli song play pannu"
    plan = planner.plan(inp)
    assert plan.get("type") == "command"
    actions = plan.get("actions", [])
    assert len(actions) == 2
    assert actions[0]["intent"] == "launch_application"
    assert actions[0]["entities"]["application"] == "Chrome"
    assert actions[1]["intent"] == "play_youtube"
    assert "Pavalamalli" in (actions[1]["entities"].get("search_query") or actions[1]["entities"].get("query") or "")


def test_2_notepad_typing(planner):
    inp = "Notepad open panni hello world type pannu"
    plan = planner.plan(inp)
    assert plan.get("type") == "command"
    actions = plan.get("actions", [])
    assert len(actions) == 2
    assert actions[0]["intent"] == "launch_application"
    assert actions[0]["entities"]["application"] == "Notepad"
    assert actions[1]["intent"] == "type_text"
    assert "hello world" in actions[1]["entities"].get("text", "")


def test_3_vscode_code_creation(planner):
    inp = "VS Code open panni Python calculator program create pannu"
    plan = planner.plan(inp)
    assert plan.get("type") == "command"
    actions = plan.get("actions", [])
    assert len(actions) == 2
    assert actions[0]["intent"] == "launch_application"
    assert actions[0]["entities"]["application"] == "VS Code"
    assert actions[1]["intent"] == "code_agent"
    assert actions[1]["entities"]["language"].lower() == "python"
    assert "calculator" in actions[1]["entities"].get("task", "").lower()


def test_4_downloads_file_copy(planner):
    inp = "Downloads folder open panni report.pdf ah Desktop ku copy pannu"
    plan = planner.plan(inp)
    assert plan.get("type") == "command"
    actions = plan.get("actions", [])
    assert len(actions) == 2
    assert actions[0]["intent"] == "open_folder"
    assert actions[0]["entities"]["folder"] == "Downloads"
    assert actions[1]["intent"] == "copy_file"
    assert actions[1]["entities"]["source"] == "report.pdf"
    assert actions[1]["entities"]["destination"] == "Desktop"


def test_5_edge_youtube(planner):
    inp = "Edge open panni YouTube la Anbe Anbe play pannu"
    plan = planner.plan(inp)
    assert plan.get("type") == "command"
    actions = plan.get("actions", [])
    assert len(actions) == 2
    assert actions[0]["intent"] == "launch_application"
    assert actions[0]["entities"]["application"] == "Edge"
    assert actions[1]["intent"] == "play_youtube"
    assert "Anbe Anbe" in (actions[1]["entities"].get("search_query") or actions[1]["entities"].get("query") or "")


def test_6_english_deterministic(planner):
    inputs = [
        ("Open Chrome", "launch_application", "Chrome"),
        ("Close Notepad", "close_application", "Notepad"),
        ("Take screenshot", "take_screenshot", None),
        ("Open Downloads", "open_folder", "Downloads"),
    ]
    for inp, expected_intent, expected_entity in inputs:
        plan = planner.plan(inp)
        assert plan.get("type") == "command"
        act = plan.get("actions", [])[0]
        assert act["intent"] == expected_intent
        if expected_entity:
            entity_val = act["entities"].get("application") or act["entities"].get("folder")
            assert entity_val == expected_entity


def test_7_tanglish_deterministic(planner):
    inputs = [
        ("Chrome open pannu", "launch_application", "Chrome"),
        ("Notepad close pannu", "close_application", "Notepad"),
    ]
    for inp, expected_intent, expected_entity in inputs:
        plan = planner.plan(inp)
        assert plan.get("type") == "command"
        act = plan.get("actions", [])[0]
        assert act["intent"] == expected_intent
        assert act["entities"].get("application") == expected_entity


def test_8_mixed_tamil_tanglish(planner):
    inputs = [
        ("Edge open panni Google la Python tutorial search pannu", ["launch_application", "google_search"]),
        ("Chrome ah open panni YouTube la song play pannu", ["launch_application", "play_youtube"]),
        ("Notepad open pannitu hello da nu type pannu", ["launch_application", "type_text"]),
    ]
    for inp, expected_intents in inputs:
        plan = planner.plan(inp)
        assert plan.get("type") == "command"
        actual = [a["intent"] for a in plan.get("actions", [])]
        assert actual == expected_intents


def test_9_normal_conversation_safety(planner):
    conv_inputs = [
        "Human body la evlo bones irukum?",
        "Wait pannu, oru doubt iruku",
        "Chrome pathi sollu",
        "Why should I open Chrome?",
        "Tell me about YouTube",
        "Why should I play a song?",
    ]
    for cinp in conv_inputs:
        plan = planner.plan(cinp)
        assert plan.get("type") == "conversation"
        assert len(plan.get("actions", [])) == 0


def test_10_multi_command_ordering(planner):
    inp = "Downloads folder open panni report.pdf ah Desktop ku copy pannu"
    plan = planner.plan(inp)
    actions = plan.get("actions", [])
    assert len(actions) == 2
    assert actions[0]["intent"] == "open_folder"
    assert actions[1]["intent"] == "copy_file"


def test_incomplete_command_safety(planner):
    plan = planner.plan("copy the file")
    assert plan.get("type") == "conversation" or len(plan.get("actions", [])) == 0
