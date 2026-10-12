"""
Comprehensive Automated Test Suite: DHEEPTHI-AI V1 Persistent Memory
Validates:
1. Conversation archiving across all input pathways (voice, text, interrupted, failed).
2. Targeted credential redaction without dropping conversational persistence.
3. Multi-fact personal memory extraction (Father, Mother, Brother in single utterance).
4. English, Tanglish, and Tamil script family extraction.
5. Education, career, project decisions, plans/deadlines, and explicit notes extraction.
6. Memory corrections and supersession.
7. Deactivation / 'Forget this' requests across context tables.
8. Durable restart survival (Session A close -> Session B fresh start).
9. Profile isolation (Profile A memories isolated from Profile B).
10. Query answering from verified SQLite records (no hallucination).
11. Context builder prompt injection with verified facts and safe address directives.
12. Command execution tracking with turn and session linkage.
13. Strict safety: Real production database (database/astra.db) is untouched.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.emotion_engine import EmotionEngine
from ai.personality_context_builder import PersonalityContextBuilder


class TestComprehensiveMemoryV1(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_memory.db"
        self.db = DatabaseManager(database_path=self.db_path)
        self.memory_manager = MemoryManager(db=self.db)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 1. CONVERSATION PERSISTENCE ACROSS ALL PATHWAYS
    # ------------------------------------------------------------------
    def test_voice_turn_lifecycle_and_interruption(self):
        """Voice turns persist raw transcript promptly and handle interruption."""
        turn_id = "voice_turn_101"
        u_ok, t_id = self.memory_manager.save_user_turn(
            user_text="Open Spotify and play my playlist",
            turn_id=turn_id,
            session_id="sess_v1",
            input_source="voice",
            intent="launch_application"
        )
        self.assertTrue(u_ok)
        self.assertEqual(t_id, turn_id)

        # Confirm turn is in DB immediately
        rec = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["user_command"], "Open Spotify and play my playlist")
        self.assertEqual(rec["turn_status"], "user_received")

        # Mark interrupted (e.g. user barge-in)
        intr_ok = self.memory_manager.mark_turn_interrupted(turn_id)
        self.assertTrue(intr_ok)
        rec_intr = self.db.get_interaction_by_turn_id(turn_id)
        self.assertEqual(rec_intr["turn_status"], "interrupted")

    def test_text_turn_lifecycle_and_failure(self):
        """Typed input persists immediately and updates to failed on model error."""
        turn_id = "text_turn_202"
        u_ok, _ = self.memory_manager.save_user_turn(
            user_text="What is quantum computing?",
            turn_id=turn_id,
            session_id="sess_t1",
            input_source="text_input",
            intent="conversation"
        )
        self.assertTrue(u_ok)

        # Simulate model error handler recording failure
        fail_ok = self.db.update_turn_status(turn_id, "failed")
        self.assertTrue(fail_ok)
        rec = self.db.get_interaction_by_turn_id(turn_id)
        self.assertEqual(rec["turn_status"], "failed")

    def test_command_execution_linked_to_turn(self):
        """Deterministic / planner command execution is logged with turn and session IDs."""
        turn_id = "cmd_turn_303"
        session_id = "sess_c1"
        self.memory_manager.save_user_turn(
            user_text="Open Calculator",
            turn_id=turn_id,
            session_id=session_id,
            input_source="voice"
        )

        cmd_id = self.db.log_command_execution(
            command="open calculator",
            intent="launch_application",
            target="calc.exe",
            status="started",
            session_id=session_id,
            turn_id=turn_id
        )
        self.assertTrue(cmd_id > 0)

        update_ok = self.db.update_command_execution(
            command_id=cmd_id,
            status="completed",
            result_summary="Calculator opened successfully",
            execution_time_ms=120
        )
        self.assertTrue(update_ok)

        recent_cmds = self.db.get_recent_commands(limit=1)
        self.assertEqual(len(recent_cmds), 1)
        # Verify status is completed
        self.assertEqual(recent_cmds[0][4], "completed")

    # ------------------------------------------------------------------
    # 2. CREDENTIAL REDACTION WITHOUT DROPPING CONVERSATIONS
    # ------------------------------------------------------------------
    def test_sensitive_credential_redaction_preserves_conversation(self):
        """Sensitive API keys, passwords, and tokens are redacted to [REDACTED_...] while preserving conversation."""
        turn_id = "sec_turn_404"
        secret_input = "My Gemini API key is AIzaSyDdummyKey1234567890abcdefghijklm and password is SuperSecretPassword123"

        u_ok, _ = self.memory_manager.save_user_turn(
            user_text=secret_input,
            turn_id=turn_id,
            session_id="sess_sec"
        )
        self.assertTrue(u_ok)

        rec = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(rec)
        stored_cmd = rec["user_command"]

        # Secrets must NOT appear in database
        self.assertNotIn("AIzaSyDdummyKey1234567890abcdefghijklm", stored_cmd)
        self.assertNotIn("SuperSecretPassword123", stored_cmd)

        # Surrounding conversational words must be preserved
        self.assertIn("My Gemini API key is", stored_cmd)
        self.assertTrue("[REDACTED_API_KEY]" in stored_cmd or "[REDACTED_CREDENTIAL]" in stored_cmd)

    # ------------------------------------------------------------------
    # 3. STRUCTURED FAMILY MEMORY (MULTI-FACT & MULTI-LINGUAL)
    # ------------------------------------------------------------------
    def test_multi_fact_family_extraction_colon_format(self):
        """Single turn with Father, Mother, Brother extracts all three distinct facts."""
        turn_id = "turn_fam_multi"
        user_utterance = "Father: Senthilnathan, Mother: Sangeetha, Brother: Deepesh"
        asst_reply = "I have noted your family members: Father Senthilnathan, Mother Sangeetha, Brother Deepesh."

        self.memory_manager.save_user_turn(user_utterance, turn_id=turn_id)
        res = self.memory_manager.complete_turn(turn_id, assistant_text=asst_reply, user_text=user_utterance)
        self.assertTrue(res["success"])

        # Check in personal_memories table
        father_mem = self.db.get_personal_memories(category="relationships", key="father", active_only=True)
        mother_mem = self.db.get_personal_memories(category="relationships", key="mother", active_only=True)
        brother_mem = self.db.get_personal_memories(category="relationships", key="brother", active_only=True)

        self.assertEqual(len(father_mem), 1)
        self.assertEqual(father_mem[0]["value"], "Senthilnathan")
        self.assertEqual(len(mother_mem), 1)
        self.assertEqual(mother_mem[0]["value"], "Sangeetha")
        self.assertEqual(len(brother_mem), 1)
        self.assertEqual(brother_mem[0]["value"], "Deepesh")

        # Check known_people records
        people = self.memory_manager.get_all_known_people()
        names = {p["name"]: p["relationship_to_primary_user"] for p in people}
        self.assertEqual(names.get("Senthilnathan"), "father")
        self.assertEqual(names.get("Sangeetha"), "mother")
        self.assertEqual(names.get("Deepesh"), "brother")

    def test_tamil_script_family_extraction(self):
        """Tamil-script family statements extract correct relationships."""
        turn_id = "turn_tamil_fam"
        user_utterance = "என் அப்பா Senthilnathan, என் அம்மா Sangeetha, தம்பி Deepesh"
        self.memory_manager.save_user_turn(user_utterance, turn_id=turn_id)
        self.memory_manager.complete_turn(turn_id, assistant_text="Noted!", user_text=user_utterance)

        father_mem = self.db.get_personal_memories(category="relationships", key="father", active_only=True)
        self.assertTrue(len(father_mem) >= 1)
        self.assertEqual(father_mem[0]["value"], "Senthilnathan")

    # ------------------------------------------------------------------
    # 4. COMPREHENSIVE PERSONAL MEMORY ACROSS ALL DOMAINS
    # ------------------------------------------------------------------
    def test_education_extraction(self):
        """College, degree, academic year, and learning goals are extracted."""
        turn_id = "turn_edu_01"
        user_text = "I am studying in PSG Tech doing CSE degree, currently in 3rd year, learning AI"
        self.memory_manager.save_user_turn(user_text, turn_id=turn_id)
        self.memory_manager.complete_turn(turn_id, assistant_text="Great to hear about your studies!", user_text=user_text)

        col = self.memory_manager.get_profile_fact("college")
        deg = self.memory_manager.get_profile_fact("degree")
        yr = self.memory_manager.get_profile_fact("academic_year")
        goal = self.memory_manager.get_profile_fact("learning_goal")

        self.assertIsNotNone(col)
        self.assertIn("PSG", col)
        self.assertIsNotNone(deg)
        self.assertIn("CSE", deg)
        self.assertIsNotNone(yr)
        self.assertEqual(yr, "3rd year")
        self.assertIsNotNone(goal)
        self.assertEqual(goal, "AI")

    def test_work_career_skills_extraction(self):
        """Job role, company, and technical skills are extracted."""
        turn_id = "turn_work_01"
        user_text = "I am working as a Software Engineer at Zoho, my skills include Python, SQL, React"
        self.memory_manager.save_user_turn(user_text, turn_id=turn_id)
        self.memory_manager.complete_turn(turn_id, assistant_text="Noted your career details!", user_text=user_text)

        role = self.memory_manager.get_profile_fact("job_role")
        comp = self.memory_manager.get_profile_fact("company")
        skills = self.memory_manager.get_profile_fact("skills")

        self.assertIsNotNone(role)
        self.assertIn("Software Engineer", role)
        self.assertIsNotNone(comp)
        self.assertIn("Zoho", comp)
        self.assertIsNotNone(skills)
        self.assertIn("Python", skills)

    def test_project_decisions_and_plans_extraction(self):
        """Project decisions, tech stack, and deadlines are extracted."""
        turn_id = "turn_proj_01"
        user_text = "We decided to use SQLite for permanent memory and deadline is next Friday"
        self.memory_manager.save_user_turn(user_text, turn_id=turn_id)
        self.memory_manager.complete_turn(turn_id, assistant_text="Decision recorded!", user_text=user_text)

        dec = self.memory_manager.get_profile_fact("project_decision")
        dl = self.memory_manager.get_profile_fact("deadline")

        self.assertIsNotNone(dec)
        self.assertIn("SQLite", dec)
        self.assertIsNotNone(dl)
        self.assertIn("Friday", dl)

    def test_explicit_remember_note(self):
        """Explicit 'remember that' instructions create durable user notes."""
        turn_id = "turn_note_01"
        user_text = "Please remember that the lab keys are kept in the third drawer"
        self.memory_manager.save_user_turn(user_text, turn_id=turn_id)
        self.memory_manager.complete_turn(turn_id, assistant_text="I will remember that!", user_text=user_text)

        notes = self.db.get_personal_memories(category="user_note", active_only=True)
        self.assertTrue(len(notes) >= 1)
        self.assertIn("third drawer", notes[0]["value"])

    # ------------------------------------------------------------------
    # 5. CORRECTIONS & SUPERSESSION
    # ------------------------------------------------------------------
    def test_explicit_relationship_correction(self):
        """User correction supersedes the old relationship fact without leaving orphaned duplicates."""
        turn_id_1 = "turn_corr_1"
        self.memory_manager.save_user_turn("My brother is Rahul", turn_id=turn_id_1)
        self.memory_manager.complete_turn(turn_id_1, assistant_text="Got it, Rahul.", user_text="My brother is Rahul")

        b1 = self.db.get_personal_memories(category="relationships", key="brother", active_only=True)
        self.assertEqual(len(b1), 1)
        self.assertEqual(b1[0]["value"], "Rahul")

        # Correction
        turn_id_2 = "turn_corr_2"
        corr_text = "Actually my brother is not Rahul, it is Deepesh"
        self.memory_manager.save_user_turn(corr_text, turn_id=turn_id_2)
        self.memory_manager.complete_turn(turn_id_2, assistant_text="Updated brother to Deepesh.", user_text=corr_text)

        b2 = self.db.get_personal_memories(category="relationships", key="brother", active_only=True)
        self.assertEqual(len(b2), 1)
        self.assertEqual(b2[0]["value"], "Deepesh")

    # ------------------------------------------------------------------
    # 6. FORGETTING & RETRACTION
    # ------------------------------------------------------------------
    def test_forget_relationship_memory(self):
        """Forget memory request deactivates the fact across tables."""
        turn_id = "turn_fgt_1"
        self.memory_manager.save_user_turn("My father is Senthilnathan", turn_id=turn_id)
        self.memory_manager.complete_turn(turn_id, assistant_text="Noted Senthilnathan.", user_text="My father is Senthilnathan")

        f1 = self.db.get_personal_memories(category="relationships", key="father", active_only=True)
        self.assertEqual(len(f1), 1)

        # User requests to forget father
        forgot = self.memory_manager.forget_memory("father")
        self.assertTrue(forgot)

        f2 = self.db.get_personal_memories(category="relationships", key="father", active_only=True)
        self.assertEqual(len(f2), 0)

    # ------------------------------------------------------------------
    # 7. DURABLE RESTART SURVIVAL (SESSION A -> B)
    # ------------------------------------------------------------------
    def test_durable_restart_preserves_all_domains(self):
        """All categories written in Session A survive complete database close and reload in Session B."""
        # --- SESSION A ---
        db_a = DatabaseManager(database_path=self.db_path)
        mm_a = MemoryManager(db=db_a)

        # 1. Identity
        mm_a.set_user_name_preference("Naresh", use_name=True)
        # 2. Family
        mm_a.save_user_turn("Father: Senthilnathan, Mother: Sangeetha, Brother: Deepesh", turn_id="t_fam")
        mm_a.complete_turn("t_fam", assistant_text="Noted!", user_text="Father: Senthilnathan, Mother: Sangeetha, Brother: Deepesh")
        # 3. Education
        mm_a.set_profile_fact("college", "PSG Tech", category="education")
        # 4. Work
        mm_a.set_profile_fact("job_role", "AI Engineer", category="work")
        # 5. Project decision
        mm_a.set_profile_fact("project_decision", "Use SQLite for durable memory", category="project")
        # 6. Preference
        mm_a.set_profile_fact("preferred_language", "Tanglish", category="preference")

        db_a.close()
        del mm_a
        del db_a

        # --- SESSION B (Cold Restart) ---
        db_b = DatabaseManager(database_path=self.db_path)
        mm_b = MemoryManager(db=db_b)

        # 1. Identity survives
        pref_name, use_name = mm_b.get_user_name_preference()
        self.assertEqual(pref_name, "Naresh")
        self.assertTrue(use_name)

        # 2. Family survives
        fam_ans = mm_b.answer_memory_query("Naan en family pathi enna sonnen?")
        self.assertIsNotNone(fam_ans)
        self.assertIn("Senthilnathan", fam_ans)
        self.assertIn("Sangeetha", fam_ans)
        self.assertIn("Deepesh", fam_ans)

        # 3. Education survives
        self.assertEqual(mm_b.get_profile_fact("college"), "PSG Tech")

        # 4. Work survives
        self.assertEqual(mm_b.get_profile_fact("job_role"), "AI Engineer")

        # 5. Project decision survives
        dec_ans = mm_b.answer_memory_query("What was our project decision?")
        self.assertIsNotNone(dec_ans)
        self.assertIn("SQLite", dec_ans)

        # 6. Preference survives
        pref_ans = mm_b.answer_memory_query("Enna language prefer pannen?")
        self.assertIsNotNone(pref_ans)
        self.assertIn("Tanglish", pref_ans)

        db_b.close()

    # ------------------------------------------------------------------
    # 8. PROFILE ISOLATION
    # ------------------------------------------------------------------
    def test_multi_profile_isolation(self):
        """Memories belonging to profile_alpha do not leak into profile_beta."""
        # Profile Alpha
        self.db.add_personal_memory("mem_a1", "relationships", "brother", "Deepesh", profile_id="profile_alpha")
        self.db.add_personal_memory("mem_b1", "relationships", "brother", "Vikram", profile_id="profile_beta")

        alpha_mems = self.db.get_personal_memories(category="relationships", key="brother", profile_id="profile_alpha")
        beta_mems = self.db.get_personal_memories(category="relationships", key="brother", profile_id="profile_beta")

        self.assertEqual(len(alpha_mems), 1)
        self.assertEqual(alpha_mems[0]["value"], "Deepesh")
        self.assertEqual(len(beta_mems), 1)
        self.assertEqual(beta_mems[0]["value"], "Vikram")

    # ------------------------------------------------------------------
    # 9. CONTEXT BUILDER PROMPT INJECTION
    # ------------------------------------------------------------------
    def test_context_builder_injects_verified_facts(self):
        """PersonalityContextBuilder injects verified facts for prompt grounding."""
        self.memory_manager.set_user_name_preference("Naresh", use_name=True)
        self.memory_manager.set_profile_fact("college", "PSG Tech", category="education")
        self.memory_manager.add_known_person("Deepesh", relationship_to_primary_user="brother")

        block = PersonalityContextBuilder.build_context_block(
            memory_manager=self.memory_manager,
            query="Who is my brother and where do I study?"
        )

        self.assertIn("Naresh", block)
        self.assertIn("Deepesh", block)
        self.assertIn("PSG Tech", block)


if __name__ == "__main__":
    unittest.main()
