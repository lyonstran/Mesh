# Mesh

Mobile-first weather-disaster relief for Georgia: neighbors helping neighbors. The current MVP matches requests to volunteers by vector similarity and opens a private chat (PLAN.md §0.1). Built at HackGT 13. It needs an internet connection; "mesh" means a human network of neighbors, not offline networking.

Full spec: [PLAN.md](PLAN.md). Contributor rules: [CLAUDE.md](CLAUDE.md).

## Local dev

```bash
cp .env.example .env          # fill in MONGODB_URI at minimum

# backend: http://localhost:8000
cd backend
python -m venv .venv && . .venv/Scripts/activate   # macOS/Linux: . .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed --reset       # demo users (set DEMO_LOGIN=true and VITE_DEMO_LOGIN=true to sign in as them)
uvicorn app.main:app --reload --port 8000

# frontend: http://localhost:5173 (proxies /api and /ws to :8000)
cd frontend
npm install
npm run dev
```

`GET /api/health` returns `{"ok": true, "db": "ok", ...}` when Mongo is reachable.
