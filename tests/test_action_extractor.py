"""
Focused Test Suite for Gemini Live <ACTION>...</ACTION> Extraction and Routing Layer.

Tests:
1. Standard single command in <ACTION> tag (Chrome + YouTube)
2. Command with quotes in <ACTION> tag (Notepad + type text)
3. Normal conversational Gemini response without ACTION (ACTION not detected)
4. Multi-line Gemini response containing an ACTION tag
5. Malformed or incomplete ACTION tags (fail safely, treat as non-action)
6. End-to-end integration: extracted command planned by SemanticCommandPlanner
"""

import pytest
from planner.semantic_command_planner import (
    SemanticCommandPlanner,
    extract_action_command,
    has_action_command,
)


def test_1_chrome_youtube_action_extraction():
    gemini_output = "<ACTION>Open Chrome and play Pavalamalli song on YouTube</ACTION>"
    assert has_action_command(gemini_output) is True
    command = extract_action_command(gemini_output)
    assert command == "Open Chrome and play Pavalamalli song on YouTube"


def test_2_notepad_typing_action_extraction():
    gemini_output = '<ACTION>Open Notepad and type "hello world"</ACTION>'
    assert has_action_command(gemini_output) is True
    command = extract_action_command(gemini_output)
    assert command == 'Open Notepad and type "hello world"'


def test_3_normal_conversation_without_action():
    conversations = [
        "Human body la 206 bones irukum da.",
        "Chrome oru popular web browser, Google create pannathu.",
        "Wait pannu da, enna doubt?",
        "Why should I open Chrome? It is up to you!",
        "Naan DHEEPTHI, ungaloda personal desktop assistant.",
    ]
    for conv in conversations:
        assert has_action_command(conv) is False
        assert extract_action_command(conv) is None


def test_4_multiline_gemini_output_with_action():
    multiline_output = (
        "Seri da, ippo naan Downloads folder open panni copy panren.\n"
        "<ACTION>Open Downloads folder and copy report.pdf to Desktop</ACTION>\n"
        "Konjam neram wait pannu."
    )
    assert has_action_command(multiline_output) is True
    command = extract_action_command(multiline_output)
    assert command == "Open Downloads folder and copy report.pdf to Desktop"


def test_5_malformed_incomplete_action_tags():
    malformed_inputs = [
        "<ACTION>Open Chrome and play music",          # Missing closing tag
        "Open Chrome and play music</ACTION>",          # Missing opening tag
        "<ACTION></ACTION>",                            # Empty tag
        "<ACTION>   \n   \t   </ACTION>",               # Whitespace only
        "<ACTION>",                                     # Incomplete
        "</ACTION>",                                    # Incomplete
        "<ACTION <ACTION>Open Chrome</ACTION>",          # Nested/malformed opening
        "Just some normal text with <action words",     # Broken angle brackets
    ]
    for inp in malformed_inputs:
        command = extract_action_command(inp)
        assert command is None, f"Expected None for malformed input '{inp}', got '{command}'"
        assert has_action_command(inp) is False


import json

def test_6_semantic_planner_handles_extracted_actions():
    planner = SemanticCommandPlanner()
    def fast_mock_generate(prompt):
        if 'User Input: "' in prompt:
            user_text = prompt.split('User Input: "')[1].rsplit('"\n\nReturn ONLY', 1)[0]
        else:
            user_text = prompt
        fb = planner._fallback_extract_structural_actions(user_text)
        if fb:
            return json.dumps(fb)
        return json.dumps({"type": "conversation", "actions": []})
    planner.gemini_client.generate_structured_plan = fast_mock_generate

    # Test Chrome + YouTube plan
    t1 = "<ACTION>Open Chrome and play Pavalamalli song on YouTube</ACTION>"
    plan1 = planner.plan(t1)
    assert plan1.get("type") == "command"
    acts1 = plan1.get("actions", [])
    assert len(acts1) == 2
    assert acts1[0]["intent"] == "launch_application"
    assert acts1[0]["entities"]["application"] == "Chrome"
    assert acts1[1]["intent"] == "play_youtube"
    assert "Pavalamalli" in (acts1[1]["entities"].get("search_query") or acts1[1]["entities"].get("query") or "")

    # Test Notepad + Type plan
    t2 = '<ACTION>Open Notepad and type "hello world"</ACTION>'
    plan2 = planner.plan(t2)
    assert plan2.get("type") == "command"
    acts2 = plan2.get("actions", [])
    assert len(acts2) == 2
    assert acts2[0]["intent"] == "launch_application"
    assert acts2[0]["entities"]["application"] == "Notepad"
    assert acts2[1]["intent"] == "type_text"
    assert "hello world" in acts2[1]["entities"].get("text", "")

    # Test Downloads + Copy plan
    t4 = "<ACTION>Open Downloads folder and copy report.pdf to Desktop</ACTION>"
    plan4 = planner.plan(t4)
    assert plan4.get("type") == "command"
    acts4 = plan4.get("actions", [])
    assert len(acts4) == 2
    assert acts4[0]["intent"] == "open_folder"
    assert acts4[0]["entities"]["folder"] == "Downloads"
    assert acts4[1]["intent"] == "copy_file"
    assert acts4[1]["entities"]["source"] == "report.pdf"
    assert acts4[1]["entities"]["destination"] == "Desktop"

    # Test Edge + YouTube plan
    t5 = "<ACTION>Open Edge and play Anbe Anbe on YouTube</ACTION>"
    plan5 = planner.plan(t5)
    assert plan5.get("type") == "command"
    acts5 = plan5.get("actions", [])
    assert len(acts5) == 2
    assert acts5[0]["intent"] == "launch_application"
    assert acts5[0]["entities"]["application"] == "Edge"
    assert acts5[1]["intent"] == "play_youtube"
    assert "Anbe Anbe" in (acts5[1]["entities"].get("search_query") or acts5[1]["entities"].get("query") or "")
