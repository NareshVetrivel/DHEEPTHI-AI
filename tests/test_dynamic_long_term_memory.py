"""
Tests for True Dynamic, Human-like Long-Term Memory System in DHEEPTHI-AI V1

Verifies:
1. Speech Act Discrimination (questions and hypotheticals rejected from fact extraction).
2. Compound Multi-Fact Extraction (multiple facts in a single utterance).
3. Open-Domain Extraction (possessions, locations, dietary/health, routines, schedules, decisions, tasks, people).
4. Broad & Specific Contextual Retrieval.
5. Memory Evolution & Supersession (corrections preserve history).
6. Selective Forgetting & Retraction.
7. Deduplication & Confidence Reinforcement.
8. Multi-Profile Isolation.
9. Sensitive Credential Safety & Redaction.
10. Model Prompt Injection & Budget Adherence.
"""

import os
import tempfile
import unittest
from pathlib import Path

from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.personality_context_builder import PersonalityContextBuilder


class TestDynamicLongTermMemory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.test_db_path = Path(self.temp_dir.name) / "test_dynamic_memory.db"
        self.db = DatabaseManager(database_path=self.test_db_path)
        self.profile_id = "test_user_alpha"
        self.mm = MemoryManager(db=self.db, profile_id=self.profile_id)

    def tearDown(self):
        try:
            if hasattr(self, "db") and self.db:
                self.db.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # ==================================================
    # 1. SPEECH ACT DISCRIMINATION
    # ==================================================

    def test_01_question_rejection_from_fact_extraction(self):
        """Questions asking about possessions, family, or locations must NOT extract facts."""
        questions = [
            "Do I have a bike?",
            "En bike enna?",
            "Where do I live?",
            "Who is my brother?",
            "What did we decide about the database?",
            "Do I have any allergies?",
            "What is my college?",
        ]
        for q in questions:
            extracted = self.mm.extract_memories_from_turn(user_text=q, source_turn_id="turn_q")
            self.assertEqual(extracted, [], f"Question incorrectly extracted facts: {q}")

        # Active memories must remain empty
        mems = self.db.get_personal_memories(active_only=True, profile_id=self.profile_id)
        self.assertEqual(len(mems), 0)

    def test_02_hypothetical_statements_rejected(self):
        """Hypothetical or speculative statements must not be extracted as facts."""
        hypo = "If I buy a car, it will be a BMW"
        extracted = self.mm.extract_memories_from_turn(user_text=hypo, source_turn_id="turn_h")
        self.assertEqual(extracted, [])

        mems = self.db.get_personal_memories(key="car", active_only=True, profile_id=self.profile_id)
        self.assertEqual(len(mems), 0)

    # ==================================================
    # 2. COMPOUND MULTI-FACT EXTRACTION
    # ==================================================

    def test_03_multi_fact_single_utterance_extraction(self):
        """Single utterance with 3 facts (living city, bike, allergy) must extract all 3."""
        utterance = "I live in Salem, my bike is Yamaha R15, and I am allergic to peanuts."
        extracted = self.mm.extract_memories_from_turn(user_text=utterance, source_turn_id="turn_multi")
        self.assertGreaterEqual(len(extracted), 3)

        city = self.mm.get_profile_fact("living_city")
        bike = self.mm.get_profile_fact("bike")
        allergy = self.mm.get_profile_fact("allergy")

        self.assertEqual(city, "Salem")
        self.assertEqual(bike, "Yamaha R15")
        self.assertEqual(allergy, "peanuts")

    # ==================================================
    # 3. OPEN-DOMAIN CATEGORIES
    # ==================================================

    def test_04_possessions_and_valuables(self):
        """Extracts car, laptop, phone, and stored items with locations."""
        # Car & laptop
        self.mm.extract_memories_from_turn("My car is Honda City and my laptop is MacBook Pro")
        self.assertEqual(self.mm.get_profile_fact("car"), "Honda City")
        self.assertEqual(self.mm.get_profile_fact("laptop"), "MacBook Pro")

        # Stored item in drawer
        self.mm.extract_memories_from_turn("I keep my lab keys in the third drawer")
        loc_val = self.mm.get_profile_fact("stored_item_lab_keys")
        self.assertIn("third drawer", loc_val.lower())

        # Recall keys
        ans = self.mm.answer_memory_query("Where did I put the lab keys?")
        self.assertIn("third drawer", ans)

    def test_05_locations_and_residence(self):
        """Extracts living city and native/hometown."""
        self.mm.extract_memories_from_turn("I live in Salem and my native is Madurai")
        self.assertEqual(self.mm.get_profile_fact("living_city"), "Salem")
        self.assertEqual(self.mm.get_profile_fact("hometown"), "Madurai")

        ans_live = self.mm.answer_memory_query("Where do I live?")
        self.assertIn("Salem", ans_live)

        ans_native = self.mm.answer_memory_query("Where is my hometown?")
        self.assertIn("Madurai", ans_native)

    def test_06_dietary_and_health_preferences(self):
        """Extracts allergies and vegetarian diet preference."""
        self.mm.extract_memories_from_turn("I am allergic to mushrooms and I am pure vegetarian")
        self.assertEqual(self.mm.get_profile_fact("allergy"), "mushrooms")
        self.assertIn("vegetarian", self.mm.get_profile_fact("dietary_preference").lower())

        ans_all = self.mm.answer_memory_query("Do I have any allergies?")
        self.assertIn("mushrooms", ans_all)

        ans_diet = self.mm.answer_memory_query("What is my diet?")
        self.assertIn("vegetarian", ans_diet.lower())

    def test_07_routines_and_habits(self):
        """Extracts wake up time and gym routine."""
        self.mm.extract_memories_from_turn("I wake up at 6 AM and I go to gym at 7 PM")
        self.assertIn("6 AM", self.mm.get_profile_fact("wake_up_time"))
        self.assertIn("7 PM", self.mm.get_profile_fact("fitness_routine"))

        ans_wake = self.mm.answer_memory_query("What time do I wake up?")
        self.assertIn("6 AM", ans_wake)

        ans_gym = self.mm.answer_memory_query("When do I go to the gym?")
        self.assertIn("7 PM", ans_gym)

    def test_08_schedules_and_appointments(self):
        """Extracts doctor appointments and meeting schedules."""
        self.mm.extract_memories_from_turn("Doctor appointment on Friday 5 PM")
        self.assertIn("Friday 5 PM", self.mm.get_profile_fact("doctor_appointment"))

        ans_doc = self.mm.answer_memory_query("When is my doctor appointment?")
        self.assertIn("Friday 5 PM", ans_doc)

    def test_09_decisions_and_tech_stack(self):
        """Extracts project/technical decisions."""
        self.mm.extract_memories_from_turn("We decided to use SQLite for database")
        self.assertIn("SQLite for database", self.mm.get_profile_fact("project_decision"))

        ans_dec = self.mm.answer_memory_query("What did we decide about the database?")
        self.assertIn("SQLite for database", ans_dec)

    def test_10_commitments_and_pending_tasks(self):
        """Extracts commitments and pending tasks."""
        self.mm.extract_memories_from_turn("I need to pay electricity bill tomorrow")
        self.assertIn("pay electricity bill", self.mm.get_profile_fact("pending_task"))

        ans_task = self.mm.answer_memory_query("What do I need to do tomorrow?")
        self.assertIn("pay electricity bill", ans_task)

    def test_11_non_family_people_network(self):
        """Extracts manager and teammate."""
        self.mm.extract_memories_from_turn("My manager is Suresh and my teammate is Priya")
        self.assertEqual(self.mm.get_profile_fact("manager"), "Suresh")
        self.assertEqual(self.mm.get_profile_fact("teammate"), "Priya")

        ans_mgr = self.mm.answer_memory_query("Who is my manager?")
        self.assertIn("Suresh", ans_mgr)

        ans_team = self.mm.answer_memory_query("Who is my teammate?")
        self.assertIn("Priya", ans_team)

    # ==================================================
    # 4. BROAD PROFILE RECALL
    # ==================================================

    def test_12_broad_overview_query(self):
        """'What do you know about me?' synthesizes personal context across categories."""
        self.mm.establish_speaker_identity("Naresh")
        self.mm.extract_memories_from_turn("I live in Salem, my bike is Yamaha R15, and my manager is Suresh")

        ans = self.mm.answer_memory_query("What do you know about me?")
        self.assertIn("Naresh", ans)
        self.assertIn("Salem", ans)
        self.assertIn("Yamaha R15", ans)
        self.assertIn("Suresh", ans)

    # ==================================================
    # 5. MEMORY EVOLUTION & CORRECTIONS
    # ==================================================

    def test_13_fact_correction_supersedes_prior_fact(self):
        """User corrects their bike: old fact is marked 'superseded', new is 'active'."""
        self.mm.extract_memories_from_turn("My bike is Yamaha R15")
        self.assertEqual(self.mm.get_profile_fact("bike"), "Yamaha R15")

        # Correction
        self.mm.extract_memories_from_turn("Actually my bike is not Yamaha R15, it is KTM Duke")

        # Active fact is KTM Duke
        self.assertEqual(self.mm.get_profile_fact("bike"), "KTM Duke")
        ans = self.mm.answer_memory_query("What bike do I have?")
        self.assertIn("KTM Duke", ans)

        # Inspect DB rows: prior memory should be superseded
        all_bike_mems = self.db.get_personal_memories(key="bike", active_only=False, profile_id=self.profile_id)
        active_bike_mems = [m for m in all_bike_mems if m.get("status") == "active"]
        superseded_mems = [m for m in all_bike_mems if m.get("status") == "superseded"]

        self.assertEqual(len(active_bike_mems), 1)
        self.assertEqual(active_bike_mems[0].get("value"), "KTM Duke")
        self.assertGreaterEqual(len(superseded_mems), 1)
        self.assertEqual(superseded_mems[0].get("value"), "Yamaha R15")

    # ==================================================
    # 6. SELECTIVE FORGETTING
    # ==================================================

    def test_14_selective_forgetting(self):
        """User requests forgetting a fact; status becomes 'retracted'."""
        self.mm.extract_memories_from_turn("My bike is Yamaha R15")
        self.assertEqual(self.mm.get_profile_fact("bike"), "Yamaha R15")

        # Forget
        self.mm.forget_memory("bike")

        ans = self.mm.answer_memory_query("What bike do I have?")
        self.assertIn("memory-la details illa", ans)

    # ==================================================
    # 7. DEDUPLICATION
    # ==================================================

    def test_15_deduplication_on_repeated_facts(self):
        """Repeating the exact same fact does not create duplicate active rows."""
        self.mm.extract_memories_from_turn("My bike is Yamaha R15")
        self.mm.extract_memories_from_turn("My bike is Yamaha R15")

        active_bike = self.db.get_personal_memories(key="bike", active_only=True, profile_id=self.profile_id)
        self.assertEqual(len(active_bike), 1)
        self.assertEqual(active_bike[0].get("value"), "Yamaha R15")

    # ==================================================
    # 8. MULTI-PROFILE ISOLATION
    # ==================================================

    def test_16_profile_isolation(self):
        """Facts saved in Profile A are completely invisible to Profile B."""
        mm_a = MemoryManager(db=self.db, profile_id="user_alpha")
        mm_b = MemoryManager(db=self.db, profile_id="user_beta")

        mm_a.extract_memories_from_turn("My bike is Yamaha R15")
        self.assertEqual(mm_a.get_profile_fact("bike"), "Yamaha R15")

        # In profile B, bike is not found
        self.assertIsNone(mm_b.get_profile_fact("bike"))
        ans_b = mm_b.answer_memory_query("What bike do I have?")
        self.assertIn("memory-la details illa", ans_b)

    # ==================================================
    # 9. SENSITIVE CREDENTIAL PROTECTION
    # ==================================================

    def test_17_sensitive_credential_redaction(self):
        """Passwords or tokens in turns are redacted before persistence and fact extraction."""
        turn_text = "My password is SecretAdmin999 and my bike is Yamaha R15"
        self.mm.save_turn(user_text=turn_text, assistant_text="Noted", turn_id="turn_sec")

        # Bike extracted safely
        self.assertEqual(self.mm.get_profile_fact("bike"), "Yamaha R15")

        # No password saved as a fact
        pw_fact = self.mm.get_profile_fact("password")
        self.assertIsNone(pw_fact)

        # In conversation context, password was redacted
        window = self.db.get_recent_conversation_window(limit=1, profile_id=self.profile_id)
        self.assertTrue(len(window) > 0)
        stored_cmd = window[0].get("user_command", "")
        self.assertNotIn("SecretAdmin999", stored_cmd)
        self.assertIn("[REDACTED_CREDENTIAL]", stored_cmd)

    # ==================================================
    # 10. PROMPT INJECTION & TOKEN BUDGET
    # ==================================================

    def test_18_prompt_injection_includes_open_domain_facts(self):
        """PersonalityContextBuilder injects retrieved memories and stays within token budget."""
        self.mm.establish_speaker_identity("Naresh")
        self.mm.extract_memories_from_turn("I live in Salem, my bike is Yamaha R15, and my manager is Suresh")

        block = PersonalityContextBuilder.build_context_block(
            memory_manager=self.mm,
            query="What bike do I have?"
        )

        self.assertIn("Naresh", block)
        self.assertIn("Yamaha R15", block)
        self.assertLess(len(block), 1990)

    # ==================================================
    # 11. ERROR TURN PERSISTENCE
    # ==================================================

    def test_19_error_turn_persisted_with_status(self):
        """Failed or error turns are archived with turn_status='error'."""
        self.mm.save_turn(
            user_text="Open invalid app",
            assistant_text="Error: Application not found",
            turn_id="turn_err_101",
            turn_status="error"
        )

        window = self.db.get_recent_conversation_window(limit=1, profile_id=self.profile_id)
        self.assertTrue(len(window) > 0)
        self.assertEqual(window[0].get("turn_status"), "error")
        self.assertIn("Error: Application not found", window[0].get("assistant_response", ""))


if __name__ == "__main__":
    unittest.main()
