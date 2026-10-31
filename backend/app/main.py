"""SENTINEL API - FastAPI application entrypoint."""
import asyncio
import logging
import re
from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import SessionLocal
from .infra import ws_manager
from .routers import auth, intel, ops, paypal, transactions
from .security import STAFF, decode_token


class RedactSecrets(logging.Filter):
    """Secure logging: never let bearer tokens or client secrets reach log output."""
    patterns = [re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*"), re.compile(r"(client_secret=)[^&\s]+"),
                re.compile(r"(access_token\"?:\s*\"?)[^\",\s]+")]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for p in self.patterns:
            msg = p.sub(r"\1[REDACTED]", msg)
        record.msg, record.args = msg, ()
        return True


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for h in logging.getLogger().handlers:
    h.addFilter(RedactSecrets())
log = logging.getLogger("sentinel")


def init_database() -> None:
    from .migrate import upgrade_head
    from .seed.loader import is_seeded, seed, shift_synthetic_to_today

    upgrade_head()
    if get_settings().auto_seed:
        db = SessionLocal()
        try:
            if not is_seeded(db):
                log.info("Seeding synthetic environment and training models (first start)...")
                log.info("Seed result: %s", seed(db))
            else:
                _ensure_model_artifact(db)
                if get_settings().shift_synthetic_to_today:
                    days = shift_synthetic_to_today(db)
                    if days:
                        log.info("Shifted synthetic history forward %d day(s) to end today", days)
        finally:
            db.close()


def _ensure_model_artifact(db) -> None:
    """Hosts with ephemeral disks (e.g. Render) lose model files on redeploy; retrain from the DB."""
    from pathlib import Path

    from sqlalchemy import select

    from .ml.service import train_from_db
    from .models import ModelVersion

    mv = db.execute(select(ModelVersion).where(ModelVersion.is_primary.is_(True), ModelVersion.is_active.is_(True))).scalar()
    if mv is None or not Path(mv.artifact_path).exists():
        log.warning("Active model artifact missing; retraining from stored transactions...")
        train_from_db(db, notes="Retrained at startup: model artifact was missing on disk.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_manager.loop = asyncio.get_running_loop()
    await asyncio.to_thread(init_database)
    yield
    from .services.demo import simulator
    simulator.stop()


app = FastAPI(
    title="SENTINEL API",
    description="Autonomous AI-powered payment risk intelligence on PayPal Sandbox. "
                "All customer, merchant and device data is SYNTHETIC demo data.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Validation failed",
                                                  "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


for r in (auth.router, transactions.router, intel.router, paypal.router, ops.router):
    app.include_router(r)


@app.get("/api/health", tags=["system"])
def health():
    s = get_settings()
    return {"status": "ok", "paypal_configured": s.paypal_configured, "groq_configured": s.groq_configured}


@app.websocket("/ws/transactions")
async def ws_transactions(ws: WebSocket):
    token = ws.query_params.get("token", "")
    try:
        payload = decode_token(token)
        if payload.get("role") not in STAFF:
            raise jwt.InvalidTokenError("staff only")
    except jwt.PyJWTError:
        await ws.close(code=4401)
        return
    await ws_manager.connect(ws)
    try:
        await ws.send_json({"event": "connected", "data": {"role": payload["role"]}})
        while True:
            await ws.receive_text()  # keepalive pings from the client
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
