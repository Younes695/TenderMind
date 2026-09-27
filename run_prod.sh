#!/usr/bin/env bash
# TenderMind — production launcher with preflight checks.
# Usage:  cp .env.example .env  (fill it in)  &&  ./run_prod.sh
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present (simple KEY=VALUE lines)
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

fail() { echo "❌ $1" >&2; exit 1; }
ok()   { echo "✅ $1"; }

export TENDERMIND_ENV="${TENDERMIND_ENV:-production}"

# 1. Required secrets
# Accounts come from /signup (and Google/Microsoft); the env admin is optional
# but must be complete if used.
if [ -n "${TENDERMIND_AUTH_EMAIL:-}" ] && [ -z "${TENDERMIND_AUTH_PASSWORD:-}" ]; then fail "TENDERMIND_AUTH_PASSWORD is missing for TENDERMIND_AUTH_EMAIL"; fi
if [ -z "${TENDERMIND_AUTH_EMAIL:-}" ] && [ -n "${TENDERMIND_AUTH_PASSWORD:-}" ]; then fail "TENDERMIND_AUTH_EMAIL is missing for TENDERMIND_AUTH_PASSWORD"; fi
[ -n "${TENDERMIND_SESSION_SECRET:-}" ]  || fail "TENDERMIND_SESSION_SECRET is not set (generate: python3 -c 'import secrets; print(secrets.token_hex(32))')"
[ "${#TENDERMIND_SESSION_SECRET}" -ge 32 ] || fail "TENDERMIND_SESSION_SECRET must be at least 32 characters"
ok "auth secrets configured"

# 2. Python deps
python3 -c "import fastapi, sqlalchemy, fitz, pytesseract, PIL, xlrd, itsdangerous, requests, docx, olefile, openpyxl, jsonschema" 2>/dev/null \
  || fail "Python deps missing — run: pip install -r requirements.txt"
ok "python dependencies"

# 3. Tesseract binary (OCR for scanned pages) — warn only
if command -v tesseract >/dev/null 2>&1 || [ -n "${TENDERMIND_TESSERACT_PATH:-}" ]; then
  ok "tesseract found"
else
  echo "⚠️  tesseract not found — scanned PDF pages will extract as empty. Install: apt-get install -y tesseract-ocr tesseract-ocr-ara"
fi

# 3b. Archive / CAD tools — warn only
if command -v unrar >/dev/null 2>&1 || command -v 7z >/dev/null 2>&1 || command -v bsdtar >/dev/null 2>&1; then
  ok "RAR extractor found"
else
  echo "⚠️  no RAR extractor — .rar uploads will fail. Install: apt-get install -y unrar (or p7zip-full / libarchive-tools)"
fi
if [ -z "${GOOGLE_CLIENT_ID:-}" ] && [ -z "${MICROSOFT_CLIENT_ID:-}" ]; then
  echo "ℹ️  Google/Microsoft sign-in not configured — email sign-up/log-in only"
fi

# 4. Built frontend
if [ ! -f frontend/dist/index.html ]; then
  echo "… frontend/dist missing, building"
  command -v npm >/dev/null 2>&1 || fail "npm not found and frontend/dist is missing"
  (cd frontend && npm install && npm run build)
fi
ok "frontend build present"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"
echo "🚀 Starting TenderMind on $HOST:$PORT (single worker — SQLite + local uploads)"
exec python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT" --workers 1 --proxy-headers
