"""Dashboard metrics, audit, model analytics, settings and demo control endpoints."""
import threading
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import SessionLocal, get_db
from ..graph.engine import get_engine
from ..infra import limiter
from ..ml.features import aware
from ..models import (
    AuditLog,
    FraudPrediction,
    Investigation,
    ModelVersion,
    PayPalOrder,
    SystemSetting,
    Transaction,
    User,
    utcnow,
)
from ..security import require_admin, require_staff
from ..services.demo import run_scenario, scenario_list, simulator
from ..services.risk import DEFAULT_POLICY, get_policy

router = APIRouter()


@router.get("/api/dashboard/metrics", tags=["dashboard"])
def dashboard_metrics(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    count = lambda *w: db.execute(select(func.count()).select_from(Transaction).where(*w)).scalar() or 0  # noqa: E731
    analysed = db.execute(select(func.count(func.distinct(FraudPrediction.transaction_id)))).scalar() or 0
    live_latency = db.execute(select(func.avg(FraudPrediction.latency_ms), func.count())
                              .where(FraudPrediction.latency_ms > 0)).one()
    captured = db.execute(select(func.count(), func.coalesce(func.sum(PayPalOrder.amount), 0))
                          .where(PayPalOrder.capture_status == "COMPLETED")).one()

    now = utcnow()
    since = now - timedelta(days=30)
    rows = db.execute(select(Transaction.created_at, Transaction.amount, Transaction.risk_level, Transaction.review_status,
                             Transaction.channel).where(Transaction.created_at >= since)).all()
    days: dict[str, dict] = {}
    for i in range(31):
        d = (since + timedelta(days=i)).date().isoformat()
        days[d] = {"date": d, "count": 0, "amount": 0.0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "rejected": 0}
    for ts, amt, lvl, rs, _ch in rows:
        d = aware(ts).date().isoformat()
        if d not in days:
            continue
        days[d]["count"] += 1
        days[d]["amount"] = round(days[d]["amount"] + float(amt), 2)
        if lvl:
            days[d][lvl] += 1
        if rs == "REJECTED":
            days[d]["rejected"] += 1

    latest = (select(FraudPrediction.transaction_id, func.max(FraudPrediction.id).label("pid"))
              .group_by(FraudPrediction.transaction_id).subquery())
    probs = [p for (p,) in db.execute(select(FraudPrediction.fraud_probability)
                                      .join(latest, FraudPrediction.id == latest.c.pid)).all()]
    hist = [0] * 10
    for p in probs:
        hist[min(int(p * 10), 9)] += 1

    pay_status = defaultdict(int)
    sentinel_status = defaultdict(int)
    for ps, ss in db.execute(select(PayPalOrder.paypal_status, PayPalOrder.sentinel_status)).all():
        pay_status[ps] += 1
        sentinel_status[ss] += 1
    by_channel = dict(db.execute(select(Transaction.channel, func.count()).group_by(Transaction.channel)).all())
    primary = db.execute(select(ModelVersion).where(ModelVersion.is_primary.is_(True), ModelVersion.is_active.is_(True))).scalar()
    inv_counts = dict(db.execute(select(Investigation.status, func.count()).group_by(Investigation.status)).all())

    return {
        "data_label": "SYNTHETIC DEMO DATA (history + simulator) and live PayPal Sandbox orders",
        "kpis": {
            "transactions_analysed": analysed,
            "suspicious": count(Transaction.risk_level.in_(("MEDIUM", "HIGH", "CRITICAL"))),
            "critical": count(Transaction.risk_level == "CRITICAL"),
            "high": count(Transaction.risk_level == "HIGH"),
            "awaiting_review": count(Transaction.review_status.in_(("PENDING_REVIEW", "ESCALATED"))),
            "captured_paypal_payments": captured[0],
            "captured_amount": float(captured[1] or 0),
            "blocked_or_rejected": count(Transaction.review_status == "REJECTED"),
            "avg_processing_ms": round(live_latency[0], 1) if live_latency[0] else None,
            "live_assessments": live_latency[1],
            "paypal_orders": sum(pay_status.values()),
        },
        "volume_series": list(days.values()),
        "risk_distribution": {lvl: count(Transaction.risk_level == lvl) for lvl in ("LOW", "MEDIUM", "HIGH", "CRITICAL")},
        "probability_histogram": [{"bucket": f"{i / 10:.1f}-{(i + 1) / 10:.1f}", "count": c} for i, c in enumerate(hist)],
        "paypal_status_distribution": dict(pay_status),
        "sentinel_status_distribution": dict(sentinel_status),
        "channels": by_channel,
        "network": get_engine(db).summary(),
        "model": {"version": primary.version, "algorithm": primary.algorithm,
                  **{k: primary.metrics.get(k) for k in ("precision", "recall", "f1", "roc_auc", "pr_auc")}} if primary else None,
        "investigations": inv_counts,
        "simulator": simulator.status(),
    }


@router.get("/api/audit", tags=["audit"])
def audit_list(db: Session = Depends(get_db), _: User = Depends(require_staff), action: str | None = None,
               entity_id: str | None = None, limit: int = Query(300, le=2000)):
    q = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        q = q.where(AuditLog.action == action)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    return [{"id": a.id, "actor": a.actor_label, "action": a.action, "entity_type": a.entity_type,
             "entity_id": a.entity_id, "details": a.details, "hash": a.hash, "prev_hash": a.prev_hash,
             "created_at": aware(a.created_at)} for a in db.execute(q.limit(limit)).scalars()]


@router.get("/api/audit/verify", tags=["audit"], summary="Verify the audit log hash chain")
def audit_verify(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return audit.verify_chain(db)


# ------------------------------------------------------------------------------- models
@router.get("/api/models", tags=["models"])
def models(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    rows = db.execute(select(ModelVersion).order_by(ModelVersion.id.desc())).scalars()
    return [{"id": m.id, "version": m.version, "algorithm": m.algorithm, "is_active": m.is_active,
             "is_primary": m.is_primary, "metrics": m.metrics, "training_rows": m.training_rows,
             "test_rows": m.test_rows, "notes": m.notes, "feature_names": m.feature_names,
             "created_at": aware(m.created_at)} for m in rows]


_retrain_lock = threading.Lock()
_retrain_state = {"running": False, "last": None, "error": None}


@router.post("/api/models/retrain", tags=["models"], summary="Retrain all models (includes reviewer-labelled live payments)")
def retrain(user: User = Depends(require_admin)):
    if not _retrain_lock.acquire(blocking=False):
        raise HTTPException(409, "Retraining already in progress")

    def job():
        db = SessionLocal()
        try:
            _retrain_state.update(running=True, error=None)
            from ..ml.service import train_from_db
            s = train_from_db(db, actor=db.get(User, user.id), notes=f"Retrained by {user.email}")
            _retrain_state["last"] = {"version": s["version"], "primary": s["primary"]}
        except Exception as exc:
            _retrain_state["error"] = str(exc)
        finally:
            _retrain_state["running"] = False
            db.close()
            _retrain_lock.release()

    threading.Thread(target=job, daemon=True).start()
    return {"started": True}


@router.get("/api/models/retrain", tags=["models"])
def retrain_status(_: User = Depends(require_staff)):
    return _retrain_state


# ------------------------------------------------------------------------------- settings
class PolicyIn(BaseModel):
    low_max: float = Field(gt=0, lt=1)
    medium_max: float = Field(gt=0, lt=1)
    high_max: float = Field(gt=0, lt=1)
    anomaly_escalation: float = Field(gt=0, le=1)
    amount_ratio_escalation: float = Field(gt=1, le=1000)
    graph_escalation: bool
    auto_investigate_levels: list[str]


@router.get("/api/settings/risk-policy", tags=["settings"])
def get_risk_policy(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return {"policy": get_policy(db), "defaults": DEFAULT_POLICY}


@router.put("/api/settings/risk-policy", tags=["settings"])
def put_risk_policy(body: PolicyIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if not body.low_max < body.medium_max < body.high_max:
        raise HTTPException(422, "Thresholds must satisfy low_max < medium_max < high_max")
    if any(l not in ("LOW", "MEDIUM", "HIGH", "CRITICAL") for l in body.auto_investigate_levels):
        raise HTTPException(422, "Invalid risk level in auto_investigate_levels")
    old = get_policy(db)
    row = db.get(SystemSetting, "risk_policy")
    if row:
        row.value = body.model_dump()
    else:
        db.add(SystemSetting(key="risk_policy", value=body.model_dump()))
    audit.record(db, "RISK_POLICY_UPDATED", "setting", "risk_policy", {"old": old, "new": body.model_dump()}, actor=user)
    db.commit()
    return {"policy": get_policy(db)}


@router.get("/api/settings/integrations", tags=["settings"])
def integrations(_: User = Depends(require_staff)):
    s = get_settings()
    db_kind = "postgresql" if s.sqlalchemy_url.startswith("postgresql") else "sqlite"
    return {
        "paypal": {"configured": s.paypal_configured, "base_url": s.paypal_base_url,
                   "webhook_verification": bool(s.paypal_webhook_id)},
        "groq": {"configured": s.groq_configured, "model": s.groq_model,
                 "mode": "LLM_AGENT" if s.groq_configured else "DETERMINISTIC_FALLBACK"},
        "database": db_kind, "rate_limiter": limiter.backend, "environment": s.app_env,
    }


# ------------------------------------------------------------------------------- demo
@router.get("/api/demo/scenarios", tags=["demo"])
def scenarios(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return {"scenarios": scenario_list(db), "paypal_configured": get_settings().paypal_configured}


@router.post("/api/demo/scenarios/{key}/run", tags=["demo"])
def run(key: str, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return run_scenario(db, key, user)


class SimIn(BaseModel):
    action: str = Field(pattern="^(start|stop)$")
    interval_seconds: float = Field(3.0, ge=1, le=30)


@router.post("/api/demo/simulator", tags=["demo"])
def sim(body: SimIn, user: User = Depends(require_staff)):
    return simulator.start(user, body.interval_seconds) if body.action == "start" else simulator.stop()


@router.get("/api/demo/simulator", tags=["demo"])
def sim_status(_: User = Depends(require_staff)):
    return simulator.status()
