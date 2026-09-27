"""API tests against a real MongoDB (set MONGODB_TEST_URI; skipped otherwise)."""

from concurrent.futures import ThreadPoolExecutor

from app.models import Role


def _create_request(env, text="A tree fell across my driveway, need chainsaw help"):
    _, headers = env.make_user(Role.requester, "Requester")
    resp = env.client.post("/api/requests", json={"text": text}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json(), headers


def test_me_and_onboarding(env):
    _, headers = env.make_user(None, "New")
    assert env.client.get("/api/me", headers=headers).json()["needs_onboarding"] is True
    # Endpoints that need a role are blocked until onboarding.
    assert env.client.get("/api/requests/mine", headers=headers).json()["error"]["code"] == "ONBOARDING_REQUIRED"
    resp = env.client.post("/api/onboarding", json={"role": "requester", "name": "Ruth", "background": "retired"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "requester"
    assert env.client.post("/api/onboarding", json={"role": "helper", "name": "x"}, headers=headers).status_code == 409


def test_no_cookie_is_401(env):
    assert env.client.get("/api/me").status_code == 401


def test_helper_profile_is_embedded(env):
    env.onboard_helper("Marcus", "chainsaw and truck for fallen trees", ["chainsaw"])
    helper = env.raw.users.find_one({"name": "Marcus"})
    assert helper["embedding"] and len(helper["embedding"]) == 384
    assert "chainsaw" in helper["profile_text"]


def test_ranking_prefers_matching_volunteer_profile(env):
    tree = _create_request(env, "A big tree fell across my driveway, need someone with a chainsaw")[0]["request"]
    water = _create_request(env, "We need drinking water and food delivered for kids")[0]["request"]
    tree_helper = env.onboard_helper("Marcus", "I have a chainsaw and can remove a fallen tree from a driveway")
    water_helper = env.onboard_helper("Diego", "I can deliver drinking water and food with my van")

    ranked = env.client.get("/api/requests/ranked", headers=tree_helper).json()
    assert ranked["vector_search"] == "local"
    assert [r["id"] for r in ranked["requests"]][:2] == [tree["id"], water["id"]]
    assert all("requester" not in r for r in ranked["requests"])

    ranked = env.client.get("/api/requests/ranked", headers=water_helper).json()
    assert [r["id"] for r in ranked["requests"]][:2] == [water["id"], tree["id"]]


def test_one_active_request_per_requester(env):
    _, headers = _create_request(env)
    resp = env.client.post("/api/requests", json={"text": "another one please"}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ACTIVE_REQUEST_EXISTS"


def test_emergency_check_and_flag(env):
    _, headers = env.make_user(Role.requester)
    assert env.client.post("/api/requests/check", json={"text": "no puedo respirar"}, headers=headers).json() == {"emergency": True}
    resp = env.client.post("/api/requests", json={"text": "my father is unconscious"}, headers=headers).json()
    assert resp["show_911"] is True and resp["request"]["emergency"] is True


def test_claim_race_only_one_wins(env):
    created, _ = _create_request(env)
    rid = created["request"]["id"]
    helpers = [env.onboard_helper(f"H{i}", "chainsaw") for i in range(2)]
    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(lambda h: env.client.post(f"/api/requests/{rid}/claim", headers=h).status_code, helpers))
    assert codes == [200, 409]


def test_requester_cannot_claim_and_helper_cannot_create(env):
    created, req_headers = _create_request(env)
    helper = env.onboard_helper("H", "anything")
    assert env.client.post(f"/api/requests/{created['request']['id']}/claim", headers=req_headers).status_code == 403
    assert env.client.post("/api/requests", json={"text": "help me"}, headers=helper).status_code == 403


def test_full_flow_with_private_chat(env):
    created, req_headers = _create_request(env)
    rid = created["request"]["id"]
    helper = env.onboard_helper("Marcus", "chainsaw")
    stranger = env.onboard_helper("Stranger", "chainsaw")

    # Chat is closed until claimed.
    assert env.client.get(f"/api/requests/{rid}/messages", headers=req_headers).status_code == 403

    claimed = env.client.post(f"/api/requests/{rid}/claim", headers=helper).json()["request"]
    assert claimed["status"] == "CLAIMED"
    assert claimed["requester"]["name"] == "Requester"  # assigned helper sees requester details

    mine = env.client.get("/api/requests/mine", headers=req_headers).json()["requests"][0]
    assert mine["helper"]["name"] == "Marcus"

    # Messages both ways.
    env.client.post(f"/api/requests/{rid}/messages", json={"text": "On my way"}, headers=helper)
    env.client.post(f"/api/requests/{rid}/messages", json={"text": "Thank you!"}, headers=req_headers)
    msgs = env.client.get(f"/api/requests/{rid}/messages", headers=req_headers).json()["messages"]
    assert [m["text"] for m in msgs] == ["On my way", "Thank you!"]
    assert [m["mine"] for m in msgs] == [False, True]

    # Polling with `after` returns only newer messages.
    newer = env.client.get(f"/api/requests/{rid}/messages", params={"after": msgs[0]["ts"]}, headers=req_headers).json()
    assert [m["text"] for m in newer["messages"]] == ["Thank you!"]

    # Strangers can't read, write, or see the claimed request.
    assert env.client.get(f"/api/requests/{rid}/messages", headers=stranger).status_code == 403
    assert env.client.post(f"/api/requests/{rid}/messages", json={"text": "hi"}, headers=stranger).status_code == 403
    assert env.client.get(f"/api/requests/{rid}", headers=stranger).status_code == 404

    resolved = env.client.post(f"/api/requests/{rid}/resolve", headers=req_headers).json()["request"]
    assert resolved["status"] == "RESOLVED"
    assert env.client.post(f"/api/requests/{rid}/messages", json={"text": "bye"}, headers=helper).status_code == 409


def test_release_hides_previous_chat_from_next_helper(env):
    created, req_headers = _create_request(env)
    rid = created["request"]["id"]
    first = env.onboard_helper("First", "chainsaw")
    second = env.onboard_helper("Second", "chainsaw")

    env.client.post(f"/api/requests/{rid}/claim", headers=first)
    env.client.post(f"/api/requests/{rid}/messages", json={"text": "private note"}, headers=req_headers)
    assert env.client.post(f"/api/requests/{rid}/release", headers=first).json()["request"]["status"] == "OPEN"

    env.client.post(f"/api/requests/{rid}/claim", headers=second)
    assert env.client.get(f"/api/requests/{rid}/messages", headers=second).json()["messages"] == []


def test_cancel_and_invalid_transition(env):
    created, req_headers = _create_request(env)
    rid = created["request"]["id"]
    assert env.client.post(f"/api/requests/{rid}/cancel", headers=req_headers).json()["request"]["status"] == "CANCELLED"
    resp = env.client.post(f"/api/requests/{rid}/resolve", headers=req_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_TRANSITION"


def test_demo_login_lists_only_demo_users(env):
    demo, _ = env.make_user(Role.helper, "Demo Helper", demo=True)
    env.make_user(Role.helper, "Real Helper")
    users = env.client.get("/api/auth/demo-users").json()["users"]
    assert [u["name"] for u in users] == ["Demo Helper"]
    resp = env.client.post("/api/auth/demo", json={"user_id": str(demo["_id"])})
    assert resp.status_code == 200 and "session" in resp.cookies


def test_volunteer_edits_profile_and_ranking_follows(env):
    tree = _create_request(env, "A tree fell on my roof and someone needs to climb up and cut it")[0]["request"]
    water = _create_request(env, "We need drinking water delivered")[0]["request"]
    headers = env.onboard_helper("Sam", "I can deliver drinking water")
    assert env.client.get("/api/requests/ranked", headers=headers).json()["requests"][0]["id"] == water["id"]

    body = {"helper": {"skills": ["chainsaw"], "custom_skills": ["tree climbing", "Tree Climbing"], "resources": ["truck"],
                       "about": "I climb and cut up fallen trees on roofs"}}
    resp = env.client.patch("/api/me", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["helper"]["custom_skills"] == ["tree climbing"]
    assert "tree climbing" in env.raw.users.find_one({"name": "Sam"})["profile_text"]
    assert env.client.get("/api/requests/ranked", headers=headers).json()["requests"][0]["id"] == tree["id"]


def test_custom_skill_validation_error_shape(env):
    headers = env.onboard_helper("Sam", "anything")
    resp = env.client.patch("/api/me", json={"helper": {"custom_skills": ["x" * 41]}}, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_profile_save_only_rematches_when_matching_text_changes(env):
    headers = env.onboard_helper("Sam", "I can deliver water")
    before = env.raw.users.find_one({"name": "Sam"})["embedding"]

    resp = env.client.patch("/api/me", json={"name": "Sam R.", "language": "es"}, headers=headers).json()
    assert resp["rematching"] is False
    assert env.raw.users.find_one({"_id": env.raw.users.find_one({"name": "Sam R."})["_id"]})["embedding"] == before

    body = {"helper": {"skills": [], "custom_skills": ["Tree climbing"], "resources": [], "about": "I can deliver water"}}
    resp = env.client.patch("/api/me", json=body, headers=headers).json()
    assert resp["rematching"] is True
    after = env.raw.users.find_one({"name": "Sam R."})
    assert after["embedding"] != before and "Tree climbing" in after["profile_text"]


def test_new_request_is_embedded_after_response(env):
    created, _ = _create_request(env, "Need water")
    doc = env.raw.requests.find_one({"text": "Need water"})
    # TestClient runs background tasks before returning, so the embedding is already there.
    assert doc["embedding"] and len(doc["embedding"]) == 384
    assert created["request"]["id"] == str(doc["_id"])


def test_stale_background_embedding_does_not_overwrite_newer_profile(env):
    import asyncio
    import os

    from pymongo import AsyncMongoClient

    from app.services.indexing import refresh_helper_embedding

    user, _ = env.make_user(Role.helper, "Racer", profile_text="newer text", embedding=[1.0] * 384)

    async def run_stale_job():
        client = AsyncMongoClient(os.environ["MONGODB_TEST_URI"])
        try:
            await refresh_helper_embedding(client[env.raw.name], user["_id"], "older text")
        finally:
            await client.close()

    asyncio.run(run_stale_job())
    assert env.raw.users.find_one({"_id": user["_id"]})["embedding"] == [1.0] * 384
