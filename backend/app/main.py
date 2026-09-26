import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.config import get_settings
from app.errors import install_error_handlers
from app.routers import auth, health, messages, requests, users
from app.services import ranking

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # On failure keep serving so /api/health reports db: "error" (and retries) instead of dying.
    if await db.init(get_settings()):
        await ranking.ensure_initialized(db.get_db())
    # TODO(M4): start the change-stream broadcaster task here (PLAN.md §10).
    try:
        yield
    finally:
        await db.close()
        ranking.reset()


app = FastAPI(title="Mesh API", lifespan=lifespan)
install_error_handlers(app)
for module in (health, auth, users, requests, messages):
    app.include_router(module.router)
