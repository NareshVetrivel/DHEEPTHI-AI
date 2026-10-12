"""
Memory Manager Module for DHEEPTHI-AI V1

Implements a 5-tiered hierarchical memory architecture:
1. Working Memory: Recent conversation turns in SQLite `conversation_context`
2. Semantic User Profile: Persistent user facts & preferences in SQLite `user_context`
3. Episodic Memory: Significant interactions & milestones in SQLite `memory_episodes`
4. Emotional Memory: Salient emotional events integrated with `EmotionEngine`
5. Interaction & People Memory: Persistent people, relationships, and habits in SQLite `people`

Features:
- Thread-safe persistence via DatabaseManager
- Strict credential safety filter: rejects passwords, OTPs, API keys, tokens
- Creator identity reconciliation: distinguishes static creator metadata from verified speaker identity
- Selective "Remember this" and "Forget this" support
- Future speaker recognition mapping: voice_profile_id -> person_id -> name -> relationship
- Lightweight rule-based memory extraction without extra LLM latency
- Compact memory retrieval formatted for Gemini context budget (~250-300 tokens)
- Automated retention control (100 working turns, 200 episodic records)
"""

import re
import json
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from database.database_manager import DatabaseManager


class MemoryManager:
    """
    Coordinates Working, Semantic Profile, Episodic, People, and Habit memory for DHEEPTHI-AI.
    """

    STATIC_CREATORS = ["Naresh", "Ragavendhiran"]

    CREDENTIAL_PATTERNS = [
        r"\b(?:password|passwd|pwd|passcode)\b(?:\s*[:=is\s]+\s*\S+)?",
        r"\b(?:otp|pin)\b(?:\s*[:=is\s]+\s*[0-9A-Za-z]{3,10}\b|\s+(?:code|number))",
        r"\bAIza[0-9A-Za-z_-]{35}\b",      # Google API key
        r"\bgsk_[a-zA-Z0-9]{20,}\b",        # Groq API key
        r"\bsk-[a-zA-Z0-9]{20,}\b",         # OpenAI API key
        r"\b(?:api[\s_-]?key|access[\s_-]?token|auth[\s_-]?token|bearer|secret[\s_-]?key)\b(?:\s*[:=is\s]+\s*\S+)?",
        r"\b(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])[A-Za-z0-9+/_-]{32,}={0,2}\b",     # High-entropy token
        r"\b(?:credit[\s_-]*card|cvv|cvc)\b(?:\s*[:=is\s]+\s*\S+)?",
    ]

    CONCEPT_ALIASES = {
        "bike": ["bike", "motorcycle", "twowheeler", "r15", "yamaha", "bullet", "enfield", "scooter", "ride", "பைக்", "இருசக்கர"],
        "car": ["car", "fourwheeler", "honda", "hyundai", "maruti", "tata", "drive", "கார்"],
        "laptop": ["laptop", "computer", "macbook", "dell", "hp", "thinkpad", "pc", "system", "லேப்டாப்"],
        "phone": ["phone", "mobile", "smartphone", "iphone", "samsung", "cell", "போன்", "மொபைல்"],
        "location": ["live", "living", "stay", "staying", "city", "place", "residence", "ooru", "thangi", "salem", "chennai", "coimbatore", "வாழ்கிறேன்", "ஊர்", "reside"],
        "hometown": ["native", "hometown", "sondha", "born", "சொந்த ஊர்"],
        "allergy": ["allergy", "allergic", "reaction", "padadhu", "peanuts", "nuts", "mushrooms", "அலர்ஜி"],
        "diet": ["diet", "vegetarian", "veg", "nonveg", "vegan", "eating", "food", "sappadu", "உணவு"],
        "routine": ["routine", "habit", "wake", "sleep", "gym", "exercise", "morning", "night", "daily", "வழக்கம்"],
        "schedule": ["schedule", "appointment", "meeting", "doctor", "dentist", "exam", "deadline", "date", "அப்பாயின்ட்மென்ட்"],
        "decision": ["decision", "decided", "chose", "choice", "mudivu", "architecture", "tech stack", "database", "sqlite", "flutter", "முடிவு"],
        "task": ["task", "todo", "need to", "promise", "pending", "commitment", "bill", "செய்ய வேண்டும்", "வேலை"],
        "people": ["manager", "boss", "teammate", "colleague", "coworker", "doctor", "mentor", "roommate", "friend"],
        "family": ["father", "mother", "brother", "sister", "wife", "husband", "son", "daughter", "appa", "amma", "anna", "thambi", "அப்பா", "அம்மா", "அண்ணன்", "தம்பி"],
        "education": ["college", "degree", "department", "year", "mca", "bca", "engineering", "studies", "padikiren", "கல்லூரி", "படிப்பு"],
        "work": ["job", "role", "company", "career", "work", "designation", "employer", "office", "tcs", "zoho", "google", "infosys", "வேலை"],
        "company": ["company", "employer", "work at", "office", "tcs", "cts", "zoho", "google", "infosys", "microsoft", "amazon", "நிறுவனம்"],
        "project": ["project", "developing", "building", "repo", "app", "application", "dheepthi", "drone", "system", "திட்டம்"],
        "hobby": ["hobby", "chess", "reading", "gaming", "photography", "drawing", "painting", "books", "விளையாட்டு", "ஆர்வம்"],
        "goal": ["goal", "ambition", "target", "aim", "future", "objective", "இலக்கு"],
        "challenge": ["challenge", "problem", "issue", "struggle", "facing", "சவால்", "பிரச்சனை"],
        "internship": ["intern", "internship", "trainee", "training"],
        "music": ["music", "song", "singer", "artist", "paattu", "பாட்டு", "இசை"],
        "preference": ["prefer", "favorite", "fav", "like", "pidikkum", "விருப்பம்"],
    }

    _STOPWORDS = {
        "the", "and", "for", "with", "that", "this", "from", "was", "were", "are",
        "has", "had", "have", "you", "not", "but", "all", "any", "can", "our", "out",
        "what", "who", "when", "where", "why", "how", "did", "does", "done", "about"
    }

    @classmethod
    def _is_query_or_question(cls, text: str) -> bool:
        """
        Returns True if the text is a question/query seeking memory retrieval,
        rather than a declarative statement sharing personal facts.
        """
        if not text:
            return False
        clean = text.strip().lower()

        # Explicit remember directives take precedence
        rem_directives = (
            "remember that", "please remember", "idha remember", "idha note", "note down",
            "idha memory", "vechuko", "அப்டேட் பண்ணிக்கோ", "ஞாபகம் வச்சுக்கோ",
            "update kar lo", "update this in your memory", "memory mein update", "memory la update"
        )
        if any(rem in clean for rem in rem_directives):
            return False

        # Recall / memory testing directives (Tamil, Tanglish, English)
        recall_markers = (
            "ஷேர் பண்ணு", "ஷேர்பண்ணு", "எனக்கு ஷேர்", "சொல்லு பார்க்கலாம்", "சொல்லு பாக்கலாம்",
            "ரிட்டன் சொல்லு", "சொல்ல முடியுமா", "சொல்லுங்க", "சொல்லு",
            "share pannu", "sollu pakalam", "sollu paakalam", "solla mudiyuma", "solrennu sonna",
            "recall", "remember about me", "what you remember", "what do you remember",
            "previous conversation", "munnadi sonna", "munbu sonna", "testing dhaan",
            "oru testing", "testing தான்", "test ah", "test dhaan", "what important things",
            "things did i tell you", "what did i tell you", "did i tell you",
            "tell me what you remember", "tell me about me", "what are my family", "who are my family",
            "which course am i", "which company am i", "what is my role", "what is my project",
            "what important things did i tell you"
        )
        if any(rm in clean for rm in recall_markers):
            return True

        # Embedded indirect questions inside sentences
        embedded_q_markers = (
            "என்ன காலேஜ்", "எந்த காலேஜ்", "என்ன கோர்ஸ்", "எந்த கோர்ஸ்", "என்ன படிக்குறேன்",
            "என்ன படிக்கிறேன்", "எந்த கம்பெனி", "என்ன ப்ராஜெக்ட்", "என்ன ரோல்",
            "enna college", "endha college", "enna course", "endha course",
            "enna padikiren", "endha company", "enna project", "enna role",
            "which college", "which course", "which company", "what role", "what project"
        )
        if any(eq in clean for eq in embedded_q_markers):
            return True

        # Declarative signals indicating information sharing even with a trailing conversational tag
        declarative_markers = (
            "padikiren", "padikkiren", "studying", "i am studying", "my name is", "en peru", "en peyar",
            "en appa", "my father", "my mother", "my brother", "my bike", "en bike", "en car",
            "my car", "i live in", "naan", "solren", "sonnen", "vechiruken", "iruken",
            "internship", "intern", "working", "work", "role", "developer", "estoy trabajando", "i am working", "project",
            "அப்டேட்", "டீடைல்ஸ்", "சொல்றேன்", "மை நேம்", "படிக்குறேன்", "படிக்கிறேன்",
            "என் பெயர்", "என் பேரு", "என் அப்பா", "என் அம்மா", "என் பைக்", "என் கார்"
        )

        # Strip rhetorical conversational tags at the end like "Ok va?", "sariya?", "தானா?", "ஓகே", "¿Okay?"
        stripped = re.sub(r"(?i)\s*(?:ok\s*va|okva|okay|ok|¿okay|¿ok|sariya|right|தானா|சரிதானா|ஓகே)[\?\.]*$", "", clean).strip()
        stripped = re.sub(r"^[¿\?]+", "", stripped).strip()

        # If after stripping conversational tag it contains clear declarative markers, check if it's still asking a question
        has_declarative = any(dm in stripped for dm in declarative_markers)

        # Explicit query starters (asking about user's identity, memory, or facts)
        q_starters = (
            "what is my", "what are my", "what was my", "what did i", "what do i",
            "who is my", "who are my", "where is my", "where do i live", "where am i",
            "when is my", "which is my", "which college do i", "which car do i", "which bike do i",
            "do i have", "did i have", "do i live", "did i say", "did i tell",
            "tell me my", "tell me about me", "do you know my", "do you remember my",
            "what do you know about me", "what did we decide", "what was the last command",
            "am i", "is my", "are my", "does my", "can you recall", "what important things",
        )
        if any(stripped.startswith(qs) or f" {qs} " in f" {stripped} " for qs in q_starters):
            return True

        # Tanglish / Tamil direct query patterns (e.g. "en bike enna?", "en appa yaar?", "enga iruken?")
        tanglish_q_patterns = [
            r"\b(?:en|ennoda|my)\s+(?:bike|car|laptop|phone|name|peru|peyar|college|degree|department|dept|year|father|mother|brother|sister|manager|teammate|allergy|hometown|native|company|role|project)\s+(?:enna|yaar|enga|edhu|endha)\b",
            r"\b(?:en|ennoda|my)\s+(?:bike|car|laptop|phone|name|peru|college|degree|father|mother|brother|company|role|project)\s*\?+$",
            r"\b(?:naan\s+enga\s+iruken|enga\s+padikiren|enaku\s+enna\s+allergy|en\s+diet\s+enna)\b",
            r"\b(?:do i have|enkitta\s+.+\s+irukka|naan\s+.+\s+padikirena|naan\s+.+\s+irukena)\b",
        ]
        if any(re.search(qp, stripped) for qp in tanglish_q_patterns):
            return True

        # If it ended with a question mark and does NOT have strong declarative statements
        if (clean.endswith("?") or clean.endswith("؟") or clean.endswith("¿")) and not has_declarative:
            return True

        return False

    @classmethod
    def _is_valid_fact_value(cls, key: str, value: Any) -> bool:
        """
        Validates whether a memory value is a genuine factual statement,
        rejecting question fragments, disfluency, and corrupted strings.
        """
        if not value or not isinstance(value, str):
            return False
        v_clean = value.strip().lower()
        if len(v_clean) < 2:
            return False

        # General rejection of question phrases stored as fact values
        q_markers = ("என்ன", "எந்த", "enna", "endha", "which", "what", "who", "where", "details na")
        if any(qm in v_clean for qm in q_markers):
            return False

        k_clean = str(key or "").strip().lower()
        if k_clean == "college":
            if any(w in v_clean for w in ("drawer", "keys", "table", "padikiren", "படிக்கிறேன்", "படிக்குறேன்", "course", "details")):
                return False
            if v_clean in ("college", "school", "technology", "of technology"):
                return False
        elif k_clean == "laptop":
            if any(w in v_clean for w in ("application yaani", "computer application", "master of", "mca", "degree", "padh raha")):
                return False
        elif k_clean == "current_project":
            if v_clean in ("bandh ke", "turant", "solid", "simple work", "code", "work", "project", "creator"):
                return False
        elif k_clean in ("father", "mother", "brother", "sister"):
            if v_clean in ("father", "mother", "brother", "sister", "name", "peru", "my", "your"):
                return False
        return True

    @classmethod
    def _is_hypothetical_or_uncertain(cls, text: str) -> bool:
        """
        Returns True if the statement is hypothetical, speculative, or uncertain.
        """
        if not text:
            return False
        clean = text.strip().lower()
        hypo_markers = (
            "if i", "what if", "assuming that", "suppose that", "suppose i",
            "maybe i", "might be", "probably", "not sure", "oru vela",
            "irundha", "therila", "doubtful", "could possibly"
        )
        return any(hm in clean for hm in hypo_markers)

    @classmethod
    def _split_clauses(cls, text: str) -> List[str]:
        """
        Splits a compound utterance into constituent declarative clauses for multi-fact extraction.
        """
        if not text:
            return []
        raw_parts = re.split(r"[\n\r;\.!\?]+|\s+(?:and|also|plus|but|அப்புறம்|apram|மேலும்)\s+", text, flags=re.IGNORECASE)
        clauses = []
        for p in raw_parts:
            sub_parts = re.split(r",\s*", p)
            for sp in sub_parts:
                sp_clean = sp.strip()
                if len(sp_clean) >= 3:
                    clauses.append(sp_clean)
        return clauses or [text.strip()]

    def __init__(self, db: Optional[DatabaseManager] = None, profile_id: str = "default"):
        self.db = db or DatabaseManager()
        self.profile_id = str(profile_id or "default")
        self.db.set_active_profile_id(self.profile_id)
        self.max_working_turns: int = 100
        self.max_episodes: int = 200

        # Pre-seed default profile facts if empty
        self._ensure_default_profile()
        # Clean up any stale or unverified user name state
        self._sanitize_user_name_state()
        # Ensure static creator entries exist in people table
        self._ensure_static_creator_records()

    def switch_profile(self, profile_id: str) -> None:
        """Switch active profile ID."""
        self.profile_id = str(profile_id or "default")
        self.db.set_active_profile_id(self.profile_id)

    def _ensure_default_profile(self) -> None:
        """Seed baseline profile facts if none exist."""
        try:
            if not self.db.get_user_context("assistant_name"):
                self.db.set_user_context("assistant_name", "Dheepthi", category="identity", source="system_metadata")
            if not self.db.get_user_context("preferred_language"):
                self.db.set_user_context("preferred_language", "Tanglish", category="preference", source="system_metadata")
        except Exception as error:
            print(f"[MEMORY] Default profile init error: {error}")

    def _sanitize_user_name_state(self) -> None:
        """
        Ensure no random, unverified, or legacy test names (such as 'Karthik', 'Rahul', 'Arun')
        pollute runtime user identity. Only explicit user statements with
        preferred_user_name_source='explicit_user' are respected.
        """
        try:
            source = self.db.get_user_context("preferred_user_name_source")
            pref_name = self.db.get_user_context("preferred_user_name")
            legacy_name = self.db.get_user_context("user_name")

            unverified_names = ("karthik", "rahul", "arun", "vani", "working")

            if legacy_name and (str(legacy_name).strip().lower() in unverified_names or source != "explicit_user"):
                print(f"[MEMORY SANITIZE] Purging unverified legacy user_name: {legacy_name}")
                self.db.delete_user_context("user_name")

            if pref_name and (str(pref_name).strip().lower() in unverified_names and source != "explicit_user"):
                print(f"[MEMORY SANITIZE] Purging unverified preferred_user_name: {pref_name}")
                self.db.delete_user_context("preferred_user_name")
                self.db.delete_user_context("preferred_user_name_source")

            # Clean any unverified entries from people table
            for bad_name in ("vani", "working"):
                self.db.delete_person(f"person_{bad_name}")
                self.db.delete_person(bad_name)
        except Exception as error:
            print(f"[MEMORY SANITIZE] Error during user name sanitization: {error}")

    def _ensure_static_creator_records(self) -> None:
        """
        Seed static creator records in people table with source='system_metadata'.
        Does NOT mark them as current primary user unless explicitly confirmed.
        """
        try:
            for c_name in self.STATIC_CREATORS:
                existing = self.db.get_person_by_name(c_name)
                if not existing:
                    self.db.add_or_update_person(
                        name=c_name,
                        preferred_name=c_name,
                        relationship_to_dheepthi="creator",
                        is_primary_user=0,
                        is_creator=1,
                        identity_source="system_metadata",
                        confidence="high",
                        voice_profile_id=c_name.lower(),
                        notes="Co-creator of DHEEPTHI-AI",
                        person_id=f"creator_{c_name.lower()}",
                    )
        except Exception as error:
            print(f"[MEMORY] Creator records seeding error: {error}")

    # ==================================================
    # SAFETY & CREDENTIAL FILTER
    # ==================================================

    @classmethod
    def contains_sensitive_data(cls, text: str) -> bool:
        """
        Returns True if the text appears to contain passwords, OTPs, or API keys.
        """
        if not text:
            return False
        clean = str(text)
        for pattern in cls.CREDENTIAL_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE):
                return True
        return False

    @classmethod
    def redact_sensitive_data(cls, text: str) -> Tuple[str, bool]:
        """
        Safely redacts detected sensitive credentials from text while preserving
        safe surrounding conversational content.
        Returns: (sanitized_text, was_redacted)
        """
        if not text:
            return "", False

        sanitized = str(text)
        was_redacted = False

        # 1. Direct API Keys
        if re.search(r"\bAIza[0-9A-Za-z_-]{35}\b", sanitized):
            sanitized = re.sub(r"\bAIza[0-9A-Za-z_-]{35}\b", "[REDACTED_API_KEY]", sanitized)
            was_redacted = True

        if re.search(r"\bgsk_[a-zA-Z0-9]{20,}\b", sanitized):
            sanitized = re.sub(r"\bgsk_[a-zA-Z0-9]{20,}\b", "[REDACTED_API_KEY]", sanitized)
            was_redacted = True

        if re.search(r"\bsk-[a-zA-Z0-9]{20,}\b", sanitized):
            sanitized = re.sub(r"\bsk-[a-zA-Z0-9]{20,}\b", "[REDACTED_API_KEY]", sanitized)
            was_redacted = True

        # 2. Contextual Credential Values (e.g. "password is Secret123", "pin is 1234", "otp is 987654")
        context_patterns = [
            (r"(\b(?:password|passwd|pwd|passcode)\s*(?:is|was|=|:)?\s*)(\S+)", r"\1[REDACTED_CREDENTIAL]"),
            (r"(\b(?:otp|pin)\s*(?:is|was|=|:)?\s*)([0-9A-Za-z]{3,10}\b)", r"\1[REDACTED_CREDENTIAL]"),
            (r"(\b(?:api[\s_-]?key|access[\s_-]?token|auth[\s_-]?token|secret[\s_-]?key|bearer)\s*(?:is|was|=|:)?\s*)(\S+)", r"\1[REDACTED_CREDENTIAL]"),
            (r"(\b(?:credit[\s_-]*card|cvv|cvc)\s*(?:is|was|=|:)?\s*)(\S+)", r"\1[REDACTED_CREDENTIAL]"),
        ]
        for pat, repl in context_patterns:
            if re.search(pat, sanitized, re.IGNORECASE):
                sanitized = re.sub(pat, repl, sanitized, flags=re.IGNORECASE)
                was_redacted = True

        # 3. High-entropy tokens
        high_entropy = r"\b(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])[A-Za-z0-9+/_-]{32,}={0,2}\b"
        if re.search(high_entropy, sanitized):
            sanitized = re.sub(high_entropy, "[REDACTED_TOKEN]", sanitized)
            was_redacted = True

        return sanitized, was_redacted

    # ==================================================
    # IDENTITY & CREATOR MODEL MANAGEMENT
    # ==================================================

    def set_user_name_preference(
        self,
        preferred_name: Optional[str],
        use_name: bool = True,
        source: str = "explicit_user",
        profile_id: Optional[str] = None,
    ) -> bool:
        """
        Explicitly establishes or suppresses the user's preferred address name.
        If use_name is False, name usage is opted out and all active user names are cleared.
        """
        try:
            p_id = profile_id or getattr(self, "profile_id", "default")
            if not use_name or preferred_name is None:
                self.db.set_user_context("use_preferred_name", "false", category="identity", source=source)
                self.db.delete_user_context("preferred_user_name")
                self.db.delete_user_context("preferred_user_name_source")
                self.db.delete_user_context("user_name")
                self.db.delete_user_context("primary_user_name")
                self.db.set_user_context("speaker_identity_status", "opted_out", category="identity", source=source)
                print("[MEMORY] User explicitly opted out of name usage (use_preferred_name=False).")
                return True

            raw_name = str(preferred_name).strip()
            clean_name = raw_name[0].upper() + raw_name[1:] if raw_name else ""
            reserved = (
                "dheepthi", "deepthi", "ai", "user", "laptop", "creator",
                "developer", "computer", "bro", "nanba", "machi", "boss",
                "thala", "thalaivi", "sir", "fine", "good", "bad", "tired",
                "busy", "happy", "sad", "none", "null"
            )
            if not clean_name or len(clean_name) < 2 or clean_name.lower() in reserved:
                return False

            self.db.set_user_context("preferred_user_name", clean_name, category="identity", source=source)
            self.db.set_user_context("preferred_user_name_source", str(source), category="identity", source=source)
            self.db.set_user_context("use_preferred_name", "true", category="identity", source=source)
            self.db.set_user_context("user_name", clean_name, category="identity", source=source)
            self.db.set_user_context("primary_user_name", clean_name, category="identity", source=source)
            print(f"[MEMORY] Explicit preferred user name saved: {clean_name} (source={source})")
            return True
        except Exception as error:
            print(f"[MEMORY] Set user name preference error: {error}")
            return False

    def get_user_name_preference(self, profile_id: Optional[str] = None) -> Tuple[Optional[str], bool]:
        """
        Retrieves (preferred_user_name, use_preferred_name).
        Returns:
            (None, False) if user explicitly opted out.
            (name, True) if an explicit user-provided name is stored.
            (None, True) if no user name has been established yet.
        """
        try:
            p_id = profile_id or getattr(self, "profile_id", "default")
            use_val = self.db.get_user_context("use_preferred_name")
            if use_val is not None and str(use_val).strip().lower() in ("false", "0", "no"):
                return None, False

            source = self.db.get_user_context("preferred_user_name_source")
            name = self.db.get_user_context("preferred_user_name")
            if not name:
                name = self.db.get_user_context("user_name")
            if not name:
                name = self.db.get_user_context("primary_user_name")
            if not source:
                source = self.db.get_user_context("identity_source")

            if name and source == "explicit_user":
                clean = str(name).strip().capitalize()
                return clean, True

            return None, True
        except Exception as error:
            print(f"[MEMORY] Get user name preference error: {error}")
            return None, True

    def establish_speaker_identity(
        self,
        name: str,
        relationship: Optional[str] = None,
        source: str = "explicit_user",
        confidence: str = "high",
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Establishes the current speaker's identity when explicitly stated.
        Links creator relationship if name matches known creators or creator was claimed.
        """
        clean_name = str(name).strip()
        norm_name = clean_name[0].upper() + clean_name[1:] if clean_name else ""

        is_creator = False
        rel_str = relationship or "user"

        if norm_name in self.STATIC_CREATORS:
            rel_str = "creator"
            is_creator = True
        elif relationship == "creator" or self.db.get_user_context("creator_relationship") == "creator":
            rel_str = "creator"
            is_creator = True

        # Save to user_context
        self.set_user_name_preference(norm_name, use_name=True, source=source)
        self.db.set_user_context("primary_user_name", norm_name, category="identity", source=source, confidence=confidence)
        self.db.set_user_context("creator_relationship", rel_str, category="identity", source=source, confidence=confidence)
        self.db.set_user_context(
            "speaker_identity_status",
            "verified_creator" if is_creator else "known_user",
            category="identity",
            source=source,
            confidence=confidence
        )
        self.db.set_user_context("identity_source", source, category="identity", source=source)
        self.db.set_user_context("identity_confidence", confidence, category="identity", source=source)
        now_iso = datetime.now().isoformat()
        self.db.set_user_context("identity_last_confirmed", now_iso, category="identity", source=source)

        # Update people table
        self.db.add_or_update_person(
            name=norm_name,
            preferred_name=norm_name,
            relationship_to_dheepthi="creator" if is_creator else "primary_user",
            relationship_to_primary_user="self",
            is_primary_user=1,
            is_creator=1 if is_creator else 0,
            identity_source=source,
            confidence=confidence,
            voice_profile_id=norm_name.lower(),
            notes=f"Primary user ({rel_str})",
            person_id=f"person_{norm_name.lower()}",
        )

        print(f"[MEMORY IDENTITY] Speaker identity established: name={norm_name} relationship={rel_str} confidence={confidence}")
        return self.get_speaker_identity()

    def set_creator_relationship(
        self,
        is_creator: bool = True,
        creator_name: Optional[str] = None,
        source: str = "explicit_user",
        confidence: str = "high",
    ) -> bool:
        """
        Records or confirms that the current speaker is DHEEPTHI's creator.
        """
        try:
            target_name = creator_name or self.db.get_user_context("preferred_user_name") or self.db.get_user_context("primary_user_name")
            if target_name:
                norm_name = str(target_name).strip().capitalize()
                return bool(self.establish_speaker_identity(norm_name, relationship="creator", source=source, confidence=confidence))

            # If name not yet established, record pending creator relationship for the active speaker
            rel_val = "creator" if is_creator else "none"
            self.db.set_user_context("creator_relationship", rel_val, category="identity", source=source, confidence=confidence)
            self.db.set_user_context("speaker_identity_status", "claimed_creator" if is_creator else "unknown", category="identity", source=source)
            self.db.set_user_context("identity_source", source, category="identity", source=source)
            self.db.set_user_context("identity_confidence", confidence, category="identity", source=source)
            now_iso = datetime.now().isoformat()
            self.db.set_user_context("identity_last_confirmed", now_iso, category="identity", source=source)
            print(f"[MEMORY IDENTITY] Creator relationship set without explicit name: status={'claimed_creator' if is_creator else 'none'}")
            return True
        except Exception as error:
            print(f"[MEMORY] Set creator relationship error: {error}")
            return False

    def ensure_canonical_identity(self) -> None:
        """
        Ensures the canonical identity state in the permanent database:
        - Seeds static creator records in people table (system_metadata).
        - Preserves existing user name if set, but does NOT force 'Naresh' on an empty profile.
        """
        try:
            # Always ensure creators exist in people table as system metadata
            self._ensure_static_creator_records()

            use_val = self.db.get_user_context("use_preferred_name")
            use_name = False if use_val is not None and str(use_val).strip().lower() in ("false", "0", "no") else True

            pref_name = self.db.get_user_context("preferred_user_name")
            prim_name = self.db.get_user_context("primary_user_name")

            # Only verify creator identity IF the name was explicitly verified as Naresh
            if pref_name == "Naresh" or prim_name == "Naresh":
                self.db.set_user_context("primary_user_name", "Naresh", category="identity", source="explicit_user", confidence="high")
                self.db.set_user_context("preferred_user_name", "Naresh", category="identity", source="explicit_user", confidence="high")
                self.db.set_user_context("preferred_user_name_source", "explicit_user", category="identity", source="explicit_user", confidence="high")
                self.db.set_user_context("creator_relationship", "creator", category="identity", source="explicit_user", confidence="high")
                self.db.set_user_context("speaker_identity_status", "verified_creator", category="identity", source="explicit_user", confidence="high")
                self.db.set_user_context("identity_source", "explicit_user", category="identity", source="explicit_user", confidence="high")
                self.db.set_user_context("identity_confidence", "high", category="identity", source="explicit_user", confidence="high")
                if not use_name:
                    self.db.set_user_context("use_preferred_name", "false", category="identity", source="explicit_user")
        except Exception as error:
            print(f"[MEMORY] Ensure canonical identity error: {error}")

    def get_speaker_identity(self) -> Dict[str, Any]:
        """
        Retrieves the complete structured speaker identity context.
        """
        pref_name, use_name = self.get_user_name_preference()
        prim_name = self.db.get_user_context("primary_user_name")
        creator_rel = self.db.get_user_context("creator_relationship", default="none")
        id_status = self.db.get_user_context("speaker_identity_status", default="unknown")
        id_conf = self.db.get_user_context("identity_confidence", default="medium")
        id_source = self.db.get_user_context("identity_source", default="inferred")
        last_conf = self.db.get_user_context("identity_last_confirmed")

        active_name = pref_name or prim_name
        is_creator = False

        if not use_name:
            id_status = "opted_out"
            active_name = None
        elif active_name:
            if active_name in self.STATIC_CREATORS or creator_rel == "creator" or id_status == "verified_creator":
                is_creator = True
                id_status = "verified_creator"
                creator_rel = "creator"
            else:
                id_status = "known_user"
        elif creator_rel == "creator" or id_status == "claimed_creator":
            id_status = "claimed_creator"
            is_creator = False
        else:
            id_status = "unknown"
            is_creator = False

        known_people = self.db.get_all_known_people()

        return {
            "primary_user_name": active_name,
            "preferred_user_name": active_name,
            "use_preferred_name": use_name,
            "creator_relationship": "creator" if is_creator else "none",
            "is_creator": is_creator,
            "creator_name": active_name if is_creator else None,
            "known_people": known_people,
            "speaker_identity_status": id_status,
            "identity_confidence": id_conf,
            "identity_source": id_source,
            "identity_last_confirmed": last_conf,
        }

    def add_known_person(
        self,
        name: str,
        relationship_to_primary_user: str,
        relationship_to_dheepthi: str = "known_person",
        voice_profile_id: Optional[str] = None,
        notes: str = "",
        source: str = "explicit_user",
        confidence: str = "high",
        profile_id: Optional[str] = None,
    ) -> bool:
        """
        Adds a known person/relation (e.g. brother, colleague, friend) to memory.
        Prepares for future speaker voice-profile recognition.
        """
        clean_name = str(name).strip()
        if not clean_name:
            return False
        norm_name = clean_name[0].upper() + clean_name[1:]
        vp_id = voice_profile_id or norm_name.lower()
        p_id = profile_id or getattr(self, "profile_id", "default")

        ok = self.db.add_or_update_person(
            name=norm_name,
            preferred_name=norm_name,
            relationship_to_dheepthi=relationship_to_dheepthi,
            relationship_to_primary_user=relationship_to_primary_user,
            is_primary_user=0,
            is_creator=0,
            identity_source=source,
            confidence=confidence,
            voice_profile_id=vp_id,
            notes=notes or f"{relationship_to_primary_user} of primary user",
            profile_id=p_id,
        )
        if ok:
            print(f"[MEMORY PEOPLE] Known person added: {norm_name} ({relationship_to_primary_user})")
        return ok

    def get_known_person(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetch a known person by name."""
        return self.db.get_person_by_name(name)

    def get_all_known_people(self) -> List[Dict[str, Any]]:
        """Fetch all known people."""
        return self.db.get_all_known_people(profile_id=getattr(self, "profile_id", None))

    # ==================================================
    # SELECTIVE FORGETTING ("FORGET THIS" SUPPORT)
    # ==================================================

    def forget_memory(self, target: str) -> bool:
        """
        Selectively removes or deactivates a specific memory or preference.
        Does NOT blindly wipe all memory.
        """
        target_clean = str(target or "").strip().lower()
        if not target_clean:
            return False

        deactivated = False
        p_id = getattr(self, "profile_id", "default")

        # 1. Name forget request
        if any(w in target_clean for w in ("name", "peru", "peyar", "call me")):
            self.set_user_name_preference(preferred_name=None, use_name=False)
            self.db.deactivate_personal_memory(key="preferred_user_name", profile_id=p_id)
            self.db.deactivate_personal_memory(key="user_name", profile_id=p_id)
            deactivated = True

        # 2. Language preference forget
        if any(w in target_clean for w in ("tanglish", "language", "english", "tamil")):
            self.db.deactivate_user_context("preferred_language")
            self.db.deactivate_personal_memory(key="preferred_language", profile_id=p_id)
            deactivated = True

        # 3. Music/song forget
        if any(w in target_clean for w in ("music", "song", "paattu", "singer", "artist")):
            self.db.deactivate_user_context("favorite_music")
            self.db.deactivate_personal_memory(key="favorite_music", profile_id=p_id)
            deactivated = True

        # 4. Project forget
        if any(w in target_clean for w in ("project", "work", "dheepthi-ai")):
            self.db.deactivate_user_context("current_project")
            self.db.deactivate_personal_memory(key="current_project", profile_id=p_id)
            deactivated = True

        # 5. Relationship forget
        rel_keys = ("father", "mother", "brother", "sister", "friend", "wife", "husband", "son", "daughter")
        for rk in rel_keys:
            if rk in target_clean or (rk == "father" and "appa" in target_clean) or (rk == "mother" and "amma" in target_clean) or (rk == "brother" and ("anna" in target_clean or "thambi" in target_clean)):
                self.db.deactivate_personal_memory(key=rk, category="relationships", profile_id=p_id)
                for p in self.get_all_known_people():
                    if p.get("relationship_to_primary_user") == rk:
                        self.db.delete_person(p.get("name", ""))
                        self.db.delete_person(p.get("person_id", ""))
                deactivated = True

        # 6. Search for any other matching key in user_context and personal_memories
        matches = self.db.search_user_context(target_clean)
        for row in matches:
            k = row[0]
            self.db.deactivate_user_context(k)
            self.db.deactivate_personal_memory(key=k, profile_id=p_id)
            deactivated = True

        m_mems = self.db.search_personal_memories(target_clean, profile_id=p_id)
        for mm in m_mems:
            k = mm.get("key")
            cat = mm.get("category")
            if k:
                self.db.deactivate_personal_memory(key=k, category=cat, profile_id=p_id)
                self.db.deactivate_user_context(k)
                deactivated = True

        if deactivated:
            self.add_episode(
                summary=f"User requested to forget: {target_clean}",
                emotional_valence=0.5,
                category="preference_update",
                importance=3,
            )
            print(f"[MEMORY FORGET] Deactivated memory related to: '{target_clean}'")

        return deactivated

    # ==================================================
    # 1. WORKING MEMORY (Recent Conversation Context)
    # ==================================================

    def save_user_turn(
        self,
        user_text: str,
        turn_id: Optional[str] = None,
        session_id: Optional[str] = None,
        input_source: str = "voice",
        intent: Optional[str] = None,
        target: Optional[str] = None,
        context_data: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Immediately persists finalized raw user transcript to SQLite.
        Returns (success: bool, turn_id: str).
        """
        user_clean = str(user_text or "").strip()
        t_id = str(turn_id) if turn_id else f"turn_{session_id or 'default'}_{int(time.time() * 1000)}"
        p_id = str(profile_id or getattr(self, "profile_id", "default") or "default")

        if not user_clean:
            return False, t_id

        sanitized_user, was_redacted = self.redact_sensitive_data(user_clean)
        if was_redacted:
            print(f"[MEMORY SAFETY] Sensitive credential pattern detected and redacted. Persisting turn: turn_id={t_id}")

        try:
            success = self.db.save_user_interaction(
                turn_id=t_id,
                user_command=sanitized_user,
                session_id=session_id,
                input_source=input_source,
                intent=intent,
                target=target,
                context_data=context_data,
                profile_id=p_id,
            )
            return success, t_id
        except Exception as error:
            print(f"[MEMORY] Save user turn error: {error}")
            return False, t_id

    def persist_user_turn(
        self,
        user_text: str = "",
        turn_id: Optional[str] = None,
        session_id: Optional[str] = None,
        input_source: str = "voice",
        intent: Optional[str] = None,
        target: Optional[str] = None,
        context_data: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> str:
        """
        Immediately persists finalized raw user transcript to SQLite.
        Accepts either (user_text, turn_id=..., session_id=...) or (turn_id, user_text, ...).
        Returns turn_id.
        """
        if turn_id and not str(turn_id).startswith("turn_") and str(user_text).startswith("turn_"):
            # Swapped positional arguments: turn_id was passed first, user_text second
            user_text, turn_id = turn_id, user_text

        ok, t_id = self.save_user_turn(
            user_text=user_text,
            turn_id=turn_id,
            session_id=session_id,
            input_source=input_source,
            intent=intent,
            target=target,
            context_data=context_data,
            profile_id=profile_id,
        )
        return t_id

    def mark_turn_interrupted(self, turn_id: str) -> bool:
        """
        Marks an in-flight turn as interrupted due to user barge-in.
        """
        return self.db.update_turn_status(turn_id=str(turn_id), turn_status="interrupted")

    def complete_turn(
        self,
        turn_id: str,
        assistant_text: str,
        user_text: Optional[str] = None,
        intent: str = "conversation",
        turn_status: str = "completed",
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Persists completed assistant response and triggers provenance-aware memory extraction.
        Returns {"success": bool, "turn_id": str, "extracted_memories": List[str]}.
        """
        t_id = str(turn_id or "").strip()
        assistant_clean = str(assistant_text or "").strip()
        p_id = str(profile_id or getattr(self, "profile_id", "default") or "default")

        sanitized_asst, a_red = self.redact_sensitive_data(assistant_clean)
        if a_red:
            print(f"[MEMORY SAFETY] Sensitive credential pattern detected and redacted in assistant response: turn_id={t_id}")

        try:
            # 1. Persist assistant response
            db_success = self.db.update_assistant_interaction(
                turn_id=t_id,
                assistant_response=sanitized_asst,
                turn_status=turn_status,
                profile_id=p_id,
            )

            # 2. Extract memories with provenance
            extracted_ids: List[str] = []
            if user_text:
                try:
                    extracted_ids = self.extract_memories_from_turn(
                        user_text=user_text,
                        assistant_text=sanitized_asst,
                        intent=intent,
                        source_turn_id=t_id
                    )
                    if extracted_ids and db_success:
                        self.db.update_assistant_interaction(
                            turn_id=t_id,
                            assistant_response=sanitized_asst,
                            turn_status=turn_status,
                            extracted_memory_ids=",".join(extracted_ids),
                            profile_id=p_id,
                        )
                except Exception as ex_err:
                    print(f"[MEMORY] Memory extraction failed: {ex_err}")

            self.db.trim_conversation_context(keep_last=self.max_working_turns)

            return {
                "success": db_success,
                "turn_id": t_id,
                "extracted_memories": extracted_ids
            }
        except Exception as error:
            print(f"[MEMORY] Complete turn error: {error}")
            return {
                "success": False,
                "turn_id": t_id,
                "extracted_memories": []
            }

    def save_turn(
        self,
        user_text: str,
        assistant_text: str = "",
        intent: str = "conversation",
        target: str = "",
        context_data: str = "",
        session_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        input_source: str = "voice",
        profile_id: Optional[str] = None,
        turn_status: str = "completed",
    ) -> bool:
        """
        Persists a completed or errored turn to conversation_context, enforces retention limit,
        and triggers background episodic/profile extraction. Backwards-compatible.
        """
        user_clean = str(user_text or "").strip()
        assistant_clean = str(assistant_text or "").strip()
        p_id = str(profile_id or getattr(self, "profile_id", "default") or "default")

        if not user_clean and not assistant_clean:
            return False

        t_id = str(turn_id) if turn_id else f"turn_{session_id or 'default'}_{int(time.time() * 1000)}"

        sanitized_user, u_red = self.redact_sensitive_data(user_clean)
        sanitized_asst, a_red = self.redact_sensitive_data(assistant_clean)
        if u_red or a_red:
            print(f"[MEMORY SAFETY] Sensitive credential pattern detected and redacted. Persisting turn: turn_id={t_id}")

        try:
            # 1. Save user turn with sanitized input
            u_ok = self.db.save_user_interaction(
                turn_id=t_id,
                user_command=sanitized_user,
                session_id=session_id,
                input_source=input_source,
                intent=intent,
                target=target,
                context_data=context_data,
                profile_id=p_id,
            )

            # 2. Extract memories with provenance
            extracted_ids: List[str] = []
            try:
                extracted_ids = self.extract_memories_from_turn(
                    user_text=sanitized_user,
                    assistant_text=sanitized_asst,
                    intent=intent,
                    source_turn_id=t_id
                )
            except Exception as ex_err:
                print(f"[MEMORY] Memory extraction failed: {ex_err}")
            self.last_extracted_memory_ids = list(extracted_ids)

            # 3. Update assistant response with sanitized text and effective turn status
            a_ok = self.db.update_assistant_interaction(
                turn_id=t_id,
                assistant_response=sanitized_asst,
                turn_status=turn_status,
                extracted_memory_ids=",".join(extracted_ids) if extracted_ids else None,
                profile_id=p_id,
            )

            self.db.trim_conversation_context(keep_last=self.max_working_turns)
            return u_ok or a_ok
        except Exception as error:
            print(f"[MEMORY] Save turn error: {error}")
            return False

    def get_recent_working_turns(self, limit: int = 8) -> List[Dict[str, str]]:
        """
        Fetch the most recent turns formatted as [{"user": "...", "assistant": "..."}].
        Returned in chronological order (oldest to newest) for prompt context.
        """
        try:
            rows = self.db.get_recent_context(limit=limit)
            turns = []
            for row in reversed(rows):
                u = row[1] or ""
                a = row[2] or ""
                if u or a:
                    turns.append({"user": u, "assistant": a})
            return turns
        except Exception as error:
            print(f"[MEMORY] Get working turns error: {error}")
            return []

    def get_conversation_history(self, limit: int = 10, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch conversation history records from database.
        """
        try:
            return self.db.get_recent_conversation_window(limit=limit, session_id=session_id)
        except Exception as error:
            print(f"[MEMORY] Get conversation history error: {error}")
            return []

    def inspect_memories(self, profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns all active personal memories scoped by profile_id.
        """
        p_id = profile_id or getattr(self, "profile_id", "default")
        return self.db.get_personal_memories(active_only=True, profile_id=p_id)

    def correct_memory(
        self,
        key: str,
        new_value: str,
        category: str = "general",
        profile_id: Optional[str] = None,
    ) -> bool:
        """
        Explicitly updates/supersedes an existing memory record with a new verified value.
        """
        p_id = profile_id or getattr(self, "profile_id", "default")
        mem_id = f"mem_corr_{key}_{int(time.time() * 1000)}"
        return self.set_profile_fact(
            key=key,
            value=new_value,
            category=category,
            source="explicit_user",
            importance=4,
            memory_id=mem_id,
        )

    def search_conversation_archive(
        self,
        query: str,
        profile_id: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search durable conversation archive using token-overlap and phrase co-occurrence.
        """
        p_id = profile_id or getattr(self, "profile_id", "default")
        try:
            return self.db.search_conversation_archive(query=query, limit=top_k, profile_id=p_id)
        except Exception as error:
            print(f"[MEMORY] Search conversation archive error: {error}")
            return []

    def add_task(
        self,
        description: str,
        deadline: Optional[str] = None,
        profile_id: Optional[str] = None,
        source_turn_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Track an unresolved user task or commitment.
        """
        p_id = profile_id or getattr(self, "profile_id", "default")
        try:
            return self.db.add_task(
                description=description,
                deadline=deadline,
                profile_id=p_id,
                source_turn_id=source_turn_id,
            )
        except Exception as error:
            print(f"[MEMORY] Add task error: {error}")
            return None

    def complete_task(
        self,
        task_keyword: str,
        profile_id: Optional[str] = None,
    ) -> bool:
        """
        Mark a task or commitment as completed and update memory state.
        """
        p_id = profile_id or getattr(self, "profile_id", "default")
        try:
            updated = self.db.update_task_status(
                task_id_or_keyword=task_keyword,
                new_status="completed",
                profile_id=p_id,
            )
            # Also deactivate or update pending_task in personal_memories
            if task_keyword:
                active_tasks = self.db.get_personal_memories(
                    category="task",
                    active_only=True,
                    profile_id=p_id,
                )
                for t in active_tasks:
                    val = str(t.get("value", "")).lower()
                    if task_keyword.lower() in val or val in task_keyword.lower():
                        self.db.supersede_personal_memory(
                            t.get("memory_id"),
                            superseded_by_id=f"comp_{int(time.time()*1000)}"
                        )
            return updated
        except Exception as error:
            print(f"[MEMORY] Complete task error: {error}")
            return False

    def get_active_tasks(
        self,
        profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return currently active/pending tasks for the specified profile.
        """
        p_id = profile_id or getattr(self, "profile_id", "default")
        try:
            return self.db.get_tasks(status="pending", profile_id=p_id)
        except Exception as error:
            print(f"[MEMORY] Get active tasks error: {error}")
            return []

    def search_relevant_memories(
        self,
        query: str,
        profile_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves active personal memories ranked by multi-factor semantic scoring:
        token overlap, concept alias expansion, category alignment, recency, and confidence.
        """
        q_clean = str(query or "").strip().lower()
        if not q_clean:
            return []

        p_id = profile_id or getattr(self, "profile_id", "default")
        active_mems = self.db.get_personal_memories(
            active_only=True,
            profile_id=p_id
        )
        if not active_mems:
            return []

        # Identify active concept clusters
        active_concepts = set()
        for concept, aliases in self.CONCEPT_ALIASES.items():
            for al in aliases:
                if al.isascii():
                    if re.search(rf"\b{re.escape(al)}\b", q_clean):
                        active_concepts.add(concept)
                        break
                else:
                    if al in q_clean:
                        active_concepts.add(concept)
                        break

        scored: List[Tuple[float, Dict[str, Any]]] = []

        for mem in active_mems:
            cat = str(mem.get("category") or "").lower()
            key = str(mem.get("key") or "").lower()
            val = str(mem.get("value") or "").lower()
            conf = str(mem.get("confidence") or "medium").lower()

            score = 0.0

            # 1. Exact key match
            if key and re.search(rf"\b{re.escape(key)}\b", q_clean):
                score += 10.0
            elif key and key in q_clean:
                score += 7.0

            # 2. Key tokens in query
            for kt in re.findall(r"[\w]+", key):
                if len(kt) >= 3 and kt.lower() not in self._STOPWORDS and re.search(rf"\b{re.escape(kt)}\b", q_clean):
                    score += 4.0

            # 3. Value tokens in query
            for vt in re.findall(r"[\w]+", val):
                if len(vt) >= 3 and vt.lower() not in self._STOPWORDS and re.search(rf"\b{re.escape(vt)}\b", q_clean):
                    score += 4.0

            # 4. Concept cluster overlap
            for concept in active_concepts:
                aliases = self.CONCEPT_ALIASES.get(concept, [])
                if concept in cat or concept in key:
                    score += 5.0
                if any(al in key or al in cat or al in val for al in aliases):
                    score += 3.0

            # 5. Category token match
            if cat and cat in q_clean:
                score += 3.0

            # 6. Confidence weighting
            conf_mult = 1.0 if conf == "high" else (0.8 if conf == "medium" else 0.5)
            final_score = score * conf_mult

            if final_score > 0:
                scored.append((final_score, mem))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def answer_memory_query(self, query: str) -> Optional[str]:
        """
        Answer user questions about past interactions, identity, family, possessions,
        locations, dietary preferences, routines, schedules, decisions, tasks, people,
        education, career, projects, plans, notes, and command history directly from verified SQLite records.
        """
        q_clean = str(query or "").strip().lower()
        if not q_clean:
            return None

        p_id = getattr(self, "profile_id", "default")

        # 0. Broad Profile Overview Queries
        broad_profile_queries = (
            "what do you know about me", "what do you remember about me",
            "en pathi enna theriyum", "en pathi unaku enna theriyum",
            "what do you know", "en profile pathi sollu", "tell me about me",
            "en details enna", "what details do you have about me",
            "tell me what you remember about me", "tell me what you remember",
            "what important things did i tell you", "what did i tell you in previous conversations",
            "previous conversations", "what you remember about me",
            "what important things", "remember about me"
        )
        if any(bq in q_clean for bq in broad_profile_queries):
            pref_name, use_name = self.get_user_name_preference()
            deg = self.get_profile_fact("degree")
            yr = self.get_profile_fact("academic_year")
            col = self.get_profile_fact("college")
            father = self.get_profile_fact("father")
            mother = self.get_profile_fact("mother")
            brother = self.get_profile_fact("brother")
            comp = self.get_profile_fact("company")
            role = self.get_profile_fact("job_role")
            intern = self.get_profile_fact("internship")
            proj = self.get_profile_fact("current_project")
            city = self.get_profile_fact("living_city") or self.get_profile_fact("city")
            hometown = self.get_profile_fact("hometown") or self.get_profile_fact("native_city")
            bike = self.get_profile_fact("bike")
            car = self.get_profile_fact("car")
            manager = self.get_profile_fact("manager")

            sections = []
            if pref_name and use_name:
                is_cr = self.get_speaker_identity().get("is_creator", False)
                cr_str = " (en creator)" if is_cr else ""
                sections.append(f"Unga name {pref_name}{cr_str}")

            edu_items = []
            if deg: edu_items.append(deg)
            if yr: edu_items.append(yr)
            if col: edu_items.append(f"{col}-la")
            if edu_items:
                sections.append(f"Studies: {' '.join(edu_items)} padikireenga")

            fam_items = []
            if mother: fam_items.append(f"Amma {mother}")
            if father: fam_items.append(f"Appa {father}")
            if brother: fam_items.append(f"Thambi/Brother {brother}")
            if fam_items:
                sections.append(f"Family: {', '.join(fam_items)}")

            work_items = []
            if role: work_items.append(f"{role} role")
            if comp: work_items.append(f"{comp}-la")
            if intern and intern != role: work_items.append(f"internship: {intern}")
            if work_items:
                sections.append(f"Work/Career: {' '.join(work_items)}")

            if proj:
                sections.append(f"Project: {proj}")

            loc_items = []
            if city: loc_items.append(f"{city}-la irukeenga")
            if hometown: loc_items.append(f"sondha ooru {hometown}")
            if loc_items:
                sections.append(f"Location: {', '.join(loc_items)}")

            poss_items = []
            if bike: poss_items.append(f"Bike: {bike}")
            if car: poss_items.append(f"Car: {car}")
            if poss_items:
                sections.append(f"Assets: {', '.join(poss_items)}")

            if manager:
                sections.append(f"Manager: {manager}")

            if sections:
                return "Neenga sonnadhu ellam enakku nallave nyabagam irukku: " + "; ".join(sections) + "."

        # 1. Identity / User Name
        name_queries = ("en peru", "en peyar", "my name", "who am i", "yaar naan", "enna koopdu", "what is my name")
        if any(nq in q_clean for nq in name_queries):
            pref_name, use_name = self.get_user_name_preference()
            identity = self.get_speaker_identity()
            if not use_name:
                return "Neenga unga name use panna vendam nu solli irukinga, so naan ungalai name vechu koopdala."
            if pref_name:
                is_cr = identity.get("is_creator")
                if "who am i" in q_clean or "yaar naan" in q_clean:
                    if is_cr:
                        return f"Unga name {pref_name}. Neenga DHEEPTHI-AI oda creator."
                    return f"Unga name {pref_name}."
                return f"Unga name {pref_name}."
            return "Unga name innum confirm aagala. Enna name-la koopdanum nu sollala."

        # 2. Family & Relationships Queries
        if re.search(r"\b(?:family|kudumbam|kudumba|ellar|ellarum|everyone)\b", q_clean):
            active_mems = self.db.get_personal_memories(
                category="relationships",
                active_only=True,
                profile_id=p_id
            )
            details = [f"{m.get('key').capitalize()}: {m.get('value')}" for m in active_mems if m.get("key") and m.get("value")]
            if not details:
                known = self.get_all_known_people()
                for p in known:
                    rel = p.get("relationship_to_primary_user")
                    if rel and rel not in ("self", "creator", "primary_user") and p.get("name") not in self.STATIC_CREATORS:
                        details.append(f"{rel.capitalize()}: {p.get('name')}")

            pref_name, use_name = self.get_user_name_preference()
            name_part = ""
            if any(w in q_clean for w in ("name", "peru", "peyar", "ellar", "ellarum")) and pref_name and use_name:
                name_part = f"Unga name {pref_name}. "

            if details:
                return f"{name_part}Neenga unga family pathi sonnadhu: {', '.join(details)}."
            elif name_part:
                return f"{name_part}Aana unga family details innum memory-la illa."
            return "Unga family pathi neenga innum edhuvum share pannala."

        rel_keywords = {
            "father": ("father", "appa", "dad"),
            "mother": ("mother", "amma", "mom"),
            "brother": ("brother", "anna", "thambi", "annan"),
            "sister": ("sister", "akka", "thangachi", "thangai"),
            "friend": ("friend", "nanban", "dost"),
            "wife": ("wife", "manaivi"),
            "husband": ("husband", "kanavan"),
            "son": ("son", "paiyan", "magan"),
            "daughter": ("daughter", "ponnu", "magal"),
        }
        for r_key, r_words in rel_keywords.items():
            if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in r_words):
                p_mem = self.db.get_personal_memories(
                    category="relationships",
                    key=r_key,
                    active_only=True,
                    profile_id=p_id
                )
                if p_mem:
                    val = p_mem[0].get("value")
                    return f"Unga {r_key} name {val}."
                for p in self.get_all_known_people():
                    if p.get("relationship_to_primary_user") == r_key:
                        return f"Unga {r_key} name {p.get('name')}."
                if any(ask in q_clean for ask in ("who", "name", "peru", "yaar", "what", "enna")):
                    return f"Unga {r_key} pathi neenga innum share pannala. {r_key.capitalize()} peru enna nu sollala."

        # 3. Non-Family People (Manager, Teammate, Colleague, Doctor, Mentor, Roommate)
        people_roles = {
            "manager": ("manager", "boss"),
            "teammate": ("teammate", "team member"),
            "colleague": ("colleague", "coworker"),
            "doctor": ("doctor", "physician"),
            "mentor": ("mentor", "guide"),
            "roommate": ("roommate", "flatmate"),
        }
        for p_role, p_words in people_roles.items():
            if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in p_words):
                if p_role == "doctor" and any(w in q_clean for w in ("appointment", "schedule", "hospital", "clinic", "when")):
                    continue
                pm = self.db.get_personal_memories(key=p_role, active_only=True, profile_id=p_id)
                if pm:
                    val = pm[0].get("value")
                    return f"Unga {p_role} {val}."
                for p in self.get_all_known_people():
                    if p.get("relationship_to_primary_user") == p_role:
                        return f"Unga {p_role} {p.get('name')}."
                if any(ask in q_clean for ask in ("who", "name", "peru", "yaar", "what", "enna")):
                    return f"Unga {p_role} pathi innum share pannala."

        # 4. Possessions & Assets (Vehicles, Gadgets, Valuables, Keys)
        # A. Bike / Motorcycle
        if re.search(r"\b(?:bike|motorcycle|twowheeler|பைக்)\b", q_clean):
            bm = self.db.get_personal_memories(key="bike", active_only=True, profile_id=p_id)
            if not bm:
                bm = self.db.get_personal_memories(category="possession", active_only=True, profile_id=p_id)
                bm = [m for m in bm if m.get("key") in ("bike", "motorcycle", "vehicle")]
            if bm:
                return f"Unga bike {bm[0].get('value')}."
            return "Unga bike pathi memory-la details illa."

        # B. Car
        if re.search(r"\b(?:car|fourwheeler|கார்)\b", q_clean):
            cm = self.db.get_personal_memories(key="car", active_only=True, profile_id=p_id)
            if cm:
                return f"Unga car {cm[0].get('value')}."
            return "Unga car pathi memory-la details illa."

        # C. Laptop / Computer
        if re.search(r"\b(?:laptop|macbook|computer|system|pc)\b", q_clean):
            lm = self.db.get_personal_memories(key="laptop", active_only=True, profile_id=p_id)
            if lm:
                return f"Unga laptop {lm[0].get('value')}."
            return "Unga laptop pathi memory-la details illa."

        # D. Phone / Mobile
        if re.search(r"\b(?:phone|mobile|smartphone)\b", q_clean):
            phm = self.db.get_personal_memories(key="phone", active_only=True, profile_id=p_id)
            if not phm:
                phm = self.db.get_personal_memories(key="mobile", active_only=True, profile_id=p_id)
            if phm:
                return f"Unga phone {phm[0].get('value')}."
            return "Unga phone pathi memory-la details illa."

        # E. Stored Items / Keys / Drawer Location
        if any(w in q_clean for w in ("keys", "key", "drawer", "kept", "keep", "enga vechiruken", "where did i put")):
            km = self.db.get_personal_memories(active_only=True, profile_id=p_id)
            matched_stored = [m for m in km if "keys" in m.get("key", "").lower() or "stored" in m.get("key", "").lower() or "drawer" in m.get("value", "").lower()]
            if matched_stored:
                item_name = matched_stored[0].get("key", "").replace("location_", "").replace("stored_item_", "").replace("_", " ")
                loc_val = matched_stored[0].get("value")
                return f"Neenga {item_name}-ah {loc_val}-la vechirukeenga nu sonneenga."
            return "Keys or items location pathi memory-la record illa."

        # 5. Locations & Living Context (Living City, Hometown, Native)
        if any(w in q_clean for w in ("live", "living", "enga iruken", "where do i live", "residence", "city")):
            lm = self.db.get_personal_memories(key="living_city", active_only=True, profile_id=p_id)
            if not lm:
                lm = self.db.get_personal_memories(category="location", active_only=True, profile_id=p_id)
                lm = [m for m in lm if m.get("key") in ("living_city", "current_city", "residence")]
            if lm:
                return f"Neenga {lm[0].get('value')}-la irukeenga."
            return "Unga living location pathi innum share pannala."

        if any(w in q_clean for w in ("native", "hometown", "sondha ooru", "sondha")):
            nm = self.db.get_personal_memories(key="hometown", active_only=True, profile_id=p_id)
            if not nm:
                nm = self.db.get_personal_memories(key="native_city", active_only=True, profile_id=p_id)
            if nm:
                return f"Unga hometown/sondha ooru {nm[0].get('value')}."
            return "Unga hometown pathi innum share pannala."

        # 6. Dietary & Health Preferences (Allergies, Diet)
        if any(w in q_clean for w in ("allergy", "allergies", "allergic", "அலர்ஜி")):
            am = self.db.get_personal_memories(key="allergy", active_only=True, profile_id=p_id)
            if not am:
                am = self.db.get_personal_memories(key="allergies", active_only=True, profile_id=p_id)
            if not am:
                am = self.db.get_personal_memories(category="health", active_only=True, profile_id=p_id)
            if am:
                return f"Neenga sonnadhu: {am[0].get('value')} allergy."
            return "Unga allergies pathi memory-la record illa."

        if any(w in q_clean for w in ("diet", "vegetarian", "veg", "non-veg", "sappadu", "food preference")):
            dm = self.db.get_personal_memories(key="dietary_preference", active_only=True, profile_id=p_id)
            if dm:
                return f"Neenga {dm[0].get('value')} nu sonneenga."
            return "Unga dietary preference pathi memory-la record illa."

        # 7. Daily Routines & Habits (Wake Up, Gym, Sleep)
        if any(w in q_clean for w in ("wake up", "wake", "enthiripen", "ezhunthiripen", "morning routine")):
            wm = self.db.get_personal_memories(key="wake_up_time", active_only=True, profile_id=p_id)
            if wm:
                return f"Neenga daily {wm[0].get('value')}-ku enthiripen nu sonneenga."
            return "Unga wake up time pathi innum share pannala."

        if any(w in q_clean for w in ("gym", "workout", "fitness", "exercise")):
            gm = self.db.get_personal_memories(key="fitness_routine", active_only=True, profile_id=p_id)
            if gm:
                return f"Neenga {gm[0].get('value')}-ku gym poren nu sonneenga."
            return "Unga gym routine pathi innum share pannala."

        # 8. Schedules & Appointments (Doctor, Dentist, Meetings, Exams)
        if any(w in q_clean for w in ("appointment", "doctor", "dentist", "hospital", "schedule", "meeting")):
            sm = self.db.get_personal_memories(category="schedule", active_only=True, profile_id=p_id)
            if sm:
                parts = [f"{m.get('key').replace('_', ' ').capitalize()}: {m.get('value')}" for m in sm]
                return f"Unga upcoming schedule/appointment: {', '.join(parts)}."
            if "doctor" in q_clean:
                return "Doctor appointment pathi memory-la details illa."
            return "Appointments or schedules pathi memory-la record illa."

        # 9. Technical & Personal Decisions
        decision_queries = ("decision", "decided", "mudivu", "architecture", "tech stack", "database", "sqlite")
        if any(re.search(rf"\b{re.escape(dq)}\b", q_clean) for dq in decision_queries):
            dec_mems = self.db.get_personal_memories(
                category="decision",
                active_only=True,
                profile_id=p_id
            )
            if not dec_mems:
                dec_mems = self.db.get_personal_memories(
                    category="project",
                    active_only=True,
                    profile_id=p_id
                )
            dec_parts = [f"{m.get('key').replace('_', ' ').capitalize()}: {m.get('value')}" for m in dec_mems]
            if dec_parts:
                return f"Namma decisions pathi sonnadhu: {', '.join(dec_parts)}."
            proj_dec = self.get_profile_fact("project_decision")
            if proj_dec:
                return f"Project decision: {proj_dec}."
            return "Project decisions pathi records edhuvum illa."

        # 10. Commitments & Pending Tasks
        task_queries = ("task", "pending", "promise", "promised", "need to do", "pannanum", "bill")
        if any(re.search(rf"\b{re.escape(tq)}\b", q_clean) for tq in task_queries):
            tm = self.db.get_personal_memories(category="task", active_only=True, profile_id=p_id)
            if tm:
                tasks = [m.get("value") for m in tm if m.get("value")]
                return f"Neenga sonna pending tasks / commitments: {'; '.join(tasks)}."
            return "Pending tasks pathi memory-la record illa."

        # 11. Education & Studies Queries
        edu_keywords = (
            "college", "degree", "course", "studying", "padikiren", "padikkiren",
            "padikiran", "studies", "education", "department", "dept", "year",
            "கல்லூரி", "காலேஜ்", "படிப்பு", "டிபார்ட்மென்ட்", "ஆண்டு", "வருடம்"
        )
        if any(re.search(rf"\b{re.escape(eq)}\b", q_clean) or eq in q_clean for eq in edu_keywords):
            col = self.get_profile_fact("college")
            deg = self.get_profile_fact("degree")
            yr = self.get_profile_fact("academic_year")
            dept = self.get_profile_fact("department")
            goal = self.get_profile_fact("learning_goal")
            if not col:
                c_m = self.db.get_personal_memories(category="education", key="college", active_only=True, profile_id=p_id)
                if c_m: col = c_m[0].get("value")
            if not deg:
                d_m = self.db.get_personal_memories(category="education", key="degree", active_only=True, profile_id=p_id)
                if d_m: deg = d_m[0].get("value")
            if not yr:
                y_m = self.db.get_personal_memories(category="education", key="academic_year", active_only=True, profile_id=p_id)
                if y_m: yr = y_m[0].get("value")
            if not dept:
                dp_m = self.db.get_personal_memories(category="education", key="department", active_only=True, profile_id=p_id)
                if dp_m: dept = dp_m[0].get("value")

            is_col_q = any(w in q_clean for w in ("college", "கல்லூரி", "காலேஜ்")) or any(w in q_clean for w in ("enga padik", "where do i study", "where", "enga"))
            is_course_q = any(w in q_clean for w in ("course", "degree", "கோர்ஸ்")) or ("enna padik" in q_clean and not any(w in q_clean for w in ("college", "year", "dept", "department")))
            is_year_q = any(w in q_clean for w in ("year", "இயர்", "வருடம்", "ஆண்டு"))
            is_dept_q = any(w in q_clean for w in ("department", "dept", "டிபார்ட்மென்ட்"))

            if is_col_q and is_course_q:
                ans_parts = []
                if deg: ans_parts.append(f"Neenga padikira course {deg}" + (f" ({yr})" if yr else ""))
                if col: ans_parts.append(f"college {col}")
                if ans_parts:
                    return ", ".join(ans_parts) + "."

            if is_dept_q and is_year_q:
                ans_parts = []
                if yr:
                    ans_parts.append(f"Neenga {yr} padikkireenga")
                else:
                    ans_parts.append("Unga academic year pathi share pannala")
                if dept:
                    ans_parts.append(f"unga department {dept}")
                elif deg:
                    ans_parts.append(f"department pathi thaniya illai, but unga course {deg}")
                else:
                    ans_parts.append("department pathi memory-la illa")
                return ", ".join(ans_parts) + "."

            if is_dept_q:
                if dept:
                    return f"Unga department {dept}."
                if deg:
                    return f"Unga department pathi memory-la thaniya illa. But neenga {deg} padikireenga nu store aagi irukku."
                return "Unga department pathi neenga innum share pannala."

            if is_col_q and not (is_course_q or is_year_q):
                if col:
                    return f"Neenga padikira college {col}."
                return "Unga college pathi neenga innum share pannala. Endha college nu sollala."

            if is_course_q and not (is_col_q or is_year_q):
                if deg:
                    return f"Neenga padikira course/degree {deg}."
                return "Unga course/degree pathi neenga innum share pannala."

            if is_year_q and not (is_col_q or is_course_q):
                if yr:
                    return f"Neenga {yr} padikkireenga."
                return "Unga academic year pathi neenga innum share pannala."

            parts = []
            if col: parts.append(f"College: {col}")
            if deg: parts.append(f"Degree/Course: {deg}")
            if yr: parts.append(f"Year: {yr}")
            if dept: parts.append(f"Department: {dept}")
            if goal: parts.append(f"Learning: {goal}")
            if parts:
                return f"Neenga sonna studies details: {', '.join(parts)}."

        # 12. Work & Career Queries
        work_queries = ("job", "career", "company", "velai", "role", "designation", "skills", "intern", "internship", "interning")
        if any(re.search(rf"\b{re.escape(wq)}\b", q_clean) for wq in work_queries):
            role = self.get_profile_fact("job_role")
            comp = self.get_profile_fact("company")
            skills = self.get_profile_fact("skills")
            intern = self.get_profile_fact("internship")
            curr_proj = self.get_profile_fact("current_project")
            parts = []
            if role: parts.append(f"Role: {role}")
            if comp: parts.append(f"Company: {comp}")
            if intern and intern != role: parts.append(f"Internship: {intern}")
            if "project" in q_clean and curr_proj and self._is_valid_fact_value("current_project", curr_proj):
                parts.append(f"Project: {curr_proj}")
            if skills: parts.append(f"Skills: {skills}")
            if not parts:
                career_mems = self.db.get_personal_memories(
                    category="work",
                    active_only=True,
                    profile_id=p_id
                )
                parts = [f"{m.get('key').replace('_', ' ').capitalize()}: {m.get('value')}" for m in career_mems if m.get('key') not in ("current_project",) and self._is_valid_fact_value(m.get('key'), m.get('value'))]
            if parts:
                return f"Neenga sonna career/work details: {', '.join(parts)}."

        # 13. Project & Discussion
        project_queries = ("project", "working on", "dheepthi", "ennoda work", "my project", "symphowork")
        if any(pq in q_clean for pq in project_queries):
            curr_proj = self.get_profile_fact("current_project")
            dec = self.get_profile_fact("project_decision")
            tech = self.get_profile_fact("primary_technology")
            role = self.get_profile_fact("job_role")
            if any(w in q_clean for w in ("goal", "aim", "target", "decision", "mudivu")):
                if dec:
                    resp = f"Project goal/decision: {dec}."
                    if curr_proj and self._is_valid_fact_value("current_project", curr_proj):
                        resp = f"Project {curr_proj} goal: {dec}."
                    return resp
            if "role" in q_clean and role and curr_proj and self._is_valid_fact_value("current_project", curr_proj):
                return f"Unga role {role}, neenga work panra project {curr_proj}" + (f" ({tech})" if tech else "") + "."
            if curr_proj and self._is_valid_fact_value("current_project", curr_proj):
                resp = f"Neenga {curr_proj} project-la work panringa nu sonninga."
                if dec:
                    resp += f" Project goal: {dec}."
                if tech:
                    resp += f" Primary technology: {tech}."
                return resp
            if dec:
                return f"Project goal/decision: {dec}."

        # 14. Plans & Milestones
        plan_queries = ("plan", "planning", "deadline", "milestone", "target date", "planniruken")
        if any(re.search(rf"\b{re.escape(pq)}\b", q_clean) for pq in plan_queries):
            plan_mems = self.db.get_personal_memories(
                category="plan",
                active_only=True,
                profile_id=p_id
            )
            parts = [f"{m.get('key').replace('_', ' ').capitalize()}: {m.get('value')}" for m in plan_mems]
            up_plan = self.get_profile_fact("upcoming_plan")
            dl = self.get_profile_fact("deadline")
            if up_plan and f"Upcoming plan: {up_plan}" not in parts:
                parts.append(f"Upcoming plan: {up_plan}")
            if dl and f"Deadline: {dl}" not in parts:
                parts.append(f"Deadline: {dl}")
            if parts:
                return f"Neenga sonna plans & milestones: {', '.join(parts)}."
            if any(ask in q_clean for ask in ("what", "enna")):
                return "Plans or deadlines pathi innum register pannala."

        # 15. Explicit Notes / Remembered Items
        note_queries = ("remember panna sonnadhu", "what did i tell you to remember", "what did you remember", "en notes", "my notes")
        if any(nq in q_clean for nq in note_queries):
            notes = self.db.get_personal_memories(
                category="user_note",
                active_only=True,
                profile_id=p_id
            )
            if notes:
                summaries = [m.get("value") for m in notes if m.get("value")]
                return f"Neenga remember panna sonna vishayangal: {'; '.join(summaries)}."
            return "Neenga specifically remember panna sonna notes edhuvum illa."

        # 16. Preferences (Language, Music)
        pref_queries = ("preference", "language", "music", "song", "pidikkum", "fav")
        if any(pq in q_clean for pq in pref_queries) and any(pq in q_clean for pq in ("sonna", "enna", "what", "prefer")):
            lang = self.get_profile_fact("preferred_language")
            music = self.get_profile_fact("favorite_music")
            if "language" in q_clean or "pesu" in q_clean:
                if lang:
                    return f"Unga preferred language: {lang}."
            if "music" in q_clean or "song" in q_clean or "paattu" in q_clean:
                if music:
                    return f"Unga favorite music: {music}."
            if lang or music:
                parts = []
                if lang: parts.append(f"Language: {lang}")
                if music: parts.append(f"Music: {music}")
                return f"Neenga sonna preferences: {', '.join(parts)}."
            return "Neenga specific preferences innum register pannala."

        # 17. Free-form History Search
        recall_match = re.search(r"(?:what did i say about|what did i tell you about|naan\s+(.+)\s+pathi enna sonnen)\s*(.+)?", q_clean)
        if recall_match:
            keyword = (recall_match.group(1) or recall_match.group(2) or "").strip().rstrip("?").strip()
            if keyword and len(keyword) > 2 and keyword not in ("it", "this", "that", "unna", "un"):
                hits = self.db.search_conversation_history(keyword=keyword, limit=3, profile_id=p_id)
                if hits:
                    u_texts = [f"'{h.get('user_command')}'" for h in hits if h.get("user_command")]
                    if u_texts:
                        return f"Neenga '{keyword}' pathi sonnadhu: {', '.join(u_texts)}."

        # 18. Previous Session / Discussion
        session_queries = ("previous session", "munnadi discuss", "enna discuss", "what did we discuss", "earlier", "kadantha murai")
        if any(sq in q_clean for sq in session_queries):
            turns = self.db.get_recent_conversation_window(limit=3)
            if turns:
                topics = []
                for t in turns:
                    u = t.get("user_command", "").strip()
                    if u and len(u) > 3:
                        topics.append(f"'{u}'")
                if topics:
                    return f"Namma previous session-la {', '.join(topics)} pathi discuss pannom."
            return "Previous discussion pathi records edhuvum illa."

        # 19. Command Execution (Dictionary & Tuple Safe)
        cmd_queries = ("command", "execute pannoma", "run pannoma", "last time", "did we run")
        if any(cq in q_clean for cq in cmd_queries):
            cmds = self.db.get_recent_commands(limit=3, profile_id=p_id)
            if cmds:
                last_cmd = cmds[0]
                if isinstance(last_cmd, dict):
                    c_name = last_cmd.get("command", "")
                    c_status = last_cmd.get("status", "unknown")
                else:
                    c_name = last_cmd[1] if len(last_cmd) > 1 else ""
                    c_status = last_cmd[4] if len(last_cmd) > 4 else "unknown"
                return f"Last time execute panna command: '{c_name}' (status: {c_status})."
            return "Recent command history edhuvum illa."

        # 20. Open-Domain: Career, Company, Role, Internship
        if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in ("company", "workplace", "internship", "designation", "job", "role")) or ("where do i work" in q_clean or "enna vela" in q_clean or "endha company" in q_clean):
            comp = self.get_profile_fact("company")
            role = self.get_profile_fact("job_role")
            intern = self.get_profile_fact("internship")
            parts = []
            if comp: parts.append(f"Company: {comp}")
            if role: parts.append(f"Role: {role}")
            if intern: parts.append(f"Internship: {intern}")
            if parts:
                return f"Unga career details: {', '.join(parts)}."

        # 21. Open-Domain: Projects
        if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in ("project", "side project", "current project")) or ("what project" in q_clean or "endha project" in q_clean):
            proj = self.get_profile_fact("current_project")
            dec = self.get_profile_fact("project_decision")
            if proj or dec:
                p_items = []
                if proj: p_items.append(f"Project: {proj}")
                if dec: p_items.append(f"Decision/Goal: {dec}")
                return f"Unga project details: {', '.join(p_items)}."

        # 22. Open-Domain: Hobbies & Free-time interests
        if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in ("hobby", "hobbies", "free time", "leisure")) or ("what are my hobbies" in q_clean or "enoda hobby" in q_clean):
            hobbies = self.get_profile_fact("hobbies")
            music = self.get_profile_fact("favorite_music")
            parts = []
            if hobbies: parts.append(f"Hobbies: {hobbies}")
            if music: parts.append(f"Favorite music: {music}")
            if parts:
                return f"Unga interests & hobbies: {', '.join(parts)}."

        # 23. Open-Domain: Goals & Ambitions
        if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in ("goal", "goals", "ambition", "target", "aim", "lakshiyam")) or ("what is my goal" in q_clean or "en goal" in q_clean):
            g = self.get_profile_fact("career_goal")
            if g:
                return f"Unga goal: {g}."

        # 24. Open-Domain: Challenges & Problems
        if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in ("challenge", "challenges", "struggle", "struggling", "problem", "kashtam", "difficulty")):
            ch = self.get_profile_fact("current_challenge")
            if ch:
                return f"Neenga face panra challenge: {ch}."

        # 25. Open-Domain: Tasks & Commitments
        if any(re.search(rf"\b{re.escape(w)}\b", q_clean) for w in ("task", "tasks", "pending", "commitment", "commitments", "unresolved")) or ("what do i need to do" in q_clean or "enna pannanum" in q_clean):
            active_tasks = self.get_active_tasks(profile_id=p_id)
            if active_tasks:
                t_list = [t.get("description", "") for t in active_tasks if t.get("description")]
                return f"Unga pending tasks: {', '.join(t_list)}."
            p_task = self.get_profile_fact("pending_task")
            if p_task:
                return f"Unga pending task: {p_task}."
            return "Active pending tasks edhuvum illa."

        # 26. Semantic Concept Search
        matches = self.search_relevant_memories(query=query, profile_id=p_id, top_k=1)
        if matches:
            m = matches[0]
            k = m.get("key", "").replace("_", " ")
            v = m.get("value", "")
            k_tokens = [tok for tok in re.findall(r"\w+", k.lower()) if len(tok) >= 3 and tok not in self._STOPWORDS]
            v_tokens = [tok for tok in re.findall(r"\w+", v.lower()) if len(tok) >= 3 and tok not in self._STOPWORDS]
            if (k_tokens and any(kt in q_clean for kt in k_tokens)) or (v_tokens and any(vt in q_clean for vt in v_tokens)):
                return f"Neenga sonnadhu ({k}): {v}."

        # 27. Conversation Archive Search Fallback (Lifelong continuity)
        archive_hits = self.search_conversation_archive(query=query, profile_id=p_id, top_k=2)
        if archive_hits:
            hit_texts = []
            for h in archive_hits:
                u_cmd = (h.get("user_command") or "").strip()
                if u_cmd and len(u_cmd) > 3 and u_cmd.lower() not in q_clean and q_clean not in u_cmd.lower():
                    hit_texts.append(f"'{u_cmd}'")
            if hit_texts:
                return f"Previous conversation record-la neenga sonnadhu: {', '.join(hit_texts[:2])}."

        if matches:
            m = matches[0]
            k = m.get("key", "").replace("_", " ")
            v = m.get("value", "")
            return f"Neenga sonnadhu ({k}): {v}."

        return None

    # ==================================================
    # 2. EPISODIC MEMORY (Significant Events & Stories)
    # ==================================================

    def add_episode(
        self,
        summary: str,
        emotional_valence: float = 0.5,
        category: str = "conversation",
        importance: int = 3,
    ) -> bool:
        """
        Add an episodic memory record with importance rating and enforce max 200 limit.
        """
        summary_clean = str(summary or "").strip()
        if not summary_clean:
            return False

        if self.contains_sensitive_data(summary_clean):
            return False

        try:
            success = self.db.add_memory_episode(
                summary=summary_clean,
                emotional_valence=emotional_valence,
                category=category,
                importance=importance,
            )
            self.db.prune_memory_episodes(max_records=self.max_episodes)
            return success
        except Exception as error:
            print(f"[MEMORY] Add episode error: {error}")
            return False

    def get_salient_episodes(self, limit: int = 5) -> List[str]:
        """
        Fetch the most important and recent episodic memories for prompt injection.
        """
        try:
            fetch_limit = max(10, limit * 2)
            recent_rows = self.db.get_recent_episodes(limit=fetch_limit)
            important_rows = self.db.get_important_episodes(min_importance=3, limit=fetch_limit)

            episodes = []
            seen = set()

            # First priority: recent episodes with importance >= 3
            for row in recent_rows:
                importance = row[5] if len(row) > 5 else 3
                summary = row[2] if len(row) > 2 else ""
                if summary and importance >= 3 and summary not in seen:
                    seen.add(summary)
                    episodes.append(str(summary))
                if len(episodes) >= limit:
                    break

            # Secondary priority: highest importance episodes if slots remain
            if len(episodes) < limit:
                for row in important_rows:
                    summary = row[2] if len(row) > 2 else ""
                    if summary and summary not in seen:
                        seen.add(summary)
                        episodes.append(str(summary))
                    if len(episodes) >= limit:
                        break

            return episodes
        except Exception as error:
            print(f"[MEMORY] Get salient episodes error: {error}")
            return []

    # ==================================================
    # 3. SEMANTIC & PROFILE MEMORY (Facts & Preferences)
    # ==================================================

    def set_profile_fact(
        self,
        key: str,
        value: Any,
        category: str = "preference",
        source: str = "explicit_user",
        importance: int = 3,
        source_turn_id: Optional[str] = None,
        memory_id: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> bool:
        """
        Persists a user profile fact into user_context table and personal_memories.
        """
        key_clean = str(key or "").strip().lower()
        val_clean = str(value or "").strip()

        if not key_clean or not val_clean:
            return False

        if self.contains_sensitive_data(val_clean) or self.contains_sensitive_data(key_clean) or key_clean in ("password", "passwd", "pwd", "otp", "pin", "api_key", "secret", "token", "cvv") or "[REDACTED" in val_clean:
            print(f"[MEMORY SAFETY] Refusing to persist sensitive key/value: {key_clean}")
            return False

        p_id = str(profile_id or getattr(self, "profile_id", "default") or "default")

        if key_clean in ("user_name", "preferred_user_name"):
            return self.set_user_name_preference(
                preferred_name=val_clean,
                use_name=True,
                source=source,
                profile_id=p_id,
            )

        try:
            ok = True
            if p_id == "default":
                ok = self.db.set_user_context(
                    key_clean, val_clean, category=category, source=source, importance=importance
                )
            m_id = memory_id or f"mem_{key_clean}_{int(time.time() * 1000)}"
            self.db.add_personal_memory(
                memory_id=m_id,
                category=category,
                key=key_clean,
                value=val_clean,
                source_turn_id=source_turn_id,
                confidence="high" if source == "explicit_user" else "medium",
                profile_id=p_id,
            )
            print(f"[MEMORY] Memory committed: id={m_id} key={key_clean} category={category} (provenance={source_turn_id}) profile={p_id}")
            return ok
        except Exception as error:
            print(f"[MEMORY] Set profile fact error: {error}")
            return False

    def get_profile_fact(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a user profile fact scoped to active profile.
        Filters out invalid/corrupted records and falls back to legitimate prior memories.
        """
        try:
            k_clean = str(key or "").strip().lower()
            p_id = getattr(self, "profile_id", "default")
            p_mems = self.db.get_personal_memories(key=k_clean, active_only=True, profile_id=p_id)
            for m in p_mems:
                val = m.get("value")
                if self._is_valid_fact_value(k_clean, val):
                    return val

            # If no active memories are valid, check non-retracted records (prior valid memories)
            all_mems = self.db.get_personal_memories(key=k_clean, active_only=False, profile_id=p_id)
            for m in all_mems:
                if m.get("status") != "retracted":
                    val = m.get("value")
                    if self._is_valid_fact_value(k_clean, val):
                        return val

            if p_id == "default":
                uc_val = self.db.get_user_context(k_clean, default=default)
                if self._is_valid_fact_value(k_clean, uc_val):
                    return uc_val
            return default
        except Exception as error:
            print(f"[MEMORY] Get profile fact error: {error}")
            return default

    def get_all_profile_facts(self) -> Dict[str, str]:
        """
        Returns all stored user context key-values as a dictionary,
        ensuring only valid factual entries are surfaced.
        """
        try:
            rows = self.db.get_all_user_context()
            facts = {}
            for row in rows:
                k, v, _ = row
                if self._is_valid_fact_value(k, v):
                    facts[k] = v

            # Overlay valid facts from personal_memories
            p_id = getattr(self, "profile_id", "default")
            active_mems = self.db.get_personal_memories(active_only=True, profile_id=p_id)
            for m in reversed(active_mems):
                k = m.get("key")
                v = m.get("value")
                if k and self._is_valid_fact_value(k, v):
                    facts[k] = v

            # Recover key facts if active record was suppressed
            for critical_key in ("college", "degree", "academic_year", "job_role", "company", "current_project"):
                if critical_key not in facts:
                    fact_val = self.get_profile_fact(critical_key)
                    if fact_val:
                        facts[critical_key] = fact_val

            return facts
        except Exception as error:
            print(f"[MEMORY] Get all profile facts error: {error}")
            return {}

    # ==================================================
    # MEMORY EXTRACTION PIPELINE
    # ==================================================

    def extract_memories_from_turn(
        self,
        user_text: str,
        assistant_text: str = "",
        intent: str = "conversation",
        source_turn_id: Optional[str] = None,
    ) -> List[str]:
        """
        Lightweight heuristic extraction for user profile facts, relationships,
        identity, and episodic events. Runs locally in < 1 ms without external LLM calls.
        Returns list of created/updated memory IDs.
        """
        extracted_ids: List[str] = []
        if not user_text:
            return extracted_ids

        # SENSITIVE DATA SANITIZATION: Redact secrets and continue safe fact extraction
        sanitized_user, had_secrets = self.redact_sensitive_data(user_text)
        if had_secrets:
            print(f"[MEMORY SAFETY] Sensitive credential pattern detected and redacted during memory extraction: turn_id={source_turn_id}")

        print(f"[MEMORY] Memory extraction started: turn_id={source_turn_id}")
        lower_user = sanitized_user.lower().strip()

        # ----------------------------------------------
        # 1. User Name Rejection / Opt-Out Check
        # ----------------------------------------------
        rejection_patterns = [
            r"\b(?:don't|dont|do not)\s+call\s+me\b",
            r"\b(?:don't|dont|do not)\s+use\s+my\s+name\b",
            r"\b(?:don't|dont|do not)\s+address\s+me\b",
            r"\bstop\s+calling\s+me\b",
            r"\bno\s+need\s+to\s+call\s+me\b",
            r"\b(?:[a-zA-Z]+\s+)?nu\s+(?:koopdatha|koopadaadha|koopadatheenga)\b",
            r"\b(?:en\s+)?peru\s+use\s+panna\s+(?:vendam|vaendam|koodadhu)\b",
            r"\benna\s+name\s+vechu\s+koopdatha\b",
            r"\bname\s+use\s+panna\s+(?:vendam|vaendam|koodadhu)\b",
            r"\bname\s+solla\s+(?:vendam|vaendam|koodadhu)\b",
            r"\bname\s+koopdatha\b",
        ]
        if any(re.search(pat, lower_user) for pat in rejection_patterns):
            self.set_user_name_preference(preferred_name=None, use_name=False)
            mem_id = f"mem_optout_{int(time.time() * 1000)}"
            self.db.add_personal_memory(
                memory_id=mem_id,
                category="preference",
                key="use_preferred_name",
                value="False",
                source_turn_id=source_turn_id,
                confidence="high"
            )
            print(f"[MEMORY] Memory committed: id={mem_id} key=use_preferred_name category=preference (provenance={source_turn_id})")
            extracted_ids.append(mem_id)
            self.add_episode(
                summary="User requested not to be addressed by name",
                emotional_valence=0.5,
                category="preference",
                importance=4,
            )
            return extracted_ids

        # ----------------------------------------------
        # 2. "FORGET THIS" COMMAND CHECK
        # ----------------------------------------------
        forget_patterns = [
            r"\b(?:forget\s+that|forget\s+my|don't\s+remember\s+this|dont\s+remember\s+this)\s+(.+)",
            r"\b(?:idha\s+memory\s+la\s+irundhu\s+remove\s+pannu|marandhudu|marandhiru)\b",
            r"\bforget\s+(?:that|this|it)\b",
        ]
        for pat in forget_patterns:
            f_match = re.search(pat, lower_user)
            if f_match:
                payload = f_match.group(1).strip() if f_match.groups() else lower_user
                self.forget_memory(payload)
                return extracted_ids

        # ----------------------------------------------
        # 3. "REMEMBER THIS" COMMAND CHECK
        # ----------------------------------------------
        recall_intent_patterns = [
            r"\b(?:what\s+you\s+remember|what\s+do\s+you\s+remember|what\s+did\s+you\s+remember)\b",
            r"\b(?:tell\s+me\s+what\s+you\s+remember|tell\s+me\s+what\s+you\s+know)\b",
            r"\b(?:do\s+you\s+remember|can\s+you\s+remember|did\s+you\s+remember)\b",
            r"\b(?:remember\s+pandriya|remember\s+panriya|remember\s+irukka|remember\s+pannitiya)\b",
            r"\b(?:i\s+don't\s+remember|i\s+dont\s+remember|naan\s+marandhuten)\b",
        ]
        is_recall_query = any(re.search(pat, user_text, re.IGNORECASE) for pat in recall_intent_patterns)

        remember_patterns = [
            r"^\s*(?:please\s+|kindly\s+)?remember\s+(?:that\s+)?(.+)",
            r"\b(?:please\s+|kindly\s+)?remember\s+that\s+(.+)",
            r"\b(?:remember\s+this[:,\s]+)(.+)",
            r"\bidha\s+remember\s+panniko[,\s]+(.+)",
            r"\bidha\s+memory\s+la\s+vechuko[,\s]+(.+)",
            r"\b(?:ஞாபகம்\s+வச்சுக்கோ|நோட்\s+பண்ணிக்கோ)[,\s]+(.+)",
        ]
        is_explicit_remember = False
        remember_payload = ""
        if not is_recall_query:
            for pat in remember_patterns:
                r_match = re.search(pat, user_text, re.IGNORECASE)
                if r_match:
                    is_explicit_remember = True
                    remember_payload = r_match.group(1).strip()
                    break

        # SPEECH ACT DISCRIMINATION: If user is asking a question/query and didn't explicitly instruct to remember,
        # do not extract declarative facts from the question (prevents questions from being stored as facts).
        if not is_explicit_remember and self._is_query_or_question(sanitized_user):
            print(f"[MEMORY] Utterance is a question/query without explicit remember directive. Skipping fact extraction: turn_id={source_turn_id}")
            return extracted_ids

        # SPEECH ACT DISCRIMINATION: If utterance is hypothetical or uncertain, skip fact extraction.
        if not is_explicit_remember and self._is_hypothetical_or_uncertain(sanitized_user):
            print(f"[MEMORY] Utterance is hypothetical or uncertain. Skipping fact extraction: turn_id={source_turn_id}")
            return extracted_ids

        # ----------------------------------------------
        # 4. CREATOR & SELF-IDENTIFICATION
        # ----------------------------------------------
        # Exclude pure 3rd-person metadata statements
        third_person_metadata = [
            r"\b(?:naresh\s+project\s+creator|created\s+by\s+naresh|developer:\s*naresh)\b",
            r"\b(?:naresh\s+branch|naresh\s+code|naresh's\s+laptop|ragavendhiran's\s+laptop)\b",
        ]
        is_third_person = any(re.search(pat, lower_user) for pat in third_person_metadata)

        if not is_third_person:
            # A. Combined Name + Creator
            combined_creator_patterns = [
                r"\b(?:i am|i'm)\s+naresh[,\s]+(?:and\s+)?(?:i am\s+)?(?:your\s+)?creator\b",
                r"\b(?:i am|i'm)\s+naresh[,\s]+i\s+created\s+you\b",
                r"\bnaan\s+naresh[,\s]+(?:naan\s+than\s+)?(?:unnoda|unga)\s+creator\b",
                r"\bnaan\s+than\s+(?:ungaloda|unnoda)\s+creator[,\s]+(?:en\s+peru\s+)?naresh\b",
                r"\bnaresh\s+naan\s+than[,\s]+unna\s+create\s+pannavan\b",
            ]
            if any(re.search(pat, lower_user) for pat in combined_creator_patterns):
                self.establish_speaker_identity("Naresh", relationship="creator", source="explicit_user", confidence="high")
                mem_id = f"mem_creator_naresh_{int(time.time() * 1000)}"
                self.db.add_personal_memory(
                    memory_id=mem_id,
                    category="identity",
                    key="creator",
                    value="Naresh",
                    source_turn_id=source_turn_id,
                    confidence="high"
                )
                print(f"[MEMORY] Memory committed: id={mem_id} key=creator category=identity (provenance={source_turn_id})")
                extracted_ids.append(mem_id)
                self.add_episode(
                    summary="User established identity as Naresh (creator of DHEEPTHI-AI)",
                    emotional_valence=0.8,
                    category="identity",
                    importance=5,
                )
            else:
                # B. Creator-only claim
                creator_claim_patterns = [
                    r"\b(?:i am|i'm)\s+(?:your\s+creator|the\s+one\s+who\s+created\s+you)\b",
                    r"\bi\s+created\s+you\b",
                    r"\bnaan\s+than\s+(?:ungaloda|unnoda|un)\s+creator\b",
                    r"\bnaan\s+than\s+unna\s+create\s+pannavan\b",
                    r"\bnaan\s+unna\s+create\s+panninen\b",
                    r"\bnaan\s+dheepthi-?ai\s+create\s+pannavan\b",
                    r"\bnaan\s+un\s+creator\b",
                ]
                if any(re.search(pat, lower_user) for pat in creator_claim_patterns):
                    self.set_creator_relationship(is_creator=True, source="explicit_user", confidence="high")
                    mem_id = f"mem_creator_rel_{int(time.time() * 1000)}"
                    self.db.add_personal_memory(
                        memory_id=mem_id,
                        category="identity",
                        key="creator_relationship",
                        value="creator",
                        source_turn_id=source_turn_id,
                        confidence="high"
                    )
                    print(f"[MEMORY] Memory committed: id={mem_id} key=creator_relationship category=identity (provenance={source_turn_id})")
                    extracted_ids.append(mem_id)
                    self.add_episode(
                        summary="User explicitly established creator relationship",
                        emotional_valence=0.8,
                        category="identity",
                        importance=5,
                    )
                else:
                    # C. Self-identification by Name
                    name_self_id_patterns = [
                        r"\b(?:my name is|call me|you can call me)\s+([A-Za-z\u0B80-\u0BFF]{2,20})\b",
                        r"\b(?:en peru|ennoda peru|en peyar)\s+(?:is\s+)?([A-Za-z\u0B80-\u0BFF]{2,20})\b",
                        r"(?:மை\s+நேம்\s+இஸ்|என்\s+பெயர்\s+(?:இஸ்\s+)?|என்\s+பேரு\s+(?:இஸ்\s+)?)\s*([A-Za-z\u0B80-\u0BFF]{2,20})",
                        r"\b([A-Za-z\u0B80-\u0BFF]{2,20})\s+nu\s+(?:koopdu|koopdalam)\b",
                        r"\bnaan\s+(?:than|dhaan)\s+([A-Za-z\u0B80-\u0BFF]{2,20})\b",
                        r"\b([A-Za-z\u0B80-\u0BFF]{2,20})\s+naan\s+(?:than|dhaan)\b",
                        r"\b(?:i am|i'm)\s+([A-Za-z\u0B80-\u0BFF]{2,20})(?:[,\.!\?]|\s*$)",
                    ]
                    for pat in name_self_id_patterns:
                        match = re.search(pat, user_text, re.IGNORECASE)
                        if match:
                            cand = match.group(1).strip()
                            tamil_name_map = {
                                "நரேஷ்": "Naresh",
                                "செந்தில்நாதன்": "Senthilnathan",
                                "சங்கீதா": "Sangeetha",
                                "தீபேஷ்": "Deepesh",
                                "தீபேஸ்": "Deepesh",
                                "ராகவேந்திரன்": "Ragavendhiran",
                                "விக்னேஷ்": "Vignesh",
                                "அருண்": "Arun",
                                "கார்த்திக்": "Karthik",
                                "ராகுல்": "Rahul",
                            }
                            if cand in tamil_name_map:
                                clean_cand = tamil_name_map[cand]
                            elif cand[0].isascii():
                                clean_cand = cand[0].upper() + cand[1:]
                            else:
                                clean_cand = cand
                            reserved = (
                                "dheepthi", "deepthi", "ai", "user", "laptop", "creator",
                                "developer", "computer", "bro", "nanba", "machi", "boss",
                                "thala", "thalaivi", "sir", "fine", "good", "bad", "tired",
                                "busy", "happy", "sad", "name", "peru", "none", "null",
                                "working", "work", "trying", "doing", "going", "playing",
                                "using", "testing", "reading", "learning", "listening",
                                "asking", "talking", "here", "ready", "online", "back",
                                "sure", "sorry", "okay", "ok", "just", "not", "the",
                                "your", "vandhen", "vandhuten", "vara", "poren", "solren",
                                "panren", "iruken", "padikiren", "vani", "vaani", "ஓகே"
                            )
                            cand_low = clean_cand.lower()
                            if (
                                cand_low not in reserved
                                and len(clean_cand) >= 2
                                and not cand_low.endswith(("ing", "ed"))
                            ):
                                is_cr = (clean_cand in self.STATIC_CREATORS)
                                self.establish_speaker_identity(
                                    clean_cand,
                                    relationship="creator" if is_cr else "user",
                                    source="explicit_user",
                                    confidence="high",
                                    profile_id=getattr(self, "profile_id", "default"),
                                )
                                self.db.set_user_context("use_preferred_name", "True")
                                self.db.deactivate_personal_memory(key="use_preferred_name", profile_id=getattr(self, "profile_id", "default"))
                                mem_id = f"mem_ident_{clean_cand.lower()}_{int(time.time() * 1000)}"
                                self.db.add_personal_memory(
                                    memory_id=mem_id,
                                    category="identity",
                                    key="preferred_user_name",
                                    value=clean_cand,
                                    source_turn_id=source_turn_id,
                                    confidence="high",
                                    profile_id=getattr(self, "profile_id", "default"),
                                )
                                print(f"[MEMORY] Memory committed: id={mem_id} key=preferred_user_name category=identity (provenance={source_turn_id})")
                                extracted_ids.append(mem_id)
                                self.add_episode(
                                    summary=f"User introduced their identity as {clean_cand}" + (" (creator)" if is_cr else ""),
                                    emotional_valence=0.7,
                                    category="identity",
                                    importance=4,
                                )
                                break

        # ----------------------------------------------
        # 5. RELATIONSHIPS, FAMILY & EXPLICIT CORRECTIONS
        # ----------------------------------------------
        rel_key_map = {
            "father": "father", "dad": "father", "appa": "father", "அப்பா": "father", "தகப்பனார்": "father", "தந்தை": "father", "பாதர்": "father",
            "mother": "mother", "mom": "mother", "amma": "mother", "அம்மா": "mother", "தாய்": "mother", "மதர்": "mother", "மம்மி": "mother",
            "brother": "brother", "anna": "brother", "thambi": "brother", "annan": "brother",
            "அண்ணன்": "brother", "தம்பி": "brother", "சகோதரன்": "brother", "பிரதர்": "brother",
            "sister": "sister", "akka": "sister", "thangachi": "sister", "thangai": "sister",
            "அக்கா": "sister", "தங்கை": "sister", "சகோதரி": "sister", "சிஸ்டர்": "sister",
            "friend": "friend", "nanban": "friend", "dost": "friend", "நண்பன்": "friend", "தோழன்": "friend", "பிரண்ட்": "friend",
            "wife": "wife", "manaivi": "wife", "மனைவி": "wife", "ஒய்ஃப்": "wife",
            "husband": "husband", "kanavan": "husband", "கணவன்": "husband", "ஹஸ்பண்ட்": "husband",
            "son": "son", "paiyan": "son", "magan": "son", "மகன்": "son", "சன்": "son",
            "daughter": "daughter", "ponnu": "daughter", "magal": "daughter", "மகள்": "daughter", "டாட்டர்": "daughter",
        }

        # A. Explicit corrections check
        correction_patterns = [
            r"\bactually\s+(?:my\s+)?(father|dad|mother|mom|brother|sister|friend|wife|husband|son|daughter)(?:'s)?\s+(?:is\s+not|isn't|name\s+is\s+not)\s+([A-Za-z\u0B80-\u0BFF]{2,30})[,\s]+(?:it\s+is|it's|he\s+is|she\s+is|is|name\s+is\s+)?\s*([A-Za-z\u0B80-\u0BFF]{2,30})\b",
            r"\b(?:actually\s+)?en\s+(brother|anna|thambi|sister|akka|thangachi|thangai|appa|amma|friend|nanban|wife|husband)\s+(?:peru\s+)?([A-Za-z\u0B80-\u0BFF]{2,30})\s+(?:illa|kedayathu)[,\s]+(?:peru\s+)?([A-Za-z\u0B80-\u0BFF]{2,30})\b",
        ]
        correction_matched = False
        for c_pat in correction_patterns:
            c_match = re.search(c_pat, user_text, re.IGNORECASE)
            if c_match:
                raw_rel = c_match.group(1).lower()
                old_n = c_match.group(2).strip().capitalize()
                new_n = c_match.group(3).strip().capitalize()
                rel_key = rel_key_map.get(raw_rel, raw_rel)
                if len(new_n) >= 2 and new_n.lower() not in ("name", "peru", "illa", "is", "a", "the", "my"):
                    self.add_known_person(
                        name=new_n,
                        relationship_to_primary_user=rel_key,
                        relationship_to_dheepthi=rel_key,
                        voice_profile_id=new_n.lower(),
                        notes=f"User's {rel_key} (corrected from {old_n})",
                        source="explicit_user",
                        confidence="high",
                    )
                    mem_id = f"mem_rel_{rel_key}_{int(time.time() * 1000)}"
                    self.db.add_personal_memory(
                        memory_id=mem_id,
                        category="relationships",
                        key=rel_key,
                        value=new_n,
                        source_turn_id=source_turn_id,
                        confidence="high",
                        status="active",
                        profile_id=getattr(self, "profile_id", "default")
                    )
                    print(f"[MEMORY CORRECTION] Relationship {rel_key} updated: {old_n} -> {new_n} (turn_id={source_turn_id})")
                    extracted_ids.append(mem_id)
                    self.add_episode(
                        summary=f"User corrected their {rel_key}: not {old_n}, but {new_n}",
                        emotional_valence=0.7,
                        category="relationships",
                        importance=4,
                    )
                    correction_matched = True
                    break

        if not correction_matched:
            # B. Standard & Multi-relationship extraction
            reserved_rel_words = {
                "name", "peru", "is", "a", "the", "my", "father", "mother",
                "brother", "sister", "friend", "wife", "husband", "son", "daughter",
                "appa", "amma", "anna", "thambi", "akka", "thangachi", "nanban",
                "dhaan", "illa", "kedayathu", "and", "details", "these", "three",
                "following", "are", "per", "enna", "pathiyum", "solren", "sonnen",
                "பெயர்", "மற்றும்", "ஓகே", "ஆப்", "டெக்னாலஜி", "செகண்ட்", "இயர்",
                "காலேஜ்", "கல்லூரி", "இன்", "student", "studying", "degree", "அப்டேட்", "பண்ணிக்கோ"
            }

            tamil_name_translit = {
                "செந்தில்நாதன்": "Senthilnathan",
                "சங்கீதா": "Sangeetha",
                "தீபேஷ்": "Deepesh",
                "தீபேஸ்": "Deepesh",
                "நரேஷ்": "Naresh",
                "ராகவேந்திரன்": "Ragavendhiran",
                "விக்னேஷ்": "Vignesh",
                "அருண்": "Arun",
                "கார்த்திக்": "Karthik",
                "ராகுல்": "Rahul",
            }

            extracted_relations = set()

            # Pattern 1: Colon / separator style (e.g. "Father: Senthilnathan", "Brother: Deepesh")
            colon_pat = r"(?i)\b(" + "|".join(re.escape(k) for k in rel_key_map.keys()) + r")\s*[:=-]\s*(?:[A-Za-z\u0B80-\u0BFF]{1,4}[\.\s]+)?([A-Za-z\u0B80-\u0BFF]{2,30})"
            for m in re.finditer(colon_pat, user_text):
                raw_rel = m.group(1).lower()
                cand_name = m.group(2).strip()
                rel_key = rel_key_map.get(raw_rel, raw_rel)
                if cand_name.lower() not in reserved_rel_words and len(cand_name) >= 2:
                    if cand_name in tamil_name_translit:
                        clean_name = tamil_name_translit[cand_name]
                    elif cand_name[0].isascii():
                        clean_name = cand_name[0].upper() + cand_name[1:]
                    else:
                        clean_name = cand_name
                    extracted_relations.add((rel_key, clean_name))

            # Pattern 2: "my father is Senthilnathan", "en appa Senthilnathan", "brother is Deepesh", "மை பாதர் நேம் இஸ் ஜி செந்தில்நாதன்"
            phrase_pat = (
                r"(?i)(?:my\s+|en\s+|ennoda\s+|our\s+|மை\s+|என்\s+|என்னோட\s+|எங்க\s+)?("
                + "|".join(re.escape(k) for k in rel_key_map.keys())
                + r")(?:['’]s)?\s+(?:name\s+is\s+|peru\s+is\s+|peru\s+|is\s+|பெயர்\s+(?:இஸ்\s+|ஆகும்\s+)?|நேம்\s+இஸ்\s+|நேம்\s+|பேர்\s+is\s+|dhaan\s+)?"
                + r"(?:[A-Za-z\u0B80-\u0BFF]{1,4}[\.\s]+)?([A-Za-z\u0B80-\u0BFF]{2,30})"
            )
            for m in re.finditer(phrase_pat, user_text):
                raw_rel = m.group(1).lower()
                cand_name = m.group(2).strip()
                rel_key = rel_key_map.get(raw_rel, raw_rel)
                if cand_name.lower() not in reserved_rel_words and len(cand_name) >= 2 and cand_name.lower() not in rel_key_map:
                    if cand_name in tamil_name_translit:
                        clean_name = tamil_name_translit[cand_name]
                    elif cand_name[0].isascii():
                        clean_name = cand_name[0].upper() + cand_name[1:]
                    else:
                        clean_name = cand_name
                    extracted_relations.add((rel_key, clean_name))

            # Pattern 3: "Senthilnathan is my father", "Deepesh is my brother"
            reverse_pat = (
                r"(?i)\b([A-Za-z\u0B80-\u0BFF]{2,30})\s+(?:is\s+my|dhaan\s+en)\s+("
                + "|".join(re.escape(k) for k in rel_key_map.keys())
                + r")\b"
            )
            for m in re.finditer(reverse_pat, user_text):
                cand_name = m.group(1).strip()
                raw_rel = m.group(2).lower()
                rel_key = rel_key_map.get(raw_rel, raw_rel)
                if cand_name.lower() not in reserved_rel_words and len(cand_name) >= 2:
                    if cand_name in tamil_name_translit:
                        clean_name = tamil_name_translit[cand_name]
                    elif cand_name[0].isascii():
                        clean_name = cand_name[0].upper() + cand_name[1:]
                    else:
                        clean_name = cand_name
                    extracted_relations.add((rel_key, clean_name))

            # Commit all extracted relations
            for rel_k, p_name in sorted(extracted_relations):
                self.add_known_person(
                    name=p_name,
                    relationship_to_primary_user=rel_k,
                    relationship_to_dheepthi=rel_k,
                    voice_profile_id=p_name.lower(),
                    notes=f"User's {rel_k}",
                    source="explicit_user",
                    confidence="high",
                )
                mem_id = f"mem_rel_{p_name.lower()}_{int(time.time() * 1000)}"
                self.db.add_personal_memory(
                    memory_id=mem_id,
                    category="relationships",
                    key=rel_k,
                    value=p_name,
                    source_turn_id=source_turn_id,
                    confidence="high",
                    status="active",
                    profile_id=getattr(self, "profile_id", "default")
                )
                print(f"[MEMORY] Memory committed: id={mem_id} key={rel_k} category=relationships (provenance={source_turn_id})")
                extracted_ids.append(mem_id)
                self.add_episode(
                    summary=f"User mentioned their {rel_k} is {p_name}",
                    emotional_valence=0.7,
                    category="relationships",
                    importance=4,
                )

        # ----------------------------------------------
        # 6. PROFILE FACT: LANGUAGE PREFERENCES
        # ----------------------------------------------
        lang_target = remember_payload if is_explicit_remember else lower_user
        if "tanglish" in lang_target and any(w in lang_target for w in ("prefer", "comfortable", "like", "pesu", "pidikkum", "remember")):
            mem_id = f"mem_lang_{int(time.time() * 1000)}"
            self.set_profile_fact("preferred_language", "Tanglish", category="preference", source="explicit_user", importance=5 if is_explicit_remember else 4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
            if is_explicit_remember:
                self.add_episode("User requested to remember Tanglish as preferred language", 0.7, "preference", 5)
        elif "english" in lang_target and any(w in lang_target for w in ("prefer", "speak", "pesu")):
            mem_id = f"mem_lang_{int(time.time() * 1000)}"
            self.set_profile_fact("preferred_language", "English", category="preference", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
        elif "tamil" in lang_target and any(w in lang_target for w in ("prefer", "pesu")):
            mem_id = f"mem_lang_{int(time.time() * 1000)}"
            self.set_profile_fact("preferred_language", "Tamil", category="preference", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)

        # ----------------------------------------------
        # 7. PROFILE FACT: FAVORITE MUSIC / ARTIST
        # ----------------------------------------------
        music_patterns = [
            r"\b(?:enaku|enoda|my)\s+(?:fav|favorite|favourite)\s+(?:song|music|singer|hero)\s+(?:is|dhaan)?\s+([a-zA-Z0-9\s\.\-_']{2,40})",
            r"\b([a-zA-Z0-9\s\.\-_']{2,40})\s+(?:song|paattu|music)\s+romba\s+pidikkum\b",
        ]
        for pat in music_patterns:
            m_match = re.search(pat, user_text, re.IGNORECASE)
            if m_match:
                music_val = m_match.group(1).strip()
                if len(music_val) > 2:
                    mem_id = f"mem_music_{int(time.time() * 1000)}"
                    self.set_profile_fact("favorite_music", music_val, category="interest", source="explicit_user", source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    break

        # ----------------------------------------------
        # 8. PROFILE FACT: PROJECT CONTEXT & INTERESTS
        # ----------------------------------------------
        proj_match = re.search(r"\b(?:working on|project)\s+([A-Za-z0-9\-_]+(?:\s+[A-Za-z0-9\-_]+)?)", user_text, re.IGNORECASE)
        if proj_match:
            raw_p_val = proj_match.group(1).strip()
            p_val = re.sub(r"^(?:is|are|was|am)\s+", "", raw_p_val, flags=re.IGNORECASE).strip()
            if self._is_valid_fact_value("current_project", p_val):
                mem_id = f"mem_proj_{int(time.time() * 1000)}"
                self.set_profile_fact("current_project", p_val, category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                extracted_ids.append(mem_id)
                self.add_episode(f"User mentioned working on project {p_val}", 0.7, "work", 4)
        elif any(w in lower_user or (assistant_text and w in assistant_text.lower()) for w in ("symphowork", "simple work", "zoho people")):
            p_val = "SymphoWork"
            mem_id = f"mem_proj_{int(time.time() * 1000)}"
            self.set_profile_fact("current_project", p_val, category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
            self.add_episode("User mentioned working on SymphoWork project (organization management platform like Zoho People)", 0.7, "work", 4)
        elif "dheepthi-ai" in lower_user or ("dheepthi" in lower_user and ("project" in lower_user or "code" in lower_user or "work" in lower_user or "develop" in lower_user)):
            mem_id = f"mem_proj_{int(time.time() * 1000)}"
            self.set_profile_fact("current_project", "DHEEPTHI-AI", category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
            self.add_episode("User mentioned working on DHEEPTHI-AI", 0.7, "work", 4)

        if "react" in lower_user and ("next.js" in lower_user or "nextjs" in lower_user):
            mem_id = f"mem_tech_{int(time.time() * 1000)}"
            self.set_profile_fact("primary_technology", "React, Next.js", category="interest", source="explicit_user", source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
        elif "python" in lower_user and any(w in lower_user for w in ("use", "develop", "code", "panren", "working")):
            mem_id = f"mem_tech_{int(time.time() * 1000)}"
            self.set_profile_fact("primary_technology", "Python", category="interest", source="explicit_user", source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)

        # ----------------------------------------------
        # 9. EPISODIC MEMORY: CONFLICTS & RECONCILIATION
        # ----------------------------------------------
        if re.search(r"\b(sorry|mannichu|mannikavum)\b", lower_user):
            self.add_episode(
                summary="User apologized and reconciled after a misunderstanding",
                emotional_valence=0.7,
                category="conflict_resolution",
                importance=4,
            )
        elif re.search(r"\b(useless|waste|stupid|idiot|mental)\b", lower_user) and (
            re.search(r"\b(dheepthi|nee|you|un)\b", lower_user)
        ):
            self.add_episode(
                summary="User expressed frustration/insult toward Dheepthi",
                emotional_valence=0.2,
                category="conflict",
                importance=4,
            )
        elif re.search(r"\b(tired|exhausted|mudiyala|thalavali)\b", lower_user):
            self.add_episode(
                summary="User shared feeling tired or exhausted",
                emotional_valence=0.4,
                category="personal_share",
                importance=3,
            )

        # ----------------------------------------------
        # 10. INTERACTION HABITS: FREQUENT APPS
        # ----------------------------------------------
        if intent == "launch_application" and "target" in intent:
            target_app = lower_user.replace("open", "").replace("launch", "").replace("pannu", "").strip()
            if target_app:
                curr_apps = self.get_profile_fact("frequent_apps", "")
                app_list = [a.strip() for a in curr_apps.split(",") if a.strip()]
                if target_app not in app_list:
                    app_list.append(target_app)
                    mem_id = f"mem_app_{int(time.time() * 1000)}"
                    self.set_profile_fact("frequent_apps", ", ".join(app_list[-5:]), category="habit", source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)

        # ----------------------------------------------
        # 11. EDUCATION & ACADEMIC DETAILS
        # ----------------------------------------------
        def _clean_college(raw: str) -> str:
            if not raw:
                return ""
            c = raw.strip()
            # If contains question tokens, reject immediately
            if any(qw in c.lower() for qw in ("என்ன", "எந்த", "enna", "endha", "which", "what", "details", "course")):
                return ""
            # Strip trailing educational noise like 'la padikiren'
            c = re.sub(
                r"(?i)\s*(?:-?la|\s+la)?\s*(?:padikiren|padikkiren|padikiran|padikaren|padikrom|padikren|studying|la)?\s*(?:ok\s+va|okva|ஓகே)?[\.,!]*$",
                "",
                c,
            ).strip()
            # Strip leading noise
            c = re.sub(
                r"(?i)^(?:en\s+|ennoda\s+|my\s+|our\s+|இன்\s+|at\s+|in\s+)?(?:college\s+(?:peru\s+|name\s+is\s+|is\s+)?|கல்லூரி\s+)?",
                "",
                c,
            ).strip()
            # Canonicalize known Tamil college representations
            if ("சோனா" in c and ("காலேஜ்" in c or "கல்லூரி" in c)) or "sona" in c.lower():
                return "Sona College of Technology"
            return c

        def _clean_degree(raw: str) -> str:
            if not raw:
                return ""
            d = re.sub(
                r"(?i)\s*(?:-?la|\s+la)?\s*(?:padikiren|padikkiren|padikiran|padikaren|studying|degree|course)?\s*(?:[\.,!].*|\s+ok\s+va.*|\s+okva.*)?$",
                "",
                raw.strip(),
            ).strip()
            d = re.sub(
                r"(?i)^(?:en\s+|ennoda\s+|my\s+)?(?:degree\s+(?:is\s+)?|course\s+(?:is\s+)?|major\s+(?:is\s+)?|degree|course)\s*",
                "",
                d,
            ).strip()
            if d.upper() in ("எம்சிஏ", "MCA"):
                return "MCA"
            elif d.upper() in ("பிசிஏ", "BCA"):
                return "BCA"
            elif d.upper() in ("எம்பிஏ", "MBA"):
                return "MBA"
            return d

        # A. Degree / Course / Field of study (check known degrees first so they don't get swallowed)
        # Ambiguous 2-letter words 'BE' and 'ME' are protected so English pronouns like 'hear me' / 'tell me' never get extracted as a degree.
        known_degree_pat = r"\b(MCA|BCA|MBA|B\.?Tech|M\.?Tech|B\.?Sc|M\.?Sc|B\.?Com|M\.?Com|BBA|MBBS|BDS|B\.?Pharm|M\.?Pharm|PhD|Diploma|CSE|ECE|EEE|IT|Mechanical|Civil|எம்சிஏ|பிசிஏ|எம்பிஏ|பிஇ|எம்இ|பிடெக்|எம்டெக்|பிஎஸ்சி|எம்எஸ்சி|பிகாம்|டிப்ளமோ)\b"
        d_known = re.search(known_degree_pat, user_text, re.IGNORECASE)
        if not d_known:
            # Check BE / ME with periods or explicit educational context (case-insensitive)
            d_known = re.search(r"\b(B\.E\.|M\.E\.|(?:BE|ME)\s+(?:degree|course|padikiren|padikkiren))\b", user_text, re.IGNORECASE)
        if not d_known:
            # Check standalone uppercase BE or ME (strictly case-sensitive)
            d_known = re.search(r"\b(BE|ME)\b", user_text)

        if d_known:
            raw_d = d_known.group(1).strip()
            deg_val = re.sub(r"(?i)\s+(?:degree|course|padikiren|padikkiren)$", "", raw_d).strip().upper()
            if deg_val in ("எம்சிஏ", "MCA"):
                deg_val = "MCA"
            elif deg_val in ("பிசிஏ", "BCA"):
                deg_val = "BCA"
            elif deg_val in ("எம்பிஏ", "MBA"):
                deg_val = "MBA"
            mem_id = f"mem_edu_deg_{int(time.time() * 1000)}"
            self.set_profile_fact("degree", deg_val, category="education", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
        else:
            deg_patterns = [
                r"\b(?:doing|studying)\s+([A-Za-z0-9\s\.\-_]{2,30})\s+(?:degree|course)\b",
                r"\b(?:degree\s+is|course\s+is)\s+([A-Za-z0-9\s\.\-_]{2,30})\b",
                r"\b([A-Za-z0-9\s\.\-_]{2,30})\s+(?:degree|course)\s*(?:-?la|\s+la)?\s+(?:padikiren|padikkiren)\b",
                r"\bmy\s+(?:major|degree|course)\s+is\s+([A-Za-z0-9\s\.\-_]{2,30})\b",
            ]
            invalid_deg_words = (
                "a", "the", "my", "our", "well", "good", "padikiren", "college",
                "second year", "first year", "internship", "an internship", "project",
                "work", "job", "research", "course", "something", "an"
            )
            for pat in deg_patterns:
                d_match = re.search(pat, user_text, re.IGNORECASE)
                if d_match:
                    raw_deg = d_match.group(1).strip()
                    deg_name = _clean_degree(raw_deg)
                    if (
                        len(deg_name) >= 2
                        and deg_name.lower() not in invalid_deg_words
                        and not any(w in deg_name.lower() for w in ("internship", "project", "work", "job", "research"))
                    ):
                        mem_id = f"mem_edu_deg_{int(time.time() * 1000)}"
                        self.set_profile_fact("degree", deg_name, category="education", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        break

        # B. Department
        dept_pat = r"\b([A-Za-z0-9\s\.\-_]{2,30})\s+(?:department|dept)\b|\b(?:department|dept)\s+(?:is\s+)?([A-Za-z0-9\s\.\-_]{2,30})\b"
        dept_match = re.search(dept_pat, user_text, re.IGNORECASE)
        if dept_match:
            raw_dept = dept_match.group(1) or dept_match.group(2)
            if raw_dept:
                clean_dept = raw_dept.strip()
                if len(clean_dept) >= 2 and clean_dept.lower() not in ("a", "the", "my", "our", "which", "what", "endha", "enna"):
                    mem_id = f"mem_edu_dept_{int(time.time() * 1000)}"
                    self.set_profile_fact("department", clean_dept, category="education", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)

        # C. College / University
        edu_stop_words = "college|my|our|is|mca|bca|mba|be|me|year|yr|padikiren|studying|doing|in|at|na|ok|en|ennoda|first|second|third|fourth|final|i|am|currently|learning|எம்சிஏ|செகண்ட்|இயர்|வருடம்"
        col_patterns = [
            # Full institution name with College/Institute/University/Tech
            rf"\b((?:(?!(?:{edu_stop_words})\b)[A-Za-z0-9\-_]+\s+){{1,3}}(?:College(?:\s+of\s+[A-Za-z0-9\-_]+)?|Institute(?:\s+of\s+[A-Za-z0-9\-_]+)?|University|Tech))\b",
            # Tamil institution preceded by preposition (இன் / in / at)
            r"(?:(?:இன்|at|in)\s+)([A-Za-z0-9\u0B80-\u0BFF\-_]+(?:\s+[A-Za-z0-9\u0B80-\u0BFF\-_]+){0,3}\s+(?:கல்லூரி(?:யில்)?|காலேஜ்(?:\s+ஆப்\s+[A-Za-z0-9\u0B80-\u0BFF\-_]+)?(?:-?ல|\s+ல)?|பல்கலைக்கழகம்))",
            # Tamil institution bounded to start of clause
            r"(?:^|[\.,!\?\s])([A-Za-z0-9\u0B80-\u0BFF\-_]+(?:\s+[A-Za-z0-9\u0B80-\u0BFF\-_]+){0,2}\s+(?:கல்லூரி(?:யில்)?|காலேஜ்(?:\s+ஆப்\s+[A-Za-z0-9\u0B80-\u0BFF\-_]+)?(?:-?ல|\s+ல)?|பல்கலைக்கழகம்))",
            # Tamil 'இன் <கல்லூரி/ஊர்>' with educational context
            r"(?:செகண்ட்\s+இயர்|முதல்\s+வருடம்|படிக்கிறேன்|படிப்பு|padikiren|college)?\s*இன்\s+([A-Za-z0-9\u0B80-\u0BFF\s,]+?)(?:,\s*|\s+ஓகே|\s+ok|\.$|$)",
            # Explicit statement
            r"\b(?:studying\s+(?:at|in)|college\s+(?:is|name\s+is)?)\s+([A-Za-z0-9\s\.\-_]{2,50})",
            r"\b([A-Za-z0-9\s\.\-_]{2,40})\s+college(?:-?la|\s+la)?\s+(?:padikiren|padikiran|padikkiren)\b",
            r"\b(?:en\s+)?college\s+(?:peru\s+)?([A-Za-z0-9\s\.\-_]{2,40})\b",
        ]
        non_colleges = (
            "a", "the", "my", "our", "this", "some", "good", "bad", "name", "peru", "is", "college", "school",
            "of technology", "technology", "drawer", "third drawer", "the third drawer",
            "table", "room", "house", "veedu", "car", "bike", "keys", "lab keys"
        )
        for pat in col_patterns:
            c_match = re.search(pat, user_text, re.IGNORECASE)
            if c_match:
                raw_col = c_match.group(1).strip()
                col_name = _clean_college(raw_col)
                if (
                    len(col_name) >= 3
                    and col_name.lower() not in non_colleges
                    and not any(w in col_name.lower() for w in ("drawer", "keys", "table", "cupboard", "pocket", "bag"))
                ):
                    mem_id = f"mem_edu_col_{int(time.time() * 1000)}"
                    self.set_profile_fact("college", col_name, category="education", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    self.add_episode(f"User shared they study at {col_name}", 0.7, "education", 4)
                    break

        # D. Academic Year
        yr_patterns = [
            r"\b(1st|2nd|3rd|4th|first|second|third|final)\s+(?:yr|year)\b",
            r"(?:^|[\s,])(முதல்|இரண்டாம்|மூன்றாம்|நான்காம்|செகண்ட்|பைனல்)\s+(?:வருடம்|ஆண்டு|இயர்)(?:[\s,.]|$)",
        ]
        for y_pat in yr_patterns:
            yr_match = re.search(y_pat, user_text, re.IGNORECASE)
            if yr_match:
                raw_y = yr_match.group(0).strip().lower()
                if "1st" in raw_y:
                    yr_str = "1st year"
                elif "2nd" in raw_y:
                    yr_str = "2nd year"
                elif "3rd" in raw_y:
                    yr_str = "3rd year"
                elif "4th" in raw_y:
                    yr_str = "4th year"
                elif any(k in raw_y for k in ("first", "முதல்")):
                    yr_str = "First year"
                elif any(k in raw_y for k in ("second", "இரண்டாம்", "செகண்ட்")):
                    yr_str = "Second year"
                elif any(k in raw_y for k in ("third", "மூன்றாம்")):
                    yr_str = "Third year"
                elif any(k in raw_y for k in ("final", "பைனல்", "நான்காம்")):
                    yr_str = "Final year"
                else:
                    yr_str = yr_match.group(0).strip().capitalize()

                mem_id = f"mem_edu_yr_{int(time.time() * 1000)}"
                self.set_profile_fact("academic_year", yr_str, category="education", source="explicit_user", importance=3, source_turn_id=source_turn_id, memory_id=mem_id)
                extracted_ids.append(mem_id)
                break

        # E. Learning Goals
        learn_match = re.search(r"\b(?:learning|want\s+to\s+learn|kathukuren)\s+([A-Za-z0-9\s\.\-_]{2,30})\b", user_text, re.IGNORECASE)
        if learn_match and learn_match.group(1).strip().lower() not in ("a", "the", "this", "it", "more", "now"):
            l_val = learn_match.group(1).strip()
            mem_id = f"mem_edu_goal_{int(time.time() * 1000)}"
            self.set_profile_fact("learning_goal", l_val, category="education", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)

        # ----------------------------------------------
        # 12. WORK, CAREER & SKILLS
        # ----------------------------------------------
        combined_turn_text = f"{user_text} {assistant_text}".lower()

        # A. Job Role / Designation / Internship Role
        role_patterns = [
            r"\b(?:working\s+as\s+(?:a\s+)?|role\s+is\s+|designation\s+is\s+|i\s+am\s+a\s+)([A-Za-z0-9\s\-_]{2,40})\b",
            r"\b([A-Za-z0-9\s\-_]{2,40})-?ah\s+work\s+panren\b",
        ]
        role_extracted = False
        for pat in role_patterns:
            r_match = re.search(pat, user_text, re.IGNORECASE)
            if r_match:
                role_val = r_match.group(1).strip()
                if len(role_val) >= 3 and role_val.lower() not in ("a", "the", "good", "student", "creator", "user", "person", "human"):
                    mem_id = f"mem_work_role_{int(time.time() * 1000)}"
                    self.set_profile_fact("job_role", role_val, category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    self.add_episode(f"User shared their role: {role_val}", 0.7, "work", 4)
                    role_extracted = True
                    break

        if not role_extracted and any(w in combined_turn_text for w in ("full-stack development", "full stack developer", "fullstackdevelopment", "full-stack", "full stack")):
            mem_id = f"mem_work_role_{int(time.time() * 1000)}"
            self.set_profile_fact("job_role", "Full Stack Developer", category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            self.set_profile_fact("internship", "Full Stack Developer", category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
            self.add_episode("User shared their role: Full Stack Developer (Internship)", 0.7, "work", 4)

        # B. Company / Workplace / Internship
        comp_patterns = [
            r"\b(?:working\s+as\s+.*?\s+at\s+|working\s+(?:at|in)\s+|company\s+is\s+)([A-Za-z0-9\-_]{2,30})\b",
            r"\b([A-Za-z0-9\-_]{2,30})-?la\s+work\s+panren\b",
        ]
        comp_extracted = False
        for pat in comp_patterns:
            c_match = re.search(pat, user_text, re.IGNORECASE)
            if c_match:
                comp_val = c_match.group(1).strip()
                if len(comp_val) >= 2 and comp_val.lower() not in ("a", "the", "my", "this", "home", "office", "project", "college"):
                    mem_id = f"mem_work_comp_{int(time.time() * 1000)}"
                    self.set_profile_fact("company", comp_val, category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    comp_extracted = True
                    break

        if not comp_extracted and any(w in combined_turn_text for w in ("simposio en labs", "symposiumlabs", "symposium labs", "symphozen labs", "symphozen")):
            mem_id = f"mem_work_comp_{int(time.time() * 1000)}"
            self.set_profile_fact("company", "Symphozen Labs", category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
            extracted_ids.append(mem_id)
            self.add_episode("User shared their internship company: Symphozen Labs", 0.7, "work", 4)

        # C. Skills
        skill_patterns = [
            r"\b(?:my\s+skills\s+(?:are|include)|skills:\s*)([A-Za-z0-9\s,._-]{2,60})\b",
            r"\benaku\s+([A-Za-z0-9\s,._-]{2,60})\s+theriyum\b",
        ]
        for pat in skill_patterns:
            s_match = re.search(pat, user_text, re.IGNORECASE)
            if s_match:
                skills_val = s_match.group(1).strip()
                if len(skills_val) >= 2 and skills_val.lower() not in ("that", "this", "everything", "nothing", "all"):
                    mem_id = f"mem_work_skills_{int(time.time() * 1000)}"
                    self.set_profile_fact("skills", skills_val, category="work", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    break

        # ----------------------------------------------
        # 13. PROJECT DECISIONS & ARCHITECTURE
        # ----------------------------------------------
        dec_patterns = [
            r"\b(?:decided\s+to|decision\s+is\s+to|we\s+decided\s+to)\s+([A-Za-z0-9\s\-_,.]+)",
            r"\b(?:mudivu\s+panniten|mudivu\s+eduthom)\s+([A-Za-z0-9\s\-_,.]+)",
            r"\b(?:architecture\s+is|tech\s+stack\s+is)\s+([A-Za-z0-9\s\-_,.]+)",
            r"\b(?:project\s+goal\s+is|goal\s+is\s+to)\s+([A-Za-z0-9\s\-_,.]+)",
        ]
        for pat in dec_patterns:
            d_match = re.search(pat, user_text, re.IGNORECASE)
            if d_match:
                dec_val = d_match.group(1).strip()
                if len(dec_val) >= 3:
                    mem_id = f"mem_proj_dec_{int(time.time() * 1000)}"
                    self.set_profile_fact("project_decision", dec_val, category="project", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    self.add_episode(f"Project decision recorded: {dec_val}", 0.7, "project", 4)
                    break

        # ----------------------------------------------
        # 14. PLANS, INTENTIONS & MILESTONES
        # ----------------------------------------------
        plan_patterns = [
            r"\b(?:planning\s+to|plan\s+is\s+to|target\s+is\s+to|planniruken)\s+([A-Za-z0-9\s\-_,.]+)",
            r"\b(?:deadline\s+is|target\s+date\s+is)\s+([A-Za-z0-9\s\-_,.]+)",
        ]
        for pat in plan_patterns:
            p_match = re.search(pat, user_text, re.IGNORECASE)
            if p_match:
                plan_val = p_match.group(1).strip()
                if len(plan_val) >= 3:
                    k_name = "deadline" if "deadline" in pat else "upcoming_plan"
                    mem_id = f"mem_plan_{int(time.time() * 1000)}"
                    self.set_profile_fact(k_name, plan_val, category="plan", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    self.add_episode(f"User plan/milestone recorded: {plan_val}", 0.7, "plan", 4)
                    break

        # Determine evaluation scopes (full utterance + separate clauses for multi-fact utterances)
        eval_texts = [user_text]
        for cl in self._split_clauses(user_text):
            if cl not in eval_texts and not self._is_hypothetical_or_uncertain(cl):
                eval_texts.append(cl)

        # ----------------------------------------------
        # 16. OPEN-DOMAIN CORRECTIONS
        # ----------------------------------------------
        corrected_keys = set()
        open_corr_patterns = [
            r"(?i)\bactually\s+(?:my\s+)?(bike|car|laptop|phone|living\s+city|manager|teammate|doctor)\s+(?:is\s+not|isn't)\s+([A-Za-z0-9\s]{2,25})[,\s]+(?:it\s+is|is\s+)?\s*([A-Za-z0-9\s]{2,25})\b",
            r"(?i)\b(?:actually\s+)?en\s+(bike|car|laptop|phone|manager|teammate)\s+([A-Za-z0-9\s]{2,25})\s+(?:illa|kedayathu)[,\s]+([A-Za-z0-9\s]{2,25})\b",
        ]
        for c_pat in open_corr_patterns:
            c_match = re.search(c_pat, user_text)
            if c_match:
                raw_k = c_match.group(1).strip().lower().replace(" ", "_")
                old_v = c_match.group(2).strip()
                new_v = c_match.group(3).strip()
                if len(new_v) >= 2:
                    corrected_keys.add(raw_k)
                    mem_id = f"mem_corr_{raw_k}_{int(time.time() * 1000)}"
                    self.set_profile_fact(raw_k, new_v, category="possession" if raw_k in ("bike", "car", "laptop", "phone") else "general", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    self.add_episode(f"User corrected {raw_k}: not {old_v}, but {new_v}", 0.7, "correction", 4)
                    print(f"[MEMORY CORRECTION] Fact {raw_k} corrected: {old_v} -> {new_v}")
                    break

        # ----------------------------------------------
        # 17. POSSESSIONS & ASSETS (VEHICLES, GADGETS, KEYS)
        # ----------------------------------------------
        for txt in eval_texts:
            # A. Bike / Motorcycle
            if "bike" not in corrected_keys:
                bike_patterns = [
                    r"(?i)\b(?:my\s+|en\s+|ennoda\s+)?(?:bike|motorcycle|twowheeler|பைக்)\s+(?:is\s+|peru\s+is\s+|dhaan\s+)?([A-Za-z0-9\s\.\-_]{2,30})\b",
                    r"(?i)\b(?:i\s+have\s+a|i\s+own\s+a|i\s+ride\s+a)\s+([A-Za-z0-9\s\.\-_]{2,30})\s+(?:bike|motorcycle)\b",
                    r"(?i)\b([A-Za-z0-9\s\.\-_]{2,30})\s+bike\s+(?:vechiruken|use\s+panren)\b",
                ]
                for pat in bike_patterns:
                    m_b = re.search(pat, txt)
                    if m_b:
                        b_val = m_b.group(1).strip()
                        b_val = re.sub(r"(?i)\s*(?:bike|vechiruken|use panren|nu|dhaan|-?la)$", "", b_val).strip()
                        if b_val.lower().startswith(("not ", "no ", "isn't", "illa", "kedayathu")):
                            continue
                        if len(b_val) >= 2 and b_val.lower() not in ("a", "the", "my", "new", "old", "good", "bad", "is", "one"):
                            mem_id = f"mem_poss_bike_{int(time.time() * 1000)}"
                            self.set_profile_fact("bike", b_val, category="possession", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                            extracted_ids.append(mem_id)
                            self.add_episode(f"User mentioned their bike is {b_val}", 0.7, "possession", 4)
                            break

            # B. Car
            if "car" not in corrected_keys:
                car_patterns = [
                    r"(?i)\b(?:my\s+|en\s+|ennoda\s+)?(?:car|fourwheeler|கார்)\s+(?:is\s+|peru\s+is\s+|dhaan\s+)?([A-Za-z0-9\s\.\-_]{2,30})\b",
                    r"(?i)\b(?:i\s+have\s+a|i\s+own\s+a|i\s+drive\s+a)\s+([A-Za-z0-9\s\.\-_]{2,30})\s+car\b",
                    r"(?i)\b([A-Za-z0-9\s\.\-_]{2,30})\s+car\s+(?:vechiruken|use\s+panren)\b",
                ]
                for pat in car_patterns:
                    m_c = re.search(pat, txt)
                    if m_c:
                        c_val = m_c.group(1).strip()
                        c_val = re.sub(r"(?i)\s*(?:car|vechiruken|use panren|nu|dhaan|-?la)$", "", c_val).strip()
                        if c_val.lower().startswith(("not ", "no ", "isn't", "illa", "kedayathu")):
                            continue
                        if len(c_val) >= 2 and c_val.lower() not in ("a", "the", "my", "new", "old", "good", "bad", "is", "one"):
                            mem_id = f"mem_poss_car_{int(time.time() * 1000)}"
                            self.set_profile_fact("car", c_val, category="possession", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                            extracted_ids.append(mem_id)
                            self.add_episode(f"User mentioned their car is {c_val}", 0.7, "possession", 4)
                            break

            # C. Laptop
            if "laptop" not in corrected_keys:
                laptop_patterns = [
                    r"(?i)\b(?:my\s+|en\s+|ennoda\s+)?(?:laptop|macbook)\s+(?:is\s+|peru\s+is\s+|dhaan\s+)?([A-Za-z0-9\s\.\-_]{2,30})\b",
                    r"(?i)\b(?:my\s+|en\s+|ennoda\s+)computer\s+(?:is\s+|peru\s+is\s+|dhaan\s+)?([A-Za-z0-9\s\.\-_]{2,30})\b",
                    r"(?i)\b(?:i\s+use\s+a|i\s+have\s+a)\s+([A-Za-z0-9\s\.\-_]{2,30})\s+(?:laptop|macbook)\b",
                ]
                for pat in laptop_patterns:
                    m_l = re.search(pat, txt)
                    if m_l:
                        l_val = m_l.group(1).strip()
                        l_val = re.sub(r"(?i)\s*(?:laptop|macbook|computer|nu|dhaan)$", "", l_val).strip()
                        if l_val.lower().startswith(("not ", "no ", "isn't", "illa", "kedayathu")):
                            continue
                        if len(l_val) >= 2 and l_val.lower() not in ("a", "the", "my", "good", "is", "our") and self._is_valid_fact_value("laptop", l_val):
                            mem_id = f"mem_poss_laptop_{int(time.time() * 1000)}"
                            self.set_profile_fact("laptop", l_val, category="possession", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                            extracted_ids.append(mem_id)
                            break

            # D. Phone / Mobile
            if "phone" not in corrected_keys:
                phone_patterns = [
                    r"(?i)\b(?:my\s+|en\s+|ennoda\s+)?(?:phone|mobile|smartphone)\s+(?:is\s+|peru\s+is\s+|dhaan\s+)?([A-Za-z0-9\s\.\-_]{2,30})\b",
                    r"(?i)\b(?:i\s+use\s+an?|i\s+have\s+an?)\s+([A-Za-z0-9\s\.\-_]{2,30})\s+(?:phone|mobile)\b",
                ]
                for pat in phone_patterns:
                    m_ph = re.search(pat, txt)
                    if m_ph:
                        ph_val = m_ph.group(1).strip()
                        ph_val = re.sub(r"(?i)\s*(?:phone|mobile|smartphone|nu|dhaan)$", "", ph_val).strip()
                        if ph_val.lower().startswith(("not ", "no ", "isn't", "illa", "kedayathu")):
                            continue
                        if len(ph_val) >= 2 and ph_val.lower() not in ("a", "the", "my", "good", "is", "our"):
                            mem_id = f"mem_poss_phone_{int(time.time() * 1000)}"
                            self.set_profile_fact("phone", ph_val, category="possession", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                            extracted_ids.append(mem_id)
                            break

            # E. Stored Items / Keys / Drawer Location
            stored_patterns = [
                r"(?i)\b(?:i\s+keep\s+my|kept\s+my|en|ennoda)\s+([A-Za-z0-9\s\-_]{2,20}\s+keys?)\s+(?:in|at|-?la)\s+(?:the\s+)?([A-Za-z0-9\s\-_]{2,30})\b",
                r"(?i)\b([A-Za-z0-9\s\-_]{2,20}\s+keys?)\s+(?:is\s+in|is\s+at)\s+(?:the\s+)?([A-Za-z0-9\s\-_]{2,30})\b",
            ]
            for pat in stored_patterns:
                m_s = re.search(pat, txt)
                if m_s:
                    item_k = m_s.group(1).strip().lower().replace(" ", "_")
                    loc_v = m_s.group(2).strip()
                    loc_v = re.sub(r"(?i)\s*(?:vechiruken|la|vechen|irukku)$", "", loc_v).strip()
                    if len(loc_v) >= 2:
                        mem_id = f"mem_stored_{item_k}_{int(time.time() * 1000)}"
                        self.set_profile_fact(f"stored_item_{item_k}", loc_v, category="possession", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User noted they keep {item_k} in {loc_v}", 0.7, "possession", 4)
                        break

        # ----------------------------------------------
        # 17. LOCATIONS & RESIDENCE (LIVING CITY, HOMETOWN)
        # ----------------------------------------------
        for txt in eval_texts:
            # A. Living City
            living_patterns = [
                r"(?i)\b(?:i\s+live\s+in|i\s+am\s+living\s+in|i\s+stay\s+in|currently\s+residing\s+in)\s+([A-Za-z\u0B80-\u0BFF]{2,30})\b",
                r"(?i)\bnaan\s+([A-Za-z\u0B80-\u0BFF]{2,30})-(?:la|il)\s+(?:iruken|thangi\s+iruken|vasikiren)\b",
                r"(?i)\b(?:en\s+living\s+place|current\s+city\s+is)\s+([A-Za-z\u0B80-\u0BFF]{2,30})\b",
            ]
            for pat in living_patterns:
                m_l = re.search(pat, txt)
                if m_l:
                    c_val = m_l.group(1).strip().capitalize()
                    if len(c_val) >= 2 and c_val.lower() not in ("a", "the", "my", "good", "fine", "here", "there", "veedu", "house", "room", "drawer"):
                        mem_id = f"mem_loc_city_{int(time.time() * 1000)}"
                        self.set_profile_fact("living_city", c_val, category="location", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User mentioned living in {c_val}", 0.7, "location", 4)
                        break

            # B. Hometown / Native
            native_patterns = [
                r"(?i)\b(?:my\s+hometown\s+is|my\s+native\s+is|native\s+place\s+is)\s+([A-Za-z\u0B80-\u0BFF]{2,30})\b",
                r"(?i)\b(?:en\s+native|en\s+sondha\s+ooru|ennoda\s+native)\s+(?:is\s+)?([A-Za-z\u0B80-\u0BFF]{2,30})\b",
            ]
            for pat in native_patterns:
                m_n = re.search(pat, txt)
                if m_n:
                    n_val = m_n.group(1).strip().capitalize()
                    if len(n_val) >= 2 and n_val.lower() not in ("a", "the", "my", "good", "fine", "city", "place"):
                        mem_id = f"mem_loc_native_{int(time.time() * 1000)}"
                        self.set_profile_fact("hometown", n_val, category="location", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User shared their hometown is {n_val}", 0.7, "location", 4)
                        break

        # ----------------------------------------------
        # 18. DIETARY & HEALTH PREFERENCES
        # ----------------------------------------------
        for txt in eval_texts:
            # A. Allergies
            allergy_patterns = [
                r"(?i)\b(?:i\s+am\s+allergic\s+to|allergic\s+to|allergy\s+to)\s+([A-Za-z\u0B80-\u0BFF\s]{2,30})\b",
                r"(?i)\b(?:enaku|enoda)\s+([A-Za-z\u0B80-\u0BFF\s]{2,30})\s+(?:allergy|padadhu)\b",
            ]
            for pat in allergy_patterns:
                m_a = re.search(pat, txt)
                if m_a:
                    a_val = m_a.group(1).strip()
                    a_val = re.sub(r"(?i)\s*(?:allergy|padadhu|romba|nu)$", "", a_val).strip()
                    if len(a_val) >= 2 and a_val.lower() not in ("a", "the", "my", "some", "bad", "food"):
                        mem_id = f"mem_health_allergy_{int(time.time() * 1000)}"
                        self.set_profile_fact("allergy", a_val, category="health", source="explicit_user", importance=5, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User shared allergy to {a_val}", 0.7, "health", 5)
                        break

            # B. Dietary Preference
            diet_patterns = [
                r"(?i)\b(?:i\s+am\s+a\s+|i\s+am\s+)?(vegetarian|pure\s+vegetarian|non-vegetarian|vegan)\b",
                r"(?i)\bnaan\s+(pure\s+veg|veg|non-veg)\b",
            ]
            for pat in diet_patterns:
                m_d = re.search(pat, txt)
                if m_d:
                    d_val = m_d.group(1).strip().title()
                    mem_id = f"mem_health_diet_{int(time.time() * 1000)}"
                    self.set_profile_fact("dietary_preference", d_val, category="health", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    break

        # ----------------------------------------------
        # 19. DAILY ROUTINES & HABITS
        # ----------------------------------------------
        for txt in eval_texts:
            # A. Wake Up Time
            wake_patterns = [
                r"(?i)\b(?:i\s+wake\s+up\s+at|wake\s+up\s+at)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)\b",
                r"(?i)\bnaan\s+daily\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm|mani)?(?:-?ku)?)\s+(?:enthiripen|ezhunthiripen)\b",
            ]
            for pat in wake_patterns:
                m_w = re.search(pat, txt)
                if m_w:
                    w_val = m_w.group(1).strip()
                    mem_id = f"mem_rout_wake_{int(time.time() * 1000)}"
                    self.set_profile_fact("wake_up_time", w_val, category="routine", source="explicit_user", importance=3, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    break

            # B. Gym / Fitness
            gym_patterns = [
                r"(?i)\b(?:i\s+go\s+to\s+gym\s+at|gym\s+at)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)\b",
                r"(?i)\b(?:daily\s+gym\s+poren|i\s+go\s+to\s+gym\s+daily|daily\s+workout)\b",
            ]
            for pat in gym_patterns:
                m_g = re.search(pat, txt)
                if m_g:
                    g_val = m_g.group(1).strip() if m_g.groups() and m_g.group(1) else "daily"
                    mem_id = f"mem_rout_gym_{int(time.time() * 1000)}"
                    self.set_profile_fact("fitness_routine", g_val, category="routine", source="explicit_user", importance=3, source_turn_id=source_turn_id, memory_id=mem_id)
                    extracted_ids.append(mem_id)
                    break

        # ----------------------------------------------
        # 20. SCHEDULES & APPOINTMENTS
        # ----------------------------------------------
        for txt in eval_texts:
            sched_patterns = [
                r"(?i)\b(doctor|dentist|hospital|clinic)\s+appointment\s+(?:is\s+)?(?:on|at)?\s*([A-Za-z0-9\s,:]{2,30})\b",
                r"(?i)\b(meeting|discussion|review|sync)\s+(?:is\s+)?(?:on|at)?\s*([A-Za-z0-9\s,:]{2,30})\b",
            ]
            for pat in sched_patterns:
                m_s = re.search(pat, txt)
                if m_s:
                    s_type = m_s.group(1).strip().lower()
                    s_time = m_s.group(2).strip()
                    s_time = re.sub(r"(?i)\s*(?:irukku|la|pannum)$", "", s_time).strip()
                    if len(s_time) >= 2:
                        k_name = f"{s_type}_appointment" if "appointment" in pat else f"{s_type}_schedule"
                        mem_id = f"mem_sched_{s_type}_{int(time.time() * 1000)}"
                        self.set_profile_fact(k_name, s_time, category="schedule", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"Recorded schedule: {s_type} on {s_time}", 0.7, "schedule", 4)
                        break

        # ----------------------------------------------
        # 21. COMMITMENTS & PENDING TASKS
        # ----------------------------------------------
        for txt in eval_texts:
            task_patterns = [
                r"(?i)\b(?:i\s+need\s+to|i\s+have\s+to|i\s+promised\s+to|need\s+to\s+remember\s+to)\s+([A-Za-z0-9\s\-_,.]+)\b",
                r"(?i)\b(?:pending\s+task|unresolved\s+task):\s*([A-Za-z0-9\s\-_,.]+)\b",
            ]
            for pat in task_patterns:
                m_t = re.search(pat, txt)
                if m_t:
                    t_val = m_t.group(1).strip()
                    t_val = re.sub(r"(?i)\s*(?:pannanum|nu sonnen|today|tomorrow)$", "", t_val).strip()
                    if len(t_val) >= 4 and not self._is_query_or_question(t_val):
                        mem_id = f"mem_task_{int(time.time() * 1000)}"
                        self.set_profile_fact("pending_task", t_val, category="task", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        self.add_task(description=t_val, profile_id=getattr(self, "profile_id", "default"), source_turn_id=source_turn_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"Recorded commitment/task: {t_val}", 0.7, "task", 4)
                        break

        # ----------------------------------------------
        # 22. NON-FAMILY PEOPLE (MANAGER, TEAMMATE, DOCTOR)
        # ----------------------------------------------
        for txt in eval_texts:
            people_patterns = [
                r"(?i)\b(?:my\s+|en\s+|ennoda\s+)?(manager|boss|teammate|colleague|mentor|doctor|roommate)(?:['’]s)?\s+(?:name\s+is\s+|peru\s+|is\s+|dhaan\s+)?([A-Za-z\u0B80-\u0BFF]{2,25})\b",
                r"(?i)\b([A-Za-z\u0B80-\u0BFF]{2,25})\s+is\s+my\s+(manager|boss|teammate|colleague|mentor|doctor|roommate)\b",
            ]
            for pat in people_patterns:
                m_p = re.search(pat, txt)
                if m_p:
                    if pat.startswith(r"(?i)\b(?:my"):
                        r_role = m_p.group(1).strip().lower()
                        p_name = m_p.group(2).strip().capitalize()
                    else:
                        p_name = m_p.group(1).strip().capitalize()
                        r_role = m_p.group(2).strip().lower()

                    reserved_names = ("is", "a", "the", "my", "good", "fine", "here", "name", "peru", "illa", "not", "appointment", "schedule", "meeting", "checkup")
                    if r_role == "doctor" and any(w in txt.lower() for w in ("appointment", "schedule", "checkup", "visit")):
                        continue
                    if len(p_name) >= 2 and p_name.lower() not in reserved_names:
                        self.add_known_person(
                            name=p_name,
                            relationship_to_primary_user=r_role,
                            relationship_to_dheepthi=r_role,
                            voice_profile_id=p_name.lower(),
                            notes=f"User's {r_role}",
                            source="explicit_user",
                            confidence="high",
                        )
                        mem_id = f"mem_people_{r_role}_{int(time.time() * 1000)}"
                        self.set_profile_fact(r_role, p_name, category="people", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User mentioned their {r_role} is {p_name}", 0.7, "people", 4)
                        break

        # ----------------------------------------------
        # 23. TASK COMPLETION & RESOLUTION
        # ----------------------------------------------
        task_comp_patterns = [
            r"(?i)\b(?:i\s+have\s+completed|i\s+completed|i\s+finished|completed\s+the\s+task|finished\s+the\s+task|task\s+done)\s*(?:of|about|for|:)?\s*([A-Za-z0-9\s\-_]{3,40})?",
            r"(?i)\b([A-Za-z0-9\s\-_]{3,40})\s+(?:task\s+mudichiten|task\s+mudinjadhu|complete\s+panniten)\b",
        ]
        for pat in task_comp_patterns:
            m_comp = re.search(pat, user_text)
            if m_comp:
                comp_kw = (m_comp.group(1) or "").strip()
                self.complete_task(comp_kw, profile_id=getattr(self, "profile_id", "default"))
                self.add_episode(f"Task marked as completed: {comp_kw or 'latest task'}", 0.8, "task", 4)
                break

        # ----------------------------------------------
        # 24. INTERNSHIP & CAREER CONTEXT
        # ----------------------------------------------
        for txt in eval_texts:
            intern_patterns = [
                r"(?i)\b(?:doing|got|selected\s+for|working\s+as\s+an?)?\s*internship\s+(?:at|in)\s+([A-Za-z0-9\s\.\-_]{2,35})\b",
                r"(?i)\b([A-Za-z0-9\s\.\-_]{2,35})-?la\s+internship\s+(?:panren|kedaichirukku|doing)\b",
                r"(?i)\bintern\s+at\s+([A-Za-z0-9\s\.\-_]{2,35})\b",
            ]
            for pat in intern_patterns:
                m_in = re.search(pat, txt)
                if m_in:
                    in_val = m_in.group(1).strip()
                    if len(in_val) >= 2 and in_val.lower() not in ("a", "the", "my", "our", "an", "good", "summer", "winter"):
                        mem_id = f"mem_intern_{int(time.time() * 1000)}"
                        self.set_profile_fact("internship", in_val, category="career", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User mentioned internship at {in_val}", 0.7, "career", 4)
                        break

        # ----------------------------------------------
        # 25. HOBBIES, GOALS & CHALLENGES
        # ----------------------------------------------
        for txt in eval_texts:
            # A. Hobbies
            hobby_patterns = [
                r"(?i)\b(?:my\s+hobb(?:y|ies)\s+(?:is|are)|in\s+my\s+free\s+time\s+i\s+like\s+to|i\s+enjoy|i\s+love\s+to)\s+([A-Za-z0-9\s,\-_]{3,40})\b",
                r"(?i)\b(?:enoda|en)\s+hobby\s+([A-Za-z0-9\s,\-_]{3,40})\b",
                r"(?i)\bfree\s+time-?la\s+([A-Za-z0-9\s,\-_]{3,40})\s+(?:panren|panna\s+pidikkum)\b",
            ]
            for pat in hobby_patterns:
                m_h = re.search(pat, txt)
                if m_h:
                    h_val = m_h.group(1).strip()
                    if len(h_val) >= 3 and h_val.lower() not in ("a", "the", "it", "that", "this", "something", "anything"):
                        mem_id = f"mem_hobby_{int(time.time() * 1000)}"
                        self.set_profile_fact("hobbies", h_val, category="interest", source="explicit_user", importance=3, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User shared hobby: {h_val}", 0.7, "interest", 3)
                        break

            # B. Goals & Ambitions
            goal_patterns = [
                r"(?i)\b(?:my\s+goal\s+is\s+to|my\s+ambition\s+is\s+to|i\s+aspire\s+to|long\s+term\s+goal\s+is\s+to)\s+([A-Za-z0-9\s,\-_]{3,50})\b",
                r"(?i)\b(?:en\s+goal|enoda\s+ambition|en\s+lakshiyam)\s+(?:is\s+)?([A-Za-z0-9\s,\-_]{3,50})\b",
            ]
            for pat in goal_patterns:
                m_g = re.search(pat, txt)
                if m_g:
                    g_val = m_g.group(1).strip()
                    if len(g_val) >= 3:
                        mem_id = f"mem_goal_{int(time.time() * 1000)}"
                        self.set_profile_fact("career_goal", g_val, category="goal", source="explicit_user", importance=4, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User shared goal: {g_val}", 0.7, "goal", 4)
                        break

            # C. Challenges & Problems
            chal_patterns = [
                r"(?i)\b(?:i\s+am\s+(?:currently\s+)?struggling\s+with|struggling\s+with|biggest\s+challenge\s+is|facing\s+difficulty\s+in|blocked\s+by)\s+([A-Za-z0-9\s,\-_]{3,50})\b",
                r"(?i)\b(?:romba\s+kashtama\s+irukku|issue\s+irukku|problem\s+irukku)\s+(?:in|for)?\s*([A-Za-z0-9\s,\-_]{3,50})?\b",
            ]
            for pat in chal_patterns:
                m_ch = re.search(pat, txt)
                if m_ch:
                    ch_val = (m_ch.group(1) or "").strip()
                    if len(ch_val) >= 3 and ch_val.lower() not in ("a", "the", "it", "this", "that"):
                        mem_id = f"mem_chal_{int(time.time() * 1000)}"
                        self.set_profile_fact("current_challenge", ch_val, category="experience", source="explicit_user", importance=3, source_turn_id=source_turn_id, memory_id=mem_id)
                        extracted_ids.append(mem_id)
                        self.add_episode(f"User shared challenge: {ch_val}", 0.5, "experience", 3)
                        break



        # ----------------------------------------------
        # 15. EXPLICIT "REMEMBER THAT" GENERAL NOTES
        # ----------------------------------------------
        invalid_note_payloads = {
            "about me", "me", "this", "it", "everything", "anything", "all",
            "what you remember", "what i said", "what i told you"
        }
        if is_explicit_remember and remember_payload and not extracted_ids:
            clean_payload = remember_payload.strip().lower().rstrip(".?!,")
            if clean_payload not in invalid_note_payloads and len(clean_payload) > 3:
                mem_id = f"mem_note_{int(time.time() * 1000)}"
                self.set_profile_fact("user_note", remember_payload, category="user_note", source="explicit_user", importance=5, source_turn_id=source_turn_id, memory_id=mem_id)
                extracted_ids.append(mem_id)
                self.add_episode(f"User asked to remember: {remember_payload}", 0.7, "user_note", 5)

        return extracted_ids

    # ==================================================
    # COMPACT RETRIEVAL FOR PROMPT INJECTION
    # ==================================================

    def get_compact_memory_context(self, query: str = "") -> Dict[str, Any]:
        """
        Retrieves working, episodic, people, and profile facts formatted compactly.
        Designed to stay within ~250-300 tokens. Reconciles verified creator identity
        with creator metadata.
        """
        profile = self.get_all_profile_facts()
        episodes = self.get_salient_episodes(limit=3)
        working_turns = self.get_recent_working_turns(limit=6)
        identity = self.get_speaker_identity()

        pref_name = identity.get("preferred_user_name")
        use_name = identity.get("use_preferred_name", True)
        is_creator = identity.get("is_creator", False)

        profile_bullets = []

        # Address & Identity Bullet
        if not use_name:
            profile_bullets.append("User address preference: The user explicitly requested NOT to be called by name. NEVER use any name for addressing.")
        elif pref_name:
            if is_creator:
                profile_bullets.append(f"Speaker identity: {pref_name} (Verified Creator of DHEEPTHI-AI)")
            else:
                profile_bullets.append(f"Speaker identity: {pref_name} (User)")
        else:
            profile_bullets.append("Speaker identity: Unknown speaker. No name established yet. Do NOT invent or guess any name.")

        # Known People / Relationships
        known_people = identity.get("known_people", [])
        if known_people:
            people_summaries = []
            for p in known_people:
                rel = p.get("relationship_to_primary_user") or p.get("relationship_to_dheepthi")
                p_name = p.get("name")
                if (
                    p_name
                    and rel
                    and rel not in ("self", "creator", "primary_user")
                    and p.get("is_primary_user") != 1
                    and p_name not in self.STATIC_CREATORS
                    and p_name.lower() not in ("vani", "vaani", "working", "karthik", "rahul", "arun")
                ):
                    people_summaries.append(f"{rel}: {p_name}")
            if people_summaries:
                profile_bullets.append(f"Known people: {', '.join(people_summaries[:3])} (Do NOT confuse with the current speaker)")

        # Personal Memories from SQLite
        try:
            active_mems = self.db.get_personal_memories(active_only=True, profile_id=getattr(self, "profile_id", "default"))
            seen_keys = set()
            for m in active_mems:
                cat = m.get("category", "")
                k = m.get("key", "")
                v = m.get("value", "")
                if not k or not v or not self._is_valid_fact_value(k, v):
                    continue
                seen_keys.add(k)
                if cat == "relationships":
                    b_str = f"Family/Relationship: {k.capitalize()} is {v}"
                    if b_str not in profile_bullets:
                        profile_bullets.append(b_str)
                elif cat in ("fact", "preference", "interest", "education", "work", "career", "project", "plan", "milestone", "user_note", "possession", "location", "health", "routine", "schedule", "decision", "task", "people", "instruction", "general"):
                    b_str = f"{cat.capitalize()} ({k.replace('_', ' ')}): {v}"
                    if b_str not in profile_bullets:
                        profile_bullets.append(b_str)

            # Ensure critical facts are represented even if latest active record was suppressed
            for critical_key, cat_name in [("college", "Education"), ("degree", "Education"), ("academic_year", "Education"), ("company", "Work"), ("job_role", "Work"), ("current_project", "Work")]:
                if critical_key not in seen_keys:
                    rec_val = self.get_profile_fact(critical_key)
                    if rec_val and self._is_valid_fact_value(critical_key, rec_val):
                        seen_keys.add(critical_key)
                        b_str = f"{cat_name} ({critical_key.replace('_', ' ')}): {rec_val}"
                        if b_str not in profile_bullets:
                            profile_bullets.append(b_str)
        except Exception:
            pass

        # Preferences & Work
        pref_lang = profile.get("preferred_language", "Tanglish")
        profile_bullets.append(f"Preferred language: {pref_lang}")

        curr_proj = profile.get("current_project")
        if curr_proj and self._is_valid_fact_value("current_project", curr_proj):
            if not any("current project" in b.lower() for b in profile_bullets):
                profile_bullets.append(f"Current project: {curr_proj}")

        fav_music = profile.get("favorite_music")
        if fav_music and self._is_valid_fact_value("favorite_music", fav_music):
            if not any("favorite music" in b.lower() for b in profile_bullets):
                profile_bullets.append(f"Favorite music: {fav_music}")

        tech = profile.get("primary_technology")
        if tech and self._is_valid_fact_value("primary_technology", tech):
            if not any("technology" in b.lower() for b in profile_bullets):
                profile_bullets.append(f"Technology: {tech}")

        freq_apps = profile.get("frequent_apps")
        if freq_apps:
            profile_bullets.append(f"Frequently used apps: {freq_apps}")

        # Active tasks
        active_tasks = self.get_active_tasks(profile_id=getattr(self, "profile_id", "default"))
        if active_tasks:
            t_descriptions = [t.get("description") for t in active_tasks[:2] if t.get("description")]
            if t_descriptions:
                profile_bullets.append(f"Active tasks: {', '.join(t_descriptions)}")

        comp = profile.get("company")
        if comp and not any("company" in b.lower() for b in profile_bullets):
            profile_bullets.append(f"Company: {comp}")

        role = profile.get("job_role")
        if role and not any("role" in b.lower() for b in profile_bullets):
            profile_bullets.append(f"Role: {role}")

        intern = profile.get("internship")
        if intern and not any("internship" in b.lower() for b in profile_bullets):
            profile_bullets.append(f"Internship: {intern}")

        hobbies = profile.get("hobbies")
        if hobbies and not any("hobbies" in b.lower() for b in profile_bullets):
            profile_bullets.append(f"Hobbies: {hobbies}")

        goal = profile.get("career_goal")
        if goal and not any("goal" in b.lower() for b in profile_bullets):
            profile_bullets.append(f"Career Goal: {goal}")

        # Relevant memory retrieval if query asks specific questions
        relevant_memories = []
        q_lower = str(query or "").lower()
        if q_lower:
            if "language" in q_lower or "prefer" in q_lower:
                relevant_memories.append(f"Preferred language is {pref_lang}")
            if any(w in q_lower for w in ("project", "working on", "goal", "decision")):
                if curr_proj:
                    relevant_memories.append(f"Current project: {curr_proj}")
                proj_dec = profile.get("project_decision")
                if proj_dec:
                    relevant_memories.append(f"Project decision/goal: {proj_dec}")
            if "who am i" in q_lower:
                if is_creator and pref_name:
                    relevant_memories.append(f"The speaker is {pref_name}, creator of DHEEPTHI-AI")
                elif pref_name:
                    relevant_memories.append(f"The speaker is {pref_name}")
                else:
                    relevant_memories.append("Speaker identity is not yet confirmed")

            # Check family / relationships
            if re.search(r"\b(?:family|kudumbam|kudumba)\b", q_lower):
                active_mems = self.db.get_personal_memories(
                    category="relationships",
                    active_only=True,
                    profile_id=getattr(self, "profile_id", "default")
                )
                fam_facts = [f"{m.get('key').capitalize()}: {m.get('value')}" for m in active_mems if m.get("key") and m.get("value")]
                if not fam_facts:
                    for p in known_people:
                        rel = p.get("relationship_to_primary_user") or p.get("relationship_to_dheepthi")
                        if rel and rel not in ("self", "creator", "primary_user") and p.get("name") not in self.STATIC_CREATORS:
                            fam_facts.append(f"{rel.capitalize()}: {p.get('name')}")
                if fam_facts:
                    relevant_memories.append(f"[VERIFIED FAMILY FACTS FROM MEMORY] " + ", ".join(fam_facts))
                else:
                    relevant_memories.append("[MEMORY DIRECTIVE] The user is asking about family, but no family details are stored yet. Do NOT hallucinate names.")
            else:
                rel_query_targets = {
                    "father": ("father", "appa", "dad"),
                    "mother": ("mother", "amma", "mom"),
                    "brother": ("brother", "anna", "thambi", "dheebes"),
                    "sister": ("sister", "akka", "thangachi", "thangai"),
                    "friend": ("friend", "nanban", "dost"),
                    "wife": ("wife", "manaivi"),
                    "husband": ("husband", "kanavan"),
                    "son": ("son", "paiyan", "magan"),
                    "daughter": ("daughter", "ponnu", "magal"),
                }
                for rel_k, rel_words in rel_query_targets.items():
                    if any(re.search(rf"\b{re.escape(rw)}\b", q_lower) for rw in rel_words):
                        rel_mems = self.db.get_personal_memories(
                            category="relationships",
                            key=rel_k,
                            active_only=True,
                            profile_id=getattr(self, "profile_id", "default")
                        )
                        found_val = rel_mems[0].get("value") if rel_mems else None
                        if not found_val:
                            for p in known_people:
                                if p.get("relationship_to_primary_user") == rel_k or (rel_k == "brother" and "dheebes" in p.get("name", "").lower()):
                                    found_val = p.get("name")
                                    break
                        if found_val:
                            relevant_memories.append(f"[VERIFIED FACT FROM MEMORY] The user's {rel_k} is {found_val}.")
                        else:
                            relevant_memories.append(
                                f"[MEMORY DIRECTIVE] The user is asking about their {rel_k}, but their {rel_k}'s name is NOT stored in memory. "
                                f"Do NOT guess, assume, or hallucinate a name. Politely state that you do not know their {rel_k}'s name yet, or ask them what their {rel_k}'s name is."
                            )

            # Check education / studies in query
            edu_query_terms = (
                "college", "degree", "studying", "studies", "education", "course",
                "department", "dept", "year", "padikiren", "padikkiren",
                "கல்லூரி", "காலேஜ்", "படிப்பு", "டிபார்ட்மென்ட்", "ஆண்டு", "வருடம்"
            )
            if any(re.search(rf"\b{re.escape(w)}\b", q_lower) or w in q_lower for w in edu_query_terms):
                edu_mems = self.db.get_personal_memories(category="education", active_only=True, profile_id=getattr(self, "profile_id", "default"))
                col = profile.get("college")
                deg = profile.get("degree")
                dept = profile.get("department")
                yr = profile.get("academic_year")
                if not col:
                    for em in edu_mems:
                        if em.get("key") == "college": col = em.get("value")
                if not deg:
                    for em in edu_mems:
                        if em.get("key") == "degree": deg = em.get("value")
                if not dept:
                    for em in edu_mems:
                        if em.get("key") == "department": dept = em.get("value")
                if not yr:
                    for em in edu_mems:
                        if em.get("key") == "academic_year": yr = em.get("value")

                e_parts = []
                if col: e_parts.append(f"College: {col}")
                if deg: e_parts.append(f"Degree/Course: {deg}")
                if yr: e_parts.append(f"Academic Year: {yr}")
                if dept: e_parts.append(f"Department: {dept}")

                if e_parts:
                    relevant_memories.append(f"[VERIFIED EDUCATION FACTS] " + ", ".join(e_parts))

                is_dept_asked = any(w in q_lower for w in ("department", "dept", "டிபார்ட்மென்ட்"))
                if is_dept_asked and not dept:
                    relevant_memories.append(
                        "[MEMORY DIRECTIVE] The user is asking about their department, but their department is NOT stored in memory. "
                        "Do NOT guess, assume, or hallucinate a department. State politely that department is not stored in memory (you may mention degree if known)."
                    )

            # Check work / career in query
            if any(re.search(rf"\b{re.escape(w)}\b", q_lower) for w in ("work", "job", "career", "company", "skills", "role")):
                role = profile.get("job_role")
                comp = profile.get("company")
                skills = profile.get("skills")
                if role or comp or skills:
                    w_parts = []
                    if role: w_parts.append(f"Role: {role}")
                    if comp: w_parts.append(f"Company: {comp}")
                    if skills: w_parts.append(f"Skills: {skills}")
                    relevant_memories.append(f"[VERIFIED CAREER FACTS] " + ", ".join(w_parts))

            # Check plans / deadlines in query
            if any(re.search(rf"\b{re.escape(w)}\b", q_lower) for w in ("plan", "deadline", "milestone", "planning")):
                up_p = profile.get("upcoming_plan")
                dl = profile.get("deadline")
                if up_p or dl:
                    p_parts = []
                    if up_p: p_parts.append(f"Upcoming Plan: {up_p}")
                    if dl: p_parts.append(f"Deadline: {dl}")
                    relevant_memories.append(f"[VERIFIED PLANS] " + ", ".join(p_parts))

            # Multi-factor semantic search for query-relevant memories
            scored_mems = self.search_relevant_memories(query=query, profile_id=getattr(self, 'profile_id', 'default'), top_k=3)
            for sm in scored_mems:
                c = sm.get("category", "")
                k = sm.get("key", "").replace("_", " ")
                v = sm.get("value", "")
                fact_str = f"[VERIFIED FACT] {c.capitalize()} ({k}): {v}"
                if fact_str not in relevant_memories:
                    relevant_memories.append(fact_str)

            # Fallback Archive Evidence Search (Lifelong continuity)
            if q_lower and len(q_lower) > 5 and len(relevant_memories) < 3:
                archive_results = self.search_conversation_archive(query=query, profile_id=getattr(self, 'profile_id', 'default'), top_k=2)
                for ar in archive_results:
                    ar_text = (ar.get("user_command") or "").strip()
                    a_resp = (ar.get("assistant_response") or "").strip()
                    if ar_text and len(ar_text) > 4 and ar_text.lower() not in q_lower:
                        evidence_bullet = f"[ARCHIVE EVIDENCE (turn {ar.get('turn_id', '')})] User previously stated: '{ar_text}'"
                        if a_resp and any(k in a_resp.lower() for k in ("symposium", "fullstack", "internship", "project", "mca", "sona")):
                            evidence_bullet += f" | Verified: '{a_resp}'"
                        if evidence_bullet not in relevant_memories:
                            relevant_memories.append(evidence_bullet)

        print(f"[MEMORY DIAGNOSTIC] profile_id={getattr(self, 'profile_id', 'default')} query='{query}' profile_bullets={len(profile_bullets)} relevant_facts={len(relevant_memories)}")
        return {
            "identity": identity,
            "profile_bullets": profile_bullets,
            "episodes": episodes,
            "working_turns": working_turns,
            "preferred_user_name": pref_name,
            "use_preferred_name": use_name,
            "is_creator": is_creator,
            "relevant_memories": relevant_memories,
        }
