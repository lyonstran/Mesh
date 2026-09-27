"""Display geometry for map overlays (NWS alert areas, tract shading): simplified, sliver-free, valid, JSON-ready."""

import logging

from shapely import make_valid, set_precision
from shapely.geometry import MultiPolygon, Polygon, mapping, shape

log = logging.getLogger("mesh.geometry")

MIN_PART_AREA_DEG2 = 2e-6  # drop slivers and tiny marsh islands (about 0.02 km²)
GRID_DEG = 1e-4  # snap to ~10 m


def polygonal(geom, min_area: float = MIN_PART_AREA_DEG2) -> Polygon | MultiPolygon | None:
    parts = []
    for g in getattr(geom, "geoms", [geom]):
        if isinstance(g, MultiPolygon):
            parts.extend(g.geoms)
        elif isinstance(g, Polygon):
            parts.append(g)
    parts = [p for p in parts if p.area >= min_area]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def clean(geom, min_area: float = MIN_PART_AREA_DEG2) -> Polygon | MultiPolygon | None:
    """Snap to a ~10 m grid and repair. Rounding coordinates by hand can make coastal shapes self-intersect."""
    return polygonal(make_valid(set_precision(make_valid(geom), GRID_DEG)), min_area)


def to_geojson(geom) -> dict:
    """shapely's mapping() nests tuples; use lists so fresh and cached (Mongo) results are identical."""

    def lists(c):
        return [c[0], c[1]] if isinstance(c[0], (int, float)) else [lists(x) for x in c]

    g = mapping(geom)
    return {"type": g["type"], "coordinates": lists(g["coordinates"])}


def simplify(geometry: dict | None, tolerance: float, min_area: float = MIN_PART_AREA_DEG2) -> dict | None:
    """Simplified, slivers dropped, snapped, valid. None if nothing polygonal remains or the shape can't be read."""
    if not geometry:
        return None
    try:
        geom = clean(shape(geometry).simplify(tolerance, preserve_topology=True), min_area)
    except Exception:
        log.exception("Could not simplify a geometry")
        return None
    return to_geojson(geom) if geom is not None else None
