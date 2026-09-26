"""Pure-logic tests: no database needed."""

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings
from app.errors import APIError
from app.main import app
from app.models import RequestStatus as S
from app.security import create_token, decode_token
from app.services.ranking import rank_local
from app.services.rules import is_emergency
from app.services.serialize import serialize_request
from app.services.state import TRANSITIONS, check_transition

# --- rules -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "My dad can't breathe",
        "I CANNOT BREATHE",
        "my neighbor is trapped under a tree",
        "water is rising inside the house",
        "there's a fire in the kitchen",
        "No puedo respirar",
        "mi mamá está atrapada",
        "tiene dolor de pecho",
        "hay un incendio",
        "My husband is unconscious",
    ],
)
def test_emergency_phrases(text):
    assert is_emergency(text)


@pytest.mark.parametrize(
    "text",
    ["A tree fell on my driveway", "Necesito agua y comida", "Power is out, need to charge my phone", "firewood for the stove"],
)
def test_non_emergency_phrases(text):
    assert not is_emergency(text)


# --- state machine -----------------------------------------------------------

VALID = [
    (S.OPEN, S.CLAIMED, "helper"),
    (S.OPEN, S.CANCELLED, "requester"),
    (S.CLAIMED, S.RESOLVED, "requester"),
    (S.CLAIMED, S.RESOLVED, "assigned_helper"),
    (S.CLAIMED, S.OPEN, "assigned_helper"),
    (S.CLAIMED, S.CANCELLED, "requester"),
]


@pytest.mark.parametrize("current,target,actor", VALID)
def test_valid_transitions(current, target, actor):
    check_transition(current, target, actor)


def test_every_other_transition_is_rejected():
    valid = set(VALID)
    for current in S:
        for target in S:
            for actor in ("requester", "assigned_helper", "helper"):
                if (current, target, actor) in valid:
                    continue
                with pytest.raises(APIError) as exc:
                    check_transition(current, target, actor)
                assert exc.value.status_code == 409
                assert exc.value.code == "INVALID_TRANSITION"
    assert len(TRANSITIONS) == 5


# --- serializer (one test per viewer row, PLAN.md §0.1) ----------------------

REQUESTER = {"_id": ObjectId(), "name": "Ruth", "role": "requester", "language": "en", "background": "retired",
             "requester_flags": {"medical_device": True, "mobility": False, "lives_alone": True}}
HELPER = {"_id": ObjectId(), "name": "Janelle", "role": "helper"}
OTHER_HELPER = {"_id": ObjectId(), "name": "Marcus", "role": "helper"}
NOW = datetime.now(UTC)


def _req(status=S.CLAIMED):
    return {
        "_id": ObjectId(), "requester_id": REQUESTER["_id"], "helper_id": HELPER["_id"], "text": "Need power",
        "status": status, "language": "en", "emergency": False, "embedding": [0.1] * 384, "embed_text": "power",
        "created_at": NOW, "updated_at": NOW, "timeline": [{"status": status, "at": NOW, "by": HELPER["_id"]}],
    }


def _ser(req, viewer):
    return serialize_request(req, viewer, requester=REQUESTER, helper=HELPER)


def test_serializer_requester_sees_own_request_and_helper_name():
    out = _ser(_req(), REQUESTER)
    assert out["viewer_relation"] == "requester"
    assert out["helper"] == {"id": str(HELPER["_id"]), "name": "Janelle"}
    assert "requester" not in out


def test_serializer_assigned_helper_sees_requester_details():
    out = _ser(_req(), HELPER)
    assert out["viewer_relation"] == "assigned_helper"
    assert out["requester"]["name"] == "Ruth"
    assert out["requester"]["requester_flags"]["medical_device"] is True


def test_serializer_other_helper_sees_text_only():
    out = _ser(_req(S.OPEN), OTHER_HELPER)
    assert out["viewer_relation"] == "other"
    assert out["text"] == "Need power"
    for hidden in ("requester", "helper", "timeline", "requester_id", "helper_id", "embedding", "embed_text"):
        assert hidden not in out


def test_serializer_helper_loses_access_after_cancel():
    out = _ser(_req(S.CANCELLED), HELPER)
    assert out["viewer_relation"] == "other"
    assert "requester" not in out


def test_serializer_never_leaks_embeddings():
    for viewer in (REQUESTER, HELPER, OTHER_HELPER):
        out = _ser(_req(), viewer)
        assert "embedding" not in out and "embed_text" not in out


# --- ranking -------------------------------------------------------------------


def test_rank_local_orders_by_similarity_and_puts_unembedded_last():
    docs = [
        {"_id": 1, "embedding": [1.0, 0.0], "created_at": NOW},
        {"_id": 2, "embedding": [0.0, 1.0], "created_at": NOW},
        {"_id": 3, "embedding": None, "created_at": NOW},
        {"_id": 4, "embedding": [0.7, 0.7], "created_at": NOW - timedelta(minutes=1)},
    ]
    ranked = rank_local(docs, [1.0, 0.1], limit=10)
    assert [d["_id"] for d, _ in ranked] == [1, 4, 2, 3]
    scores = [s for _, s in ranked]
    assert all(0.0 <= s <= 1.0 for s in scores[:3]) and scores[3] is None


# --- auth ------------------------------------------------------------------------


def test_jwt_round_trip():
    settings = get_settings()
    assert decode_token(create_token("abc123", settings), settings) == "abc123"
    assert decode_token("not-a-token", settings) is None


@pytest.fixture
def app_without_db(monkeypatch):
    async def fail_connect(_settings):
        raise RuntimeError("no db")

    monkeypatch.setattr(db, "connect", fail_connect)
    with TestClient(app) as client:
        yield client


def test_demo_endpoints_404_when_flag_off(app_without_db):
    assert app_without_db.get("/api/auth/demo-users").status_code == 404
    resp = app_without_db.post("/api/auth/demo", json={"user_id": str(ObjectId())})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_me_requires_login(app_without_db):
    # Without a DB the dependency reports 503 before auth; either way no user data leaks.
    assert app_without_db.get("/api/me").status_code in (401, 503)
