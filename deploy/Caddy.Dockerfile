# Builds the frontend and serves it with Caddy, so the VM needs no Node and no committed dist folder.
# Build context is the repo root (see docker-compose.yml). VITE_* values are baked into the JavaScript at build time,
# so changing them means rebuilding this image (./deploy/deploy.sh does that).

FROM node:22-alpine AS web
WORKDIR /repo/frontend

ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_DEMO_LOGIN=false
ARG VITE_MAP_TILE_URL=
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_DEMO_LOGIN=$VITE_DEMO_LOGIN \
    VITE_MAP_TILE_URL=$VITE_MAP_TILE_URL

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM caddy:2
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=web /repo/frontend/dist /srv
