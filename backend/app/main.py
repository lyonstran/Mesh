import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.config import get_settings
from app.errors import install_error_handlers
from app.routers import health

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # On failure keep serving so /api/health reports db: "error" (and retries) instead of dying.
    await db.init(get_settings())
    # TODO(M4): start the change-stream broadcaster task here (PLAN.md §10).
    try:
        yield
    finally:
        await db.close()


app = FastAPI(title="Mesh API", lifespan=lifespan)
install_error_handlers(app)
app.include_router(health.router)
