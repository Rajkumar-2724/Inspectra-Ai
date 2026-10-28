# Test results (authoring sandbox: Linux, Python 3.12.3, Node 22; re-verified on Windows 11, Python 3.13, Node 24)

## Verification run on Windows 11 / Python 3.13 / Node 24 (2026-10-24)

| Suite | Command | Result |
|---|---|---|
| Playwright end-to-end (5 specs) | `cd frontend && npx playwright install chromium && npm run e2e` (backend :8000 + seeded) | **5 passed** — login (bad+good), dashboard charts, upload+demo inspect+result views, human-review approve flow, PDF download. One strict-mode selector fixed on first run, as predicted below. |
| Full API smoke (87 checks) | httpx script | **87/87 passed** — auth/RBAC/password change, system, demo samples/scenarios, products CRUD+reference image, demo inspections (PASS/FAIL/REVIEW) + 6 image kinds + PDF + CSV, real-mode 409, corrupt-upload & unknown-product 4xx, history filters/search, batch create/queue/complete/report/CSV, review approve/reject (+ validation errors), all dashboard/analytics endpoints, ground-truth labeling (post-label evaluation flags on), model registry rejections (path traversal, missing artifact), audit events + chain verify, unauthenticated 401s. |
| Alembic on fresh DB | `alembic upgrade head` | **applied** |
| Seed | `python -m app.scripts.seed` then `--demo-data` | **admin + inspector + reviewer + 3 products + 60 simulated inspections** |
| `start_backend.bat`, `start_frontend.bat`, `scripts\run_tests.bat`, `scripts\seed_demo.bat` | executed on real Windows | **all OK** (backend serves :8000, frontend serves :5173 with working /api proxy, combined test runner 52+8 passed) |
| `scripts/generate_demo_assets.py` | executed | **5 synthetic PNGs written to `demo_assets/`** |
| Backend (pytest, 52 tests) on Python 3.13 | `python -m pytest tests -q` | **52 passed** |
| Frontend type-check, Vitest (8), prod build | `npm run typecheck` / `npm test` / `npm run build` | **all clean** |

Dependency note: pins in `backend/requirements.txt` were bumped (`opencv-python-headless 4.11.0.86`, `numpy 2.2.6`, `onnxruntime 1.21.1`, dev `onnx 1.18.0`) because the previous pins had no Python 3.13 wheels and pip failed building NumPy from source. The new pins support Python 3.10–3.13 (3.11/3.12 still covered, including the Docker image).

## Original authoring-sandbox results

| Suite | Command | Result |
|---|---|---|
| Backend (pytest, 52 tests) | `cd backend && python -m pytest tests -q` | **52 passed** |
| Frontend type-check | `cd frontend && npx tsc -b --noEmit` | **clean** |
| Frontend unit/component (Vitest, 8 tests) | `cd frontend && npm test` | **8 passed** |
| Frontend production build | `cd frontend && npm run build` | **succeeded** |
| Alembic | `alembic upgrade head` on a fresh DB, then `alembic check` | **applied; no model/migration drift** |
| Live API smoke (uvicorn + curl) | seed → login → CORS preflight → demo inspect → real inspect | **OK**; real mode returned `409 REAL_MODE_UNAVAILABLE`, demo returned `simulated:true`; audit chain verified on 40 seeded records |
| Model registration script | `python -m app.scripts.register_models` with a test ONNX + a missing file | **READY / FILE_MISSING as expected** |

## Still NOT run
- **Docker Compose** — Docker Desktop is installed but its daemon could not be started headlessly in the verification environment. Compose files were not modified.
- **PostgreSQL** (SQLite was used everywhere) and **real webcam capture** — no camera/managed DB in the environment. The webcam page compiles and its logic is unit-untested.
- **No AI model was trained or used.** The one real-path test uses a tiny *untrained* ONNX graph created inside the test (channel mean) purely to exercise loading/validation/inference plumbing. It says nothing about detection quality.

## What the backend tests cover
auth (register/login/me/password/roles/self-registration role lock) · threshold boundaries & invalid thresholds · image validation, EXIF orientation, aspect-preserving resize, localizer · all five demo scenarios (decision, boxes, simulated flag, determinism) · persistence, images, filters, invalid uploads · real-mode refusal without models (nothing saved) · ONNX registration (missing/invalid/pickle/traversal/valid) and real inference through the registry, corrupted-file re-check, product compatibility · mock PatchCore + classifier (known/unknown) through `InspectionEngine`, no-fallback guarantee · batch partial failure & retry, PDF/CSV · review workflow preserving AI decision · audit chain, hash formula, tampering of payload / inspection row / deleted record · dashboard & analytics incl. empty state and ground-truth-only metrics · product CRUD/archive/reference patch.

## Known limitations
- Demo results depend on the chosen scenario, not on image content — by design, and labelled so.
- Reference "nearest good patch" is a same-region crop of the product's reference image, not a PatchCore memory-bank neighbour.
- In-process batch queue and audit-append lock assume a single backend process.
- Hash chain gives tamper evidence only.
- Anomalib export compatibility, score calibration and any detection accuracy are entirely up to the artifacts you supply and must be evaluated separately.
