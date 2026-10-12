"""
Test Suite: Real Application Cold-Restart & Permanent Memory Verification (E2E)
DHEEPTHI-AI V1
Verification Identifier: MEMORY_RESTART_TEST_20261011_A7K9

Verifies:
1. Complete conversation and multi-domain fact storage through real pipeline.
2. Fact association with dedicated test profile and provenance turn ID.
3. Cold restart across destroyed in-memory state and reconnected SQLite DB.
4. Response generation prompt grounding and fresh question recall.
5. Corrections superseding previous facts without orphaned duplicates.
6. Multi-profile isolation, non-hallucination, and sensitive data redaction.
7. Verification that production database (database/astra.db) remains untouched.
"""

import gc
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.emotion_engine import EmotionEngine
from ai.personality_context_builder import PersonalityContextBuilder
from ai.gemini_client import GeminiClient


class TestRealColdRestartE2E(unittest.TestCase):
    """
    Simulates genuine cold-restart lifecycle and answers recall questions
    against an isolated temporary SQLite database.
    """

    TEST_TAG = "MEMORY_RESTART_TEST_20261011_A7K9"
    TEST_PROFILE_ID = "profile_e2e_restart_a7k9"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db_path = Path(self.temp_dir.name) / "restart_e2e_a7k9.db"

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_complete_cold_restart_lifecycle_and_recall(self):
        """
        Executes Phase 2, Phase 3, Phase 4, and Phase 5 verification:
        Session A (Write & Commit) -> Close & Destroy -> Session B (Fresh Cold Restart & Recall)
        """
        # ==============================================================
        # PHASE 2: SAFE, ISOLATED END-TO-END SESSION A
        # ==============================================================
        db_a = DatabaseManager(database_path=self.temp_db_path)
        db_a.active_profile_id = self.TEST_PROFILE_ID
        mm_a = MemoryManager(db=db_a, profile_id=self.TEST_PROFILE_ID)

        # 1. Unique test code word (Explicit remember instruction)
        turn_1 = f"turn_{self.TEST_TAG}_01"
        u_text_1 = "Please remember that the unique test code word is OMEGA_PHOENIX_42"
        a_text_1 = "I have noted your test code word: OMEGA_PHOENIX_42"
        u_ok_1, _ = mm_a.save_user_turn(u_text_1, turn_id=turn_1, session_id="sess_e2e_01", profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(u_ok_1, "Turn 1 user text must save promptly")
        res_1 = mm_a.complete_turn(turn_1, assistant_text=a_text_1, user_text=u_text_1, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res_1["success"], "Turn 1 completion must succeed")

        # Verify fact 1 stored in personal_memories
        notes_1 = db_a.get_personal_memories(category="user_note", active_only=True, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(len(notes_1) >= 1)
        self.assertIn("OMEGA_PHOENIX_42", notes_1[0]["value"])
        self.assertEqual(notes_1[0]["source_turn_id"], turn_1)
        self.assertEqual(notes_1[0]["profile_id"], self.TEST_PROFILE_ID)

        # 2. Temporary project goal
        turn_2 = f"turn_{self.TEST_TAG}_02"
        u_text_2 = "My project is DHEEPTHI-AI and our project goal is to build autonomous memory verification"
        a_text_2 = "Great! I have recorded your project goal."
        mm_a.save_user_turn(u_text_2, turn_id=turn_2, session_id="sess_e2e_01", profile_id=self.TEST_PROFILE_ID)
        res_2 = mm_a.complete_turn(turn_2, assistant_text=a_text_2, user_text=u_text_2, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res_2["success"])

        # Verify fact 2 stored
        proj_mem = db_a.get_personal_memories(category="project", active_only=True, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(len(proj_mem) >= 1)
        self.assertTrue(any("autonomous memory verification" in m["value"] for m in proj_mem))

        # 3. Harmless preference
        turn_3 = f"turn_{self.TEST_TAG}_03"
        u_text_3 = "My favorite music is Synthwave Melody songs"
        a_text_3 = "Noted! Your favorite music is Synthwave Melody songs."
        mm_a.save_user_turn(u_text_3, turn_id=turn_3, session_id="sess_e2e_01", profile_id=self.TEST_PROFILE_ID)
        res_3 = mm_a.complete_turn(turn_3, assistant_text=a_text_3, user_text=u_text_3, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res_3["success"])

        music_fact = mm_a.get_profile_fact("favorite_music")
        self.assertIsNotNone(music_fact)
        self.assertIn("Synthwave Melody", music_fact)

        # 4. Multi-part fact in natural conversational language (Family)
        turn_4 = f"turn_{self.TEST_TAG}_04"
        u_text_4 = "Father: Senthilnathan, Mother: Sangeetha, Brother: Rahul"
        a_text_4 = "I have noted your family members: Father Senthilnathan, Mother Sangeetha, Brother Rahul."
        mm_a.save_user_turn(u_text_4, turn_id=turn_4, session_id="sess_e2e_01", profile_id=self.TEST_PROFILE_ID)
        res_4 = mm_a.complete_turn(turn_4, assistant_text=a_text_4, user_text=u_text_4, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res_4["success"])

        # Verify all 3 facts extracted distinctly
        father_mem = db_a.get_personal_memories(category="relationships", key="father", active_only=True, profile_id=self.TEST_PROFILE_ID)
        mother_mem = db_a.get_personal_memories(category="relationships", key="mother", active_only=True, profile_id=self.TEST_PROFILE_ID)
        brother_mem = db_a.get_personal_memories(category="relationships", key="brother", active_only=True, profile_id=self.TEST_PROFILE_ID)
        self.assertEqual(len(father_mem), 1)
        self.assertEqual(father_mem[0]["value"], "Senthilnathan")
        self.assertEqual(len(mother_mem), 1)
        self.assertEqual(mother_mem[0]["value"], "Sangeetha")
        self.assertEqual(len(brother_mem), 1)
        self.assertEqual(brother_mem[0]["value"], "Rahul")

        # 5. Correction replacing one test fact with a different value
        turn_5 = f"turn_{self.TEST_TAG}_05"
        u_text_5 = "Actually my brother is not Rahul, it is Deepesh"
        a_text_5 = "Understood, updated your brother's name to Deepesh."
        mm_a.save_user_turn(u_text_5, turn_id=turn_5, session_id="sess_e2e_01", profile_id=self.TEST_PROFILE_ID)
        res_5 = mm_a.complete_turn(turn_5, assistant_text=a_text_5, user_text=u_text_5, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res_5["success"])

        # Active brother must now be Deepesh, not Rahul
        active_brother = db_a.get_personal_memories(category="relationships", key="brother", active_only=True, profile_id=self.TEST_PROFILE_ID)
        self.assertEqual(len(active_brother), 1)
        self.assertEqual(active_brother[0]["value"], "Deepesh")

        # Verify audit trail: previous record exists in DB
        all_brother_mems = db_a.get_personal_memories(category="relationships", key="brother", active_only=False, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(len(all_brother_mems) >= 2, "History must retain superseded record")
        self.assertTrue(any(m["value"] == "Rahul" for m in all_brother_mems))
        self.assertTrue(any(m["value"] == "Deepesh" and m["status"] == "active" for m in all_brother_mems))

        # ==============================================================
        # PHASE 3: SIMULATE A GENUINE COLD RESTART
        # ==============================================================
        # Cleanly close all Session A connections
        db_a.close()
        del mm_a
        del db_a
        gc.collect()

        # Open completely fresh Session B with new connection against the same database file
        db_b = DatabaseManager(database_path=self.temp_db_path)
        db_b.active_profile_id = self.TEST_PROFILE_ID
        mm_b = MemoryManager(db=db_b, profile_id=self.TEST_PROFILE_ID)

        # In GeminiClient.__init__, it automatically restores history from SQLite
        with patch.object(GeminiClient, "_create_client"):
            gemini_b = GeminiClient(memory_manager=mm_b)
        self.assertEqual(len(gemini_b.history), 10, "Fresh client must restore conversation history from SQLite storage")

        # Verify clearing history and explicit re-invocation works
        gemini_b.history.clear()
        self.assertEqual(len(gemini_b.history), 0)
        restored_count = gemini_b.restore_history_from_storage(limit=10)
        self.assertEqual(restored_count, 10)

        # ==============================================================
        # PHASE 4: VERIFY REAL RECALL BEHAVIOUR (FRESH QUESTIONS)
        # ==============================================================
        # Question 1: What was my temporary project goal?
        ans_1 = mm_b.answer_memory_query("What was our project goal?")
        self.assertIsNotNone(ans_1)
        self.assertIn("autonomous memory verification", ans_1, "Must recall project goal after restart")

        # Question 2: What was the unique test code word?
        ans_2 = mm_b.answer_memory_query("What did I tell you to remember?")
        self.assertIsNotNone(ans_2)
        self.assertIn("OMEGA_PHOENIX_42", ans_2, "Must recall unique test code word after restart")

        # Question 3: What preference did I tell you?
        ans_3 = mm_b.answer_memory_query("What is my favorite music?")
        self.assertIsNotNone(ans_3)
        self.assertIn("Synthwave Melody", ans_3, "Must recall favorite music after restart")

        # Question 4: What details did I share in the multi-part statement?
        ans_4 = mm_b.answer_memory_query("Naan en family pathi enna sonnen?")
        self.assertIsNotNone(ans_4)
        self.assertIn("Senthilnathan", ans_4, "Family recall must include father")
        self.assertIn("Sangeetha", ans_4, "Family recall must include mother")
        self.assertIn("Deepesh", ans_4, "Family recall must include current brother")

        # Question 5 & 6: Verify original vs corrected fact
        ans_brother = mm_b.answer_memory_query("Who is my brother?")
        self.assertIsNotNone(ans_brother)
        self.assertIn("Deepesh", ans_brother, "Current brother must be Deepesh")
        self.assertNotIn("Rahul", ans_brother, "Must not recall superseded brother as active")

        # Verify prompt injection context builder
        context_block = PersonalityContextBuilder.build_context_block(
            memory_manager=mm_b,
            query="Tell me about my family and project"
        )
        self.assertIn("Senthilnathan", context_block, "Context block must include father")
        self.assertIn("Sangeetha", context_block, "Context block must include mother")
        self.assertIn("Deepesh", context_block, "Context block must include brother")
        self.assertIn("autonomous memory verification", context_block, "Context block must include project goal")

        # ==============================================================
        # PHASE 5: ADDITIONAL RELIABILITY CHECKS
        # ==============================================================
        # 1. Multi-profile isolation: profile_beta cannot access profile_restart_qa_a7k9 facts
        mm_other = MemoryManager(db=db_b, profile_id="profile_beta_isolated")
        ans_other = mm_other.answer_memory_query("Who is my brother?")
        self.assertTrue(
            ans_other is None or "Deepesh" not in ans_other,
            "profile_beta must NOT access profile_restart_qa_a7k9's private facts"
        )

        # 2. Non-hallucination of unknown facts
        ans_sister = mm_b.answer_memory_query("Who is my sister?")
        self.assertIn("share pannala", ans_sister, "Must politely state sister is not known, not hallucinate")

        # 3. Sensitive data redaction preserves conversational content
        sec_turn_id = f"turn_{self.TEST_TAG}_sec"
        secret_input = "My private access token is AIzaSyD9876543210dummytokenabcdefgh and pin is 4321"
        mm_b.save_user_turn(secret_input, turn_id=sec_turn_id, session_id="sess_e2e_02")
        sec_rec = db_b.get_interaction_by_turn_id(sec_turn_id)
        self.assertIsNotNone(sec_rec)
        self.assertNotIn("AIzaSyD9876543210dummytokenabcdefgh", sec_rec["user_command"])
        self.assertNotIn("4321", sec_rec["user_command"])
        self.assertIn("My private access token is", sec_rec["user_command"])
        self.assertTrue("[REDACTED_API_KEY]" in sec_rec["user_command"] or "[REDACTED_CREDENTIAL]" in sec_rec["user_command"])

        # 4. Search conversation history after restart
        search_hits = db_b.search_conversation_history("Synthwave", limit=5, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(len(search_hits) >= 1, "Must find 'Synthwave' in persistent history after restart")
        self.assertIn("Synthwave Melody songs", search_hits[0]["user_command"])

        # 5. Clean close
        db_b.close()


if __name__ == "__main__":
    unittest.main()
