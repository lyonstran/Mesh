from fastapi import APIRouter

from app import db
from app.ai.provider import get_provider
from app.config import get_settings
from app.services import ranking, sim

router = APIRouter()


@router.get("/api/health")
async def health() -> dict:
    # Retry init if startup failed (e.g. Atlas IP allowlist fixed after boot).
    db_ok = db.is_ready() or await db.init(get_settings())
    sim_active = False
    if db_ok:
        try:
            database = db.get_db()
            sim_active = (await sim.state(database))["active"]  # only ever true in demo mode
            await ranking.ensure_initialized(database)
        except Exception:
            db_ok = False
    return {
        "ok": True,
        "db": "ok" if db_ok else "error",
        "llm_provider": get_provider().name,
        "vector_search": ranking.mode(),
        "sim_active": sim_active,
    }
