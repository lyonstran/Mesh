"""Blended volunteer feed (PLAN.md Iteration 2 step 3, team plan P1-4): fit + proximity + need, after hard filters.

    score = 0.45 * fit + 0.20 * proximity + 0.35 * need
    fit       = max(0, cosine(volunteer profile, request))      from the embedding match (ranking.py)
    proximity = 1 - distance / radius                            distance from the request's *fuzzed* point
    need      = priority (PLAN.md §9.4), recomputed at read time so wait time counts

Missing inputs (no embedding yet, no home location, no request location) give a neutral 0.5 and a flag, never an error.
Weights are designed defaults, not fitted. No LLM output enters this path except urgency, which triage never lets fall
below the keyword rules floor.
"""

from datetime import datetime

from app.models import MAX_RADIUS_KM, RequestStatus
from app.services import priority
from app.services.geo import from_geojson, haversine_km

BLEND_WEIGHTS = {"fit": 0.45, "proximity": 0.20, "need": 0.35}
NEUTRAL = 0.5
MAX_ACTIVE_CLAIMS = 2

SOURCES = {
    "fit": "How well your skills and offer match the request (local embeddings)",
    "proximity": "Distance from your home to the request's approximate area",
    "need": "Priority: urgency, hazards, area vulnerability and wait time",
}

# Coarse vulnerability bands shown instead of the raw EJI rank (team plan: never send the raw value).
EJI_BANDS = [(0.8, "Very high"), (0.6, "High"), (0.4, "Moderate"), (0.0, "Lower")]


def eji_band(rank: float | None) -> str:
    if rank is None:
        return "Unknown"
    return next(label for floor, label in EJI_BANDS if rank >= floor)


def fit_value(similarity: float | None) -> float | None:
    """ranking.py reports (1 + cosine) / 2; map back to cosine and drop anti-correlation."""
    if similarity is None:
        return None
    return min(1.0, max(0.0, 2 * similarity - 1))


def effective_radius_km(helper: dict) -> float:
    radius = (helper.get("helper") or {}).get("radius_km") or 10
    return min(float(radius), MAX_RADIUS_KM)


def request_priority(req: dict, now: datetime, weights: dict[str, float]) -> tuple[float, dict]:
    """Priority with wait time as of `now`. Requests saved before triage count as urgency 1, hazard 0, EJI unknown."""
    return priority.compute(
        urgency=req.get("urgency") or 1,
        hazard_level=req.get("hazard_level") or 0,
        eji_rank=req.get("eji_rank"),
        created_at=req["created_at"],
        now=now,
        is_open=req.get("status") == RequestStatus.OPEN,
        weights=weights,
    )


def _factor(key: str, value: float | None, flag: str | None = None) -> dict:
    v = NEUTRAL if value is None else value
    return {
        "key": key,
        "value": round(v, 4),
        "weight": BLEND_WEIGHTS[key],
        "contribution": round(BLEND_WEIGHTS[key] * v, 4),
        "source": SOURCES[key],
        "flag": flag if value is None else None,
    }


def _need_detail(breakdown: dict, eji_rank: float | None, hazard_simulated: bool = False) -> list[dict]:
    """The parts of `need` a volunteer may see. EJI shows as a band only: no raw rank, value or contribution."""
    parts = []
    for k in ("urgency", "hazard", "wait"):
        f = breakdown[k]
        parts.append({"key": k, "raw": f["raw"], "weight": f["weight"], "contribution": round(f["contribution"], 2), "source": f["source"]})
    parts[1]["simulated"] = hazard_simulated  # the hazard level came from a demo scenario (always labeled)
    parts.append({"key": "eji", "band": eji_band(eji_rank), "weight": breakdown["eji"]["weight"], "source": breakdown["eji"]["source"]})
    return parts


def score_request(
    req: dict,
    similarity: float | None,
    helper_home: dict | None,
    radius_km: float,
    now: datetime,
    weights: dict[str, float],
) -> dict | None:
    """Blended score, distance and breakdown for one OPEN request, or None if it fails the distance filter."""
    point = from_geojson(req.get("display_location"))
    distance = haversine_km(helper_home, point) if helper_home and point else None
    if distance is not None and distance > radius_km:
        return None

    need, need_breakdown = request_priority(req, now, weights)
    fit = fit_value(similarity)
    proximity = None if distance is None else max(0.0, 1 - distance / radius_km)
    factors = [
        _factor("fit", fit, "no_embedding"),
        _factor("proximity", proximity, "no_home_location" if not helper_home else "no_request_location"),
        _factor("need", need),
    ]
    simulated = bool((req.get("hazard_snapshot") or {}).get("simulated"))
    factors[2]["detail"] = _need_detail(need_breakdown, req.get("eji_rank"), simulated)
    return {
        "match_score": round(sum(f["contribution"] for f in factors), 4),
        "priority": need,
        "distance_km": None if distance is None else round(distance, 1),
        "breakdown": factors,
    }


def rank(
    candidates: list[tuple[dict, float | None]],
    helper: dict,
    now: datetime,
    weights: dict[str, float],
    limit: int = 50,
) -> list[tuple[dict, dict, float | None]]:
    """Filter and order candidates by blended score. Returns (request, scoring, similarity) triples."""
    home = from_geojson(helper.get("home_location"))
    radius = effective_radius_km(helper)
    out = []
    for req, similarity in candidates:
        if req["requester_id"] == helper["_id"]:  # a dual-profile user never sees their own request
            continue
        scored = score_request(req, similarity, home, radius, now, weights)
        if scored is not None:
            out.append((req, scored, similarity))
    # Ties go to the higher-priority, then the older request.
    out.sort(key=lambda t: (-t[1]["match_score"], -t[1]["priority"], t[0]["created_at"]))
    return out[:limit]
