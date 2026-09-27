from collections.abc import Awaitable, Callable

from bson import ObjectId
from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from app import db
from app.config import get_settings
from app.errors import APIError
from app.models import Role, held_roles
from app.security import COOKIE_NAME, decode_token


def get_database() -> AsyncDatabase:
    if not db.is_ready():
        raise APIError(503, "DB_UNAVAILABLE", "Database is not available")
    return db.get_db()


async def get_current_user(request: Request, database: AsyncDatabase = Depends(get_database)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    user_id = decode_token(token, get_settings()) if token else None
    if not user_id or not ObjectId.is_valid(user_id):
        raise APIError(401, "UNAUTHORIZED", "Not signed in")
    user = await database.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise APIError(401, "UNAUTHORIZED", "Not signed in")
    return user


async def require_onboarded(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") is None:
        raise APIError(409, "ONBOARDING_REQUIRED", "Finish onboarding first")
    return user


def require_role(*roles: Role) -> Callable[..., Awaitable[dict]]:
    async def dependency(user: dict = Depends(require_onboarded)) -> dict:
        if not set(held_roles(user)) & set(roles):
            raise APIError(403, "FORBIDDEN", "Not allowed for your role")
        return user

    return dependency


def parse_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise APIError(404, "NOT_FOUND", "Not found")
    return ObjectId(value)
