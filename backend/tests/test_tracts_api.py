"""GET /api/tracts: EJI band shading for the volunteer map. Needs MONGODB_TEST_URI; skipped otherwise."""

import json

import pytest
from pymongo import GEOSPHERE
from shapely.geometry import shape

from app.models import Role
from app.services import tracts as tracts_service


def _square(lon: float, lat: float, size: float = 0.01) -> dict:
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]]}


# Test squares near the venue, not real boundaries.
TRACTS = [
    {"_id": "13121000001", "geoid": "13121000001", "eji_rank": 0.9137, "geometry": _square(-84.40, 33.77)},
    {"_id": "13121000002", "geoid": "13121000002", "eji_rank": 0.1234, "geometry": _square(-84.39, 33.77)},
    {"_id": "13121000003", "geoid": "13121000003", "eji_rank": None, "geometry": _square(-84.38, 33.77)},
    {"_id": "13051000004", "geoid": "13051000004", "eji_rank": 0.5, "geometry": _square(-81.10, 32.08)},  # Savannah
]
ATL_BBOX = "-84.45,33.74,-84.35,33.80"


@pytest.fixture
def tracts(env):
    tracts_service._display_cache.clear()
    env.raw.tracts.create_index([("geometry", GEOSPHERE)])
    env.raw.tracts.insert_many(TRACTS)


def _get(env, headers, bbox=ATL_BBOX, zoom=12):
    return env.client.get("/api/tracts", params={"bbox": bbox, "zoom": zoom}, headers=headers)


def test_returns_bands_in_the_box_only(env, tracts):
    body = _get(env, env.onboard_helper("Vol", "chainsaw")).json()
    bands = sorted(f["properties"]["band"] for f in body["features"])
    assert bands == ["Lower", "Unknown", "Very high"]  # Savannah is outside the box
    by_band = {f["properties"]["band"]: f["properties"]["band_index"] for f in body["features"]}
    assert by_band == {"Very high": 4, "Lower": 1, "Unknown": 0}
    assert all(shape(f["geometry"]).is_valid for f in body["features"])
    assert body["too_zoomed_out"] is False


def test_payload_has_no_geoid_or_raw_rank(env, tracts):
    blob = json.dumps(_get(env, env.onboard_helper("Vol", "chainsaw")).json())
    for hidden in ("13121000001", "geoid", "0.9137", "0.1234", "eji_rank"):
        assert hidden not in blob, hidden


def test_is_for_volunteers_only(env, tracts):
    assert env.client.get("/api/tracts", params={"bbox": ATL_BBOX, "zoom": 12}).status_code == 401
    _, requester = env.make_user(Role.requester, "R")
    assert _get(env, requester).status_code == 403


@pytest.mark.parametrize("bbox", ["nonsense", "-84.3,33.7,-84.4,33.8", "-90,30,-80,35", "1,2,3"])
def test_bad_bbox_is_422(env, tracts, bbox):
    resp = _get(env, env.onboard_helper("Vol", "chainsaw"), bbox=bbox)
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_zoomed_out_returns_nothing(env, tracts):
    body = _get(env, env.onboard_helper("Vol", "chainsaw"), zoom=7).json()
    assert body["features"] == [] and body["too_zoomed_out"] is True


def test_coarser_zoom_uses_coarser_shapes():
    assert tracts_service.tolerance_for_zoom(8) > tracts_service.tolerance_for_zoom(11) > tracts_service.tolerance_for_zoom(14)
