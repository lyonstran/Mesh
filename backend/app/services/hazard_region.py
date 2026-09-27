"""Statewide NWS alerts with map geometry (PLAN.md §7 "regional variant", GET /api/hazards/region).

Most Georgia alerts are zone-based and carry no polygon, so each alert's `affectedZones` are fetched from NWS once,
simplified for display, and cached in `nws_zones` for a week (zone boundaries rarely change). The feed itself is
cached in `hazard_cache` like point reports. Only api.weather.gov zone URLs are ever fetched.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
from pymongo.asynchronous.database import AsyncDatabase
from shapely import make_valid
from shapely.geometry import MultiPolygon, shape
from shapely.ops import unary_union

from app.config import get_settings
from app.services import geometry as geometry_util
from app.services import sim
from app.services.hazards import NWS_ALERTS_URL, TIMEOUT_S, _get_json, event_type, severity_level

log = logging.getLogger("mesh.hazards.region")

AREA = "GA"
ZONE_URL_PREFIX = "https://api.weather.gov/zones/"
ZONE_TTL = timedelta(days=7)
SIMPLIFY_DEG = 0.002  # about 200 m: plenty for a statewide overlay; a coastal zone drops from ~6,500 vertices to ~1,500
MAX_CONCURRENT_ZONES = 6


def _nws_headers() -> dict:
    return {"User-Agent": get_settings().nws_user_agent, "Accept": "application/geo+json"}


def simplify(geometry: dict | None) -> dict | None:
    """Display geometry for an alert area (see services/geometry.py)."""
    return geometry_util.simplify(geometry, SIMPLIFY_DEG)


def _merge(geometries: list[dict]) -> dict | None:
    """One shape for an alert's zones. Falls back to the zones side by side if the union fails."""
    shapes = [shape(g) for g in geometries if g]
    if not shapes:
        return None
    try:
        merged = geometry_util.clean(unary_union([make_valid(s) for s in shapes]))
    except Exception:
        log.warning("Zone union failed; drawing the zones side by side")
        merged = geometry_util.polygonal(MultiPolygon([p for s in shapes for p in getattr(s, "geoms", [s])]))
    return geometry_util.to_geojson(merged) if merged is not None else None


async def _zone_geometry(db: AsyncDatabase, client: httpx.AsyncClient, url: str, gate: asyncio.Semaphore) -> dict | None:
    if not url.startswith(ZONE_URL_PREFIX):
        log.warning("Ignoring non-NWS zone URL %s", url)
        return None
    cached = await db.nws_zones.find_one({"_id": url})
    if cached and cached["fetched_at"] > datetime.now(UTC) - ZONE_TTL:
        return cached["geometry"]
    async with gate:
        try:
            payload = await _get_json(client, url, {}, _nws_headers())
        except Exception as e:
            log.warning("NWS zone %s failed: %r", url, e)
            return cached["geometry"] if cached else None  # a stale shape beats none
    geometry = simplify(payload.get("geometry"))
    name = (payload.get("properties") or {}).get("name")
    await db.nws_zones.replace_one(
        {"_id": url}, {"geometry": geometry, "name": name, "fetched_at": datetime.now(UTC)}, upsert=True
    )
    return geometry


def alert_properties(feature: dict) -> dict | None:
    p = feature.get("properties") or {}
    event = p.get("event")
    if not event or (p.get("status") or "Actual") != "Actual":
        return None
    return {
        "id": p.get("id") or feature.get("id"),
        "event": event,
        "type": event_type(event),
        "level": severity_level(p.get("severity")),
        "official": True,
        "source": "NWS",
        "headline": p.get("headline"),
        "area_desc": p.get("areaDesc"),
        "expires": p.get("expires"),
        "instruction": p.get("instruction"),
    }


async def build_region(db: AsyncDatabase, payload: dict, client: httpx.AsyncClient) -> dict:
    """GeoJSON FeatureCollection of alerts. Alerts whose shape couldn't be found keep geometry: null."""
    gate = asyncio.Semaphore(MAX_CONCURRENT_ZONES)
    features = []
    for feature in payload.get("features") or []:
        props = alert_properties(feature)
        if props is None:
            continue
        if feature.get("geometry"):
            geometry = simplify(feature["geometry"])
        else:
            zones = (feature.get("properties") or {}).get("affectedZones") or []
            shapes = await asyncio.gather(*(_zone_geometry(db, client, z, gate) for z in zones))
            try:
                geometry = _merge([g for g in shapes if g])
            except Exception:
                log.exception("Could not build a shape for %s", props["event"])
                geometry = None
        features.append({"type": "Feature", "geometry": geometry, "properties": props})
    features.sort(key=lambda f: -f["properties"]["level"])
    return {"type": "FeatureCollection", "features": features}


async def get_region(db: AsyncDatabase, client: httpx.AsyncClient | None = None) -> dict:
    """Active alerts for Georgia with geometry, cached like point reports. Never raises for an upstream failure."""
    key = f"region:{AREA}"
    max_age = timedelta(seconds=get_settings().hazard_cache_seconds)
    cached = await db.hazard_cache.find_one({"_id": key})
    if cached and cached["fetched_at"] > datetime.now(UTC) - max_age:
        return await sim.merge_region(cached["report"], db)

    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        try:
            payload = await _get_json(client, NWS_ALERTS_URL, {"area": AREA}, _nws_headers())
        except Exception as e:
            log.warning("NWS region feed failed: %r", e)
            payload = None
        collection = await build_region(db, payload, client) if payload else {"type": "FeatureCollection", "features": []}
    finally:
        if own:
            await client.aclose()

    report = collection | {
        "area": AREA,
        "simulated": False,
        "sources_failed": [] if payload else ["NWS"],
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    if payload:
        await db.hazard_cache.replace_one({"_id": key}, {"report": report, "fetched_at": datetime.now(UTC)}, upsert=True)
    return await sim.merge_region(report, db)
