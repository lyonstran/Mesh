"""Blended volunteer feed (services/matching.py, team plan P1-4). Pure scoring first, then the API (needs MONGODB_TEST_URI)."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from app.db import DEFAULT_WEIGHTS
from app.models import RequestStatus, Role
from app.services import matching
from app.services.geo import destination, to_geojson
from app.services.priority import normalize_weights

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
HOME = {"lat": 33.7756, "lon": -84.3963}
W = normalize_weights(DEFAULT_WEIGHTS)


def _req(km_east: float | None = 1.0, urgency=2, hazard_level=0, eji_rank=0.5, minutes=0, **extra) -> dict:
    doc = {
        "_id": ObjectId(), "requester_id": ObjectId(), "status": RequestStatus.OPEN,
        "urgency": urgency, "hazard_level": hazard_level, "eji_rank": eji_rank,
        "created_at": NOW - timedelta(minutes=minutes),
    } | extra
    if km_east is not None:
        lat, lon = destination(HOME["lat"], HOME["lon"], 90, km_east * 1000)
        doc["display_location"] = to_geojson(lat, lon)
    return doc


def _helper(radius_km=10, home=HOME) -> dict:
    return {"_id": ObjectId(), "helper": {"radius_km": radius_km}, "home_location": to_geojson(home["lat"], home["lon"]) if home else None}


def _score(req, similarity=0.8, home=HOME, radius=10):
    return matching.score_request(req, similarity, home, radius, NOW, W)


# --- pure scoring -------------------------------------------------------------------

def test_blend_is_045_fit_020_proximity_035_need():
    scored = _score(_req(km_east=2.5, urgency=5, hazard_level=3, eji_rank=1.0, minutes=60), similarity=0.9)
    by = {f["key"]: f for f in scored["breakdown"]}
    assert by["fit"]["value"] == pytest.approx(0.8)  # (1 + cos)/2 = 0.9 -> cos 0.8
    assert by["proximity"]["value"] == pytest.approx(0.75, abs=0.01)  # 2.5 of 10 km
    assert by["need"]["value"] == pytest.approx(1.0)
    assert scored["match_score"] == pytest.approx(0.45 * 0.8 + 0.20 * 0.75 + 0.35 * 1.0, abs=0.01)
    assert sum(f["weight"] for f in scored["breakdown"]) == pytest.approx(1.0)


def test_outside_radius_is_filtered_and_radius_caps_at_15():
    assert _score(_req(km_east=11), radius=10) is None
    assert _score(_req(km_east=9), radius=10) is not None
    assert matching.effective_radius_km(_helper(radius_km=40)) == 15


def test_distance_is_rounded_and_from_the_fuzzed_point():
    scored = _score(_req(km_east=3.14159))
    assert scored["distance_km"] == 3.1


@pytest.mark.parametrize(
    "req, similarity, home, key, flag",
    [
        (_req(), None, HOME, "fit", "no_embedding"),
        (_req(), 0.8, None, "proximity", "no_home_location"),
        (_req(km_east=None), 0.8, HOME, "proximity", "no_request_location"),
    ],
)
def test_missing_inputs_are_neutral_and_flagged(req, similarity, home, key, flag):
    scored = _score(req, similarity=similarity, home=home)
    factor = next(f for f in scored["breakdown"] if f["key"] == key)
    assert factor["value"] == 0.5 and factor["flag"] == flag
    assert all(f["flag"] is None for f in scored["breakdown"] if f["key"] != key)


def test_anti_correlated_fit_counts_as_zero_not_negative():
    assert matching.fit_value(0.2) == 0.0 and matching.fit_value(1.0) == 1.0


def test_wait_time_raises_need_at_read_time():
    fresh = _score(_req(minutes=0))["breakdown"][2]["value"]
    waiting = _score(_req(minutes=45))["breakdown"][2]["value"]
    assert waiting > fresh


def test_need_detail_shows_an_eji_band_never_the_rank():
    scored = _score(_req(eji_rank=0.8731))
    detail = next(f for f in scored["breakdown"] if f["key"] == "need")["detail"]
    eji = next(d for d in detail if d["key"] == "eji")
    assert eji["band"] == "Very high" and "raw" not in eji and "contribution" not in eji
    assert "0.8731" not in json.dumps(scored)


@pytest.mark.parametrize("rank, band", [(None, "Unknown"), (0.1, "Lower"), (0.45, "Moderate"), (0.65, "High"), (0.95, "Very high")])
def test_eji_bands(rank, band):
    assert matching.eji_band(rank) == band


def test_rank_orders_by_blend_and_drops_own_requests():
    helper = _helper()
    urgent_far = _req(km_east=8, urgency=5, hazard_level=3, eji_rank=0.9)
    calm_near = _req(km_east=0.5, urgency=1)
    own = _req(km_east=0.5, urgency=5, requester_id=helper["_id"])
    ranked = matching.rank([(calm_near, 0.6), (urgent_far, 0.6), (own, 0.9)], helper, NOW, W)
    assert [r["_id"] for r, _, _ in ranked] == [urgent_far["_id"], calm_near["_id"]]


def test_legacy_request_without_triage_fields_still_scores():
    legacy = {"_id": ObjectId(), "requester_id": ObjectId(), "status": RequestStatus.OPEN, "created_at": NOW}
    assert _score(legacy)["breakdown"][2]["detail"][0]["raw"] == 1


# --- API (needs MONGODB_TEST_URI) ---------------------------------------------------

def _post(env, text, location):
    _, headers = env.make_user(Role.requester, "Requester")
    body = {"text": text} | ({"location": location} if location else {})
    resp = env.client.post("/api/requests", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["request"]


def _volunteer(env, radius_km=10, home=HOME, about="chainsaw, generator, water"):
    headers = env.onboard_helper("Vol", about)
    fields = {"helper": {"skills": [], "custom_skills": [], "resources": [], "about": about, "radius_km": radius_km}}
    if home:
        fields["home_location"] = home
    assert env.client.patch("/api/me", json=fields, headers=headers).status_code == 200
    return headers


def _at(km_east):
    lat, lon = destination(HOME["lat"], HOME["lon"], 90, km_east * 1000)
    return {"lat": lat, "lon": lon}


def test_feed_filters_by_radius_and_returns_distance_and_breakdown(env):
    near = _post(env, "Need drinking water", _at(2))
    _post(env, "Need drinking water too", _at(14))
    headers = _volunteer(env, radius_km=5)
    body = env.client.get("/api/requests/ranked", headers=headers).json()
    assert [r["id"] for r in body["requests"]] == [near["id"]]
    seen = body["requests"][0]
    assert 1.4 <= seen["distance_km"] <= 2.6  # 2 km, give or take the 300-500 m fuzz
    assert {f["key"] for f in seen["breakdown"]} == {"fit", "proximity", "need"}
    assert body["radius_km"] == 5 and body["home_set"] is True
    assert body["weights_note"] == "Weights are designed defaults, not fitted."


def test_feed_never_sends_tract_or_raw_eji(env):
    env.raw.tracts.create_index([("geometry", "2dsphere")])
    env.raw.tracts.insert_one({
        "_id": "13121000000", "geoid": "13121000000", "eji_rank": 0.7234,
        "geometry": {"type": "Polygon", "coordinates": [[[-84.42, 33.76], [-84.37, 33.76], [-84.37, 33.79], [-84.42, 33.79], [-84.42, 33.76]]]},
    })
    _post(env, "Need drinking water", HOME)
    blob = json.dumps(env.client.get("/api/requests/ranked", headers=_volunteer(env)).json())
    assert "13121000000" not in blob and "0.7234" not in blob and "tract_geoid" not in blob and "eji_rank" not in blob
    assert '"band": "High"' in blob


def test_more_urgent_request_ranks_first_all_else_equal(env):
    calm = _post(env, "Could use some drinking water this week", _at(3))
    urgent = _post(env, "Need drinking water, my baby is here", _at(3))  # "baby" sets the floor to 4
    ids = [r["id"] for r in env.client.get("/api/requests/ranked", headers=_volunteer(env)).json()["requests"]]
    assert ids.index(urgent["id"]) < ids.index(calm["id"])


def test_no_home_location_still_lists_everything_with_a_flag(env):
    _post(env, "Need drinking water", _at(40))
    body = env.client.get("/api/requests/ranked", headers=_volunteer(env, home=None)).json()
    assert len(body["requests"]) == 1 and body["home_set"] is False
    prox = next(f for f in body["requests"][0]["breakdown"] if f["key"] == "proximity")
    assert prox["flag"] == "no_home_location" and body["requests"][0]["distance_km"] is None


def test_claim_cap_is_two_and_the_feed_says_so(env):
    ids = [_post(env, f"Need drinking water {i}", _at(1))["id"] for i in range(3)]
    headers = _volunteer(env)
    for rid in ids[:2]:
        assert env.client.post(f"/api/requests/{rid}/claim", headers=headers).status_code == 200
    third = env.client.post(f"/api/requests/{ids[2]}/claim", headers=headers)
    assert third.status_code == 409 and third.json()["error"]["code"] == "CLAIM_LIMIT"
    assert env.raw.requests.find_one({"_id": ObjectId(ids[2])})["status"] == RequestStatus.OPEN
    feed = env.client.get("/api/requests/ranked", headers=headers).json()
    assert feed["claim_limit_reached"] is True and feed["requests"] == [] and feed["active_claims"] == 2

    # Releasing one frees a slot.
    assert env.client.post(f"/api/requests/{ids[0]}/release", headers=headers).status_code == 200
    assert env.client.post(f"/api/requests/{ids[2]}/claim", headers=headers).status_code == 200


def test_racing_claims_never_exceed_the_cap(env):
    ids = [_post(env, f"Need drinking water {i}", _at(1))["id"] for i in range(5)]
    headers = _volunteer(env)
    with ThreadPoolExecutor(max_workers=5) as pool:
        codes = list(pool.map(lambda rid: env.client.post(f"/api/requests/{rid}/claim", headers=headers).status_code, ids))
    held = env.raw.requests.count_documents({"status": RequestStatus.CLAIMED})
    assert held <= 2 and codes.count(200) == held
    assert all(c in (200, 409) for c in codes)
    # Rolled-back claims leave clean OPEN requests.
    for doc in env.raw.requests.find({"status": RequestStatus.OPEN}):
        assert doc["helper_id"] is None and "claimed_at" not in doc and doc["timeline"][-1]["status"] == RequestStatus.OPEN


def test_priority_is_restored_on_status_change(env):
    rid = _post(env, "Need drinking water", _at(1))["id"]
    headers = _volunteer(env)
    env.raw.requests.update_one({"_id": ObjectId(rid)}, {"$set": {"priority": -1}})
    env.client.post(f"/api/requests/{rid}/claim", headers=headers)
    assert env.raw.requests.find_one({"_id": ObjectId(rid)})["priority"] >= 0
