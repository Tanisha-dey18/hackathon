"""Transaction creation and the risk-decision branching shared by every channel."""
from __future__ import annotations

import hashlib
import secrets
import string
import time

from sqlalchemy.orm import Session

from .. import audit
from ..graph.engine import sync_transaction
from ..infra import ws_manager
from ..models import Customer, Device, FraudPrediction, Merchant, PaymentDestination, Transaction, User
from .risk import assess_transaction, get_policy

_ALPHA = string.ascii_uppercase + string.digits


def new_id(prefix: str) -> str:
    stamp = ""
    n = int(time.time() * 1000)
    while n:
        n, r = divmod(n, 36)
        stamp = _ALPHA[r] + stamp
    return f"{prefix}_{stamp[-7:]}{''.join(secrets.choice(_ALPHA) for _ in range(3))}"


def resolve_device(db: Session, fingerprint: str, device_type: str = "BROWSER", os: str = "Unknown") -> Device:
    fp = fingerprint.strip()[:128]
    dev = db.query(Device).filter(Device.fingerprint == fp).first()
    if dev:
        return dev
    dev = Device(id="DEV_" + hashlib.sha1(fp.encode()).hexdigest()[:8].upper(), fingerprint=fp,
                 device_type=device_type, os=os)
    db.add(dev)
    db.flush()
    return dev


def create_transaction(
    db: Session,
    *,
    customer: Customer,
    amount: float,
    device: Device,
    merchant: Merchant | None,
    destination: PaymentDestination,
    channel: str,
    lat: float | None = None,
    lon: float | None = None,
    scenario: str | None = None,
    description: str | None = None,
    status: str = "ASSESSING",
    actor: User | None = None,
) -> Transaction:
    txn = Transaction(
        id=new_id("TXN"),
        customer_id=customer.id,
        merchant_id=merchant.id if merchant else None,
        device_id=device.id,
        destination_id=destination.id,
        amount=round(float(amount), 2),
        currency="USD",
        lat=lat if lat is not None else customer.home_lat,
        lon=lon if lon is not None else customer.home_lon,
        channel=channel,
        status=status,
        scenario=scenario,
        description=description,
    )
    db.add(txn)
    db.flush()
    audit.record(db, "TRANSACTION_CREATED", "transaction", txn.id, {
        "customer_id": customer.id, "amount": float(txn.amount), "merchant_id": txn.merchant_id,
        "device_id": device.id, "destination_id": destination.id, "channel": channel,
    }, actor=actor)
    ws_manager.broadcast("transaction.created", {"transaction_id": txn.id, "amount": float(txn.amount),
                                                 "customer_id": customer.id, "channel": channel})
    return txn


def apply_risk_branch(db: Session, txn: Transaction, fp: FraudPrediction) -> str:
    """Route a transaction according to the risk policy. Returns the action taken.

    LOW -> cleared for capture; MEDIUM -> additional verification (reviewer);
    HIGH/CRITICAL -> held for human review. Nothing here moves money."""
    sync_transaction(db, txn)
    if fp.risk_level == "LOW":
        txn.status = "CLEARED"
        txn.review_status = "NONE"
        action = "CLEARED_FOR_CAPTURE"
    elif fp.risk_level == "MEDIUM":
        txn.status = "HELD_FOR_VERIFICATION"
        txn.review_status = "PENDING_REVIEW"
        action = "HELD_FOR_VERIFICATION"
    else:
        txn.status = "HELD_FOR_REVIEW"
        txn.review_status = "PENDING_REVIEW"
        action = "HELD_FOR_REVIEW"
    audit.record(db, "RISK_POLICY_APPLIED", "transaction", txn.id,
                 {"risk_level": fp.risk_level, "action": action}, actor_label="sentinel-policy-engine")
    ws_manager.broadcast("transaction.updated", {"transaction_id": txn.id, "status": txn.status,
                                                 "risk_level": fp.risk_level})
    return action


def should_auto_investigate(db: Session, txn: Transaction, fp: FraudPrediction) -> bool:
    return txn.channel in ("PAYPAL_CHECKOUT", "DEMO") and fp.risk_level in get_policy(db)["auto_investigate_levels"]


def assess_and_route(db: Session, txn: Transaction, actor: User | None = None) -> tuple[FraudPrediction, str]:
    fp = assess_transaction(db, txn, actor=actor)
    action = apply_risk_branch(db, txn, fp)
    return fp, action
