"""Address search via the US Census geocoder (PLAN.md §6/§13). Street addresses only: it does not match place names."""

import logging

import httpx

log = logging.getLogger(__name__)

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
TIMEOUT_S = 8
MAX_MATCHES = 5


class GeocoderUnavailable(Exception):
    pass


def parse_census(payload: dict) -> list[dict]:
    """Verified against a live response: result.addressMatches[].coordinates {x: lon, y: lat} and matchedAddress."""
    matches = (payload.get("result") or {}).get("addressMatches") or []
    out = []
    for m in matches[:MAX_MATCHES]:
        coords = m.get("coordinates") or {}
        if "x" in coords and "y" in coords:
            out.append({"label": str(m.get("matchedAddress", "")).title(), "lat": coords["y"], "lon": coords["x"]})
    return out


async def geocode(query: str) -> list[dict]:
    params = {"address": query, "benchmark": "Public_AR_Current", "format": "json"}
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for _ in range(2):  # one retry (CLAUDE.md)
            try:
                resp = await client.get(CENSUS_URL, params=params)
                resp.raise_for_status()
                return parse_census(resp.json())
            except (httpx.HTTPError, ValueError) as e:
                last = e
    log.warning("Census geocoder failed: %s", last)
    raise GeocoderUnavailable from last
