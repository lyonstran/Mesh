"""Location fuzzing (PLAN.md §9.5): the point other volunteers see is 300-500 m from the real one.

The offset is deterministic per request, so reloading never moves the pin, but it is seeded with an
HMAC keyed by a server secret rather than the bare request id. The id is visible to every volunteer;
seeding with it alone would let anyone replay the generator and subtract the offset.
"""

import hashlib
import hmac
import random

from app.services.geo import destination

MIN_OFFSET_M = 300
MAX_OFFSET_M = 500


def fuzz_point(lat: float, lon: float, request_id: str, secret: str) -> tuple[float, float]:
    digest = hmac.new(secret.encode(), request_id.encode(), hashlib.sha256).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    return destination(lat, lon, rng.uniform(0, 360), rng.uniform(MIN_OFFSET_M, MAX_OFFSET_M))
