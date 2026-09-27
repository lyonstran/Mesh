# Deploying Mesh on Vultr

This puts Mesh on a small Ubuntu VM behind Caddy with automatic HTTPS at `https://mesh-together.tech`. HTTPS is not optional: phones block location sharing (and later the microphone) on plain http.

The repo does the work; the steps below are the parts only you can do (accounts, DNS, secrets). Budget about 45 minutes, most of it waiting for the first build.

```
phone / browser ──HTTPS──▶ Caddy (serves the built site, proxies /api) ──▶ backend (FastAPI) ──▶ MongoDB Atlas
```

## What you need before you start
- A Vultr account with credit.
- The domain `mesh-together.tech` and access to its DNS settings.
- Access to your MongoDB Atlas project (Network Access) and your Google Cloud OAuth client.
- A terminal with `ssh`, and an SSH key (`ssh-keygen -t ed25519` if you have none).

## 1. Create the VM (Vultr dashboard)
1. **Deploy → Cloud Compute.**
2. Location: **Atlanta** (closest to the demo).
3. Image: **Ubuntu 24.04 LTS x64**.
4. Plan: at least **2 GB RAM**. The embedding model and the frontend build need the room; 1 GB will likely fail the build. Check Vultr's pricing page: a 2 GB machine costs a small fraction of a $100 credit for the whole event.
5. Add your **SSH key**. Leave IPv4 on. Deploy.
6. When it shows **Running**, copy the **public IPv4 address**. Call it `VM_IP` below.

## 2. Point the domain at it (your DNS provider)
Add two `A` records, both to `VM_IP`, TTL as low as allowed:

| Host | Type | Value |
|---|---|---|
| `@` (mesh-together.tech) | A | `VM_IP` |
| `www` | A | `VM_IP` |

Check from your laptop (may take a few minutes): `nslookup mesh-together.tech` should print `VM_IP`. Caddy can't get a certificate until this resolves.

## 3. Allow the VM in MongoDB Atlas
Atlas → **Network Access → Add IP Address** → `VM_IP`. Without this the site loads but `/api/health` reports `"db": "error"`.

## 4. Allow the site in Google sign-in
Google Cloud Console → **APIs & Services → Credentials →** your OAuth 2.0 Web client → **Authorized JavaScript origins → Add** `https://mesh-together.tech`. Save. (Changes can take a few minutes.)

## 5. Set up the VM (once)
```bash
ssh root@VM_IP
git clone https://github.com/lyonstran/Mesh.git
cd Mesh
sudo bash ./deploy/bootstrap-vm.sh
```
If the repo is private, `git clone` asks for credentials; use a personal access token as the password, or add a deploy key.

The script installs Docker, opens only ports 22, 80 and 443 in the firewall, and adds a 2 GB swap file.

## 6. Create the production `.env` (on the VM)
```bash
cp deploy/env.production.example .env
chmod 600 .env
nano .env
```
Fill in the blanks:

| Variable | Value |
|---|---|
| `MONGODB_URI` | your Atlas connection string |
| `JWT_SECRET` | run `openssl rand -hex 32` and paste the result |
| `GOOGLE_CLIENT_ID` and `VITE_GOOGLE_CLIENT_ID` | the same OAuth client id |
| `COORDINATOR_INVITE_CODE` | any code you choose |
| `NWS_USER_AGENT` | `"(Mesh, your-real-email@example.com)"` (the weather service asks for a real contact) |
| `DEMO_LOGIN` and `VITE_DEMO_LOGIN` | both `true` to let judges sign in as demo users; both `false` otherwise. They must match. |

**The real `.env` stays on the VM.** Never commit it or paste it into a chat.

## 7. Deploy
```bash
bash ./deploy/deploy.sh
```
The first run takes several minutes: it downloads the embedding model into the image and builds the frontend. The script refuses to start if the `.env` is unsafe (empty `JWT_SECRET`, `COOKIE_SECURE` not `true`, mismatched demo flags) and waits for the backend to report healthy.

## 8. Check it works
```bash
curl -fsS https://mesh-together.tech/api/health
```
Expect `"ok": true` and `"db": "ok"`. Then open the site in a browser (you should see the padlock).

**Seed the demo data** (deletes and recreates only `demo: true` users and requests):
```bash
docker compose exec backend python -m app.seed --reset
```
The demo data lives in whichever Atlas database `MONGODB_DB` names, so if your laptop uses the same one, this refreshes it there too.

## 9. Phone smoke test (two real phones on cellular, not Wi-Fi)
- [ ] Open the site; the page loads with a padlock.
- [ ] Sign in (Google, or a demo user if demo login is on).
- [ ] Requester: set a location ("Use my current location" prompts for permission), post a request.
- [ ] Volunteer (second phone): the request appears on the map and in the list; claim it.
- [ ] Both: tap "Share my location"; each sees the other's dot moving.
- [ ] Resolve the request; both dots disappear.

## Updating, rolling back, logs
| Task | Command |
|---|---|
| Deploy the latest `main` | `cd Mesh && bash ./deploy/deploy.sh` |
| Roll back to an older version | `git checkout <commit>` then `bash ./deploy/deploy.sh --no-pull` |
| Follow the API log | `docker compose logs -f backend` |
| Follow the web server log | `docker compose logs -f caddy` |
| Status | `docker compose ps` |
| Restart | `docker compose restart` |

Frontend settings that start with `VITE_` are baked into the site at build time, so changing one in `.env` needs `bash ./deploy/deploy.sh` (which rebuilds), not just a restart.

## Trying the stack on your own machine
With Docker Desktop running, set `SITE_DOMAIN=localhost` in a scratch `.env`, then `docker compose up --build` and open `https://localhost` (accept the local certificate warning). Geolocation works on `localhost` even without HTTPS.

## If something's wrong
| Symptom | Likely cause |
|---|---|
| Browser can't connect, or certificate error | DNS hasn't reached `VM_IP` yet, or port 80/443 is blocked. `docker compose logs caddy` shows certificate attempts. |
| `"db": "error"` in `/api/health` | `VM_IP` isn't in Atlas Network Access, or `MONGODB_URI` is wrong. |
| Google button missing or sign-in fails | `VITE_GOOGLE_CLIENT_ID` empty (rebuild after fixing), or the origin isn't authorized in Google Cloud. |
| 502 Bad Gateway | The backend isn't healthy yet. `docker compose logs backend`. |
| Build fails or the VM freezes | Not enough memory: use a 2 GB or larger plan (the swap file helps but isn't a substitute). |
| Logged out after every deploy | `JWT_SECRET` is empty or changing; set a fixed value. |

## Cost and teardown
The VM bills while it exists, even if stopped. When the event is over, **destroy** it from the Vultr dashboard (Settings → Destroy). Delete the DNS records too.
