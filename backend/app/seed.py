"""Demo data for the MVP: `python -m app.seed --reset` (PLAN.md §15, adapted for §0.1).

Only touches documents flagged demo: true. Everyone here is fictional.
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app import db
from app.config import get_settings
from app.models import RequestStatus, Role
from app.services.embeddings import embed_for_matching
from app.services.fuzz import fuzz_point
from app.services.geo import destination, to_geojson
from app.services.profile import helper_embedding_fields
from app.services.rules import is_emergency

HELPERS = [
    {
        "name": "Marcus (demo)",
        "background": "Landscaper in Midtown for ten years.",
        "helper": {
            "skills": ["chainsaw", "heavy_lifting", "driving"],
            "resources": ["truck"],
            "about": "I have a chainsaw and a pickup truck. Happy to cut up fallen trees and haul away debris.",
        },
    },
    {
        "name": "Priya (demo)",
        "background": "Registered nurse at a local clinic.",
        "helper": {
            "skills": ["nursing", "first_aid", "cpr", "elder_care"],
            "resources": ["medical_kit"],
            "about": "Can do welfare checks on elderly neighbors, basic wound care, and help with medications or medical devices.",
        },
    },
    {
        "name": "Diego (demo)",
        "language": "es",
        "background": "Bilingual, drive for a delivery company.",
        "helper": {
            "skills": ["spanish", "driving"],
            "resources": ["vehicle", "water", "food"],
            "about": "Hablo español. I have a minivan and can drive people to shelters or bring groceries, water, and prescriptions.",
        },
    },
    {
        "name": "Janelle (demo)",
        "background": "Electrician's apprentice.",
        "helper": {
            "skills": ["electrical_safe"],
            "resources": ["generator", "power_bank"],
            "about": "I own a portable generator and several power banks. Can bring power for phones, fridges, or medical equipment.",
        },
    },
]

REQUESTERS = [
    ("Alex (demo)", "en", {}, "A tree fell across my driveway and I can't get my car out."),
    ("Ruth (demo)", "en", {"medical_device": True}, "My oxygen concentrator needs power. The electricity has been out since last night."),
    ("Rosa (demo)", "es", {"mobility": True}, "Necesito que alguien me lleve al refugio, no tengo carro."),
    ("Sam (demo)", "en", {}, "My elderly neighbor lives alone and hasn't answered her door since the storm. Can someone check on her?"),
    ("Tanya (demo)", "en", {}, "We're running low on drinking water and food for two kids."),
    ("Jordan (demo)", "en", {}, "Big branches and debris are blocking the road in front of my house."),
    ("Casey (demo)", "en", {}, None),  # no request yet: use this account to try submitting one
]


# Demo locations are offsets (bearing in degrees, distance in km) from the HackGT venue in PLAN.md §0, not real
# addresses. Every seeded user and request is flagged demo: true.
VENUE = (33.7756, -84.3963)
PLACES = [(20, 0.4), (95, 1.2), (170, 0.9), (250, 1.6), (320, 1.1), (60, 2.3), (140, 2.6), (210, 2.0), (285, 2.8), (350, 3.0),
          (40, 0.9), (115, 1.9), (190, 1.4), (265, 0.7), (330, 2.2), (75, 3.4), (155, 3.2), (230, 3.6), (300, 0.5), (10, 1.7)]


def place(i: int) -> dict:
    """GeoJSON Point for the i-th demo place."""
    bearing, km = PLACES[i % len(PLACES)]
    lat, lon = destination(VENUE[0], VENUE[1], bearing, km * 1000)
    return to_geojson(lat, lon)


async def reset(database) -> None:
    demo_requests = await database.requests.find({"demo": True}, {"_id": 1}).to_list()
    await database.messages.delete_many({"request_id": {"$in": [r["_id"] for r in demo_requests]}})
    await database.requests.delete_many({"demo": True})
    await database.users.delete_many({"demo": True})


async def seed(database) -> None:
    now = datetime.now(UTC)
    n = 0

    for spec in HELPERS:
        n += 1
        user = {
            "google_sub": f"demo-{n}",
            "email": f"demo-{n}@example.com",
            "name": spec["name"],
            "role": Role.helper,
            "roles": [Role.helper],
            "language": spec.get("language", "en"),
            "background": spec["background"],
            "home_location": place(n - 1),
            "helper": {"radius_km": 10} | spec["helper"],
            "requester_flags": None,
            "verified": True,
            "demo": True,
            "created_at": now,
            "updated_at": now,
        }
        user |= await helper_embedding_fields(user)
        await database.users.insert_one(user)

    for i, (name, language, flags, text) in enumerate(REQUESTERS):
        n += 1
        user = {
            "google_sub": f"demo-{n}",
            "email": f"demo-{n}@example.com",
            "name": name,
            "role": Role.requester,
            "roles": [Role.requester],
            "language": language,
            "background": "",
            "home_location": place(n - 1),
            "helper": None,
            "requester_flags": {"medical_device": False, "mobility": False, "lives_alone": False} | flags,
            "demo": True,
            "created_at": now,
            "updated_at": now,
        }
        user["_id"] = (await database.users.insert_one(user)).inserted_id
        if text is None:
            continue
        created = now - timedelta(minutes=5 * (len(REQUESTERS) - i))
        embed_text, vector = await embed_for_matching(text, "request")
        request_id = ObjectId()
        exact = user["home_location"]
        fuzzed = fuzz_point(exact["coordinates"][1], exact["coordinates"][0], str(request_id), get_settings().jwt_secret)
        await database.requests.insert_one({
            "_id": request_id,
            "location": exact,
            "display_location": to_geojson(*fuzzed),
            "requester_id": user["_id"],
            "text": text,
            "language": language,
            "emergency": is_emergency(text),
            "status": RequestStatus.OPEN,
            "helper_id": None,
            "embed_text": embed_text,
            "embedding": vector,
            "timeline": [{"status": RequestStatus.OPEN, "at": created, "by": user["_id"]}],
            "demo": True,
            "created_at": created,
            "updated_at": created,
        })


    # One account with both profiles, to try the navbar mode switcher.
    n += 1
    dual = {
        "google_sub": f"demo-{n}",
        "email": f"demo-{n}@example.com",
        "name": "Dana (demo, both profiles)",
        "role": Role.requester,
        "roles": [Role.requester, Role.helper],
        "language": "en",
        "background": "Retired paramedic who lives on the second floor and uses a cane.",
        "helper": {"skills": ["first_aid", "cpr"], "custom_skills": [], "resources": ["medical_kit"], "radius_km": 10, "about": "Can check on neighbors and give basic first aid."},
        "requester_flags": {"medical_device": False, "mobility": True, "lives_alone": True},
        "home_location": place(n - 1),
        "verified": True,
        "demo": True,
        "created_at": now,
        "updated_at": now,
    }
    dual |= await helper_embedding_fields(dual)
    await database.users.insert_one(dual)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Mesh demo data (demo: true only)")
    parser.add_argument("--reset", action="store_true", help="delete existing demo data first")
    args = parser.parse_args()

    settings = get_settings()
    if not await db.init(settings):
        raise SystemExit("Could not connect to MongoDB; check MONGODB_URI")
    database = db.get_db()
    try:
        if args.reset:
            await reset(database)
        elif await database.users.count_documents({"demo": True}, limit=1):
            raise SystemExit("Demo data already exists; rerun with --reset")
        await seed(database)
        print(f"Seeded {len(HELPERS)} volunteers, {len(REQUESTERS)} requesters and 1 dual-profile user into '{settings.mongodb_db}'.")
        if not settings.demo_login:
            print("Note: set DEMO_LOGIN=true (and VITE_DEMO_LOGIN=true) to sign in as these users.")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
