import asyncio
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings
from app.deps import get_current_user, get_database
from app.errors import APIError
from app.models import DemoLogin, GoogleCredential
from app.security import clear_session_cookie, set_session_cookie
from app.services.serialize import public_user

router = APIRouter()

_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _login_response(user: dict) -> dict:
    return {"user": public_user(user), "needs_onboarding": user.get("role") is None}


@router.post("/api/auth/google")
async def google_login(body: GoogleCredential, response: Response, database: AsyncDatabase = Depends(get_database)) -> dict:
    settings = get_settings()
    if not settings.google_client_id:
        # TODO(HUMAN): set GOOGLE_CLIENT_ID (and VITE_GOOGLE_CLIENT_ID) from the OAuth Web client.
        raise APIError(503, "GOOGLE_NOT_CONFIGURED", "Google sign-in is not configured")
    try:
        info = await asyncio.to_thread(
            id_token.verify_oauth2_token, body.credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError as e:
        raise APIError(401, "INVALID_TOKEN", "Google sign-in failed") from e
    if info.get("iss") not in _GOOGLE_ISSUERS:
        raise APIError(401, "INVALID_TOKEN", "Google sign-in failed")

    now = datetime.now(UTC)
    user = await database.users.find_one_and_update(
        {"google_sub": info["sub"]},
        {
            "$set": {"email": info.get("email"), "picture": info.get("picture"), "updated_at": now},
            "$setOnInsert": {"name": info.get("name"), "role": None, "verified": False, "created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    set_session_cookie(response, str(user["_id"]), settings)
    return _login_response(user)


@router.post("/api/auth/logout")
async def logout(response: Response) -> dict:
    clear_session_cookie(response, get_settings())
    return {"ok": True}


@router.get("/api/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": public_user(user), "needs_onboarding": user.get("role") is None}


def _require_demo() -> None:
    if not get_settings().demo_login:
        raise APIError(404, "NOT_FOUND", "Not Found")


@router.get("/api/auth/demo-users", dependencies=[Depends(_require_demo)])
async def demo_users(database: AsyncDatabase = Depends(get_database)) -> dict:
    users = await database.users.find({"demo": True}).sort([("role", 1), ("name", 1)]).to_list()
    return {"users": [{"id": str(u["_id"]), "name": u.get("name"), "role": u.get("role")} for u in users]}


@router.post("/api/auth/demo", dependencies=[Depends(_require_demo)])
async def demo_login(body: DemoLogin, response: Response, database: AsyncDatabase = Depends(get_database)) -> dict:
    user = None
    if ObjectId.is_valid(body.user_id):
        user = await database.users.find_one({"_id": ObjectId(body.user_id), "demo": True})
    if user is None:
        raise APIError(404, "NOT_FOUND", "Demo user not found")
    set_session_cookie(response, str(user["_id"]), get_settings())
    return _login_response(user)
