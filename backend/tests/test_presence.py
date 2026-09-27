"""Live-location rules that need no database."""

from datetime import UTC, datetime, timedelta

from app.services.presence import MIN_INTERVAL_S, age_seconds, is_throttled

NOW = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)


def test_first_update_is_never_throttled():
    assert is_throttled(None, NOW) is False


def test_updates_closer_than_the_minimum_interval_are_dropped():
    assert is_throttled(NOW - timedelta(seconds=MIN_INTERVAL_S - 1), NOW) is True
    assert is_throttled(NOW - timedelta(seconds=MIN_INTERVAL_S), NOW) is False
    assert is_throttled(NOW - timedelta(minutes=5), NOW) is False


def test_naive_mongo_datetimes_compare_with_aware_ones():
    """pymongo returns naive UTC datetimes by default; comparing them to an aware `now` must not raise."""
    naive = (NOW - timedelta(seconds=30)).replace(tzinfo=None)
    assert age_seconds(naive, NOW) == 30
    assert is_throttled(naive, NOW) is False


def test_age_is_never_negative_when_clocks_disagree():
    assert age_seconds(NOW + timedelta(seconds=3), NOW) == 0


# --- simulated positions for demo accounts ------------------------------------------

def test_simulated_point_stays_within_its_radius_and_moves():
    from app.services.geo import haversine_km
    from app.services.presence import SIM_RADIUS_M, simulated_point

    origin = {"lat": 33.7756, "lon": -84.3963}
    seen = set()
    for seconds in range(0, 120, 5):
        p = simulated_point(origin, NOW + timedelta(seconds=seconds))
        assert haversine_km(origin, p) * 1000 == __import__("pytest").approx(SIM_RADIUS_M, abs=1)
        assert p["age_s"] == 0
        seen.add((round(p["lat"], 6), round(p["lon"], 6)))
    assert len(seen) > 10  # it actually moves between polls


def test_simulated_point_repeats_every_lap_and_is_the_same_for_everyone():
    from app.services.presence import SIM_PERIOD_S, simulated_point

    origin = {"lat": 33.7756, "lon": -84.3963}
    a = simulated_point(origin, NOW)
    b = simulated_point(origin, NOW + timedelta(seconds=SIM_PERIOD_S))
    assert (a["lat"], a["lon"]) == __import__("pytest").approx((b["lat"], b["lon"]), abs=1e-9)
    assert simulated_point(origin, NOW) == simulated_point(origin, NOW)
