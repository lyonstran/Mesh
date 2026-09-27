"""Join Georgia TIGER/Line 2020 tracts to CDC/ATSDR EJI 2024 ranks (PLAN.md §4).

Reads data/raw/<EJI csv> and data/raw/tl_2020_13_tract.zip, writes data/processed/ga_tracts.geojson.
Column names come from eji_columns.yaml (verified against the EJI 2024 data dictionary).

    python prepare_tracts.py [--eji path/to/eji.csv]
"""

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "processed" / "ga_tracts.geojson"
TIGER_ZIP = RAW / "tl_2020_13_tract.zip"
GA_FIPS = "13"
MIN_MATCH_RATE = 0.99
RANK_FIELDS = ("eji_rank", "climate_rank", "env_rank", "svm_rank", "hvm_rank")
SIMPLIFY_TOLERANCE = 0.0001  # degrees, about 10 m


def load_columns(path: Path = HERE / "eji_columns.yaml") -> dict[str, str]:
    cols = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = [f for f in ("geoid", *RANK_FIELDS) if not cols.get(f)]
    if missing:
        raise SystemExit(f"eji_columns.yaml has no column for: {', '.join(missing)}")
    return cols


def clean_rank(value) -> float | None:
    """EJI rank -> float in [0, 1], or None for missing values and the -999 "no data" sentinel."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or v < 0:  # EJI uses -999 for "no data"; ranks are never negative
        return None
    if v > 1:
        raise ValueError(f"EJI rank out of range: {v}")
    return v


def normalize_geoid(value) -> str:
    """Tract FIPS as an 11-character string. CSV readers can drop the leading zero of some states."""
    return str(value).strip().split(".")[0].zfill(11)


def find_eji_csv() -> Path:
    candidates = [p for p in RAW.glob("*.csv") if "DICTIONARY" not in p.name.upper()]
    if len(candidates) != 1:
        found = ", ".join(p.name for p in candidates) or "none"
        raise SystemExit(f"Expected exactly one EJI CSV in {RAW} (found: {found}). Pass --eji PATH.")
    return candidates[0]


def read_eji(path: Path, cols: dict[str, str]) -> pd.DataFrame:
    geoid_col = cols["geoid"]
    df = pd.read_csv(path, dtype={geoid_col: str}, encoding_errors="replace")
    absent = [c for c in (geoid_col, *(cols[f] for f in RANK_FIELDS)) if c not in df.columns]
    if absent:
        raise SystemExit(f"EJI CSV is missing columns {absent}; check eji_columns.yaml against the data dictionary.")
    out = pd.DataFrame({"geoid": df[geoid_col].map(normalize_geoid)})
    for field in RANK_FIELDS:
        out[field] = df[cols[field]].map(clean_rank)
    out = out[out["geoid"].str.startswith(GA_FIPS)]
    dupes = out["geoid"].duplicated()
    if dupes.any():
        raise SystemExit(f"EJI CSV has duplicate GEOIDs, e.g. {out.loc[dupes, 'geoid'].head(5).tolist()}")
    return out


def polygonal(geom):
    """Valid Polygon/MultiPolygon, or None. make_valid can return collections with stray lines/points."""
    from shapely import get_parts, make_valid
    from shapely.geometry import MultiPolygon, Polygon

    geom = make_valid(geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True))
    polys = []
    for part in get_parts(geom):
        if isinstance(part, Polygon):
            polys.append(part)
        elif isinstance(part, MultiPolygon):
            polys.extend(part.geoms)
    polys = [p for p in polys if not p.is_empty and p.area > 0]
    if not polys:
        return None
    return polys[0] if len(polys) == 1 else MultiPolygon(polys)


def main() -> int:
    import geopandas as gpd
    from shapely.geometry import mapping

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--eji", type=Path, help="EJI 2024 CSV (defaults to the only non-dictionary CSV in data/raw)")
    args = parser.parse_args()

    cols = load_columns()
    eji_path = args.eji or find_eji_csv()
    if not TIGER_ZIP.exists():
        raise SystemExit(f"Missing {TIGER_ZIP}. Download tl_2020_13_tract.zip from Census TIGER/Line 2020.")

    eji = read_eji(eji_path, cols)
    tracts = gpd.read_file(f"zip://{TIGER_ZIP}").to_crs(epsg=4326)
    tracts = tracts[tracts["GEOID"].str.startswith(GA_FIPS)][["GEOID", "NAMELSAD", "ALAND", "geometry"]]
    print(f"EJI rows (Georgia): {len(eji)} from {eji_path.name}")
    print(f"TIGER tracts:       {len(tracts)}")

    merged = tracts.merge(eji, left_on="GEOID", right_on="geoid", how="left", indicator=True)
    matched = merged["_merge"] == "both"
    tract_rate = matched.mean()
    eji_unmatched = sorted(set(eji["geoid"]) - set(tracts["GEOID"]))
    eji_rate = 1 - len(eji_unmatched) / len(eji) if len(eji) else 0.0
    print(f"Match rate: {tract_rate:.2%} of tracts have EJI; {eji_rate:.2%} of EJI rows have a tract")

    unmatched = merged.loc[~matched]
    if len(unmatched):
        land = unmatched["ALAND"].eq(0).sum()
        print(f"  {len(unmatched)} tracts without EJI ({land} water-only), kept with null ranks: "
              f"{unmatched['GEOID'].head(10).tolist()}")
    if eji_unmatched:
        print(f"  EJI GEOIDs with no tract: {eji_unmatched[:10]}")
    if min(tract_rate, eji_rate) < MIN_MATCH_RATE:
        print(f"FAIL: match rate below {MIN_MATCH_RATE:.0%}. Check the tract vintage (EJI 2024 uses 2020 tracts).")
        return 1

    nulls = {f: int(merged.loc[matched, f].isna().sum()) for f in RANK_FIELDS}
    print(f"Null ranks among matched tracts (sentinel or missing): {nulls}")

    features, dropped = [], []
    for row in merged.itertuples(index=False):
        geom = polygonal(row.geometry)
        if geom is None:
            dropped.append(row.GEOID)
            continue
        props = {"geoid": row.GEOID, "name": row.NAMELSAD}
        props |= {f: (None if pd.isna(getattr(row, f)) else float(getattr(row, f))) for f in RANK_FIELDS}
        features.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})
    if dropped:
        print(f"Dropped {len(dropped)} tracts with no polygon after cleanup: {dropped[:10]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    print(f"Wrote {len(features)} tracts to {OUT.relative_to(HERE)} ({OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
