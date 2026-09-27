"""Keyword rules: the emergency path, the urgency floor and fallback categories (PLAN.md §9.2 step 1, §14.6). No LLM."""

import re
import unicodedata
from dataclasses import dataclass

from app.models import Category, TriageFlag

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


# Fallback categories when the LLM is unavailable (PLAN.md §9.2 step 3): the first category with a match wins,
# so more specific needs come first. EN + ES, matched like the emergency patterns.
CATEGORY_PATTERNS: list[tuple[Category, list[str]]] = [
    (Category.power, [r"\bpower\b", r"electricity", r"\boutage", r"generator", r"\bcharg(e|ing)\b", r"electricidad", r"\bluz\b", r"\bcargar\b"]),
    (Category.medical_supplies, [r"oxygen", r"insulin", r"dialysis", r"medicat", r"medicine", r"prescription", r"oxigeno", r"insulina", r"medicina", r"medicamento", r"receta"]),
    (Category.water, [r"\bwater\b", r"\bagua\b"]),
    (Category.food, [r"\bfood\b", r"grocer", r"hungry", r"\bmeals?\b", r"baby formula", r"comida", r"alimento", r"hambre"]),
    (Category.transport, [r"\bride\b", r"drive (me|us)", r"transport", r"\blleve\b", r"llevar", r"transporte"]),
    (Category.shelter, [r"shelter", r"place to stay", r"refugio", r"albergue"]),
    (Category.debris, [r"\btrees?\b", r"branch", r"debris", r"\barbol", r"\bramas?\b", r"escombros"]),
    (Category.warming, [r"\bcold\b", r"freezing", r"no heat\b", r"heater", r"heating", r"\bfrio\b", r"calefaccion"]),
    (Category.cooling, [r"\bheat\b", r"too hot", r"air condition", r"\ba/?c\b", r"\bcalor\b"]),
    (Category.respiratory, [r"smoke", r"asthma", r"inhaler", r"\bhumo\b", r"\basma\b"]),
    (Category.welfare_check, [r"check on", r"welfare", r"hasn'?t (answered|responded)", r"haven'?t heard", r"ver como esta"]),
    (Category.supplies, [r"\btarps?\b", r"sandbag", r"diaper", r"batter(y|ies)", r"flashlight", r"supplies", r"\blona\b", r"panales", r"pilas", r"baterias"]),
]
_CATEGORY_RES = [(cat, re.compile("|".join(patterns))) for cat, patterns in CATEGORY_PATTERNS]


def rule_category(text: str) -> Category | None:
    normalized = _normalize(text)
    return next((cat for cat, pattern in _CATEGORY_RES if pattern.search(normalized)), None)


# HIGH terms (PLAN.md §9.2 step 1): floor 4 and the matching flag. EN + ES, matched like the emergency patterns.
# Spanish "ventilador" alone also means "fan", so only the unambiguous forms count for a ventilator.
HIGH_PATTERNS: list[tuple[TriageFlag, list[str]]] = [
    (TriageFlag.medical_device, [
        r"oxygen", r"concentrator", r"dialysis", r"insulin", r"ventilator", r"\bcpap\b",
        r"oxigeno", r"concentrador", r"dialisis", r"insulina", r"respirador", r"ventilador mecanico",
    ]),
    (TriageFlag.mobility, [
        r"wheelchair", r"bedridden", r"bed-bound", r"bedbound", r"can'?t walk", r"cannot walk",
        r"silla de ruedas", r"encamad[oa]", r"postrad[oa]", r"no puede caminar", r"no puedo caminar",
    ]),
    (TriageFlag.infant, [r"\binfants?\b", r"\bbaby\b", r"\bbabies\b", r"newborn", r"\bbebes?\b", r"recien nacid[oa]"]),
]
_HIGH_RES = [(flag, re.compile("|".join(patterns))) for flag, patterns in HIGH_PATTERNS]

# "Elderly alone": an older person and being alone in the same sentence, in either order.
_OLDER = (
    r"(\belderly\b|\bolder (man|woman|person|adult|lady|gentleman|neighbor|relative)|\bseniors?\b"
    r"|\bgrand(mother|father|ma|pa)\b|\b(i am|i'm|she'?s|he'?s|is) (7|8|9)\d\b"  # matched against lowercased text
    r"|\bancian[oa]s?\b|persona mayor|adulto mayor|\babuel[oa]s?\b)"
)
_ALONE = r"(\balone\b|by (her|him|my|them)sel(f|ves)|\bsol[oa]s?\b)"
_ELDERLY_ALONE_RE = re.compile(rf"{_OLDER}[^.!?]{{0,60}}{_ALONE}|{_ALONE}[^.!?]{{0,60}}{_OLDER}")

# Stored requester_flags raise the floor (PLAN.md §9.2 step 1).
_FLAG_FLOORS: dict[TriageFlag, int] = {TriageFlag.medical_device: 4, TriageFlag.mobility: 3, TriageFlag.lives_alone: 3}
HIGH_FLOOR = 4


@dataclass(frozen=True)
class RuleResult:
    """What the keyword rules decided. Triage merges the LLM on top and never goes below `floor`."""

    floor: int  # 1-5
    emergency: bool
    flags: frozenset[TriageFlag]
    category: Category | None


def high_need_flags(text: str) -> frozenset[TriageFlag]:
    """Flags from HIGH terms in the text. Any of them sets the floor to 4."""
    normalized = _normalize(text)
    flags = {flag for flag, pattern in _HIGH_RES if pattern.search(normalized)}
    if _ELDERLY_ALONE_RE.search(normalized):
        flags |= {TriageFlag.elderly, TriageFlag.lives_alone}
    return frozenset(flags)


def urgency_floor(text: str, requester_flags: dict | None = None) -> RuleResult:
    """The rules.urgency_floor contract: emergency terms → 5, HIGH terms → 4, stored flags → 4 or 3, else 1."""
    emergency = is_emergency(text)
    stored = frozenset(f for f in _FLAG_FLOORS if (requester_flags or {}).get(f))
    from_text = high_need_flags(text)
    floor = max([1, *(_FLAG_FLOORS[f] for f in stored), *([HIGH_FLOOR] if from_text else [])])
    if emergency:
        floor = 5
    return RuleResult(floor=floor, emergency=emergency, flags=stored | from_text, category=rule_category(text))
