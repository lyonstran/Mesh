"""Simulation mode (PLAN.md §7): demo-only switch, labeled scenario hazards, re-scoring. Needs MONGODB_TEST_URI."""

import json

import pytest

from app.config import get_settings
from app.models import Role
from app.services import hazard_region, sim

VENUE = {"lat": 33.7756, "lon": -84.3963}
SAVANNAH = {"lat": 32.0809, "lon": -81.0912}  # far outside the scenario's areas
SCENARIO = "atl_hurricane_remnants"


# --- scenario files -----------------------------------------------------------------

def test_every_scenario_is_labeled_and_never_official():
    assert sim.scenarios(), "at least one scenario ships"
    for s in sim.scenarios().values():
        assert s["label"] == "SIMULATED"
        for h in s["hazards"]:
            assert h["source"] == "Simulation" and h["official"] is False
            for text in (h.get("event"), h.get("headline"), h.get("instruction")):
                if text:
                    assert "SIMULATED" in text or "demo scenario" in text, text
        assert all(h["area"] in s["areas"] for h in s["hazards"])


# --- API ------------------------------------------------------------------------------

@pytest.fixture
def quiet_region(monkeypatch):
    """No live NWS in tests: the statewide feed is empty apart from the scenario."""

    async def empty(client, url, params, headers=None):
        return {"type": "FeatureCollection", "features": []}

    monkeypatch.setattr(hazard_region, "_get_json", empty)


def _volunteer(env):
    headers = env.onboard_helper("Vol", "chainsaw, generator, water")
    helper = {"skills": [], "custom_skills": [], "resources": [], "about": "chainsaw, generator, water", "radius_km": 15}
    assert env.client.patch("/api/me", json={"home_location": VENUE, "helper": helper}, headers=headers).status_code == 200
    return headers


def _request_at(env, point, text="Tree down on my street, need help clearing it"):
    _, headers = env.make_user(Role.requester, "Requester")
    resp = env.client.post("/api/requests", json={"text": text, "location": point}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["request"]["id"]


def test_routes_are_404_outside_demo_mode(env, monkeypatch):
    _, headers = env.make_user(Role.helper, "V")
    monkeypatch.setenv("DEMO_LOGIN", "false")
    get_settings.cache_clear()
    assert env.client.get("/api/sim", headers=headers).status_code == 404
    assert env.client.post("/api/sim/activate", json={"scenario_id": SCENARIO}, headers=headers).status_code == 404


def test_needs_login_and_a_known_scenario(env):
    assert env.client.get("/api/sim").status_code == 401
    _, headers = env.make_user(Role.helper, "V")
    state = env.client.get("/api/sim", headers=headers).json()
    assert state["active"] is False and [s["id"] for s in state["scenarios"]] == [SCENARIO]
    bad = env.client.post("/api/sim/activate", json={"scenario_id": "nope"}, headers=headers)
    assert bad.status_code == 404 and bad.json()["error"]["code"] == "UNKNOWN_SCENARIO"


def test_scenario_hazards_apply_inside_its_area_only_and_are_labeled(env):
    _, headers = env.make_user(Role.helper, "V")
    assert env.client.post("/api/sim/activate", json={"scenario_id": SCENARIO}, headers=headers).json()["active"] is True

    inside = env.client.get("/api/hazards", params=VENUE, headers=headers).json()
    assert inside["simulated"] is True and inside["level"] == 3
    sim_hazards = [h for h in inside["hazards"] if h["source"] == "Simulation"]
    assert {h["type"] for h in sim_hazards} >= {"tropical", "flood"} and not any(h["official"] for h in sim_hazards)
    assert inside["current"]["wind_gust_mph"] == 65

    outside = env.client.get("/api/hazards", params=SAVANNAH, headers=headers).json()
    assert outside["simulated"] is False and outside["level"] == 0

    env.client.post("/api/sim/deactivate", headers=headers)
    assert env.client.get("/api/hazards", params=VENUE, headers=headers).json()["simulated"] is False


def test_region_feed_adds_labeled_scenario_areas(env, quiet_region):
    headers = _volunteer(env)
    env.client.post("/api/sim/activate", json={"scenario_id": SCENARIO}, headers=headers)
    region = env.client.get("/api/hazards/region", headers=headers).json()
    assert region["simulated"] is True
    props = [f["properties"] for f in region["features"]]
    assert props and all(p["source"] == "Simulation" and p["official"] is False and "SIMULATED" in p["event"] for p in props)
    env.client.post("/api/sim/deactivate", headers=headers)
    assert env.client.get("/api/hazards/region", headers=headers).json()["features"] == []


def test_activation_rescores_open_requests_and_deactivation_restores(env):
    rid = _request_at(env, VENUE)
    before = env.raw.requests.find_one()
    assert before["hazard_level"] == 0
    _, headers = env.make_user(Role.helper, "V")

    assert env.client.post("/api/sim/activate", json={"scenario_id": SCENARIO}, headers=headers).json()["rescored"] == 1
    during = env.raw.requests.find_one()
    assert during["hazard_level"] == 3 and during["hazard_snapshot"]["simulated"] is True
    assert during["priority"] > before["priority"]

    env.client.post("/api/sim/deactivate", headers=headers)
    after = env.raw.requests.find_one()
    assert after["hazard_level"] == 0 and after["hazard_snapshot"]["simulated"] is False
    assert str(after["_id"]) == rid


def test_feed_labels_simulated_hazard_levels(env):
    _request_at(env, VENUE)
    headers = _volunteer(env)
    env.client.post("/api/sim/activate", json={"scenario_id": SCENARIO}, headers=headers)
    feed = env.client.get("/api/requests/ranked", headers=headers).json()
    assert feed["simulated"] is True
    need = next(f for f in feed["requests"][0]["breakdown"] if f["key"] == "need")
    hazard = next(p for p in need["detail"] if p["key"] == "hazard")
    assert hazard["raw"] == 3 and hazard["simulated"] is True


def test_requests_created_during_a_scenario_store_a_simulated_snapshot(env):
    _, headers = env.make_user(Role.helper, "V")
    env.client.post("/api/sim/activate", json={"scenario_id": SCENARIO}, headers=headers)
    _request_at(env, VENUE, "Water is coming into the street, need sandbags")
    doc = env.raw.requests.find_one()
    assert doc["hazard_level"] == 3 and doc["hazard_snapshot"]["simulated"] is True


def test_a_leftover_flag_never_applies_outside_demo_mode(env, monkeypatch):
    env.raw.settings.update_one({"_id": "sim"}, {"$set": {"active": True, "scenario_id": SCENARIO}}, upsert=True)
    monkeypatch.setenv("DEMO_LOGIN", "false")
    get_settings.cache_clear()
    _, headers = env.make_user(Role.helper, "V")
    report = env.client.get("/api/hazards", params=VENUE, headers=headers).json()
    assert report["simulated"] is False
    assert "Simulation" not in json.dumps(report)
