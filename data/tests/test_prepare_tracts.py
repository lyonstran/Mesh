"""Pure helpers of prepare_tracts.py (PLAN.md §4). Run from data/: pytest -q"""

import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_tracts import RANK_FIELDS, clean_rank, load_columns, normalize_geoid, polygonal  # noqa: E402


@pytest.mark.parametrize("raw", [-999, -999.0, "-999", None, float("nan"), "", "n/a"])
def test_sentinel_and_missing_ranks_become_none(raw):
    assert clean_rank(raw) is None


@pytest.mark.parametrize("raw, expected", [(0, 0.0), (0.4312, 0.4312), ("0.9", 0.9), (1, 1.0)])
def test_valid_ranks_pass_through(raw, expected):
    assert clean_rank(raw) == expected


def test_rank_above_one_is_an_error_not_silently_kept():
    with pytest.raises(ValueError):
        clean_rank(1.5)


def test_geoid_is_padded_string():
    assert normalize_geoid("13121001100") == "13121001100"
    assert normalize_geoid(1073000100) == "01073000100"
    assert normalize_geoid("1073000100.0") == "01073000100"


def test_column_map_covers_every_rank_field():
    cols = load_columns()
    assert cols["geoid"] and all(cols[f] for f in RANK_FIELDS)


def test_bowtie_polygon_is_repaired_to_polygons():
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])  # self-intersecting
    assert not bowtie.is_valid
    fixed = polygonal(bowtie)
    assert fixed is not None and fixed.is_valid
    assert isinstance(fixed, (Polygon, MultiPolygon))
