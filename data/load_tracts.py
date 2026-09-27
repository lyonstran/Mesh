"""Upsert data/processed/ga_tracts.geojson into the Mongo `tracts` collection (PLAN.md §4).

Uses MONGODB_URI / MONGODB_DB from the repo-root .env (or the environment).

    python load_tracts.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import GEOSPHERE, MongoClient, ReplaceOne
from pymongo.errors import BulkWriteError

HERE = Path(__file__).resolve().parent
SRC = HERE / "processed" / "ga_tracts.geojson"
FIELDS = ("geoid", "name", "eji_rank", "climate_rank", "env_rank", "svm_rank", "hvm_rank")
BATCH = 200


def to_doc(feature: dict) -> dict:
    props = feature["properties"]
    return {"_id": props["geoid"], **{f: props.get(f) for f in FIELDS}, "geometry": feature["geometry"]}


def main() -> int:
    load_dotenv(HERE.parent / ".env")
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise SystemExit("MONGODB_URI is not set (repo-root .env).")
    if not SRC.exists():
        raise SystemExit(f"Missing {SRC}. Run prepare_tracts.py first.")

    features = json.loads(SRC.read_text(encoding="utf-8"))["features"]
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    coll = client[os.environ.get("MONGODB_DB") or "mesh"].tracts
    # Index first so every write is validated by the 2dsphere index (it rejects invalid polygons).
    coll.create_index([("geometry", GEOSPHERE)])

    upserted = modified = 0
    failed: list[tuple[str, str]] = []
    for i in range(0, len(features), BATCH):
        docs = [to_doc(f) for f in features[i : i + BATCH]]
        ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
        try:
            result = coll.bulk_write(ops, ordered=False)
        except BulkWriteError as e:
            result = None
            details = e.details
            upserted += details.get("nUpserted", 0)
            modified += details.get("nMatched", 0)
            for err in details.get("writeErrors", []):
                failed.append((docs[err["index"]]["_id"], err.get("errmsg", "")[:200]))
        if result is not None:
            upserted += result.upserted_count
            modified += result.matched_count

    total = coll.count_documents({})
    with_eji = coll.count_documents({"eji_rank": {"$ne": None}})
    print(f"Upserted {upserted}, replaced {modified}, failed {len(failed)}. "
          f"Collection now has {total} tracts ({with_eji} with an EJI rank).")
    for geoid, msg in failed[:10]:
        print(f"  {geoid}: {msg}")
    client.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
