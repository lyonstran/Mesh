"""Rank OPEN requests for a volunteer by vector similarity (PLAN.md §0.1).

Uses Atlas Vector Search when available, otherwise cosine similarity in Python.
Scores are in [0, 1] either way: Atlas reports (1 + cosine) / 2 for cosine indexes, and the
local path uses the same formula so the numbers are comparable.
"""

import asyncio
import logging
import math
from typing import Literal

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.operations import SearchIndexModel

from app.config import get_settings
from app.models import RequestStatus
from app.services.embeddings import DIMENSIONS

log = logging.getLogger("mesh.ranking")

INDEX_NAME = "requests_embedding"
Mode = Literal["atlas", "local"]

_mode: Mode = "local"
_initialized = False
_init_lock = asyncio.Lock()


def mode() -> Mode:
    return _mode


def reset() -> None:
    global _mode, _initialized
    _mode, _initialized = "local", False


async def ensure_initialized(db: AsyncDatabase) -> Mode:
    """Pick atlas/local once. Creates the vector search index on Atlas if it's missing."""
    global _mode, _initialized
    async with _init_lock:
        if _initialized:
            return _mode
        setting = get_settings().vector_search
        _mode = "local"
        if setting != "local":
            try:
                cursor = await db.requests.list_search_indexes(INDEX_NAME)
                if not await cursor.to_list():
                    await db.requests.create_search_index(
                        SearchIndexModel(
                            definition={
                                "fields": [
                                    {"type": "vector", "path": "embedding", "numDimensions": DIMENSIONS, "similarity": "cosine"},
                                    {"type": "filter", "path": "status"},
                                ]
                            },
                            name=INDEX_NAME,
                            type="vectorSearch",
                        )
                    )
                    log.info("Created Atlas Vector Search index %s", INDEX_NAME)
                _mode = "atlas"
            except Exception as e:
                level = logging.ERROR if setting == "atlas" else logging.INFO
                log.log(level, "Atlas Vector Search unavailable (%s); using local cosine ranking", e)
        _initialized = True
        log.info("Vector search mode: %s", _mode)
        return _mode


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def rank_local(docs: list[dict], query: list[float], limit: int) -> list[tuple[dict, float | None]]:
    """Score docs by (1 + cosine) / 2. Docs without an embedding go last, newest first."""
    scored = [(d, (1 + _cosine(query, d["embedding"])) / 2 if d.get("embedding") else None) for d in docs]
    scored.sort(key=lambda p: p[0]["created_at"], reverse=True)
    scored.sort(key=lambda p: p[1] if p[1] is not None else -1.0, reverse=True)
    return scored[:limit]


async def rank_open_requests(db: AsyncDatabase, helper: dict, limit: int = 50) -> list[tuple[dict, float | None]]:
    open_filter = {"status": RequestStatus.OPEN}
    query = helper.get("embedding")
    if not query:
        docs = await db.requests.find(open_filter).sort("created_at", -1).limit(limit).to_list()
        return [(d, None) for d in docs]

    if await ensure_initialized(db) == "atlas":
        try:
            cursor = await db.requests.aggregate([
                {"$vectorSearch": {
                    "index": INDEX_NAME, "path": "embedding", "queryVector": query,
                    "numCandidates": max(limit * 10, 100), "limit": limit, "filter": open_filter,
                }},
                {"$addFields": {"_score": {"$meta": "vectorSearchScore"}}},
            ])
            docs = await cursor.to_list()
            # An index that is still building returns nothing; fall through to local then.
            if docs:
                ranked = [(d, d.pop("_score")) for d in docs]
                seen = {d["_id"] for d, _ in ranked}
                unembedded = await db.requests.find(
                    open_filter | {"embedding": None}
                ).sort("created_at", -1).limit(limit).to_list()
                return (ranked + [(d, None) for d in unembedded if d["_id"] not in seen])[:limit]
        except Exception:
            log.exception("$vectorSearch failed; falling back to local ranking")

    docs = await db.requests.find(open_filter).to_list(1000)
    return rank_local(docs, query, limit)
