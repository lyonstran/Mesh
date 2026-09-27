"""Live location through the real API (needs MONGODB_TEST_URI; skipped otherwise)."""

from app.models import Role

HOME = {"lat": 33.7756, "lon": -84.3963}
HELPER_AT = {"lat": 33.7701, "lon": -84.3899, "accuracy": 12}
REQUESTER_AT = {"lat": 33.7758, "lon": -84.3961, "accuracy": 8}


def _claimed(env):
    """A claimed request: (request id, requester headers, helper headers)."""
    _, req_headers = env.make_user(Role.requester, "Requester")
    rid = env.client.post("/api/requests", json={"text": "tree across my driveway", "location": HOME}, headers=req_headers).json()["request"]["id"]
    helper = env.onboard_helper("Marcus", "chainsaw")
    assert env.client.post(f"/api/requests/{rid}/claim", headers=helper).status_code == 200
    return rid, req_headers, helper


def _point(env, headers, rid):
    return env.client.get(f"/api/requests/{rid}/location", headers=headers).json()["other"]


def test_each_side_sees_only_the_other_persons_point(env):
    rid, req_headers, helper = _claimed(env)
    assert env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper).json() == {"ok": True, "throttled": False}
    assert env.client.post(f"/api/requests/{rid}/location", json=REQUESTER_AT, headers=req_headers).status_code == 200

    seen_by_requester = _point(env, req_headers, rid)
    assert (seen_by_requester["lat"], seen_by_requester["lon"]) == (HELPER_AT["lat"], HELPER_AT["lon"])
    seen_by_helper = _point(env, helper, rid)
    assert (seen_by_helper["lat"], seen_by_helper["lon"]) == (REQUESTER_AT["lat"], REQUESTER_AT["lon"])
    assert "age_s" in seen_by_helper


def test_nobody_else_can_read_or_write_live_location(env):
    rid, _, _ = _claimed(env)
    other_helper = env.onboard_helper("Stranger", "chainsaw")
    _, other_requester = env.make_user(Role.requester, "Other requester")
    for headers in (other_helper, other_requester):
        assert env.client.get(f"/api/requests/{rid}/location", headers=headers).status_code == 403
        assert env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=headers).status_code == 403
        assert env.client.delete(f"/api/requests/{rid}/location", headers=headers).status_code == 403
    assert env.client.get(f"/api/requests/{rid}/location").status_code == 401


def test_sharing_is_only_available_while_claimed(env):
    _, req_headers = env.make_user(Role.requester, "Requester")
    rid = env.client.post("/api/requests", json={"text": "need water", "location": HOME}, headers=req_headers).json()["request"]["id"]
    # OPEN: no volunteer yet, so nothing to share with.
    resp = env.client.post(f"/api/requests/{rid}/location", json=REQUESTER_AT, headers=req_headers)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "NOT_ACTIVE"


def test_updates_arriving_too_fast_are_dropped_not_errors(env):
    rid, _, helper = _claimed(env)
    first = env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper).json()
    second = env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper).json()
    assert first["throttled"] is False and second == {"ok": True, "throttled": True}


def test_pausing_removes_your_point_immediately(env):
    rid, req_headers, helper = _claimed(env)
    env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper)
    assert _point(env, req_headers, rid) is not None
    assert env.client.delete(f"/api/requests/{rid}/location", headers=helper).status_code == 200
    assert _point(env, req_headers, rid) is None


def test_release_resolve_and_cancel_end_sharing(env):
    for ending in ("release", "resolve", "cancel"):
        rid, req_headers, helper = _claimed(env)
        env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper)
        env.client.post(f"/api/requests/{rid}/location", json=REQUESTER_AT, headers=req_headers)
        actor = helper if ending == "release" else req_headers
        assert env.client.post(f"/api/requests/{rid}/{ending}", headers=actor).status_code == 200, ending
        from bson import ObjectId

        assert env.raw.presence.count_documents({"request_id": ObjectId(rid)}) == 0, ending
        # And nobody can keep sending once it has ended.
        assert env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper).status_code in (403, 409)


def test_a_volunteer_can_share_on_two_requests_at_once(env):
    """Presence is keyed by (user, request), not by user alone."""
    helper = env.onboard_helper("Marcus", "chainsaw")
    rids = []
    for name in ("A", "B"):
        _, req_headers = env.make_user(Role.requester, f"Requester {name}")
        rid = env.client.post("/api/requests", json={"text": f"need help {name}", "location": HOME}, headers=req_headers).json()["request"]["id"]
        assert env.client.post(f"/api/requests/{rid}/claim", headers=helper).status_code == 200
        assert env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper).status_code == 200
        rids.append(rid)
    from bson import ObjectId

    assert env.raw.presence.count_documents({"request_id": {"$in": [ObjectId(r) for r in rids]}}) == 2


def test_only_the_latest_point_is_kept_never_a_trail(env):
    rid, _, helper = _claimed(env)
    env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT, headers=helper)
    from bson import ObjectId

    env.raw.presence.update_one({"request_id": ObjectId(rid)}, {"$set": {"updated_at": __import__("datetime").datetime(2020, 1, 1)}})
    env.client.post(f"/api/requests/{rid}/location", json=HELPER_AT | {"lat": 33.78}, headers=helper)
    assert env.raw.presence.count_documents({"request_id": ObjectId(rid)}) == 1


def test_bad_coordinates_are_rejected(env):
    rid, _, helper = _claimed(env)
    for bad in ({"lat": 91, "lon": 0}, {"lat": 0, "lon": 181}, {"lat": "x", "lon": 1}):
        assert env.client.post(f"/api/requests/{rid}/location", json=bad, headers=helper).status_code == 422


# --- demo accounts: a labelled, simulated position when no real one exists ------------

def _claimed_by_real_volunteer(env, *, demo_requester: bool):
    _, req_headers = env.make_user(Role.requester, "Ruth (demo)", **({"demo": True} if demo_requester else {}))
    rid = env.client.post("/api/requests", json={"text": "tree across my driveway", "location": HOME}, headers=req_headers).json()["request"]["id"]
    helper = env.onboard_helper("Marcus", "chainsaw")
    assert env.client.post(f"/api/requests/{rid}/claim", headers=helper).status_code == 200
    return rid, req_headers, helper


def test_a_demo_requester_shows_a_simulated_position_to_the_volunteer(env):
    from app.services.geo import haversine_km
    from app.services.presence import SIM_RADIUS_M

    rid, _, helper = _claimed_by_real_volunteer(env, demo_requester=True)
    body = env.client.get(f"/api/requests/{rid}/location", headers=helper).json()
    assert body["simulated"] is True  # rule 7: always labelled
    assert abs(haversine_km(HOME, body["other"]) * 1000 - SIM_RADIUS_M) < 1
    assert env.raw.presence.count_documents({}) == 0  # never stored as if it were a real device


def test_real_requesters_are_never_simulated(env):
    rid, _, helper = _claimed_by_real_volunteer(env, demo_requester=False)
    body = env.client.get(f"/api/requests/{rid}/location", headers=helper).json()
    assert body == {"other": None, "simulated": False, "stale_after_s": 45}


def test_a_real_shared_location_beats_the_simulation(env):
    rid, req_headers, helper = _claimed_by_real_volunteer(env, demo_requester=True)
    env.client.post(f"/api/requests/{rid}/location", json=REQUESTER_AT, headers=req_headers)
    body = env.client.get(f"/api/requests/{rid}/location", headers=helper).json()
    assert body["simulated"] is False
    assert (body["other"]["lat"], body["other"]["lon"]) == (REQUESTER_AT["lat"], REQUESTER_AT["lon"])


def test_nothing_is_simulated_when_demo_mode_is_off(env, monkeypatch):
    from types import SimpleNamespace

    rid, _, helper = _claimed_by_real_volunteer(env, demo_requester=True)
    monkeypatch.setattr("app.routers.location.get_settings", lambda: SimpleNamespace(demo_login=False))
    assert env.client.get(f"/api/requests/{rid}/location", headers=helper).json()["other"] is None
