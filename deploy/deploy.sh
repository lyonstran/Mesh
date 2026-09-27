#!/usr/bin/env bash
# Deploy or update Mesh on the VM. Run from anywhere inside the repo:
#   ./deploy/deploy.sh              pull the latest main, rebuild, restart
#   ./deploy/deploy.sh --no-pull    rebuild what is checked out (use this to roll back to an older commit)
# It stops before touching anything if .env is missing or unsafe.
set -euo pipefail
cd "$(dirname "$0")/.."

PULL=1
[ "${1:-}" = "--no-pull" ] && PULL=0

die()  { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }

[ -f .env ] || die ".env not found. Run: cp deploy/env.production.example .env  and fill it in."

# Read one value from .env (last one wins), without echoing secrets.
get() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//'; }

[ -n "$(get MONGODB_URI)" ]       || die "MONGODB_URI is empty."
[ -n "$(get JWT_SECRET)" ]        || die "JWT_SECRET is empty. Generate one with: openssl rand -hex 32"
[ "$(get COOKIE_SECURE)" = "true" ] || die "COOKIE_SECURE must be true in production."
[ "$(get DEMO_LOGIN)" = "$(get VITE_DEMO_LOGIN)" ] || die "DEMO_LOGIN and VITE_DEMO_LOGIN must be the same value."
[ -n "$(get GOOGLE_CLIENT_ID)" ] || warn "GOOGLE_CLIENT_ID is empty: Google sign-in will not work."
[ -n "$(get VITE_GOOGLE_CLIENT_ID)" ] || warn "VITE_GOOGLE_CLIENT_ID is empty: the Google button will not render."
case "$(get NWS_USER_AGENT)" in *example.com*) warn "NWS_USER_AGENT still uses an example.com address. NWS asks for a real contact." ;; esac

DOMAIN="$(get SITE_DOMAIN)"; DOMAIN="${DOMAIN:-mesh-together.tech}"

docker compose config -q || die "docker-compose.yml or .env is invalid."

if [ "$PULL" = 1 ]; then
  echo "==> Pulling latest code"
  git pull --ff-only
fi

echo "==> Building and starting (the first build downloads the embedding model and builds the frontend, so it takes a few minutes)"
docker compose up -d --build

echo "==> Waiting for the backend to become healthy"
for i in $(seq 1 40); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$(docker compose ps -q backend)" 2>/dev/null || echo starting)"
  [ "$status" = "healthy" ] && break
  sleep 3
done
[ "$status" = "healthy" ] || { docker compose logs --tail=60 backend; die "Backend did not become healthy."; }

echo "==> Status"
docker compose ps
echo
echo "Check:  curl -fsS https://$DOMAIN/api/health"
echo "        expect \"db\": \"ok\". If it says \"error\", allow this VM's IP in Atlas > Network Access."
echo "Logs:   docker compose logs -f backend"
