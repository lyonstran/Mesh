"""Hazard engine (PLAN.md §7): NWS active alerts first, Open-Meteo forecast and air quality as derived signals.

Parsers are pure functions over the raw API payloads (tests feed them recorded real responses).
`get_hazards` fetches all three sources concurrently, returns partial results with `sources_failed`
instead of raising, and caches complete results in `hazard_cache` for about 1 km.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import httpx
import yaml
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings
from app.models import Hazard, HazardReport, HazardType
from app.services import sim

log = logging.getLogger("mesh.hazards")

NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEOUT_S = 8
THRESHOLDS_PATH = Path(__file__).resolve().parents[1] / "hazard_thresholds.yaml"

SRC_NWS = "NWS"
SRC_FORECAST = "Open-Meteo forecast"
SRC_AIR = "Open-Meteo air quality"

# Case-insensitive substring match, first hit wins (PLAN.md §7). "Flash Flood" is covered by "Flood".
EVENT_TYPES: list[tuple[str, HazardType]] = [
    ("tornado", "tornado"),
    ("severe thunderstorm", "severe_storm"),
    ("flood", "flood"),
    ("excessive heat", "heat"),
    ("extreme heat", "heat"),
    ("heat advisory", "heat"),
    ("air quality", "air_quality"),
    ("dense smoke", "air_quality"),
    ("winter storm", "winter"),
    ("ice storm", "winter"),
    ("winter weather", "winter"),
    ("freeze", "winter"),
    ("cold", "winter"),
    ("hurricane", "tropical"),
    ("tropical storm", "tropical"),
    ("high wind", "wind"),
    ("wind advisory", "wind"),
]

SEVERITY_LEVELS = {"extreme": 3, "severe": 3, "moderate": 2, "minor": 1, "unknown": 1}

_STORM_NEEDS = ["debris", "power", "shelter", "supplies"]
_FLOOD_NEEDS = ["transport", "supplies", "shelter"]
LIKELY_NEEDS: dict[str, list[str]] = {
    "tornado": _STORM_NEEDS,
    "severe_storm": _STORM_NEEDS,
    "wind": _STORM_NEEDS,
    "flood": _FLOOD_NEEDS,
    "heat": ["water", "cooling", "welfare_check", "transport"],
    "air_quality": ["respiratory", "supplies", "welfare_check"],
    "winter": ["warming", "power", "supplies"],
    "tropical": list(dict.fromkeys(_STORM_NEEDS + _FLOOD_NEEDS)),
}


@lru_cache
def thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))


# --- parsers (pure) -------------------------------------------------------------

def event_type(event: str) -> HazardType:
    lowered = event.lower()
    for needle, kind in EVENT_TYPES:
        if needle in lowered:
            return kind
    return "other"


def severity_level(severity: str | None) -> int:
    return SEVERITY_LEVELS.get((severity or "unknown").lower(), 1)


def parse_nws(payload: dict) -> list[Hazard]:
    """GeoJSON FeatureCollection from /alerts/active. Test and exercise messages are skipped."""
    out = []
    for feature in payload.get("features") or []:
        p = feature.get("properties") or {}
        event = p.get("event")
        if not event or (p.get("status") or "Actual") != "Actual":
            continue
        out.append(
            Hazard(
                type=event_type(event),
                level=severity_level(p.get("severity")),
                source="NWS",
                official=True,
                event=event,
                headline=p.get("headline"),
                expires=p.get("expires"),
                instruction=p.get("instruction"),
            )
        )
    return out


def _max(values: list) -> float | None:
    nums = [v for v in values if isinstance(v, (int, float))]
    return max(nums) if nums else None


def _derived(kind: HazardType, level: int, value: float, unit: str, category: str | None = None) -> Hazard:
    cap = thresholds()["derived_level_cap"]
    return Hazard(
        type=kind, level=min(level, cap), source="Open-Meteo", official=False, value=value, unit=unit, category=category
    )


def parse_forecast(payload: dict) -> tuple[list[Hazard], dict[str, float | None]]:
    """Open-Meteo /v1/forecast with current + 12 hourly steps (units requested as F, mph, inch)."""
    t = thresholds()
    cur = payload.get("current") or {}
    hourly = payload.get("hourly") or {}
    gust = _max([cur.get("wind_gusts_10m"), *(hourly.get("wind_gusts_10m") or [])])
    feels = _max([cur.get("apparent_temperature"), *(hourly.get("apparent_temperature") or [])])
    rain = [v for v in hourly.get("precipitation") or [] if isinstance(v, (int, float))]
    rain_12h = round(sum(rain), 2) if rain else None

    hazards = []
    if gust is not None and gust >= t["wind_gust_mph"]["min"]:
        hazards.append(_derived("wind", t["wind_gust_mph"]["level"], gust, "mph gust"))
    if feels is not None and feels >= t["apparent_temp_f"]["min"]:
        hazards.append(_derived("heat", t["apparent_temp_f"]["level"], feels, "°F feels-like"))
    if rain_12h is not None and rain_12h >= t["precip_12h_in"]["min"]:
        hazards.append(_derived("flood", t["precip_12h_in"]["level"], rain_12h, "in rain, next 12 h"))
    current = {
        "temperature_f": cur.get("temperature_2m"),
        "apparent_temperature_f": cur.get("apparent_temperature"),
        "wind_gust_mph": cur.get("wind_gusts_10m"),
        "precip_next_12h_in": rain_12h,
    }
    return hazards, current


def aqi_band(aqi: float) -> dict | None:
    band = None
    for b in thresholds()["aqi"]:  # ascending by min
        if aqi >= b["min"]:
            band = b
    return band


def parse_air_quality(payload: dict) -> tuple[list[Hazard], dict[str, float | None]]:
    cur = payload.get("current") or {}
    aqi = cur.get("us_aqi")
    hazards = []
    if isinstance(aqi, (int, float)) and (band := aqi_band(aqi)):
        hazards.append(_derived("air_quality", band["level"], aqi, "US AQI", band["category"]))
    return hazards, {"us_aqi": aqi, "pm2_5": cur.get("pm2_5")}


def likely_needs(hazards: list[Hazard]) -> list[str]:
    needs: list[str] = []
    for h in sorted(hazards, key=lambda h: -h.level):
        needs.extend(LIKELY_NEEDS.get(h.type, []))
    return list(dict.fromkeys(needs))


def build_report(
    nws: dict | None, forecast: dict | None, air: dict | None, *, fetched_at: datetime | None = None
) -> HazardReport:
    """Combine raw payloads (None = that source failed) into the §7 output shape."""
    hazards: list[Hazard] = []
    current: dict[str, float | None] = {
        "temperature_f": None, "apparent_temperature_f": None, "wind_gust_mph": None,
        "precip_next_12h_in": None, "us_aqi": None, "pm2_5": None,
    }
    failed = []
    if nws is None:
        failed.append(SRC_NWS)
    else:
        hazards += parse_nws(nws)
    for payload, name, parse in ((forecast, SRC_FORECAST, parse_forecast), (air, SRC_AIR, parse_air_quality)):
        if payload is None:
            failed.append(name)
            continue
        found, values = parse(payload)
        hazards += found
        current |= values
    hazards.sort(key=lambda h: (-h.level, not h.official))
    return HazardReport(
        level=max((h.level for h in hazards), default=0),
        hazards=hazards,
        likely_needs=likely_needs(hazards),
        current=current,
        simulated=False,
        sources_failed=failed,
        fetched_at=(fetched_at or datetime.now(UTC)).isoformat(),
    )


# --- fetching ---------------------------------------------------------------------

async def _get_json(client: httpx.AsyncClient, url: str, params: dict, headers: dict | None = None) -> dict:
    last: Exception | None = None
    for _ in range(2):  # one retry (CLAUDE.md)
        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            last = e
    raise last  # type: ignore[misc]


def _forecast_params(lat: float, lon: float) -> dict:
    return {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,wind_gusts_10m,precipitation",
        "hourly": "apparent_temperature,wind_gusts_10m,precipitation",
        "forecast_hours": 12,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": get_settings().default_timezone,
    }


def _air_params(lat: float, lon: float) -> dict:
    return {"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5,pm10,ozone", "timezone": get_settings().default_timezone}


async def fetch_report(lat: float, lon: float, client: httpx.AsyncClient | None = None) -> HazardReport:
    """Fetch all three sources concurrently. Never raises for an upstream failure."""
    headers = {"User-Agent": get_settings().nws_user_agent, "Accept": "application/geo+json"}
    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        results = await asyncio.gather(
            # NWS wants at most 4 decimal places in `point`.
            _get_json(client, NWS_ALERTS_URL, {"point": f"{lat:.4f},{lon:.4f}"}, headers),
            _get_json(client, FORECAST_URL, _forecast_params(lat, lon)),
            _get_json(client, AIR_QUALITY_URL, _air_params(lat, lon)),
            return_exceptions=True,
        )
    finally:
        if own:
            await client.aclose()
    payloads = []
    for name, r in zip((SRC_NWS, SRC_FORECAST, SRC_AIR), results, strict=True):
        if isinstance(r, BaseException):
            log.warning("%s failed: %r", name, r)
            payloads.append(None)
        else:
            payloads.append(r)
    try:
        return build_report(*payloads)
    except Exception:  # a response shape we don't understand: degrade rather than 500
        log.exception("Could not parse hazard sources; returning an empty report")
        return build_report(None, None, None)


def cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 2)},{round(lon, 2)}"


async def get_hazards(db: AsyncDatabase, lat: float, lon: float, client: httpx.AsyncClient | None = None) -> dict:
    """The §7 hazard report for a point, served from `hazard_cache` when fresh."""
    key = cache_key(lat, lon)
    max_age = timedelta(seconds=get_settings().hazard_cache_seconds)
    cached = await db.hazard_cache.find_one({"_id": key})
    # The TTL monitor only runs about once a minute, so check freshness here too.
    if cached and cached["fetched_at"] > datetime.now(UTC) - max_age:
        report = cached["report"]
    else:
        report = (await fetch_report(lat, lon, client)).model_dump()
        # Only cache complete results, so a failed source is retried on the next call.
        if not report["sources_failed"]:
            await db.hazard_cache.replace_one(
                {"_id": key}, {"report": report, "fetched_at": datetime.now(UTC)}, upsert=True
            )
    # Simulation merge (PLAN.md §7): adds the active demo scenario's hazards here and sets simulated: true.
    return await sim.merge(report, db, lat, lon)
