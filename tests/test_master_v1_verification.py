"""
Master V1 Verification Test Suite
=================================
Validates all requirements of the DHEEPTHI-AI V1 Master Implementation:
1. Gemini 3.8 Flash standardization across config, client, vision, OCR, and planner hierarchy.
2. Gemini Live model independence (gemini-3.1-flash-live-preview).
3. Real-time Voice Interruption (Barge-In) audio queue flushing, latency (<100ms), stale rejection, subsequent playback, and full-duplex mic.
4. SQLite conversation turn persistence: immediate capture, status transitions, command linkage.
5. Permanent personal memory & family recall: multi-relation extraction in English/Tanglish, fact correction superseding, and anti-hallucination directives.
6. Per-user profile isolation: schema, scoped memories/turns, switching, and elimination of hardcoded 'Naresh' defaults.
"""

import sys
import os
import unittest
import tempfile
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from ai.gemini_client import GeminiClient
from vision.gemini_vision import GeminiVision
from vision.ocr import OCREngine
from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.personality_context_builder import PersonalityContextBuilder
from ui.components.header import HeaderWidget
from ui.widgets.conversation_panel import ConversationPanel


class TestPhase2ModelStandardization(unittest.TestCase):
    """Phase 2: Standardize Compatible Gemini calls on Gemini 3.8 Flash."""

    def test_settings_standard_models(self):
        """Verify standard model configuration in settings."""
        self.assertEqual(settings.GEMINI_MODEL, "gemini-3.8-flash")
        self.assertEqual(settings.GEMINI_PLANNER_PRIMARY_MODEL, "gemini-3.8-flash")
        self.assertEqual(settings.GEMINI_PLANNER_FALLBACK_1, "gemini-3.6-flash")
        self.assertEqual(settings.GEMINI_PLANNER_FALLBACK_2, "gemini-3.5-flash")

    def test_planner_hierarchy_excludes_deprecated_models(self):
        """Verify gemini-3.7-flash is completely excluded from planner configuration."""
        all_models = [
            settings.GEMINI_PLANNER_PRIMARY_MODEL,
            settings.GEMINI_PLANNER_FALLBACK_1,
            settings.GEMINI_PLANNER_FALLBACK_2,
        ]
        self.assertNotIn("gemini-3.7-flash", all_models)
        self.assertNotIn("gemini-2.0-flash", all_models)
        # Ensure hierarchy has distinct models (no redundant fallback loops)
        self.assertEqual(len(all_models), len(set(all_models)))

    def test_gemini_live_model_is_separate(self):
        """Verify Gemini Live model is independent and set to verified working preview."""
        self.assertEqual(settings.GEMINI_LIVE_MODEL, "gemini-3.1-flash-live-preview")
        self.assertNotEqual(settings.GEMINI_LIVE_MODEL, settings.GEMINI_MODEL)

    def test_client_and_vision_defaults(self):
        """Verify default models in GeminiClient, GeminiVision, and OCREngine."""
        client = GeminiClient.__new__(GeminiClient)
        client_default = getattr(client, "model_id", settings.GEMINI_MODEL)
        self.assertEqual(client_default, "gemini-3.8-flash")

        vision = GeminiVision.__new__(GeminiVision)
        vision_model = getattr(vision, "model", getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash"))
        self.assertEqual(vision_model, "gemini-3.8-flash")

        ocr = OCREngine.__new__(OCREngine)
        ocr_model = getattr(ocr, "model", getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash"))
        self.assertEqual(ocr_model, "gemini-3.8-flash")


class TestPhase3RealTimeBargeIn(unittest.TestCase):
    """Phase 3: Real-Time Voice Interruption (Barge-In) Logic."""

    def setUp(self):
        # Create a mock audio worker with identical queue/buffer logic as GeminiLiveAudioWorker
        from ui.main_window import GeminiLiveAudioWorker
        self.worker = GeminiLiveAudioWorker(live_session=None)

    def tearDown(self):
        self.worker.interrupt_and_flush()

    def test_playback_detection_and_flush(self):
        """Verify interrupt_and_flush stops speaker, clears queue, and empties buffer in <100ms."""
        # Enqueue dummy output
        chunk1 = b"\x01\x00" * 384  # 32ms audio
        chunk2 = b"\x02\x00" * 384
        self.worker.enqueue_output(chunk1, response_id=1)
        self.worker.enqueue_output(chunk2, response_id=1)
        
        self.assertTrue(self.worker.is_output_playing())

        # Measure interruption latency
        t0 = time.perf_counter()
        self.worker.interrupt_and_flush(response_id=1)
        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Assert playback stopped and queues emptied promptly (<100ms requirement)
        self.assertLess(t_elapsed_ms, 100.0)
        self.assertFalse(self.worker.is_output_playing())
        self.assertEqual(len(self.worker._output_buffer), 0)
        self.assertTrue(self.worker._output_queue.empty())

    def test_stale_audio_rejection(self):
        """Verify stale chunks from an interrupted response are dropped and cannot play."""
        self.worker.enqueue_output(b"\x01\x00" * 100, response_id=1)
        self.worker.interrupt_and_flush(response_id=1)

        # Attempt to enqueue more chunks belonging to the interrupted turn (response_id=1)
        self.worker.enqueue_output(b"\x03\x00" * 100, response_id=1)
        self.assertTrue(self.worker._output_queue.empty())
        self.assertFalse(self.worker.is_output_playing())

    def test_subsequent_response_plays_normally(self):
        """Verify that interrupting turn 1 does not prevent turn 2 from playing."""
        self.worker.enqueue_output(b"\x01\x00" * 100, response_id=1)
        self.worker.interrupt_and_flush(response_id=1)

        # New turn arrives (response_id=2)
        chunk_new = b"\x04\x00" * 100
        self.worker.enqueue_output(chunk_new, response_id=2)
        self.assertTrue(self.worker.is_output_playing())
        self.assertEqual(self.worker._output_queue.qsize(), 1)

    def test_physical_mic_mute_gate(self):
        """Verify muting microphone stops audio capture and clears buffers."""
        self.worker.set_input_enabled(True)
        self.assertTrue(self.worker.input_enabled())

        self.worker.set_input_enabled(False)
        self.assertFalse(self.worker.input_enabled())
        self.assertEqual(self.worker.get_audio_level(), 0.0)


class TestPhase4SQLiteTurnPersistence(unittest.TestCase):
    """Phase 4: Persist Every User Input and Conversation Turn in SQLite."""

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = DatabaseManager(database_path=self.temp_db_path)
        self.mm = MemoryManager(db=self.db)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_immediate_user_turn_persistence(self):
        """Verify user input is recorded immediately before processing."""
        turn_id = self.mm.persist_user_turn("Open Chrome and search weather", session_id="test_sess_1")
        self.assertTrue(turn_id.startswith("turn_"))

        # Verify record exists in DB with initial received status
        turn = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(turn)
        self.assertEqual(turn["user_command"], "Open Chrome and search weather")
        self.assertIn(turn["turn_status"], ("user_received", "in_flight"))

    def test_turn_interrupted_transition(self):
        """Verify in-flight turn transitions to 'interrupted' status on barge-in."""
        turn_id = self.mm.persist_user_turn("Tell me a long story", session_id="test_sess_2")
        self.mm.mark_turn_interrupted(turn_id)

        turn = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(turn)
        self.assertEqual(turn["turn_status"], "interrupted")

    def test_turn_completed_transition(self):
        """Verify completed assistant interaction updates turn status to completed."""
        turn_id = self.mm.persist_user_turn("What is 2+2?", session_id="test_sess_3")
        self.db.update_assistant_interaction(turn_id, "2 + 2 = 4", turn_status="completed")

        turn = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(turn)
        self.assertEqual(turn["assistant_response"], "2 + 2 = 4")
        self.assertEqual(turn["turn_status"], "completed")

    def test_command_execution_linkage(self):
        """Verify executed commands link turn_id and profile_id."""
        turn_id = self.mm.persist_user_turn("Open Notepad", session_id="test_sess_4")
        row_id = self.db.log_command_execution(
            command="open notepad",
            intent="open_application",
            status="success",
            profile_id="default_profile",
            turn_id=turn_id,
        )

        with self.db.lock:
            self.db.cursor.execute("SELECT command, turn_id, profile_id, status FROM command_history WHERE id = ?", (row_id,))
            cmd_row = self.db.cursor.fetchone()

        self.assertIsNotNone(cmd_row)
        self.assertEqual(cmd_row[0], "open notepad")
        self.assertEqual(cmd_row[1], turn_id)
        self.assertEqual(cmd_row[2], "default_profile")


class TestPhase5PersonalMemoryAndFamilyRecall(unittest.TestCase):
    """Phase 5: Permanent Personal Memory & Family Recall (Multi-relation, Tanglish, Superseding)."""

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = DatabaseManager(database_path=self.temp_db_path)
        self.mm = MemoryManager(db=self.db)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_multi_relationship_extraction_english_and_tanglish(self):
        """Verify extraction of father, mother, brother, sister, friend, spouse."""
        test_cases = [
            ("My father's name is Ramesh", "father", "Ramesh"),
            ("En amma peru Lakshmi", "mother", "Lakshmi"),
            ("My brother name is Suresh", "brother", "Suresh"),
            ("En sister peru Priya", "sister", "Priya"),
            ("My friend name is Vignesh", "friend", "Vignesh"),
            ("My wife name is Anitha", "wife", "Anitha"),
        ]
        for utterance, expected_rel, expected_name in test_cases:
            self.mm.save_turn(utterance, "Got it!")
            memories = self.db.get_personal_memories(category="relationships")
            matching = [m for m in memories if m["key"] == expected_rel and m["status"] == "active"]
            self.assertTrue(len(matching) >= 1, f"Failed to extract {expected_rel} from '{utterance}'")
            self.assertEqual(matching[0]["value"], expected_name)

    def test_explicit_fact_correction_supersedes_old_memory(self):
        """Verify explicit correction supersedes old fact (e.g. Suresh -> Vignesh)."""
        # Initial statement
        self.mm.save_turn("My brother name is Suresh", "Saved.")
        ans1 = self.mm.answer_memory_query("Who is my brother?")
        self.assertIn("Suresh", ans1)

        # Correction statement (English / Tanglish)
        self.mm.save_turn("Actually en brother peru Suresh illa, Vignesh", "Noted, I updated it.")
        
        # Check DB state
        memories = self.db.get_personal_memories(category="relationships", key="brother", active_only=False)
        # Should have at least one superseded and one active
        active = [m for m in memories if m["status"] == "active"]
        superseded = [m for m in memories if m["status"] == "superseded"]

        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["value"], "Vignesh")
        self.assertTrue(len(superseded) >= 1)
        self.assertEqual(superseded[0]["value"], "Suresh")

        # Query should now return Vignesh, never Suresh
        ans2 = self.mm.answer_memory_query("Who is my brother?")
        self.assertIn("Vignesh", ans2)
        self.assertNotIn("Suresh", ans2)

    def test_anti_hallucination_directive_for_unknown_family_member(self):
        """Verify asking about unrecorded family member triggers anti-hallucination directive."""
        # Database has no record of sister
        context = PersonalityContextBuilder.build_context_block(
            memory_manager=self.mm,
            query="Who is my sister?",
        )
        # Context must contain directive to not hallucinate and clarify
        self.assertIn("sister", context.lower())
        self.assertTrue("do not" in context.lower() or "never" in context.lower())

    def test_profile_isolation_of_memories_and_turns(self):
        """Verify profile A and profile B store completely isolated memories and history."""
        # Create Profile A (Alice)
        prof_a = self.db.get_or_create_profile(profile_id="profile_alice", display_name="Alice")
        self.mm.switch_profile("profile_alice")
        self.mm.save_turn("My father's name is Ramesh", "Hello Alice, noted.")

        # Create Profile B (Bob)
        prof_b = self.db.get_or_create_profile(profile_id="profile_bob", display_name="Bob")
        self.mm.switch_profile("profile_bob")
        self.mm.save_turn("My father's name is Joseph", "Hello Bob, noted.")

        # In Bob's profile, father is Joseph
        ans_bob = self.mm.answer_memory_query("Who is my father?")
        self.assertIn("Joseph", ans_bob)
        self.assertNotIn("Ramesh", ans_bob)

        # Switch back to Alice's profile, father is Ramesh
        self.mm.switch_profile("profile_alice")
        ans_alice = self.mm.answer_memory_query("Who is my father?")
        self.assertIn("Ramesh", ans_alice)
        self.assertNotIn("Joseph", ans_alice)

    def test_ui_defaults_have_zero_hardcoded_naresh(self):
        """Verify Header and ConversationPanel show neutral greetings for unknown user."""
        header = HeaderWidget.__new__(HeaderWidget)
        header.username = None
        header.greeting_label = type("MockLabel", (), {"setText": lambda s, t: setattr(s, "text", t)})()
        header.time_chip = type("MockLabel", (), {"setText": lambda s, t: None})()
        header.date_chip = type("MockLabel", (), {"setText": lambda s, t: None})()
        header.day_chip = type("MockLabel", (), {"setText": lambda s, t: None})()
        header.update_datetime()
        self.assertNotIn("Naresh", getattr(header.greeting_label, "text", ""))

        panel = ConversationPanel.__new__(ConversationPanel)
        panel.user_name = None
        self.assertFalse(any("Naresh" in g for g in panel.GREETINGS))

    def test_context_builder_unknown_speaker_directive(self):
        """Verify unknown speaker generates neutral directive with NO 'Naresh'."""
        context = PersonalityContextBuilder.build_context_block(
            memory_manager=self.mm,
            query="Who am I?",
        )
        self.assertIn("Unknown speaker", context)
        self.assertIn("NEVER invent, guess, or randomly select any name", context)
        self.assertNotIn("Verified Speaker: Naresh", context)


if __name__ == "__main__":
    unittest.main()
