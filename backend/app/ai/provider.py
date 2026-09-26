import logging
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

log = logging.getLogger("mesh.ai")


class LLMError(Exception):
    pass


class LLMProvider(Protocol):
    """PLAN.md §8. The MVP only needs complete_text; complete_json arrives with triage (post-MVP)."""

    name: str

    async def complete_text(self, system: str, user: str, temperature: float = 0.3) -> str: ...


@lru_cache
def get_provider() -> LLMProvider:
    from app.ai.mock import MockProvider
    from app.ai.muse import MuseProvider

    settings = get_settings()
    if settings.llm_provider == "muse":
        if settings.muse_api_key:
            return MuseProvider(settings)
        log.warning("LLM_PROVIDER=muse but MUSE_API_KEY is empty; using MockProvider")
    return MockProvider()
