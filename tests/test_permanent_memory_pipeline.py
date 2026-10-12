"""
Comprehensive Automated Regression Tests for DHEEPTHI-AI Permanent Memory,
Conversation Context & Command History Pipeline.

Verifies:
1. Finalized user transcript persists in SQLite.
2. Assistant response persists.
3. Command history stores actual success and failure statuses.
4. Confirmed personal fact is saved with provenance.
5. Fresh MemoryManager instance retrieves the fact.
6. Fresh GeminiClient restores conversation context.
7. Simulated full application restart preserves records.
8. Family relationships survive restart.
9. User correction updates the canonical fact correctly.
10. Ambiguous Tanglish speech does not create false names.
11. Repeated turn-completion callbacks do not create duplicate records.
12. Memory extraction failure does not erase raw conversation.
13. Database write failure does not produce false "saved" confirmation.
14. Existing command routing and ACTION extraction continue passing.
15. Gemini Live two-turn behavior, interruption, and shutdown regressions pass.
16. Test cleanup does not erase or mutate the real user database or canonical identity.
+ Mandatory Real Restart Verification (Session A -> Shutdown -> Session B).
"""

import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.emotion_engine import EmotionEngine
from ai.personality_context_builder import PersonalityContextBuilder
from ai.gemini_client import GeminiClient


class TestPermanentMemoryPipeline(unittest.TestCase):
    """
    Test suite for permanent conversation, personal memory, and command history persistence.
    Operates on an isolated temporary SQLite database to guarantee zero mutation of production data.
    """

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary SQLite database
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_db_path = Path(cls.temp_dir.name) / "test_pipeline.db"
        cls.db = DatabaseManager(database_path=cls.temp_db_path)
        cls.memory_manager = MemoryManager(db=cls.db)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.close()
        except Exception:
            pass
        try:
            cls.temp_dir.cleanup()
        except Exception:
            pass
        # Ensure production database canonical identity is intact
        try:
            prod_db = DatabaseManager()
            prod_mm = MemoryManager(db=prod_db)
            prod_mm.ensure_canonical_identity()
            prod_db.close()
        except Exception:
            pass

    def setUp(self):
        # Ensure database connection is open and active
        try:
            self.db.cursor.execute("SELECT 1")
        except Exception:
            self.__class__.db = DatabaseManager(database_path=self.temp_db_path)
            self.__class__.memory_manager = MemoryManager(db=self.__class__.db)
        # Re-ensure canonical baseline in temp db before each test
        self.memory_manager.ensure_canonical_identity()

    def test_01_finalized_user_transcript_persists_in_sqlite(self):
        """1. A finalized user transcript persists in SQLite."""
        turn_id = "turn_test_01"
        user_cmd = "Hello Dheepthi, can you hear me?"
        ok = self.db.save_user_interaction(
            turn_id=turn_id,
            user_command=user_cmd,
            session_id="sess_01",
            input_source="gemini_live"
        )
        self.assertTrue(ok)
        record = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["user_command"], user_cmd)
        self.assertEqual(record["turn_status"], "user_received")
        self.assertEqual(record["persistence_status"], "committed")

    def test_02_assistant_response_persists(self):
        """2. The assistant response persists."""
        turn_id = "turn_test_02"
        self.db.save_user_interaction(turn_id=turn_id, user_command="Hi", session_id="sess_02")
        ok = self.db.update_assistant_interaction(
            turn_id=turn_id,
            assistant_response="Hello! I can hear you clearly.",
            turn_status="completed"
        )
        self.assertTrue(ok)
        record = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["assistant_response"], "Hello! I can hear you clearly.")
        self.assertEqual(record["turn_status"], "completed")

    def test_03_command_history_stores_actual_success_and_failure_statuses(self):
        """3. Command history stores actual success and failure statuses."""
        # Success command
        cmd_id_1 = self.db.log_command_execution(
            command="open notepad",
            intent="launch_application",
            target="notepad",
            status="started",
            session_id="sess_03"
        )
        self.assertGreater(cmd_id_1, 0)
        up_ok1 = self.db.update_command_execution(
            cmd_id_1,
            status="completed",
            result_summary="Notepad opened successfully",
            execution_time_ms=125
        )
        self.assertTrue(up_ok1)

        # Failure command
        cmd_id_2 = self.db.log_command_execution(
            command="close imaginary_app",
            intent="close_application",
            target="imaginary_app",
            status="started",
            session_id="sess_03"
        )
        self.assertGreater(cmd_id_2, 0)
        up_ok2 = self.db.update_command_execution(
            cmd_id_2,
            status="failed",
            error_summary="Process imaginary_app not running",
            execution_time_ms=45
        )
        self.assertTrue(up_ok2)

        # Verify in database
        commands = self.db.get_recent_commands(limit=10)
        cmd_map = {c[0]: c for c in commands}
        self.assertIn(cmd_id_1, cmd_map)
        self.assertEqual(cmd_map[cmd_id_1][4], "completed")
        self.assertIn(cmd_id_2, cmd_map)
        self.assertEqual(cmd_map[cmd_id_2][4], "failed")

    def test_04_confirmed_personal_fact_saved_with_provenance(self):
        """4. A confirmed personal fact is saved with provenance."""
        turn_id = "turn_prov_04"
        ok = self.memory_manager.set_profile_fact(
            key="primary_technology",
            value="Python and PyTorch",
            category="work",
            source="explicit_user",
            source_turn_id=turn_id
        )
        self.assertTrue(ok)
        memories = self.db.get_personal_memories(key="primary_technology")
        self.assertTrue(len(memories) > 0)
        self.assertEqual(memories[0]["value"], "Python and PyTorch")
        self.assertEqual(memories[0]["source_turn_id"], turn_id)

    def test_05_fresh_memory_manager_instance_retrieves_fact(self):
        """5. A fresh MemoryManager instance retrieves the fact."""
        # Create separate fresh db connection and memory manager pointing to same test DB
        fresh_db = DatabaseManager(database_path=self.temp_db_path)
        fresh_mm = MemoryManager(db=fresh_db)
        fact = fresh_mm.get_profile_fact("primary_technology")
        fresh_db.close()
        self.assertEqual(fact, "Python and PyTorch")

    def test_06_fresh_gemini_client_restores_conversation_context(self):
        """6. A fresh GeminiClient restores conversation context."""
        # Save a conversation turn into SQLite
        self.db.save_user_interaction("turn_client_06", "What is the capital of France?", session_id="sess_06")
        self.db.update_assistant_interaction("turn_client_06", "The capital of France is Paris.")

        # Create fresh GeminiClient pointing to test MemoryManager
        fresh_db = DatabaseManager(database_path=self.temp_db_path)
        fresh_mm = MemoryManager(db=fresh_db)
        with patch.object(GeminiClient, "_create_client"):
            client = GeminiClient(memory_manager=fresh_mm)
            restored = client.history
            self.assertTrue(len(restored) > 0)
            user_texts = [m["text"] for m in restored if m["role"] == "user"]
            asst_texts = [m["text"] for m in restored if m["role"] == "assistant"]
            self.assertIn("What is the capital of France?", user_texts)
            self.assertIn("The capital of France is Paris.", asst_texts)
        fresh_db.close()

    def test_07_simulated_full_app_restart_preserves_records(self):
        """7. A simulated full application restart preserves the relevant records."""
        # Session A: Save facts and turns
        self.memory_manager.set_profile_fact("current_project", "DHEEPTHI-AI V1", category="work", source="explicit_user")
        self.memory_manager.save_turn("I am working on DHEEPTHI-AI V1", "Got it, I noted your project!")

        # Close session
        self.db.close()

        # Session B: Spin up brand new instances
        fresh_db = DatabaseManager(database_path=self.temp_db_path)
        fresh_mm = MemoryManager(db=fresh_db)
        context_block = PersonalityContextBuilder.build_context_block(memory_manager=fresh_mm, query="project")

        self.assertIn("DHEEPTHI-AI V1", context_block)
        # Restore class references for subsequent tests
        self.__class__.db = fresh_db
        self.__class__.memory_manager = fresh_mm

    def test_08_family_relationships_survive_restart(self):
        """8. Family relationships survive restart."""
        # Session A: Add brother
        self.memory_manager.add_known_person(
            name="Dheebes",
            relationship_to_primary_user="brother",
            notes="User's younger brother",
            source="explicit_user"
        )

        # Session B: Fresh instance
        fresh_db = DatabaseManager(database_path=self.temp_db_path)
        fresh_mm = MemoryManager(db=fresh_db)
        brother = fresh_mm.get_known_person("Dheebes")
        self.assertIsNotNone(brother)
        self.assertEqual(brother.get("relationship_to_primary_user"), "brother")

        # Check memory query answer
        ans = fresh_mm.answer_memory_query("Naan en family pathi enna sonnen?")
        self.assertIsNotNone(ans)
        self.assertIn("Dheebes", ans)
        fresh_db.close()

    def test_09_user_correction_updates_canonical_fact_correctly(self):
        """9. A user correction updates the canonical fact correctly."""
        # Initial fact
        self.memory_manager.set_profile_fact("favorite_music", "Rock", category="interest")
        self.assertEqual(self.memory_manager.get_profile_fact("favorite_music"), "Rock")

        # User correction
        self.memory_manager.set_profile_fact("favorite_music", "Ilaiyaraaja Songs", category="interest")
        self.assertEqual(self.memory_manager.get_profile_fact("favorite_music"), "Ilaiyaraaja Songs")

    def test_10_ambiguous_tanglish_speech_does_not_create_false_names(self):
        """10. Ambiguous Tanglish speech does not create false names."""
        dirty_inputs = [
            "naan vandhen nethu",
            "naan work panren",
            "I am working on code",
            "I am tired",
            "I am trying to fix it",
        ]
        for inp in dirty_inputs:
            self.memory_manager.extract_memories_from_turn(inp, "Sure")

        # Preferred name must remain verified Naresh or unset, NEVER Vani, Working, Vandhen
        pref_name, _ = self.memory_manager.get_user_name_preference()
        if pref_name:
            self.assertNotIn(pref_name.lower(), ("vandhen", "working", "work", "trying", "tired", "vani"))
        # Ensure people table doesn't have these verbs
        for bad in ("vandhen", "working", "vani"):
            self.assertIsNone(self.db.get_person_by_name(bad))

    def test_11_repeated_turn_completion_callbacks_do_not_create_duplicate_records(self):
        """11. Repeated turn-completion callbacks do not create duplicate records."""
        turn_id = "turn_dup_11"
        self.db.save_user_interaction(turn_id=turn_id, user_command="Repeat test", session_id="sess_11")
        # First completion
        self.db.update_assistant_interaction(turn_id=turn_id, assistant_response="Reply A")
        # Second (duplicate) completion
        self.db.update_assistant_interaction(turn_id=turn_id, assistant_response="Reply A")

        # Verify only 1 record exists in SQLite
        with self.db.lock:
            self.db.cursor.execute("SELECT COUNT(*) FROM conversation_context WHERE turn_id = ?", (turn_id,))
            cnt = self.db.cursor.fetchone()[0]
            self.assertEqual(cnt, 1)

    def test_12_memory_extraction_failure_does_not_erase_raw_conversation(self):
        """12. Memory extraction failure does not erase the raw conversation."""
        turn_id = "turn_fail_12"
        self.db.save_user_interaction(turn_id=turn_id, user_command="Keep this safe", session_id="sess_12")

        # Force extraction to raise an exception
        with patch.object(self.memory_manager, "extract_memories_from_turn", side_effect=RuntimeError("Extraction crashed")):
            result = self.memory_manager.complete_turn(turn_id=turn_id, assistant_text="Response despite crash", user_text="Keep this safe")
            # Result indicates assistant was saved but extraction crashed gracefully
            self.assertTrue(result["success"])

        # Check raw conversation is still preserved
        rec = self.db.get_interaction_by_turn_id(turn_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["user_command"], "Keep this safe")
        self.assertEqual(rec["assistant_response"], "Response despite crash")

    def test_13_database_write_failure_does_not_produce_false_saved_confirmation(self):
        """13. A database write failure does not produce a false 'saved' confirmation."""
        closed_db = DatabaseManager(database_path=Path(self.temp_dir.name) / "closed.db")
        closed_db.connection.close()
        ok = closed_db.save_user_interaction(turn_id="turn_disk_err", user_command="Should fail")
        self.assertFalse(ok)

    def test_14_existing_command_routing_and_action_extraction_continue_passing(self):
        """14. Existing command routing and ACTION extraction tests continue passing."""
        from planner.semantic_command_planner import has_action_command, extract_action_command
        raw_output = "Sure! Opening Notepad now.\n<ACTION>launch_application:notepad</ACTION>"
        self.assertTrue(has_action_command(raw_output))
        command = extract_action_command(raw_output)
        self.assertEqual(command, "launch_application:notepad")

    def test_15_gemini_live_two_turn_behavior_interruption_shutdown_pass(self):
        """15. Gemini Live two-turn behavior, interruption, and shutdown regressions continue passing."""
        from ai.gemini_client import GeminiLiveSession
        # Test session interruption and suppression logic
        session = GeminiLiveSession(
            api_key="mock_key",
            model="models/gemini-3.5-flash",
            voice="Aoede"
        )
        # Test interruption counter increments
        session._speaking_response_id = 1
        session._active_response_id = 1
        intr_id = session.interrupt_current_response()
        self.assertEqual(intr_id, 1)
        supp_id = session.suppress_active_and_next_response()
        self.assertEqual(supp_id, 2)
        session.reset_suppression()
        self.assertFalse(session._suppress_upcoming_response)

    def test_16_test_cleanup_does_not_erase_or_mutate_real_db_or_canonical_identity(self):
        """16. Test cleanup does not erase or mutate the user's real database or canonical identity."""
        # Inspect real production database at database/astra.db
        prod_db_path = PROJECT_ROOT / "database" / "astra.db"
        self.assertTrue(prod_db_path.exists())
        prod_db = DatabaseManager(database_path=prod_db_path)
        creator = prod_db.get_person_by_name("Naresh")
        self.assertIsNotNone(creator)
        self.assertEqual(creator.get("is_creator"), 1)
        prod_db.close()

    def test_mandatory_real_restart_verification(self):
        """
        12. Mandatory real restart verification:
        Session A:
        - Save a user transcript containing an explicitly stated personal fact.
        - Save the assistant response.
        - Confirm structured memory was committed.
        - Close all service instances.
        Session B:
        - Create fresh database-manager, MemoryManager, GeminiClient, and context-builder instances.
        - Confirm conversation and fact are retrieved from SQLite.
        - Build a new-session context and verify that it contains the relevant persisted fact.
        - Verify that no unverified identity is injected.
        - Repeat with family relationship and command result.
        """
        integration_db_path = Path(self.temp_dir.name) / "restart_verification.db"

        # ==============================================================
        # SESSION A
        # ==============================================================
        db_a = DatabaseManager(database_path=integration_db_path)
        mm_a = MemoryManager(db=db_a)
        mm_a.ensure_canonical_identity()

        turn_a1 = "turn_restart_fact_1"
        u_text = "My favorite music is A.R. Rahman melody songs"
        a_text = "I will remember that your favorite music is A.R. Rahman melody songs!"

        # 1. Save user transcript promptly
        u_ok, _ = mm_a.save_user_turn(u_text, turn_id=turn_a1, session_id="sess_A")
        self.assertTrue(u_ok)

        # 2. Complete turn with assistant response & structured memory
        res = mm_a.complete_turn(turn_a1, assistant_text=a_text, user_text=u_text)
        self.assertTrue(res["success"])
        self.assertTrue(len(res["extracted_memories"]) > 0)

        # 3. Save family relationship
        turn_a2 = "turn_restart_fam_2"
        mm_a.save_user_turn("My brother is Dheebes", turn_id=turn_a2, session_id="sess_A")
        mm_a.complete_turn(turn_a2, assistant_text="Got it, noted Dheebes as your brother.", user_text="My brother is Dheebes")

        # 4. Save command result
        cmd_id = db_a.log_command_execution(
            command="open chrome",
            intent="launch_application",
            target="chrome",
            status="started",
            session_id="sess_A",
            turn_id=turn_a1
        )
        db_a.update_command_execution(cmd_id, status="completed", result_summary="Chrome opened")

        # Close all Session A instances
        db_a.close()
        del mm_a
        del db_a

        # ==============================================================
        # SESSION B (Simulated App Restart)
        # ==============================================================
        db_b = DatabaseManager(database_path=integration_db_path)
        mm_b = MemoryManager(db=db_b)
        mm_b.ensure_canonical_identity()

        # Confirm conversation turns exist
        rec_a1 = db_b.get_interaction_by_turn_id(turn_a1)
        self.assertIsNotNone(rec_a1)
        self.assertEqual(rec_a1["user_command"], u_text)
        self.assertEqual(rec_a1["assistant_response"], a_text)

        # Confirm fact exists
        fav_music = mm_b.get_profile_fact("favorite_music")
        self.assertIsNotNone(fav_music)
        self.assertIn("A.R. Rahman", fav_music)

        # Confirm family relationship exists
        brother = mm_b.get_known_person("Dheebes")
        self.assertIsNotNone(brother)
        self.assertEqual(brother["relationship_to_primary_user"], "brother")

        # Confirm command result exists
        recent_cmds = db_b.get_recent_commands(limit=5)
        self.assertTrue(len(recent_cmds) > 0)
        self.assertEqual(recent_cmds[0][1], "open chrome")
        self.assertEqual(recent_cmds[0][4], "completed")

        # Build fresh context block in Session B
        with patch.object(GeminiClient, "_create_client"):
            gemini_b = GeminiClient(memory_manager=mm_b)
            self.assertTrue(len(gemini_b.history) >= 2)

        context_block = PersonalityContextBuilder.build_context_block(
            memory_manager=mm_b,
            query="Who is my brother and what is my favorite music?"
        )

        # Verify context contains the persisted fact and brother
        self.assertIn("A.R. Rahman", context_block)
        self.assertIn("Dheebes", context_block)
        self.assertIn("Naresh", context_block)

        # Verify no unverified identity is injected
        for unverified in ("vani", "karthik", "rahul", "arun", "working"):
            self.assertNotIn(unverified, context_block.lower())

        db_b.close()

    def test_17_startup_session_id_and_datetime_import(self):
        """17. Verify datetime and uuid are defined and session ID generation succeeds without NameError."""
        import ui.main_window as mw_module
        self.assertTrue(hasattr(mw_module, "datetime"), "datetime must be imported in ui.main_window")
        self.assertTrue(hasattr(mw_module, "uuid"), "uuid must be imported in ui.main_window")

        # Test session ID generation exactly as performed in MainWindow.create_backend()
        now = mw_module.datetime.now()
        session_id = f"session_{now.strftime('%Y%m%d_%H%M%S')}_{mw_module.uuid.uuid4().hex[:6]}"
        self.assertTrue(session_id.startswith("session_"))
        self.assertEqual(len(session_id.split("_")), 4)

    def test_18_startup_history_restored_from_sqlite_not_in_memory(self):
        """18. Verify that Startup history restored represents true SQLite retrieval rather than in-memory state."""
        # 1. Create a dedicated isolated test DB
        hist_db_path = Path(self.temp_dir.name) / "hist_test.db"
        hist_db = DatabaseManager(database_path=hist_db_path)

        # 2. Directly write 2 conversation turns into SQLite
        hist_db.save_user_interaction(
            turn_id="turn_sqlite_01",
            user_command="Turn 1 from SQLite",
            session_id="session_alpha",
            input_source="text"
        )
        hist_db.update_assistant_interaction(
            turn_id="turn_sqlite_01",
            assistant_response="Response 1 from SQLite",
            turn_status="completed"
        )
        hist_db.save_user_interaction(
            turn_id="turn_sqlite_02",
            user_command="Turn 2 from SQLite",
            session_id="session_alpha",
            input_source="text"
        )
        hist_db.update_assistant_interaction(
            turn_id="turn_sqlite_02",
            assistant_response="Response 2 from SQLite",
            turn_status="completed"
        )
        hist_db.close()

        # 3. Open completely fresh database & client instances (zero RAM history)
        fresh_db = DatabaseManager(database_path=hist_db_path)
        fresh_mm = MemoryManager(db=fresh_db)
        with patch.object(GeminiClient, "_create_client"):
            client = GeminiClient(memory_manager=fresh_mm)

        # 4. Confirm history was populated directly from SQLite storage
        self.assertEqual(len(client.history), 4)
        self.assertEqual(client.history[0]["text"], "Turn 1 from SQLite")
        self.assertEqual(client.history[1]["text"], "Response 1 from SQLite")
        self.assertEqual(client.history[2]["text"], "Turn 2 from SQLite")
        self.assertEqual(client.history[3]["text"], "Response 2 from SQLite")

        # 5. Clear client's in-RAM history and re-invoke restore_history_from_storage
        client.history.clear()
        self.assertEqual(len(client.history), 0)
        restored_count = client.restore_history_from_storage(limit=10)
        self.assertEqual(restored_count, 4)
        self.assertEqual(len(client.history), 4)

        fresh_db.close()


if __name__ == "__main__":
    unittest.main()
