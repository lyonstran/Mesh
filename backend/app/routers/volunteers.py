from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings
from app.deps import get_database, require_role
from app.models import Role
from app.services.volunteers import nearby_volunteers

router = APIRouter(prefix="/api/volunteers")

MAX_RADIUS_KM = 25


@router.get("/nearby")
async def nearby(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_km: float = Query(15, ge=1, le=MAX_RADIUS_KM),
    user: dict = Depends(require_role(Role.requester)),
    database: AsyncDatabase = Depends(get_database),
) -> dict:
    """Approximate areas of volunteers around a point. No names, ids or exact locations (services/volunteers.py)."""
    volunteers = await nearby_volunteers(
        database, lat=lat, lon=lon, radius_km=radius_km, secret=get_settings().jwt_secret, exclude_id=user["_id"]
    )
    return {"volunteers": volunteers, "radius_km": radius_km}
