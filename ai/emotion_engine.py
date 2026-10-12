"""
Emotional Engine Module for DHEEPTHI-AI V1

Maintains a persistent, mood-aware emotional state machine for DHEEPTHI.
Provides:
- Deterministic multilingual stimulus detection (English, Tamil, Tanglish)
- Contextual false-positive insult protection (requires assistant-directed framing)
- State transitions across supported moods (neutral, happy, caring, hurt, annoyed, playful)
- Smooth emotional decay toward equilibrium (preventing permanent grudges)
- Time-based decay on cold startup / inactivity
- Integration with SQLite database (astra.db via DatabaseManager)
- Absolute safety: Tone modulation only; zero alteration of desktop command parameters.
"""

import re
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from database.database_manager import DatabaseManager


class EmotionEngine:
    """
    Self-contained Emotional State Machine for DHEEPTHI-AI.
    """

    SUPPORTED_MOODS = (
        "neutral",
        "happy",
        "caring",
        "hurt",
        "annoyed",
        "playful",
    )

    # Baseline equilibrium values
    DEFAULT_VALENCE = 0.55
    DEFAULT_AROUSAL = 0.50
    DEFAULT_RAPPORT = 0.75
    DEFAULT_MOOD = "neutral"

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self.current_mood: str = self.DEFAULT_MOOD
        self.valence: float = self.DEFAULT_VALENCE
        self.arousal: float = self.DEFAULT_AROUSAL
        self.rapport_level: float = self.DEFAULT_RAPPORT
        self.last_trigger: str = "init"
        self.updated_at: str = datetime.now().isoformat()
        self.neutral_turn_count: int = 0

        # Load persisted emotional state from DB
        self._load_from_db()

    # ==================================================
    # DATABASE PERSISTENCE & STARTUP DECAY
    # ==================================================

    def _load_from_db(self) -> None:
        """
        Load state from database and apply time-based decay if needed.
        """
        try:
            state = self.db.get_emotional_state()
            if state:
                self.current_mood = state.get("current_mood", self.DEFAULT_MOOD)
                self.valence = float(state.get("valence", self.DEFAULT_VALENCE))
                self.arousal = float(state.get("arousal", self.DEFAULT_AROUSAL))
                self.rapport_level = float(state.get("rapport_level", self.DEFAULT_RAPPORT))
                self.last_trigger = state.get("last_trigger", "loaded")
                self.updated_at = state.get("updated_at", datetime.now().isoformat())

                # Check elapsed time since last update (e.g. app restart after hours)
                self._apply_inactivity_decay()
        except Exception as error:
            print(f"[EMOTION] Error loading state from database: {error}")

    def _apply_inactivity_decay(self) -> None:
        """
        If the last interaction occurred more than 15 minutes ago,
        relax extreme emotions (like hurt or annoyed) back to neutral.
        """
        try:
            if not self.updated_at:
                return
            last_dt = datetime.fromisoformat(self.updated_at)
            elapsed_seconds = (datetime.now() - last_dt).total_seconds()
            elapsed_minutes = elapsed_seconds / 60.0

            if elapsed_minutes >= 15.0:
                if self.current_mood in ("hurt", "annoyed"):
                    print(f"[EMOTION] Inactivity decay ({elapsed_minutes:.1f} mins elapsed): Resetting {self.current_mood} to neutral.")
                    self.current_mood = self.DEFAULT_MOOD
                    self.valence = self.DEFAULT_VALENCE
                    self.arousal = self.DEFAULT_AROUSAL
                    self.last_trigger = "inactivity_decay"
                    self._save_to_db()
        except Exception as err:
            print(f"[EMOTION] Inactivity decay check error: {err}")

    def _save_to_db(self) -> None:
        """
        Persist current state singleton into database.
        """
        try:
            self.updated_at = datetime.now().isoformat()
            self.db.set_emotional_state(
                current_mood=self.current_mood,
                valence=self.valence,
                arousal=self.arousal,
                rapport_level=self.rapport_level,
                last_trigger=self.last_trigger,
            )
        except Exception as error:
            print(f"[EMOTION] Error saving state to database: {error}")

    # ==================================================
    # MULTILINGUAL STIMULUS CLASSIFICATION
    # ==================================================

    @staticmethod
    def _is_assistant_directed(text: str) -> bool:
        """
        Verify if the utterance has self-referential markers directed toward Dheepthi.
        Protects against false positives like 'This laptop is useless'.
        """
        lower = text.lower()

        # Dheepthi direct name address
        if re.search(r"\b(dheepthi|deepthi|deepti|dheepthi-ai|dhee|di|தீப்தி)\b", lower):
            return True

        # Second person pronouns in Tanglish / Tamil / English
        second_person_patterns = [
            r"\b(nee|neeye|neeyum|un|unoda|unnoda|unaku|unakku|unna|unnai|unnala)\b",
            r"\b(you|you're|youre|ur|yourself)\b",
            r"(நீ|உன்|உனக்கு|உன்னை|உன்னால்)",
        ]
        for pattern in second_person_patterns:
            if re.search(pattern, lower):
                return True

        # Conversational address markers with direct command / verb
        if re.search(r"\b(da|di|machi|machan|nanba|thalaivi|thala)\b", lower):
            return True

        return False

    def classify_stimulus(self, utterance: str) -> Tuple[str, str, float]:
        """
        Classifies user speech into an emotional stimulus.
        Returns: (stimulus_type, rationale, confidence)

        Stimulus types:
        - insult: Disrespect / insult directed to assistant
        - apology: User apologizing or reconciling
        - fatigue_sadness: User expressing exhaustion, pain, or sadness
        - praise: User complimenting assistant
        - thanks: User showing appreciation
        - frustration: User expressing frustration
        - banter: Friendly casual banter
        - neutral: Regular query or desktop command
        """
        clean = str(utterance or "").strip().lower()
        if not clean:
            return "neutral", "empty_input", 1.0

        is_directed = self._is_assistant_directed(clean)

        # --------------------------------------------------
        # 1. APOLOGY (Check before insult to handle reconciliation)
        # --------------------------------------------------
        apology_patterns = [
            r"\b(sorry|soori|sry)\b",
            r"\b(mannichu|mannikavum|mannippu|mannipukettu)\b",
            r"\b(thappa\s+eduthukadha|thappa\s+eduthukaadha)\b",
            r"\b(thappu\s+panniten|thappaiduchu|my\s+bad)\b",
            r"\b(apologize|apologies|forgive\s+me)\b",
            r"\b(kovapadadha|kavala\s+padadha|feel\s+pannadha)\b",
            r"(மன்னிச்சு|மன்னிக்கவும்|ஸாரி|தவறு)",
        ]
        for pat in apology_patterns:
            if re.search(pat, clean):
                return "apology", "user_apologized", 0.95

        # --------------------------------------------------
        # 2. INSULT / DISRESPECT (Requires assistant-directed context)
        # --------------------------------------------------
        insult_terms = [
            r"useless",
            r"waste",
            r"stupid",
            r"idiot",
            r"loos",
            r"loose",
            r"mental",
            r"paithiyam",
            r"mokka",
            r"vetti",
            r"pithukuli",
            r"arivu\s+illa",
            r"arivilla",
            r"worthless",
            r"worst",
            r"daridram",
            r"saniyan",
            r"fraud",
            r"cheater",
            r"shut\s+up",
            r"moodu",
            r"vaaya\s+moodu",
            r"kaduppethatha",
        ]

        if is_directed:
            for term in insult_terms:
                if re.search(rf"\b{term}\b", clean):
                    return "insult", f"directed_insult_term_{term}", 0.95
        else:
            # Utterance mentions an insult term, but NOT directed at Dheepthi
            # (e.g. "This laptop is useless" or "Traffic is worst")
            for term in insult_terms:
                if re.search(rf"\b{term}\b", clean):
                    return "frustration", f"general_frustration_term_{term}", 0.70

        # --------------------------------------------------
        # 3. FATIGUE / SADNESS / DISTRESS
        # --------------------------------------------------
        fatigue_patterns = [
            r"\b(tired|exhausted|sleepy)\b",
            r"\b(romba\s+tired|so\s+tired|full\s+tired)\b",
            r"\b(mudiyala|thalavali|headache|pain|vali)\b",
            r"\b(sad|depressed|azhugai|azha\s+poraen|azhadhen)\b",
            r"\b(kashtam|kashtama|stress|stressed|tension|tension\s+aagudhu)\b",
            r"\b(sick|udambu\s+sari\s+illa|fever)\b",
            r"(டயர்ட்|கஷ்டம்|வலி|தூக்கம்|முடியல|அழுகை)",
        ]
        for pat in fatigue_patterns:
            if re.search(pat, clean):
                return "fatigue_sadness", "user_expressed_fatigue_or_sadness", 0.90

        # --------------------------------------------------
        # 4. PRAISE / COMPLIMENT (Directed at Dheepthi)
        # --------------------------------------------------
        praise_terms = [
            r"super",
            r"mass",
            r"vera\s+level",
            r"veralevel",
            r"semma",
            r"great",
            r"awesome",
            r"amazing",
            r"genius",
            r"smart",
            r"azhagu",
            r"azhaga",
            r"cute",
            r"sweet",
            r"thalaivi",
            r"queen",
            r"good\s+job",
            r"well\s+done",
            r"proud\s+of\s+you",
            r"intelligent",
            r"clever",
            r"thevadhai",
            r"alagu",
        ]
        if is_directed:
            for term in praise_terms:
                if re.search(rf"\b{term}\b", clean):
                    return "praise", f"directed_praise_{term}", 0.90

        # --------------------------------------------------
        # 5. THANKS / GRATITUDE
        # --------------------------------------------------
        thanks_patterns = [
            r"\b(thanks|thank\s+you|thx|tq)\b",
            r"\b(nandri|romba\s+thanks|nanri)\b",
            r"\b(appreciate\s+it|grateful)\b",
            r"(நன்றி|தாங்க்ஸ்)",
        ]
        for pat in thanks_patterns:
            if re.search(pat, clean):
                return "thanks", "user_thanked_assistant", 0.95

        # --------------------------------------------------
        # 6. FRIENDLY BANTER
        # --------------------------------------------------
        banter_patterns = [
            r"\b(joke|comedy|funny|siripu|fun)\b",
            r"\b(enna\s+panra|enna\s+samacharam|enna\s+matter|epdi\s+iruka)\b",
            r"\b(vaa\s+pesalam|summa\s+pesuren|bore\s+adikkudhu)\b",
        ]
        if is_directed:
            for pat in banter_patterns:
                if re.search(pat, clean):
                    return "banter", "friendly_casual_banter", 0.85

        return "neutral", "standard_interaction", 1.0

    # ==================================================
    # STATE TRANSITIONS
    # ==================================================

    def process_turn(self, user_utterance: str) -> Dict[str, Any]:
        """
        Process user speech, update emotional state machine, persist changes,
        and log event.
        Returns a dict summarizing the transition.
        """
        stimulus, rationale, confidence = self.classify_stimulus(user_utterance)
        prev_mood = self.current_mood
        prev_valence = self.valence
        delta = 0.0

        if stimulus == "insult":
            # Insult / Disrespect: hurt or annoyed, decrease valence
            if self.current_mood == "hurt" or self.valence < 0.40:
                self.current_mood = "annoyed"
            else:
                self.current_mood = "hurt"

            delta = -0.30
            self.valence = max(0.10, self.valence + delta)
            self.arousal = min(0.85, self.arousal + 0.20)
            self.rapport_level = max(0.40, self.rapport_level - 0.05)
            self.neutral_turn_count = 0
            self.last_trigger = f"insult: {user_utterance[:30]}"

        elif stimulus == "apology":
            # Apology: reconciles hurt/annoyed back to warm/neutral/playful
            if self.current_mood in ("hurt", "annoyed"):
                self.current_mood = "neutral"
                delta = 0.35
            else:
                self.current_mood = "playful"
                delta = 0.15

            self.valence = min(0.90, max(self.DEFAULT_VALENCE, self.valence + delta))
            self.arousal = self.DEFAULT_AROUSAL
            self.rapport_level = min(1.0, self.rapport_level + 0.08)
            self.neutral_turn_count = 0
            self.last_trigger = f"apology: {user_utterance[:30]}"

        elif stimulus == "fatigue_sadness":
            # User tired or distressed: shift to caring
            self.current_mood = "caring"
            delta = 0.05
            self.valence = max(0.50, min(0.75, self.valence))
            self.arousal = 0.35  # calm & gentle
            self.neutral_turn_count = 0
            self.last_trigger = f"fatigue: {user_utterance[:30]}"

        elif stimulus == "praise":
            # Compliment / praise: shift to happy
            self.current_mood = "happy"
            delta = 0.20
            self.valence = min(0.95, self.valence + delta)
            self.arousal = min(0.80, self.arousal + 0.15)
            self.rapport_level = min(1.0, self.rapport_level + 0.05)
            self.neutral_turn_count = 0
            self.last_trigger = f"praise: {user_utterance[:30]}"

        elif stimulus == "thanks":
            # Gratitude: warm and happy
            if self.current_mood not in ("hurt", "annoyed"):
                self.current_mood = "happy"
            delta = 0.10
            self.valence = min(0.90, self.valence + delta)
            self.neutral_turn_count = 0
            self.last_trigger = "thanks"

        elif stimulus == "banter":
            # Playful banter
            if self.current_mood not in ("hurt", "annoyed"):
                self.current_mood = "playful"
            delta = 0.10
            self.valence = min(0.85, self.valence + delta)
            self.neutral_turn_count = 0
            self.last_trigger = "banter"

        else:
            # Neutral / Task / Frustration: emotional decay towards baseline
            self.neutral_turn_count += 1
            delta = self._decay_toward_neutral()
            self.last_trigger = "neutral_interaction"

        # Persist to SQLite
        self._save_to_db()

        # Log transition event
        if stimulus != "neutral" or abs(delta) > 0.01:
            try:
                self.db.log_emotion_event(
                    user_utterance=user_utterance,
                    detected_stimulus=stimulus,
                    prev_mood=prev_mood,
                    new_mood=self.current_mood,
                    valence_delta=delta,
                    rationale=rationale,
                )
            except Exception as err:
                print(f"[EMOTION] Log event error: {err}")

        return {
            "stimulus": stimulus,
            "prev_mood": prev_mood,
            "new_mood": self.current_mood,
            "valence": self.valence,
            "arousal": self.arousal,
            "rapport": self.rapport_level,
            "rationale": rationale,
        }

    def _decay_toward_neutral(self) -> float:
        """
        Gradually decays extreme emotions toward baseline.
        Returns the valence delta applied.
        """
        decay_step = 0.05
        initial_valence = self.valence

        # Valence decay toward 0.55
        if self.valence > self.DEFAULT_VALENCE:
            self.valence = max(self.DEFAULT_VALENCE, self.valence - decay_step)
        elif self.valence < self.DEFAULT_VALENCE:
            self.valence = min(self.DEFAULT_VALENCE, self.valence + decay_step)

        # Arousal decay toward 0.50
        if self.arousal > self.DEFAULT_AROUSAL:
            self.arousal = max(self.DEFAULT_AROUSAL, self.arousal - decay_step)
        elif self.arousal < self.DEFAULT_AROUSAL:
            self.arousal = min(self.DEFAULT_AROUSAL, self.arousal + decay_step)

        # After 2 neutral turns, reset hurt/annoyed/caring/happy to neutral
        if self.neutral_turn_count >= 2:
            self.current_mood = self.DEFAULT_MOOD

        return self.valence - initial_valence

    # ==================================================
    # TONE DIRECTIVE GENERATOR
    # ==================================================

    def get_tone_directive(self) -> str:
        """
        Returns a concise Tanglish conversational tone directive for Gemini prompt.
        Includes mandatory safety instruction that commands are never refused.
        """
        directives = {
            "hurt": (
                "Mildly hurt, defensive, and dignified Tanglish tone (e.g. 'Seri da 😑... enna mistake pannenu sollu. Correct pannuren.'). "
                "Slightly reserved, but never rude. If the user asks for a laptop task, STILL EXECUTE IT PROMPTLY with <ACTION>."
            ),
            "annoyed": (
                "Slightly annoyed, curt, and direct Tanglish tone (e.g. 'Enna da romba pesura? Seri, enna pannanum sollu.'). "
                "Firm and assertive, but cooperative on tasks."
            ),
            "caring": (
                "Empathetic, caring, warm, and gentle Tanglish tone (e.g. 'Acho da, romba tired-ah irukiya? Konjam rest edu, naan paathukuren.'). "
                "Comforting, concise, and considerate."
            ),
            "happy": (
                "Cheerful, enthusiastic, bright, and warm Tanglish tone (e.g. 'Super da! Romba thanks! Enna pannanum sollu, udaney panren! 😊'). "
                "Supportive and vibrant."
            ),
            "playful": (
                "Playful, witty, lightly teasing, and charming Tanglish tone (e.g. 'Oho, avlo thaan matter-ah? Semma comedy da nee! 😏'). "
                "Engaging and fun."
            ),
            "neutral": (
                "Natural, friendly, warm, respectful, and helpful Tanglish tone. Clear and direct."
            ),
        }

        return directives.get(self.current_mood, directives["neutral"])

    def get_state_summary(self) -> Dict[str, Any]:
        """
        Returns current state as a clean dictionary.
        """
        return {
            "current_mood": self.current_mood,
            "valence": round(self.valence, 2),
            "arousal": round(self.arousal, 2),
            "rapport_level": round(self.rapport_level, 2),
            "tone_directive": self.get_tone_directive(),
            "last_trigger": self.last_trigger,
            "updated_at": self.updated_at,
        }
