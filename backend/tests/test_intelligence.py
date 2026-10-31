"""ML, risk policy, graph, agent tools, investigation workflow, API and audit tests."""
import math

import pandas as pd
import pytest
from app import audit
from app.agent.tools import (
    EvidenceCollectionTool,
    ToolError,
    customer_behaviour_tool,
    fraud_prediction_tool,
    graph_investigation_tool,
    investigation_report_tool,
    merchant_risk_tool,
    transaction_history_tool,
)
from app.agent.workflow import launch_investigation
from app.db import SessionLocal
from app.graph.engine import get_engine
from app.ml.features import FEATURE_NAMES
from app.ml.predictor import load_bundle, predict_frame
from app.models import AuditLog, Investigation, ModelVersion, Transaction
from app.services.risk import DEFAULT_POLICY, classify, level_at_least
from sqlalchemy import select, text


def test_models_trained_with_honest_metrics(client, reviewer):
    models = client.get("/api/models", headers=reviewer).json()
    algos = {m["algorithm"] for m in models if m["is_active"]}
    assert algos == {"logistic_regression", "random_forest", "xgboost", "isolation_forest"}
    primary = [m for m in models if m["is_primary"]]
    assert len(primary) == 1
    for m in models:
        mt = m["metrics"]
        for k in ("precision", "recall", "f1", "roc_auc", "pr_auc"):
            assert 0 <= mt[k] <= 1
        cm = mt["confusion_matrix"]
        assert cm["tn"] + cm["fp"] + cm["fn"] + cm["tp"] == m["test_rows"]
    # primary is the supervised model with the best hold-out PR-AUC
    sup = [m for m in models if m["is_active"] and m["algorithm"] != "isolation_forest"]
    assert primary[0]["metrics"]["pr_auc"] == max(m["metrics"]["pr_auc"] for m in sup)


def test_ml_prediction_structure(client):
    with SessionLocal() as db:
        mv = db.execute(select(ModelVersion).where(ModelVersion.is_primary.is_(True))).scalar()
        bundle = load_bundle(mv.artifact_path)
    row = {f: 0.0 for f in FEATURE_NAMES} | {"amount": 4200.0, "log_amount": math.log1p(4200), "amount_to_avg_ratio": 60.0,
                                             "device_distinct_customers": 5.0, "destination_flagged": 1.0,
                                             "hours_since_prev": float("nan"), "is_night": 1.0, "hour_of_day": 2.0}
    out = predict_frame(bundle, pd.DataFrame([row], columns=FEATURE_NAMES))[0]
    assert 0 <= out["fraud_probability"] <= 1 and 0 <= out["anomaly_score"] <= 1
    assert set(out["shap_values"]) == set(FEATURE_NAMES)
    assert out["top_risk_factors"] and all(f["shap"] > 0 for f in out["top_risk_factors"])
    assert out["features"]["hours_since_prev"] is None  # missing value preserved as null, imputed in pipeline


def test_risk_classification_policy():
    p = DEFAULT_POLICY
    assert classify(0.05, p) == "LOW"
    assert classify(0.31, p) == "MEDIUM"
    assert classify(0.75, p) == "HIGH"
    assert classify(0.95, p) == "CRITICAL"
    assert level_at_least("LOW", "HIGH") == "HIGH"
    assert level_at_least("CRITICAL", "MEDIUM") == "CRITICAL"  # escalation never lowers risk


def test_transaction_creation_and_assessment(client, reviewer, ava):
    body = {"customer_id": "CUS_0001", "amount": 52.0, "merchant_id": "MER_002", "device_fingerprint": "fp-ava-macbook-air"}
    assert client.post("/api/transactions", json=body).status_code == 401
    assert client.post("/api/transactions", headers=ava, json=body).status_code == 403
    r = client.post("/api/transactions", headers=reviewer, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    risk = out["risk"]
    assert risk["transaction_id"] == out["transaction"]["id"]
    assert risk["risk_level"] == "LOW" and risk["recommended_action"] == "AUTO_APPROVE"
    assert {"fraud_probability", "model_version", "top_risk_factors"} <= set(risk)
    assert out["transaction"]["status"] == "CLEARED"
    detail = client.get(f"/api/transactions/{out['transaction']['id']}", headers=reviewer).json()
    assert detail["predictions"] and any(a["action"] == "RISK_ASSESSED" for a in detail["audit"])
    bad = client.post("/api/transactions", headers=reviewer, json={**body, "amount": -5})
    assert bad.status_code == 422


def test_anomalous_amount_escalates(client, reviewer):
    r = client.post("/api/demo/scenarios/B/run", headers=reviewer)
    assert r.status_code == 200
    risk = r.json()["risk"]
    assert risk["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")
    assert r.json()["status"] in ("HELD_FOR_VERIFICATION", "HELD_FOR_REVIEW")
    assert any("Amount" in f or "amount" in f for f in risk["top_risk_factors"])


def test_graph_detects_fraud_structures(client, reviewer):
    with SessionLocal() as db:
        eng = get_engine(db)
        devices = {s["device"]: s for s in eng.shared_devices}
        assert "DEV_0147" in devices and devices["DEV_0147"]["account_count"] >= 3
        assert any(set(c["customers"]) == {"CUS_0080", "CUS_0081", "CUS_0082", "CUS_0083"} for c in eng.cycles)
        assert {f["destination"] for f in eng.flagged_destinations} == {"DST_MULE_01", "DST_MULE_02"}
        sig = eng.customer_signals("CUS_0003", "DEV_0147", "DST_021")
        assert sig["cluster"]["suspicious"] and sig["graph_risk_score"] >= 0.8
        clean = eng.customer_signals("CUS_0001")
        assert not clean["shared_devices"] and not clean["cycles"] and not clean["flagged_destinations"]
    view = client.get("/api/graph/entity/CUS_0003", headers=reviewer).json()
    assert any(n["ref_id"] == "DEV_0147" for n in view["nodes"])
    assert any(e["suspicious"] and e["evidence"] for e in view["edges"])
    assert client.get("/api/graph/entity/CUS_9999", headers=reviewer).status_code == 404


def test_incremental_graph_matches_full_rebuild(client, reviewer):
    from app.graph.engine import GraphEngine

    with SessionLocal() as db:
        before = get_engine(db)
    # a ring-device payment, a new-device payment and a P2P transfer to a flagged wallet
    for body in ({"customer_id": "CUS_0094", "amount": 410.0, "merchant_id": "MER_021", "device_fingerprint": "fp-ring-emulator-02"},
                 {"customer_id": "CUS_0010", "amount": 35.0, "merchant_id": "MER_002", "device_fingerprint": "fp-incremental-new-01"},
                 {"customer_id": "CUS_0012", "amount": 120.0, "destination_id": "DST_MULE_01", "device_fingerprint": "fp-incremental-new-02"}):
        assert client.post("/api/transactions", headers=reviewer, json=body).status_code == 200
    with SessionLocal() as db:
        live = get_engine(db)
        assert live is before  # updated in place, not rebuilt
        fresh = GraphEngine(db, -1)
    assert live.summary() == fresh.summary()
    assert sorted(map(str, live.shared_devices)) == sorted(map(str, fresh.shared_devices))
    assert sorted(map(str, live.flagged_destinations)) == sorted(map(str, fresh.flagged_destinations))
    for cid in ("CUS_0094", "CUS_0010", "CUS_0012", "CUS_0003"):
        assert live.customer_signals(cid)["graph_risk_score"] == fresh.customer_signals(cid)["graph_risk_score"]


def test_agent_tools_return_real_records(client):
    with SessionLocal() as db:
        txn = db.execute(select(Transaction).where(Transaction.customer_id == "CUS_0003")
                         .order_by(Transaction.created_at.desc())).scalars().first()
        th = transaction_history_tool(db, transaction_id=txn.id)
        assert th["transaction"]["id"] == txn.id and all(r["id"] != txn.id for r in th["recent"])
        cb = customer_behaviour_tool(db, "CUS_0003", txn.id)
        assert cb["prior_transactions"] == len(th["recent"]) or cb["prior_transactions"] >= len(th["recent"])
        fp = fraud_prediction_tool(db, txn.id)
        assert fp["transaction_id"] == txn.id
        g = graph_investigation_tool(db, "CUS_0003", txn.id)
        assert g["shared_devices"]
        m = merchant_risk_tool(db, "MER_021")
        assert m["high_risk_category"] is True
        with pytest.raises(ToolError):
            transaction_history_tool(db, transaction_id="TXN_DOES_NOT_EXIST")
        ev = EvidenceCollectionTool()
        ev.from_prediction(fp)
        ev.from_behaviour(cb)
        ev.from_graph(g)
        ev.from_merchant(m)
        keys = ev.keys()
        assert keys and any(e["category"] == "SHARED_DEVICE" for e in ev.items)
        draft = {"risk_level": "HIGH", "summary": "s", "recommendation": "REJECT", "rationale": "r", "findings": [
            {"statement": "Supported", "evidence_keys": [sorted(keys)[0]]},
            {"statement": "Invented claim", "evidence_keys": ["E999"]},
            {"statement": "No citation", "evidence_keys": []},
        ]}
        rep = investigation_report_tool(draft, ev, "LLM_AGENT", txn.id)
        assert len(rep["findings"]) == 1 and len(rep["rejected_findings"]) == 2
        bad_rec = investigation_report_tool({**draft, "recommendation": "CAPTURE_NOW"}, ev, "LLM_AGENT", txn.id)
        assert bad_rec["recommendation"] == "HOLD_FOR_REVIEW"
        with pytest.raises(ToolError):
            investigation_report_tool({**draft, "findings": [{"statement": "x", "evidence_keys": ["E999"]}]}, ev, "LLM_AGENT", txn.id)


def test_investigation_workflow_deterministic_fallback(client, reviewer):
    import time

    run = client.post("/api/demo/scenarios/C/run", headers=reviewer).json()
    inv_id = run["investigation_id"]  # demo C auto-launches the agent; a second launch dedupes to it
    assert launch_investigation(run["transaction_id"], None) == inv_id
    for _ in range(120):
        inv = client.get(f"/api/investigations/{inv_id}", headers=reviewer).json()
        if inv["status"] != "RUNNING":
            break
        time.sleep(0.25)
    assert inv["status"] == "COMPLETED", inv.get("error")
    assert inv["mode"] == "DETERMINISTIC_FALLBACK"  # no GROQ_API_KEY in tests; clearly labelled
    names = [s["tool"] for s in inv["steps"]]
    for tool in ("TransactionHistoryTool", "CustomerBehaviourTool", "FraudPredictionTool", "GraphInvestigationTool",
                 "MerchantRiskTool", "EvidenceCollectionTool", "InvestigationReportTool"):
        assert tool in names
    rep = inv["report"]
    keys = {e["key"] for e in inv["evidence"]}
    assert rep["findings"] and all(set(f["evidence_keys"]) <= keys for f in rep["findings"])
    assert rep["recommendation"] in ("HOLD_FOR_REVIEW", "REJECT", "ESCALATE")
    # agent never moves money
    txn = client.get(f"/api/transactions/{run['transaction_id']}", headers=reviewer).json()["transaction"]
    assert txn["status"] in ("HELD_FOR_REVIEW", "HELD_FOR_VERIFICATION")


def test_rbac_and_auth(client, ava, reviewer):
    assert client.get("/api/dashboard/metrics").status_code == 401
    assert client.get("/api/dashboard/metrics", headers=ava).status_code == 403
    assert client.get("/api/dashboard/metrics", headers={"Authorization": "Bearer forged.token.value"}).status_code == 401
    assert client.put("/api/settings/risk-policy", headers=reviewer, json=DEFAULT_POLICY).status_code == 403
    assert client.post("/api/auth/login", json={"email": "reviewer@sentinel.dev", "password": "nope"}).status_code == 401
    m = client.get("/api/dashboard/metrics", headers=reviewer).json()
    assert m["kpis"]["transactions_analysed"] >= 2000


def test_audit_chain_detects_tampering(client):
    with SessionLocal() as db:
        assert audit.verify_chain(db)["valid"] is True
        row = db.execute(select(AuditLog).order_by(AuditLog.id).limit(1).offset(3)).scalar()
        original = row.details
        db.execute(text("UPDATE audit_logs SET details = :d WHERE id = :i"), {"d": '{"tampered": true}', "i": row.id})
        db.commit()
        res = audit.verify_chain(db)
        assert res["valid"] is False and res["broken_at_id"] == row.id
        db.execute(text("UPDATE audit_logs SET details = :d WHERE id = :i"),
                   {"d": __import__("json").dumps(original), "i": row.id})
        db.commit()
        assert audit.verify_chain(db)["valid"] is True


def test_investigations_persisted(client):
    with SessionLocal() as db:
        inv = db.execute(select(Investigation).where(Investigation.status == "COMPLETED")).scalars().first()
        assert inv is not None and inv.evidence and inv.report["notice"].startswith("Recommendation only")
