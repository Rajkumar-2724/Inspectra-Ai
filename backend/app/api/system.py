import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.model_registry import registry
from app.core.config import get_settings
from app.core.deps import get_current_user, require_roles, user_from_token
from app.database.session import SessionLocal, get_db
from app.models import AppSetting, User
from app.schemas.schemas import SettingsIn
from app.services.events import hub

router = APIRouter(tags=["system"])
START = time.time()
EDITABLE_SETTINGS = {"organization_name", "camera_interval_seconds"}


@router.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "uptime_s": round(time.time() - START, 1)}


@router.get("/api/system/status")
def system_status(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = get_settings()
    m = registry.overall(db)
    return {"api": "ok", "database": "ok", "environment": s.ENVIRONMENT, "max_upload_mb": s.MAX_UPLOAD_MB,
            "real_mode_available": m["real_mode_available"], "demo_mode_available": False, "uptime_s": round(time.time() - START, 1),
            "settings": {r.key: r.value for r in db.execute(select(AppSetting)).scalars()}}


@router.put("/api/system/settings")
def put_settings(body: SettingsIn, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    bad = set(body.values) - EDITABLE_SETTINGS
    if bad:
        raise HTTPException(422, f"Unknown settings: {sorted(bad)}")
    for k, v in body.values.items():
        row = db.get(AppSetting, k)
        if row:
            row.value = v[:500]
        else:
            db.add(AppSetting(key=k, value=v[:500]))
    db.commit()
    return {"ok": True}


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket, token: str = Query("")):
    db = SessionLocal()
    try:
        user_from_token(db, token)
    except HTTPException:
        await ws.close(code=4401)
        return
    finally:
        db.close()
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
