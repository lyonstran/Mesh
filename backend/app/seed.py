"""Demo data: `python -m app.seed --reset` (PLAN.md §15, adapted for §0.1).

Only touches documents flagged demo: true. Everyone here is fictional, and every place is a made-up offset from the
HackGT venue, never a real address. Requests go through the same scoring as the create flow (rules triage, tract +
EJI, hazards, priority), so the volunteer map and "Why this rank?" look like the real thing. The AI step only
normalizes text for embeddings; triage here is rules-only so the seed is repeatable.
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app import db
from app.config import get_settings
from app.models import RequestStatus, Role
from app.services import priority
from app.services.embeddings import embed_for_matching
from app.services.fuzz import fuzz_point
from app.services.geo import destination, to_geojson
from app.services.hazards import get_hazards
from app.services.profile import helper_embedding_fields
from app.services.rules import urgency_floor
from app.services.tracts import tract_for_point
from app.services.triage import merge

CONCURRENCY = 6  # the AI normalization takes seconds per item; run a few at once

# (name, background, skills, resources, about, radius_km, place) -- place = (bearing°, km) from the venue.
HELPERS = [
    ("Marcus (demo)", "Landscaper in Midtown for ten years.", ["chainsaw", "heavy_lifting", "driving"], ["truck"],
     "I have a chainsaw and a pickup truck. Happy to cut up fallen trees and haul away debris.", 12, (0, 0.2)),
    ("Priya (demo)", "Registered nurse at a local clinic.", ["nursing", "first_aid", "cpr", "elder_care"], ["medical_kit"],
     "Can do welfare checks on elderly neighbors, basic wound care, and help with medications or medical devices.", 10, (95, 1.2)),
    ("Diego (demo)", "Bilingual, drive for a delivery company.", ["spanish", "driving"], ["vehicle", "water", "food"],
     "Hablo español. I have a minivan and can drive people to shelters or bring groceries, water, and prescriptions.", 15, (170, 3.5)),
    ("Janelle (demo)", "Electrician's apprentice.", ["electrical_safe"], ["generator", "power_bank"],
     "I own a portable generator and several power banks. Can bring power for phones, fridges, or medical equipment.", 12, (250, 2.6)),
    ("Kwame (demo)", "Contractor, builds decks and fences.", ["heavy_lifting", "chainsaw"], ["truck", "tarp"],
     "Can tarp damaged roofs, clear limbs with a chainsaw, and board up broken windows.", 15, (200, 6.0)),
    ("Mei (demo)", "Pharmacy technician.", ["first_aid"], ["medical_kit", "water"],
     "Can pick up and deliver prescriptions, insulin coolers, and basic first-aid supplies.", 10, (60, 4.0)),
    ("Luis (demo)", "Runs a church food pantry.", ["spanish", "driving"], ["food", "water", "vehicle"],
     "Delivering hot meals, bottled water, and baby formula. Hablo español.", 15, (225, 8.0)),
    ("Hannah (demo)", "EMT on weekends.", ["first_aid", "cpr"], ["medical_kit", "vehicle"],
     "Certified EMT. Can check on people who are hurt or unwell and help them get to care.", 12, (130, 5.5)),
    ("Omar (demo)", "Owns a moving company van.", ["driving", "heavy_lifting"], ["truck", "vehicle"],
     "Can move people and belongings to shelters or relatives, including wheelchairs.", 15, (300, 7.0)),
    ("Grace (demo)", "Retired social worker.", ["elder_care", "other_language"], ["vehicle"],
     "Welfare checks, sitting with older neighbors, and helping with phone calls to family or insurers.", 10, (330, 3.0)),
    ("Tomás (demo)", "Plumber.", ["heavy_lifting"], ["truck", "sandbags"],
     "Pumping out flooded basements, sandbagging doors, and shutting off water safely.", 12, (180, 9.0)),
    ("Aisha (demo)", "Owns a cool, air-conditioned community room.", ["childcare"], ["ac_space", "water", "food"],
     "Our community room has generator power and A/C. Families and kids can come cool off and charge phones.", 10, (150, 2.0)),
]

# (name, language, requester_flags, request text or None, place, minutes ago, claimed_by helper index or None)
REQUESTERS = [
    ("Alex (demo)", "en", {}, "A tree fell across my driveway and I can't get my car out.", (20, 0.8), 12, None),
    ("Ruth (demo)", "en", {"medical_device": True}, "My oxygen concentrator needs power. The electricity has been out since last night.", (95, 2.2), 40, None),
    ("Rosa (demo)", "es", {"mobility": True}, "Necesito que alguien me lleve al refugio, no tengo carro.", (185, 6.5), 55, None),
    ("Sam (demo)", "en", {}, "My elderly neighbor lives alone and hasn't answered her door since the storm. Can someone check on her?", (250, 4.2), 25, None),
    ("Tanya (demo)", "en", {}, "We're running low on drinking water and food for two kids.", (210, 7.5), 70, None),
    ("Jordan (demo)", "en", {}, "Big branches and debris are blocking the road in front of my house.", (320, 1.6), 8, None),
    ("Keisha (demo)", "en", {}, "Water is coming into the house and we're trapped upstairs with the kids.", (175, 9.5), 4, None),
    ("Bill (demo)", "en", {"lives_alone": True}, "I'm 82 and alone, the power's out and my house is getting cold and dark.", (140, 5.0), 35, None),
    ("Maria (demo)", "es", {}, "Tengo un bebé recién nacido y no tenemos agua potable.", (230, 10.5), 22, None),
    ("Devon (demo)", "en", {}, "Part of my roof blew off. Need a tarp before more rain comes.", (200, 3.8), 50, None),
    ("Linh (demo)", "en", {"medical_device": True}, "My dad needs dialysis tomorrow and our street is flooded. Need a ride.", (160, 7.0), 30, None),
    ("Jamal (demo)", "en", {}, "Basement has a foot of water. Could use a pump and sandbags.", (190, 11.0), 90, None),
    ("Patricia (demo)", "en", {"mobility": True}, "I use a wheelchair and the ramp is covered in fallen limbs.", (270, 5.8), 18, None),
    ("Carlos (demo)", "es", {}, "Se cayó un árbol sobre la cerca y bloquea la salida de mi casa.", (240, 8.8), 44, None),
    ("Denise (demo)", "en", {}, "My insulin needs to stay cold and the fridge has been off for a day.", (120, 3.2), 28, None),
    ("Frank (demo)", "en", {}, "Need phone charging and some batteries, power has been out two days.", (45, 5.5), 120, None),
    ("Imani (demo)", "en", {}, "My grandmother is by herself and not answering. She lives near the creek.", (205, 5.2), 15, None),
    ("Ben (demo)", "en", {}, "Could use help moving furniture upstairs before the water rises more.", (165, 4.5), 65, None),
    ("Yolanda (demo)", "en", {}, "Our family needs a place to stay tonight, the apartment is flooded.", (215, 6.2), 38, None),
    ("Kevin (demo)", "en", {}, "A power line is down across my yard and sparking.", (80, 2.8), 6, None),
    ("Ana (demo)", "es", {"lives_alone": True}, "Mi abuela vive sola y no tiene luz ni comida.", (255, 9.8), 47, None),
    ("Tyrone (demo)", "en", {}, "Fallen tree on my car, nobody hurt. Need it cut and moved.", (300, 3.5), 80, None),
    ("Sofia (demo)", "en", {}, "Need baby formula and diapers, stores are closed.", (185, 3.0), 26, None),
    ("Walter (demo)", "en", {"medical_device": True}, "My CPAP needs power tonight. Anyone with a generator?", (30, 7.5), 33, None),
    ("Nia (demo)", "en", {}, "Kids are overheating, no A/C since the storm. Need somewhere cool.", (150, 6.8), 52, None),
    ("George (demo)", "en", {}, "Gutters ripped off and water coming through the ceiling.", (345, 4.8), 100, None),
    ("Lucía (demo)", "es", {"mobility": True}, "No puedo caminar bien y necesito medicinas de la farmacia.", (225, 4.0), 20, 5),
    ("Ray (demo)", "en", {}, "Debris all over the driveway, can't get out for work.", (10, 3.9), 140, 0),
    ("Mona (demo)", "en", {}, "Need drinking water for my elderly parents, about 4 gallons.", (110, 8.2), 60, 6),
    ("Casey (demo)", "en", {}, None, (60, 1.0), 0, None),  # no request yet: use this account to try submitting one
]

VENUE = (33.7756, -84.3963)


def place(bearing: float, km: float) -> dict:
    """GeoJSON Point for a made-up offset from the venue (not a real address)."""
    lat, lon = destination(VENUE[0], VENUE[1], bearing, km * 1000)
    return to_geojson(lat, lon)


async def reset(database) -> None:
    demo_requests = await database.requests.find({"demo": True}, {"_id": 1}).to_list()
    await database.messages.delete_many({"request_id": {"$in": [r["_id"] for r in demo_requests]}})
    await database.requests.delete_many({"demo": True})
    await database.users.delete_many({"demo": True})


def _user(n: int, now: datetime, **fields) -> dict:
    return {"google_sub": f"demo-{n}", "email": f"demo-{n}@example.com", "demo": True, "created_at": now, "updated_at": now} | fields


async def _helper(n: int, spec: tuple, now: datetime, gate: asyncio.Semaphore) -> dict:
    name, background, skills, resources, about, radius, where = spec
    user = _user(
        n, now, name=name, role=Role.helper, roles=[Role.helper], language="es" if "spanish" in skills else "en",
        background=background, home_location=place(*where), requester_flags=None, verified=True,
        helper={"skills": skills, "custom_skills": [], "resources": resources, "about": about, "radius_km": radius},
    )
    async with gate:
        user |= await helper_embedding_fields(user)
    return user


async def _requester(database, n: int, spec: tuple, now: datetime, gate: asyncio.Semaphore, helpers: list[dict], weights: dict) -> tuple[dict, dict | None]:
    name, language, flags, text, where, minutes_ago, claimed_by = spec
    home = place(*where)
    user = _user(
        n, now, name=name, role=Role.requester, roles=[Role.requester], language=language, background="", helper=None,
        home_location=home, requester_flags={"medical_device": False, "mobility": False, "lives_alone": False} | flags,
    )
    user["_id"] = ObjectId()
    if text is None:
        return user, None

    lat, lon = home["coordinates"][1], home["coordinates"][0]
    request_id = ObjectId()
    created = now - timedelta(minutes=minutes_ago)
    card = merge(urgency_floor(text, user["requester_flags"]), None, text, language)  # the create flow's rules path
    async with gate:  # keep the NWS / Open-Meteo calls polite too
        tract = await tract_for_point(database, lat, lon)
        hazards = await get_hazards(database, lat, lon)
    status = RequestStatus.CLAIMED if claimed_by is not None else RequestStatus.OPEN
    eji_rank = tract.get("eji_rank") if tract else None
    score, breakdown = priority.compute(
        urgency=card.urgency, hazard_level=hazards["level"], eji_rank=eji_rank,
        created_at=created, now=now, is_open=status == RequestStatus.OPEN, weights=weights,
    )
    async with gate:
        embed_text, vector = await embed_for_matching(text, "request")
    timeline = [{"status": RequestStatus.OPEN, "at": created, "by": user["_id"]}]
    doc = {
        "_id": request_id, "requester_id": user["_id"], "text": text, "language": language,
        "emergency": card.emergency, "category": card.category, "urgency": card.urgency,
        "urgency_rule_floor": card.urgency_rule_floor, "flags": list(card.flags), "needs": card.needs,
        "summary": card.summary, "triage_source": card.source,
        "tract_geoid": tract["geoid"] if tract else None, "eji_rank": eji_rank,
        "hazard_snapshot": hazards, "hazard_level": hazards["level"], "priority": score, "priority_breakdown": breakdown,
        "location": home, "display_location": to_geojson(*fuzz_point(lat, lon, str(request_id), get_settings().jwt_secret)),
        "status": status, "helper_id": None, "embed_text": embed_text, "embedding": vector,
        "timeline": timeline, "demo": True, "created_at": created, "updated_at": created,
    }
    if claimed_by is not None:
        claimed_at = created + timedelta(minutes=min(10, minutes_ago // 2))
        doc |= {"helper_id": helpers[claimed_by]["_id"], "claimed_at": claimed_at, "updated_at": claimed_at}
        timeline.append({"status": RequestStatus.CLAIMED, "at": claimed_at, "by": helpers[claimed_by]["_id"]})
    return user, doc


async def seed(database) -> None:
    now = datetime.now(UTC)
    gate = asyncio.Semaphore(CONCURRENCY)
    weights = await priority.load_weights(database)

    helpers = await asyncio.gather(*(_helper(i + 1, spec, now, gate) for i, spec in enumerate(HELPERS)))
    for h in helpers:
        h["_id"] = (await database.users.insert_one(h)).inserted_id

    offset = len(HELPERS) + 1
    results = await asyncio.gather(
        *(_requester(database, offset + i, spec, now, gate, helpers, weights) for i, spec in enumerate(REQUESTERS))
    )
    await database.users.insert_many([u for u, _ in results])
    await database.requests.insert_many([d for _, d in results if d is not None])

    # One account with both profiles, to try the navbar mode switcher.
    dual = _user(
        offset + len(REQUESTERS), now, name="Dana (demo, both profiles)", role=Role.requester,
        roles=[Role.requester, Role.helper], language="en",
        background="Retired paramedic who lives on the second floor and uses a cane.",
        helper={"skills": ["first_aid", "cpr"], "custom_skills": [], "resources": ["medical_kit"], "radius_km": 10,
                "about": "Can check on neighbors and give basic first aid."},
        requester_flags={"medical_device": False, "mobility": True, "lives_alone": True},
        home_location=place(75, 1.5), verified=True,
    )
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
        n_requests = sum(1 for r in REQUESTERS if r[3] is not None)
        print(f"Seeded {len(HELPERS)} volunteers, {len(REQUESTERS)} requesters ({n_requests} requests) and 1 dual-profile user into '{settings.mongodb_db}'.")
        if not settings.demo_login:
            print("Note: set DEMO_LOGIN=true (and VITE_DEMO_LOGIN=true) to sign in as these users.")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
