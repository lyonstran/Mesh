"""tract_for_point against a real MongoDB with a fixture polygon (needs MONGODB_TEST_URI; skipped otherwise)."""

import pytest
from pymongo import GEOSPHERE

from app.services.tracts import tract_for_point

VENUE = {"lat": 33.7756, "lon": -84.3963}

# A small square around the venue, in GeoJSON [lon, lat] order. Not a real tract boundary.
FIXTURE_TRACT = {
    "_id": "13121000000",
    "geoid": "13121000000",
    "name": "Fixture Tract",
    "eji_rank": 0.72,
    "climate_rank": 0.65,
    "env_rank": 0.5,
    "svm_rank": 0.8,
    "hvm_rank": 0.2,
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-84.40, 33.77], [-84.39, 33.77], [-84.39, 33.78], [-84.40, 33.78], [-84.40, 33.77]]],
    },
}
NO_DATA_TRACT = FIXTURE_TRACT | {
    "_id": "13121000001",
    "geoid": "13121000001",
    "eji_rank": None,
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-84.39, 33.77], [-84.38, 33.77], [-84.38, 33.78], [-84.39, 33.78], [-84.39, 33.77]]],
    },
}


@pytest.fixture
async def db(async_db):
    await async_db.tracts.create_index([("geometry", GEOSPHERE)])
    await async_db.tracts.insert_many([FIXTURE_TRACT, NO_DATA_TRACT])
    return async_db


async def test_point_inside_returns_tract_without_geometry(db):
    tract = await tract_for_point(db, VENUE["lat"], VENUE["lon"])
    assert tract is not None
    assert tract["geoid"] == "13121000000" and tract["eji_rank"] == 0.72
    assert "geometry" not in tract


async def test_point_outside_returns_none(db):
    assert await tract_for_point(db, 40.7128, -74.0060) is None


async def test_swapped_coordinates_do_not_match(db):
    # (lon, lat) passed as (lat, lon) lands nowhere near Georgia.
    assert await tract_for_point(db, VENUE["lon"], VENUE["lat"]) is None


async def test_missing_eji_is_none_not_zero(db):
    tract = await tract_for_point(db, 33.775, -84.385)
    assert tract is not None and tract["geoid"] == "13121000001"
    assert tract["eji_rank"] is None
