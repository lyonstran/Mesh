"""Muse Spark via the Meta Model API's OpenAI-compatible Chat Completions endpoint.

Implemented only from docs/muse-api.md (PLAN.md §14.1).
"""

import httpx

from app.ai.provider import LLMError
from app.config import Settings

_TIMEOUT = httpx.Timeout(8.0)


class MuseProvider:
    name = "muse"

    def __init__(self, settings: Settings) -> None:
        self._url = settings.muse_base_url.rstrip("/") + "/chat/completions"
        self._model = settings.muse_text_model
        self._headers = {"Authorization": f"Bearer {settings.muse_api_key}"}

    async def complete_text(self, system: str, user: str, temperature: float = 0.3) -> str:
        body = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
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
        raise LLMError(f"Muse request failed: {last_error}")
