"""Request create flow (PLAN.md §9.3): triage, tract + EJI, hazards, priority. Needs MONGODB_TEST_URI; skipped otherwise."""

import json

import pytest
from pymongo import GEOSPHERE

from app.ai.provider import LLMError
from app.models import Role
from app.services import hazards
from app.services import triage as triage_module

VENUE = {"lat": 33.7756, "lon": -84.3963}
FIXTURE_TRACT = {
    "_id": "13121000000",
    "geoid": "13121000000",
    "name": "Fixture Tract",  # a test square around the venue, not a real boundary
    "eji_rank": 0.72, "climate_rank": 0.6, "env_rank": 0.5, "svm_rank": 0.8, "hvm_rank": 0.2,
    "geometry": {"type": "Polygon", "coordinates": [[[-84.40, 33.77], [-84.39, 33.77], [-84.39, 33.78], [-84.40, 33.78], [-84.40, 33.77]]]},
}
STORM_NWS = {"features": [{"properties": {
    "event": "Severe Thunderstorm Warning", "severity": "Severe", "status": "Actual",
    "headline": "Severe Thunderstorm Warning (test)", "expires": "2026-09-27T20:00:00-04:00", "instruction": "Move indoors.",
}}]}


class CountingProvider:
    """Muse stand-in that records calls and returns a fixed triage, or raises."""

    name = "fake"

    def __init__(self, error: Exception | None = None, urgency: int = 2) -> None:
        self.error, self.urgency, self.calls, self.hazard_inputs = error, urgency, 0, []

    async def complete_json(self, system, user, schema, temperature=0.2):
        self.calls += 1
        self.hazard_inputs.append(user)
        if self.error:
            raise self.error
        return schema(category="power", urgency=self.urgency, flags=[], needs=["generator"], summary="Needs power for a device")


@pytest.fixture
def provider(monkeypatch):
    def install(fake):
        monkeypatch.setattr(triage_module, "get_provider", lambda: fake)
        return fake

    return install


@pytest.fixture
def storm(monkeypatch):
    """A level-3 official alert everywhere (built through the real parser)."""
    report = hazards.build_report(STORM_NWS, {"current": {}, "hourly": {}}, {"current": {}})

    async def fetch(lat, lon, client=None):
        return report

    monkeypatch.setattr(hazards, "fetch_report", fetch)


@pytest.fixture
def tract(env):
    env.raw.tracts.create_index([("geometry", GEOSPHERE)])
    env.raw.tracts.insert_one(FIXTURE_TRACT)


def _requester(env, **fields):
    return env.make_user(Role.requester, "Requester", **fields)[1]


def test_create_stores_triage_tract_hazards_and_priority(env, tract, storm, provider):
    provider(CountingProvider(urgency=2))
    headers = _requester(env, requester_flags={"medical_device": True, "mobility": False, "lives_alone": False})
    resp = env.client.post("/api/requests", json={"text": "Power is out and my oxygen concentrator needs power", "location": VENUE}, headers=headers)
    assert resp.status_code == 200, resp.text
    doc = env.raw.requests.find_one()

    assert doc["urgency_rule_floor"] == 4 and doc["urgency"] == 4  # the LLM said 2; it can't lower the floor
    assert doc["category"] == "power" and doc["summary"] == "Needs power for a device" and doc["triage_source"] == "ai"
    assert "medical_device" in doc["flags"]
    assert doc["tract_geoid"] == "13121000000" and doc["eji_rank"] == 0.72
    assert doc["hazard_level"] == 3 and doc["hazard_snapshot"]["hazards"][0]["event"] == "Severe Thunderstorm Warning"

    b = doc["priority_breakdown"]
    assert (b["urgency"]["raw"], b["hazard"]["raw"], b["eji"]["raw"], b["wait"]["raw"]) == (4, 3, 0.72, 0)
    assert doc["priority"] == pytest.approx(0.45 * 0.75 + 0.20 * 1.0 + 0.20 * 0.72 + 0.0, abs=1e-3)
    assert b["eji_missing"] is False


def test_hazard_types_reach_triage(env, storm, provider):
    fake = provider(CountingProvider())
    env.client.post("/api/requests", json={"text": "Tree down, no power", "location": VENUE}, headers=_requester(env))
    assert "severe_storm" in fake.hazard_inputs[0]


def test_outside_georgia_or_no_location_degrades_to_missing_eji(env, provider):
    provider(CountingProvider())
    env.client.post("/api/requests", json={"text": "Need drinking water", "location": {"lat": 40.71, "lon": -74.0}}, headers=_requester(env))
    env.client.post("/api/requests", json={"text": "Need drinking water"}, headers=_requester(env))
    for doc in env.raw.requests.find():
        assert doc["tract_geoid"] is None and doc["eji_rank"] is None
        assert doc["priority_breakdown"]["eji_missing"] is True and doc["priority_breakdown"]["eji"]["value"] == 0.5
    no_loc = env.raw.requests.find_one({"location": {"$exists": False}})
    assert no_loc["hazard_snapshot"] is None and no_loc["hazard_level"] == 0


def test_preview_then_create_calls_the_ai_once(env, provider):
    fake = provider(CountingProvider())
    headers = _requester(env)
    body = {"text": "Power is out, need a generator for the fridge", "location": VENUE}
    assert env.client.post("/api/requests/preview", json=body, headers=headers).status_code == 200
    resp = env.client.post("/api/requests", json=body | {"category_override": "food"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert fake.calls == 1
    doc = env.raw.requests.find_one()
    assert doc["category"] == "food" and doc["summary"] == "Needs power for a device"


def test_changed_text_after_preview_is_triaged_again(env, provider):
    fake = provider(CountingProvider())
    headers = _requester(env)
    env.client.post("/api/requests/preview", json={"text": "Need a generator", "location": VENUE}, headers=headers)
    env.client.post("/api/requests", json={"text": "Need a generator for my insulin fridge", "location": VENUE}, headers=headers)
    assert fake.calls == 2
    assert env.raw.requests.find_one()["urgency"] == 4  # the new text's HIGH term counts


@pytest.mark.parametrize("text", ["My father is unconscious", "Mi padre no puede respirar", "Water is rising inside, we're trapped"])
def test_emergency_with_the_llm_down_still_sets_emergency_and_urgency_5(env, provider, text):
    fake = provider(CountingProvider(error=LLMError("Muse returned 503")))
    resp = env.client.post("/api/requests", json={"text": text, "location": VENUE}, headers=_requester(env)).json()
    assert resp["show_911"] is True and resp["request"]["emergency"] is True
    doc = env.raw.requests.find_one()
    assert doc["emergency"] is True and doc["urgency"] == 5 and doc["urgency_rule_floor"] == 5
    assert fake.calls == 0  # emergencies don't wait on the AI


def test_non_emergency_with_the_llm_down_uses_the_rules(env, provider):
    provider(CountingProvider(error=LLMError("down")))
    env.client.post("/api/requests", json={"text": "I use a wheelchair and need a ride", "location": VENUE}, headers=_requester(env))
    doc = env.raw.requests.find_one()
    assert doc["triage_source"] == "rules" and doc["urgency"] == 4 and doc["category"] == "transport"


def test_other_volunteers_see_triage_but_not_flags_or_internals(env, tract, storm, provider):
    provider(CountingProvider())
    headers = _requester(env, requester_flags={"medical_device": True, "mobility": False, "lives_alone": False})
    own = env.client.post("/api/requests", json={"text": "My oxygen needs power", "location": VENUE}, headers=headers).json()["request"]
    assert "medical_device" in own["flags"] and own["urgency"] == 4

    helper = env.onboard_helper("Marcus", "generator")
    for url in (f"/api/requests/{own['id']}", "/api/requests/ranked"):
        body = env.client.get(url, headers=helper).json()
        seen = body["request"] if "request" in body else body["requests"][0]
        assert (seen["category"], seen["urgency"], seen["summary"], seen["needs"]) == ("power", 4, "Needs power for a device", ["generator"])
        blob = json.dumps(body)
        for hidden in ("flags", "medical_device", "tract_geoid", "13121000000", "eji_rank", "hazard_snapshot", "priority_breakdown"):
            assert hidden not in blob, hidden
