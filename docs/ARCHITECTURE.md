# Architecture

```
React (Vite, TS, Tailwind, TanStack Query) ──HTTPS/JSON + WebSocket──▶ FastAPI
                                                                      ├─ api/        routers (auth, products, inspections, batches, reviews, analytics, models, audit, system)
                                                                      ├─ services/   inspection_service, batch_queue, audit (hash chain), reports (ReportLab), events (WS)
                                                                      ├─ ai/         InspectionEngine ─ preprocessing, patchcore/classifier/onnx adapters,
                                                                      │              localization, decision_engine, explainability, model_registry, demo_engine
                                                                      └─ SQLAlchemy 2 ─ SQLite (dev) / PostgreSQL-ready, Alembic migrations
Files (images) → backend/storage/ (paths in DB)      Models → models/ (validated, never pickled)
```

## Key decisions
- **Demo vs real is explicit.** `mode` is stored on every inspection; `simulated=true` for demo. Analytics, CSV, PDFs and the UI keep them distinguishable. Real mode raises `ModelNotReadyError` → HTTP 409; there is no fallback.
- **Decision logic** (`ai/decision_engine.py`): `score<review → PASS`, `review≤score<fail → REVIEW`, `score≥fail → FAIL`, thresholds validated `0≤review<fail≤1`; the exact thresholds and model version are stored per inspection.
- **Human review** writes `ReviewAction` rows and `final_decision`; the AI `decision`/`score` are never modified.
- **Audit chain**: `record_hash = SHA256(prev_hash + canonical_json(payload))`. Events: `INSPECTION` (written in the same DB transaction as the inspection) and `REVIEW`. `verify` recomputes the chain **and** compares each inspection row with its audited payload, so edits to either side, deletions and re-ordering are detected. It is tamper *evidence*: someone with full DB write access could rewrite the whole chain consistently. For stronger guarantees, periodically publish `head_hash` externally. A process-wide lock serialises appends (single-process deployment; use a DB-level sequence/lock if you scale out workers).
- **Batch queue**: bounded `queue.Queue` + worker threads; job state persisted in `batch_jobs`; interrupted jobs are re-queued on startup; per-job failures never affect completed inspections.
- **Security**: Argon2 hashing, JWT, backend-enforced roles, image content verification (Pillow decode, format allow-list, size & decompression-bomb limits), generated filenames, storage path confinement, model path confinement, no pickle loading, generic 500 messages.
- **Analytics** use pandas over stored rows (fine for tens of thousands of inspections; move to SQL aggregates beyond that).

## Roles
| Capability | Admin | Inspector | Reviewer |
|---|---|---|---|
| Inspect / batch / camera | ✔ | ✔ | – |
| View history, analytics, reports | ✔ | ✔ | ✔ |
| Review decisions, ground-truth labels | ✔ | – | ✔ |
| Products, thresholds, models, users | ✔ | – | – |
| Verify audit chain | ✔ | – | – |

## Data model
users · products · product_defect_classes · model_versions · inspections · inspection_images · inspection_defects · inspection_batches · batch_jobs · review_actions · audit_events · app_settings · evaluation_labels
