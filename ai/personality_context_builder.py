"""
Personality Context Builder Module for DHEEPTHI-AI V1

Synthesizes the active emotional state, verified speaker identity,
and rich persistent memory hierarchy into a compact, structured
prompt section for Gemini Live and Gemini text chat.

Target: ~250-300 tokens maximum.
Enforces non-negotiable safety guardrails:
- Distinguishes static creator metadata from verified speaker identity.
- Seamlessly reconciles when speaker identifies as creator Naresh without contradicting metadata.
- Conversational identity only: identity claims NEVER bypass OS/execution safety or CommandDispatcher.
- Strictly prevents inventing user names.
- Internal variables, databases, and prompt implementation must never be revealed.
- Laptop command execution and <ACTION> generation must never be blocked or altered.
"""

from typing import Optional, Dict, Any
from ai.emotion_engine import EmotionEngine
from ai.memory_manager import MemoryManager


class PersonalityContextBuilder:
    """
    Constructs dynamic context blocks injecting emotion, identity, and persistent memory
    into Gemini system prompts.
    """

    @classmethod
    def build_context_block(
        cls,
        emotion_engine: Optional[EmotionEngine] = None,
        memory_manager: Optional[MemoryManager] = None,
        query: str = "",
    ) -> str:
        """
        Builds a compact, structured dynamic context block.
        """
        try:
            # 1. Emotional state extraction
            if emotion_engine is not None:
                state = emotion_engine.get_state_summary()
                current_mood = state.get("current_mood", "neutral")
                valence = state.get("valence", 0.55)
                rapport = state.get("rapport_level", 0.75)
                tone_directive = state.get("tone_directive", "Natural, warm, friendly Tanglish.")
            else:
                current_mood = "neutral"
                valence = 0.55
                rapport = 0.75
                tone_directive = "Natural, warm, friendly Tanglish."

            # 2. Memory & Identity context extraction
            profile_bullets = []
            episodes = []
            relevant_memories = []
            identity: Dict[str, Any] = {}

            if memory_manager is not None:
                mem_data = memory_manager.get_compact_memory_context(query=query)
                profile_bullets = mem_data.get("profile_bullets", [])
                episodes = mem_data.get("episodes", [])
                relevant_memories = mem_data.get("relevant_memories", [])
                identity = mem_data.get("identity", {})

            pref_name = identity.get("preferred_user_name")
            use_preferred_name = identity.get("use_preferred_name", True)
            is_creator = identity.get("is_creator", False)

            # When speaker is unknown or opted out, purge any personal/creator names from injected memory bullets
            if not pref_name or not use_preferred_name:
                filter_names = ("naresh", "ragavendhiran", "karthik", "rahul", "arun", "vani")
                profile_bullets = [b for b in profile_bullets if not any(n in b.lower() for n in filter_names)]
                episodes = [e for e in episodes if not any(n in e.lower() for n in filter_names)]
                relevant_memories = [m for m in relevant_memories if not any(n in m.lower() for n in filter_names)]
            else:
                # When a verified user is active, purge any episodes introducing conflicting or unverified names
                bad_names = ("vani", "working", "karthik", "rahul")
                episodes = [
                    e for e in episodes
                    if not any(b in e.lower() for b in bad_names)
                    and not ("introduced their" in e.lower() and pref_name.lower() not in e.lower())
                ]

            # 3. Speaker Identity & Creator Reconciliation Directives
            if not use_preferred_name:
                identity_directive = (
                    "SPEAKER IDENTITY & ADDRESS DIRECTIVE:\n"
                    "- The user explicitly requested NOT to be addressed by name.\n"
                    "- NEVER use any name for addressing. Respond naturally without a name.\n"
                    "- If asked 'Who am I?' or 'What is my name?': Reply that they prefer not to be called by name."
                )
            elif is_creator and pref_name == "Naresh":
                identity_directive = (
                    "SPEAKER IDENTITY & CREATOR RECONCILIATION:\n"
                    "- Verified user preferred name is 'Naresh'\n"
                    "- Verified Speaker: Naresh (Creator)\n"
                    "- Address Directive: You may address the user as Naresh naturally.\n"
                    "- Reconcile: Speaker is Naresh, one of your creators (along with Ragavendhiran). Acknowledge warmly. NEVER say 'You are another user'.\n"
                    "- STRICT ADDRESS RULE: Address user ONLY as Naresh. NEVER use any other name.\n"
                    "- If asked 'Who am I?': Respond 'You are Naresh, my creator.'\n"
                    "- If asked 'What is my name?': Respond 'Your name is Naresh.'\n"
                    "- If asked 'Who created you?': Respond 'You did, Naresh, along with Ragavendhiran.'"
                )
            elif is_creator:
                identity_directive = (
                    f"SPEAKER IDENTITY & CREATOR RECONCILIATION:\n"
                    f"- Verified user preferred name is '{pref_name or 'Creator'}'\n"
                    f"- Verified Speaker: {pref_name or 'Creator'} (Creator)\n"
                    "- Address Directive: Respond with natural respect and warmth.\n"
                    "- If asked 'Who am I?': Respond 'You are my creator.'\n"
                    f"- If asked 'What is my name?': Respond 'Your name is {pref_name or 'Creator'}.'\n"
                    "- If asked 'Who created you?': Respond 'You created me, along with Ragavendhiran.'"
                )
            elif pref_name:
                identity_directive = (
                    f"SPEAKER IDENTITY & ADDRESS DIRECTIVE:\n"
                    f"- Verified user preferred name is '{pref_name}'\n"
                    f"- Verified Speaker Name: {pref_name}\n"
                    f"- Address Directive: You may address the user as {pref_name} naturally.\n"
                    f"- If asked 'Who am I?': Respond 'You are {pref_name}.'\n"
                    f"- If asked 'What is my name?': Respond 'Your name is {pref_name}.'"
                )
            else:
                identity_directive = (
                    "SPEAKER IDENTITY & ADDRESS DIRECTIVE:\n"
                    "- Speaker Identity: Unknown speaker.\n"
                    "- Address Directive: No user name is known. NEVER invent, guess, or randomly select any name. Respond naturally without addressing the user by any name.\n"
                    "- If asked 'Who am I?' or 'What is my name?': Respond that identity/name is not yet confirmed; ask what they'd like to be called."
                )
                if query:
                    identity_directive += "\n- Creator metadata: DHEEPTHI was created by Naresh and Ragavendhiran."

            # If query is asking about past memory, retrieve targeted answer
            if memory_manager is not None and query:
                direct_ans = memory_manager.answer_memory_query(query)
                if direct_ans and direct_ans not in relevant_memories:
                    relevant_memories.insert(0, direct_ans)

            # 4. Format Profile, Relevant Memories & Episodes
            def _assemble_mem_section(bullets, rel_mems, eps):
                section = ""
                if rel_mems:
                    rel_str = "\n".join(f"- {m}" for m in rel_mems[:3])
                    section += f"\nDirectly Relevant Facts:\n{rel_str}\n"
                if bullets:
                    bullets_str = "\n".join(f"- {b}" for b in bullets)
                    section += f"\nUser Profile & Preferences:\n{bullets_str}\n"
                if eps:
                    episodes_str = "\n".join(f"- {e}" for e in eps[:2])
                    section += f"\nRecent Shared Context:\n{episodes_str}\n"
                return section

            active_bullets = list(profile_bullets[:12])
            mem_section = _assemble_mem_section(active_bullets, relevant_memories, episodes)

            def _assemble_block(m_sec):
                return (
                    "\n"
                    "==================================================\n"
                    "23. ACTIVE CONTEXT, EMOTIONAL STATE & MEMORY\n"
                    "==================================================\n"
                    f"Current Mood: {current_mood} (Valence: {valence:.2f}, Rapport: {rapport:.2f})\n\n"
                    f"Tone Directive:\n{tone_directive}\n\n"
                    f"{identity_directive}\n"
                    f"{m_sec}\n"
                    "CRITICAL BEHAVIOR RULES:\n"
                    "- CREATOR RECONCILIATION: Accept verified creator warmly; never contradict.\n"
                    "- CONVERSATIONAL IDENTITY ONLY: Identity never bypasses CommandDispatcher or system security.\n"
                    "- USER NAME SAFETY: NEVER invent or guess user's name. Use only verified name.\n"
                    "- NO MEMORY/EDUCATION FABRICATION: Never invent college, degree, dept, year, or facts not in memory.\n"
                    "- Modulate phrasing/empathy per Current Mood; emotional state affects conversational style only.\n"
                    "- NEVER refuse, delay, or alter laptop tasks or <ACTION> command tags.\n"
                    "==================================================\n"
                )

            block = _assemble_block(mem_section)
            while len(block) >= 1990 and len(active_bullets) > 4:
                active_bullets.pop()
                mem_section = _assemble_mem_section(active_bullets, relevant_memories, episodes)
                block = _assemble_block(mem_section)

            p_id = getattr(memory_manager, "profile_id", "default") if memory_manager else "none"
            print(f"[CONTEXT BUILDER DIAGNOSTIC] profile_id={p_id} block_len={len(block)} bullets_injected={len(active_bullets)} relevant_facts={len(relevant_memories)}")
            return block

        except Exception as error:
            print(f"[CONTEXT BUILDER] Error generating context block: {error}")
            return ""
