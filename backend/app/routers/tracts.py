from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import get_database, require_role
from app.errors import APIError
from app.models import Role
from app.services.tracts import tracts_in_bbox

router = APIRouter()

MIN_ZOOM = 8  # below this, tracts are too small to read; the client hides the layer
MAX_SPAN_DEG = 4.0


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    try:
        min_lon, min_lat, max_lon, max_lat = (float(v) for v in raw.split(","))
    except ValueError:
        raise APIError(422, "VALIDATION_ERROR", "bbox must be minLon,minLat,maxLon,maxLat") from None
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise APIError(422, "VALIDATION_ERROR", "bbox must be minLon,minLat,maxLon,maxLat with min < max")
    if max_lon - min_lon > MAX_SPAN_DEG or max_lat - min_lat > MAX_SPAN_DEG:
        raise APIError(422, "VALIDATION_ERROR", f"bbox can span at most {MAX_SPAN_DEG} degrees")
    return min_lon, min_lat, max_lon, max_lat


@router.get("/api/tracts")
async def tracts(
    bbox: str = Query(max_length=100),
    zoom: int = Query(ge=0, le=22),
    _: dict = Depends(require_role(Role.helper)),  # TODO(P2): allow Role.coordinator for the dashboard choropleth
    db: AsyncDatabase = Depends(get_database),
) -> dict:
    """EJI vulnerability bands by tract for map shading (PLAN.md §11 shape). Bands only: no GEOID, no raw rank."""
    box = _parse_bbox(bbox)
    if zoom < MIN_ZOOM:
        return {"type": "FeatureCollection", "features": [], "too_zoomed_out": True}
    return {"type": "FeatureCollection", "features": await tracts_in_bbox(db, box, zoom), "too_zoomed_out": False}
