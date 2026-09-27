"""Background (re)embedding for matching (PLAN.md §0.1).

Normalizing text with Muse Spark takes several seconds, so routes save first and schedule these
to run after the response is sent. Each write is guarded so a slow job can't overwrite newer data.
"""

import logging

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.services.embeddings import embed_for_matching

log = logging.getLogger("mesh.indexing")


async def refresh_helper_embedding(database: AsyncDatabase, user_id: ObjectId, profile_text: str) -> None:
    """Embed a volunteer's profile text. Skips the write if the profile changed again meanwhile."""
    if profile_text:
        embed_text, vector = await embed_for_matching(profile_text, "helper")
    else:
        embed_text, vector = "", None
    result = await database.users.update_one(
        {"_id": user_id, "profile_text": profile_text},
        {"$set": {"embed_text": embed_text, "embedding": vector}},
    )
    if result.matched_count == 0:
        log.info("Profile for %s changed during embedding; kept the newer version", user_id)


async def refresh_request_embedding(database: AsyncDatabase, request_id: ObjectId, text: str) -> None:
    """Embed a new request. Until this finishes the request ranks after embedded ones."""
    embed_text, vector = await embed_for_matching(text, "request")
    await database.requests.update_one({"_id": request_id, "text": text}, {"$set": {"embed_text": embed_text, "embedding": vector}})
