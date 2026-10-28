# Setup (Windows 10/11 + VS Code)

## Required software
| Tool | Version |
|---|---|
| Python | 3.11 (3.12 and 3.13 also tested) |
| Node.js | 20 LTS or newer (22 tested) · npm 10+ |
| Browser | Current Chrome/Edge/Firefox (webcam needs `http://localhost` or HTTPS) |
| Docker Desktop | optional |

## One-time setup & run (easiest)
1. Double-click `start_backend.bat` — creates `backend\.venv`, copies `.env.example` → `.env`, installs dependencies, runs `alembic upgrade head`, starts API on :8000.
2. Edit `backend\.env`: set `SECRET_KEY` (32+ random chars) and `ADMIN_PASSWORD`.
3. Create the admin user, sample products and optional **simulated** demo data: `scripts\seed_demo.bat`
   (or `cd backend && .venv\Scripts\activate && python -m app.scripts.seed` for users/products only).
   Seed creates `admin` (email/username/password from `.env`) plus `inspector` and `reviewer` accounts with the **same password** — development only; the script refuses `ENVIRONMENT=production`.
4. Double-click `start_frontend.bat` (installs npm packages on first run) → http://127.0.0.1:5173.
   `start_all.bat` starts both.

## Manual commands
```bat
cd backend
py -3.11 -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000

cd ..\frontend
copy .env.example .env
npm install
npm run dev
```
macOS/Linux: same, with `source .venv/bin/activate` and `cp`.

## Environment variables (backend/.env)
`ENVIRONMENT` · `SECRET_KEY` (≥32 chars; app refuses the default in production) · `ACCESS_TOKEN_EXPIRE_MINUTES` · `DATABASE_URL` (SQLite default; `postgresql+psycopg://…` later — install the driver) · `STORAGE_DIR` · `MODELS_DIR` · `CORS_ORIGINS` · `MAX_UPLOAD_MB` · `BATCH_WORKERS` · `BATCH_QUEUE_SIZE` · seed-only: `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
Frontend: `VITE_API_URL` (default `http://127.0.0.1:8000`).

## Database migrations
`cd backend && alembic upgrade head` (also run automatically on API start). New migration: `alembic revision --autogenerate -m "msg"`.

## Tests
```bat
scripts\run_tests.bat                     :: backend pytest + frontend typecheck + vitest
cd backend && python -m pytest tests -q   :: needs requirements-dev.txt
cd frontend && npm test
cd frontend && npx playwright install chromium && npm run e2e   :: backend must be running and seeded
```
Playwright credentials default to `admin` / `ChangeMe-Admin-123`; override with `E2E_USER`, `E2E_PASSWORD`.

## Docker (optional)
`copy .env.docker.example .env` → set `SECRET_KEY` → `docker compose up --build`. Not exercised in the authoring environment (no Docker available there).

## Optional AI extras
`pip install -r backend/requirements-ai.txt` (PyTorch, Anomalib, Albumentations …) — only needed to train/export models or load TorchScript. ONNX inference needs nothing beyond `requirements.txt`.
