import asyncio
import logging
from datetime import UTC, datetime

from pymongo import ASCENDING, GEOSPHERE, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings

DEFAULT_WEIGHTS = {"urgency": 0.45, "hazard": 0.20, "eji": 0.20, "wait": 0.15}

log = logging.getLogger("mesh.db")

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None
_ready = False
_init_lock = asyncio.Lock()


async def connect(settings: Settings) -> AsyncDatabase:
    global _client, _db
    if not settings.mongodb_uri:
        # TODO(HUMAN): set MONGODB_URI in .env (Atlas SRV string).
        raise RuntimeError("MONGODB_URI is not set")
    await close()
    _client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    _db = _client[settings.mongodb_db]
    await _client.admin.command("ping")
    return _db


async def init(settings: Settings) -> bool:
    """Connect, ensure indexes and settings docs. Safe to call repeatedly; returns readiness."""
    global _ready
    async with _init_lock:
        if _ready:
            return True
        try:
            database = await connect(settings)
            await ensure_indexes(database, settings.hazard_cache_seconds)
            await ensure_settings_docs(database)
        except Exception:
            log.exception("MongoDB init failed")
            return False
        _ready = True
        log.info("MongoDB ready (db=%s); indexes and settings ensured", settings.mongodb_db)
        return True


def is_ready() -> bool:
    return _ready


async def close() -> None:
    global _client, _db, _ready
    if _client is not None:
        await _client.close()
    _client = None
    _db = None
    _ready = False


def get_db() -> AsyncDatabase:
    if _db is None:
        raise RuntimeError("Database not connected")
    return _db


async def ensure_indexes(db: AsyncDatabase, hazard_cache_seconds: int) -> None:
    """Create all indexes from PLAN.md §5. Idempotent."""
    await db.users.create_index("google_sub", unique=True)
    await db.users.create_index("email")

    await db.presence.create_index([("location", GEOSPHERE)])
    # Presence is per (user, request). Drop the legacy unique index on user_id alone if an older run created it.
    if "user_id_1" in await db.presence.index_information():
        await db.presence.drop_index("user_id_1")
    await db.presence.create_index([("user_id", ASCENDING), ("request_id", ASCENDING)], unique=True)
    await db.presence.create_index("request_id")
    await _ensure_ttl(db, "presence", "updated_at", 120)

    await db.requests.create_index([("location", GEOSPHERE)])
    await db.requests.create_index([("display_location", GEOSPHERE)])
    for field in ("status", "requester_id", "helper_id", "created_at"):
        await db.requests.create_index(field)

    await db.messages.create_index([("request_id", ASCENDING), ("ts", ASCENDING)])

    await db.tracts.create_index([("geometry", GEOSPHERE)])

    await db.resources.create_index([("location", GEOSPHERE)])

    # hazard_cache._id (the cache key string) is indexed automatically.
    await _ensure_ttl(db, "hazard_cache", "fetched_at", hazard_cache_seconds)


async def _ensure_ttl(db: AsyncDatabase, coll: str, field: str, seconds: int) -> None:
    """Create a TTL index, updating expireAfterSeconds in place if it changed."""
    name = f"{field}_1"
    existing = await db[coll].index_information()
    if name in existing and existing[name].get("expireAfterSeconds") != seconds:
        await db.command("collMod", coll, index={"name": name, "expireAfterSeconds": seconds})
        return
    await db[coll].create_index(field, expireAfterSeconds=seconds)


async def ensure_settings_docs(db: AsyncDatabase) -> None:
    """Create the `weights` and `sim` settings documents if missing."""
    await db.settings.update_one(
        {"_id": "weights"},
        {"$setOnInsert": {**DEFAULT_WEIGHTS, "updated_at": datetime.now(UTC)}},
        upsert=True,
    )
    await db.settings.update_one(
        {"_id": "sim"},
        {"$setOnInsert": {"active": False, "scenario_id": None, "activated_at": None}},
        upsert=True,
    )
