import logging
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from app.config import Settings

log = logging.getLogger("mesh.security")

COOKIE_NAME = "session"
_ALGORITHM = "HS256"
_dev_secret: str | None = None


def _secret(settings: Settings) -> str:
    global _dev_secret
    if settings.jwt_secret:
        return settings.jwt_secret
    # Dev convenience: a per-process secret, so sessions end when the server restarts.
    if _dev_secret is None:
        log.warning("JWT_SECRET is not set; using a random per-process secret")
        _dev_secret = secrets.token_urlsafe(32)
    return _dev_secret


def create_token(user_id: str, settings: Settings) -> str:
    exp = datetime.now(UTC) + timedelta(hours=settings.jwt_ttl_hours)
    return jwt.encode({"sub": user_id, "exp": exp}, _secret(settings), algorithm=_ALGORITHM)


def decode_token(token: str, settings: Settings) -> str | None:
    """Return the user id in a valid token, or None."""
    try:
        payload = jwt.decode(token, _secret(settings), algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def set_session_cookie(response: Response, user_id: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_token(user_id, settings),
        max_age=settings.jwt_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=settings.cookie_secure)
