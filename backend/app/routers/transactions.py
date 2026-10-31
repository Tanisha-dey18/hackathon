"""Transactions, risk assessment and reviewer decision endpoints."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..ml.features import aware
from ..models import (
    AuditLog,
    Customer,
    Device,
    FraudPrediction,
    Investigation,
    Merchant,
    ModelVersion,
    PaymentDestination,
    PaymentEvent,
    PayPalOrder,
    ReviewerDecision,
    Transaction,
    User,
)
from ..security import require_reviewer, require_staff
from ..services import review
from ..services.payments import order_view
from ..services.risk import assess_transaction, prediction_payload
from ..services.transactions import apply_risk_branch, create_transaction, resolve_device

router = APIRouter(tags=["transactions"])


def _latest_pred_subq():
    return (select(FraudPrediction.transaction_id, func.max(FraudPrediction.id).label("pid"))
            .group_by(FraudPrediction.transaction_id).subquery())


def txn_row(t: Transaction, fp: FraudPrediction | None) -> dict:
    return {
        "id": t.id, "customer_id": t.customer_id, "customer_name": t.customer.name if t.customer else None,
        "merchant_id": t.merchant_id, "merchant_name": t.merchant.name if t.merchant else None,
        "device_id": t.device_id, "destination_id": t.destination_id, "amount": float(t.amount),
        "currency": t.currency, "channel": t.channel, "status": t.status, "risk_level": t.risk_level,
        "review_status": t.review_status, "scenario": t.scenario, "description": t.description,
        "created_at": aware(t.created_at),
        "fraud_probability": fp.fraud_probability if fp else None,
        "anomaly_score": fp.anomaly_score if fp else None,
        "is_synthetic": t.channel != "PAYPAL_CHECKOUT",
    }


class TxnCreate(BaseModel):
    customer_id: str = Field(pattern=r"^CUS_\w+$")
    amount: float = Field(gt=0, le=100000)
    merchant_id: str | None = Field(default=None, pattern=r"^MER_\w+$")
    destination_id: str | None = Field(default=None, pattern=r"^DST_\w+$")
    device_fingerprint: str = Field(min_length=4, max_length=128)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    description: str | None = Field(default=None, max_length=255)


@router.post("/api/transactions", summary="Create a synthetic transaction and run it through the risk engine")
def create_txn(body: TxnCreate, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    customer = db.get(Customer, body.customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    merchant = db.get(Merchant, body.merchant_id) if body.merchant_id else None
    if body.merchant_id and not merchant:
        raise HTTPException(404, "Merchant not found")
    dest_id = body.destination_id or (merchant.payout_destination_id if merchant else None)
    dest = db.get(PaymentDestination, dest_id) if dest_id else None
    if not dest:
        raise HTTPException(422, "A valid destination_id (or merchant_id) is required")
    txn = create_transaction(db, customer=customer, amount=body.amount, device=resolve_device(db, body.device_fingerprint),
                             merchant=merchant, destination=dest, channel="DEMO", lat=body.lat, lon=body.lon,
                             scenario="MANUAL", description=body.description or "Manual synthetic transaction", actor=user)
    fp = assess_transaction(db, txn, actor=user)
    action = apply_risk_branch(db, txn, fp)
    db.commit()
    return {"transaction": txn_row(txn, fp), "risk": prediction_payload(fp), "action": action}


@router.get("/api/transactions")
def list_txns(
    db: Session = Depends(get_db), _: User = Depends(require_staff),
    risk_level: str | None = None, status: str | None = None, channel: str | None = None,
    review_status: str | None = None, customer_id: str | None = None, q: str | None = Query(None, max_length=60),
    limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0),
):
    sub = _latest_pred_subq()
    stmt = (select(Transaction, FraudPrediction).outerjoin(sub, sub.c.transaction_id == Transaction.id)
            .outerjoin(FraudPrediction, FraudPrediction.id == sub.c.pid))
    if risk_level:
        stmt = stmt.where(Transaction.risk_level.in_(risk_level.split(",")))
    if status:
        stmt = stmt.where(Transaction.status.in_(status.split(",")))
    if channel:
        stmt = stmt.where(Transaction.channel.in_(channel.split(",")))
    if review_status:
        stmt = stmt.where(Transaction.review_status.in_(review_status.split(",")))
    if customer_id:
        stmt = stmt.where(Transaction.customer_id == customer_id)
    if q:
        stmt = stmt.where(Transaction.id.ilike(f"%{q}%") | Transaction.customer_id.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    rows = db.execute(stmt.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [txn_row(t, fp) for t, fp in rows]}


@router.get("/api/transactions/{txn_id}")
def get_txn(txn_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    t = db.get(Transaction, txn_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    preds = list(db.execute(select(FraudPrediction).where(FraudPrediction.transaction_id == txn_id)
                            .order_by(FraudPrediction.id.desc())).scalars())
    invs = list(db.execute(select(Investigation).where(Investigation.transaction_id == txn_id)
                           .order_by(Investigation.created_at.desc())).scalars())
    decisions = list(db.execute(select(ReviewerDecision).where(ReviewerDecision.transaction_id == txn_id)
                                .order_by(ReviewerDecision.id)).scalars())
    order = db.execute(select(PayPalOrder).where(PayPalOrder.transaction_id == txn_id)).scalar()
    events = list(db.execute(select(PaymentEvent).where(PaymentEvent.paypal_order_id == order.paypal_order_id)
                             .order_by(PaymentEvent.id)).scalars()) if order else []
    entity_ids = [txn_id] + [i.id for i in invs] + ([order.paypal_order_id] if order else [])
    audits = list(db.execute(select(AuditLog).where(AuditLog.entity_id.in_(entity_ids)).order_by(AuditLog.id)).scalars())
    dev: Device = t.device
    return {
        "transaction": txn_row(t, preds[0] if preds else None),
        "customer": {"id": t.customer.id, "name": t.customer.name, "email": t.customer.email, "city": t.customer.city,
                     "country": t.customer.country, "segment": t.customer.segment},
        "merchant": {"id": t.merchant.id, "name": t.merchant.name, "category": t.merchant.category,
                     "risk_score": t.merchant.risk_score, "high_risk_category": t.merchant.high_risk_category} if t.merchant else None,
        "device": {"id": dev.id, "type": dev.device_type, "os": dev.os, "fingerprint": dev.fingerprint[:12] + "…"},
        "destination": {"id": t.destination.id, "label": t.destination.label, "kind": t.destination.kind,
                        "flagged": t.destination.is_flagged},
        "location": {"lat": t.lat, "lon": t.lon},
        "predictions": [prediction_payload(p) for p in preds],
        "investigations": [{"id": i.id, "status": i.status, "mode": i.mode, "recommendation": i.recommendation,
                            "created_at": aware(i.created_at)} for i in invs],
        "decisions": [{"id": d.id, "decision": d.decision, "reason": d.reason, "reviewer": d.reviewer.email,
                       "risk_level_at_decision": d.risk_level_at_decision, "payment_outcome": d.payment_outcome,
                       "created_at": aware(d.created_at)} for d in decisions],
        "paypal_order": order_view(order) if order else None,
        "payment_events": [{"id": e.id, "source": e.source, "event_type": e.event_type, "http_status": e.http_status,
                            "debug_id": e.paypal_debug_id, "verified": e.signature_verified,
                            "created_at": aware(e.created_at)} for e in events],
        "audit": [{"id": a.id, "action": a.action, "actor": a.actor_label, "details": a.details,
                   "created_at": aware(a.created_at), "hash": a.hash[:16]} for a in audits],
    }


# ------------------------------------------------------------------------------- risk
class AssessIn(BaseModel):
    transaction_id: str = Field(pattern=r"^TXN_\w+$")


@router.post("/api/risk/assess", tags=["risk"], summary="(Re-)assess an existing transaction with the active model")
def assess(body: AssessIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    t = db.get(Transaction, body.transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    fp = assess_transaction(db, t, actor=user)
    db.commit()
    return prediction_payload(fp)


@router.get("/api/risk/metrics", tags=["risk"])
def risk_metrics(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    models = list(db.execute(select(ModelVersion).where(ModelVersion.is_active.is_(True))).scalars())
    dist = dict(db.execute(select(Transaction.risk_level, func.count()).group_by(Transaction.risk_level)).all())
    return {
        "models": [{"version": m.version, "algorithm": m.algorithm, "is_primary": m.is_primary,
                    **{k: m.metrics.get(k) for k in ("precision", "recall", "f1", "roc_auc", "pr_auc")}} for m in models],
        "risk_distribution": {k or "UNASSESSED": v for k, v in dist.items()},
    }


# ------------------------------------------------------------------------------- reviews
class DecisionIn(BaseModel):
    decision: Literal["APPROVE", "REJECT", "ESCALATE"]
    reason: str = Field(min_length=5, max_length=2000)
    password: str = Field(min_length=1, max_length=200)
    confirm_transaction_id: str


@router.post("/api/reviews/{txn_id}/decision", tags=["reviews"],
             summary="Reviewer decision (requires re-authentication and typed confirmation)")
def decide(txn_id: str, body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_reviewer)):
    return review.decide(db, user, txn_id, body.decision, body.reason, body.password, body.confirm_transaction_id)


@router.get("/api/reviews/queue", tags=["reviews"])
def review_queue(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    sub = _latest_pred_subq()
    rows = db.execute(
        select(Transaction, FraudPrediction).outerjoin(sub, sub.c.transaction_id == Transaction.id)
        .outerjoin(FraudPrediction, FraudPrediction.id == sub.c.pid)
        .where(Transaction.review_status.in_(("PENDING_REVIEW", "ESCALATED")))
        .order_by(Transaction.created_at.desc())
    ).all()
    return [txn_row(t, fp) for t, fp in rows]
