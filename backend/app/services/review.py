"""Human-in-the-loop decisions. Reviewers re-authenticate and confirm; every decision is persisted
and audited, and only an APPROVE decision can unlock a PayPal capture for a held payment."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..infra import ws_manager
from ..models import Investigation, PayPalOrder, ReviewerDecision, Transaction, User
from ..security import verify_password
from .payments import execute_capture

REVIEWABLE = ("HELD_FOR_REVIEW", "HELD_FOR_VERIFICATION", "ESCALATED")


def decide(db: Session, reviewer: User, txn_id: str, decision: str, reason: str, password: str,
           confirm_transaction_id: str) -> dict:
    if reviewer.role not in ("ADMIN", "REVIEWER"):
        raise HTTPException(403, "Only reviewers can decide payments")
    if not verify_password(password, reviewer.password_hash):
        audit.record(db, "REVIEW_REAUTH_FAILED", "transaction", txn_id, {"decision": decision}, actor=reviewer)
        db.commit()
        raise HTTPException(401, "Re-authentication failed")
    if confirm_transaction_id != txn_id:
        raise HTTPException(422, "Confirmation does not match the transaction ID")
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.status not in REVIEWABLE:
        raise HTTPException(409, f"Transaction is {txn.status}; it is not awaiting a decision")
    if txn.status == "ESCALATED" and reviewer.role != "ADMIN":
        raise HTTPException(403, "Escalated payments require an ADMIN decision")
    if decision == "ESCALATE" and txn.status == "ESCALATED":
        raise HTTPException(409, "Already escalated")
    if txn.risk_level in ("HIGH", "CRITICAL") and decision == "APPROVE" and len(reason.strip()) < 20:
        raise HTTPException(422, "Approving a HIGH/CRITICAL risk payment requires a justification of at least 20 characters")

    inv = db.execute(select(Investigation).where(Investigation.transaction_id == txn_id)
                     .order_by(Investigation.created_at.desc())).scalar()
    d = ReviewerDecision(transaction_id=txn_id, investigation_id=inv.id if inv else None, reviewer_id=reviewer.id,
                         decision=decision, reason=reason.strip(), risk_level_at_decision=txn.risk_level)
    db.add(d)
    db.flush()
    order = db.execute(select(PayPalOrder).where(PayPalOrder.transaction_id == txn_id)).scalar()
    outcome: str
    result: dict = {}

    if decision == "ESCALATE":
        txn.status = "ESCALATED"
        txn.review_status = "ESCALATED"
        if order:
            order.sentinel_status = "ESCALATED"
        outcome = "ESCALATED_TO_ADMIN"
    elif decision == "REJECT":
        txn.status = "REJECTED"
        txn.review_status = "REJECTED"
        if order:
            order.sentinel_status = "REJECTED"
            outcome = f"NOT_CAPTURED (PayPal order remains {order.paypal_status}; no funds moved)"
        else:
            outcome = "REJECTED (no PayPal order attached)"
    else:
        txn.review_status = "APPROVED"
        txn.status = "APPROVED"
        if order:
            db.commit()
            audit.record(db, "REVIEW_DECISION", "transaction", txn_id,
                         {"decision": decision, "reason": reason, "decision_id": d.id}, actor=reviewer)
            db.commit()
            result = execute_capture(db, order, authorized_by="REVIEWER", actor=reviewer)
            d.payment_outcome = f"PAYPAL_CAPTURE {result.get('capture_status') or result.get('message')}"
            db.commit()
            _broadcast(txn, d)
            return {"decision_id": d.id, "decision": decision, "transaction_status": txn.status,
                    "payment_outcome": d.payment_outcome, "paypal": result}
        outcome = "APPROVED (no PayPal order attached; nothing to capture)"

    d.payment_outcome = outcome
    audit.record(db, "REVIEW_DECISION", "transaction", txn_id,
                 {"decision": decision, "reason": reason, "decision_id": d.id, "outcome": outcome}, actor=reviewer)
    db.commit()
    _broadcast(txn, d)
    return {"decision_id": d.id, "decision": decision, "transaction_status": txn.status, "payment_outcome": outcome,
            "paypal": result or None}


def _broadcast(txn: Transaction, d: ReviewerDecision) -> None:
    ws_manager.broadcast("decision.made", {"transaction_id": txn.id, "decision": d.decision, "status": txn.status})
