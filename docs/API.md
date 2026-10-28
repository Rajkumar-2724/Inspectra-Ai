# API

Interactive OpenAPI docs: `http://127.0.0.1:8000/docs` (generated from the code). All endpoints except `/api/auth/register`, `/api/auth/login` and `/api/health` need `Authorization: Bearer <token>`.
Errors: `{"detail": "..."}` (422 adds `errors:[{field,message}]`). Real-mode refusal: `409 {"detail":{"code":"REAL_MODE_UNAVAILABLE","message":...,"reasons":[...]}}`.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register` · `POST /api/auth/login` · `GET /api/auth/me` · `POST /api/auth/change-password` · admin: `GET/POST /api/users`, `PATCH /api/users/{id}` |
| Dashboard | `GET /api/dashboard/stats` · `/trends` · `/recent` (optional `mode=demo|real`) |
| Inspection | `POST /api/inspect` (multipart: file, product_id, mode, scenario, product_code, batch_code, line_id, notes) · `GET /api/inspections` (filters+pagination) · `GET /api/inspections/export/csv` · `GET /api/inspections/{id}` · `/{id}/images` · `/{id}/images/{kind}` · `/{id}/report` |
| Batch | `POST /api/batches` · `GET /api/batches` · `POST /api/batches/{id}/inspect` (multipart files) · `POST /api/batches/{id}/retry` · `GET /api/batches/{id}` · `/status` · `/inspections` · `/report` · `/export/csv` |
| Products | `GET/POST /api/products` · `GET/PATCH/DELETE /api/products/{id}` (DELETE archives) · `POST/GET /api/products/{id}/reference-image` |
| Reviews | `GET /api/reviews/pending` · `POST /api/reviews/{inspection_id}/decision` `{decision: approve|reject|reinspect, comment}` |
| Analytics | `GET /api/analytics/defects` · `/trends` · `/latency` · `POST /api/analytics/ground-truth` |
| Models | `GET /api/models` · `GET /api/models/status` · `POST /api/models/register` · `POST /api/models/{id}/validate` |
| Audit | `GET /api/audit/events` · `GET /api/audit/verify` (admin) |
| System | `GET /api/health` · `GET /api/system/status` · `PUT /api/system/settings` · `GET /api/demo/scenarios` · `GET /api/demo/samples/{scenario}.png` · `WS /ws/events?token=` |
