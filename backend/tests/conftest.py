import os
import re
import uuid
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.ai.provider import get_provider
from app.config import get_settings
from app.models import Role
from app.security import COOKIE_NAME, create_token
from app.services import embeddings, ranking


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words are more similar. No model download."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * embeddings.DIMENSIONS
            for word in re.findall(r"[a-z]+", text.lower()):
                if len(word) > 2:
                    vec[zlib.crc32(word.encode()) % embeddings.DIMENSIONS] += 1.0
            out.append(vec)
        return out


def _reset_caches() -> None:
    get_settings.cache_clear()
    get_provider.cache_clear()
    ranking.reset()


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch) -> Iterator[None]:
    """Tests never depend on a developer's .env values for these flags."""
    monkeypatch.setenv("DEMO_LOGIN", "false")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("VECTOR_SEARCH", "local")
    embeddings.set_embedder(FakeEmbedder())
    _reset_caches()
    yield
    embeddings.set_embedder(None)
    _reset_caches()


class Env:
    """A running app against a throwaway database, plus helpers to create users."""

    def __init__(self, client: TestClient, raw) -> None:
        self.client = client
        self.raw = raw  # sync pymongo database for setup/inspection

    def make_user(self, role: Role | None, name: str = "User", **fields) -> tuple[dict, dict]:
        now = datetime.now(UTC)
        doc = {
            "google_sub": f"test-{uuid.uuid4().hex}",
            "email": f"{uuid.uuid4().hex[:8]}@example.com",
            "name": name,
            "role": role,
            "language": "en",
            "background": "",
            "helper": {"skills": [], "resources": [], "about": ""} if role == Role.helper else None,
            "requester_flags": {"medical_device": False, "mobility": False, "lives_alone": False},
            "created_at": now,
            "updated_at": now,
        } | fields
        doc["_id"] = self.raw.users.insert_one(doc).inserted_id
        headers = {"Cookie": f"{COOKIE_NAME}={create_token(str(doc['_id']), get_settings())}"}
        return doc, headers

    def onboard_helper(self, name: str, about: str, skills: list[str] | None = None) -> dict:
        """Create a helper through the API so their profile gets embedded."""
        _, headers = self.make_user(None, name)
        body = {"role": "helper", "name": name, "helper": {"skills": skills or [], "resources": [], "about": about}}
        resp = self.client.post("/api/onboarding", json=body, headers=headers)
        assert resp.status_code == 200, resp.text
        return headers


@pytest.fixture
def env(monkeypatch) -> Iterator[Env]:
    uri = os.environ.get("MONGODB_TEST_URI")
    if not uri:
        pytest.skip("MONGODB_TEST_URI not set")
    db_name = f"mesh_test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("MONGODB_URI", uri)
    monkeypatch.setenv("MONGODB_DB", db_name)
    monkeypatch.setenv("DEMO_LOGIN", "true")
    _reset_caches()

    from app.main import app

    sync = MongoClient(uri)
    try:
        with TestClient(app) as client:
            yield Env(client, sync[db_name])
    finally:
        drop_test_db(sync[db_name])
        sync.close()


def drop_test_db(db) -> None:
    """Drop every collection; Mongo removes the empty database. Atlas readWrite roles can't dropDatabase."""
    for name in db.list_collection_names():
        db.drop_collection(name)
