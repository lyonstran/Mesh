from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_current_user, get_database, require_onboarded
from app.errors import APIError
from app.models import ACTIVE_STATUSES, OnboardingIn, ProfileUpdate, Role
from app.services.profile import helper_embedding_fields
from app.services.serialize import public_user

router = APIRouter()


async def _save_profile(database: AsyncDatabase, user: dict, fields: dict) -> dict:
    merged = user | fields
    if merged.get("role") == Role.helper:
        fields |= await helper_embedding_fields(merged)
    fields["updated_at"] = datetime.now(UTC)
    return await database.users.find_one_and_update(
        {"_id": user["_id"]}, {"$set": fields}, return_document=ReturnDocument.AFTER
    )


@router.post("/api/onboarding")
async def onboarding(
    body: OnboardingIn, user: dict = Depends(get_current_user), database: AsyncDatabase = Depends(get_database)
) -> dict:
    if user.get("role") is not None:
        raise APIError(409, "ALREADY_ONBOARDED", "Already onboarded; edit your profile instead")
    fields = body.model_dump(mode="json")
    if body.role == Role.helper:
        fields["helper"] = fields["helper"] or {"skills": [], "resources": [], "about": ""}
        fields["requester_flags"] = None
    else:
        fields["helper"] = None
        fields["requester_flags"] = fields["requester_flags"] or {"medical_device": False, "mobility": False, "lives_alone": False}
    user = await _save_profile(database, user, fields)
    return {"user": public_user(user), "needs_onboarding": False}


@router.patch("/api/me")
async def update_me(
    body: ProfileUpdate, user: dict = Depends(require_onboarded), database: AsyncDatabase = Depends(get_database)
) -> dict:
    fields = body.model_dump(mode="json", exclude_unset=True)
    if fields.get("role") and fields["role"] != user["role"]:
        active = await database.requests.find_one({
            "$or": [{"requester_id": user["_id"]}, {"helper_id": user["_id"]}],
            "status": {"$in": list(ACTIVE_STATUSES)},
        })
        if active:
            raise APIError(409, "ACTIVE_REQUEST", "Finish or cancel your active request before switching roles")
        if fields["role"] == Role.helper and not (fields.get("helper") or user.get("helper")):
            fields["helper"] = {"skills": [], "resources": [], "about": ""}
    user = await _save_profile(database, user, fields)
    return {"user": public_user(user), "needs_onboarding": False}
