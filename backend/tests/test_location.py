"""Location, fuzzing, privacy, and geocoder parsing (PLAN.md Iteration 2). No database needed."""

import json
from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.models import GeoPoint, HelperProfile, ProfileUpdate, RequestCreate
from app.models import RequestStatus as S
from app.services.fuzz import MAX_OFFSET_M, MIN_OFFSET_M, fuzz_point
from app.services.geo import destination, from_geojson, haversine_km, to_geojson
from app.services.geocode import parse_census
from app.services.serialize import public_user, serialize_request
from app.services.volunteers import shares_area

VENUE = {"lat": 33.7756, "lon": -84.3963}
SECRET = "test-secret"


# --- coordinates -----------------------------------------------------------------

def test_geojson_is_lon_lat_and_round_trips():
    point = to_geojson(33.7756, -84.3963)
    assert point == {"type": "Point", "coordinates": [-84.3963, 33.7756]}  # [lon, lat], never [lat, lon]
    assert from_geojson(point) == VENUE
    assert from_geojson(None) is None
    assert from_geojson({"type": "Point", "coordinates": []}) is None


def test_destination_and_haversine_agree():
    lat, lon = destination(VENUE["lat"], VENUE["lon"], 90, 1000)
    assert haversine_km(VENUE, {"lat": lat, "lon": lon}) == pytest.approx(1.0, abs=0.005)
    assert lon > VENUE["lon"]  # due east moves toward larger longitude


def test_geopoint_rejects_out_of_range_and_swapped_values():
    with pytest.raises(ValidationError):
        GeoPoint(lat=91, lon=0)
    with pytest.raises(ValidationError):
        GeoPoint(lat=33.7, lon=-184.0)
    # The classic mix-up: a lon/lat pair sent as lat/lon puts "lat" at -84 (valid) but "lon" at 33; the API can't
    # catch that, which is why storage helpers are the only place [lon, lat] is built.
    assert GeoPoint(lat=-84.39, lon=33.77).lat == -84.39


def test_helper_radius_defaults_and_is_capped():
    assert HelperProfile().radius_km == 10
    assert HelperProfile(radius_km=15).radius_km == 15
    for bad in (0, 0.5, 16, 100):
        with pytest.raises(ValidationError):
            HelperProfile(radius_km=bad)


def test_models_accept_optional_locations():
    assert RequestCreate(text="need help").location is None
    assert RequestCreate(text="need help", location={"lat": 33.7, "lon": -84.4}).location.lat == 33.7
    assert ProfileUpdate(home_location=None).model_dump(exclude_unset=True) == {"home_location": None}


# --- fuzzing ----------------------------------------------------------------------

def test_fuzz_is_300_to_500_metres_away():
    for i in range(200):
        lat, lon = fuzz_point(VENUE["lat"], VENUE["lon"], str(ObjectId()), SECRET)
        metres = haversine_km(VENUE, {"lat": lat, "lon": lon}) * 1000
        assert MIN_OFFSET_M - 1 <= metres <= MAX_OFFSET_M + 1, (i, metres)


def test_fuzz_is_deterministic_per_request_and_varies_between_requests():
    a, b = str(ObjectId()), str(ObjectId())
    assert fuzz_point(33.7, -84.4, a, SECRET) == fuzz_point(33.7, -84.4, a, SECRET)
    assert fuzz_point(33.7, -84.4, a, SECRET) != fuzz_point(33.7, -84.4, b, SECRET)


def test_fuzz_depends_on_the_server_secret():
    """The request id is public. If the offset were seeded by it alone, anyone could replay the generator."""
    rid = str(ObjectId())
    assert fuzz_point(33.7, -84.4, rid, "secret-a") != fuzz_point(33.7, -84.4, rid, "secret-b")


# --- serializer: one test per viewer (CLAUDE.md rule 5) --------------------------------

EXACT = {"lat": 33.777777, "lon": -84.391111}
REQUESTER = {"_id": ObjectId(), "name": "Ruth", "language": "en", "background": "", "requester_flags": {}}
HELPER = {"_id": ObjectId(), "name": "Janelle"}
OTHER = {"_id": ObjectId(), "name": "Marcus"}
NOW = datetime.now(UTC)


def _req(status=S.CLAIMED):
    rid = ObjectId()
    lat, lon = fuzz_point(EXACT["lat"], EXACT["lon"], str(rid), SECRET)
    return {
        "_id": rid, "requester_id": REQUESTER["_id"], "helper_id": HELPER["_id"] if status != S.OPEN else None,
        "text": "Need power", "status": status, "language": "en", "emergency": False,
        "location": to_geojson(EXACT["lat"], EXACT["lon"]), "display_location": to_geojson(lat, lon),
        "created_at": NOW, "updated_at": NOW, "timeline": [{"status": status, "at": NOW, "by": HELPER["_id"]}],
    }


def _ser(req, viewer):
    return serialize_request(req, viewer, requester=REQUESTER, helper=HELPER)


def test_requester_sees_exact_and_display_location():
    out = _ser(_req(), REQUESTER)
    assert out["location"] == EXACT
    assert "display_location" in out


def test_assigned_volunteer_sees_exact_location():
    out = _ser(_req(), HELPER)
    assert out["viewer_relation"] == "assigned_helper"
    assert out["location"] == EXACT


def test_other_volunteers_see_only_the_fuzzed_location():
    out = _ser(_req(S.OPEN), OTHER)
    assert "location" not in out
    assert out["display_location"] != EXACT
    assert haversine_km(EXACT, out["display_location"]) * 1000 >= MIN_OFFSET_M - 1
    # The exact coordinates must not appear anywhere in the payload, in any form.
    blob = json.dumps(out)
    assert str(EXACT["lat"]) not in blob and str(EXACT["lon"]) not in blob


def test_volunteer_loses_the_exact_location_after_cancel_or_release():
    for status in (S.CANCELLED, S.OPEN):
        req = _req(status) | {"helper_id": HELPER["_id"]}
        out = _ser(req, HELPER)
        assert out["viewer_relation"] == "other"
        assert "location" not in out


def test_requests_without_a_location_still_serialize():
    req = _req() | {"location": None, "display_location": None}
    for viewer in (REQUESTER, HELPER, OTHER):
        out = _ser(req, viewer)
        assert "location" not in out and "display_location" not in out


def test_public_user_returns_home_location_as_lat_lon():
    user = {"_id": ObjectId(), "role": "helper", "home_location": to_geojson(33.7, -84.4)}
    assert public_user(user)["home_location"] == {"lat": 33.7, "lon": -84.4}
    assert public_user({"_id": ObjectId(), "role": "helper"})["home_location"] is None


# --- geocoder parsing (shape verified against a live Census response) -----------------

CENSUS_MATCH = {
    "result": {
        "input": {"address": {"address": "225 North Ave NW, Atlanta, GA 30332"}},
        "addressMatches": [
            {
                "tigerLine": {"side": "R", "tigerLineId": "640546382"},
                "coordinates": {"x": -84.39427987228, "y": 33.771377284052},
                "matchedAddress": "225 NORTH AVE NW, ATLANTA, GA, 30332",
            }
        ],
    }
}


def test_parse_census_maps_x_to_lon_and_y_to_lat():
    (match,) = parse_census(CENSUS_MATCH)
    assert match["lat"] == pytest.approx(33.771377, abs=1e-5)
    assert match["lon"] == pytest.approx(-84.394280, abs=1e-5)
    assert match["label"] == "225 North Ave Nw, Atlanta, Ga, 30332"


def test_parse_census_handles_no_match_and_odd_payloads():
    assert parse_census({"result": {"addressMatches": []}}) == []
    assert parse_census({}) == []
    assert parse_census({"result": {"addressMatches": [{"matchedAddress": "x"}]}}) == []


# --- volunteers shown to requesters ---------------------------------------------------

def test_volunteers_share_their_area_unless_they_opt_out():
    assert shares_area({}) is True  # accounts created before the setting existed
    assert shares_area({"helper": {}}) is True
    assert shares_area({"helper": {"show_area_to_requesters": True}}) is True
    assert shares_area({"helper": {"show_area_to_requesters": False}}) is False


def test_volunteer_fuzz_is_stable_and_keyed_differently_from_requests():
    same_id = str(ObjectId())
    a = fuzz_point(33.7, -84.4, f"volunteer:{same_id}", SECRET)
    assert a == fuzz_point(33.7, -84.4, f"volunteer:{same_id}", SECRET)  # stable between calls, so no averaging attack
    assert a != fuzz_point(33.7, -84.4, same_id, SECRET)  # a request and a volunteer never share an offset


# --- saving a home location (no database: a stub records what would be stored) ----------

def _save_with_stub(user, body):
    import asyncio

    from fastapi import BackgroundTasks

    from app.routers.users import _save_profile

    captured = {}

    class Users:
        async def find_one_and_update(self, flt, update, return_document=None):
            captured["set"] = update["$set"]
            return {**user, **update["$set"]}

    class DB:
        users = Users()

    fields = ProfileUpdate.model_validate(body).model_dump(mode="json", exclude_unset=True)
    updated, _ = asyncio.run(_save_profile(DB(), user, fields, BackgroundTasks()))
    return captured["set"], updated


def test_patching_home_location_stores_geojson_and_reads_back_as_lat_lon():
    user = {"_id": ObjectId(), "role": "requester", "roles": ["requester"]}
    stored, updated = _save_with_stub(user, {"home_location": {"lat": 33.7756, "lon": -84.3963}})
    assert stored["home_location"] == {"type": "Point", "coordinates": [-84.3963, 33.7756]}
    assert public_user(updated)["home_location"] == VENUE


def test_clearing_home_location_stores_null():
    user = {"_id": ObjectId(), "role": "requester", "roles": ["requester"], "home_location": to_geojson(33.7, -84.4)}
    stored, updated = _save_with_stub(user, {"home_location": None})
    assert stored["home_location"] is None
    assert public_user(updated)["home_location"] is None


def test_saving_only_a_profile_section_leaves_the_home_location_alone():
    home = to_geojson(33.7, -84.4)
    user = {"_id": ObjectId(), "role": "requester", "roles": ["requester"], "home_location": home}
    stored, _ = _save_with_stub(user, {"requester_flags": {"mobility": True}})
    assert "home_location" not in stored
