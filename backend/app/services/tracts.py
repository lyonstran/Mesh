"""Point -> census tract lookup against the `tracts` collection loaded by data/load_tracts.py (PLAN.md §4)."""

from pymongo.asynchronous.database import AsyncDatabase

from app.services.geo import to_geojson
from app.services.geometry import simplify
from app.services.matching import eji_band

TRACT_FIELDS = {"geoid": 1, "name": 1, "eji_rank": 1, "climate_rank": 1, "env_rank": 1, "svm_rank": 1, "hvm_rank": 1}


async def tract_for_point(db: AsyncDatabase, lat: float, lon: float) -> dict | None:
    """The tract containing (lat, lon), without geometry. None outside Georgia or before tracts are loaded.

    Ranks may be None (EJI "no data", or a tract EJI doesn't cover); callers treat that as missing, not 0.
    """
    return await db.tracts.find_one(
        {"geometry": {"$geoIntersects": {"$geometry": to_geojson(lat, lon)}}},
        TRACT_FIELDS,
    )


# --- tract shading for the volunteer map (GET /api/tracts) -----------------------------------------------------------

BAND_ORDER = ["Unknown", "Lower", "Moderate", "High", "Very high"]  # index 0-4; the map colors by index
MAX_TRACTS = 3000  # all of Georgia is 2,796
_display_cache: dict[tuple[str, float], dict | None] = {}


def tolerance_for_zoom(zoom: int) -> float:
    """Coarser shapes when zoomed out; a tract is only a few pixels wide at zoom 8."""
    if zoom <= 8:
        return 0.003
    if zoom <= 10:
        return 0.0015
    if zoom <= 12:
        return 0.0006
    return 0.0002


def bbox_polygon(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat], [min_lon, min_lat]]],
    }


async def tracts_in_bbox(db: AsyncDatabase, bbox: tuple[float, float, float, float], zoom: int) -> list[dict]:
    """Tracts touching the box as GeoJSON features carrying only an EJI band. No GEOID and no raw rank leave here.

    Full-resolution shapes are large (about 10 MB statewide), so they're read from Mongo only for tracts whose
    simplified shape at this zoom isn't cached yet.
    """
    tolerance = tolerance_for_zoom(zoom)
    hits = await db.tracts.find(
        {"geometry": {"$geoIntersects": {"$geometry": bbox_polygon(*bbox)}}}, {"eji_rank": 1}
    ).limit(MAX_TRACTS).to_list()
    missing = [h["_id"] for h in hits if (h["_id"], tolerance) not in _display_cache]
    if missing:
        async for doc in db.tracts.find({"_id": {"$in": missing}}, {"geometry": 1}):
            _display_cache[(doc["_id"], tolerance)] = simplify(doc["geometry"], tolerance, min_area=1e-7)
    features = []
    for hit in hits:
        geometry = _display_cache.get((hit["_id"], tolerance))
        if geometry is None:
            continue
        band = eji_band(hit.get("eji_rank"))
        features.append({"type": "Feature", "geometry": geometry, "properties": {"band": band, "band_index": BAND_ORDER.index(band)}})
    return features
