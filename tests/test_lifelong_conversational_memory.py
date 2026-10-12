"""
Test suite for DHEEPTHI-AI V1 Lifelong Conversational Memory System

Verifies:
1. Open-domain lifelong memory extraction (Company, Role, Internship, Projects, Hobbies, Goals, Challenges).
2. Task & commitment lifecycle (creation, tracking in tasks table, natural language completion).
3. Conversation Archive Fallback (finding unextracted or rich conversational facts directly from archive).
4. Short query memory injection fix in GeminiClient (queries < 150 chars receive dynamic memory context).
5. Multi-profile isolation for lifelong memory and tasks.
6. Speech act discrimination (questions & hypotheticals rejected).
7. Cold restart persistence across distinct database sessions.
"""

import os
import sys
import tempfile
import pytest

from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.gemini_client import GeminiClient
from ai.personality_context_builder import PersonalityContextBuilder


@pytest.fixture
def isolated_env():
    """Provides an isolated temporary database for clean test execution."""
    temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = os.path.join(temp_dir.name, "test_lifelong.db")
    db = DatabaseManager(database_path=db_path)
    mem = MemoryManager(db=db, profile_id="default")
    yield {"db": db, "mem": mem, "dir": temp_dir, "db_path": db_path}
    try:
        temp_dir.cleanup()
    except Exception:
        pass


class TestLifelongConversationalMemory:

    def test_01_open_domain_career_and_company(self, isolated_env):
        mem = isolated_env["mem"]
        # Extract company and role
        user_turn = "I am working as a Software Architect at Zoho"
        mems = mem.extract_memories_from_turn(user_turn, source_turn_id="turn_job_1")
        assert len(mems) > 0

        # Query recall
        ans = mem.answer_memory_query("Where do I work?")
        assert ans is not None
        assert "Zoho" in ans

        ans_role = mem.answer_memory_query("What is my designation and role?")
        assert ans_role is not None
        assert "Software Architect" in ans_role

    def test_02_open_domain_internship(self, isolated_env):
        mem = isolated_env["mem"]
        user_turn = "I got an internship at Google in Chennai"
        mems = mem.extract_memories_from_turn(user_turn, source_turn_id="turn_intern_1")
        assert len(mems) > 0

        ans = mem.answer_memory_query("Where am I doing my internship?")
        assert ans is not None
        assert "Google" in ans

    def test_03_open_domain_hobbies_and_free_time(self, isolated_env):
        mem = isolated_env["mem"]
        user_turn = "My hobbies are landscape photography and playing chess"
        mems = mem.extract_memories_from_turn(user_turn, source_turn_id="turn_hobby_1")
        assert len(mems) > 0

        ans = mem.answer_memory_query("What are my hobbies?")
        assert ans is not None
        assert "landscape photography" in ans.lower() or "playing chess" in ans.lower()

    def test_04_open_domain_career_goals_and_ambitions(self, isolated_env):
        mem = isolated_env["mem"]
        user_turn = "My goal is to build an autonomous AI robotics startup"
        mems = mem.extract_memories_from_turn(user_turn, source_turn_id="turn_goal_1")
        assert len(mems) > 0

        ans = mem.answer_memory_query("What is my goal?")
        assert ans is not None
        assert "autonomous AI robotics startup" in ans

    def test_05_open_domain_challenges_and_struggles(self, isolated_env):
        mem = isolated_env["mem"]
        user_turn = "Currently I am struggling with CUDA memory fragmentation"
        mems = mem.extract_memories_from_turn(user_turn, source_turn_id="turn_chal_1")
        assert len(mems) > 0

        ans = mem.answer_memory_query("What challenges am I struggling with?")
        assert ans is not None
        assert "CUDA memory fragmentation" in ans

    def test_06_task_lifecycle_creation_and_completion(self, isolated_env):
        mem = isolated_env["mem"]
        db = isolated_env["db"]

        # 1. User commits to a pending task
        user_turn = "I need to submit the MCA project report by Friday"
        mems = mem.extract_memories_from_turn(user_turn, source_turn_id="turn_task_1")
        assert len(mems) > 0

        # Verify task is tracked in tasks table
        active_tasks = db.get_tasks(status="pending", profile_id="default")
        assert len(active_tasks) >= 1
        assert any("MCA project report" in t["description"] for t in active_tasks)

        # Query recall before completion
        ans = mem.answer_memory_query("What pending tasks do I need to do?")
        assert ans is not None
        assert "MCA project report" in ans

        # 2. User completes the task
        comp_turn = "I have completed the task of submitting the MCA project report"
        mem.extract_memories_from_turn(comp_turn, source_turn_id="turn_task_comp_1")

        # Verify task status is now completed
        active_after = db.get_tasks(status="pending", profile_id="default")
        assert not any("MCA project report" in t["description"] for t in active_after)
        completed_tasks = db.get_tasks(status="completed", profile_id="default")
        assert any("MCA project report" in t["description"] for t in completed_tasks)

    def test_07_conversation_archive_search_fallback(self, isolated_env):
        db = isolated_env["db"]
        mem = isolated_env["mem"]

        # Simulate a complex conversational utterance persisted to the conversation archive
        # that may not have a rigid single-field category
        turn_text = "We agreed that our release code name is Project Phoenix with v1 launch in December"
        db.add_conversation_context(
            user_command=turn_text,
            assistant_response="Understood, Project Phoenix noted.",
            turn_id="turn_archive_1",
            session_id="session_live_101",
        )

        # Direct archive search verify
        hits = db.search_conversation_archive(query="Project Phoenix", profile_id="default")
        assert len(hits) >= 1
        assert "Project Phoenix" in hits[0]["user_command"]

        # Archive fallback in answer_memory_query
        ans = mem.answer_memory_query("What was our release code name Project Phoenix?")
        assert ans is not None
        assert "Project Phoenix" in ans

    def test_08_short_query_memory_injection_in_gemini_client(self, isolated_env):
        mem = isolated_env["mem"]
        db = isolated_env["db"]

        # Seed facts
        mem.set_profile_fact("company", "Zoho Corporation", category="work")
        mem.set_profile_fact("job_role", "Principal Architect", category="work")

        client = GeminiClient(
            memory_manager=mem,
        )
        client.context_builder = PersonalityContextBuilder

        # Short query (< 150 chars)
        short_query = "Where do I work?"
        assert len(short_query) < 150

        # Build simple prompt
        prompt = client.build_simple_prompt(short_query)

        # Verify prompt includes dynamic context with company and role
        assert "23. ACTIVE CONTEXT" in prompt
        assert "Zoho Corporation" in prompt or "Principal Architect" in prompt

    def test_09_multi_profile_lifelong_memory_isolation(self, isolated_env):
        db = isolated_env["db"]
        mem_user_a = MemoryManager(db=db, profile_id="alice")
        mem_user_b = MemoryManager(db=db, profile_id="bob")

        # Alice adds task and job
        mem_user_a.extract_memories_from_turn("I am working at Microsoft as a Security Engineer", source_turn_id="turn_a1")
        mem_user_a.add_task("Review Alice quarterly budget", profile_id="alice")

        # Bob queries
        ans_bob_job = mem_user_b.answer_memory_query("Where do I work?")
        assert ans_bob_job is None or "Microsoft" not in ans_bob_job

        bob_tasks = mem_user_b.get_active_tasks(profile_id="bob")
        assert not any("Alice" in t.get("description", "") for t in bob_tasks)

        # Alice queries
        ans_alice_job = mem_user_a.answer_memory_query("Where do I work?")
        assert ans_alice_job is not None and "Microsoft" in ans_alice_job

    def test_10_speech_act_discrimination_rejects_questions_and_hypotheticals(self, isolated_env):
        mem = isolated_env["mem"]

        # Question should not extract memory
        q_turn = "Am I working as a pilot at Emirates?"
        extracted_q = mem.extract_memories_from_turn(q_turn, source_turn_id="turn_q")
        assert len(extracted_q) == 0
        assert mem.get_profile_fact("company") is None

        # Hypothetical should not extract memory
        hyp_turn = "If I ever join Google, I would probably live in Mountain View"
        extracted_h = mem.extract_memories_from_turn(hyp_turn, source_turn_id="turn_h")
        assert len(extracted_h) == 0
        assert mem.get_profile_fact("company") is None

    def test_11_cold_restart_persistence(self, isolated_env):
        db_path = isolated_env["db_path"]
        db1 = DatabaseManager(database_path=db_path)
        mem1 = MemoryManager(db=db1, profile_id="default")

        # Session 1: Store multiple lifelong memory categories
        mem1.extract_memories_from_turn("My college is Sona College of Technology", source_turn_id="turn_c1")
        mem1.extract_memories_from_turn("My degree is MCA and I am in Second year", source_turn_id="turn_c2")
        mem1.extract_memories_from_turn("I got an internship at Infosys", source_turn_id="turn_c3")
        mem1.extract_memories_from_turn("My hobbies are playing chess", source_turn_id="turn_c4")
        mem1.extract_memories_from_turn("I need to complete the cryptography assignment", source_turn_id="turn_c5")

        # Simulate full shutdown
        del mem1
        del db1

        # Session 2: Cold boot from the exact same database
        db2 = DatabaseManager(database_path=db_path)
        mem2 = MemoryManager(db=db2, profile_id="default")

        # Verify all lifelong memories are recalled after cold restart
        assert mem2.get_profile_fact("college") == "Sona College of Technology"
        assert mem2.get_profile_fact("degree") == "MCA"
        assert mem2.get_profile_fact("academic_year") == "Second year"
        assert mem2.get_profile_fact("internship") == "Infosys"
        assert "chess" in str(mem2.get_profile_fact("hobbies")).lower()

        active_tasks = mem2.get_active_tasks()
        assert any("cryptography assignment" in t["description"] for t in active_tasks)

    def test_12_tamil_and_tanglish_recall_questions_do_not_mutate_memory(self, isolated_env):
        mem = isolated_env["mem"]
        # Seed legitimate facts
        mem.set_profile_fact("college", "Sona College of Technology", category="education")
        mem.set_profile_fact("degree", "MCA", category="education")
        mem.set_profile_fact("company", "Symphozen Labs", category="work")

        # Tamil testing directive + embedded question
        tamil_test_q = "ஹேய் தீப்தி, நான் இது ஒரு டெஸ்டிங் தான்... நான் என்ன காலேஜ்ல படிக்கிறேன்..."
        extracted = mem.extract_memories_from_turn(tamil_test_q, source_turn_id="turn_test_q1")
        assert len(extracted) == 0, f"Expected 0 extractions from test query, got: {extracted}"
        assert mem.get_profile_fact("college") == "Sona College of Technology"

        # Tanglish testing/recall question
        tanglish_q = "naan enna college-la padikiren sollunga paarkalaam"
        extracted2 = mem.extract_memories_from_turn(tanglish_q, source_turn_id="turn_test_q2")
        assert len(extracted2) == 0
        assert mem.get_profile_fact("college") == "Sona College of Technology"

        # English recall question
        eng_q = "Which company am I interning at?"
        extracted3 = mem.extract_memories_from_turn(eng_q, source_turn_id="turn_test_q3")
        assert len(extracted3) == 0
        assert mem.get_profile_fact("company") == "Symphozen Labs"

        # Broad recall question
        broad_q = "Tell me what you remember about me"
        extracted4 = mem.extract_memories_from_turn(broad_q, source_turn_id="turn_test_q4")
        assert len(extracted4) == 0

    def test_13_mca_degree_does_not_extract_as_laptop_possession(self, isolated_env):
        mem = isolated_env["mem"]
        # Utterance explaining MCA degree
        turn = "Master of Computer Application yaani ki MCA"
        extracted = mem.extract_memories_from_turn(turn, source_turn_id="turn_mca_1")
        laptop_fact = mem.get_profile_fact("laptop")
        assert laptop_fact is None, f"Expected no laptop fact, got {laptop_fact}"

    def test_14_compound_education_recall(self, isolated_env):
        mem = isolated_env["mem"]
        mem.set_profile_fact("degree", "MCA", category="education")
        mem.set_profile_fact("college", "Sona College of Technology", category="education")

        ans = mem.answer_memory_query("Which course am I studying, and where?")
        assert ans is not None
        assert "MCA" in ans
        assert "Sona College" in ans

    def test_15_broad_profile_overview_recall(self, isolated_env):
        mem = isolated_env["mem"]
        mem.set_profile_fact("user_name", "Naresh", category="personal")
        mem.set_profile_fact("degree", "MCA", category="education")
        mem.set_profile_fact("college", "Sona College of Technology", category="education")
        mem.set_profile_fact("father", "Senthil Nathan", category="family")
        mem.set_profile_fact("mother", "Sangeetha", category="family")
        mem.set_profile_fact("brother", "Deepesh", category="family")
        mem.set_profile_fact("company", "Symphozen Labs", category="work")
        mem.set_profile_fact("job_role", "Full Stack Developer", category="work")
        mem.set_profile_fact("current_project", "SymphoWork", category="work")

        # 1. "Tell me what you remember about me."
        ans1 = mem.answer_memory_query("Tell me what you remember about me.")
        assert ans1 is not None
        assert "Naresh" in ans1
        assert "MCA" in ans1
        assert "Sona College" in ans1
        assert "Senthil Nathan" in ans1
        assert "Sangeetha" in ans1
        assert "Deepesh" in ans1
        assert "Symphozen Labs" in ans1
        assert "Full Stack Developer" in ans1
        assert "SymphoWork" in ans1

        # 2. "What important things did I tell you in previous conversations?"
        ans2 = mem.answer_memory_query("What important things did I tell you in previous conversations?")
        assert ans2 is not None
        assert "Sona College" in ans2
        assert "Symphozen Labs" in ans2

    def test_16_archive_retrieval_with_stemming_and_semantic_expansion(self, isolated_env):
        db = isolated_env["db"]
        mem = isolated_env["mem"]

        # Persist a conversation turn where user spoke about internship
        db.add_conversation_context(
            user_command="I am currently doing my internship at Symphozen Labs as a full stack developer",
            assistant_response="Great! Full stack development internship at Symphozen Labs.",
            turn_id="turn_arch_intern",
            session_id="session_live_intern",
        )

        # Query using morphological variation ("interning")
        hits = db.search_conversation_archive(query="Which company am I interning at?", profile_id="default")
        assert len(hits) >= 1
        assert "Symphozen Labs" in hits[0]["user_command"] or "Symphozen Labs" in hits[0]["assistant_response"]

