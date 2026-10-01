# TenderMind production image: FastAPI (single worker) + built React frontend.
# Ollama runs as a separate service (see docker-compose.yml).

# ---- frontend build
FROM node:22.12-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- runtime
FROM python:3.11.11-slim-bookworm AS runtime

# OCR (English + Arabic) and archive extraction (bsdtar reads ZIP/RAR/7z).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara libarchive-tools curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TENDERMIND_ENV=production \
    DATABASE_URL=sqlite:////data/tender.db \
    TENDERMIND_STORAGE_ROOT=/data/uploads \
    TENDERMIND_TWO_STAGE_LLM=1 \
    TENDERMIND_WORKERS_ENABLED=1 \
    TENDERMIND_MAX_AI_WORKERS=2 \
    FORWARDED_ALLOW_IPS=127.0.0.1,::1,172.30.87.0/24

# Only the proxy network pinned in docker-compose.yml (Caddy, and the gateway a
# proxy on this host connects through) is trusted for X-Forwarded-For; uvicorn
# reads FORWARDED_ALLOW_IPS. The client address is then the last one that is not
# a trusted proxy, i.e. the one the proxy itself saw: a value the client puts in
# the header cannot become its address, so the login and sign-up limits cannot
# be dodged. It was "*" (trust everything): with a proxy that appends to the
# header, like nginx's default, the client chose its own address. Trusting all
# private ranges instead would still let a LAN client forge it.

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

# app/ imports helpers from evaluation/ (extractors, OCR, two-stage prompts).
COPY app/ ./app/
COPY evaluation/ ./evaluation/
COPY schemas/ ./schemas/
COPY --from=frontend /build/dist ./frontend/dist

RUN groupadd --gid 1001 tendermind \
 && useradd --uid 1001 --gid tendermind --no-create-home --shell /usr/sbin/nologin tendermind \
 && mkdir -p /data/uploads && chown -R tendermind:tendermind /data
USER tendermind

VOLUME ["/data"]
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8001/health || exit 1

# One worker: SQLite + in-process background jobs (see docs/RELEASE_READINESS.md).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", \
     "--workers", "1", "--proxy-headers"]
