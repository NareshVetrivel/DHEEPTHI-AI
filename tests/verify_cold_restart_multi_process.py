"""
Multi-process Cold-Restart Verification Script for DHEEPTHI-AI V1
Lifelong Conversational Memory System

Demonstrates and verifies:
- Phase 1: Process 1 ingests varied open-domain conversations, commits lifelong memories and tasks, then exits cleanly.
- Phase 2: Process 2 boots from a fresh interpreter, connects to the same database file, and proves 100% recall of open-domain memories, tasks, conversation archive evidence, and system prompt injection.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

PYTHON_EXE = sys.executable


def run_phase_1(db_path: str):
    """Executes Phase 1 in an isolated subprocess."""
    script = f"""
import sys, os
from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager

db = DatabaseManager(database_path=r'{db_path}')
mem = MemoryManager(db=db, profile_id='default')

# 1. Ingest education details
mem.extract_memories_from_turn("My college is Sona College of Technology and degree is MCA Second year", source_turn_id="turn_p1_1")

# 2. Ingest career and workplace
mem.extract_memories_from_turn("I am working as a Senior Cloud Architect at Zoho in Chennai", source_turn_id="turn_p1_2")

# 3. Ingest internship
mem.extract_memories_from_turn("I am doing an internship at Microsoft Research", source_turn_id="turn_p1_3")

# 4. Ingest goals and hobbies
mem.extract_memories_from_turn("My hobbies are astrophotography and playing violin", source_turn_id="turn_p1_4")
mem.extract_memories_from_turn("My goal is to build an autonomous drone navigation system", source_turn_id="turn_p1_5")

# 5. Ingest challenges
mem.extract_memories_from_turn("I am currently struggling with TensorRT model optimization", source_turn_id="turn_p1_6")

# 6. Ingest pending commitments/tasks
mem.extract_memories_from_turn("I need to submit the IEEE conference paper by next Monday", source_turn_id="turn_p1_7")

# 7. Store conversational archive interaction without explicit category
db.add_conversation_context(
    user_command="We decided that the internal project code name is Apollo Nebula",
    assistant_response="Understood! Project Apollo Nebula noted in records.",
    turn_id="turn_p1_archive",
    session_id="session_live_phase1"
)

# Shutdown DB cleanly
db.close()
print("PHASE_1_SUCCESS")
"""
    res = subprocess.run([PYTHON_EXE, "-c", script], capture_output=True, text=True, check=True)
    assert "PHASE_1_SUCCESS" in res.stdout, f"Phase 1 failed: {res.stderr}"
    print("[MULTI-PROCESS VERIFICATION] Phase 1 completed successfully.")


def run_phase_2(db_path: str):
    """Executes Phase 2 in a completely fresh subprocess to verify cold-restart recall."""
    script = f"""
import sys, os
from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.personality_context_builder import PersonalityContextBuilder
from ai.gemini_client import GeminiClient

db = DatabaseManager(database_path=r'{db_path}')
mem = MemoryManager(db=db, profile_id='default')

# Verification 1: Education recall
assert mem.get_profile_fact("college") == "Sona College of Technology", f"College mismatch: {{mem.get_profile_fact('college')}}"
assert mem.get_profile_fact("degree") == "MCA", f"Degree mismatch: {{mem.get_profile_fact('degree')}}"
assert mem.get_profile_fact("academic_year") == "Second year", f"Year mismatch: {{mem.get_profile_fact('academic_year')}}"

# Verification 2: Career recall
job_ans = mem.answer_memory_query("Where do I work and what is my role?")
assert job_ans is not None and "Zoho" in job_ans and "Senior Cloud Architect" in job_ans, f"Career recall failed: {{job_ans}}"

# Verification 3: Internship recall
intern_ans = mem.answer_memory_query("Where am I doing an internship?")
assert intern_ans is not None and "Microsoft Research" in intern_ans, f"Internship recall failed: {{intern_ans}}"

# Verification 4: Hobbies & Goals recall
hobby_ans = mem.answer_memory_query("What are my hobbies?")
assert hobby_ans is not None and "astrophotography" in hobby_ans.lower(), f"Hobby recall failed: {{hobby_ans}}"

goal_ans = mem.answer_memory_query("What is my goal?")
assert goal_ans is not None and "autonomous drone" in goal_ans, f"Goal recall failed: {{goal_ans}}"

# Verification 5: Challenges recall
chal_ans = mem.answer_memory_query("What challenges am I facing?")
assert chal_ans is not None and "TensorRT" in chal_ans, f"Challenge recall failed: {{chal_ans}}"

# Verification 6: Task tracking & Completion in cold session
active_tasks = mem.get_active_tasks()
assert any("IEEE conference paper" in t["description"] for t in active_tasks), f"Task tracking failed: {{active_tasks}}"

# Complete the task
mem.extract_memories_from_turn("I have completed the task of submitting the IEEE conference paper", source_turn_id="turn_p2_comp")
active_tasks_after = mem.get_active_tasks()
assert not any("IEEE conference paper" in t["description"] for t in active_tasks_after), "Task did not complete"

# Verification 7: Lifelong Conversation Archive Fallback
archive_ans = mem.answer_memory_query("What was the internal code name Apollo Nebula?")
assert archive_ans is not None and "Apollo Nebula" in archive_ans, f"Archive recall failed: {{archive_ans}}"

# Verification 8: System prompt dynamic context injection
client = GeminiClient(memory_manager=mem)
client.context_builder = PersonalityContextBuilder
simple_prompt = client.build_simple_prompt("Where do I work?")
assert "23. ACTIVE CONTEXT" in simple_prompt, "Active context not found in simple prompt"
assert "Zoho" in simple_prompt or "Senior Cloud Architect" in simple_prompt, "Career not in prompt"

live_prompt = client.live_system_prompt()
assert "23. ACTIVE CONTEXT" in live_prompt, "Active context not found in Live prompt"

db.close()
print("PHASE_2_SUCCESS")
"""
    res = subprocess.run([PYTHON_EXE, "-c", script], capture_output=True, text=True, check=True)
    assert "PHASE_2_SUCCESS" in res.stdout, f"Phase 2 failed: {res.stderr}\nStdout: {res.stdout}"
    print("[MULTI-PROCESS VERIFICATION] Phase 2 completed successfully.")


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        db_path = os.path.join(temp_dir, "cold_restart_test.db")
        print(f"[TEST RUNNER] Using isolated database at: {db_path}")

        print("[TEST RUNNER] Starting Phase 1 (Ingestion & Shutdown)...")
        run_phase_1(db_path)

        print("[TEST RUNNER] Starting Phase 2 (Cold Interpreter Boot & Full Verification)...")
        run_phase_2(db_path)

        print("\n=======================================================")
        print(">>> ALL MULTI-PROCESS COLD-RESTART CHECKS PASSED 100%! <<<")
        print("=======================================================")


if __name__ == "__main__":
    main()
