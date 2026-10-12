"""
Test Suite: Gemini Live Persistent Memory & Education Recall Verification
DHEEPTHI-AI V1
Verification Identifier: GEMINI_LIVE_MEMORY_RECALL_20261011_R9V2

Verifies:
1. Extraction of college, degree, and academic year from natural spoken English/Tanglish:
   "Ok. Na MCA second year Sona College of Technology la padikiren. Ok va?"
2. Extraction from Tamil script:
   "நான் வந்துட்டு செகண்ட் இயர் இன் சோனா, சேலம். ஓகே."
3. Education query recall across English, Tanglish, and Tamil:
   - "Naan endha college-la padikkiren?"
   - "En course enna?"
   - "Naan endha year padikkiren?"
   - "Naan enna studies padikkiren?"
4. Department vs Degree handling:
   - Must NOT fabricate unrecorded department when user asks "Naan endha department?"
   - Distinguishes degree (MCA) from unrecorded department.
   - Accurately answers department when explicitly recorded.
5. Separation of user-name recall from creator identity:
   - "What is my name?" / "En peru enna?" answers directly with name without creator lecture.
   - "Who am I?" acknowledges creator relationship.
6. Gemini Live system prompt grounding & synchronization:
   - live_system_prompt() contains verified education and profile facts.
   - Context refresh incorporates newly committed memories without losing state.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.database_manager import DatabaseManager
from ai.memory_manager import MemoryManager
from ai.emotion_engine import EmotionEngine
from ai.personality_context_builder import PersonalityContextBuilder
from ai.gemini_client import GeminiClient


class TestGeminiLivePersistentMemory(unittest.TestCase):
    """
    Dedicated regression test suite verifying real Gemini Live persistent memory recall
    using an isolated temporary SQLite database and dedicated profile.
    """

    TEST_PROFILE_ID = "profile_live_recall_test_r9v2"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db_path = Path(self.temp_dir.name) / "test_live_recall.db"
        self.db = DatabaseManager(database_path=self.temp_db_path)
        self.db.active_profile_id = self.TEST_PROFILE_ID
        self.mm = MemoryManager(db=self.db, profile_id=self.TEST_PROFILE_ID)
        self.ee = EmotionEngine(db=self.db)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. Spoken Tanglish Education Extraction
    # -------------------------------------------------------------------------
    def test_01_spoken_tanglish_education_extraction(self):
        """
        Verify exact production turn:
        'Ok. Na MCA second year Sona College of Technology la padikiren. Ok va?'
        correctly extracts college, degree, and academic year without corruption.
        """
        turn_id = "turn_edu_prod_868"
        user_text = "Ok. Na MCA second year Sona College of Technology la padikiren. Ok va?"
        asst_text = "Noted! Neenga Sona College of Technology-la MCA second year padikiringa."

        self.mm.save_user_turn(user_text, turn_id=turn_id, session_id="sess_live_01", profile_id=self.TEST_PROFILE_ID)
        res = self.mm.complete_turn(turn_id, assistant_text=asst_text, user_text=user_text, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res["success"])

        col = self.mm.get_profile_fact("college")
        deg = self.mm.get_profile_fact("degree")
        yr = self.mm.get_profile_fact("academic_year")

        self.assertEqual(col, "Sona College of Technology")
        self.assertEqual(deg, "MCA")
        self.assertEqual(yr, "Second year")

        # Verify not corrupt: college must NOT end with 'la padikiren' or 'of Technology'
        self.assertNotIn("la padikiren", col)
        self.assertNotIn("Ok va", col)

    # -------------------------------------------------------------------------
    # 2. Tamil Script Education Extraction
    # -------------------------------------------------------------------------
    def test_02_tamil_script_education_extraction(self):
        """
        Verify Tamil script input:
        'நான் வந்துட்டு செகண்ட் இயர் இன் சோனா, சேலம். ஓகே.'
        extracts college and academic year.
        """
        turn_id = "turn_edu_tamil_865"
        user_text = "நான் வந்துட்டு செகண்ட் இயர் இன் சோனா, சேலம். ஓகே."
        asst_text = "Purinjidhu! Neenga Salem Sona-la second year padikiringa."

        self.mm.save_user_turn(user_text, turn_id=turn_id, session_id="sess_live_02", profile_id=self.TEST_PROFILE_ID)
        res = self.mm.complete_turn(turn_id, assistant_text=asst_text, user_text=user_text, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res["success"])

        yr = self.mm.get_profile_fact("academic_year")
        self.assertEqual(yr, "Second year")

        col = self.mm.get_profile_fact("college")
        self.assertIsNotNone(col)
        self.assertIn("சோனா", col)

    # -------------------------------------------------------------------------
    # 3. Targeted Education Recall Queries
    # -------------------------------------------------------------------------
    def test_03_education_recall_queries(self):
        """
        Populate verified education facts and verify targeted recall across all query phrasings:
        - 'Naan endha college-la padikkiren?'
        - 'En course enna?'
        - 'Naan endha year padikkiren?'
        - 'Naan enna studies padikkiren?'
        """
        self.mm.set_profile_fact("college", "Sona College of Technology", category="education")
        self.mm.set_profile_fact("degree", "MCA", category="education")
        self.mm.set_profile_fact("academic_year", "Second year", category="education")

        # College query
        ans_col = self.mm.answer_memory_query("Naan endha college-la padikkiren?")
        self.assertIsNotNone(ans_col)
        self.assertIn("Sona College of Technology", ans_col)

        # English college query
        ans_col_en = self.mm.answer_memory_query("Which college do I study in?")
        self.assertIsNotNone(ans_col_en)
        self.assertIn("Sona College of Technology", ans_col_en)

        # Course / Degree query
        ans_deg = self.mm.answer_memory_query("En course enna?")
        self.assertIsNotNone(ans_deg)
        self.assertIn("MCA", ans_deg)

        ans_deg_en = self.mm.answer_memory_query("What is my degree?")
        self.assertIsNotNone(ans_deg_en)
        self.assertIn("MCA", ans_deg_en)

        # Academic Year query
        ans_yr = self.mm.answer_memory_query("Naan endha year padikkiren?")
        self.assertIsNotNone(ans_yr)
        self.assertIn("Second year", ans_yr)

        ans_yr_en = self.mm.answer_memory_query("Which year am I studying in?")
        self.assertIsNotNone(ans_yr_en)
        self.assertIn("Second year", ans_yr_en)

        # General education / studies query
        ans_studies = self.mm.answer_memory_query("Naan enna studies padikkiren?")
        self.assertIsNotNone(ans_studies)
        self.assertIn("Sona College of Technology", ans_studies)
        self.assertIn("MCA", ans_studies)
        self.assertIn("Second year", ans_studies)

    # -------------------------------------------------------------------------
    # 4. Department vs Degree Handling (No Fabrication)
    # -------------------------------------------------------------------------
    def test_04_department_vs_degree_no_fabrication(self):
        """
        When department is NOT recorded:
        'Naan endha department?' must state that department is not stored,
        mention degree (MCA) if helpful, and NEVER fabricate a department!
        """
        self.mm.set_profile_fact("college", "Sona College of Technology", category="education")
        self.mm.set_profile_fact("degree", "MCA", category="education")
        self.mm.set_profile_fact("academic_year", "Second year", category="education")

        ans_dept = self.mm.answer_memory_query("Naan endha department?")
        self.assertIsNotNone(ans_dept)
        # Must clearly indicate department is not in memory
        self.assertIn("department pathi memory-la thaniya illa", ans_dept)
        # Must report the known degree
        self.assertIn("MCA", ans_dept)

        # Department + Year multi-query
        ans_dept_yr = self.mm.answer_memory_query("எந்த டிபார்ட்மென்ட், எந்த இயர்?")
        self.assertIsNotNone(ans_dept_yr)
        self.assertIn("Second year", ans_dept_yr)
        self.assertIn("MCA", ans_dept_yr)

        # Now when department IS recorded:
        self.mm.set_profile_fact("department", "Computer Applications", category="education")
        ans_dept_known = self.mm.answer_memory_query("Naan endha department?")
        self.assertIn("Computer Applications", ans_dept_known)

    # -------------------------------------------------------------------------
    # 5. Separation of User-Name Recall from Creator Identity
    # -------------------------------------------------------------------------
    def test_05_separate_user_name_from_creator_identity(self):
        """
        When user asks 'What is my name?' or 'En peru enna?':
        Answers directly with their name without unprompted creator lectures.
        When user asks 'Who am I?':
        Acknowledges creator identity if verified.
        """
        self.mm.establish_speaker_identity("Naresh", relationship="creator", source="explicit_user")

        # 1. Simple name question: "What is my name?"
        ans_name = self.mm.answer_memory_query("What is my name?")
        self.assertIsNotNone(ans_name)
        self.assertIn("Naresh", ans_name)
        # Must not contain creator lecture
        self.assertNotIn("creator", ans_name.lower())

        # 2. Tanglish name question: "En peru enna?"
        ans_peru = self.mm.answer_memory_query("En peru enna?")
        self.assertIsNotNone(ans_peru)
        self.assertIn("Naresh", ans_peru)
        self.assertNotIn("creator", ans_peru.lower())

        # 3. Identity question: "Who am I?"
        ans_who = self.mm.answer_memory_query("Who am I?")
        self.assertIsNotNone(ans_who)
        self.assertIn("Naresh", ans_who)
        self.assertIn("creator", ans_who.lower())

    # -------------------------------------------------------------------------
    # 6. Gemini Live System Prompt Construction & Context Synchronization
    # -------------------------------------------------------------------------
    def test_06_live_prompt_grounding_and_synchronization(self):
        """
        Verify that PersonalityContextBuilder and GeminiClient.live_system_prompt()
        include verified education facts and correctly update when new facts are stored.
        """
        self.mm.set_profile_fact("college", "Sona College of Technology", category="education")
        self.mm.set_profile_fact("degree", "MCA", category="education")
        self.mm.set_profile_fact("academic_year", "Second year", category="education")
        self.mm.establish_speaker_identity("Naresh", relationship="creator", source="explicit_user")

        # Build context block
        block = PersonalityContextBuilder.build_context_block(
            emotion_engine=self.ee,
            memory_manager=self.mm,
            query="Naan endha college-la padikkiren?"
        )

        # Context block must contain verified education facts
        self.assertIn("Sona College of Technology", block)
        self.assertIn("MCA", block)
        self.assertIn("Second year", block)
        self.assertIn("NO MEMORY/EDUCATION FABRICATION", block)

        # Live system prompt injection check
        with patch.object(GeminiClient, "_create_client"):
            client = GeminiClient(memory_manager=self.mm)
            live_prompt = client.live_system_prompt()

        self.assertIn("ACTIVE CONTEXT, EMOTIONAL STATE & MEMORY", live_prompt)
        self.assertIn("Sona College of Technology", live_prompt)
        self.assertIn("MCA", live_prompt)

        # Verify dynamic update: add new fact
        self.mm.set_profile_fact("department", "Computer Applications", category="education")
        new_block = PersonalityContextBuilder.build_context_block(
            emotion_engine=self.ee,
            memory_manager=self.mm,
            query="Naan endha department?"
        )
        self.assertIn("Computer Applications", new_block)

    # -------------------------------------------------------------------------
    # 7. WebSocket 1006 Recovery Simulation & Memory Preservation
    # -------------------------------------------------------------------------
    def test_07_websocket_reconnect_retains_memory(self):
        """
        Simulate a Gemini Live session encountering WebSocket abnormal closure (code 1006).
        Verify that when a new session or reconnect occurs, the reconstructed system prompt
        re-establishes all persistent memories from SQLite.
        """
        self.mm.set_profile_fact("college", "Sona College of Technology", category="education")
        self.mm.set_profile_fact("degree", "MCA", category="education")

        # Simulate abnormal termination by deleting in-memory Gemini client
        with patch.object(GeminiClient, "_create_client"):
            client_session_1 = GeminiClient(memory_manager=self.mm)
            prompt_1 = client_session_1.live_system_prompt()
            self.assertIn("Sona College of Technology", prompt_1)

        del client_session_1

        # Simulate reconnected session reading fresh from persistent storage
        mm_reconnected = MemoryManager(db=self.db, profile_id=self.TEST_PROFILE_ID)
        with patch.object(GeminiClient, "_create_client"):
            client_session_2 = GeminiClient(memory_manager=mm_reconnected)
            prompt_2 = client_session_2.live_system_prompt()

        self.assertIn("Sona College of Technology", prompt_2)
        self.assertIn("MCA", prompt_2)

    # -------------------------------------------------------------------------
    # 8. Turn 1183 Full Multi-Fact Tamil Extraction
    # -------------------------------------------------------------------------
    def test_08_turn1183_multi_fact_tamil_extraction(self):
        """
        Verify exact production utterance from Turn 1183 extracts all 7 facts simultaneously:
        name, college, degree, academic year, father, mother, and brother,
        without sentence bleeding or data loss.
        """
        turn_id = "live_turn_session_20261011_170740_d5cb2d_5"
        user_text = (
            "நான் என்னோட டீடைல்ஸ் சொல்றேன் ஷேர் பண்றேன். நீ உன்னுடைய மெமரில அப்டேட் பண்ணிக்கோ. "
            "மை நேம் இஸ் நரேஷ். ஐ அம் ஸ்டடிங் எம்சிஏ செகண்ட் இயர் இன் சோனா காலேஜ் ஆப் டெக்னாலஜி. "
            "மை பாதர் நேம் இஸ் ஜி செந்தில்நாதன். மை மதர் நேம் இஸ் எஸ் சங்கீதா அண்ட் மை பிரதர் நேம் இஸ் எஸ் தீபேஷ். ஓகே."
        )
        asst_text = "Noted! Unga details ellam memory-la store panniten."

        self.mm.save_user_turn(user_text, turn_id=turn_id, session_id="session_20261011_170740_d5cb2d", profile_id=self.TEST_PROFILE_ID)
        res = self.mm.complete_turn(turn_id, assistant_text=asst_text, user_text=user_text, profile_id=self.TEST_PROFILE_ID)
        self.assertTrue(res["success"])

        # 1. Identity
        pref_name, use_name = self.mm.get_user_name_preference()
        self.assertEqual(pref_name, "Naresh")
        self.assertTrue(use_name)

        # 2. Education
        col = self.mm.get_profile_fact("college")
        deg = self.mm.get_profile_fact("degree")
        yr = self.mm.get_profile_fact("academic_year")
        self.assertEqual(col, "Sona College of Technology")
        self.assertEqual(deg, "MCA")
        self.assertEqual(yr, "Second year")
        self.assertNotIn("நான் என்னோட", col)

        # 3. Family / Relationships
        active_mems = self.db.get_personal_memories(category="relationships", active_only=True, profile_id=self.TEST_PROFILE_ID)
        rel_dict = {m.get("key"): m.get("value") for m in active_mems}
        self.assertEqual(rel_dict.get("father"), "Senthilnathan")
        self.assertEqual(rel_dict.get("mother"), "Sangeetha")
        self.assertEqual(rel_dict.get("brother"), "Deepesh")

    # -------------------------------------------------------------------------
    # 9. Turn 1184 Post-Restart Query Recall
    # -------------------------------------------------------------------------
    def test_09_turn1184_post_restart_family_recall(self):
        """
        Verify the exact Turn 1184 query recalls all four names:
        Naresh (user), Senthilnathan (father), Sangeetha (mother), Deepesh (brother).
        """
        # Seed the memories
        self.mm.establish_speaker_identity("Naresh", relationship="creator", profile_id=self.TEST_PROFILE_ID)
        self.mm.db.set_user_context("preferred_user_name", "Naresh")
        self.mm.db.set_user_context("use_preferred_name", "True")
        for rel, name in [("father", "Senthilnathan"), ("mother", "Sangeetha"), ("brother", "Deepesh")]:
            self.mm.db.add_personal_memory(
                memory_id=f"mem_rel_{rel}_test",
                category="relationships",
                key=rel,
                value=name,
                profile_id=self.TEST_PROFILE_ID,
                status="active"
            )

        query = "Hey, na previous conversation la ennoda name and family details share pannirundhen. Anga ellar name'um sollu."
        ans = self.mm.answer_memory_query(query)
        self.assertIsNotNone(ans)
        self.assertIn("Naresh", ans)
        self.assertIn("Senthilnathan", ans)
        self.assertIn("Sangeetha", ans)
        self.assertIn("Deepesh", ans)

    # -------------------------------------------------------------------------
    # 10. Cold Restart Simulation & Gemini Live Prompt Grounding
    # -------------------------------------------------------------------------
    def test_10_cold_restart_live_prompt_injection(self):
        """
        Simulate an entire application cold restart from SQLite persistence:
        New DatabaseManager, new MemoryManager, new PersonalityContextBuilder.
        Verify Gemini Live system prompt immediately receives all personal and family facts.
        """
        # Save facts in first process
        self.mm.establish_speaker_identity("Naresh", relationship="creator", profile_id=self.TEST_PROFILE_ID)
        self.mm.db.set_user_context("preferred_user_name", "Naresh")
        self.mm.db.set_user_context("use_preferred_name", "True")
        self.mm.set_profile_fact("college", "Sona College of Technology", category="education")
        self.mm.set_profile_fact("degree", "MCA", category="education")
        self.mm.set_profile_fact("academic_year", "Second year", category="education")
        for rel, name in [("father", "Senthilnathan"), ("mother", "Sangeetha"), ("brother", "Deepesh")]:
            self.mm.db.add_personal_memory(
                memory_id=f"mem_rel_{rel}_cold",
                category="relationships",
                key=rel,
                value=name,
                profile_id=self.TEST_PROFILE_ID,
                status="active"
            )

        # Close session
        self.db.close()

        # Simulate fresh application restart
        fresh_db = DatabaseManager(database_path=self.temp_db_path)
        fresh_mm = MemoryManager(db=fresh_db, profile_id=self.TEST_PROFILE_ID)

        with patch.object(GeminiClient, "_create_client"):
            fresh_client = GeminiClient(memory_manager=fresh_mm)
            prompt = fresh_client.live_system_prompt()

        fresh_db.close()

        self.assertIn("Naresh", prompt)
        self.assertIn("Sona College of Technology", prompt)
        self.assertIn("MCA", prompt)
        self.assertIn("Second year", prompt)
        self.assertIn("Senthilnathan", prompt)
        self.assertIn("Sangeetha", prompt)
        self.assertIn("Deepesh", prompt)


if __name__ == "__main__":
    unittest.main()

