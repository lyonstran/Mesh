# Mesh: Build Plan (HackGT 13)

> **For Claude Code:** This is the complete spec. Read all of it before writing code. Build in the milestone order in §13. Anything marked **[HUMAN]** needs input from the team (API docs, keys, files). Do not guess it. Stub it behind an interface and leave a clear TODO. Rules in §14 are non-negotiable.

---

## 0. Product summary

**Name note:** "Mesh" refers to a *human* mesh, meaning neighbors linked to neighbors. The app does **not** do peer-to-peer or offline mesh networking. It needs internet access (§1). Don't describe it as offline-capable in UI copy, docs, or the pitch. Use the product name "Mesh" in UI titles, the page `<title>`, and the manifest.

Mesh is a mobile-first web app for weather-disaster relief. It works like a delivery app, but for help.

- **Requesters** ask for help by voice or text ("tree on my power line, I use an oxygen machine").
- **AI triage** turns the request into structured data: category, urgency, and flags.
- **Helpers** (verified volunteers) see nearby requests on a map, ranked by a transparent priority score. They claim a request and move it through statuses.
- **Live hazard data** feeds priority and suggests likely needs:
  - NWS alerts;
  - Open-Meteo forecast and air quality;
  - CDC/ATSDR EJI tract vulnerability.
- **Coordinators** (community organizations) see a regional dashboard and an AI situation summary.

**Region:** Georgia, demo centered on the HackGT venue at Georgia Tech (≈ 33.7756, -84.3963).

**Prize targets:**
- Meta "Bringing people closer together with AI": uses Muse Spark and Muse Voice Transcribe.
- Aramco "A Marina's Mission."
- MLH: MongoDB Atlas, ElevenLabs, Vultr, .TECH domain.

Every sponsor technology must do real work, not decoration.

**Non-goals:**
- Not a 911 replacement.
- No real emergency dispatch.
- No native mobile app.
- No payments.
- No multi-region scaling.

---

## 0.1 Iteration 1: MVP (current build target)

> **Build this first.** Everything else in this plan is the target for later iterations (see §21). Where this section and a later section disagree, this section wins for the MVP.

The MVP is a working prototype the team builds on afterwards. Both sides are registered users. There are no external or social-media posts, no location data, and no map.

### User journeys
- **Volunteer** (role `helper`, shown as "Volunteer" in the UI):
  1. Signs in with Google.
  2. Onboarding: name, language, background, skills and resources (enums from §6), up to 10 custom skills of their own ("+ Add your own", max 40 characters each), and a free-text "What I can offer." Everything can be edited later on `/profile`; saving re-embeds the profile.
  3. Sees open requests **ranked purely by vector similarity** between each request and their profile.
  4. Picks a request (atomic claim) and goes to a private chat with that requester.
- **Requester:**
  1. Signs in with Google.
  2. Onboarding: name, language, background, and optional `requester_flags` (shared only with the volunteer who picks the request).
  3. Submits a request. Emergency phrases trigger the 911 interstitial first (§9.2 step 5, keyword rules only).
  4. When a volunteer picks it, sees the private chat with that volunteer.

### One account, two profiles
A user can hold both a Volunteer profile and a Requester profile on the same account.
- Onboarding still picks one role. The second profile is added later from `/profile` ("Become a volunteer" / "Request help") via `POST /api/me/roles`.
- `users.roles` lists the profiles held; `users.role` is the **active mode**, which only decides the home page (`/r` or `/h`). Users with both profiles switch mode from the navbar (`PATCH /api/me {role}`).
- Endpoint guards check the profiles held, not the active mode.
- Switching mode is always allowed, including with an active request, because it deletes nothing.
- A user cannot claim, or see in their ranked list, their own request (409 `OWN_REQUEST`).
- `background` is one shared field. The volunteer embedding and the requester's view for a claiming volunteer both use it.

### In scope
- Google auth, JWT cookie, and demo login (§6).
- Onboarding and profile editing.
- Requests with the statuses `OPEN`, `CLAIMED`, `RESOLVED`, and `CANCELLED` (a subset of §9.1, so later iterations extend it):
  - `OPEN` → `CLAIMED` (volunteer claim) or `CANCELLED` (requester).
  - `CLAIMED` → `RESOLVED` (either party), `OPEN` (volunteer release), or `CANCELLED` (requester).
  - A requester has at most 1 active request.
- Similarity ranking.
- Private chat per claimed request, using REST polling.
- The 911 keyword check (EN + ES).
- Seed data.

### Out of scope for the MVP
Location, fuzzing, and maps; hazards and simulation; EJI and tracts; triage category/urgency and the priority formula; voice; the coordinator role; WebSocket realtime; translation; verified-helper rules; social-media leads. See §21. (Iteration 2 below brings the first four back into scope.)

### Iteration 2: location, map, tracts/EJI, hazards, matching (in scope)
Built in four phases, each ending with tests and a team check before the next. Specs are §4 (data), §7 (hazards), §9.4-9.6 (priority, fuzzing, serializer) and §10 (live location); this list says what changes for the MVP.
1. **Location and map.** Requests carry an exact `location` and a deterministic fuzzed `display_location` (300-500 m). Volunteers set a `home_location` and `radius_km` (default 10, max 15 km); requesters may set a home location. `GET /api/geocode?q=` (Census geocoder) or a dropped pin sets a location. Maps use Leaflet + OpenStreetMap tiles with attribution.
2. **Data sources.** `data/` loads Georgia tracts with EJI 2024 ranks into Mongo (`tracts`). Requests store `tract_geoid`, `eji_rank`, `hazard_snapshot` and `hazard_level` at create time. Hazards come from NWS + Open-Meteo (§7), always `simulated: false` here (simulation mode stays deferred).
3. **Matching.** The volunteer list is a blended score: fit (embedding similarity, §0.1) + proximity + need (`priority`, §9.4, using the rules urgency floor since there is no LLM triage yet). Hard filters: within radius, fewer than 2 active claims. Distance uses `display_location`. Each request returns a per-factor `breakdown`; weights are designed defaults, not fitted.
4. **Live location.** After a claim, both parties share location with each other only, via polling (`POST/GET /api/requests/{id}/location`), until the request is released, resolved or cancelled. Only the latest point is stored (TTL), keyed by `(user_id, request_id)`. When the other person is a `demo: true` account with no real presence (and `DEMO_LOGIN` is on), `GET` returns a moving position around their location with `simulated: true`, and the UI shows a SIMULATED badge (§14 rule 7); it is never stored.

5. **Volunteers on the requester's map.** `GET /api/volunteers/nearby?lat&lon&radius_km` (requester only) returns volunteers' fuzzed `display_location` and nothing else: no id, name, skills or exact point. Each volunteer's point is fuzzed 300-500 m with the same HMAC scheme, keyed by their user id, so it is stable between calls. Volunteers can opt out with `helper.show_area_to_requesters` (default true).

Privacy for Iteration 2: exact location goes only to the requester and the assigned volunteer; every other viewer gets `display_location`. The other party's live location is never part of `serialize_request`; it has its own endpoint that enforces the same two-party rule.

### Similarity ranking
1. **Text to embed:**
   - For a request: the request text.
   - For a volunteer: skills (listed and custom) + resources + "What I can offer" + background, joined into `profile_text`.
2. **Normalize (optional, Muse Spark):** when `LLM_PROVIDER=muse`, Spark rewrites the text into a short list of needs (request) or capabilities (volunteer) before embedding. Under `mock` the text passes through unchanged.
3. **Embed:** `fastembed` runs `sentence-transformers/all-MiniLM-L6-v2` locally (384 dimensions, ONNX, about 90 MB downloaded on first use). The Meta Model API has no embeddings endpoint (checked 2026-09-26), so vectors come from this local model.
   - We use `fastembed` instead of the `sentence-transformers` package because it runs the same model without PyTorch and fits the smallest Vultr VM.
4. **Retrieve:** MongoDB Atlas Vector Search (`$vectorSearch` on search index `requests_embedding`: path `embedding`, 384 dimensions, cosine similarity, filter on `status`) returns `OPEN` requests ordered by similarity to the volunteer's profile vector.
   - When Atlas Search isn't available (local Mongo, tests), the backend computes cosine similarity in Python instead.
   - `VECTOR_SEARCH=auto|atlas|local` controls this, and `/api/health` reports which mode is active.
5. **Scores come from code.** The LLM only rewrites text; it never produces a score or a rank.
6. **Embedding runs after the response.** Spark normalization takes about 5–20 s, so saving a profile or creating a request returns immediately and a background task writes the vector (`services/indexing.py`); ranking catches up when it lands. A background write is skipped if the profile changed again in the meantime, and saves that don't change the matching text skip Spark entirely.

### MVP endpoints
| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/api/auth/google` | public | §6 |
| POST | `/api/auth/logout` | any | |
| GET | `/api/me` | authed | |
| GET/POST | `/api/auth/demo-users`, `/api/auth/demo` | public | 404 unless `DEMO_LOGIN` |
| POST | `/api/onboarding` | authed | role `requester` or `helper` |
| PATCH | `/api/me` | onboarded | re-embeds volunteer profile; `role` switches the active mode to a held profile (409 `ROLE_NOT_HELD`) |
| POST | `/api/me/roles` | onboarded | adds the missing profile (`helper` or `requester_flags`); 409 `ROLE_EXISTS` |
| POST | `/api/requests/check` | requester | `{text}` → `{emergency}`; no save |
| POST | `/api/requests` | requester | max 1 active → 409 |
| GET | `/api/requests/mine` | onboarded | requester: own; volunteer: claimed |
| GET | `/api/requests/ranked` | volunteer | `OPEN` requests + similarity score; excludes the caller's own requests |
| GET | `/api/requests/{id}` | per serializer | |
| POST | `/api/requests/{id}/claim` | volunteer | atomic; 409 `ALREADY_CLAIMED`; 409 `OWN_REQUEST` |
| POST | `/api/requests/{id}/release` | assigned volunteer | back to `OPEN` |
| POST | `/api/requests/{id}/resolve` | requester or assigned volunteer | |
| POST | `/api/requests/{id}/cancel` | requester | |
| GET/POST | `/api/requests/{id}/messages` | requester + assigned volunteer | `?after=<iso>` for polling |
| POST/GET/DELETE | `/api/requests/{id}/location` | requester + assigned volunteer, only while `CLAIMED` | POST shares your point (≥5 s apart; extra updates are dropped, not errors); GET returns only the *other* person's point; DELETE pauses sharing. 409 `NOT_ACTIVE` otherwise, 403 for everyone else |

### MVP privacy (serializer, §9.6 adapted)
| Viewer | Request text | Requester name / flags | Chat |
|---|---|---|---|
| The requester | yes | own | yes, once claimed |
| Assigned volunteer | yes | yes | yes |
| Other volunteers | yes (plus score) | no | no |

### Pages
`/` (public landing page), `/login`, `/onboarding`, `/profile` (edit onboarding details), `/r` (requester: submit form, current request, chat link), `/h` (volunteer: my active chats plus the ranked list), `/chat/:requestId`. Polling intervals: chat every 3 s, requester status every 5 s, ranked list every 10 s.

### Hard rules that bind the MVP
All of §14 still applies. In particular:
- no invented API specs;
- the privacy serializer;
- the 911 path;
- no secrets in git;
- `DEMO_LOGIN` returns 404 when off;
- the app works with `LLM_PROVIDER=mock`;
- similarity scores come from code, never the LLM.

---

## 1. Architecture overview

```
 Phone/Browser (Vite + React SPA)
   │  HTTPS REST (/api/*)      WSS (/ws)
   ▼
 Caddy (Vultr VM) ── serves frontend/dist static files
   │  reverse proxy /api/* and /ws
   ▼
 FastAPI (uvicorn, single process)
   ├── auth (Google ID token → own JWT cookie)
   ├── requests (state machine, fuzzing, priority, matching)
   ├── hazards (NWS + Open-Meteo, cache, simulation)
   ├── ai (triage, match reasons, translation, summaries) → Muse Spark
   ├── voice (transcribe → Muse Voice Transcribe; speak → ElevenLabs)
   ├── realtime (WebSocket manager + Mongo change streams)
   └── geo (Census geocoder, tract lookup via $geoIntersects)
   │
   ▼
 MongoDB Atlas (users, presence, requests, messages, tracts, resources, hazard_cache, settings)
```

**One domain for everything** (`https://<domain>.tech`), so:
- there is no CORS setup;
- the session cookie is sent on the WebSocket handshake automatically.

In local dev, the Vite dev server proxies `/api` and `/ws` to `localhost:8000`.

---

## 2. Repository layout

```
mesh/
├── PLAN.md
├── CLAUDE.md                  # short rules summary pointing to PLAN.md
├── .env.example
├── docker-compose.yml
├── deploy/
│   └── Caddyfile
├── data/
│   ├── raw/                   # [HUMAN] EJI CSV + TIGER tract shapefile go here (gitignored)
│   ├── processed/             # generated (gitignored)
│   ├── eji_columns.yaml       # mapping of EJI column names (verify vs data dictionary)
│   ├── prepare_tracts.py      # EJI + TIGER → GeoJSON
│   └── load_tracts.py         # GeoJSON → Mongo tracts collection
├── backend/
│   ├── pyproject.toml / requirements.txt
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan (db, indexes, change-stream task)
│   │   ├── config.py          # pydantic-settings
│   │   ├── db.py              # AsyncMongoClient, get_db, ensure_indexes()
│   │   ├── models.py          # pydantic models + enums
│   │   ├── deps.py            # get_current_user, require_role
│   │   ├── security.py        # JWT create/verify
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── requests.py
│   │   │   ├── messages.py
│   │   │   ├── hazards.py
│   │   │   ├── sim.py
│   │   │   ├── geo.py
│   │   │   ├── voice.py
│   │   │   ├── coordinator.py
│   │   │   ├── resources.py
│   │   │   └── ws.py
│   │   ├── services/
│   │   │   ├── hazards.py     # fetch, normalize, cache, combine
│   │   │   ├── triage.py      # rules floor + LLM merge
│   │   │   ├── rules.py       # keyword lists (EN + ES)
│   │   │   ├── priority.py
│   │   │   ├── matching.py
│   │   │   ├── fuzz.py
│   │   │   ├── state.py       # request state machine
│   │   │   ├── serialize.py   # viewer-aware request serialization
│   │   │   ├── geocode.py
│   │   │   ├── tts.py         # ElevenLabs
│   │   │   ├── transcribe.py  # Muse Voice Transcribe
│   │   │   └── realtime.py    # ConnectionManager + change stream broadcaster
│   │   ├── ai/
│   │   │   ├── provider.py    # LLMProvider protocol
│   │   │   ├── muse.py        # MuseProvider [HUMAN docs]
│   │   │   ├── mock.py        # MockProvider (deterministic, for dev/tests)
│   │   │   └── prompts.py
│   │   ├── scenarios/         # simulation JSON files
│   │   └── seed.py            # demo users/requests/resources
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts         # dev proxy /api, /ws → :8000
│   ├── index.html
│   └── src/
│       ├── main.tsx, App.tsx, router.tsx
│       ├── api/               # fetch wrappers + TanStack Query hooks
│       ├── realtime/          # WebSocket provider, event → cache updates
│       ├── auth/              # Google button, AuthGuard, RoleGuard
│       ├── pages/             # Login, Onboarding, Requester*, Helper*, Coordinator, Settings
│       ├── components/        # Map, HazardBanner, PriorityBreakdown, VoiceRecorder, ...
│       ├── hooks/             # useGeolocationStream, useAudioPlayer
│       └── lib/               # types.ts (mirror backend models), constants
└── docs/
    ├── muse-api.md            # [HUMAN] paste Muse API docs here
    └── demo-script.md
```

---

## 3. Environment variables (`.env.example`)

```
# Backend
MONGODB_URI=                      # [HUMAN] Atlas SRV string
MONGODB_DB=mesh
JWT_SECRET=                       # long random string
JWT_TTL_HOURS=24
GOOGLE_CLIENT_ID=                 # [HUMAN] OAuth Web client ID
COOKIE_SECURE=false               # true in prod
DEMO_LOGIN=false                  # true only for local/demo; enables seeded-user login
COORDINATOR_INVITE_CODE=          # [HUMAN] choose a code
NWS_USER_AGENT=(Mesh, team-email@example.com)   # [HUMAN] real contact email
MUSE_API_KEY=                     # [HUMAN]
MUSE_BASE_URL=https://api.meta.ai/v1          # docs/muse-api.md
MUSE_TEXT_MODEL=muse-spark-1.3                # docs/muse-api.md
MUSE_TRANSCRIBE_MODEL=muse-voice-transcribe-1.0
LLM_PROVIDER=mock                 # mock | muse
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2   # fastembed, local (§0.1)
VECTOR_SEARCH=auto                # auto | atlas | local (§0.1)
ELEVENLABS_API_KEY=               # [HUMAN]
ELEVENLABS_VOICE_ID=              # [HUMAN] pick a multilingual voice
ELEVENLABS_MODEL_ID=eleven_multilingual_v2   # verify against current docs
HAZARD_CACHE_SECONDS=300
DEFAULT_TIMEZONE=America/New_York

# Frontend (Vite, must be prefixed VITE_)
VITE_GOOGLE_CLIENT_ID=
VITE_DEMO_LOGIN=false
```

Never commit `.env`. Add `.env`, `data/raw`, `data/processed`, and `backend/media` to `.gitignore`.

---

## 4. Component: Data preprocessing (`data/`)

**Purpose:** get Georgia census tracts, with EJI scores and geometry, into MongoDB so that any point can be mapped to a tract and its vulnerability percentile without calling an external API.

**Libraries:** `pandas`, `geopandas`, `shapely` (≥2.0, for `make_valid`), `pyyaml`, `pymongo`.

**Inputs [HUMAN]:**
1. The CDC/ATSDR EJI 2024 CSV (Georgia rows, or the national file filtered to state FIPS `13`) goes in `data/raw/`. Verify the download is still available, since some federal environmental datasets changed in 2025.
2. The Census TIGER/Line tract shapefile for Georgia (`tl_2020_13_tract.zip`) goes in `data/raw/`. Use the boundary vintage that matches EJI's tract GEOIDs (2020 tracts expected).

**`eji_columns.yaml`:** maps our field names to EJI column names. The names below are placeholders; open the EJI data dictionary and correct them. Do not assume.
```yaml
geoid: GEOID           # 11-digit tract FIPS as string
eji_rank: RPL_EJI      # overall EJI percentile rank 0-1
climate_rank: null     # EJI + Climate Burden rank column (fill in from dictionary)
env_rank: null         # environmental burden module
svm_rank: null         # social vulnerability module
hvm_rank: null         # health vulnerability module
```

**`prepare_tracts.py` steps:**
1. Read the EJI CSV with `dtype={geoid_col: str}`. Zero-pad GEOID to 11 chars. Filter to GEOIDs starting with `13`.
2. Read the TIGER shapefile and reproject to EPSG:4326.
3. Left-join tracts to EJI on GEOID. **Print the match rate**; it must be > 99%. On failure, print unmatched sample GEOIDs and exit non-zero.
4. Replace EJI sentinel values (e.g., `-999`) with null.
5. Simplify geometries with `simplify(0.0001, preserve_topology=True)`, apply `make_valid`, and keep only Polygon or MultiPolygon. Mongo's 2dsphere index rejects invalid polygons.
6. Write `data/processed/ga_tracts.geojson` with properties `{geoid, eji_rank, climate_rank, env_rank, svm_rank, hvm_rank, name}`.

**`load_tracts.py` steps:**
1. Upsert each feature into `tracts` as `{_id: geoid, geoid, eji_rank, ..., geometry}`.
2. Create a `2dsphere` index on `geometry`.
3. Log inserted and failed counts. Failures should be 0; fix geometry if not.

**At runtime:** `tract_for_point(lon, lat)` runs `tracts.find_one({"geometry": {"$geoIntersects": {"$geometry": {"type": "Point", "coordinates": [lon, lat]}}}})`.

---

## 5. Component: Backend core (FastAPI)

**Libraries:**
- `fastapi`, `uvicorn[standard]`, `pydantic` v2, `pydantic-settings`;
- `pymongo` (≥4.9, using its **async** `AsyncMongoClient`; do not use Motor, which is being deprecated);
- `httpx` (async HTTP for external APIs);
- `google-auth` (ID token verification);
- `pyjwt`;
- `python-multipart` (audio uploads);
- `pytest`, `pytest-asyncio`.

**`main.py` lifespan:**
1. Connect Mongo.
2. Run `ensure_indexes()`.
3. Create the settings documents if missing (weights, sim).
4. Start the change-stream broadcaster task (§10).
5. On shutdown, cancel tasks and close the client.

**Indexes (`db.ensure_indexes`):**

| Collection | Index |
|---|---|
| users | unique `google_sub`; `email` |
| presence | 2dsphere `location`; unique `user_id`; **TTL on `updated_at`, `expireAfterSeconds=120`** |
| requests | 2dsphere `location`; 2dsphere `display_location`; `status`; `requester_id`; `helper_id`; `created_at` |
| messages | `request_id` + `ts` |
| tracts | 2dsphere `geometry` |
| resources | 2dsphere `location` |
| hazard_cache | `_id` (key string); TTL on `fetched_at`, `expireAfterSeconds=HAZARD_CACHE_SECONDS` |

**Error format:** `{"error": {"code": "STRING_CODE", "message": "human text"}}` with the correct HTTP status.

**`/api/health`** returns `{ok, db, llm_provider, sim_active}`.

---

## 6. Component: Authentication and onboarding

**Libraries:** `google-auth`, `pyjwt` (backend); `@react-oauth/google` (frontend).

### Google Cloud setup [HUMAN]
1. Create an OAuth 2.0 Client ID of type "Web application."
2. Set authorized JavaScript origins to `http://localhost:5173` and `https://<domain>.tech`.
3. Set scopes to `openid email profile` only.
4. On the consent screen, while in "Testing" mode, add every teammate and every demo account as test users, or publish the app. Basic scopes don't require verification.

### Flow
1. The frontend renders `<GoogleLogin onSuccess={({credential}) => POST /api/auth/google {credential}} />`.
2. The backend verifies the token with `id_token.verify_oauth2_token(credential, google.auth.transport.requests.Request(), GOOGLE_CLIENT_ID)`, checks the issuer, and reads `sub`, `email`, `name`, `picture`.
3. It upserts the user by `google_sub`, using `$setOnInsert` for defaults (`role: null`, `verified: false`).
4. It issues a JWT `{sub: user_id, exp}` and sets cookie `session` with `httponly`, `samesite=lax`, `secure=COOKIE_SECURE`, `path=/`.
5. It returns `{user, needs_onboarding: role is null}`.
6. The frontend routes to `/onboarding` if onboarding is needed; otherwise it routes to the role's home page.

**Endpoints:**
- `POST /api/auth/google`
- `POST /api/auth/logout` (clears cookie)
- `GET /api/me`
- `POST /api/auth/demo {user_id}`: **only if `DEMO_LOGIN=true`**; otherwise return 404. Lists seeded users via `GET /api/auth/demo-users` under the same flag.

**Dependencies (`deps.py`):**
- `get_current_user`: reads the cookie and decodes the JWT. It returns **401** if either is missing or invalid, and **401** if the user is not found.
- `require_role(*roles)`: returns **403** otherwise.
- `require_onboarded`: returns **409** `ONBOARDING_REQUIRED` if the role is null.

### Onboarding
`POST /api/onboarding` body:
```json
{
  "role": "requester" | "helper" | "coordinator",
  "name": "string",
  "language": "en" | "es" | ...,
  "home_location": {"lat": 0, "lon": 0} ,        // from map pin or geocoded address
  "helper": {"skills": [], "resources": [], "radius_km": 5, "org": "optional"},
  "requester_flags": {"medical_device": false, "mobility": false, "lives_alone": false},
  "invite_code": "only for coordinator"
}
```

**Rules:**
- `coordinator` requires `invite_code == COORDINATOR_INVITE_CODE`; otherwise 403.
- `helper` users are created with `verified: false`. Verification is set only by seed or by a coordinator endpoint: `POST /api/coordinator/verify/{user_id}`.
- `requester_flags` are optional. The UI must explain that they are shared only with a helper who has claimed the user's request.

**Other user endpoints:**
- `PATCH /api/me`: edit the profile and switch the active mode between held profiles (requester ⇄ helper). A user cannot switch to coordinator without the code.
- `POST /api/me/roles`: add the second (requester or helper) profile to the account. `users.roles` holds every profile the user has; `require_role` checks it (see §0.1, "One account, two profiles").
- `POST /api/me/duty {on_duty: bool}`: helpers only.

**Enums:**
- **Skills:** `first_aid`, `cpr`, `nursing`, `chainsaw`, `heavy_lifting`, `driving`, `spanish`, `other_language`, `electrical_safe`, `childcare`, `elder_care`.
- **Resources:** `vehicle`, `truck`, `generator`, `power_bank`, `water`, `food`, `tarp`, `sandbags`, `ac_space`, `n95_masks`, `medical_kit`.

---

## 7. Component: Hazard engine (`services/hazards.py`)

**Libraries:** `httpx` (async, 8 s timeout, one retry).

**Principle:** official NWS alerts come first. Values derived from raw forecasts are only an "elevated" signal, capped at level 2.

### Sources
1. **NWS active alerts:** `GET https://api.weather.gov/alerts/active?point={lat},{lon}`
   - Headers: `User-Agent: {NWS_USER_AGENT}`, `Accept: application/geo+json`.
   - For each feature, read `properties`: `event`, `severity`, `urgency`, `certainty`, `headline`, `description`, `instruction`, `onset`, `expires`, `areaDesc`, `id`.
   - Regional variant for coordinators: `GET https://api.weather.gov/alerts/active?area=GA`.
   - Use `/alerts/active`, not the deprecated `/alerts?active=true`.
2. **Open-Meteo forecast:**
   - URL: `GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_gusts_10m,precipitation&hourly=apparent_temperature,wind_gusts_10m,precipitation&forecast_hours=12&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=America%2FNew_York`
   - Verify parameter names against the Open-Meteo docs.
3. **Open-Meteo air quality:** `GET https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi,pm2_5,pm10,ozone&timezone=America%2FNew_York` (no key).

### Caching
- The cache key is `f"{round(lat,2)},{round(lon,2)}"` (about 1 km).
- Store the combined result in `hazard_cache` with `fetched_at`.
- If a source fails, return the partial result with `sources_failed: [...]`. Never 500 the whole call.

### NWS event → hazard type mapping (case-insensitive substring match)

| Match | type |
|---|---|
| Tornado | `tornado` |
| Severe Thunderstorm | `severe_storm` |
| Flash Flood, Flood | `flood` |
| Excessive Heat, Extreme Heat, Heat Advisory | `heat` |
| Air Quality, Dense Smoke | `air_quality` |
| Winter Storm, Ice Storm, Winter Weather, Freeze, Cold | `winter` |
| Hurricane, Tropical Storm | `tropical` |
| High Wind, Wind Advisory | `wind` |
| anything else | `other` |

**NWS severity → level:** Extreme → 3, Severe → 3, Moderate → 2, Minor → 1, Unknown → 1.

### Derived signals (from `backend/app/hazard_thresholds.yaml`, with a source comment per value)

| Signal | Threshold | Level | Source note |
|---|---|---|---|
| US AQI | 101–150 | 1 | EPA AQI category "Unhealthy for Sensitive Groups" |
| US AQI | 151–200 | 2 | EPA "Unhealthy" |
| US AQI | > 200 | 2 (derived cap) | EPA "Very Unhealthy"/"Hazardous" |
| Wind gust (current or next 12 h) | ≥ 58 mph | 2 | NWS severe thunderstorm wind criterion |
| Apparent temp | ≥ 103 °F | 1 | **Team-chosen elevated threshold, not an NWS criterion.** Heat advisories come from NWS alerts |
| Precip next 12 h | ≥ 2.0 in | 1 | **Team-chosen, editable** |

### Output
```json
{
  "level": 0-3,                        // max over all hazards
  "hazards": [
    {"type": "severe_storm", "level": 3, "source": "NWS", "official": true,
     "event": "Severe Thunderstorm Warning", "headline": "...", "expires": "ISO", "instruction": "..."},
    {"type": "air_quality", "level": 2, "source": "Open-Meteo", "official": false,
     "value": 158, "unit": "US AQI", "category": "Unhealthy"}
  ],
  "likely_needs": ["power", "debris", "respiratory"],
  "current": {"apparent_temperature_f": 88, "wind_gust_mph": 22, "us_aqi": 158, "pm2_5": 61},
  "simulated": false,
  "sources_failed": [],
  "fetched_at": "ISO"
}
```

### Hazard → likely needs (used for requester quick-pick chips and helper prep)

| type | likely_needs |
|---|---|
| tornado, severe_storm, wind | `debris`, `power`, `shelter`, `supplies` |
| flood | `transport`, `supplies`, `shelter` |
| heat | `water`, `cooling`, `welfare_check`, `transport` |
| air_quality | `respiratory`, `supplies` (masks), `welfare_check` |
| winter | `warming`, `power`, `supplies` |
| tropical | union of storm and flood |

### Simulation mode (`routers/sim.py`, coordinator only)
- `GET /api/sim`, `POST /api/sim/activate {scenario_id}`, `POST /api/sim/deactivate`. State lives in `settings` doc `{_id: "sim", active, scenario_id, activated_at}`.
- Scenarios live in `backend/app/scenarios/*.json`. Each file is a list of hazard objects in the output shape above, plus optional `current` overrides.
- The team may replace the synthetic content with a real archived NWS alert. Every scenario file must include `"label": "SIMULATED"`, and its text must not claim to be a live alert.
- Starter scenario: `atl_storm_smoke.json`, a severe thunderstorm warning (level 3) plus AQI 158 (level 2) around the venue.
- While the simulation is active, `get_hazards()` merges scenario hazards into real results and sets `simulated: true`. **The UI must show a persistent "SIMULATED SCENARIO" badge whenever `simulated` is true.**
- Activating or deactivating broadcasts `hazard.updated` over WebSocket.

**Endpoints:**
- `GET /api/hazards?lat=&lon=`
- `GET /api/hazards/region` (coordinator: GA active alerts, normalized, with their geometry if present)

---

## 8. Component: AI layer (`app/ai/`)

**Libraries:** `httpx`, `pydantic` (output validation).

### Provider interface
```python
class LLMProvider(Protocol):
    async def complete_json(self, system: str, user: str, schema: type[BaseModel], temperature: float = 0.2) -> BaseModel: ...
    async def complete_text(self, system: str, user: str, temperature: float = 0.3) -> str: ...
```
- **`MuseProvider`:** implement **only** from `docs/muse-api.md`. Do not invent endpoints, auth headers, or model IDs. The docs show an OpenAI-compatible chat API (`POST {MUSE_BASE_URL}/chat/completions`, `Authorization: Bearer`), so use that format. The MVP uses only `complete_text` (§0.1 normalization).
- **`MockProvider`:** deterministic keyword-based outputs so the whole app works with no API key. Used in tests and when `LLM_PROVIDER=mock`.
- **JSON handling:** ask for JSON only, strip code fences, and validate with pydantic. On failure, retry once with the validation error appended. On a second failure, raise `TriageFallback` so the caller uses rules-only output.

### Uses (all prompts in `prompts.py`)
1. **Triage**, called on request preview and create (§9.2).
2. **Match reason:** one sentence explaining why a helper fits, generated from computed fields only. Template fallback: `"{name} is {dist} away and has {resource}."`
3. **Helper safety notes:** 2–3 bullet points, given the category, hazards, and the fixed safety rules below. Always append these fixed lines regardless of LLM output:
   - flood: "Never drive or walk through floodwater."
   - power / debris: "Stay away from downed power lines; assume they are live."
   - any: "If anyone's life is in danger, call 911."
4. **Translation:** `translate(text, target_lang)` for chat messages and TTS confirmations. Skip the call if the language already matches.
5. **Coordinator situation summary:** the input is a JSON stats object computed by Mongo aggregation (§11). The prompt must say: use only the numbers provided; do not invent figures. Output is 3–5 sentences. Regenerate at most once per 60 s (cache in memory).

---

## 9. Component: Requests (core workflow)

### 9.1 Data model (`requests` collection)
```js
{
  _id, requester_id,
  raw_text, transcript?, language,
  category,               // enum below
  urgency,                // 1-5 final
  urgency_rule_floor,     // 1-5 from rules
  emergency: bool,        // life-threatening keywords hit
  flags: [],              // medical_device, mobility, elderly, lives_alone, infant, language_barrier
  needs: [],              // short strings
  summary,                // one line, AI or fallback
  location: GeoJSON Point,          // exact, NEVER sent to unauthorized viewers
  display_location: GeoJSON Point,  // fuzzed
  tract_geoid, eji_rank,            // eji_rank may be null
  hazard_snapshot: {...}, hazard_level,
  priority, priority_breakdown: {urgency, hazard, eji, wait, weights},
  status,                 // enum below
  helper_id?, claimed_at?, resolved_at?,
  safety_notes: [],
  timeline: [{status, at, by}],
  created_at, updated_at
}
```

- **Categories:** `power`, `water`, `food`, `medical_supplies`, `transport`, `shelter`, `cooling`, `warming`, `debris`, `respiratory`, `welfare_check`, `supplies`, `other`.
- **Statuses:** `OPEN`, `CLAIMED`, `EN_ROUTE`, `ON_SITE`, `RESOLVED`, `ESCALATED`, `CANCELLED`.

### 9.2 Triage pipeline (`services/triage.py`, `services/rules.py`)
1. **Rules first** (English and Spanish keyword and regex lists in `rules.py`):
   - `EMERGENCY` terms (can't breathe / no puedo respirar, chest pain, unconscious, trapped, bleeding heavily, water rising inside, fire) set `emergency=true` and `urgency_rule_floor=5`.
   - `HIGH` terms (oxygen, concentrator, dialysis, insulin, ventilator, wheelchair, bedridden, infant/baby, elderly alone) set floor 4 and add the matching flags.
   - Otherwise the floor is 1.
   - The user's stored `requester_flags` also raise the floor: `medical_device` → 4; `mobility` or `lives_alone` → 3.
2. **LLM** (`complete_json` with the `TriageOutput` schema: `category, urgency 1-5, flags[], needs[], summary, language`). The input is text plus active hazard types.
3. **Merge:**
   - `urgency = max(rule_floor, llm_urgency)`. **The LLM can never lower urgency.**
   - `flags = union`.
   - If the LLM failed: `category = first rule-matched category` or `other`, `summary = raw_text[:120]`.
4. **Two-step UX:**
   - `POST /api/requests/preview {text, lat, lon}` returns the triage + `emergency` + suggested category without saving anything.
   - `POST /api/requests {text, transcript?, lat, lon, category_override?}` saves. `category_override` may change the category but **not** lower urgency.
5. **If `emergency`:**
   - the API response includes `show_911: true`;
   - the frontend shows a full-screen "Call 911 now" interstitial with a `tel:911` button **before** it confirms submission;
   - the request is still saved (urgency 5) so community helpers can assist.

### 9.3 On create, in order
1. Triage (above).
2. `tract_for_point` → `tract_geoid`, `eji_rank` (null if outside Georgia).
3. `get_hazards(lat, lon)` → `hazard_snapshot`, `hazard_level`.
4. `display_location = fuzz(location, request_id)` (§9.5).
5. `priority` and `priority_breakdown` (§9.4).
6. `safety_notes` (AI + fixed lines).
7. Insert with `status=OPEN` and a timeline entry.
8. The response includes a `confirmation_text` translated to the requester's language, which the frontend sends to `/api/voice/speak`.

### 9.4 Priority (`services/priority.py`)
```
u = (urgency - 1) / 4
h = hazard_level / 3
e = eji_rank if not null else 0.5        # breakdown marks "eji_missing": true
w = min(minutes_since_created / 60, 1)   # only while OPEN
priority = W_u*u + W_h*h + W_e*e + W_w*w
defaults: W_u=0.45, W_h=0.20, W_e=0.20, W_w=0.15
```
- Weights live in `settings {_id: "weights"}`. `GET/PUT /api/coordinator/weights`; PUT validates non-negative values and normalizes the sum to 1.
- **Wait time changes over time, so recompute priority at read time** in the feed endpoint, in Python after the query. Persist the stored `priority` on create and on status change.
- `priority_breakdown` includes each raw value, normalized value, weight, contribution, and source label. The UI's "Why this rank?" panel uses it.
- Weights are **designed defaults, not fitted**. The UI and docs must say so.

### 9.5 Location fuzzing (`services/fuzz.py`)
- Deterministic: seed a PRNG with `HMAC-SHA256(server secret, request_id)`. Pick a random bearing and a distance of 300–500 m, and offset the point. The same request always produces the same fuzzed point. The secret matters: request ids are visible to every volunteer, so seeding with the id alone would let anyone replay the generator and subtract the offset.

### 9.6 Viewer-aware serialization (`services/serialize.py`), mandatory
`serialize_request(req, viewer)` returns:

| Viewer | Exact `location` | `requester_flags` / name / phone | Chat |
|---|---|---|---|
| The requester | yes | own | yes |
| Assigned helper (status CLAIMED or later, not CANCELLED) | yes | yes | yes |
| Other helpers | **no** (only `display_location`) | no (category, urgency, summary, needs only) | no |
| Coordinator | **no** (display_location) | no | no |

**Every endpoint and WebSocket event that emits a request must go through this function.** Write tests for each row.

### 9.7 State machine (`services/state.py`)
```
OPEN      → CLAIMED (helper claim) | CANCELLED (requester)
CLAIMED   → EN_ROUTE (helper) | OPEN (helper release) | ESCALATED (helper) | CANCELLED (requester)
EN_ROUTE  → ON_SITE (helper) | OPEN (release) | ESCALATED | CANCELLED (requester)
ON_SITE   → RESOLVED (helper or requester) | ESCALATED
ESCALATED → OPEN (coordinator) | RESOLVED (coordinator)
```
- Invalid transitions return 409 `INVALID_TRANSITION`.
- Every transition appends to `timeline` and sets `updated_at`.
- A release clears `helper_id` and `claimed_at`.

**Claim is atomic:**
```python
find_one_and_update({"_id": id, "status": "OPEN"},
                    {"$set": {"status": "CLAIMED", "helper_id": uid, "claimed_at": now}, "$push": {...}})
```
- A `None` result means 409 `ALREADY_CLAIMED`.
- Unverified helpers cannot claim requests with `urgency >= 4` (403 `VERIFICATION_REQUIRED`).
- A helper can have at most **2** active claims.

### 9.8 Request endpoints

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/api/requests/preview` | requester | no save |
| POST | `/api/requests` | requester | max 1 active (non-terminal) request per requester → 409 |
| GET | `/api/requests/mine` | requester | active + recent |
| GET | `/api/requests/feed?lat&lon` | helper | OPEN requests within `radius_km` via `$geoNear` on `display_location`, priority recomputed, sorted desc, limit 50 |
| GET | `/api/requests/{id}` | per serialize rules | |
| POST | `/api/requests/{id}/claim` | helper | |
| POST | `/api/requests/{id}/status {status}` | per state machine | |
| POST | `/api/requests/{id}/release` | assigned helper | |
| POST | `/api/requests/{id}/escalate {reason}` | assigned helper | |
| POST | `/api/requests/{id}/cancel` | requester | |
| GET | `/api/requests/{id}/matches` | requester, coordinator | top 3 helpers + reasons |
| GET/POST | `/api/requests/{id}/messages` | requester, assigned helper | |

### 9.9 Matching (`services/matching.py`)
1. **Candidates:** `presence` docs with `role=helper`, joined to users with `on_duty=true` and no more than 1 active claim, found via `$geoNear` from the request location. Limit 20.
2. **Keep** those with distance ≤ min(helper `radius_km`, 15 km).
3. **Score each:**
   ```
   score = 0.40*dist_score + 0.35*skill_fit + 0.15*resource_fit + 0.10*verified
   dist_score = 1 - d/max_d
   ```
4. **Category → required skills and resources:**
   - power → generator | power_bank, electrical_safe
   - debris → chainsaw, heavy_lifting, truck
   - transport → vehicle, driving
   - medical_supplies → medical_kit, first_aid | nursing
   - respiratory → n95_masks
   - cooling → ac_space, vehicle
   - water → water, vehicle
   - welfare_check → any
   - (add the rest sensibly)

   A language match counts as a skill match when the requester's language is not `en`.
5. Top 3 get an AI match reason, with the template fallback.

### 9.10 Messages
- `{_id, request_id, from_user_id, text, lang, translated_text?, target_lang?, ts}`.
- On POST, if the recipient's language differs, translate the text and store both. Broadcast `chat.message`.

---

## 10. Component: Realtime (WebSocket + live location)

**Backend libraries:** FastAPI WebSockets and Mongo change streams (Atlas replica set).

**Endpoint:** `GET /ws` (upgrade).
- Authenticate from the `session` cookie. Close with code 4401 if the cookie is invalid.
- In local dev, Vite proxies `/ws` with `ws: true`.

**`ConnectionManager`** (in-memory; a single process is fine):
- `connections: dict[user_id, set[WebSocket]]`
- `request_rooms: dict[request_id, set[user_id]]`. Join automatically on connect for the user's active request(s). Update on claim, release, or cancel.
- Helper area subscriptions come from each helper's latest presence location and `radius_km`.

**Client → server messages:**
```json
{"type": "location", "lat": 33.77, "lon": -84.39, "accuracy": 12}
{"type": "ping"}
```
- On `location`: upsert `presence {user_id, role, location, request_id?, updated_at: now}`.
- Accept only if the user is an on-duty helper or a requester with an active request; otherwise ignore.
- If the user is in a request room, broadcast `location.update {user_id, role, lat, lon}` to the **other party in that room only**.
- Rate limit: drop updates that arrive less than 5 s after the previous one from the same user.

**Server → client events:**

| Event | Payload | Recipients |
|---|---|---|
| `request.created` | serialized request (helper view) | on-duty helpers whose radius contains it |
| `request.updated` | serialized per recipient | request room + helpers whose feeds contain it + coordinators |
| `location.update` | `{user_id, role, lat, lon}` | other party in room |
| `chat.message` | message | request room |
| `hazard.updated` | `{simulated, region_level}` | everyone |
| `summary.updated` | `{text, stats}` | coordinators |
| `pong` | — | sender |

**Change-stream broadcaster:**
1. A lifespan task runs `db.requests.watch(full_document="updateLookup")`.
2. For each insert or update, it computes recipients and emits `request.created` or `request.updated`. Payloads are always serialized per recipient.
3. It wraps the loop in retry with backoff.
4. **Fallback:** if `REALTIME_MODE=poll`, the frontend polls the REST endpoints every 5 s instead. Implement polling first; add WebSockets after milestone M3.

**Frontend (`src/realtime/`):**
- `RealtimeProvider` opens `wss://<host>/ws` (or `ws://` in dev).
- It reconnects with exponential backoff (1 s → 30 s) and sends `ping` every 25 s.
- Incoming events update the TanStack Query cache via `queryClient.setQueryData` / `invalidateQueries`.
- **`useGeolocationStream(enabled)`:**
  - uses `navigator.geolocation.watchPosition({enableHighAccuracy: true, maximumAge: 10000})`;
  - sends at most every 10 s, or when moved > 25 m (haversine);
  - is enabled only for on-duty helpers and for requesters with an active request.
- Geolocation and the microphone require HTTPS; `localhost` is exempt.

---

## 11. Component: Coordinator features

**Endpoints (coordinator role):**
- `GET /api/coordinator/stats`: a Mongo aggregation returning:
  - counts by status and by category;
  - unclaimed counts with urgency ≥ 4, and the oldest unclaimed wait in minutes;
  - requests per tract, with `eji_rank`;
  - the count of requests in tracts where EJI ≥ 0.9;
  - the count of active helpers from presence.
- `GET /api/coordinator/summary`: AI summary from the stats JSON, cached 60 s.
- `GET/PUT /api/coordinator/weights`.
- `POST /api/coordinator/verify/{user_id}`.
- `GET /api/tracts?bbox=minLon,minLat,maxLon,maxLat`: tracts GeoJSON for the choropleth via `$geoIntersects` with a bbox polygon. Limit fields to `geoid` and ranks.
- Sim endpoints (§7).

---

## 12. Component: Voice

### Transcription (Meta: Muse Voice Transcribe) [HUMAN docs]
- `POST /api/voice/transcribe` takes multipart `audio` and returns `{text, language?}`.
- `services/transcribe.py` calls Muse Voice Transcribe **per `docs/muse-api.md` only**.
- Accept `audio/webm` (Chrome/Android) and `audio/mp4` (Safari/iOS). Convert with `ffmpeg` in the backend container **only if** Muse needs a specific format.
- Max 60 s and 10 MB.
- **Fallback chain:**
  1. if Muse is not configured, return 503 `TRANSCRIBE_UNAVAILABLE`;
  2. the frontend then offers the browser Web Speech API (where supported);
  3. then typed input.

### Text-to-speech (ElevenLabs)
- `POST /api/voice/speak {text, language}` returns `audio/mpeg`.
- `services/tts.py` calls ElevenLabs text-to-speech. Expected REST shape (**verify against current ElevenLabs docs**):
  - `POST https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}`
  - header `xi-api-key`
  - body `{text, model_id: ELEVENLABS_MODEL_ID}`
- Use a multilingual model so Spanish works.
- Cache audio on disk at `backend/media/tts/{sha256(text+voice+model)}.mp3`. Max text length 500 chars.
- **Where it's used:**
  - request confirmation;
  - status changes the requester receives ("Marcus is on the way, about 9 minutes");
  - hazard banner read-aloud button.

**Frontend:**
- `VoiceRecorder` uses `MediaRecorder` and picks the first supported mime type from `['audio/webm;codecs=opus','audio/webm','audio/mp4']`.
- It is hold-to-record with a visible timer.
- It sends the recording to `/transcribe`, then shows editable text before preview.
- `useAudioPlayer` plays returned blobs. Show a "Tap to hear" button, because iOS blocks autoplay.

---

## 13. Component: Frontend (Vite + React + TS)

**Libraries:**
- `react`, `react-dom`, `react-router-dom`, `@tanstack/react-query`;
- `@react-oauth/google`;
- `leaflet`, `react-leaflet` (OpenStreetMap tiles with the required attribution);
- `tailwindcss`;
- `zod` (optional, for response validation);
- `date-fns`.

Mobile-first; test at 375 px width.

**`vite.config.ts`** dev proxy:
```ts
server: { proxy: { '/api': 'http://localhost:8000', '/ws': { target: 'ws://localhost:8000', ws: true } } }
```

**Routing and guards:**
- `AuthGuard` loads `/api/me`: 401 → `/login`; role null → `/onboarding`.
- `RoleGuard` redirects to the role's home.
- `fetch` wrapper always uses `credentials: 'include'`, parses the error format, and turns 401 into a logout redirect.

**Pages:**

| Route | Role | Contents |
|---|---|---|
| `/login` | public | Google button; if `VITE_DEMO_LOGIN`, a "Demo login" dropdown of seeded users |
| `/onboarding` | any authed | role cards (requester / helper; coordinator requires code), profile form, home location (map pin or address via `/api/geocode`), role-specific fields |
| `/r` | requester | `HazardBanner` (with read-aloud); big "Get help" button; active request card with status timeline, map showing own location + assigned helper live dot, chat, "Tap to hear" updates; nearby resources list |
| `/r/new` | requester | quick-pick chips from `likely_needs`; `VoiceRecorder` or textarea; Preview → triage card (category editable, urgency shown); 911 interstitial if `emergency`; Submit → plays confirmation audio |
| `/h` | helper | on-duty toggle (starts location stream); map of fuzzed request circles colored by priority; ranked list; `HazardBanner` |
| `/h/req/:id` | helper | summary, needs, flags (after claim), `PriorityBreakdown` ("Why this rank?"), safety notes, Claim button; after claim: exact pin, "Open in Google Maps" directions link (`https://www.google.com/maps/dir/?api=1&destination=lat,lon`), status buttons, release/escalate, chat, requester live dot |
| `/c` | coordinator | map with EJI choropleth (tract fill by `eji_rank`), request markers, active alerts; stats cards; AI summary (auto-refresh); weight sliders (PUT on release); sim toggle + scenario picker; persistent SIMULATED badge |
| `/settings` | any | profile edit, role switch, logout |

**Shared components:**
- `MapView`
- `RequestMarker`
- `HelperDot`
- `HazardBanner` (level colors 0 gray, 1 yellow, 2 orange, 3 red; source tags "NWS (official)" / "Open-Meteo (derived)")
- `SimulatedBadge`
- `PriorityBreakdown` (bar per factor, value, weight, source; footer "Weights are designed defaults, not fitted")
- `StatusTimeline`
- `ChatPanel` (shows the original and translated text)
- `VoiceRecorder`
- `EmergencyInterstitial`
- `ResourceList`

**Types:** `src/lib/types.ts` mirrors the pydantic models exactly. Keep them in sync.

---

## 14. Rules for Claude Code (non-negotiable)

1. **Don't invent API specs.** For Muse, only implement from `docs/muse-api.md`. For ElevenLabs, Open-Meteo, NWS, and the Census geocoder, follow this plan, and if a response shape differs, adapt the parser and note it. Don't fabricate fields.
2. **Don't invent data.**
   - EJI column names come from the data dictionary.
   - Shelter, cooling-center, and charging locations in `resources` are **[HUMAN]**-supplied. Seed data may use obviously fake names ("Demo Community Center A") at plausible coordinates, flagged `demo: true`.
   - Never present fake resources as real.
3. **Numbers come from code, not the LLM.** The LLM may classify, explain, translate, and summarize given numbers. It never produces priority, hazard levels, distances, counts, or EJI values.
4. **The LLM can never lower urgency** below the rules floor.
5. **Location privacy:** every request that leaves the backend goes through `serialize_request`. Tests must cover each viewer row.
6. **Emergency path:** emergency keywords always trigger the 911 interstitial, even when the LLM is down.
7. **Simulation is always labeled** in the UI and in API responses.
8. **No secrets in code or git.** Use `.env` only.
9. **`DEMO_LOGIN` endpoints return 404** unless the flag is true.
10. **Stay in scope.** No features beyond this plan without team approval. Mark stretch items as stretch.
11. Keep the app working with `LLM_PROVIDER=mock` and no ElevenLabs key: graceful degradation everywhere.

---

## 15. Seed script (`backend/app/seed.py`)

`python -m app.seed --reset` does the following:
- Deletes only documents flagged `demo: true`.
- Creates:
  - **8 helpers** within 3 km of (33.7756, -84.3963):
    - varied skills and resources (at least one with a generator, one Spanish speaker, one with a truck + chainsaw, one nurse);
    - 6 verified and 2 unverified;
    - all on duty, with presence docs (refresh `updated_at` so TTL doesn't expire them; add `--keepalive` to refresh every 60 s during the demo).
  - **12 requesters with 12 OPEN requests** across categories and urgencies, including one Spanish-language medical-device power request. Triage runs through the normal pipeline (MockProvider is fine).
  - **1 coordinator.**
  - **4 demo resources** (fake names, `demo: true`).
- All seeded users use `google_sub: "demo-<n>"` and are available through demo login.

---

## 16. Deployment (Vultr + Caddy + .tech)

**The runbook is `docs/DEPLOY.md`; the scripts are `deploy/bootstrap-vm.sh` (once per VM) and `deploy/deploy.sh` (every deploy). Summary of what is built:**

**`docker-compose.yml`:**
- `backend`: build `./backend`; `env_file: .env`; a named volume for `/app/media`; a healthcheck on `/api/health`. The image runs as a normal user, pre-downloads the fastembed model at build time (`FASTEMBED_CACHE_PATH=/opt/fastembed`), and starts uvicorn with `--proxy-headers`. No port is published; only Caddy reaches it.
- `caddy`: built from `deploy/Caddy.Dockerfile`, a multi-stage build that compiles the frontend (the `VITE_*` values are build args read from `.env`) and copies `dist` into the `caddy:2` image, so the VM needs no Node and no committed `frontend/dist`. Ports 80, 443 and 443/udp; volumes for Caddy data and config (certificates); waits for a healthy backend.

**`deploy/Caddyfile`:** the domain comes from `SITE_DOMAIN` (default `mesh-together.tech`; `localhost` gives a local test certificate). It gzips, adds `X-Content-Type-Options`, `Referrer-Policy` and a short HSTS, proxies `/api/*` and `/ws` to `backend:8000`, serves the SPA with `try_files {path} /index.html` (hashed `/assets/*` cached for a year, the page itself `no-cache`), and redirects `www` to the bare domain.

**Steps [HUMAN where noted]:**
1. Create a Vultr Ubuntu VM (smallest plan is fine). Install Docker and the compose plugin. Open ports 80 and 443 in the firewall.
2. **[HUMAN]** Register the .tech domain and point an A record (`@`) at the VM's IP.
3. **[HUMAN]** In Atlas Network Access, allow the VM's IP.
4. Create `.env` from `deploy/env.production.example` (no inline comments, `COOKIE_SECURE=true`), then `bash ./deploy/deploy.sh`. It refuses unsafe settings, builds both images (the frontend with the `VITE_*` values baked in), and waits for a healthy backend. Caddy obtains HTTPS certificates automatically.
5. Set `COOKIE_SECURE=true` and `DEMO_LOGIN` as desired. Add the production origin to the Google OAuth client.
6. **Smoke test on a real phone over cellular:** login, microphone, geolocation, WebSocket connection, audio playback.

---

## 17. Testing

**Backend (pytest):**
- state machine (all valid and invalid transitions);
- atomic claim (race between two helpers → one 409);
- verified-claim rule;
- priority math and weight normalization;
- rules floor (EN and ES), with the LLM unable to lower urgency;
- fuzz determinism and a 300–500 m distance range;
- `serialize_request` for every viewer row;
- hazard mapping and threshold levels (using fixture JSON for NWS and Open-Meteo);
- `DEMO_LOGIN` 404 when off.

**Manual end-to-end checklist (three browsers or phones: requester, helper, coordinator):**
1. Google login → onboarding for each role.
2. Coordinator activates the simulation → banners update everywhere with the SIMULATED badge.
3. Requester records a Spanish voice request → transcript → preview → submit → confirmation audio.
4. The helper feed shows it at the top with a breakdown → claim → exact pin appears → EN_ROUTE → requester sees the live helper dot and hears the status audio.
5. Translated chat both ways.
6. ON_SITE → RESOLVED; the coordinator summary updates.
7. An emergency phrase triggers the 911 interstitial with `LLM_PROVIDER=mock`.

---

## 18. Milestones (build order)

> **Post-MVP.** Build §0.1 first. These milestones describe the full target and apply after the MVP works.

Times assume a Sunday ~9 AM ET deadline. **[HUMAN] Confirm the real cutoff.**

| # | Target | Deliverable | Done when |
|---|---|---|---|
| M0 | Sat 3 PM | Repo scaffold, `.env.example`, Vite + FastAPI running, dev proxy, Mongo connection, indexes, `/api/health` | health returns `db: ok` |
| M1 | Sat 5 PM | Google auth + JWT cookie + onboarding + guards + demo login; `data/` pipeline loads GA tracts | login → onboarding → role home works; `tract_for_point` returns the venue tract |
| M2 | Sat 7 PM | Hazards service (NWS + Open-Meteo + AQ + cache) + sim mode; requests create (rules-only triage), feed, claim, status, fuzzing, serialization; frontend requester and helper flows with **polling** | **Checkpoint 1:** request → helper feed → claim → status visible to requester |
| M3 | Sat 11 PM | AI layer (Muse or mock), triage merge, priority + breakdown UI, matching + reasons, safety notes, voice transcribe + ElevenLabs TTS, 911 interstitial, seed script | **Checkpoint 2:** full demo path works locally |
| M4 | Sun 1 AM | WebSocket realtime + live location + change streams; Vultr deploy with HTTPS on the domain | works on phones over HTTPS |
| M5 | Sun 5 AM | Coordinator dashboard (choropleth, stats, AI summary, weight sliders), chat translation, polish | — |
| Freeze | Sun 6 AM | Bug fixes only | — |
| Submit | Sun 8:30 AM | Meta video recorded (problem 30 s / demo 90 s / AI role 30 s / tools 30 s), Devpost with one section per prize | submitted |

**If behind schedule, cut in this order:**
1. coordinator weight sliders;
2. chat translation;
3. change streams (keep WebSocket for location only, poll requests);
4. coordinator dashboard (keep only the sim toggle).

**Never cut:** auth, the request lifecycle, the hazard banner, AI triage, the 911 path, the privacy serializer, or sim mode.

---

## 19. How the components work together (end-to-end)

1. **Sign-in:** Google button → ID token → `/api/auth/google` verifies it → Mongo `users` upsert → JWT cookie → onboarding sets role and profile → role home.
2. **Hazard context:** the page loads → `/api/hazards?lat&lon` → cache check → NWS alerts + Open-Meteo forecast + AQ in parallel → normalized levels + `likely_needs` → banner and quick-pick chips. A coordinator's sim toggle merges the scenario and broadcasts `hazard.updated`.
3. **Request:**
   1. voice → MediaRecorder → `/api/voice/transcribe` (Muse) → text;
   2. `/api/requests/preview` → rules floor + Muse triage → merged urgency;
   3. 911 interstitial if needed;
   4. `/api/requests` → tract lookup (`$geoIntersects`) + EJI rank + hazard snapshot + fuzz + priority → insert;
   5. confirmation → `/api/voice/speak` (ElevenLabs) → audio.
4. **Dispatch:**
   1. the change stream sees the insert → `request.created` to on-duty helpers in radius (helper view, fuzzed);
   2. the helper feed re-ranks with live wait time;
   3. the helper opens the detail → breakdown + match reason + safety notes → atomic claim → room joined → exact location unlocked for that helper only.
5. **En route:** the helper's phone streams location over `/ws` → `presence` upsert (TTL) → `location.update` to the requester only. Status changes trigger `request.updated` + a spoken update for the requester. Chat is translated between languages.
6. **Oversight:** the coordinator sees stats (Mongo aggregation) + AI summary (numbers from the aggregation only) + the EJI choropleth. The coordinator can adjust priority weights, verify helpers, and handle escalations.

---

## 20. Open items for the team [HUMAN]

- [ ] Confirm HackGT 13 submission deadline and Devpost requirements.
- [ ] Paste Muse Spark and Muse Voice Transcribe API docs into `docs/muse-api.md`; redeem $50 credits (each teammate).
- [ ] Create the Google OAuth client; add test users.
- [ ] Get the ElevenLabs API key; choose a multilingual voice ID.
- [ ] Create the Atlas cluster and user; allow the Vultr IP.
- [ ] Register the .tech domain; create the Vultr VM.
- [ ] Download the EJI 2024 CSV and GA TIGER tracts into `data/raw/`; fill `eji_columns.yaml` from the data dictionary.
- [ ] (Optional) Supply real Atlanta shelter or cooling-center locations with sources.
- [ ] Set the NWS User-Agent contact email and the coordinator invite code.

---

## 21. Backlog (iteration 2+)

These build on the MVP (§0.1). Both specs below came from judge feedback. They are **not** in the MVP. All §14 rules apply.

### 21.1 AI-driven helper matching v2
Extends §9.9 and the §0.1 similarity ranking.
1. **Hard filters (code):** on duty, within radius, fewer than 2 active claims, verified if urgency ≥ 4.
2. **Retrieve:** top ~10 candidates by embedding similarity between the request's needs and helper profiles (Atlas Vector Search, §0.1).
3. **LLM rerank (Muse Spark, structured JSON).** Per candidate, it returns which request needs they cover and a short reason. If no single helper covers all needs, it may propose a 2-helper team. **The LLM outputs rankings and coverage only**, never distances or priority numbers.
4. **Validate (code):**
   - every `helper_id` must be in the candidate list;
   - re-check the hard filters;
   - on any failure, fall back to the deterministic §9.9 score.
5. **Fairness:** penalize helpers who already have an active claim.
6. **Push model:**
   - Send the top match a `match.suggested` WebSocket event with accept/decline.
   - On decline or a 5-minute timeout, offer to the next candidate.
   - Helpers can still browse the feed.
7. **UI:** a need-coverage checklist per matched helper and a "Matched by AI" reason.
8. **Evaluation (`backend/eval/matching_eval.py`):**
   - ~30 synthetic requests, ~15 helpers, and a human-labeled best-helper file (labels are `TODO(HUMAN)`).
   - Reports top-1 and top-3 agreement for formula vs embeddings vs embeddings + LLM.

### 21.2 Social-media leads (synthetic only)
- **No real scraping.**
  - A `SourceAdapter` interface with a `SyntheticSource` implementation only.
  - Every lead has `synthetic: true` and shows a SYNTHETIC badge.
- **Leads are not requests.**
  - They're stored in a `leads` collection visible only to coordinators, with minimal fields and a TTL expiry of 48 h.
  - Helpers never see raw post text or handles.
  - The TTL is data minimization; classification never deletes anything.
- **Classifier labels:** `genuine_request`, `offer_to_help`, `scam`, `spam_bot`, `misinfo_rumor`, `not_actionable`, `duplicate`, plus confidence and reasons.
- **Signals:**
  - content (money vs goods, payment handles, links, templates);
  - near-duplicate detection across accounts via embeddings;
  - plausibility vs current hazard data (a feature, never a veto);
  - simulated account metadata.
- **Buckets:** `surface`, `needs_review`, `suppressed` (logged and reviewable). No auto-delete.
- **Conversion:**
  - A coordinator must confirm a lead (simulated "contacted and confirmed") before it converts to a normal request via the existing pipeline.
  - Social-sourced requests are claimable only by verified helpers.
  - Strip payment handles and URLs from displayed text. Mesh never facilitates money transfer.
- **Untrusted input:** delimit post text, force structured output, and never let it set fields directly. The dataset includes prompt-injection samples.
- **Dataset (`backend/eval/social_posts.jsonl`):**
  - Mixes template-generated, LLM-generated, and `TODO(HUMAN)` hand-written posts.
  - Includes hard cases: genuine posts mentioning money, lure scams without payment info, sarcasm, Spanish, informal and typo-heavy writing.
  - Has a held-out test split.
- **Eval script** prints:
  - a confusion matrix;
  - precision and recall for `scam` and `genuine_request`;
  - the false-positive rate by writing-style tag;
  - a keyword-rules baseline for comparison.
- **Coordinator UI:** a leads queue with label, confidence, reasons, bucket, and confirm/dismiss actions.

### 21.3 Deferred from the full plan
Everything in §§4–13 not listed in §0.1 or Iteration 2:
- simulation mode (hazards, EJI, tracts, location, fuzzing and maps moved to Iteration 2);
- triage category/urgency and priority;
- voice (transcribe and TTS);
- the coordinator dashboard;
- WebSocket realtime and change streams;
- chat translation;
- verified-helper rules;
- deploy.

If time is short, cut coordinator weight sliders and chat translation first.
