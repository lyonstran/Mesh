from fastapi import APIRouter, Depends, Query

from app.deps import get_current_user
from app.errors import APIError
from app.services.geocode import GeocoderUnavailable, geocode

router = APIRouter()


@router.get("/api/geocode")
async def search_address(q: str = Query(min_length=3, max_length=200), _: dict = Depends(get_current_user)) -> dict:
    try:
        return {"matches": await geocode(q)}
    except GeocoderUnavailable:
        raise APIError(
            502, "GEOCODER_UNAVAILABLE", "Address search isn't available right now. Use your location or drop a pin instead."
        ) from None
