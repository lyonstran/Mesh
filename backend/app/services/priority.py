"""Request priority (PLAN.md §9.4). All numbers come from code; the LLM only contributes urgency via triage,
and triage never lowers the rules floor.

    priority = W_u*u + W_h*h + W_e*e + W_w*w
    u = (urgency - 1) / 4, h = hazard_level / 3, e = eji_rank (0.5 when missing), w = min(minutes_open / 60, 1)

Weights are designed defaults, not fitted.
"""

from datetime import datetime

from pymongo.asynchronous.database import AsyncDatabase

from app.db import DEFAULT_WEIGHTS

FACTORS = ("urgency", "hazard", "eji", "wait")
EJI_MISSING_VALUE = 0.5
WEIGHTS_NOTE = "Weights are designed defaults, not fitted."

SOURCES = {
    "urgency": "Triage: keyword rules floor, raised (never lowered) by AI",
    "hazard": "NWS alerts (official) + Open-Meteo (derived, max level 2)",
    "eji": "CDC/ATSDR EJI 2024 tract rank",
    "wait": "Minutes since posted (while open, caps at 60)",
}


def normalize_weights(raw: dict) -> dict[str, float]:
    """Non-negative weights scaled to sum to 1. Falls back to the defaults if they're all zero or missing."""
    weights = {k: max(0.0, float(raw.get(k, 0) or 0)) for k in FACTORS}
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in weights.items()}


async def load_weights(db: AsyncDatabase) -> dict[str, float]:
    doc = await db.settings.find_one({"_id": "weights"}) or {}
    return normalize_weights({k: doc.get(k, DEFAULT_WEIGHTS[k]) for k in FACTORS})


def compute(
    *,
    urgency: int,
    hazard_level: int,
    eji_rank: float | None,
    created_at: datetime,
    now: datetime,
    is_open: bool,
    weights: dict[str, float],
) -> tuple[float, dict]:
    """Priority in [0, 1] and its breakdown: each factor's raw value, normalized value, weight and contribution."""
    minutes_open = max(0.0, (now - created_at).total_seconds() / 60) if is_open else 0.0
    raw = {"urgency": urgency, "hazard": hazard_level, "eji": eji_rank, "wait": round(minutes_open, 1)}
    value = {
        "urgency": (min(max(urgency, 1), 5) - 1) / 4,
        "hazard": min(max(hazard_level, 0), 3) / 3,
        "eji": EJI_MISSING_VALUE if eji_rank is None else min(max(eji_rank, 0.0), 1.0),
        "wait": min(minutes_open / 60, 1.0),
    }
    breakdown: dict = {
        k: {
            "raw": raw[k],
            "value": round(value[k], 4),
            "weight": round(weights[k], 4),
            "contribution": round(weights[k] * value[k], 4),
            "source": SOURCES[k],
        }
        for k in FACTORS
    }
    priority = sum(weights[k] * value[k] for k in FACTORS)
    breakdown["eji_missing"] = eji_rank is None
    breakdown["weights"] = {k: round(weights[k], 4) for k in FACTORS}
    breakdown["note"] = WEIGHTS_NOTE
    return round(priority, 4), breakdown
