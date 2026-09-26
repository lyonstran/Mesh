# Mesh

Mobile-first weather-disaster relief for Georgia: neighbors helping neighbors, with AI triage and live hazard data. Built at HackGT 13. It needs an internet connection; "mesh" means a human network of neighbors, not offline networking.

Full spec: [PLAN.md](PLAN.md). Contributor rules: [CLAUDE.md](CLAUDE.md).

## Local dev

```bash
cp .env.example .env          # fill in MONGODB_URI at minimum

# backend: http://localhost:8000
cd backend
python -m venv .venv && . .venv/Scripts/activate   # macOS/Linux: . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# frontend: http://localhost:5173 (proxies /api and /ws to :8000)
cd frontend
npm install
npm run dev
```

`GET /api/health` returns `{"ok": true, "db": "ok", ...}` when Mongo is reachable.
