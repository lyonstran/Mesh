"""Statewide NWS alerts with geometry (GET /api/hazards/region). Uses recorded real responses (2026-09-27):

- nws_ga.json: /alerts/active?area=GA (zone-based alerts, no polygons)
- nws_zone_GAZ044.json: /zones/forecast/GAZ044 (South Fulton), served for every zone URL in these tests
"""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from shapely.geometry import shape

from app.models import Role
from app.services import hazard_region as hr

FIXTURES = Path(__file__).parent / "fixtures" / "hazards"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _vertices(geometry: dict) -> int:
    def count(c):
        return 1 if isinstance(c[0], (int, float)) else sum(count(x) for x in c)

    return count(geometry["coordinates"])


def _transport(calls: list | None = None, fail_zones: bool = False, fail_feed: bool = False, feed: dict | None = None):
    feed = feed or load("nws_ga.json")
    zone = load("nws_zone_GAZ044.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if request.url.path == "/alerts/active":
            return httpx.Response(500) if fail_feed else httpx.Response(200, json=feed)
        if request.url.path.startswith("/zones/"):
            return httpx.Response(500) if fail_zones else httpx.Response(200, json=zone)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


# --- pure geometry ------------------------------------------------------------------

def test_simplify_keeps_a_valid_polygon_with_fewer_or_equal_vertices():
    raw = load("nws_zone_GAZ044.json")["geometry"]
    out = hr.simplify(raw)
    assert out["type"] in ("Polygon", "MultiPolygon") and shape(out).is_valid
    assert _vertices(out) <= _vertices(raw)
    assert shape(out).area == pytest.approx(shape(raw).area, rel=0.02)


def test_simplify_drops_slivers_and_handles_missing_geometry():
    sliver = {"type": "Polygon", "coordinates": [[[0, 0], [0.0001, 0], [0.0001, 0.0001], [0, 0], [0, 0]]]}
    assert hr.simplify(sliver) is None
    assert hr.simplify(None) is None


def test_alert_properties_map_type_and_level_and_skip_tests():
    feature = load("nws_ga.json")["features"][0]
    props = hr.alert_properties(feature)
    assert props["event"] == feature["properties"]["event"] and props["official"] is True
    assert 1 <= props["level"] <= 3 and props["type"]
    test_msg = copy.deepcopy(feature)
    test_msg["properties"]["status"] = "Test"
    assert hr.alert_properties(test_msg) is None


# --- fetching (needs MONGODB_TEST_URI) ---------------------------------------------

async def test_zone_alerts_get_merged_zone_geometry_and_zones_are_cached(async_db):
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        region = await hr.get_region(async_db, client)
    feed = load("nws_ga.json")
    assert len(region["features"]) == len(feed["features"]) and region["sources_failed"] == []
    assert all(f["geometry"] and shape(f["geometry"]).is_valid for f in region["features"])
    zone_urls = {z for f in feed["features"] for z in f["properties"]["affectedZones"]}
    assert await async_db.nws_zones.count_documents({}) == len(zone_urls)

    # A new feed (cache expired) reuses the stored zone shapes instead of refetching them.
    await async_db.hazard_cache.delete_many({})
    calls.clear()
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        await hr.get_region(async_db, client)
    assert [c for c in calls if "/zones/" in c] == []


async def test_region_feed_is_cached(async_db):
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        first = await hr.get_region(async_db, client)
        calls.clear()
        second = await hr.get_region(async_db, client)
    assert calls == [] and second == first


async def test_failed_zone_leaves_the_alert_listed_without_a_shape(async_db):
    async with httpx.AsyncClient(transport=_transport(fail_zones=True)) as client:
        region = await hr.get_region(async_db, client)
    assert region["features"] and all(f["geometry"] is None for f in region["features"])
    assert region["sources_failed"] == []


async def test_stale_zone_shape_is_used_when_nws_fails(async_db):
    alert = load("nws_ga.json")["features"][0]["properties"]
    url = alert["affectedZones"][0]
    old = datetime.now(UTC) - hr.ZONE_TTL - timedelta(days=1)
    geometry = hr.simplify(load("nws_zone_GAZ044.json")["geometry"])
    await async_db.nws_zones.insert_one({"_id": url, "geometry": geometry, "name": "x", "fetched_at": old})
    async with httpx.AsyncClient(transport=_transport(fail_zones=True)) as client:
        region = await hr.get_region(async_db, client)
    [seeded] = [f for f in region["features"] if f["properties"]["event"] == alert["event"]]
    assert seeded["geometry"] is not None


async def test_feed_failure_returns_empty_and_is_not_cached(async_db):
    async with httpx.AsyncClient(transport=_transport(fail_feed=True)) as client:
        region = await hr.get_region(async_db, client)
    assert region["features"] == [] and region["sources_failed"] == ["NWS"] and region["simulated"] is False
    assert await async_db.hazard_cache.count_documents({}) == 0


async def test_only_nws_zone_urls_are_fetched(async_db):
    feed = load("nws_ga.json")
    feed["features"][0]["properties"]["affectedZones"] = ["https://evil.example.com/zones/x", "http://api.weather.gov/zones/y"]
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls, feed=feed)) as client:
        await hr.get_region(async_db, client)
    assert not any("evil" in c or c.startswith("http://") for c in calls)


async def test_alert_with_its_own_polygon_uses_it(async_db):
    feed = load("nws_ga.json")
    feed["features"][0]["geometry"] = load("nws_zone_GAZ044.json")["geometry"]
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls, feed=feed)) as client:
        region = await hr.get_region(async_db, client)
    [own] = [f for f in region["features"] if f["properties"]["event"] == feed["features"][0]["properties"]["event"]]
    assert own["geometry"] is not None


# --- endpoint (needs MONGODB_TEST_URI) ----------------------------------------------

def test_region_endpoint_is_for_volunteers(env, monkeypatch):
    async def fake_region(db, client=None):
        return {"type": "FeatureCollection", "features": [], "area": "GA", "simulated": False, "sources_failed": [], "fetched_at": "x"}

    monkeypatch.setattr("app.routers.hazards.get_region", fake_region)
    assert env.client.get("/api/hazards/region").status_code == 401
    _, requester = env.make_user(Role.requester, "R")
    assert env.client.get("/api/hazards/region", headers=requester).status_code == 403
    helper = env.onboard_helper("Marcus", "chainsaw")
    resp = env.client.get("/api/hazards/region", headers=helper)
    assert resp.status_code == 200 and resp.json()["type"] == "FeatureCollection"


def test_merge_repairs_invalid_and_overlapping_zone_shapes():
    # A self-intersecting "bowtie" plus an overlapping square: the kind of input that made unary_union throw
    # on real coastal zones before geometries were repaired.
    bowtie = {"type": "Polygon", "coordinates": [[[-81.6, 30.8], [-81.5, 30.9], [-81.5, 30.8], [-81.6, 30.9], [-81.6, 30.8]]]}
    square = {"type": "Polygon", "coordinates": [[[-81.55, 30.8], [-81.45, 30.8], [-81.45, 30.9], [-81.55, 30.9], [-81.55, 30.8]]]}
    merged = hr._merge([bowtie, square])
    assert merged is not None and shape(merged).is_valid
