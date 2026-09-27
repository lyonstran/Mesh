"""Point -> census tract lookup against the `tracts` collection loaded by data/load_tracts.py (PLAN.md §4)."""

from pymongo.asynchronous.database import AsyncDatabase

from app.services.geo import to_geojson

TRACT_FIELDS = {"geoid": 1, "name": 1, "eji_rank": 1, "climate_rank": 1, "env_rank": 1, "svm_rank": 1, "hvm_rank": 1}


async def tract_for_point(db: AsyncDatabase, lat: float, lon: float) -> dict | None:
    """The tract containing (lat, lon), without geometry. None outside Georgia or before tracts are loaded.

    Ranks may be None (EJI "no data", or a tract EJI doesn't cover); callers treat that as missing, not 0.
    """
    return await db.tracts.find_one(
        {"geometry": {"$geoIntersects": {"$geometry": to_geojson(lat, lon)}}},
        TRACT_FIELDS,
    )
