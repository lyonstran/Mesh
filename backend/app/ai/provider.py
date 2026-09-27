import json
import logging
import re
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings

log = logging.getLogger("mesh.ai")

M = TypeVar("M", bound=BaseModel)


class LLMError(Exception):
    pass


class TriageFallback(LLMError):
    """The LLM's JSON was still invalid after one retry; the caller uses rules-only output (PLAN.md §8)."""


class LLMProvider(Protocol):
    """PLAN.md §8."""

    name: str

    async def complete_text(self, system: str, user: str, temperature: float = 0.3) -> str: ...

    async def complete_json(self, system: str, user: str, schema: type[M], temperature: float = 0.2) -> M: ...


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json(raw: str, schema: type[M]) -> M:
    """Validate an LLM reply against `schema`. Strips code fences and any text around the JSON object."""
    text = _FENCE.sub("", raw.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("No JSON object in the reply")
    return schema.model_validate(json.loads(text[start : end + 1]))


async def complete_json_via_text(
    complete: Callable[[str, str, float], Awaitable[str]], system: str, user: str, schema: type[M], temperature: float
) -> M:
    """Get JSON from `complete(system, user, temperature)` and validate it. On invalid output, retry once with the error."""
    prompt = user
    for attempt in range(2):
        raw = await complete(system, prompt, temperature)
        try:
            return parse_json(raw, schema)
        except (ValueError, ValidationError) as e:
            log.warning("LLM JSON invalid (attempt %d): %s", attempt + 1, e)
            prompt = f"{user}\n\nYour previous reply was invalid ({e}). Reply with only the JSON object."
    raise TriageFallback("Invalid JSON from the LLM after a retry")


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
