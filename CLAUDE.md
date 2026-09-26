# CLAUDE.md: Mesh

Mesh is a mobile-first web app for weather-disaster relief, built at HackGT 13. It works like a delivery app for help:

- Requesters ask for help by voice or text.
- AI triages each request.
- Verified volunteer helpers nearby claim requests and update their status.
- Coordinators oversee the region.

Priority combines AI triage, live hazards (NWS + Open-Meteo), and CDC EJI tract vulnerability.

"Mesh" means a human mesh of neighbors. **It is not offline or peer-to-peer mesh networking.** Never describe it that way.

**`PLAN.md` is the source of truth.** Read it in full before starting work, and re-read the relevant section before each task. If this file and `PLAN.md` disagree, `PLAN.md` wins.

---

## Stack

- **Frontend:** Vite + React + TypeScript, react-router-dom, TanStack Query, react-leaflet (OSM tiles), Tailwind, @react-oauth/google
- **Backend:** FastAPI, pydantic v2, pydantic-settings, PyMongo async (`AsyncMongoClient`; not Motor), httpx, google-auth, PyJWT
- **Database:** MongoDB Atlas (2dsphere, TTL indexes, change streams)
- **AI:** Muse Spark + Muse Voice Transcribe behind `LLMProvider` (`LLM_PROVIDER=mock|muse`)
- **TTS:** ElevenLabs
- **Deploy:** Vultr VM, Docker Compose, Caddy (HTTPS, same domain for SPA + `/api` + `/ws`)

## Layout

`frontend/` · `backend/app/` (routers, services, ai, scenarios, seed.py) · `data/` (EJI + TIGER → Mongo) · `deploy/` · `docs/` (muse-api.md). Full tree is in PLAN.md §2.

## Commands

```bash
# backend (from backend/)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q
python -m app.seed --reset            # demo data (add --keepalive during demos)

# data (from data/)
python prepare_tracts.py && python load_tracts.py

# frontend (from frontend/)
npm install
npm run dev                            # :5173, proxies /api and /ws to :8000
npm run build && npm run typecheck && npm run lint

# deploy (repo root, on the VM)
docker compose up -d --build
```

If a command above doesn't exist yet, create the script when you scaffold. Keep this section accurate.

---

## Hard rules (see PLAN.md §14)

1. **Never invent API specs.**
   - Muse: implement only from `docs/muse-api.md`. If that file is missing, use `MockProvider` and leave a `TODO(HUMAN)`.
   - ElevenLabs, NWS, Open-Meteo, Census: follow PLAN.md. If a real response differs, adapt the parser and note the difference in the PR or commit message.
2. **Never invent data.**
   - EJI column names come from the data dictionary via `data/eji_columns.yaml`.
   - Seed resources use obviously fake names and are flagged `demo: true`.
   - Never present fake locations as real.
3. **Numbers come from code, not the LLM.** The LLM classifies, explains, translates, and summarizes numbers it's given. It never outputs priority, hazard levels, distances, counts, or EJI values.
4. **The LLM can never lower urgency.** Final urgency is `max(rule_floor, llm_urgency)`. Category overrides can't lower it either.
5. **Location privacy:** every request leaving the backend (REST or WebSocket) goes through `serialize_request(req, viewer)`. Exact location goes only to the requester and the assigned helper. Tests cover every viewer type.
6. **Emergency path:**
   - Emergency keywords (EN + ES) always set `emergency=true` and trigger the 911 interstitial, even when the LLM is down.
   - Mesh is not a 911 replacement.
7. **Simulation is always labeled.** API responses include `simulated: true`, and the UI shows a persistent SIMULATED badge.
8. **No secrets in code or git.** Use `.env` only, and keep `.env.example` current when adding variables.
9. **`DEMO_LOGIN` routes return 404** unless the flag is true.
10. **Degrade gracefully.** The app must run with `LLM_PROVIDER=mock` and no ElevenLabs key.
11. **Stay in scope.** Don't add features that aren't in PLAN.md. Ask first, or mark them as stretch.

## Conventions

- **Backend:** type hints everywhere. Routers stay thin; logic lives in `services/`.
- **Errors:** use the error shape `{"error": {"code", "message"}}`.
- **External HTTP:** use async `httpx` with an 8 s timeout and one retry. Partial hazard results are fine; never 500 the whole call.
- **Time and coordinates:** UTC datetimes in Mongo, ISO strings in the API. GeoJSON coordinates are always `[lon, lat]`; the API accepts `{lat, lon}`. Don't mix them up.
- **Shared types:** `frontend/src/lib/types.ts` mirrors the backend pydantic models. Update both together.
- **Frontend fetches** use `credentials: 'include'`. A 401 redirects to `/login`.
- **Mobile-first:** test at 375 px. Microphone and geolocation need HTTPS (localhost is exempt).
- **Realtime:** implement polling first. Switch to WebSocket + change streams only after milestone M3 works.
- **Tests:** add or update pytest tests for the state machine, claim race, priority, rules floor, fuzzing, serializer, and hazard mapping whenever you touch them.

## Workflow

- Build in the PLAN.md §18 milestone order (M0 → M5). Don't start a milestone until the previous one's "done when" check passes.
- After each milestone:
  1. run backend tests and the frontend typecheck;
  2. summarize what works and what's stubbed;
  3. list any `TODO(HUMAN)` items.
- Mark human-dependent gaps with `TODO(HUMAN): <what's needed>`. Don't guess.
- Small, focused commits with clear messages.
- If time is short, cut in the PLAN.md §18 order. Never cut: auth, the request lifecycle, the hazard banner, AI triage, the 911 path, the privacy serializer, or sim mode.
