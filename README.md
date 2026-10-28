# AI-Based Automated Visual Inspection System

Industrial quality-inspection platform: image upload, webcam and batch inspection, PASS / REVIEW / FAIL decisions, heatmaps and defect boxes, human review queue, analytics, PDF/CSV reports, SHA-256 hash-chained audit trail, and a model registry ready for future PatchCore / classifier ONNX artifacts.

> **Honesty notes**
> - **No AI model was trained and none is included.** *Real AI mode* is disabled until valid model artifacts are registered.
> - **Demo mode** is a deterministic simulator. Its outcomes are chosen by the demo scenario, not by analysing the image, and every screen, PDF and CSV row marks them as simulated.
> - No accuracy/precision/recall/F1/AUROC is shown anywhere. See `docs/TEST_RESULTS.md` for what was and was not executed (Playwright E2E, Windows scripts and Docker were **not** run by the author).

## Stack
React 18 · Vite · TypeScript · Tailwind · React Router · TanStack Query · Axios · Framer Motion · Recharts · React Hook Form + Zod · react-dropzone · react-webcam · react-hot-toast — FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · JWT + Argon2 · OpenCV · Pillow · NumPy · pandas · ReportLab · ONNX Runtime — SQLite (PostgreSQL-ready).

## Quick start (Windows 10/11)
1. `start_backend.bat` (first run creates the venv, `.env`, installs, migrates, serves :8000)
2. Edit `backend\.env` → `SECRET_KEY`, `ADMIN_PASSWORD`
3. `scripts\seed_demo.bat` → admin + `inspector` + `reviewer` users, 3 sample products, 60 **simulated** inspections
4. `start_frontend.bat` → http://127.0.0.1:5173 · API docs http://127.0.0.1:8000/docs
   (or `start_all.bat`)

Login: username `admin`, password = your `ADMIN_PASSWORD` (`inspector` / `reviewer` share it — development only).

Details, manual commands, env vars, tests, Docker: **`docs/SETUP.md`**. Other docs: `ARCHITECTURE.md`, `API.md`, `USER_GUIDE.md`, `AI_MODEL_INTEGRATION.md`, `TEST_RESULTS.md`.

## Tests
```
cd backend  && pip install -r requirements-dev.txt && python -m pytest tests -q
cd frontend && npm test            # Vitest
cd frontend && npx playwright install chromium && npm run e2e   # backend running + seeded
```

## Adding trained models later
Export to ONNX, drop `model.onnx` + `model.meta.json` into `models/`, register via *Models* page or `python -m app.scripts.register_models`, assign to the product. Contract: `docs/AI_MODEL_INTEGRATION.md`.

## Layout
```
frontend/  React app (src/pages, components, services, contexts, hooks, types, utils; tests/, e2e/)
backend/   FastAPI app (app/api, ai, services, models, schemas, core, database, scripts), alembic/, tests/
models/    model artifacts + registry.example.yaml (no weights shipped)
demo_assets/ synthetic sample images   scripts/ helpers   docs/
```
