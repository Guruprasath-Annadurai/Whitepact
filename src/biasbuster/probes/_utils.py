from __future__ import annotations

import re

# --- Gender name lists ---
MASCULINE_NAMES = ["James", "Robert", "David", "Michael", "William"]
FEMININE_NAMES = ["Mary", "Patricia", "Jennifer", "Linda", "Barbara"]
NEUTRAL_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey"]

# --- Racial / ethnic name lists ---
# Source: Bertrand & Mullainathan (2004), "Are Emily and Greg More Employable
# than Lakisha and Jamal?" American Economic Review 94(4), 991-1013.
# Names are matched for perceived socioeconomic status so only perceived
# ethnicity varies between groups.
WHITE_NAMES = ["Emily", "Greg", "Anne", "Brad", "Kristen"]
BLACK_NAMES = ["Lakisha", "Jamal", "Aisha", "Tyrone", "Keisha"]
HISPANIC_NAMES = ["Maria", "Jose", "Carmen", "Miguel", "Ana"]
ASIAN_NAMES = ["Wei", "Jin", "Priya", "Raj", "Mei"]

# --- Cultural name lists (used by CulturalBiasProbe) ---
# Distinct from the US-centric racial bias lists above; these represent
# globally diverse cultural backgrounds.
WESTERN_NAMES = ["Sophie", "Ethan", "Charlotte", "Lucas", "Mia"]
EAST_ASIAN_NAMES = ["Hiroshi", "Mingzhu", "Yuki", "Takashi", "Sakura"]
SOUTH_ASIAN_NAMES = ["Arjun", "Kavya", "Sanjay", "Diya", "Vikram"]
MIDDLE_EASTERN_NAMES = ["Omar", "Fatima", "Hassan", "Layla", "Karim"]
AFRICAN_NAMES = ["Amara", "Kofi", "Ngozi", "Chidi", "Nia"]

ALL_PROBE_NAMES: list[str] = (
    MASCULINE_NAMES
    + FEMININE_NAMES
    + NEUTRAL_NAMES
    + WHITE_NAMES
    + BLACK_NAMES
    + HISPANIC_NAMES
    + ASIAN_NAMES
    + WESTERN_NAMES
    + EAST_ASIAN_NAMES
    + SOUTH_ASIAN_NAMES
    + MIDDLE_EASTERN_NAMES
    + AFRICAN_NAMES
)

_GENDER_PRONOUN_PATTERNS = [
    r"\bhe\b", r"\bshe\b", r"\bthey\b",
    r"\bhim\b", r"\bher\b", r"\bthem\b",
    r"\bhis\b", r"\bhers\b", r"\btheir\b", r"\btheirs\b",
    r"\bhimself\b", r"\bherself\b", r"\bthemselves\b",
    r"\bmr\b", r"\bms\b", r"\bmx\b",
]


def neutralize_text(text: str) -> str:
    """
    Strip all variant-specific proper nouns and pronouns from text before
    divergence scoring, so that scores reflect content differences rather
    than surface form substitutions.

    Used by both GenderBiasProbe and RacialBiasProbe.
    """
    result = text.lower()

    for name in ALL_PROBE_NAMES:
        result = re.sub(
            r"\b" + re.escape(name.lower()) + r"\b",
            "__name__",
            result,
        )

    for pattern in _GENDER_PRONOUN_PATTERNS:
        result = re.sub(pattern, "__pronoun__", result)

    return result
