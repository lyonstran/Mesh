from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_current_user, get_database, require_onboarded
from app.errors import APIError
from app.models import ACTIVE_STATUSES, OnboardingIn, ProfileUpdate, Role
from app.services.indexing import refresh_helper_embedding
from app.services.profile import helper_profile_text
from app.services.serialize import public_user

router = APIRouter()

def _empty_helper() -> dict:
    return {"skills": [], "custom_skills": [], "resources": [], "about": ""}


async def _save_profile(database: AsyncDatabase, user: dict, fields: dict, background: BackgroundTasks) -> tuple[dict, bool]:
    """Save immediately; re-embed a volunteer's profile after the response only if its matching text changed.

    Returns (updated user, whether matches are being refreshed).
    """
    merged = user | fields
    rematching = False
    if merged.get("role") == Role.helper:
        text = helper_profile_text(merged)
        if text != user.get("profile_text") or (text and not user.get("embedding")):
            fields["profile_text"] = text
            background.add_task(refresh_helper_embedding, database, user["_id"], text)
            rematching = True
    fields["updated_at"] = datetime.now(UTC)
    updated = await database.users.find_one_and_update(
        {"_id": user["_id"]}, {"$set": fields}, return_document=ReturnDocument.AFTER
    )
    return updated, rematching


@router.post("/api/onboarding")
async def onboarding(
    body: OnboardingIn,
    background: BackgroundTasks,
    user: dict = Depends(get_current_user),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    if user.get("role") is not None:
        raise APIError(409, "ALREADY_ONBOARDED", "Already onboarded; edit your profile instead")
    fields = body.model_dump(mode="json")
    if body.role == Role.helper:
        fields["helper"] = fields["helper"] or _empty_helper()
        fields["requester_flags"] = None
    else:
        fields["helper"] = None
        fields["requester_flags"] = fields["requester_flags"] or {"medical_device": False, "mobility": False, "lives_alone": False}
    user, _ = await _save_profile(database, user, fields, background)
    return {"user": public_user(user), "needs_onboarding": False}


@router.patch("/api/me")
async def update_me(
    body: ProfileUpdate,
    background: BackgroundTasks,
    user: dict = Depends(require_onboarded),
    database: AsyncDatabase = Depends(get_database),
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
            fields["helper"] = _empty_helper()
    user, rematching = await _save_profile(database, user, fields, background)
    return {"user": public_user(user), "needs_onboarding": False, "rematching": rematching}
