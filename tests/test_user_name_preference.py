"""
Test Suite: User Name Safety and Persistent Preference
DHEEPTHI-AI V1
Verifies:
1. No known name -> No random or invented name (Karthik, Rahul, Arun, etc.)
2. Explicit name -> preferred_user_name == 'Naresh', use_preferred_name == True
3. Name usage -> Verified name present in prompt context
4. Reject name -> use_preferred_name == False, preferred_user_name == None
5. No random fallback across repeated queries
6. Creator metadata isolation -> Creator Naresh != User Name
7. Persistent name preference survives restart
8. Persistent opt-out survives restart
9. Emotion layer regression check
10. Action/automation command regression check
"""

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.database_manager import DatabaseManager
from ai.emotion_engine import EmotionEngine
from ai.memory_manager import MemoryManager
from ai.personality_context_builder import PersonalityContextBuilder
from ai.gemini_client import GeminiClient
from planner.semantic_command_planner import SemanticCommandPlanner


class TestUserNamePreference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.temp_db_path = Path(cls.temp_dir.name) / "test_user_name_pref.db"
        cls.db = DatabaseManager(database_path=cls.temp_db_path)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.close()
            del cls.db
            import gc
            gc.collect()
        except Exception:
            pass
        try:
            cls.temp_dir.cleanup()
        except Exception:
            pass

    def setUp(self):
        # Reset name preferences to a clean unknown state
        self.db.delete_user_context("preferred_user_name")
        self.db.delete_user_context("preferred_user_name_source")
        self.db.delete_user_context("use_preferred_name")
        self.db.delete_user_context("user_name")

    def tearDown(self):
        self.db.delete_user_context("preferred_user_name")
        self.db.delete_user_context("preferred_user_name_source")
        self.db.delete_user_context("use_preferred_name")
        self.db.delete_user_context("user_name")

    # --------------------------------------------------
    # TEST 1: No known name
    # --------------------------------------------------
    def test_1_no_known_name(self):
        mm = MemoryManager(db=self.db)
        # Turn with no explicit name
        mm.save_turn("Hi, can you hear me?", "Hi! Yes, I can hear you.")
        pref_name, use_name = mm.get_user_name_preference()
        self.assertIsNone(pref_name)
        self.assertTrue(use_name)

        # Context builder verification
        ee = EmotionEngine(db=self.db)
        block = PersonalityContextBuilder.build_context_block(ee, mm)

        # Must not contain any invented names
        forbidden = ["Karthik", "Rahul", "Arun"]
        for f in forbidden:
            self.assertNotIn(f, block, f"Context block leaked forbidden name: {f}")

        # Directive must explicitly state no user name is known
        self.assertIn("No user name is known", block)
        self.assertIn("NEVER invent, guess, or randomly select", block)

    # --------------------------------------------------
    # TEST 2: Explicit name
    # --------------------------------------------------
    def test_2_explicit_name(self):
        mm = MemoryManager(db=self.db)
        mm.save_turn("My name is Naresh", "Hello Naresh, nice to meet you!")
        pref_name, use_name = mm.get_user_name_preference()
        self.assertEqual(pref_name, "Naresh")
        self.assertTrue(use_name)

        # Tanglish equivalent check
        mm.save_turn("En peru Vignesh", "Vanakkam Vignesh!")
        pref_name2, use_name2 = mm.get_user_name_preference()
        self.assertEqual(pref_name2, "Vignesh")
        self.assertTrue(use_name2)

    # --------------------------------------------------
    # TEST 3: Name usage in context
    # --------------------------------------------------
    def test_3_name_usage_in_context(self):
        mm = MemoryManager(db=self.db)
        mm.set_user_name_preference("Naresh", use_name=True, source="explicit_user")
        ee = EmotionEngine(db=self.db)
        block = PersonalityContextBuilder.build_context_block(ee, mm)

        self.assertIn("Verified user preferred name is 'Naresh'", block)
        self.assertIn("You may address the user as Naresh naturally", block)

    # --------------------------------------------------
    # TEST 4: Reject name (Opt-out)
    # --------------------------------------------------
    def test_4_reject_name_opt_out(self):
        mm = MemoryManager(db=self.db)
        # First set a name
        mm.set_user_name_preference("Naresh", use_name=True, source="explicit_user")
        pref_name, use_name = mm.get_user_name_preference()
        self.assertEqual(pref_name, "Naresh")

        # Now user says: "Naresh nu koopdatha"
        mm.save_turn("Naresh nu koopdatha", "Seri da, naan unga name use panna maatten.")
        pref_name, use_name = mm.get_user_name_preference()
        self.assertIsNone(pref_name)
        self.assertFalse(use_name)

        # Check context block enforces opt-out
        ee = EmotionEngine(db=self.db)
        block = PersonalityContextBuilder.build_context_block(ee, mm)
        self.assertIn("The user explicitly requested NOT to be addressed by name", block)
        self.assertNotIn("Naresh", block)

        # Test another Tanglish opt-out phrasing
        mm.save_turn("En peru use panna vendam", "Seri pa.")
        pref_name2, use_name2 = mm.get_user_name_preference()
        self.assertFalse(use_name2)

        # Test English opt-out phrasing
        mm.save_turn("Don't call me by my name", "Understood.")
        pref_name3, use_name3 = mm.get_user_name_preference()
        self.assertFalse(use_name3)

    # --------------------------------------------------
    # TEST 5: No random fallback across repeated queries
    # --------------------------------------------------
    def test_5_no_random_fallback_repeated_queries(self):
        mm = MemoryManager(db=self.db)
        ee = EmotionEngine(db=self.db)
        queries = [
            "Hi",
            "Can you hear me?",
            "How are you?",
            "Are you listening?",
            "Tell me about the universe",
        ]
        forbidden = ["Karthik", "Rahul", "Arun", "Naresh"]

        for q in queries:
            mm.save_turn(q, "Yes, I am here.")
            pref_name, _ = mm.get_user_name_preference()
            self.assertIsNone(pref_name, f"Query '{q}' mistakenly set a name: {pref_name}")
            block = PersonalityContextBuilder.build_context_block(ee, mm)
            for f in forbidden:
                self.assertNotIn(f, block, f"Query '{q}' caused leaked name '{f}' in context block")

    # --------------------------------------------------
    # TEST 6: Creator metadata isolation
    # --------------------------------------------------
    def test_6_creator_metadata_isolation(self):
        mm = MemoryManager(db=self.db)
        # Creator discussions must NOT be treated as user name
        test_inputs = [
            "Naresh project creator",
            "Created by Naresh",
            "Developer: Naresh",
            "Naresh branch",
            "Naresh code",
            "Naresh's laptop",
        ]
        for inp in test_inputs:
            mm.save_turn(inp, "Naresh and Ragavendhiran created DHEEPTHI.")
            pref_name, _ = mm.get_user_name_preference()
            self.assertIsNone(pref_name, f"Creator input '{inp}' wrongly established user name: {pref_name}")

        # Check prompt separation in GeminiClient
        client = GeminiClient()
        live_prompt = client.live_system_prompt()
        self.assertIn("CREATOR IDENTITY & USER NAME SAFETY", live_prompt)
        self.assertIn("CRITICAL USER NAME SAFETY & SEPARATION", live_prompt)
        self.assertIn("NEVER assume the person speaking to you is Naresh or Ragavendhiran", live_prompt)

    # --------------------------------------------------
    # TEST 7: Persistent name preference survives restart
    # --------------------------------------------------
    def test_7_persistent_name_preference_survives_restart(self):
        # Session A: establish name
        mm_a = MemoryManager(db=self.db)
        mm_a.set_user_name_preference("Naresh", use_name=True, source="explicit_user")
        self.assertEqual(mm_a.get_user_name_preference(), ("Naresh", True))

        # Session B: simulate app restart with fresh MemoryManager
        db_b = DatabaseManager(database_path=self.temp_db_path)
        try:
            mm_b = MemoryManager(db=db_b)
            pref_name_b, use_name_b = mm_b.get_user_name_preference()
            self.assertEqual(pref_name_b, "Naresh")
            self.assertTrue(use_name_b)
        finally:
            db_b.close()

    # --------------------------------------------------
    # TEST 8: Persistent opt-out survives restart
    # --------------------------------------------------
    def test_8_persistent_opt_out_survives_restart(self):
        # Session A: user opts out
        mm_a = MemoryManager(db=self.db)
        mm_a.set_user_name_preference(preferred_name=None, use_name=False)
        self.assertEqual(mm_a.get_user_name_preference(), (None, False))

        # Session B: simulate app restart
        db_b = DatabaseManager(database_path=self.temp_db_path)
        try:
            mm_b = MemoryManager(db=db_b)
            pref_name_b, use_name_b = mm_b.get_user_name_preference()
            self.assertIsNone(pref_name_b)
            self.assertFalse(use_name_b)
        finally:
            db_b.close()

    # --------------------------------------------------
    # TEST 9: Emotion layer regression
    # --------------------------------------------------
    def test_9_emotion_regression(self):
        ee = EmotionEngine(db=self.db)
        # Insult
        r1 = ee.process_turn("Dheepthi nee romba useless da")
        self.assertIn(r1["new_mood"], ("hurt", "annoyed"))
        # Apology
        r2 = ee.process_turn("Sorry Dheepthi")
        self.assertIn(r2["new_mood"], ("neutral", "playful", "happy"))
        # Fatigue
        r3 = ee.process_turn("Dheepthi naan romba tired ah iruken")
        self.assertEqual(r3["new_mood"], "caring")

    # --------------------------------------------------
    # TEST 10: ACTION / automation command regression
    # --------------------------------------------------
    def test_10_action_command_regression(self):
        # Verify action extraction works even when name preferences change
        mm = MemoryManager(db=self.db)
        mm.set_user_name_preference("Naresh", use_name=True, source="explicit_user")

        raw_output = "Sure Naresh! <ACTION>chrome open panni pavalamalli song play pannu</ACTION>"
        cmd = SemanticCommandPlanner.extract_action_command(raw_output)
        self.assertEqual(cmd, "chrome open panni pavalamalli song play pannu")

        # Verify action extraction when user opted out of name
        mm.set_user_name_preference(preferred_name=None, use_name=False)
        raw_output2 = "Sure! <ACTION>open chrome</ACTION>"
        cmd2 = SemanticCommandPlanner.extract_action_command(raw_output2)
        self.assertEqual(cmd2, "open chrome")


if __name__ == "__main__":
    unittest.main()
