"""Populate the database with the synthetic environment, train models and score history."""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..graph.engine import get_engine, rebuild_graph_tables
from ..ml.predictor import load_bundle, predict_frame
from ..ml.service import train_from_db
from ..models import (
    Customer,
    Device,
    FraudPrediction,
    Merchant,
    ModelVersion,
    PaymentDestination,
    Product,
    SystemSetting,
    Transaction,
    User,
)
from ..security import hash_password
from ..services.risk import ACTIONS, DEFAULT_POLICY, classify, level_at_least
from .synthetic import MERCHANTS, PRODUCTS, generate

log = logging.getLogger("sentinel.seed")

STAFF_USERS = [
    ("admin@sentinel.dev", "Morgan Admin", "ADMIN", None),
    ("reviewer@sentinel.dev", "Riley Reviewer", "REVIEWER", None),
    ("analyst@sentinel.dev", "Alex Analyst", "ANALYST", None),
    ("ava@shopper.sentinel.dev", "Ava Thompson", "CUSTOMER", "CUS_0001"),
    ("ben@shopper.sentinel.dev", "Ben Carter", "CUSTOMER", "CUS_0002"),
    ("cara@shopper.sentinel.dev", "Cara Novak", "CUSTOMER", "CUS_0003"),
]


def is_seeded(db: Session) -> bool:
    return (db.execute(select(func.count()).select_from(Transaction)).scalar() or 0) > 0


def seed(db: Session) -> dict:
    t0 = time.time()
    world = generate()
    pw = hash_password(get_settings().seed_password)

    for c in world.customers:
        db.add(Customer(id=c.id, name=c.name, email=c.email, city=c.city, country=c.country, home_lat=c.lat,
                        home_lon=c.lon, segment=c.segment, created_at=world.now - timedelta(days=120)))
    db.flush()
    for d in world.destinations:
        db.add(PaymentDestination(id=d.id, label=d.label, kind=d.kind, owner_customer_id=d.owner, is_flagged=d.flagged,
                                  flag_reason=d.reason))
    db.flush()
    for m in MERCHANTS:
        db.add(Merchant(id=m[0], name=m[1], category=m[2], country="US", risk_score=m[3], high_risk_category=m[4],
                        chargeback_rate=m[5], payout_destination_id=f"DST_{m[0][4:]}"))
    for d in world.devices:
        db.add(Device(id=d.id, fingerprint=d.fingerprint, device_type=d.device_type, os=d.os))
    db.flush()
    for p in PRODUCTS:
        db.add(Product(id=p[0], name=p[1], description=p[2], category=p[3], price=p[4], image=p[5], merchant_id=p[6]))
    for email, name, role, cid in STAFF_USERS:
        db.add(User(email=email, full_name=name, role=role, password_hash=pw, customer_id=cid))
    db.flush()
    for t in world.transactions:
        db.add(Transaction(
            id=t.id, customer_id=t.customer_id, merchant_id=t.merchant_id, device_id=t.device_id,
            destination_id=t.destination_id, amount=t.amount, lat=t.lat, lon=t.lon, channel="SYNTHETIC_HISTORY",
            status="FAILED" if t.failed else "COMPLETED", is_fraud=t.is_fraud, scenario=t.scenario,
            description=t.description, created_at=t.ts,
        ))
    db.add(SystemSetting(key="risk_policy", value=DEFAULT_POLICY))
    db.flush()
    graph_stats = rebuild_graph_tables(db)
    audit.record(db, "SYNTHETIC_ENVIRONMENT_SEEDED", "system", "seed", {
        "customers": len(world.customers), "devices": len(world.devices), "merchants": len(MERCHANTS),
        "transactions": len(world.transactions), "graph": graph_stats, "label": "SYNTHETIC DEMO DATA",
    }, actor_label="system:seed")
    db.commit()

    summary = train_from_db(db, notes="Initial model trained on synthetic history during seeding.")
    score_history(db, summary)
    log.info("Seed complete in %.1fs", time.time() - t0)
    return {"transactions": len(world.transactions), "model_version": summary["version"],
            "primary": summary["primary"], "seconds": round(time.time() - t0, 1)}


def score_history(db: Session, summary: dict) -> None:
    """Score all historical transactions with the newly trained model (stored as predictions).

    Note: historical rows include the training set, so these scores are in-sample; honest model
    quality is reported from the hold-out metrics on the Model Analytics page."""
    mv = db.execute(select(ModelVersion).where(ModelVersion.version == summary["version"],
                                               ModelVersion.is_primary.is_(True))).scalar()
    bundle = load_bundle(mv.artifact_path)
    X, ids = summary["_X"], summary["_ids"]
    preds = predict_frame(bundle, X)
    rebuild_graph_tables(db)  # ensure engine sees entities
    engine = get_engine(db)
    policy = DEFAULT_POLICY
    txns = {t.id: t for t in db.execute(select(Transaction)).scalars()}
    recent_cut = max(t.created_at for t in txns.values()) - timedelta(hours=48)
    for tid, p in zip(ids, preds):
        t = txns[tid]
        level = classify(p["fraud_probability"], policy)
        notes = [f"Model score {p['fraud_probability']:.3f} -> {level} (batch scoring of synthetic history)"]
        if p["anomaly_score"] >= policy["anomaly_escalation"] and level == "LOW":
            level = "MEDIUM"
            notes.append("Anomaly percentile escalation -> MEDIUM")
        sig = engine.customer_signals(t.customer_id, t.device_id, t.destination_id)
        if any(f["destination"] == t.destination_id for f in sig["flagged_destinations"]) or \
                any(s["device"] == t.device_id for s in sig["shared_devices"]):
            if level in ("LOW", "MEDIUM"):
                notes.append("Graph policy escalation -> HIGH")
            level = level_at_least(level, "HIGH")
        db.add(FraudPrediction(
            transaction_id=tid, model_version_id=mv.id, fraud_probability=p["fraud_probability"],
            anomaly_score=p["anomaly_score"], graph_risk_score=sig["graph_risk_score"], risk_level=level,
            recommended_action=ACTIONS[level], top_risk_factors=p["top_risk_factors"],
            shap_values={"space": p["shap_space"], "values": p["shap_values"]}, features=p["features"],
            policy_notes=notes, latency_ms=0.0, created_at=t.created_at,
        ))
        t.risk_level = level
        if level in ("HIGH", "CRITICAL") and t.created_at >= recent_cut and t.status == "COMPLETED":
            t.status = "HELD_FOR_REVIEW"
            t.review_status = "PENDING_REVIEW"
    db.commit()
    rebuild_graph_tables(db)
    db.commit()
