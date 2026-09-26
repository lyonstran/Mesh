from fastapi import APIRouter

from app import db
from app.config import get_settings

router = APIRouter()


@router.get("/api/health")
async def health() -> dict:
    settings = get_settings()
    # Retry init if startup failed (e.g. Atlas IP allowlist fixed after boot).
    db_ok = db.is_ready() or await db.init(settings)
    sim_active = False
    if db_ok:
        try:
            sim = await db.get_db().settings.find_one({"_id": "sim"})
            sim_active = bool(sim and sim.get("active"))
        except Exception:
            db_ok = False
    return {
        "ok": True,
        "db": "ok" if db_ok else "error",
        "llm_provider": settings.llm_provider,
        "sim_active": sim_active,
    }
