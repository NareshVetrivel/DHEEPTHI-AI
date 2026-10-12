"""
Unit and Integration Tests for Emotional Layer + Persistent Memory
DHEEPTHI-AI V1
"""

import os
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


class TestEmotionAndMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()

    def setUp(self):
        # Reset to known baseline state for tests
        self.db.set_emotional_state(
            current_mood="neutral",
            valence=0.55,
            arousal=0.50,
            rapport_level=0.75,
            last_trigger="test_setup"
        )

    # --------------------------------------------------
    # 1. Database memory CRUD
    # --------------------------------------------------
    def test_1_database_memory_crud(self):
        # Set state
        ok = self.db.set_emotional_state("happy", 0.85, 0.60, 0.80, "test_trigger")
        self.assertTrue(ok)
        state = self.db.get_emotional_state()
        self.assertEqual(state["current_mood"], "happy")
        self.assertAlmostEqual(state["valence"], 0.85, places=2)

        # Log emotion event
        ok_log = self.db.log_emotion_event(
            user_utterance="Great job",
            detected_stimulus="praise",
            prev_mood="neutral",
            new_mood="happy",
            valence_delta=0.3,
            rationale="testing"
        )
        self.assertTrue(ok_log)
        logs = self.db.get_recent_emotion_logs(5)
        self.assertGreaterEqual(len(logs), 1)

    # --------------------------------------------------
    # 2. Conversation persistence
    # --------------------------------------------------
    def test_2_conversation_persistence(self):
        self.db.add_conversation_context(
            user_command="test message 1",
            assistant_response="test response 1",
            intent="conversation"
        )
        recent = self.db.get_recent_context(limit=5)
        self.assertGreaterEqual(len(recent), 1)
        self.assertEqual(recent[0][1], "test message 1")
        self.assertEqual(recent[0][2], "test response 1")

        # Trim test
        trimmed = self.db.trim_conversation_context(keep_last=50)
        self.assertTrue(trimmed)

    # --------------------------------------------------
    # 3. User profile persistence
    # --------------------------------------------------
    def test_3_user_profile_persistence(self):
        self.db.set_user_context("test_key", "test_value")
        val = self.db.get_user_context("test_key")
        self.assertEqual(val, "test_value")
        self.db.delete_user_context("test_key")
        self.assertIsNone(self.db.get_user_context("test_key"))

    # --------------------------------------------------
    # 4. Episodic memory persistence
    # --------------------------------------------------
    def test_4_episodic_memory_persistence(self):
        ok = self.db.add_memory_episode(
            summary="User finished important sprint",
            emotional_valence=0.9,
            category="achievement",
            importance=5
        )
        self.assertTrue(ok)
        episodes = self.db.get_important_episodes(min_importance=4, limit=5)
        self.assertGreaterEqual(len(episodes), 1)
        self.assertIn("User finished important sprint", [e[2] for e in episodes])

    # --------------------------------------------------
    # 5. Emotional state initialization
    # --------------------------------------------------
    def test_5_emotional_state_initialization(self):
        engine = EmotionEngine(db=self.db)
        summary = engine.get_state_summary()
        self.assertIn(summary["current_mood"], EmotionEngine.SUPPORTED_MOODS)
        self.assertGreaterEqual(summary["valence"], 0.0)
        self.assertLessEqual(summary["valence"], 1.0)
        self.assertIn("tone_directive", summary)

    # --------------------------------------------------
    # 6. Insult -> hurt/annoyed
    # --------------------------------------------------
    def test_6_insult_to_hurt_or_annoyed(self):
        engine = EmotionEngine(db=self.db)
        res = engine.process_turn("Dheepthi nee romba useless da")
        self.assertEqual(res["stimulus"], "insult")
        self.assertIn(res["new_mood"], ("hurt", "annoyed"))
        self.assertLess(res["valence"], 0.50)

    # --------------------------------------------------
    # 7. Apology -> warm/neutral
    # --------------------------------------------------
    def test_7_apology_to_warm_or_neutral(self):
        engine = EmotionEngine(db=self.db)
        # First trigger hurt
        engine.process_turn("Dheepthi nee useless")
        self.assertIn(engine.current_mood, ("hurt", "annoyed"))
        # Now apologize
        res = engine.process_turn("Sorry Dheepthi")
        self.assertEqual(res["stimulus"], "apology")
        self.assertIn(res["new_mood"], ("neutral", "playful", "happy"))
        self.assertGreater(res["valence"], 0.50)

    # --------------------------------------------------
    # 8. Fatigue -> caring
    # --------------------------------------------------
    def test_8_fatigue_to_caring(self):
        engine = EmotionEngine(db=self.db)
        res = engine.process_turn("Dheepthi naan romba tired ah iruken")
        self.assertEqual(res["stimulus"], "fatigue_sadness")
        self.assertEqual(res["new_mood"], "caring")
        self.assertIn("caring", engine.get_tone_directive().lower())

    # --------------------------------------------------
    # 9. Praise -> happy/warm
    # --------------------------------------------------
    def test_9_praise_to_happy(self):
        engine = EmotionEngine(db=self.db)
        res = engine.process_turn("Dheepthi nee super di")
        self.assertEqual(res["stimulus"], "praise")
        self.assertEqual(res["new_mood"], "happy")
        self.assertGreater(res["valence"], 0.60)

    # --------------------------------------------------
    # 10. Neutral emotional decay
    # --------------------------------------------------
    def test_10_neutral_emotional_decay(self):
        engine = EmotionEngine(db=self.db)
        # Put into hurt state
        engine.process_turn("Dheepthi nee useless")
        self.assertIn(engine.current_mood, ("hurt", "annoyed"))

        # Neutral turns
        engine.process_turn("What is the time?")
        engine.process_turn("Tell me about Python")
        # After 2 neutral turns, extreme mood should decay to neutral
        self.assertEqual(engine.current_mood, "neutral")

    # --------------------------------------------------
    # 11. False-positive insult protection
    # --------------------------------------------------
    def test_11_false_positive_insult_protection(self):
        engine = EmotionEngine(db=self.db)
        # Utterance mentions 'useless', but directed at laptop, NOT Dheepthi
        stimulus, _, _ = engine.classify_stimulus("This laptop is useless")
        self.assertNotEqual(stimulus, "insult")
        # Ensure mood does not become hurt
        res = engine.process_turn("This laptop is useless")
        self.assertNotIn(res["new_mood"], ("hurt", "annoyed"))

    # --------------------------------------------------
    # 12. Memory retrieval
    # --------------------------------------------------
    def test_12_memory_retrieval(self):
        try:
            mm = MemoryManager(db=self.db)
            mm.set_profile_fact("user_name", "Naresh")
            mm.set_profile_fact("favorite_music", "Anirudh")
            ctx = mm.get_compact_memory_context()
            self.assertTrue(any("Naresh" in b for b in ctx["profile_bullets"]))
            self.assertTrue(any("Anirudh" in b for b in ctx["profile_bullets"]))
        finally:
            self.db.delete_user_context("user_name")
            self.db.delete_user_context("preferred_user_name")
            self.db.delete_user_context("preferred_user_name_source")
            self.db.delete_user_context("use_preferred_name")

    # --------------------------------------------------
    # 13. Context builder
    # --------------------------------------------------
    def test_13_context_builder(self):
        engine = EmotionEngine(db=self.db)
        mm = MemoryManager(db=self.db)
        block = PersonalityContextBuilder.build_context_block(engine, mm)
        self.assertIn("ACTIVE CONTEXT, EMOTIONAL STATE & MEMORY", block)
        self.assertIn("CRITICAL BEHAVIOR RULES", block)
        self.assertIn("NEVER refuse", block)
        # Budget check: < 2000 chars (~400 tokens max, target ~250-300)
        self.assertLess(len(block), 2000)

    # --------------------------------------------------
    # 14. Gemini prompt context injection
    # --------------------------------------------------
    def test_14_gemini_prompt_context_injection(self):
        client = GeminiClient()
        live_prompt = client.live_system_prompt()
        self.assertIn("ACTIVE CONTEXT, EMOTIONAL STATE & MEMORY", live_prompt)
        text_prompt = client.build_prompt("Hello Dheepthi")
        self.assertIn("ACTIVE CONTEXT, EMOTIONAL STATE & MEMORY", text_prompt)

    # --------------------------------------------------
    # 15. Emotion must not alter ACTION command
    # --------------------------------------------------
    def test_15_emotion_must_not_alter_action_command(self):
        # Even if Dheepthi is hurt, ACTION parsing remains strictly functional
        engine = EmotionEngine(db=self.db)
        engine.process_turn("Dheepthi nee useless")
        self.assertIn(engine.current_mood, ("hurt", "annoyed"))

        # Output with action tag while hurt
        assistant_output = "Seri da un mela kovama irundhalum <ACTION>open chrome</ACTION> panren."
        action = SemanticCommandPlanner.extract_action_command(assistant_output)
        self.assertEqual(action, "open chrome")

    # --------------------------------------------------
    # 16. Existing ACTION routing regression
    # --------------------------------------------------
    def test_16_existing_action_routing_regression(self):
        # Test standard tags
        test_cases = [
            ("<ACTION>open chrome</ACTION>", "open chrome"),
            ("<ACTION>close notepad</ACTION>", "close notepad"),
            ("Sure! <ACTION>play jailer song</ACTION>", "play jailer song"),
        ]
        for raw, expected in test_cases:
            self.assertEqual(SemanticCommandPlanner.extract_action_command(raw), expected)

    # --------------------------------------------------
    # 17. Existing conversation/no-ACTION regression
    # --------------------------------------------------
    def test_17_existing_conversation_no_action_regression(self):
        conv_outputs = [
            "Hello nanba! Epdi irukinga?",
            "Black holes are regions of spacetime where gravity is so strong that nothing can escape.",
            "Enna da panra? Summa dhaan iruken.",
        ]
        for raw in conv_outputs:
            self.assertIsNone(SemanticCommandPlanner.extract_action_command(raw))

    # --------------------------------------------------
    # 18. Multi-turn simulation
    # --------------------------------------------------
    def test_18_multi_turn_simulation(self):
        engine = EmotionEngine(db=self.db)
        mm = MemoryManager(db=self.db)

        # Turn 1: Insult
        t1 = engine.process_turn("Dheepthi nee romba useless da")
        self.assertIn(t1["new_mood"], ("hurt", "annoyed"))
        mm.save_turn("Dheepthi nee romba useless da", "Seri da... enna mistake pannenu sollu.")

        # Turn 2: Apology
        t2 = engine.process_turn("Sorry Dheepthi")
        self.assertIn(t2["new_mood"], ("neutral", "playful", "happy"))
        mm.save_turn("Sorry Dheepthi", "Paravala da vidu.")

        # Turn 3: Action command
        action_output = "Sure! <ACTION>open notepad</ACTION>"
        action = SemanticCommandPlanner.extract_action_command(action_output)
        self.assertEqual(action, "open notepad")
        mm.save_turn("Open Notepad", action_output, intent="desktop_action", target="notepad")

        # Turn 4: Fatigue
        t4 = engine.process_turn("Dheepthi naan tired ah iruken")
        self.assertEqual(t4["new_mood"], "caring")
        self.assertIn("caring", engine.get_tone_directive().lower())
        mm.save_turn("Dheepthi naan tired ah iruken", "Acho da, take rest.")

    # --------------------------------------------------
    # 19. Restart simulation
    # --------------------------------------------------
    def test_19_restart_simulation(self):
        try:
            # Session A: Persist user context and state
            mm_a = MemoryManager(db=self.db)
            mm_a.set_profile_fact("user_name", "TestUser")
            mm_a.add_episode("Completed project demo", importance=4)
            engine_a = EmotionEngine(db=self.db)
            engine_a.process_turn("Dheepthi nee super di")
            self.assertEqual(engine_a.current_mood, "happy")

            # Session B: Simulate complete application restart by instantiating new objects
            db_b = DatabaseManager()
            mm_b = MemoryManager(db=db_b)
            engine_b = EmotionEngine(db=db_b)

            # Verify recovered data
            self.assertEqual(mm_b.get_profile_fact("user_name"), "TestUser")
            episodes_b = mm_b.get_salient_episodes()
            self.assertTrue(any("Completed project demo" in ep for ep in episodes_b))
            self.assertEqual(engine_b.current_mood, "happy")
            self.assertGreater(engine_b.valence, 0.60)
        finally:
            # Clean up test keys so live database is not polluted
            self.db.delete_user_context("user_name")
            self.db.delete_user_context("preferred_user_name")
            self.db.delete_user_context("preferred_user_name_source")
            self.db.delete_user_context("use_preferred_name")

    @classmethod
    def tearDownClass(cls):
        # Restore canonical identity so permanent database remains valid after test runs
        mm = MemoryManager(db=cls.db)
        mm.ensure_canonical_identity()


if __name__ == "__main__":
    unittest.main()
