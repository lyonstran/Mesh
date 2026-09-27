from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_database, parse_object_id, require_onboarded, require_role
from app.errors import APIError
from app.models import ACTIVE_STATUSES, RequestCreate, RequestStatus, Role, TextIn
from app.services import ranking
from app.services.indexing import refresh_request_embedding
from app.services.rules import is_emergency
from app.services.serialize import relation, serialize_request
from app.services.state import Actor, check_transition

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
    if relation(req, user) == "other" and not (user["role"] == Role.helper and req["status"] == RequestStatus.OPEN):
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
    return updated


@router.post("/check")
async def check(body: TextIn, _: dict = Depends(require_role(Role.requester))) -> dict:
    return {"emergency": is_emergency(body.text)}


@router.post("")
async def create(
    body: RequestCreate,
    background: BackgroundTasks,
    user: dict = Depends(require_role(Role.requester)),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    active = await database.requests.find_one({"requester_id": user["_id"], "status": {"$in": list(ACTIVE_STATUSES)}})
    if active:
        raise APIError(409, "ACTIVE_REQUEST_EXISTS", "You already have an active request")
    emergency = is_emergency(body.text)
    now = datetime.now(UTC)
    doc = {
        "requester_id": user["_id"],
        "text": body.text,
        "language": user.get("language", "en"),
        "emergency": emergency,
        "status": RequestStatus.OPEN,
        "helper_id": None,
        "embed_text": None,  # filled in after the response by refresh_request_embedding
        "embedding": None,
        "timeline": [{"status": RequestStatus.OPEN, "at": now, "by": user["_id"]}],
        "created_at": now,
        "updated_at": now,
    }
    doc["_id"] = (await database.requests.insert_one(doc)).inserted_id
    background.add_task(refresh_request_embedding, database, doc["_id"], body.text)
    return {"request": await _serialize_one(database, doc, user), "show_911": emergency}


@router.get("/mine")
async def mine(user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)) -> dict:
    if user["role"] == Role.requester:
        query: dict = {"requester_id": user["_id"]}
    else:
        query = {"helper_id": user["_id"], "status": {"$in": [RequestStatus.CLAIMED, RequestStatus.RESOLVED]}}
    reqs = await database.requests.find(query).sort("updated_at", -1).limit(20).to_list()
    return {"requests": await _serialize_many(database, reqs, user)}


@router.get("/ranked")
async def ranked(user: dict = Depends(require_role(Role.helper)), database: AsyncDatabase = Depends(get_database)) -> dict:
    results = await ranking.rank_open_requests(database, user)
    return {
        "requests": [serialize_request(r, user, score=score) for r, score in results],
        "vector_search": ranking.mode(),
        "profile_embedded": bool(user.get("embedding")),
    }


@router.get("/{request_id}")
async def get_one(request_id: str, user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)) -> dict:
    req = await _load_visible(database, request_id, user)
    return {"request": await _serialize_one(database, req, user)}


@router.post("/{request_id}/claim")
async def claim(request_id: str, user: dict = Depends(require_role(Role.helper)), database: AsyncDatabase = Depends(get_database)) -> dict:
    oid = parse_object_id(request_id)
    now = datetime.now(UTC)
    req = await database.requests.find_one_and_update(
        {"_id": oid, "status": RequestStatus.OPEN},
        {
            "$set": {"status": RequestStatus.CLAIMED, "helper_id": user["_id"], "claimed_at": now, "updated_at": now},
            "$push": {"timeline": {"status": RequestStatus.CLAIMED, "at": now, "by": user["_id"]}},
        },
        return_document=ReturnDocument.AFTER,
    )
    if req is None:
        if await database.requests.count_documents({"_id": oid}, limit=1):
            raise APIError(409, "ALREADY_CLAIMED", "Someone else already picked this request")
        raise APIError(404, "NOT_FOUND", "Request not found")
    return {"request": await _serialize_one(database, req, user)}


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
