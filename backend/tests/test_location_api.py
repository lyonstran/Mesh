"""Location through the real API (needs MONGODB_TEST_URI; skipped otherwise)."""

import json

from app.models import Role
from app.services.geo import haversine_km

HOME = {"lat": 33.7756, "lon": -84.3963}


def _create(env, location=HOME, text="A tree fell across my driveway, need chainsaw help"):
    _, headers = env.make_user(Role.requester, "Requester")
    body = {"text": text} | ({"location": location} if location else {})
    resp = env.client.post("/api/requests", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["request"], headers


def test_create_with_location_returns_exact_and_fuzzed_to_the_requester(env):
    req, _ = _create(env)
    assert req["location"] == HOME
    assert 300 - 1 <= haversine_km(HOME, req["display_location"]) * 1000 <= 500 + 1


def test_create_without_location_still_works(env):
    req, _ = _create(env, location=None)
    assert "location" not in req and "display_location" not in req


def test_other_volunteers_never_receive_the_exact_location(env):
    req, _ = _create(env)
    other = env.onboard_helper("Marcus", "chainsaw")
    for url in (f"/api/requests/{req['id']}", "/api/requests/ranked"):
        blob = json.dumps(env.client.get(url, headers=other).json())
        assert '"location"' not in blob
        assert str(HOME["lat"]) not in blob and str(HOME["lon"]) not in blob
        assert '"display_location"' in blob


def test_assigned_volunteer_gets_the_exact_location_only_while_claimed(env):
    req, req_headers = _create(env)
    helper = env.onboard_helper("Marcus", "chainsaw")
    claimed = env.client.post(f"/api/requests/{req['id']}/claim", headers=helper).json()["request"]
    assert claimed["location"] == HOME
    env.client.post(f"/api/requests/{req['id']}/release", headers=helper)
    after = env.client.get(f"/api/requests/{req['id']}", headers=helper).json()["request"]
    assert "location" not in after


def test_home_location_and_radius_round_trip(env):
    _, headers = env.make_user(Role.helper, "Helper", helper={"skills": [], "custom_skills": [], "resources": [], "about": "x"})
    resp = env.client.patch(
        "/api/me", json={"home_location": HOME, "helper": {"about": "x", "radius_km": 7}}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["home_location"] == HOME and user["helper"]["radius_km"] == 7
    # Stored as GeoJSON [lon, lat].
    stored = env.raw.users.find_one({"email": user["email"]})
    assert stored["home_location"]["coordinates"] == [HOME["lon"], HOME["lat"]]
    cleared = env.client.patch("/api/me", json={"home_location": None}, headers=headers).json()["user"]
    assert cleared["home_location"] is None


def test_radius_is_capped_at_15_km(env):
    _, headers = env.make_user(Role.helper, "Helper", helper={"skills": [], "custom_skills": [], "resources": [], "about": "x"})
    resp = env.client.patch("/api/me", json={"helper": {"about": "x", "radius_km": 40}}, headers=headers)
    assert resp.status_code == 422


def test_geocode_requires_login_and_reports_outages_without_a_500(env, monkeypatch):
    assert env.client.get("/api/geocode", params={"q": "225 North Ave NW"}).status_code == 401
    _, headers = env.make_user(Role.requester, "Requester")

    async def down(_query):
        from app.services.geocode import GeocoderUnavailable

        raise GeocoderUnavailable

    monkeypatch.setattr("app.routers.geocode.geocode", down)
    resp = env.client.get("/api/geocode", params={"q": "225 North Ave NW"}, headers=headers)
    assert resp.status_code == 502 and resp.json()["error"]["code"] == "GEOCODER_UNAVAILABLE"

    async def found(_query):
        return [{"label": "225 North Ave Nw", "lat": 33.77, "lon": -84.39}]

    monkeypatch.setattr("app.routers.geocode.geocode", found)
    assert env.client.get("/api/geocode", params={"q": "225 North Ave NW"}, headers=headers).json()["matches"][0]["lat"] == 33.77


def _volunteer(env, name, home, **helper_extra):
    from app.services.geo import to_geojson

    helper = {"skills": [], "custom_skills": [], "resources": [], "about": "x", "radius_km": 10} | helper_extra
    return env.make_user(Role.helper, name, helper=helper, home_location=to_geojson(home["lat"], home["lon"]))


def test_requesters_see_only_fuzzed_volunteer_areas(env):
    volunteer, _ = _volunteer(env, "Marcus Volunteer", HOME)
    _, req_headers = env.make_user(Role.requester, "Requester")
    resp = env.client.get("/api/volunteers/nearby", params=HOME, headers=req_headers)
    assert resp.status_code == 200, resp.text
    (shown,) = resp.json()["volunteers"]
    assert set(shown) == {"display_location"}  # no id, name, skills, or exact point
    assert 300 - 1 <= haversine_km(HOME, shown["display_location"]) * 1000 <= 500 + 1
    blob = json.dumps(resp.json())
    assert "Marcus" not in blob and str(volunteer["_id"]) not in blob
    # Stable between calls.
    again = env.client.get("/api/volunteers/nearby", params=HOME, headers=req_headers).json()["volunteers"]
    assert again == [shown]


def test_volunteers_can_opt_out_and_far_ones_are_not_listed(env):
    _volunteer(env, "Hidden", HOME, show_area_to_requesters=False)
    _volunteer(env, "Far away", {"lat": 34.9, "lon": -85.5})  # roughly 150 km off
    _, req_headers = env.make_user(Role.requester, "Requester")
    assert env.client.get("/api/volunteers/nearby", params=HOME, headers=req_headers).json()["volunteers"] == []


def test_only_requesters_can_list_nearby_volunteers(env):
    _, helper_headers = _volunteer(env, "Helper only", HOME)
    assert env.client.get("/api/volunteers/nearby", params=HOME, headers=helper_headers).status_code == 403
    assert env.client.get("/api/volunteers/nearby", params=HOME).status_code == 401


def test_a_dual_user_never_sees_their_own_area_as_a_nearby_volunteer(env):
    from app.services.geo import to_geojson

    _, headers = env.make_user(
        Role.requester, "Dana", roles=["requester", "helper"], home_location=to_geojson(HOME["lat"], HOME["lon"]),
        helper={"skills": [], "custom_skills": [], "resources": [], "about": "x"},
    )
    assert env.client.get("/api/volunteers/nearby", params=HOME, headers=headers).json()["volunteers"] == []
