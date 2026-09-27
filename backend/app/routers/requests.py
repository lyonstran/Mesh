from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings
from app.deps import get_database, parse_object_id, require_onboarded, require_role
from app.errors import APIError
from app.models import ACTIVE_STATUSES, RequestCreate, RequestStatus, Role, TextIn, Triage, held_roles
from app.services import matching, preview_cache, presence, priority, ranking
from app.services.fuzz import fuzz_point
from app.services.geo import to_geojson
from app.services.hazards import get_hazards
from app.services.indexing import refresh_request_embedding
from app.services.rules import RuleResult, is_emergency, urgency_floor
from app.services.triage import apply_category_override, merge, triage
from app.services.serialize import relation, serialize_request
from app.services.state import Actor, check_transition
from app.services.tracts import tract_for_point

router = APIRouter(prefix="/api/requests")


async def _people(database: AsyncDatabase, reqs: list[dict]) -> dict[ObjectId, dict]:
    ids = {r["requester_id"] for r in reqs} | {r["helper_id"] for r in reqs if r.get("helper_id")}
    users = await database.users.find({"_id": {"$in": list(ids)}}).to_list()
    return {u["_id"]: u for u in users}


async def _serialize_many(database: AsyncDatabase, reqs: list[dict], viewer: dict) -> list[dict]:
    people = await _people(database, reqs)
    return [
        serialize_request(r, viewer, requester=people.get(r["requester_id"]), helper=people.get(r.get("helper_id")))
        for r in reqs
    ]


async def _serialize_one(database: AsyncDatabase, req: dict, viewer: dict) -> dict:
    return (await _serialize_many(database, [req], viewer))[0]


async def _load_visible(database: AsyncDatabase, request_id: str, user: dict) -> dict:
    """Load a request the user may see: their own, one they're assigned to, or any OPEN one for helpers."""
    req = await database.requests.find_one({"_id": parse_object_id(request_id)})
    if req is None:
        raise APIError(404, "NOT_FOUND", "Request not found")
    if relation(req, user) == "other" and not (Role.helper in held_roles(user) and req["status"] == RequestStatus.OPEN):
        raise APIError(404, "NOT_FOUND", "Request not found")
    return req


def _actor(req: dict, user: dict) -> Actor:
    rel = relation(req, user)
    if rel == "requester":
        return "requester"
    if req.get("helper_id") == user["_id"]:
        return "assigned_helper"
    return "helper"


async def _transition(
    database: AsyncDatabase, req: dict, user: dict, target: RequestStatus, set_fields: dict | None = None, unset: list[str] | None = None
) -> dict:
    check_transition(RequestStatus(req["status"]), target, _actor(req, user))
    now = datetime.now(UTC)
    update: dict = {
        "$set": {"status": target, "updated_at": now, **(set_fields or {})},
        "$push": {"timeline": {"status": target, "at": now, "by": user["_id"]}},
    }
    if unset:
        update["$unset"] = {f: "" for f in unset}
    # Guard on the current status so concurrent changes can't both succeed.
    updated = await database.requests.find_one_and_update(
        {"_id": req["_id"], "status": req["status"]}, update, return_document=ReturnDocument.AFTER
    )
    if updated is None:
        raise APIError(409, "CONFLICT", "This request changed; refresh and try again")
    await presence.clear_request(database, req["_id"])  # release, resolve and cancel all end live sharing
    await _store_priority(database, updated)
    return updated


@router.post("/check")
async def check(body: TextIn, _: dict = Depends(require_role(Role.requester))) -> dict:
    return {"emergency": is_emergency(body.text)}


async def _hazards_at(database: AsyncDatabase, body: RequestCreate) -> dict | None:
    return await get_hazards(database, body.location.lat, body.location.lon) if body.location else None


def _hazard_types(report: dict | None) -> list[str]:
    return sorted({h["type"] for h in (report or {}).get("hazards", [])})


def _reconcile(card: Triage, rule: RuleResult) -> Triage:
    """Re-apply today's rules to a cached preview: the floor, emergency and flags can only go up."""
    return card.model_copy(
        update={
            "urgency": max(card.urgency, rule.floor),
            "urgency_rule_floor": rule.floor,
            "emergency": rule.emergency,
            "flags": sorted(set(card.flags) | rule.flags),
        }
    )


@router.post("/preview")
async def preview(
    body: RequestCreate,
    user: dict = Depends(require_role(Role.requester)),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    """The triage card for the two-step submit (PLAN.md §9.2 step 4). Saves nothing."""
    rule = urgency_floor(body.text, user.get("requester_flags"))
    hazard_types = _hazard_types(await _hazards_at(database, body))
    card = await triage(body.text, hazard_types, rule, language=user.get("language", "en"))
    loc = body.location
    preview_cache.put(user["_id"], body.text, loc and loc.lat, loc and loc.lon, card)
    card = apply_category_override(card, body.category_override)
    return {"triage": card.model_dump(mode="json"), "emergency": card.emergency}


@router.post("")
async def create(
    body: RequestCreate,
    background: BackgroundTasks,
    user: dict = Depends(require_role(Role.requester)),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    """Save a request (PLAN.md §9.3): triage, tract + EJI, hazards, fuzzed location, priority, insert."""
    active = await database.requests.find_one({"requester_id": user["_id"], "status": {"$in": list(ACTIVE_STATUSES)}})
    if active:
        raise APIError(409, "ACTIVE_REQUEST_EXISTS", "You already have an active request")
    language = user.get("language", "en")
    loc = body.location

    # 1. Triage. The rules always run here; the AI card comes from the preview when there was one.
    rule = urgency_floor(body.text, user.get("requester_flags"))
    hazard_report = await _hazards_at(database, body)
    cached = preview_cache.take(user["_id"], body.text, loc and loc.lat, loc and loc.lon)
    if cached is not None:
        card = _reconcile(cached, rule)
    elif rule.emergency:
        # Don't make someone in an emergency wait on the AI: urgency is already 5 from the rules.
        card = merge(rule, None, body.text, language)
    else:
        card = await triage(body.text, _hazard_types(hazard_report), rule, language=language)
    card = apply_category_override(card, body.category_override)

    # 2-3. Tract + EJI (from the exact point) and the hazard snapshot.
    tract = await tract_for_point(database, loc.lat, loc.lon) if loc else None
    hazard_level = hazard_report["level"] if hazard_report else 0

    now = datetime.now(UTC)
    # 5. Priority. Wait time is 0 at create; the feed recomputes it at read time (PLAN.md §9.4).
    score, breakdown = priority.compute(
        urgency=card.urgency,
        hazard_level=hazard_level,
        eji_rank=tract.get("eji_rank") if tract else None,
        created_at=now,
        now=now,
        is_open=True,
        weights=await priority.load_weights(database),
    )
    request_id = ObjectId()
    doc = {
        "_id": request_id,
        "requester_id": user["_id"],
        "text": body.text,
        "language": language,
        "emergency": card.emergency,
        "category": card.category,
        "urgency": card.urgency,
        "urgency_rule_floor": card.urgency_rule_floor,
        "flags": list(card.flags),
        "needs": card.needs,
        "summary": card.summary,
        "triage_source": card.source,
        "tract_geoid": tract["geoid"] if tract else None,
        "eji_rank": tract.get("eji_rank") if tract else None,
        "hazard_snapshot": hazard_report,
        "hazard_level": hazard_level,
        "priority": score,
        "priority_breakdown": breakdown,
        "status": RequestStatus.OPEN,
        "helper_id": None,
        "embed_text": None,  # filled in after the response by refresh_request_embedding
        "embedding": None,
        "timeline": [{"status": RequestStatus.OPEN, "at": now, "by": user["_id"]}],
        "created_at": now,
        "updated_at": now,
    }
    if loc:
        # 4. Fuzzed location for everyone but the two people on the request.
        fuzzed_lat, fuzzed_lon = fuzz_point(loc.lat, loc.lon, str(request_id), get_settings().jwt_secret)
        doc["location"] = to_geojson(loc.lat, loc.lon)
        doc["display_location"] = to_geojson(fuzzed_lat, fuzzed_lon)
    await database.requests.insert_one(doc)
    background.add_task(refresh_request_embedding, database, doc["_id"], body.text)
    return {"request": await _serialize_one(database, doc, user), "show_911": card.emergency}


@router.get("/mine")
async def mine(user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)) -> dict:
    if user["role"] == Role.requester:
        query: dict = {"requester_id": user["_id"]}
    else:
        query = {"helper_id": user["_id"], "status": {"$in": [RequestStatus.CLAIMED, RequestStatus.RESOLVED]}}
    reqs = await database.requests.find(query).sort("updated_at", -1).limit(20).to_list()
    return {"requests": await _serialize_many(database, reqs, user)}


async def _active_claims(database: AsyncDatabase, helper_id: ObjectId) -> int:
    return await database.requests.count_documents({"helper_id": helper_id, "status": RequestStatus.CLAIMED})


@router.get("/ranked")
async def ranked(user: dict = Depends(require_role(Role.helper)), database: AsyncDatabase = Depends(get_database)) -> dict:
    """OPEN requests for this volunteer: hard filters, then fit + proximity + need (services/matching.py)."""
    active = await _active_claims(database, user["_id"])
    base = {
        "vector_search": ranking.mode(),
        "profile_embedded": bool(user.get("embedding")),
        "home_set": bool(user.get("home_location")),
        "radius_km": matching.effective_radius_km(user),
        "active_claims": active,
        "claim_limit": matching.MAX_ACTIVE_CLAIMS,
        "weights_note": priority.WEIGHTS_NOTE,
    }
    if active >= matching.MAX_ACTIVE_CLAIMS:
        return base | {"requests": [], "claim_limit_reached": True}
    # Fetch a wide slate by similarity, then filter and re-rank with the blend.
    candidates = await ranking.rank_open_requests(database, user, limit=100)
    weights = await priority.load_weights(database)
    results = matching.rank(candidates, user, datetime.now(UTC), weights)
    requests = []
    for req, scored, similarity in results:
        out = serialize_request(req, user, score=similarity)
        out |= {
            "match_score": scored["match_score"],
            "distance_km": scored["distance_km"],
            "breakdown": scored["breakdown"],
        }
        requests.append(out)
    return base | {"requests": requests, "claim_limit_reached": False}


@router.get("/{request_id}")
async def get_one(request_id: str, user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)) -> dict:
    req = await _load_visible(database, request_id, user)
    return {"request": await _serialize_one(database, req, user)}


@router.post("/{request_id}/claim")
async def claim(request_id: str, user: dict = Depends(require_role(Role.helper)), database: AsyncDatabase = Depends(get_database)) -> dict:
    oid = parse_object_id(request_id)
    if await _active_claims(database, user["_id"]) >= matching.MAX_ACTIVE_CLAIMS:
        raise _claim_limit()
    now = datetime.now(UTC)
    req = await database.requests.find_one_and_update(
        # The requester_id guard keeps the check atomic with the claim itself.
        {"_id": oid, "status": RequestStatus.OPEN, "requester_id": {"$ne": user["_id"]}},
        {
            "$set": {"status": RequestStatus.CLAIMED, "helper_id": user["_id"], "claimed_at": now, "updated_at": now},
            "$push": {"timeline": {"status": RequestStatus.CLAIMED, "at": now, "by": user["_id"]}},
        },
        return_document=ReturnDocument.AFTER,
    )
    if req is None:
        existing = await database.requests.find_one({"_id": oid}, {"requester_id": 1})
        if existing:
            if existing["requester_id"] == user["_id"]:
                raise APIError(409, "OWN_REQUEST", "You can't pick up your own request")
            raise APIError(409, "ALREADY_CLAIMED", "Someone else already picked this request")
        raise APIError(404, "NOT_FOUND", "Request not found")
    # Two claims racing past the check above could both land; undo this one if the cap is now exceeded.
    if await _active_claims(database, user["_id"]) > matching.MAX_ACTIVE_CLAIMS:
        await database.requests.update_one(
            {"_id": oid, "status": RequestStatus.CLAIMED, "helper_id": user["_id"]},
            {"$set": {"status": RequestStatus.OPEN, "helper_id": None, "updated_at": datetime.now(UTC)},
             "$unset": {"claimed_at": ""}, "$pop": {"timeline": 1}},
        )
        raise _claim_limit()
    await _store_priority(database, req)
    return {"request": await _serialize_one(database, req, user)}


def _claim_limit() -> APIError:
    return APIError(
        409, "CLAIM_LIMIT", f"You're already helping with {matching.MAX_ACTIVE_CLAIMS} requests. Finish or release one first."
    )


async def _store_priority(database: AsyncDatabase, req: dict) -> None:
    """Persist priority on status changes (PLAN.md §9.4); the feed still recomputes it at read time."""
    if "created_at" not in req:
        return
    score, breakdown = matching.request_priority(req, datetime.now(UTC), await priority.load_weights(database))
    await database.requests.update_one({"_id": req["_id"]}, {"$set": {"priority": score, "priority_breakdown": breakdown}})


@router.post("/{request_id}/release")
async def release(request_id: str, user: dict = Depends(require_role(Role.helper)), database: AsyncDatabase = Depends(get_database)) -> dict:
    req = await _load_visible(database, request_id, user)
    req = await _transition(database, req, user, RequestStatus.OPEN, set_fields={"helper_id": None}, unset=["claimed_at"])
    return {"request": await _serialize_one(database, req, user)}


@router.post("/{request_id}/resolve")
async def resolve(request_id: str, user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)) -> dict:
    req = await _load_visible(database, request_id, user)
    req = await _transition(database, req, user, RequestStatus.RESOLVED, set_fields={"resolved_at": datetime.now(UTC)})
    return {"request": await _serialize_one(database, req, user)}


@router.post("/{request_id}/cancel")
async def cancel(request_id: str, user: dict = Depends(require_role(Role.requester)), database: AsyncDatabase = Depends(get_database)) -> dict:
    req = await _load_visible(database, request_id, user)
    req = await _transition(database, req, user, RequestStatus.CANCELLED)
    return {"request": await _serialize_one(database, req, user)}
