"""Keyword rules for the emergency path (PLAN.md §9.2 step 1, §14.6). No LLM involved."""

import re
import unicodedata

# Patterns match accent-stripped, lowercased text. Err on the side of showing the 911 screen.
EMERGENCY_PATTERNS_EN = [
    r"can'?t breathe",
    r"cannot breathe",
    r"not breathing",
    r"trouble breathing",
    r"chest pain",
    r"heart attack",
    r"stroke",
    r"unconscious",
    r"passed out",
    r"unresponsive",
    r"not responding",
    r"overdos",
    r"trapped",
    r"bleeding (heavily|a lot|badly)",
    r"heavy bleeding",
    r"water (is )?(rising|coming) (inside|in)",
    r"on fire",
    r"\bfire\b",
]

EMERGENCY_PATTERNS_ES = [
    r"no puedo respirar",
    r"no (puede )?respira",
    r"dolor (de|en el) pecho",
    r"ataque al corazon",
    r"derrame cerebral",
    r"inconsciente",
    r"desmayad[oa]",
    r"no responde",
    r"atrapad[oa]s?",
    r"sangrando mucho",
    r"sangrado (fuerte|abundante)",
    r"el agua (esta )?(subiendo|entrando)",
    r"incendio",
    r"\bfuego\b",
]

_EMERGENCY_RE = re.compile("|".join(EMERGENCY_PATTERNS_EN + EMERGENCY_PATTERNS_ES))


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("’", "'")


def is_emergency(text: str) -> bool:
    return bool(_EMERGENCY_RE.search(_normalize(text)))
