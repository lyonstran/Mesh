"""Remember each requester's last triage preview for a few minutes, so create() doesn't make them wait for the AI twice.

In-process only (single uvicorn worker). A miss just means create() runs triage again; nothing depends on a hit.
The cached card is a server-side result keyed by what was previewed, so the client can never supply its own urgency.
"""

import time

from app.models import Triage

TTL_S = 10 * 60
MAX_ENTRIES = 500

_entries: dict[tuple, tuple[float, Triage]] = {}


def _key(user_id: object, text: str, lat: float | None, lon: float | None) -> tuple:
    point = (round(lat, 3), round(lon, 3)) if lat is not None and lon is not None else None
    return (str(user_id), text.strip(), point)


def put(user_id: object, text: str, lat: float | None, lon: float | None, card: Triage) -> None:
    now = time.monotonic()
    if len(_entries) >= MAX_ENTRIES:
        for k in [k for k, (at, _) in _entries.items() if now - at > TTL_S] or list(_entries)[: MAX_ENTRIES // 2]:
            _entries.pop(k, None)
    _entries[_key(user_id, text, lat, lon)] = (now, card)


def take(user_id: object, text: str, lat: float | None, lon: float | None) -> Triage | None:
    """The cached card for exactly this draft, if fresh. Removes it either way."""
    hit = _entries.pop(_key(user_id, text, lat, lon), None)
    if hit is None or time.monotonic() - hit[0] > TTL_S:
        return None
    return hit[1]


def clear() -> None:
    _entries.clear()
