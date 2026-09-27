FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed

WORKDIR /app

# Run as a normal user. /app/media is where a named volume mounts (kept writable for it).
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /opt/fastembed /app/media \
 && chown -R app:app /opt/fastembed /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app app ./app

USER app

# Bake the embedding model into the image (about 90 MB). Without this it downloads on the first request after every
# rebuild, and that request is slow or fails if the download is blocked. If EMBEDDING_MODEL is changed in .env later,
# the new model still downloads at runtime into the same writable cache.
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from fastembed import TextEmbedding; m = TextEmbedding('${EMBEDDING_MODEL}'); print('model ready, dims:', len(next(iter(m.embed(['warm up'])))))"

EXPOSE 8000

# /api/health answers 200 as soon as the app is up (it reports the database separately as db: ok|error), so this
# only means "the process is serving". The first check waits for startup.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Reached only by Caddy over the compose network, so trusting its forwarded headers is safe.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
