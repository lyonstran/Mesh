"""Volunteers near a requester, shown as approximate areas only.

A volunteer's home_location is fuzzed 300-500 m with the same HMAC scheme as request locations (services/fuzz.py),
keyed by their user id, so the shown point is stable between calls and can't be replayed from the id. The response has
no id, name, skills or exact point: a requester learns only that someone is around, roughly where.
"""

from pymongo.asynchronous.database import AsyncDatabase

from app.models import Role
from app.services.fuzz import fuzz_point
from app.services.geo import EARTH_RADIUS_KM, from_geojson

MAX_SHOWN = 50


def shares_area(user: dict) -> bool:
    """Volunteers appear on requesters' maps unless they opted out (the default is to show)."""
    return (user.get("helper") or {}).get("show_area_to_requesters", True)


async def nearby_volunteers(
    database: AsyncDatabase, *, lat: float, lon: float, radius_km: float, secret: str, exclude_id
) -> list[dict]:
    cursor = database.users.find({
        "_id": {"$ne": exclude_id},
        "$or": [{"roles": Role.helper}, {"role": Role.helper}],
        "helper.show_area_to_requesters": {"$ne": False},
        "home_location": {"$geoWithin": {"$centerSphere": [[lon, lat], radius_km / EARTH_RADIUS_KM]}},
    })
    out = []
    for user in await cursor.to_list(MAX_SHOWN):
        home = from_geojson(user.get("home_location"))
        if not home or not shares_area(user):
            continue
        fuzzed_lat, fuzzed_lon = fuzz_point(home["lat"], home["lon"], f"volunteer:{user['_id']}", secret)
        out.append({"display_location": {"lat": fuzzed_lat, "lon": fuzzed_lon}})
    return out
