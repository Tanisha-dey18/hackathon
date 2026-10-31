"""Risk engine: ML score + anomaly score + graph signals -> policy-governed risk level and action."""
from __future__ import annotations

import threading
import time

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..graph.engine import get_engine
from ..infra import ws_manager
from ..ml.features import FEATURE_NAMES, FeatureState, StaticContext, TxnRecord, record_from_txn
from ..ml.predictor import load_bundle, predict_frame
from ..models import (
    Customer,
    FraudPrediction,
    Merchant,
    ModelVersion,
    PaymentDestination,
    SystemSetting,
    Transaction,
    User,
)

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ACTIONS = {
    "LOW": "AUTO_APPROVE",
    "MEDIUM": "ADDITIONAL_VERIFICATION",
    "HIGH": "MANUAL_REVIEW",
    "CRITICAL": "MANUAL_REVIEW_AND_INVESTIGATE",
}
DEFAULT_POLICY = {
    "low_max": 0.30,  # p < low_max -> LOW
    "medium_max": 0.70,  # p < medium_max -> MEDIUM
    "high_max": 0.90,  # p < high_max -> HIGH, else CRITICAL
    "anomaly_escalation": 0.98,  # anomaly percentile at/above which risk is at least MEDIUM
    "amount_ratio_escalation": 10.0,  # amount >= N x customer average -> at least MEDIUM
    "graph_escalation": True,  # shared-device rings / flagged destinations / cycles -> at least HIGH
    "auto_investigate_levels": ["HIGH", "CRITICAL"],
}


def get_policy(db: Session) -> dict:
    row = db.get(SystemSetting, "risk_policy")
    return {**DEFAULT_POLICY, **(row.value if row else {})}


def level_at_least(level: str, floor: str) -> str:
    return RISK_LEVELS[max(RISK_LEVELS.index(level), RISK_LEVELS.index(floor))]


def classify(prob: float, policy: dict) -> str:
    if prob < policy["low_max"]:
        return "LOW"
    if prob < policy["medium_max"]:
        return "MEDIUM"
    if prob < policy["high_max"]:
        return "HIGH"
    return "CRITICAL"


# ------------------------------------------------------------------ shared state
_state_lock = threading.Lock()
_feature_state: FeatureState | None = None


def static_context(db: Session) -> StaticContext:
    return StaticContext(
        merchants={m.id: (m.risk_score, m.high_risk_category) for m in db.execute(select(Merchant)).scalars()},
        destinations={d.id: d.is_flagged for d in db.execute(select(PaymentDestination)).scalars()},
        homes={c.id: (c.home_lat, c.home_lon) for c in db.execute(select(Customer)).scalars()},
    )


def reset_feature_state() -> None:
    global _feature_state
    with _state_lock:
        _feature_state = None


def feature_state(db: Session) -> FeatureState:
    """History-backed feature state; built once from the DB, then updated incrementally."""
    global _feature_state
    with _state_lock:
        if _feature_state is None:
            st = FeatureState(static_context(db))
            assessed = select(FraudPrediction.transaction_id).distinct()
            q = select(Transaction).where(
                (Transaction.channel == "SYNTHETIC_HISTORY") | Transaction.id.in_(assessed)
            ).order_by(Transaction.created_at)
            for t in db.execute(q).scalars():
                st.add(record_from_txn(t))
            _feature_state = st
        return _feature_state


def active_model(db: Session) -> ModelVersion:
    mv = db.execute(
        select(ModelVersion).where(ModelVersion.is_active.is_(True), ModelVersion.is_primary.is_(True))
        .order_by(ModelVersion.id.desc())
    ).scalar()
    if not mv:
        raise HTTPException(503, "No trained model is active. Run the seed/training pipeline.")
    return mv


def assess_transaction(db: Session, txn: Transaction, actor: User | None = None) -> FraudPrediction:
    """Score one transaction, apply the configured policy, persist and audit the result."""
    t0 = time.perf_counter()
    mv = active_model(db)
    bundle = load_bundle(mv.artifact_path)
    policy = get_policy(db)
    st = feature_state(db)

    # The destination flag can change after the feature state was built (reviewer decisions)
    dest = db.get(PaymentDestination, txn.destination_id)
    st.ctx.destinations[txn.destination_id] = bool(dest and dest.is_flagged)

    rec: TxnRecord = record_from_txn(txn)
    feats = st.features(rec)
    pred = predict_frame(bundle, pd.DataFrame([feats], columns=FEATURE_NAMES))[0]
    prob = pred["fraud_probability"]

    level = classify(prob, policy)
    notes: list[str] = [f"Model score {prob:.3f} ({pred['model_algorithm']} {mv.version}) -> {level}"]

    if pred["anomaly_score"] >= policy["anomaly_escalation"] and level == "LOW":
        level = "MEDIUM"
        notes.append(f"Isolation Forest anomaly percentile {pred['anomaly_score']:.3f} >= {policy['anomaly_escalation']} -> at least MEDIUM")
    ratio = feats.get("amount_to_avg_ratio")
    if ratio is not None and ratio == ratio and ratio >= policy["amount_ratio_escalation"] and RISK_LEVELS.index(level) < 1:
        level = "MEDIUM"
        notes.append(f"Amount is {ratio:.1f}x customer average (>= {policy['amount_ratio_escalation']}x) -> at least MEDIUM")

    signals = get_engine(db).customer_signals(txn.customer_id, txn.device_id, txn.destination_id)
    graph_score = signals["graph_risk_score"]
    if policy["graph_escalation"]:
        reasons = []
        if signals["flagged_destinations"] and any(f["destination"] == txn.destination_id for f in signals["flagged_destinations"]):
            reasons.append("payment to a flagged destination")
        if any(s["device"] == txn.device_id for s in signals["shared_devices"]):
            reasons.append(f"device shared by {signals['device_account_count']} accounts")
        if signals["cycles"]:
            reasons.append("account participates in a circular payment loop")
        if reasons and RISK_LEVELS.index(level) < 2:
            level = "HIGH"
            notes.append("Graph policy: " + "; ".join(reasons) + " -> at least HIGH")
        elif reasons:
            notes.append("Graph signals present: " + "; ".join(reasons))

    latency = (time.perf_counter() - t0) * 1000
    fp = FraudPrediction(
        transaction_id=txn.id,
        model_version_id=mv.id,
        fraud_probability=prob,
        anomaly_score=pred["anomaly_score"],
        graph_risk_score=graph_score,
        risk_level=level,
        recommended_action=ACTIONS[level],
        top_risk_factors=pred["top_risk_factors"],
        shap_values={"space": pred["shap_space"], "values": pred["shap_values"]},
        features=pred["features"],
        policy_notes=notes,
        latency_ms=round(latency, 2),
    )
    db.add(fp)
    txn.risk_level = level
    db.flush()
    st.add(rec)
    audit.record(db, "RISK_ASSESSED", "transaction", txn.id, {
        "fraud_probability": prob, "risk_level": level, "anomaly_score": pred["anomaly_score"],
        "graph_risk_score": graph_score, "model_version": mv.version, "algorithm": mv.algorithm,
        "policy_notes": notes,
    }, actor=actor)
    ws_manager.broadcast("transaction.assessed", {
        "transaction_id": txn.id, "risk_level": level, "fraud_probability": prob, "amount": float(txn.amount),
        "customer_id": txn.customer_id, "channel": txn.channel,
    })
    return fp


def prediction_payload(fp: FraudPrediction) -> dict:
    """Structured risk result as exposed by the API."""
    return {
        "transaction_id": fp.transaction_id,
        "fraud_probability": fp.fraud_probability,
        "anomaly_score": fp.anomaly_score,
        "graph_risk_score": fp.graph_risk_score,
        "risk_level": fp.risk_level,
        "model_version": fp.model_version.version if fp.model_version else None,
        "model_algorithm": fp.model_version.algorithm if fp.model_version else None,
        "top_risk_factors": [f["description"] for f in fp.top_risk_factors],
        "top_risk_factor_details": fp.top_risk_factors,
        "recommended_action": fp.recommended_action,
        "policy_notes": fp.policy_notes,
        "shap": fp.shap_values,
        "features": fp.features,
        "latency_ms": fp.latency_ms,
        "assessed_at": fp.created_at,
    }
