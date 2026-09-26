"""Text → vector for similarity ranking (PLAN.md §0.1).

Muse Spark optionally normalizes the text; fastembed (all-MiniLM-L6-v2, local ONNX) embeds it.
The Meta Model API has no embeddings endpoint, so vectors always come from the local model.
"""

import asyncio
import logging
import threading
from typing import Literal, Protocol

from app.ai import prompts
from app.ai.provider import get_provider
from app.config import get_settings

log = logging.getLogger("mesh.embeddings")

Kind = Literal["request", "helper"]
DIMENSIONS = 384


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding  # heavy import; load on first use

                log.info("Loading embedding model %s (downloads on first run)", self._model_name)
                self._model = TextEmbedding(self._model_name)
        return [vec.tolist() for vec in self._model.embed(texts)]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = FastEmbedEmbedder(get_settings().embedding_model)
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    """Swap the embedder (tests use a fake so they don't download the model)."""
    global _embedder
    _embedder = embedder


async def normalize_for_embedding(text: str, kind: Kind) -> str:
    provider = get_provider()
    if provider.name == "mock":
        return text
    system = prompts.NORMALIZE_REQUEST if kind == "request" else prompts.NORMALIZE_HELPER
    try:
        out = (await provider.complete_text(system, prompts.wrap_untrusted(text), temperature=0.0)).strip()
    except Exception:
        log.exception("Normalization failed; embedding the raw text")
        return text
    return out[:1000] or text


async def embed_for_matching(text: str, kind: Kind) -> tuple[str, list[float] | None]:
    """Return (text that was embedded, vector). The vector is None if embedding failed."""
    embed_text = await normalize_for_embedding(text, kind)
    try:
        [vector] = await asyncio.to_thread(get_embedder().embed, [embed_text])
    except Exception:
        log.exception("Embedding failed; this item will be ranked without a score")
        return embed_text, None
    return embed_text, vector
