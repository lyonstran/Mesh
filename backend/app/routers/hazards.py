from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_current_user, get_database, require_role
from app.models import HazardReport, Role
from app.services.hazard_region import get_region
from app.services.hazards import get_hazards

router = APIRouter()


@router.get("/api/hazards", response_model=HazardReport)
async def hazards_at_point(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    _: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
) -> dict:
    return await get_hazards(db, lat, lon)


@router.get("/api/hazards/region")
async def hazards_region(_: dict = Depends(require_role(Role.helper)), db: AsyncDatabase = Depends(get_database)) -> dict:
    """Georgia's active NWS alerts as GeoJSON for the volunteer map. TODO(P2): allow Role.coordinator too."""
    return await get_region(db)
