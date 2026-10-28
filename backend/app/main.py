import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics, audit_api, auth, batches, inspections, models_api, products, reviews, system
from app.core.config import get_settings
from app.services import batch_queue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.database.migrate import upgrade_head
    upgrade_head()  # Alembic is the single source of truth for the schema
    if not get_settings().BATCH_INLINE:
        batch_queue.start_workers()

    # Preload and warm up configured ONNX models once during backend initialization
    try:
        from app.ai.model_registry import registry
        from app.database.session import SessionLocal
        with SessionLocal() as db:
            init_status = registry.overall(db)
            log.info("ONNX Model Registry preloaded at startup: real_mode_available=%s, active_cached_models=%d",
                     init_status.get("real_mode_available"), len(registry._cache))
    except Exception as e:
        log.warning("Model preloading warning at startup: %s", e)

    yield


app = FastAPI(title="AI-Based Automated Visual Inspection System", version="1.0.0", lifespan=lifespan,
              description="Industrial visual inspection API. DEMO mode results are simulated; REAL mode requires validated model artifacts.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_log(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, (time.perf_counter() - t0) * 1000)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errs = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errs})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})  # no internals leaked


for r in (auth.router, products.router, inspections.router, batches.router, reviews.router, analytics.router,
          models_api.router, audit_api.router, system.router):
    app.include_router(r)
