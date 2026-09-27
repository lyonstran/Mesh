from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_current_user, get_database
from app.models import HazardReport
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
