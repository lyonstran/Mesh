from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings
from app.deps import get_database, parse_object_id, require_onboarded
from app.errors import APIError
from app.models import GeoPoint, RequestStatus
from app.services import presence
from app.services.geo import from_geojson
from app.services.serialize import relation

router = APIRouter(prefix="/api/requests")


class LocationUpdate(GeoPoint):
    accuracy: float | None = Field(None, ge=0, le=100_000)  # metres, from the device


async def _load_live(database: AsyncDatabase, request_id: str, user: dict) -> tuple[dict, str, object]:
    """The request, the caller's side of it, and the other person's id.

    Live location is between exactly two people: the requester and the assigned volunteer, and only while the
    request is CLAIMED. Everyone else gets 403, the same wall as the chat.
    """
    req = await database.requests.find_one({"_id": parse_object_id(request_id)})
    if req is None:
        raise APIError(404, "NOT_FOUND", "Request not found")
    rel = relation(req, user)
    if rel == "other":
        raise APIError(403, "FORBIDDEN", "Live location is private to the two people on this request")
    if req["status"] != RequestStatus.CLAIMED or not req.get("helper_id"):
        raise APIError(409, "NOT_ACTIVE", "Location sharing is only on while a volunteer is helping")
    other_id = req["helper_id"] if rel == "requester" else req["requester_id"]
    return req, rel, other_id


@router.post("/{request_id}/location")
async def share_location(
    request_id: str,
    body: LocationUpdate,
    user: dict = Depends(require_onboarded),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    req, rel, _ = await _load_live(database, request_id, user)
    accepted = await presence.update_presence(
        database, user_id=user["_id"], request_id=req["_id"], role=rel, lat=body.lat, lon=body.lon,
        accuracy=body.accuracy, now=datetime.now(UTC),
    )
    return {"ok": True, "throttled": not accepted}


@router.get("/{request_id}/location")
async def other_location(
    request_id: str, user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)
) -> dict:
    """Only the OTHER person's point. Your own is never echoed back."""
    req, _, other_id = await _load_live(database, request_id, user)
    now = datetime.now(UTC)
    point = await presence.other_party_location(database, request_id=req["_id"], other_user_id=other_id, now=now)
    simulated = False
    if point is None and get_settings().demo_login:
        # A demo account has no phone to share from. When the other person is one and isn't really sharing, show a
        # clearly labelled simulated position so the feature can be seen working.
        other_user = await database.users.find_one({"_id": other_id}, {"demo": 1, "home_location": 1})
        if other_user and other_user.get("demo"):
            origin = from_geojson(req.get("location")) if other_id == req["requester_id"] else from_geojson(other_user.get("home_location"))
            if origin:
                point, simulated = presence.simulated_point(origin, now), True
    return {"other": point, "simulated": simulated, "stale_after_s": presence.STALE_AFTER_S}


@router.delete("/{request_id}/location")
async def stop_sharing(
    request_id: str, user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)
) -> dict:
    """Pause sharing: deletes the caller's stored point right away. Works only for the two participants."""
    req = await database.requests.find_one({"_id": parse_object_id(request_id)})
    if req is None:
        raise APIError(404, "NOT_FOUND", "Request not found")
    if relation(req, user) == "other":
        raise APIError(403, "FORBIDDEN", "Live location is private to the two people on this request")
    await presence.stop_sharing(database, user_id=user["_id"], request_id=req["_id"])
    return {"ok": True}
