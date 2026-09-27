"""Viewer-aware serialization (PLAN.md §9.6, MVP table in §0.1).

Every request and user that leaves the backend goes through this module.
"""

from datetime import datetime
from typing import Literal

from app.models import RequestStatus, held_roles
from app.services.geo import from_geojson

Relation = Literal["requester", "assigned_helper", "other"]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def relation(req: dict, viewer: dict) -> Relation:
    if req.get("requester_id") == viewer["_id"]:
        return "requester"
    if (
        req.get("helper_id") == viewer["_id"]
        and req.get("status") in (RequestStatus.CLAIMED, RequestStatus.RESOLVED)
    ):
        return "assigned_helper"
    return "other"


def public_user(user: dict) -> dict:
    """The signed-in user's own profile (never includes embeddings or google_sub)."""
    return {
        "id": str(user["_id"]),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "role": user.get("role"),
        "roles": held_roles(user),
        "home_location": from_geojson(user.get("home_location")),
        "language": user.get("language", "en"),
        "background": user.get("background", ""),
        "helper": user.get("helper"),
        "requester_flags": user.get("requester_flags"),
    }


def _person(user: dict | None, *, with_details: bool) -> dict | None:
    if user is None:
        return None
    out = {"id": str(user["_id"]), "name": user.get("name")}
    if with_details:
        out |= {
            "language": user.get("language", "en"),
            "background": user.get("background", ""),
            "requester_flags": user.get("requester_flags"),
        }
    return out


def serialize_request(
    req: dict,
    viewer: dict,
    *,
    requester: dict | None = None,
    helper: dict | None = None,
    score: float | None = None,
) -> dict:
    rel = relation(req, viewer)
    out = {
        "id": str(req["_id"]),
        "text": req["text"],
        "language": req.get("language", "en"),
        "status": req["status"],
        "emergency": req.get("emergency", False),
        "created_at": _iso(req.get("created_at")),
        "updated_at": _iso(req.get("updated_at")),
        "viewer_relation": rel,
    }
    if score is not None:
        out["score"] = round(score, 4)
    # Everyone sees the fuzzed point; the exact one is only for the two people on the request (PLAN.md §9.6).
    if display := from_geojson(req.get("display_location")):
        out["display_location"] = display
    if rel == "other":
        return out
    if exact := from_geojson(req.get("location")):
        out["location"] = exact

    out |= {
        "claimed_at": _iso(req.get("claimed_at")),
        "resolved_at": _iso(req.get("resolved_at")),
        "timeline": [
            {"status": t["status"], "at": _iso(t["at"]), "by": str(t["by"]) if t.get("by") else None}
            for t in req.get("timeline", [])
        ],
    }
    if rel == "requester":
        has_helper = req.get("status") in (RequestStatus.CLAIMED, RequestStatus.RESOLVED)
        out["helper"] = _person(helper, with_details=False) if has_helper else None
    else:  # assigned_helper
        out["requester"] = _person(requester, with_details=True)
    return out


def serialize_message(msg: dict, viewer: dict) -> dict:
    return {
        "id": str(msg["_id"]),
        "request_id": str(msg["request_id"]),
        "from_user_id": str(msg["from_user_id"]),
        "mine": msg["from_user_id"] == viewer["_id"],
        "text": msg["text"],
        "ts": _iso(msg["ts"]),
    }
