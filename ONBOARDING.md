# Onboarding: Mesh (HackGT 13)

Welcome. This file covers getting set up (about 20 minutes), trying the MVP, and who owns what next. **[PLAN.md](PLAN.md) is the spec** (start with **§0.1, the MVP**) and CLAUDE.md holds the rules. Skim both before writing code.

---

## Part 1: Get set up

### 1. Access (ask Chris)
- [ ] Collaborator access to `github.com/lyonstran/Mesh`
- [ ] Added as a **test user** on the Google OAuth consent screen (Google login won't work without this; demo login works regardless)
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
In your `.env`:
- Set **`MONGODB_DB=mesh_<yourname>`** (e.g. `mesh_alex`). Each of us gets a private dev database, so `python -m app.seed --reset` never wipes a teammate's data. The shared `mesh` database is for integration and the demo.
- Set **`DEMO_LOGIN=true`** and **`VITE_DEMO_LOGIN=true`** for local work, so you can sign in as seeded demo users.
- Set **`JWT_SECRET`** to any long random string, or sessions reset every time the backend restarts.

### 4. Run the backend (terminal 1)
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate          # Windows (Git Bash)
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements-dev.txt
python -m app.seed --reset        # demo volunteers + requesters (first run downloads the ~90 MB embedding model)
uvicorn app.main:app --reload --port 8000
```

### 5. Run the frontend (terminal 2)
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

### 6. Verify
- [ ] http://localhost:5173/api/health shows `"db": "ok"`. It also shows `vector_search`: `atlas` on our Atlas cluster, `local` otherwise.
- [ ] `cd backend && pytest -q` passes. To also run the database tests, set `MONGODB_TEST_URI` to a MongoDB URI (the dev Atlas URI is fine). Each test uses its own `mesh_test_*` database and drops its collections afterwards (the Atlas role cannot `dropDatabase`).
- [ ] `cd frontend && npm run typecheck && npm run lint` passes.

If the database shows `error`, the usual cause is that your IP isn't allowed in Atlas or `MONGODB_URI` is wrong. The backend log shows the exact error.

If the backend takes **~25 seconds to start** (common on a VPN or restrictive network), the slow part is the DNS lookup behind a `mongodb+srv://` connection string. Use the standard form instead: in Atlas, **Connect → Drivers**, choose the oldest driver version listed, and copy the `mongodb://host1,host2,host3/?...` string. Same cluster and credentials; startup drops to a couple of seconds.

### 7. Try the MVP (10 minutes)
Use two browser windows (one normal, one private) so you can be both sides at once:
- [ ] **Volunteer:** sign in as **Marcus (demo)** → "Requests that fit you" lists the tree and debris requests first.
- [ ] **Requester:** sign in as **Casey (demo)** → type "my neighbor is trapped" → the red 911 screen appears → "Go back and edit" → ask for something normal, like "a branch fell on my porch roof".
- [ ] **Volunteer:** Casey's request shows up (within 10 s) → "Help with this" → chat opens.
- [ ] **Chat:** send messages both ways (they appear within 3 s) → "Mark as resolved".
- [ ] Anything broken or confusing: post it in the team chat with steps to reproduce.

### 8. Personal tasks
- [ ] Redeem your **$50 Muse credits** (PLAN.md §20)
- [ ] Read PLAN.md §0.1 (MVP), §14 (the non-negotiable rules), §21 (backlog), and your lane below

### Working with Claude Code
CLAUDE.md loads automatically. Start each task with something like:

> Read PLAN.md and ONBOARDING.md. I'm Lane B. Do task B1. Stay inside my lane's files; if you need to change a shared file, keep the change minimal and tell me.

Claude Code will leave `TODO(HUMAN)` markers where it needs keys, docs, or data. Don't let it guess API specs (rule §14.1).

---

## Part 2: The plan from here

### Phase 0: the MVP (done, on `main`)
The first working prototype is on `main` (PLAN.md §0.1). It covers:
- Google + demo login and onboarding;
- requests with the 911 keyword check;
- volunteer lists **ranked purely by vector similarity**: fastembed `all-MiniLM-L6-v2` vectors, with Atlas Vector Search or a local fallback, and optional Muse Spark text normalization;
- claiming, and a private chat per request (polling).

There's no location, map, hazards, or triage yet; those are Phase 1+.

**Everyone, before Phase 1:**
1. `git fetch origin && git switch lane/<your-lane> && git pull origin main` (lane branches were created before the MVP).
2. Do the Part 1 checklist, including "Try the MVP".
3. Finish your human tasks in the table below.

### Phase 1: build on the MVP
Same four lanes and branches. Each lane's tasks are **in order**: finish and merge one before starting the next.

| Lane | Focus | Suggested owner |
|---|---|---|
| **A: Platform** | deploy, realtime, coordinator role, offer delivery | Chris (holds the keys, Atlas, and Vultr) |
| **B: Requests core** | request lifecycle, triage rules, verified-helper rules, matching filters | Teammate 1 |
| **C: UI** | profile page, polish, matching v2 UI, leads queue, map (later) | Teammate 2 |
| **D: AI & data** | Muse Spark, AI matching v2, matching eval, synthetic leads | Teammate 3 |

**Lane A: Platform** (`lane/a-platform`)
1. **A1 Deploy:** Vultr VM, Docker Compose, Caddy, .tech DNS, HTTPS (PLAN.md §16). The repo side is done: the embedding model is baked into the image, the frontend builds inside Docker, and `docs/DEPLOY.md` is the runbook (`deploy/bootstrap-vm.sh`, `deploy/deploy.sh`, and a clean production `.env` template). What's left is yours: create the VM, add the DNS records, allow the VM's IP in Atlas, add the production origin to the OAuth client, fill in `.env` on the VM, and run the phone smoke test over cellular.
2. **A2 Realtime:** `/ws` for chat messages and request status (PLAN.md §10), keeping polling as a fallback. Every payload goes through `serialize_request`.
3. **A3 Coordinator role:** invite-code onboarding, `POST /api/coordinator/verify/{user_id}`. Lanes B and D need verified helpers and a coordinator view.
4. **A4 Match offers:** `match.suggested` WebSocket event with accept/decline, plus the 5-minute timeout that offers to the next candidate (PLAN.md §21.1 step 6), using D's ranked candidates.

**Lane B: Requests core** (`lane/b-requests`)
1. **B1 Lifecycle:** add `EN_ROUTE`, `ON_SITE`, `ESCALATED` to the state machine and endpoints (PLAN.md §9.7), with tests for every transition.
2. **B2 Triage rules:** high-urgency terms and flags in `rules.py` plus the `requester_flags` floor (PLAN.md §9.2 step 1), giving each request a category and urgency. D adds the LLM merge on top.
3. **B3 Helper rules:** verified-only claims when urgency ≥ 4, and at most 2 active claims per helper.
4. **B4 Matching v2 filters:** hard filters (on duty, radius once location exists, fewer than 2 active claims, verified if urgency ≥ 4), the fairness penalty, and the deterministic fallback score (PLAN.md §21.1 steps 1, 4, 5). Expose these as one function D's reranker calls.
5. **B5 Lead conversion:** the confirmed-lead → request path and the verified-only rule for social-sourced requests (PLAN.md §21.2), once D's leads land.

**Lane C: UI** (`lane/c-ui`)
1. **C1 Profile page:** ~~edit name, background, skills (including custom skills), and "What can you offer?"~~ Done: `/profile`. Dual Volunteer + Requester profiles with a navbar mode switcher are covered by PLAN.md §0.1 "One account, two profiles".
2. **C2 Polish:** fix issues from everyone's MVP testing; add a status timeline on the requester page.
3. **C3 Matching v2 UI:** need-coverage checklist per matched helper, the "Matched by AI" reason, and the accept/decline prompt for suggested matches (with A4 and D2).
4. **C4 Leads queue:** coordinator page with label, confidence, reasons, bucket, a SYNTHETIC badge on every lead, and confirm/dismiss (with D4).
5. **C5 Location + map:** only once location returns to scope (PLAN.md §13).

**Lane D: AI & data** (`lane/d-hazards-ai`)
1. **D1 Muse Spark live:** set `LLM_PROVIDER=muse` + `MUSE_API_KEY`. Check whether normalization improves ranking (a good test: with the demo data and mock mode, Diego's #2 is the tree request because it mentions a car; see if it becomes the water/food request), and tune `ai/prompts.py`.
2. **D2 AI matching v2:** top ~10 by vector search, then a Spark rerank returning structured JSON (need coverage, reason, optional 2-helper team), then code validation with fallback to B4's score (PLAN.md §21.1 steps 2–4). The LLM never outputs scores or distances.
3. **D3 Matching eval:** `backend/eval/matching_eval.py`, ~30 synthetic requests and ~15 helpers, a best-helper labels file (`TODO(HUMAN)`: the team labels it). Reports top-1/top-3 agreement for formula vs embeddings vs embeddings + LLM.
4. **D4 Synthetic leads:** `SourceAdapter` + `SyntheticSource`, the classifier with the keyword baseline, near-duplicate detection, the `social_posts.jsonl` dataset with a held-out split, and the eval script (PLAN.md §21.2).

**If we fall behind**, cut in this order: coordinator weight sliders and chat translation (neither is built yet), then the leads queue polish, then match offers (keep the ranked list). **Never cut:** auth, the request lifecycle, AI matching, the 911 path, or the privacy serializer.

### Interfaces between lanes
- **B → D:** B4's filter + fallback-score function, which D2's reranker calls.
- **D → A and C:** D2's ranked candidates with coverage, which A4 delivers as offers and C3 displays.
- **D → B and C:** D4's lead records, which B5 converts and C4 displays.
- **A → B and D:** A3's verified flag and coordinator role.

### Human (non-code) tasks by owner
| Owner | Task |
|---|---|
| A | Google OAuth client ID + test users (`GOOGLE_CLIENT_ID`, `VITE_GOOGLE_CLIENT_ID`); Atlas URI, confirm `/api/health` shows `vector_search: atlas` against it; .tech domain; Vultr VM; confirm the real deadline |
| B | Write `docs/demo-script.md` from the "Try the MVP" steps plus PLAN.md §17 |
| C | Line up two phones (one iOS, one Android) for the A1 smoke test |
| D | `MUSE_API_KEY`; confirm the transcription endpoint (`docs/muse-api.md` lists two conflicting paths); label the D3 best-helper file with the team |

---

## Part 3: Working together

### Git workflow
- Each lane has its own branch off `main`:

  | Lane | Branch |
  |---|---|
  | A: Platform | `lane/a-platform` |
  | B: Requests core | `lane/b-requests` |
  | C: UI | `lane/c-ui` |
  | D: AI & data | `lane/d-hazards-ai` |

  ```bash
  git fetch origin
  git switch lane/b-requests        # your lane's branch
  git pull origin main              # bring in the latest main
  ```
- Commit to your lane branch and push often. Never push directly to `main`.
- **Merge into `main` via PR whenever a task works**, and at the latest at every sync point. Before merging: `pytest -q` and `npm run typecheck` pass, and one teammate glances at it (a 2-minute review is fine).

  **Run the database tests too** (they skip silently without a database, and that hides the location privacy tests). With Docker Desktop running:
  ```bash
  docker run -d --name mesh-test-mongo -p 27018:27017 mongo:7
  cd backend && MONGODB_TEST_URI=mongodb://localhost:27018 python -m pytest -q     # expect: 0 skipped
  docker rm -f mesh-test-mongo                                                       # when done
  ```
  (PowerShell: `$env:MONGODB_TEST_URI='mongodb://localhost:27018'`.) The tests create and drop their own scratch databases; nothing touches Atlas.
- After anything merges to `main`, update your lane branch: `git pull origin main` (or `git rebase origin/main` if you prefer). Lane branches that drift from `main` for hours cause painful merges.

### Shared files (where conflicts happen)
| File | Rule |
|---|---|
| `backend/app/models.py` + `frontend/src/lib/types.ts` | Anyone may add to them, but change **both files in the same PR**. |
| `backend/app/services/serialize.py` | Lane B owns it. Every request leaving the backend goes through it; ask B before changing what a viewer sees. |
| `backend/app/services/{embeddings,ranking}.py`, `backend/app/ai/` | Lane D owns them. |
| `backend/app/main.py` | Only add your `include_router` line. |
| `frontend/src/router.tsx` | Lane C owns it. Other lanes add only their own routes. |
| `requirements.txt` / `package.json` | Add dependencies in your PR. After a rebase, re-run `npm install` so the lockfile is regenerated rather than hand-merged. |
| `.env.example` | Add every new variable here (without a value) and tell the team. |

### Not blocking each other
- **The API contract is PLAN.md.** Frontend work builds against the shapes in PLAN.md using hardcoded sample data, then swaps in the real endpoint when it merges.
- Backend logic in `services/` is pure functions with tests where possible, so it doesn't wait on the frontend.
- If you're blocked for more than 15 minutes, say so in the team chat.

### Sync points
Every ~2 hours (agree on times in the team chat, starting when everyone finishes Phase 0), spend 10 minutes together: merge everything to `main`, run "Try the MVP" plus whatever landed on one machine, and re-split anything that's behind.
