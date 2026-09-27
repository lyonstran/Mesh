"""Simulation mode (PLAN.md §7): demo disaster scenarios merged into real hazard results, always labeled.

Scenarios live in app/scenarios/*.json and must carry "label": "SIMULATED". While one is active (and only while
DEMO_LOGIN is on, so a leftover flag in the database can never leak simulated hazards into a real deployment):
- get_hazards() merges the scenario's hazards into points inside its areas and sets simulated: true;
- the region feed adds the scenario's areas as clearly labeled "Simulation" alerts;
- open requests are re-scored on activate and deactivate, so priority reflects the scenario.
Scenario hazards are never presented as official: source is "Simulation" and official is false.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from pymongo.asynchronous.database import AsyncDatabase
from shapely.geometry import Point, shape

from app.config import get_settings
from app.models import Hazard

log = logging.getLogger("mesh.sim")

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"
RESCORE_CONCURRENCY = 8


class UnknownScenario(Exception):
    pass


@lru_cache
def scenarios() -> dict[str, dict]:
    out = {}
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("label") != "SIMULATED":
            raise ValueError(f"{path.name} must carry \"label\": \"SIMULATED\" (PLAN.md §7)")
        data["_shapes"] = {name: shape(g) for name, g in data.get("areas", {}).items()}
        out[data["id"]] = data
    return out


def public_scenario(s: dict) -> dict:
    return {"id": s["id"], "title": s["title"], "description": s["description"], "label": s["label"]}


async def state(db: AsyncDatabase) -> dict:
    doc = await db.settings.find_one({"_id": "sim"}) or {}
    active = bool(doc.get("active")) and get_settings().demo_login and doc.get("scenario_id") in scenarios()
    return {
        "active": active,
        "scenario_id": doc.get("scenario_id") if active else None,
        "activated_at": doc["activated_at"].isoformat() if active and doc.get("activated_at") else None,
        "scenarios": [public_scenario(s) for s in scenarios().values()],
    }


async def _active(db: AsyncDatabase) -> tuple[dict, datetime] | None:
    if not get_settings().demo_login:
        return None
    doc = await db.settings.find_one({"_id": "sim"}) or {}
    scenario = scenarios().get(doc.get("scenario_id") or "")
    if not doc.get("active") or scenario is None:
        return None
    return scenario, doc.get("activated_at") or datetime.now(UTC)


def _hazards_for(scenario: dict, activated_at: datetime, area_names: set[str]) -> list[Hazard]:
    expires = (activated_at + timedelta(hours=scenario.get("duration_hours", 6))).isoformat()
    return [
        Hazard(**{k: v for k, v in h.items() if k != "area"} | ({"expires": expires} if h.get("event") else {}))
        for h in scenario["hazards"]
        if h.get("area") in area_names
    ]


async def merge(report: dict, db: AsyncDatabase, lat: float, lon: float) -> dict:
    """The sim.merge contract: add the active scenario's hazards for a point inside its areas; label it simulated."""
    active = await _active(db)
    if active is None:
        return report
    scenario, activated_at = active
    point = Point(lon, lat)
    inside = {name for name, geom in scenario["_shapes"].items() if geom.contains(point)}
    if not inside:
        return report
    from app.services.hazards import likely_needs  # hazards.py imports this module

    hazards = [Hazard(**h) for h in report["hazards"]] + _hazards_for(scenario, activated_at, inside)
    hazards.sort(key=lambda h: (-h.level, not h.official))
    return report | {
        "hazards": [h.model_dump() for h in hazards],
        "level": max((h.level for h in hazards), default=0),
        "likely_needs": likely_needs(hazards),
        "current": report["current"] | scenario.get("current", {}),
        "simulated": True,
    }


async def merge_region(report: dict, db: AsyncDatabase) -> dict:
    """Add the active scenario's areas to the statewide alert feed as labeled simulation alerts."""
    active = await _active(db)
    if active is None:
        return report
    scenario, activated_at = active
    features = []
    for h in _hazards_for(scenario, activated_at, set(scenario["_shapes"])):
        if not h.event:  # derived readings have no area of their own
            continue
        area = next(x["area"] for x in scenario["hazards"] if x.get("event") == h.event)
        features.append({
            "type": "Feature",
            "geometry": scenario["areas"][area],
            "properties": {
                "id": f"sim-{scenario['id']}-{area}",
                "event": h.event,
                "type": h.type,
                "level": h.level,
                "official": False,
                "source": "Simulation",
                "headline": h.headline,
                "area_desc": f"SIMULATED: {scenario['title']}",
                "expires": h.expires,
                "instruction": h.instruction,
            },
        })
    return report | {"features": features + report["features"], "simulated": True}


async def rescore_open_requests(db: AsyncDatabase) -> int:
    """Refresh the hazard snapshot and priority of every OPEN request with a location (on activate/deactivate)."""
    from app.services import matching, priority
    from app.services.geo import from_geojson
    from app.services.hazards import get_hazards

    weights = await priority.load_weights(db)
    gate = asyncio.Semaphore(RESCORE_CONCURRENCY)
    reqs = await db.requests.find({"status": "OPEN", "location": {"$exists": True}}).to_list()

    async def one(req: dict) -> None:
        point = from_geojson(req["location"])
        if point is None:
            return
        async with gate:
            report = await get_hazards(db, point["lat"], point["lon"])
        req |= {"hazard_snapshot": report, "hazard_level": report["level"]}
        score, breakdown = matching.request_priority(req, datetime.now(UTC), weights)
        await db.requests.update_one(
            {"_id": req["_id"]},
            {"$set": {"hazard_snapshot": report, "hazard_level": report["level"], "priority": score, "priority_breakdown": breakdown}},
        )

    await asyncio.gather(*(one(r) for r in reqs))
    return len(reqs)


async def activate(db: AsyncDatabase, scenario_id: str) -> int:
    if scenario_id not in scenarios():
        raise UnknownScenario(scenario_id)
    await db.settings.update_one(
        {"_id": "sim"}, {"$set": {"active": True, "scenario_id": scenario_id, "activated_at": datetime.now(UTC)}}, upsert=True
    )
    return await rescore_open_requests(db)


async def deactivate(db: AsyncDatabase) -> int:
    await db.settings.update_one({"_id": "sim"}, {"$set": {"active": False, "scenario_id": None, "activated_at": None}}, upsert=True)
    return await rescore_open_requests(db)
