# Onboarding: Mesh (HackGT 13)

Welcome. This file covers getting set up (about 20 minutes) and who owns what for the rest of the hackathon. **[PLAN.md](PLAN.md) is the spec** and CLAUDE.md holds the rules. Skim both before writing code.

---

## Part 1: Get set up

### 1. Access (ask Chris)
- [ ] Collaborator access to `github.com/lyonstran/Mesh`
- [ ] Added as a **test user** on the Google OAuth consent screen (login won't work without this)
- [ ] The team `.env` values, sent over DM. **Never commit `.env`, and never paste it in a public channel.**
- [ ] Your IP allowed in MongoDB Atlas → Network Access. Venue Wi-Fi IPs change, so for the hackathon we may allow `0.0.0.0/0` with a strong DB password and remove it after the event.

### 2. Install prerequisites
- Git
- Python **3.12+** (3.13 recommended; the Docker image uses 3.13)
- Node **20.19+** (22 or 24 is fine)
- [Claude Code](https://claude.com/claude-code) (recommended)

### 3. Clone and configure
```bash
git clone https://github.com/lyonstran/Mesh.git
cd Mesh
cp .env.example .env        # paste in the values Chris sends you
```
In your `.env`, set **`MONGODB_DB=mesh_<yourname>`** (e.g. `mesh_alex`). Each of us gets a private dev database, so `python -m app.seed --reset` never wipes a teammate's data. The shared `mesh` database is for integration and the demo.

### 4. Run the backend (terminal 1)
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate          # Windows (Git Bash)
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### 5. Run the frontend (terminal 2)
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

### 6. Verify
- [ ] http://localhost:5173 shows **Database: ok**
- [ ] `cd backend && pytest -q` passes
- [ ] `cd frontend && npm run typecheck && npm run lint` passes

If the database shows `error`, the usual cause is that your IP isn't allowed in Atlas or `MONGODB_URI` is wrong. The backend log shows the exact error.

### 7. Personal tasks
- [ ] Redeem your **$50 Muse credits** (PLAN.md §20)
- [ ] Read PLAN.md §14 (the non-negotiable rules) and your lane below

### Working with Claude Code
CLAUDE.md loads automatically. Start each task with something like:

> Read PLAN.md and ONBOARDING.md. I'm Lane B. Do task B2. Stay inside my lane's files; if you need to change a shared file, keep the change minimal and tell me.

Claude Code will leave `TODO(HUMAN)` markers where it needs keys, docs, or data. Don't let it guess API specs (rule §14.1).

---

## Part 2: How we split the work

Four lanes, split by **file ownership** so we rarely edit the same files. Lanes own full-stack slices where that makes sense: Lane A owns realtime on both ends, and Lane D builds the hazard and coordinator UI on top of its own data. That keeps Lane C's frontend load manageable.

| Lane | Focus | Suggested owner |
|---|---|---|
| **A: Platform** | auth and onboarding API, seed data, voice services, realtime (backend + frontend), deploy, coordinator API | Chris (holds the keys, Atlas, and Vultr) |
| **B: Requests core** | data models, state machine, fuzzing, priority, privacy serializer, request endpoints, matching, chat | Teammate 1 |
| **C: Requester & helper UI** | routing, login, onboarding, requester and helper pages, voice recording and playback UI, 911 screen | Teammate 2 |
| **D: Hazards, AI & data** | tract data, triage rules, hazards and sim mode, AI layer, hazard banner, coordinator dashboard UI | Teammate 3 |

### Interfaces between lanes (agree on these early)
- **B → everyone:** `models.py` + `frontend/src/lib/types.ts`, first version merged by **~4:15 PM**.
- **D → B:** `services/triage.py` exposes a rules-only triage by M2 and the full LLM merge by M3. B's create and preview endpoints call it; D owns what's inside.
- **D → B:** `tract_for_point(lon, lat)` and `get_hazards(lat, lon)` for the request create pipeline (PLAN.md §9.3).
- **A → C:** `deps.py` guards and the `/api/me` shape by M1; `RealtimeProvider` by M4. C's pages consume them.
- **D → C:** `HazardBanner` and `SimulatedBadge` components, which C drops into the `/r` and `/h` pages.

### Task list by milestone

Deadlines from PLAN.md §18 (Saturday → Sunday). Each milestone ends with a **10-minute all-hands integration check** (see "Sync points" below).

#### M1: due Sat 5 PM (auth, onboarding, tract data)
| Lane | Tasks | Main files |
|---|---|---|
| A | **A1** Google auth, JWT cookie, `/api/me`, logout, demo login behind `DEMO_LOGIN` (404 when off) · **A2** onboarding + `PATCH /api/me` + duty toggle + invite code check · tests | `routers/auth.py`, `routers/users.py`, `security.py`, `deps.py` |
| B | **B1 (first 30 min, then open a PR right away)** `models.py` enums and pydantic models + matching `types.ts` · **B2** pure logic with tests: `state.py`, `fuzz.py`, `priority.py`, `serialize.py` (every viewer row) | `models.py`, `services/{state,fuzz,priority,serialize}.py` |
| C | **C1** router, `AuthGuard`/`RoleGuard`, 401 → `/login` in the fetch wrapper · **C2** Login page (Google button + demo dropdown), Onboarding page (role cards, profile, map pin, role fields, flags privacy note) · Leaflet `MapView` base | `frontend/src/{auth,pages,components}` |
| D | **D1** `data/prepare_tracts.py` + `load_tracts.py` + `tract_for_point` · **D2** `rules.py` (EN + ES emergency/high keyword lists, flag detection, rule floor) with tests | `data/`, `services/{rules,geocode}.py` |

**Done when:** login → onboarding → role home works, and `tract_for_point` returns the venue tract.

#### M2: due Sat 7 PM (Checkpoint 1: core loop with polling)
| Lane | Tasks |
|---|---|
| A | **A3** `/api/geocode` (Census geocoder) · coordinator `POST /verify/{user_id}` · help B test the claim flow across two logged-in users |
| B | **B3** `routers/requests.py`: create (rules-only triage) → tract → hazards → fuzz → priority → insert; `/mine`, `/feed` (`$geoNear`, priority recomputed), `/{id}`, claim (atomic, verified rule, max 2), status/release/cancel/escalate · claim-race test |
| C | **C3** requester `/r` + `/r/new` (text only for now), helper `/h` (map + ranked list + on-duty toggle) + `/h/req/:id` (claim, status buttons, Google Maps link), 5 s polling, `StatusTimeline` |
| D | **D3** `services/hazards.py` (NWS + Open-Meteo + AQ, cache, partial failures), `hazard_thresholds.yaml`, `/api/hazards`, fixture tests · **D4** sim mode + `atl_storm_smoke.json` (labeled SIMULATED) · `HazardBanner` + `SimulatedBadge` components |

**Done when:** a request goes to the helper feed, gets claimed, and the requester sees the status change.

#### M3: due Sat 11 PM (Checkpoint 2: full demo path, local)
| Lane | Tasks |
|---|---|
| A | **A4** `seed.py` (8 helpers, 12 requests incl. a Spanish medical-device one, 1 coordinator, 4 fake `demo: true` resources, `--keepalive`) · **A5** voice backend: `services/tts.py` (ElevenLabs + disk cache), `services/transcribe.py` (Muse, 503 fallback), `routers/voice.py` |
| B | **B4** `matching.py` + `/matches` (scoring, category → skills/resources, language match), using D's match-reason function with template fallback · `resources` endpoint for the nearby list |
| C | **C4** `EmergencyInterstitial` (tel:911), triage preview card (editable category), `PriorityBreakdown` ("designed defaults, not fitted") · **C5** `VoiceRecorder`, `useAudioPlayer` ("Tap to hear"), Web Speech fallback, confirmation audio |
| D | **D5** `ai/` provider protocol, `MockProvider`, `MuseProvider` (from `docs/muse-api.md` only), JSON retry → `TriageFallback` · **D6** triage LLM merge (can't lower urgency), `/preview` wiring with B, `show_911`, safety notes (+ fixed lines), `confirmation_text`, match-reason prompt |

#### M4: due Sun 1 AM (realtime + deploy)
| Lane | Tasks |
|---|---|
| A | **A6** `/ws` + `ConnectionManager` + presence upserts + change-stream broadcaster (always serialized per recipient) · `RealtimeProvider` + `useGeolocationStream` on the frontend · **A7** Vultr VM, Docker Compose, Caddy, .tech DNS, HTTPS, prod OAuth origin |
| B | **B5** messages endpoints + translation on send · audit every REST/WS path for `serialize_request` · fill test gaps (PLAN.md §17) |
| C | **C6** live helper/requester dots on maps, `ChatPanel` (original + translated), spoken status updates for the requester |
| D | **D7** `translate()` for chat and TTS (skip when the language already matches) · triage prompt tuning with real Muse · `/api/hazards/region` for coordinators |

**Done when:** it works on phones over HTTPS (cellular smoke test, PLAN.md §16.6).

#### M5: due Sun 5 AM (coordinator + polish)
| Lane | Tasks |
|---|---|
| A | **A8** `/api/coordinator/stats` (aggregation), weights GET/PUT (normalize), `/api/tracts?bbox` |
| B | **B6** end-to-end test pass (PLAN.md §17 manual checklist) and bug fixing across the request lifecycle |
| C | **C7** `/settings` page · 375 px polish pass across all requester and helper pages |
| D | **D8** coordinator AI summary (numbers from stats only, 60 s cache) · `/c` dashboard: EJI choropleth, markers, alerts, stats cards, summary, weight sliders, sim toggle + scenario picker |

**Freeze 6 AM:** bug fixes only. **Submit by 8:30 AM:** Chris records the Meta video; each lane writes the Devpost sections for the sponsor tech it built (A: Vultr, MongoDB, .tech, ElevenLabs; B: privacy and matching design; C: UX and the voice experience; D: Muse Spark, Muse Voice, hazard data).

If we fall behind, cut in PLAN.md §18 order: weight sliders → chat translation → change streams → coordinator dashboard. **Never cut:** auth, the request lifecycle, the hazard banner, AI triage, the 911 path, the privacy serializer, or sim mode.

### Human (non-code) tasks by owner
| Owner | Task |
|---|---|
| A | Atlas cluster + user + IP allowlist, Google OAuth client + test users, .tech domain, Vultr VM, ElevenLabs key + multilingual voice ID, NWS User-Agent email, coordinator invite code, confirm the real deadline |
| B | Write `docs/demo-script.md` from the PLAN.md §17 checklist |
| C | Line up two phones (one iOS, one Android) for the M4 cellular smoke test |
| D | Download EJI 2024 CSV + GA TIGER tracts into `data/raw/`, fix `data/eji_columns.yaml` from the data dictionary, paste Muse docs into `docs/muse-api.md` |

---

## Part 3: Working together

### Git workflow
- Branch per task: `a/auth`, `b/state-machine`, `c/onboarding`, `d/hazards`. Never push directly to `main`.
- Open small PRs. Before merging: `pytest -q` and `npm run typecheck` pass, and one teammate glances at it (a 2-minute review is fine).
- Pull or rebase on `main` at least every hour. Merge early; long-lived branches hurt.

### Shared files (where conflicts happen)
| File | Rule |
|---|---|
| `backend/app/models.py` + `frontend/src/lib/types.ts` | Lane B lands the first version by ~4:15 PM. After that anyone may add to them, but change **both files in the same PR**. |
| `backend/app/services/triage.py` | Lane D owns it. Lane B calls it and doesn't edit it; ask D for changes. |
| `backend/app/main.py` | Only add your `include_router` line. |
| `frontend/src/router.tsx` | Lane C owns it. Lane D adds only the `/c` route. |
| `requirements.txt` / `package.json` | Add dependencies in your PR. After a rebase, re-run `npm install` so the lockfile is regenerated rather than hand-merged. |
| `.env.example` | Add every new variable here (without a value) and tell the team. |

### Not blocking each other
- **The API contract is PLAN.md.** Frontend work (C, and D's dashboard) builds against the shapes in PLAN.md §6–§11 using hardcoded sample data, then swaps in the real endpoint when it merges.
- Lanes B and D write logic in `services/` as pure functions with tests, so that work doesn't need auth or the frontend to be done.
- Until D's triage lands, B can stub it with a function that returns urgency 1 and category `other`.
- If you're blocked for more than 15 minutes, say so in the team chat.

### Sync points
At **5 PM, 7 PM, 11 PM, 1 AM, and 5 AM**, spend 10 minutes together: merge everything to `main`, run the milestone's "done when" check on one machine, and re-split anything that's behind.
