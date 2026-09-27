"""Muse Spark via the Meta Model API's OpenAI-compatible Chat Completions endpoint.

Implemented only from docs/muse-api.md (PLAN.md §14.1).
"""

import httpx
from pydantic import BaseModel

from app.ai.provider import LLMError, complete_json_via_text
from app.config import Settings

# Spark responses measured 4.5-8.1 s (2026-09-26), so the usual 8 s external-HTTP timeout made
# many calls fail. LLM calls run in background tasks (app/services/indexing.py), so a longer read
# timeout doesn't block users; connecting still fails fast.
_TIMEOUT = httpx.Timeout(25.0, connect=8.0)

# Structured calls (triage) are on the requester's critical path. At the default effort Spark spent ~875 of ~915
# output tokens reasoning and took 10-25 s; at "minimal" it took ~2 s with equal or better labels (2026-09-27).
# "none" is rejected for muse-spark-1.3. Both parameters are in docs/muse-api.md.
_JSON_EXTRAS = {"reasoning_effort": "minimal", "response_format": {"type": "json_object"}}


class MuseProvider:
    name = "muse"

    def __init__(self, settings: Settings) -> None:
        self._url = settings.muse_base_url.rstrip("/") + "/chat/completions"
        self._model = settings.muse_text_model
        self._headers = {"Authorization": f"Bearer {settings.muse_api_key}"}

    async def complete_text(self, system: str, user: str, temperature: float = 0.3) -> str:
        return await self._chat(system, user, temperature, {})

    async def complete_json[M: BaseModel](self, system: str, user: str, schema: type[M], temperature: float = 0.2) -> M:
        # JSON mode guarantees JSON, not our schema, so pydantic still validates it (PLAN.md §8).
        async def complete(s: str, u: str, t: float) -> str:
            return await self._chat(s, u, t, _JSON_EXTRAS)

        return await complete_json_via_text(complete, system, user, schema, temperature)

    async def _chat(self, system: str, user: str, temperature: float, extras: dict) -> str:
        body = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            **extras,
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for _ in range(2):  # one retry
                try:
                    resp = await client.post(self._url, json=body, headers=self._headers)
                    if resp.status_code >= 500:
                        last_error = LLMError(f"Muse returned {resp.status_code}")
                        continue
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]
                except (httpx.TransportError, httpx.HTTPStatusError, KeyError, IndexError, ValueError) as e:
                    last_error = e
                    if isinstance(e, httpx.HTTPStatusError):
                        break  # 4xx won't succeed on retry
        raise LLMError(f"Muse request failed: {type(last_error).__name__}: {last_error}")
