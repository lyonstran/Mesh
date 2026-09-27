"""Hazard engine (PLAN.md §7). Parsers run on recorded real responses in tests/fixtures/hazards/ (recorded 2026-09-27):

- nws_venue.json: /alerts/active?point= at the HackGT venue (no alerts at the time)
- nws_ga.json: /alerts/active?area=GA (Coastal Flood Advisory + Rip Current Statement, zone-based, no geometry)
- nws_national_sample.json: one real feature per event type from the national /alerts/active feed
- nws_alert_point.json: /alerts/active?point= inside a live Special Weather Statement polygon
- openmeteo_forecast_venue.json, openmeteo_aq_venue.json: the exact §7 Open-Meteo requests at the venue
"""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.config import get_settings
from app.services import hazards as hz

FIXTURES = Path(__file__).parent / "fixtures" / "hazards"
VENUE = (33.7756, -84.3963)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def by_event(report_hazards) -> dict:
    return {h.event: h for h in report_hazards}


# --- NWS mapping -----------------------------------------------------------------

@pytest.mark.parametrize(
    "event, kind",
    [
        ("Tornado Warning", "tornado"),
        ("Tornado Watch", "tornado"),
        ("Severe Thunderstorm Warning", "severe_storm"),
        ("Flash Flood Warning", "flood"),
        ("Flood Watch", "flood"),
        ("Coastal Flood Advisory", "flood"),
        ("Excessive Heat Warning", "heat"),
        ("Extreme Heat Warning", "heat"),
        ("Heat Advisory", "heat"),
        ("Air Quality Alert", "air_quality"),
        ("Dense Smoke Advisory", "air_quality"),
        ("Winter Storm Warning", "winter"),
        ("Ice Storm Warning", "winter"),
        ("Winter Weather Advisory", "winter"),
        ("Freeze Warning", "winter"),
        ("Extreme Cold Warning", "winter"),
        ("Hurricane Warning", "tropical"),
        ("Tropical Storm Watch", "tropical"),
        ("High Wind Warning", "wind"),
        ("Wind Advisory", "wind"),
        ("Small Craft Advisory", "other"),
        ("Special Weather Statement", "other"),
        ("Rip Current Statement", "other"),
    ],
)
def test_event_to_type_table(event, kind):
    assert hz.event_type(event) == kind
    assert hz.event_type(event.upper()) == kind  # case-insensitive


@pytest.mark.parametrize(
    "severity, level", [("Extreme", 3), ("Severe", 3), ("Moderate", 2), ("Minor", 1), ("Unknown", 1), (None, 1), ("odd", 1)]
)
def test_severity_to_level(severity, level):
    assert hz.severity_level(severity) == level


def test_real_national_alerts_map_by_type_and_severity():
    found = by_event(hz.parse_nws(load("nws_national_sample.json")))
    assert (found["Flood Watch"].type, found["Flood Watch"].level) == ("flood", 3)  # Severe
    assert (found["Wind Advisory"].type, found["Wind Advisory"].level) == ("wind", 2)  # Moderate
    assert (found["High Wind Warning"].type, found["High Wind Warning"].level) == ("wind", 1)  # Minor
    assert (found["Heat Advisory"].type, found["Heat Advisory"].level) == ("heat", 2)
    assert (found["Air Quality Alert"].type, found["Air Quality Alert"].level) == ("air_quality", 1)  # Unknown
    assert found["Small Craft Advisory"].type == "other"
    assert all(h.official and h.source == "NWS" for h in found.values())


def test_real_alert_keeps_headline_expiry_and_instruction_fields():
    [alert] = hz.parse_nws(load("nws_alert_point.json"))
    raw = load("nws_alert_point.json")["features"][0]["properties"]
    assert alert.event == raw["event"] and alert.headline == raw["headline"]
    assert alert.expires == raw["expires"] and alert.instruction == raw["instruction"]


def test_test_messages_are_ignored():
    payload = load("nws_ga.json")
    for f in payload["features"]:
        f["properties"]["status"] = "Test"
    assert hz.parse_nws(payload) == []


def test_georgia_feed_parses_zone_alerts_without_geometry():
    found = by_event(hz.parse_nws(load("nws_ga.json")))
    assert found["Coastal Flood Advisory"].type == "flood"
    assert found["Rip Current Statement"].type == "other"


# --- Open-Meteo derived signals ---------------------------------------------------

def test_calm_venue_reports_level_zero_with_current_readings():
    forecast, air = load("openmeteo_forecast_venue.json"), load("openmeteo_aq_venue.json")
    report = hz.build_report(load("nws_venue.json"), forecast, air)
    assert report.level == 0 and report.hazards == [] and report.likely_needs == []
    assert report.sources_failed == [] and report.simulated is False
    assert report.current["apparent_temperature_f"] == forecast["current"]["apparent_temperature"]
    assert report.current["wind_gust_mph"] == forecast["current"]["wind_gusts_10m"]
    assert report.current["us_aqi"] == air["current"]["us_aqi"]
    assert report.current["pm2_5"] == air["current"]["pm2_5"]


def _forecast_with(**hourly_overrides) -> dict:
    payload = copy.deepcopy(load("openmeteo_forecast_venue.json"))
    for key, (index, value) in hourly_overrides.items():
        payload["hourly"][key][index] = value
    return payload


@pytest.mark.parametrize("gust, expect", [(57.9, None), (58.0, 2), (95.0, 2)])
def test_gust_threshold_is_58_mph_and_capped_at_2(gust, expect):
    hazards, _ = hz.parse_forecast(_forecast_with(wind_gusts_10m=(5, gust)))
    wind = [h for h in hazards if h.type == "wind"]
    assert (wind[0].level if wind else None) == expect
    if wind:
        assert wind[0].official is False and wind[0].value == gust


@pytest.mark.parametrize("feels, expect", [(102.9, None), (103.0, 1), (115.0, 1)])
def test_heat_threshold_is_team_chosen_103f(feels, expect):
    hazards, _ = hz.parse_forecast(_forecast_with(apparent_temperature=(3, feels)))
    heat = [h for h in hazards if h.type == "heat"]
    assert (heat[0].level if heat else None) == expect


def test_rain_threshold_sums_the_next_12_hours():
    payload = copy.deepcopy(load("openmeteo_forecast_venue.json"))
    n = len(payload["hourly"]["precipitation"])
    payload["hourly"]["precipitation"] = [2.0 / n] * n
    hazards, current = hz.parse_forecast(payload)
    assert current["precip_next_12h_in"] == pytest.approx(2.0)
    assert [(h.type, h.level) for h in hazards] == [("flood", 1)]


@pytest.mark.parametrize(
    "aqi, expect",
    [(100, None), (101, (1, "Unhealthy for Sensitive Groups")), (151, (2, "Unhealthy")),
     (250, (2, "Very Unhealthy")), (350, (2, "Hazardous"))],
)
def test_aqi_bands_follow_epa_categories_and_cap_at_2(aqi, expect):
    payload = copy.deepcopy(load("openmeteo_aq_venue.json"))
    payload["current"]["us_aqi"] = aqi
    hazards, _ = hz.parse_air_quality(payload)
    assert ((hazards[0].level, hazards[0].category) if hazards else None) == expect


def test_official_alert_outranks_derived_and_sets_level():
    air = copy.deepcopy(load("openmeteo_aq_venue.json"))
    air["current"]["us_aqi"] = 158
    report = hz.build_report(load("nws_national_sample.json"), load("openmeteo_forecast_venue.json"), air)
    assert report.level == 3
    assert report.hazards[0].official and report.hazards[0].level == 3
    assert any(h.type == "air_quality" and not h.official for h in report.hazards)


def test_likely_needs_follow_hazard_table_highest_level_first():
    storm = hz.Hazard(type="severe_storm", level=3, source="NWS", official=True, event="Severe Thunderstorm Warning")
    heat = hz.Hazard(type="heat", level=1, source="Open-Meteo", official=False, value=104, unit="°F feels-like")
    assert hz.likely_needs([heat, storm]) == ["debris", "power", "shelter", "supplies", "water", "cooling", "welfare_check", "transport"]
    tropical = hz.Hazard(type="tropical", level=3, source="NWS", official=True, event="Hurricane Warning")
    assert hz.likely_needs([tropical]) == ["debris", "power", "shelter", "supplies", "transport"]


def test_thresholds_file_matches_plan():
    t = hz.thresholds()
    assert t["derived_level_cap"] == 2
    assert t["wind_gust_mph"]["min"] == 58 and t["apparent_temp_f"]["min"] == 103 and t["precip_12h_in"]["min"] == 2.0
    assert [b["min"] for b in t["aqi"]] == [101, 151, 201, 301]


# --- fetching and graceful degradation --------------------------------------------

def _transport(fail: set[str] | None = None, calls: list | None = None, flaky: set[str] | None = None):
    """Serve recorded fixtures by host. `fail` hosts always 500; `flaky` hosts 500 once, then succeed."""
    fail, flaky = fail or set(), set(flaky or ())
    served = {
        "api.weather.gov": load("nws_venue.json"),
        "api.open-meteo.com": load("openmeteo_forecast_venue.json"),
        "air-quality-api.open-meteo.com": load("openmeteo_aq_venue.json"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if calls is not None:
            calls.append(request)
        if host in fail:
            return httpx.Response(500)
        if host in flaky:
            flaky.discard(host)
            return httpx.Response(503)
        return httpx.Response(200, json=served[host])

    return httpx.MockTransport(handler)


async def test_all_sources_ok_and_nws_gets_user_agent_and_4dp_point():
    calls: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=_transport(calls=calls)) as client:
        report = await hz.fetch_report(33.775612, -84.396345, client)
    assert report.sources_failed == []
    nws = next(r for r in calls if r.url.host == "api.weather.gov")
    assert nws.headers["User-Agent"] == get_settings().nws_user_agent
    assert nws.headers["Accept"] == "application/geo+json"
    assert nws.url.params["point"] == "33.7756,-84.3963"


async def test_one_failed_source_returns_partial_result_not_an_error():
    async with httpx.AsyncClient(transport=_transport(fail={"api.weather.gov"})) as client:
        report = await hz.fetch_report(*VENUE, client)
    assert report.sources_failed == ["NWS"]
    assert report.current["us_aqi"] is not None  # the other sources still arrived


async def test_everything_down_still_returns_a_report():
    hosts = {"api.weather.gov", "api.open-meteo.com", "air-quality-api.open-meteo.com"}
    async with httpx.AsyncClient(transport=_transport(fail=hosts)) as client:
        report = await hz.fetch_report(*VENUE, client)
    assert report.level == 0 and len(report.sources_failed) == 3


async def test_a_single_blip_is_retried_once():
    calls: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=_transport(calls=calls, flaky={"api.open-meteo.com"})) as client:
        report = await hz.fetch_report(*VENUE, client)
    assert report.sources_failed == []
    assert sum(r.url.host == "api.open-meteo.com" for r in calls) == 2


async def test_timeouts_count_as_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await hz.fetch_report(*VENUE, client)
    assert len(report.sources_failed) == 3


# --- cache (needs MONGODB_TEST_URI) -------------------------------------------------

async def test_cache_serves_repeat_calls_within_a_km(async_db):
    calls: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=_transport(calls=calls)) as client:
        first = await hz.get_hazards(async_db, *VENUE, client)
        second = await hz.get_hazards(async_db, VENUE[0] + 0.001, VENUE[1] - 0.001, client)
    assert len(calls) == 3  # one fetch per source, then the cache
    assert second == first


async def test_stale_cache_is_refetched(async_db):
    old = datetime.now(UTC) - timedelta(seconds=get_settings().hazard_cache_seconds + 5)
    report = hz.build_report(load("nws_venue.json"), None, None).model_dump()
    await async_db.hazard_cache.insert_one({"_id": hz.cache_key(*VENUE), "report": report, "fetched_at": old})
    calls: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=_transport(calls=calls)) as client:
        fresh = await hz.get_hazards(async_db, *VENUE, client)
    assert len(calls) == 3 and fresh["sources_failed"] == []


async def test_partial_results_are_not_cached(async_db):
    async with httpx.AsyncClient(transport=_transport(fail={"api.weather.gov"})) as client:
        report = await hz.get_hazards(async_db, *VENUE, client)
    assert report["sources_failed"] == ["NWS"]
    assert await async_db.hazard_cache.count_documents({}) == 0


# --- endpoint (needs MONGODB_TEST_URI) ----------------------------------------------

def test_endpoint_requires_login_and_validates_coordinates(env, monkeypatch):
    async def fake_fetch(lat, lon, client=None):
        return hz.build_report(load("nws_venue.json"), load("openmeteo_forecast_venue.json"), load("openmeteo_aq_venue.json"))

    monkeypatch.setattr(hz, "fetch_report", fake_fetch)
    assert env.client.get("/api/hazards", params={"lat": VENUE[0], "lon": VENUE[1]}).status_code == 401
    _, headers = env.make_user(None, "Viewer")
    resp = env.client.get("/api/hazards", params={"lat": VENUE[0], "lon": VENUE[1]}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["simulated"] is False and body["level"] == 0 and body["sources_failed"] == []
    assert set(body) == {"level", "hazards", "likely_needs", "current", "simulated", "sources_failed", "fetched_at"}
    bad = env.client.get("/api/hazards", params={"lat": 95, "lon": 0}, headers=headers)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"
