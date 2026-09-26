from app.services.embeddings import embed_for_matching


def helper_profile_text(user: dict) -> str:
    """Everything about a volunteer that should drive matching, as one string."""
    helper = user.get("helper") or {}
    parts = []
    if helper.get("skills"):
        parts.append("Skills: " + ", ".join(s.replace("_", " ") for s in helper["skills"]))
    if helper.get("resources"):
        parts.append("Resources: " + ", ".join(r.replace("_", " ") for r in helper["resources"]))
    if helper.get("about"):
        parts.append("Can offer: " + helper["about"])
    if user.get("background"):
        parts.append("Background: " + user["background"])
    return ". ".join(parts)


async def helper_embedding_fields(user: dict) -> dict:
    """Fields to $set on a volunteer after their profile changes."""
    text = helper_profile_text(user)
    if not text:
        return {"profile_text": "", "embed_text": "", "embedding": None}
    embed_text, vector = await embed_for_matching(text, "helper")
    return {"profile_text": text, "embed_text": embed_text, "embedding": vector}
