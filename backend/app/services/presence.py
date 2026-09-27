"""Live location sharing between the requester and the assigned volunteer (PLAN.md Iteration 2, item 4).

Only the latest point per (user, request) is stored, never a trail. Documents expire 120 s after the last update
(TTL index in db.py), and are deleted as soon as the request is released, resolved or cancelled, or the person
pauses sharing.
"""

from datetime import UTC, datetime

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.services.geo import destination, from_geojson, to_geojson

SIM_RADIUS_M = 45  # how far a demo account's simulated dot wanders from its origin
SIM_PERIOD_S = 60  # seconds per lap
MIN_INTERVAL_S = 5  # updates arriving sooner than this are dropped (PLAN.md §10)
STALE_AFTER_S = 45  # the client dims a dot that hasn't updated for this long


def _utc(value: datetime) -> datetime:
    """Mongo returns naive UTC datetimes; make them comparable with aware ones."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def age_seconds(updated_at: datetime, now: datetime) -> float:
    return max(0.0, (_utc(now) - _utc(updated_at)).total_seconds())


def is_throttled(previous_updated_at: datetime | None, now: datetime) -> bool:
    return previous_updated_at is not None and age_seconds(previous_updated_at, now) < MIN_INTERVAL_S


async def update_presence(
    database: AsyncDatabase, *, user_id: ObjectId, request_id: ObjectId, role: str, lat: float, lon: float,
    accuracy: float | None, now: datetime,
) -> bool:
    """Store the latest point. Returns False when dropped for arriving too soon after the previous one."""
    key = {"user_id": user_id, "request_id": request_id}
    previous = await database.presence.find_one(key, {"updated_at": 1})
    if previous and is_throttled(previous["updated_at"], now):
        return False
    await database.presence.update_one(
        key,
        {"$set": {"role": role, "location": to_geojson(lat, lon), "accuracy": accuracy, "updated_at": now}},
        upsert=True,
    )
    return True


async def other_party_location(
    database: AsyncDatabase, *, request_id: ObjectId, other_user_id: ObjectId, now: datetime
) -> dict | None:
    """The other person's latest point, or None if they aren't sharing (or their point has expired)."""
    doc = await database.presence.find_one({"user_id": other_user_id, "request_id": request_id})
    point = from_geojson(doc.get("location")) if doc else None
    if not point:
        return None
    return point | {"updated_at": _utc(doc["updated_at"]).isoformat(), "age_s": round(age_seconds(doc["updated_at"], now))}


async def stop_sharing(database: AsyncDatabase, *, user_id: ObjectId, request_id: ObjectId) -> None:
    await database.presence.delete_many({"user_id": user_id, "request_id": request_id})


async def clear_request(database: AsyncDatabase, request_id: ObjectId) -> None:
    """Called when a request leaves CLAIMED (released, resolved or cancelled): nobody is sharing after that."""
    await database.presence.delete_many({"request_id": request_id})


def simulated_point(origin: dict, now: datetime) -> dict:
    """A fake live position for a demo account: a slow lap around `origin`.

    Demo accounts have no device, so there is nothing real to share. The lap depends only on the clock, so the dot
    keeps moving between polls and every viewer sees the same place. The router marks the result `simulated`
    (CLAUDE.md rule 7); it is never stored as presence and never used for anything but the map.
    """
    phase = (_utc(now).timestamp() % SIM_PERIOD_S) / SIM_PERIOD_S
    lat, lon = destination(origin["lat"], origin["lon"], phase * 360, SIM_RADIUS_M)
    return {"lat": lat, "lon": lon, "updated_at": _utc(now).isoformat(), "age_s": 0}
