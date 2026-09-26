from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_database, parse_object_id, require_onboarded
from app.errors import APIError
from app.models import MessageCreate, RequestStatus
from app.services.serialize import relation, serialize_message

router = APIRouter(prefix="/api/requests")

_CHAT_STATUSES = (RequestStatus.CLAIMED, RequestStatus.RESOLVED)


async def _load_chat(database: AsyncDatabase, request_id: str, user: dict) -> dict:
    """The chat is private to the requester and the assigned volunteer, once the request is claimed."""
    req = await database.requests.find_one({"_id": parse_object_id(request_id)})
    if req is None:
        raise APIError(404, "NOT_FOUND", "Request not found")
    if relation(req, user) == "other":
        raise APIError(403, "FORBIDDEN", "This chat is private")
    if req["status"] not in _CHAT_STATUSES or not req.get("helper_id"):
        raise APIError(403, "CHAT_NOT_AVAILABLE", "Chat opens once a volunteer picks this request")
    return req


@router.get("/{request_id}/messages")
async def list_messages(
    request_id: str,
    after: datetime | None = Query(None, description="Only messages after this ISO timestamp"),
    user: dict = Depends(require_onboarded),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    req = await _load_chat(database, request_id, user)
    # Scope to the current pair: if a volunteer released the request, the next one can't read that chat.
    query: dict = {"request_id": req["_id"], "helper_id": req["helper_id"]}
    if after is not None:
        query["ts"] = {"$gt": after if after.tzinfo else after.replace(tzinfo=UTC)}
    msgs = await database.messages.find(query).sort("ts", 1).limit(200).to_list()
    return {"messages": [serialize_message(m, user) for m in msgs]}


@router.post("/{request_id}/messages")
async def send_message(
    request_id: str, body: MessageCreate, user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)
) -> dict:
    req = await _load_chat(database, request_id, user)
    if req["status"] != RequestStatus.CLAIMED:
        raise APIError(409, "CHAT_CLOSED", "This request is resolved; the chat is read-only")
    msg = {
        "request_id": req["_id"],
        "helper_id": req["helper_id"],
        "from_user_id": user["_id"],
        "text": body.text,
        "ts": datetime.now(UTC),
    }
    msg["_id"] = (await database.messages.insert_one(msg)).inserted_id
    return {"message": serialize_message(msg, user)}
