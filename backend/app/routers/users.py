from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_current_user, get_database, require_onboarded
from app.errors import APIError
from app.models import AddRoleIn, OnboardingIn, ProfileUpdate, Role, held_roles
from app.services.indexing import refresh_helper_embedding
from app.services.profile import helper_profile_text
from app.services.serialize import public_user

router = APIRouter()

_EMPTY_FLAGS = {"medical_device": False, "mobility": False, "lives_alone": False}


def _empty_helper() -> dict:
    return {"skills": [], "custom_skills": [], "resources": [], "about": ""}


async def _save_profile(database: AsyncDatabase, user: dict, fields: dict, background: BackgroundTasks) -> tuple[dict, bool]:
    """Save immediately; re-embed a volunteer's profile after the response only if its matching text changed.

    Returns (updated user, whether matches are being refreshed).
    """
    merged = user | fields
    rematching = False
    if Role.helper in held_roles(merged):
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
    fields["roles"] = [str(body.role)]
    if body.role == Role.helper:
        fields["helper"] = fields["helper"] or _empty_helper()
        fields["requester_flags"] = None
    else:
        fields["helper"] = None
        fields["requester_flags"] = fields["requester_flags"] or dict(_EMPTY_FLAGS)
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
    held = held_roles(user)
    # Switching the active mode deletes nothing, so it is allowed with an active request. Editing or
    # switching to a profile the user doesn't hold must go through POST /api/me/roles.
    if fields.get("role") and Role(fields["role"]) not in held:
        raise APIError(409, "ROLE_NOT_HELD", "Add that profile to your account first")
    if fields.get("helper") is not None and Role.helper not in held:
        raise APIError(409, "ROLE_NOT_HELD", "Add a volunteer profile to your account first")
    if fields.get("requester_flags") is not None and Role.requester not in held:
        raise APIError(409, "ROLE_NOT_HELD", "Add a requester profile to your account first")
    user, rematching = await _save_profile(database, user, fields, background)
    return {"user": public_user(user), "needs_onboarding": False, "rematching": rematching}


@router.post("/api/me/roles")
async def add_role(
    body: AddRoleIn,
    background: BackgroundTasks,
    user: dict = Depends(require_onboarded),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    held = held_roles(user)
    if body.role in held:
        raise APIError(409, "ROLE_EXISTS", "You already have that profile")
    fields: dict = {"roles": [str(r) for r in (*held, body.role)]}
    if body.role == Role.helper:
        fields["helper"] = body.helper.model_dump(mode="json") if body.helper else _empty_helper()
    else:
        fields["requester_flags"] = body.requester_flags.model_dump(mode="json") if body.requester_flags else dict(_EMPTY_FLAGS)
    user, rematching = await _save_profile(database, user, fields, background)
    return {"user": public_user(user), "needs_onboarding": False, "rematching": rematching}
