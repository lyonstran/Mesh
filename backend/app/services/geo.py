"""Coordinate helpers. The API speaks {lat, lon}; Mongo stores GeoJSON [lon, lat] (CLAUDE.md: don't mix them up)."""

import math

EARTH_RADIUS_KM = 6371.0088


def to_geojson(lat: float, lon: float) -> dict:
    return {"type": "Point", "coordinates": [lon, lat]}


def from_geojson(point: dict | None) -> dict | None:
    """GeoJSON Point -> {"lat", "lon"}, or None when there is no (valid) point."""
    if not point or point.get("type") != "Point":
        return None
    coords = point.get("coordinates") or []
    if len(coords) != 2:
        return None
    return {"lat": coords[1], "lon": coords[0]}


def haversine_km(a: dict, b: dict) -> float:
    """Great-circle distance between two {"lat", "lon"} points."""
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(b["lon"] - a["lon"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def destination(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """The point `distance_m` metres from (lat, lon) along `bearing_deg` (clockwise from north)."""
    ang = distance_m / 1000 / EARTH_RADIUS_KM
    brg = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(ang) + math.cos(p1) * math.sin(ang) * math.cos(brg))
    l2 = l1 + math.atan2(math.sin(brg) * math.sin(ang) * math.cos(p1), math.cos(ang) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180
