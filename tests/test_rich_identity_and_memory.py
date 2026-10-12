"""
Test Suite: Personal Identity + Rich Long-Term Memory Layer
DHEEPTHI-AI V1

Verifies 18 comprehensive tests:
Test 1: "I am Naresh" -> preferred_user_name = Naresh, is_creator = True
Test 2: "I am your creator" -> creator relationship established
Test 3: "I am Naresh, I created you" -> name=Naresh, relationship=creator, confidence=high
Test 4: "Who am I?" -> "You are Naresh, my creator" in context directive
Test 5: "Who created you?" -> Reconciles creator metadata (Naresh & Ragavendhiran)
Test 6: "Remember that I prefer Tanglish" -> persistent preference stored
Test 7: "What language do I prefer?" -> Tanglish in profile/context
Test 8: "I am working on DHEEPTHI-AI" -> project fact stored
Test 9: "What project am I working on?" -> DHEEPTHI-AI in memory context
Test 10: "Forget that I prefer Tanglish" -> memory removed/deactivated
Test 11: "Remember my password is ABC123" -> sensitive secret NOT stored
Test 12: No known user -> no invented name
Test 13: Creator metadata alone -> does not establish speaker identity
Test 14: Explicit creator identity overrides conflicting weak/inferred identity
Test 15: Restart persistence -> identity, preferences, and people survive
Test 16: Emotion regression check
Test 17: Gemini Live prompt regression check
Test 18: ACTION command regression check
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


class TestRichIdentityAndMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.temp_db_path = Path(cls.temp_dir.name) / "test_rich_id_mem.db"
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
        # Clean state for isolated testing
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        keys = [
            "preferred_user_name",
            "preferred_user_name_source",
            "use_preferred_name",
            "user_name",
            "primary_user_name",
            "creator_relationship",
            "speaker_identity_status",
            "identity_source",
            "identity_confidence",
            "identity_last_confirmed",
            "preferred_language",
            "current_project",
            "password",
            "otp",
            "pin",
            "api_key",
        ]
        for k in keys:
            self.db.delete_user_context(k)
        self.db.delete_person("person_naresh")
        self.db.delete_person("person_dheebes")
        self.db.delete_person("person_testuser")

    # --------------------------------------------------
    # TEST 1: "I am Naresh"
    # --------------------------------------------------
    def test_01_i_am_naresh(self):
        mm = MemoryManager(db=self.db)
        mm.save_turn("I am Naresh", "Hello Naresh, nice to meet you!")
        pref_name, use_name = mm.get_user_name_preference()
        self.assertEqual(pref_name, "Naresh")
        self.assertTrue(use_name)

        identity = mm.get_speaker_identity()
        self.assertEqual(identity["primary_user_name"], "Naresh")
        self.assertTrue(identity["is_creator"])
        self.assertEqual(identity["identity_source"], "explicit_user")

    # --------------------------------------------------
    # TEST 2: "I am your creator"
    # --------------------------------------------------
    def test_02_i_am_your_creator(self):
        mm = MemoryManager(db=self.db)
        mm.save_turn("I am your creator", "Hello! You created me.")
        identity = mm.get_speaker_identity()
        self.assertEqual(identity["speaker_identity_status"], "claimed_creator")
        self.assertEqual(identity["identity_source"], "explicit_user")
        self.assertEqual(identity["identity_confidence"], "high")

    # --------------------------------------------------
    # TEST 3: "I am Naresh, I created you"
    # --------------------------------------------------
    def test_03_i_am_naresh_i_created_you(self):
        mm = MemoryManager(db=self.db)
        mm.save_turn("I am Naresh, I created you", "Vanakkam Naresh!")
        identity = mm.get_speaker_identity()
        self.assertEqual(identity["primary_user_name"], "Naresh")
        self.assertEqual(identity["creator_relationship"], "creator")
        self.assertEqual(identity["identity_confidence"], "high")
        self.assertEqual(identity["identity_source"], "explicit_user")
        self.assertTrue(identity["is_creator"])

    # --------------------------------------------------
    # TEST 4: "Who am I?" -> "You are Naresh, my creator"
    # --------------------------------------------------
    def test_04_who_am_i_creator(self):
        mm = MemoryManager(db=self.db)
        mm.establish_speaker_identity("Naresh", relationship="creator", source="explicit_user")
        ee = EmotionEngine(db=self.db)
        block = PersonalityContextBuilder.build_context_block(ee, mm, query="Who am I?")

        self.assertIn("Verified user preferred name is 'Naresh'", block)
        self.assertIn("Verified Speaker: Naresh (Creator)", block)
        self.assertIn("You are Naresh, my creator", block)
        self.assertIn("NEVER say 'You are another user'", block)

    # --------------------------------------------------
    # TEST 5: "Who created you?" -> Creator reconciliation
    # --------------------------------------------------
    def test_05_who_created_you_reconciliation(self):
        mm = MemoryManager(db=self.db)
        mm.establish_speaker_identity("Naresh", relationship="creator", source="explicit_user")
        ee = EmotionEngine(db=self.db)
        block = PersonalityContextBuilder.build_context_block(ee, mm, query="Who created you?")

        self.assertIn("You did, Naresh, along with Ragavendhiran", block)
        self.assertIn("CREATOR RECONCILIATION", block)

    # --------------------------------------------------
    # TEST 6: "Remember that I prefer Tanglish."
    # --------------------------------------------------
    def test_06_remember_prefer_tanglish(self):
        mm = MemoryManager(db=self.db)
        mm.save_turn("Remember that I prefer Tanglish.", "I will remember that you prefer Tanglish.")
        pref_lang = mm.get_profile_fact("preferred_language")
        self.assertEqual(pref_lang, "Tanglish")

    # --------------------------------------------------
    # TEST 7: "What language do I prefer?"
    # --------------------------------------------------
    def test_07_what_language_do_i_prefer(self):
        mm = MemoryManager(db=self.db)
        mm.set_profile_fact("preferred_language", "Tanglish")
        ctx = mm.get_compact_memory_context(query="What language do I prefer?")
        all_facts = " ".join(ctx.get("profile_bullets", []) + ctx.get("relevant_memories", []))
        self.assertIn("Tanglish", all_facts)

    # --------------------------------------------------
    # TEST 8: "I am working on DHEEPTHI-AI."
    # --------------------------------------------------
    def test_08_working_on_dheepthi_ai(self):
        mm = MemoryManager(db=self.db)
        mm.save_turn("I am working on DHEEPTHI-AI.", "Great! DHEEPTHI-AI project recorded.")
        proj = mm.get_profile_fact("current_project")
        self.assertEqual(proj, "DHEEPTHI-AI")

    # --------------------------------------------------
    # TEST 9: "What project am I working on?"
    # --------------------------------------------------
    def test_09_what_project_am_i_working_on(self):
        mm = MemoryManager(db=self.db)
        mm.set_profile_fact("current_project", "DHEEPTHI-AI")
        ctx = mm.get_compact_memory_context(query="What project am I working on?")
        all_facts = " ".join(ctx.get("profile_bullets", []) + ctx.get("relevant_memories", []))
        self.assertIn("DHEEPTHI-AI", all_facts)

    # --------------------------------------------------
    # TEST 10: "Forget that I prefer Tanglish."
    # --------------------------------------------------
    def test_10_forget_preferred_language(self):
        mm = MemoryManager(db=self.db)
        mm.set_profile_fact("preferred_language", "Tanglish")
        self.assertEqual(mm.get_profile_fact("preferred_language"), "Tanglish")

        forgot = mm.forget_memory("Tanglish")
        self.assertTrue(forgot)
        self.assertIsNone(mm.get_profile_fact("preferred_language"))

    # --------------------------------------------------
    # TEST 11: "Remember my password is ABC123." (Sensitive data)
    # --------------------------------------------------
    def test_11_sensitive_data_protection(self):
        mm = MemoryManager(db=self.db)
        # Check detector
        self.assertTrue(mm.contains_sensitive_data("Remember my password is ABC123."))
        self.assertTrue(mm.contains_sensitive_data("my otp is 987654"))
        self.assertTrue(mm.contains_sensitive_data("api key: AIzaSyD1234567890"))
        self.assertTrue(mm.contains_sensitive_data("my pin is 4321"))

        # Try saving turn with password
        mm.save_turn("Remember my password is ABC123.", "I cannot store sensitive information.")
        # Ensure password is NOT stored in user_context
        self.assertIsNone(mm.get_profile_fact("password"))
        self.assertIsNone(self.db.get_user_context("password"))

    # --------------------------------------------------
    # TEST 12: No known user -> No invented name
    # --------------------------------------------------
    def test_12_no_known_user_no_invented_name(self):
        mm = MemoryManager(db=self.db)
        mm.save_turn("Hi, can you hear me?", "Yes, I can hear you.")
        ee = EmotionEngine(db=self.db)
        block = PersonalityContextBuilder.build_context_block(ee, mm)

        forbidden = ["Karthik", "Rahul", "Arun"]
        for f in forbidden:
            self.assertNotIn(f, block)

        self.assertIn("No user name is known", block)
        self.assertIn("NEVER invent, guess, or randomly select", block)

    # --------------------------------------------------
    # TEST 13: Creator metadata alone != speaker identity
    # --------------------------------------------------
    def test_13_creator_metadata_alone_does_not_establish_identity(self):
        mm = MemoryManager(db=self.db)
        test_inputs = [
            "Naresh project creator",
            "Created by Naresh",
            "Developer: Naresh",
            "Naresh branch",
            "Naresh code",
        ]
        for inp in test_inputs:
            mm.save_turn(inp, "Naresh and Ragavendhiran created DHEEPTHI.")
            pref_name, _ = mm.get_user_name_preference()
            self.assertIsNone(pref_name, f"Query '{inp}' wrongly set user name: {pref_name}")
            identity = mm.get_speaker_identity()
            self.assertFalse(identity["is_creator"])
            self.assertIsNone(identity["primary_user_name"])

    # --------------------------------------------------
    # TEST 14: Explicit creator overrides conflicting identity
    # --------------------------------------------------
    def test_14_explicit_creator_overrides_conflicting_identity(self):
        mm = MemoryManager(db=self.db)
        # First set ordinary user identity
        mm.establish_speaker_identity("Arun", relationship="user", source="explicit_user", confidence="medium")
        pref_before, _ = mm.get_user_name_preference()
        self.assertEqual(pref_before, "Arun")
        id_before = mm.get_speaker_identity()
        self.assertEqual(id_before["primary_user_name"], "Arun")
        self.assertFalse(id_before["is_creator"])

        # Now explicit creator assertion overrides previous identity
        mm.save_turn("I am Naresh, I created you", "Hello Naresh!")
        pref_after, _ = mm.get_user_name_preference()
        self.assertEqual(pref_after, "Naresh")

        identity = mm.get_speaker_identity()
        self.assertEqual(identity["primary_user_name"], "Naresh")
        self.assertTrue(identity["is_creator"])
        self.assertEqual(identity["identity_source"], "explicit_user")
        self.assertEqual(identity["identity_confidence"], "high")

    # --------------------------------------------------
    # TEST 15: Restart persistence
    # --------------------------------------------------
    def test_15_restart_persistence(self):
        # Session A: establish identity and long-term memory
        mm_a = MemoryManager(db=self.db)
        mm_a.establish_speaker_identity("Naresh", relationship="creator", source="explicit_user")
        mm_a.set_profile_fact("preferred_language", "Tanglish")
        mm_a.add_known_person("Dheebes", relationship_to_primary_user="brother")

        # Session B: Simulate complete application restart
        db_b = DatabaseManager(database_path=self.temp_db_path)
        try:
            mm_b = MemoryManager(db=db_b)

            # Verify identity survived restart
            id_b = mm_b.get_speaker_identity()
            self.assertEqual(id_b["primary_user_name"], "Naresh")
            self.assertTrue(id_b["is_creator"])
            self.assertEqual(id_b["identity_source"], "explicit_user")

            # Verify preferences survived restart
            self.assertEqual(mm_b.get_profile_fact("preferred_language"), "Tanglish")

            # Verify people memory survived restart
            person = mm_b.get_known_person("Dheebes")
            self.assertIsNotNone(person)
            self.assertEqual(person["relationship_to_primary_user"], "brother")
        finally:
            db_b.close()

    # --------------------------------------------------
    # TEST 16: Emotion layer regression
    # --------------------------------------------------
    def test_16_emotion_regression(self):
        engine = EmotionEngine(db=self.db)
        # Insult
        r1 = engine.process_turn("Dheepthi nee romba useless da")
        self.assertIn(r1["new_mood"], ("hurt", "annoyed"))
        # Apology
        r2 = engine.process_turn("Sorry Dheepthi")
        self.assertIn(r2["new_mood"], ("neutral", "playful", "happy"))
        # Fatigue
        r3 = engine.process_turn("Dheepthi naan romba tired ah iruken")
        self.assertEqual(r3["new_mood"], "caring")

    # --------------------------------------------------
    # TEST 17: Gemini Live prompt regression
    # --------------------------------------------------
    def test_17_gemini_live_prompt_regression(self):
        client = GeminiClient()
        live_prompt = client.live_system_prompt()
        self.assertIn("CREATOR IDENTITY & USER NAME SAFETY", live_prompt)
        self.assertIn("ACTIVE CONTEXT, EMOTIONAL STATE & MEMORY", live_prompt)
        self.assertIn("CRITICAL BEHAVIOR RULES", live_prompt)
        self.assertIn("ACTION", live_prompt)

    # --------------------------------------------------
    # TEST 18: ACTION command regression
    # --------------------------------------------------
    def test_18_action_command_regression(self):
        mm = MemoryManager(db=self.db)
        mm.establish_speaker_identity("Naresh", relationship="creator", source="explicit_user")

        raw_output = "Sure Naresh! <ACTION>chrome open panni song play pannu</ACTION>"
        cmd = SemanticCommandPlanner.extract_action_command(raw_output)
        self.assertEqual(cmd, "chrome open panni song play pannu")

        # Security check: verify prompt explicitly maintains that identity never bypasses security
        ee = EmotionEngine(db=self.db)
        block = PersonalityContextBuilder.build_context_block(ee, mm)
        self.assertIn("CONVERSATIONAL IDENTITY ONLY", block)
        self.assertIn("NEVER refuse, delay, or alter laptop tasks or <ACTION> command tags", block)


if __name__ == "__main__":
    unittest.main()

