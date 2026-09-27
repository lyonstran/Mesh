from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings
from app.deps import get_current_user, get_database
from app.errors import APIError
from app.services import sim

router = APIRouter(prefix="/api/sim")


def require_demo_mode() -> None:
    """Simulation is a demo tool: like demo login, every route is a 404 unless DEMO_LOGIN is on (CLAUDE.md rule 9)."""
    if not get_settings().demo_login:
        raise APIError(404, "NOT_FOUND", "Not found")


class ActivateIn(BaseModel):
    scenario_id: str


@router.get("", dependencies=[Depends(require_demo_mode)])
async def get_sim(_: dict = Depends(get_current_user), db: AsyncDatabase = Depends(get_database)) -> dict:
    return await sim.state(db)


# TODO(P2): restrict activate/deactivate to Role.coordinator once that role exists (PLAN.md §7). For now any
# signed-in user may flip it, and only in demo mode.
@router.post("/activate", dependencies=[Depends(require_demo_mode)])
async def activate(body: ActivateIn, _: dict = Depends(get_current_user), db: AsyncDatabase = Depends(get_database)) -> dict:
    try:
        rescored = await sim.activate(db, body.scenario_id)
    except sim.UnknownScenario:
        raise APIError(404, "UNKNOWN_SCENARIO", "No such scenario") from None
    return await sim.state(db) | {"rescored": rescored}


@router.post("/deactivate", dependencies=[Depends(require_demo_mode)])
async def deactivate(_: dict = Depends(get_current_user), db: AsyncDatabase = Depends(get_database)) -> dict:
    rescored = await sim.deactivate(db)
    return await sim.state(db) | {"rescored": rescored}
