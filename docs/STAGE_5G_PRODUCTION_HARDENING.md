# Stage 5G — Production hardening

## Defects fixed
| # | Severity | Defect | Fix |
|---|---|---|---|
| 1 | Critical | No data isolation: with open sign-up, any account could read, change and delete every tender, uploaded file and company document | `owner_email` on tenders and company documents; one router guard (`app/access.py`) on every `{tender_id}` route; lists, company documents, processing jobs and evaluation passages scoped to the owner. Other accounts get 404. Demo tender readable by all, writable only by the env admin. Rows created before 5G belong to the env admin only. |
| 2 | Critical | Microsoft sign-in account takeover: `preferred_username` is set by any tenant admin, and the account was matched by email | A provider identity may only sign in to an account bound to that identity; Microsoft never takes over an account created another way (`auth._may_link`). |
| 3 | High | Clean install crashed at startup: `itsdangerous` (sessions), `requests`, `python-docx`, `olefile`, `openpyxl` missing from `requirements.txt` | Pinned. Verified by a fresh venv install + full suite. |
| 4 | High | Known CVEs: Pillow 10.4.0, Starlette 0.38.6 (via FastAPI 0.115), python-dotenv 1.0.1 | FastAPI 0.141.1, Pillow 12.3.0, python-dotenv 1.2.2, uvicorn 0.54.0, python-multipart 0.0.32, jinja2 3.1.6. `pip-audit`: no known vulnerabilities. `npm audit`: 0. |
| 5 | Medium | No brute-force protection on password login | 10 failures per IP+email / 50 per IP in 15 min → 429 (per IP+email so a stranger cannot lock a victim out). |
| 6 | Medium | Placeholder admin password in `.env.example` would be accepted | Production refuses to start with a weak/placeholder `TENDERMIND_AUTH_PASSWORD`; example no longer ships one. |
| 7 | Low | No browser security headers; `/docs` + `/openapi.json` public in production | CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy, HSTS in production; API docs off in production (`TENDERMIND_API_DOCS=1` to expose). |
| 8 | Low | `/health` always said ok | Checks the database; 503 when it is unavailable. |
| 9 | Low | Evidence matcher ignored `OLLAMA_BASE_URL` (only localhost / `TENDERMIND_OLLAMA_ENDPOINT`) — broke containerized Ollama | Honors both. |
| 10 | Low | `.7z` needed the `7z` binary even where `bsdtar` is installed | bsdtar fallback. |

Unused `@react-oauth/google` dependency removed.

## Deployment
`Dockerfile` (multi-stage: frontend build → python 3.11 slim, tesseract eng+ara,
bsdtar, non-root user, healthcheck) and `docker-compose.yml` (app + Ollama +
one-shot model pull; read-only root FS, `cap_drop: ALL`, no-new-privileges, data
volume, port bound to 127.0.0.1 behind a TLS proxy). See `DEPLOY_NOW.md`.

## Known limits (not defects, stated plainly)
- RAR/7z expanded size is checked after extraction (ZIP is checked before). The
  container's `/tmp` tmpfs (4 GB) bounds the damage.
- Tender IDs are unique server-wide, so creating an ID another account already
  used returns 409 (reveals only that the ID exists).
- One worker process (SQLite + in-process jobs); the rate limiter is in-process too.
- Old `.doc` files use the olefile fallback in the container (LibreOffice not installed, ~500 MB).
