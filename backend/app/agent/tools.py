"""Investigation tools. Each tool reads real records from the database and returns a JSON-safe
result; evidence items are derived deterministically from these outputs so every statement in a
report can be traced to a tool output."""
from __future__ import annotations

import math
import statistics
from collections import Counter
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..graph.engine import get_engine
from ..ml.features import aware, haversine_km
from ..models import (
    Customer,
    Device,
    FraudPrediction,
    Merchant,
    PaymentDestination,
    Transaction,
)


class ToolError(Exception):
    pass


def _txn_brief(t: Transaction) -> dict:
    return {
        "id": t.id, "amount": float(t.amount), "merchant_id": t.merchant_id, "device_id": t.device_id,
        "destination_id": t.destination_id, "status": t.status, "risk_level": t.risk_level,
        "created_at": aware(t.created_at).isoformat(), "channel": t.channel,
    }


# 1 ------------------------------------------------------------------------------------------
def transaction_history_tool(db: Session, transaction_id: str | None = None, customer_id: str | None = None,
                             limit: int = 25) -> dict:
    """TransactionHistoryTool: the focal transaction (if given) and the customer's recent history."""
    focal = None
    if transaction_id:
        focal = db.get(Transaction, transaction_id)
        if not focal:
            raise ToolError(f"Transaction {transaction_id} not found")
        customer_id = focal.customer_id
    if not customer_id or not db.get(Customer, customer_id):
        raise ToolError(f"Customer {customer_id} not found")
    q = select(Transaction).where(Transaction.customer_id == customer_id)
    if focal:
        q = q.where(Transaction.id != focal.id, Transaction.created_at <= focal.created_at)
    hist = list(db.execute(q.order_by(Transaction.created_at.desc()).limit(limit)).scalars())
    total = db.execute(select(func.count()).select_from(Transaction).where(Transaction.customer_id == customer_id)).scalar()
    out = {
        "tool": "TransactionHistoryTool",
        "customer_id": customer_id,
        "total_transactions": total,
        "recent": [_txn_brief(t) for t in hist],
    }
    if focal:
        c = focal.customer
        out["transaction"] = {
            **_txn_brief(focal), "customer_name": c.name, "customer_city": c.city,
            "merchant_name": focal.merchant.name if focal.merchant else None,
            "destination_label": focal.destination.label, "lat": focal.lat, "lon": focal.lon,
            "description": focal.description, "scenario": focal.scenario,
        }
    out["summary"] = (f"Customer {customer_id} has {total} transactions on record; returned {len(hist)} prior."
                      + (f" Focal {focal.id}: ${float(focal.amount):,.2f}." if focal else ""))
    return out


# 2 ------------------------------------------------------------------------------------------
def customer_behaviour_tool(db: Session, customer_id: str, transaction_id: str | None = None) -> dict:
    """CustomerBehaviourTool: spending baseline, devices, locations and failure history."""
    c = db.get(Customer, customer_id)
    if not c:
        raise ToolError(f"Customer {customer_id} not found")
    focal = db.get(Transaction, transaction_id) if transaction_id else None
    q = select(Transaction).where(Transaction.customer_id == customer_id)
    if focal:
        q = q.where(Transaction.id != focal.id, Transaction.created_at <= focal.created_at)
    hist = list(db.execute(q.order_by(Transaction.created_at)).scalars())
    ok = [float(t.amount) for t in hist if t.status not in ("FAILED", "CAPTURE_FAILED", "REJECTED")]
    devices = Counter(t.device_id for t in hist)
    out: dict = {
        "tool": "CustomerBehaviourTool",
        "customer_id": customer_id, "name": c.name, "home_city": c.city, "segment": c.segment,
        "account_created": aware(c.created_at).isoformat(),
        "prior_transactions": len(hist),
        "avg_amount": round(statistics.mean(ok), 2) if ok else None,
        "median_amount": round(statistics.median(ok), 2) if ok else None,
        "std_amount": round(statistics.stdev(ok), 2) if len(ok) > 1 else None,
        "max_amount": round(max(ok), 2) if ok else None,
        "devices": [{"device_id": d, "transactions": n} for d, n in devices.most_common()],
        "failed_attempts": sum(1 for t in hist if t.status == "FAILED"),
        "night_transactions": sum(1 for t in hist if aware(t.created_at).hour < 5),
        "distinct_merchants": len({t.merchant_id for t in hist if t.merchant_id}),
    }
    if focal:
        ts = aware(focal.created_at)
        out["current"] = {
            "amount": float(focal.amount),
            "device_id": focal.device_id,
            "amount_to_avg_ratio": round(float(focal.amount) / out["avg_amount"], 2) if out["avg_amount"] else None,
            "device_known": focal.device_id in devices,
            "device_prior_uses": devices.get(focal.device_id, 0),
            "distance_from_home_km": round(haversine_km(c.home_lat, c.home_lon, focal.lat, focal.lon), 1),
            "txns_prior_1h": sum(1 for t in hist if ts - aware(t.created_at) <= timedelta(hours=1)),
            "failed_prior_24h": sum(1 for t in hist if t.status == "FAILED" and ts - aware(t.created_at) <= timedelta(hours=24)),
            "hour_utc": ts.hour,
        }
        if hist:
            prev = hist[-1]
            hours = max((ts - aware(prev.created_at)).total_seconds() / 3600, 1e-3)
            dist = haversine_km(prev.lat, prev.lon, focal.lat, focal.lon)
            out["current"]["previous_transaction"] = {"id": prev.id, "hours_before": round(hours, 2),
                                                      "distance_km": round(dist, 1),
                                                      "implied_speed_kmh": round(dist / hours, 1)}
    out["summary"] = (f"{c.name}: {len(hist)} prior transactions, average ${out['avg_amount'] or 0:,.2f}, "
                      f"{len(devices)} device(s), {out['failed_attempts']} failed attempts.")
    return out


# 3 ------------------------------------------------------------------------------------------
def fraud_prediction_tool(db: Session, transaction_id: str) -> dict:
    """FraudPredictionTool: the stored ML assessment with SHAP attributions."""
    fp = db.execute(select(FraudPrediction).where(FraudPrediction.transaction_id == transaction_id)
                    .order_by(FraudPrediction.id.desc())).scalar()
    if not fp:
        raise ToolError(f"No ML prediction exists for {transaction_id}")
    return {
        "tool": "FraudPredictionTool",
        "transaction_id": transaction_id,
        "fraud_probability": fp.fraud_probability,
        "anomaly_percentile": fp.anomaly_score,
        "graph_risk_score": fp.graph_risk_score,
        "risk_level": fp.risk_level,
        "recommended_action": fp.recommended_action,
        "model_version": fp.model_version.version,
        "model_algorithm": fp.model_version.algorithm,
        "top_risk_factors": fp.top_risk_factors,
        "policy_notes": fp.policy_notes,
        "summary": f"{fp.model_version.algorithm} {fp.model_version.version} scored {fp.fraud_probability:.3f} "
                   f"({fp.risk_level}); anomaly percentile {fp.anomaly_score:.3f}.",
    }


# 4 ------------------------------------------------------------------------------------------
def graph_investigation_tool(db: Session, entity_id: str, transaction_id: str | None = None) -> dict:
    """GraphInvestigationTool: shared devices, flagged destinations, cycles and cluster membership."""
    eng = get_engine(db)
    t = db.get(Transaction, transaction_id) if transaction_id else None
    if entity_id.startswith("CUS_"):
        sig = eng.customer_signals(entity_id, t.device_id if t else None, t.destination_id if t else None)
    elif entity_id.startswith("DEV_"):
        dev = next((s for s in eng.shared_devices if s["device"] == entity_id), None)
        n = f"DEVICE:{entity_id}"
        accounts = sorted(eng.P.nodes[m]["ref_id"] for m in eng.P.neighbors(n)) if eng.P.has_node(n) else []
        sig = {"device": entity_id, "accounts": accounts, "shared_device": dev}
    elif entity_id.startswith("DST_"):
        n = f"DESTINATION:{entity_id}"
        if not eng.P.has_node(n):
            raise ToolError(f"Destination {entity_id} not in graph")
        payers = [eng.P.nodes[m]["ref_id"] for m in eng.P.neighbors(n) if eng.P[n][m]["rel"] == "PAID_TO"]
        fd = next((f for f in eng.flagged_destinations if f["destination"] == entity_id), None)
        sig = {"destination": entity_id, "flagged": bool(fd), "payers": sorted(payers)[:30], "payer_count": len(payers),
               "flagged_detail": fd}
    else:
        raise ToolError(f"Unsupported entity {entity_id}")
    sig = {"tool": "GraphInvestigationTool", "entity_id": entity_id, **sig}
    parts = []
    if sig.get("shared_devices"):
        parts.append(f"{len(sig['shared_devices'])} shared device(s)")
    if sig.get("flagged_destinations"):
        parts.append(f"{len(sig['flagged_destinations'])} flagged destination link(s)")
    if sig.get("cycles"):
        parts.append(f"{len(sig['cycles'])} circular payment loop(s)")
    if sig.get("cluster") and sig["cluster"].get("suspicious"):
        parts.append(f"suspicious cluster #{sig['cluster']['cluster_id']} ({len(sig['cluster']['customers'])} accounts)")
    if "accounts" in sig:
        parts.append(f"device used by {len(sig['accounts'])} account(s)")
    if "payer_count" in sig:
        parts.append(f"{sig['payer_count']} paying account(s){' - FLAGGED' if sig['flagged'] else ''}")
    sig["summary"] = f"Graph analysis of {entity_id}: " + (", ".join(parts) if parts else "no suspicious relationships found")
    return sig


# 5 ------------------------------------------------------------------------------------------
def merchant_risk_tool(db: Session, merchant_id: str) -> dict:
    """MerchantRiskTool: merchant profile and observed outcomes."""
    m = db.get(Merchant, merchant_id)
    if not m:
        raise ToolError(f"Merchant {merchant_id} not found")
    rows = db.execute(select(Transaction.is_fraud, Transaction.risk_level).where(Transaction.merchant_id == merchant_id)).all()
    labelled = [r[0] for r in rows if r[0] is not None]
    high = sum(1 for r in rows if r[1] in ("HIGH", "CRITICAL"))
    out = {
        "tool": "MerchantRiskTool",
        "merchant_id": m.id, "name": m.name, "category": m.category, "country": m.country,
        "risk_score": m.risk_score, "high_risk_category": m.high_risk_category, "chargeback_rate": m.chargeback_rate,
        "transactions": len(rows), "high_risk_transactions": high,
        "historical_fraud_rate": round(sum(labelled) / len(labelled), 4) if labelled else None,
    }
    out["summary"] = (f"{m.name} ({m.category}): risk score {m.risk_score:.2f}, chargeback rate "
                      f"{m.chargeback_rate:.1%}, {high}/{len(rows)} high-risk transactions.")
    return out


# 6 ------------------------------------------------------------------------------------------
class EvidenceCollectionTool:
    """Derives typed evidence items (E1, E2, ...) from tool outputs using fixed, auditable rules."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def _add(self, tool: str, category: str, severity: str, summary: str, data: dict | None = None,
             mitigating: bool = False) -> None:
        self.items.append({"key": f"E{len(self.items) + 1}", "tool": tool, "category": category,
                           "severity": severity, "summary": summary, "data": data or {}, "mitigating": mitigating})

    def from_behaviour(self, b: dict) -> None:
        cur = b.get("current") or {}
        tool = "CustomerBehaviourTool"
        r = cur.get("amount_to_avg_ratio")
        if r is not None:
            if r >= 10:
                self._add(tool, "AMOUNT_ANOMALY", "HIGH", f"Transaction amount ${cur['amount']:,.2f} is {r:.1f}x the customer's historical average of ${b['avg_amount']:,.2f}.", {"ratio": r})
            elif r >= 3:
                self._add(tool, "AMOUNT_ANOMALY", "MEDIUM", f"Transaction amount ${cur['amount']:,.2f} is {r:.1f}x the customer's historical average of ${b['avg_amount']:,.2f}.", {"ratio": r})
            else:
                self._add(tool, "AMOUNT_BASELINE", "INFO", f"Amount ${cur['amount']:,.2f} is within the customer's normal range ({r:.1f}x average).", {"ratio": r}, mitigating=True)
        elif b.get("prior_transactions", 0) == 0:
            self._add(tool, "NO_HISTORY", "MEDIUM", "Customer has no prior transaction history to compare against.")
        if cur:
            if not cur.get("device_known") and b.get("prior_transactions", 0) > 0:
                self._add(tool, "NEW_DEVICE", "MEDIUM", f"The device used ({cur.get('device_id')}) has never been used by this customer before.", {"device_prior_uses": 0})
            elif cur.get("device_known"):
                self._add(tool, "KNOWN_DEVICE", "INFO", f"Device previously used by this customer in {cur['device_prior_uses']} transaction(s).", mitigating=True)
            if cur.get("distance_from_home_km", 0) > 1500:
                self._add(tool, "GEO_ANOMALY", "HIGH", f"Transaction located {cur['distance_from_home_km']:,.0f} km from the customer's home ({b['home_city']}).")
            prev = cur.get("previous_transaction")
            if prev and prev["implied_speed_kmh"] > 900 and prev["distance_km"] > 300:
                self._add(tool, "IMPOSSIBLE_TRAVEL", "HIGH", f"{prev['distance_km']:,.0f} km from previous transaction {prev['id']} only {prev['hours_before']:.1f}h earlier (implied {prev['implied_speed_kmh']:,.0f} km/h).", prev)
            if cur.get("failed_prior_24h", 0) >= 3:
                self._add(tool, "CARD_TESTING", "HIGH", f"{cur['failed_prior_24h']} failed payment attempts in the 24 hours before this transaction.")
            if cur.get("txns_prior_1h", 0) >= 3:
                self._add(tool, "VELOCITY", "MEDIUM", f"{cur['txns_prior_1h']} transactions by this customer in the hour before this one.")

    def from_prediction(self, p: dict) -> None:
        sev = {"LOW": "INFO", "MEDIUM": "MEDIUM", "HIGH": "HIGH", "CRITICAL": "HIGH"}[p["risk_level"]]
        self._add("FraudPredictionTool", "ML_SCORE", sev,
                  f"{p['model_algorithm']} model {p['model_version']} fraud probability {p['fraud_probability']:.3f}; "
                  f"final policy risk level {p['risk_level']}" + (f" ({p['policy_notes'][-1]})" if len(p.get('policy_notes') or []) > 1 else "") + ".",
                  {"fraud_probability": p["fraud_probability"]}, mitigating=p["risk_level"] == "LOW")
        if p["anomaly_percentile"] >= 0.95:
            self._add("FraudPredictionTool", "ANOMALY", "MEDIUM",
                      f"Isolation Forest ranks this transaction more anomalous than {p['anomaly_percentile']:.1%} of training transactions.")
        factors = p.get("top_risk_factors") or []
        if factors:
            self._add("FraudPredictionTool", "SHAP_DRIVERS", "INFO",
                      "Top SHAP risk drivers: " + "; ".join(f["description"] for f in factors[:4]) + ".",
                      {"factors": factors[:4]})

    def from_graph(self, g: dict) -> None:
        tool = "GraphInvestigationTool"
        for s in g.get("shared_devices") or []:
            self._add(tool, "SHARED_DEVICE", "HIGH",
                      f"Device {s['device']} is shared by {s['account_count']} accounts ({', '.join(s['customers'][:6])}{'...' if len(s['customers']) > 6 else ''}); {s['high_risk_accounts']} of them have high-risk transactions.",
                      {"device": s["device"], "customers": s["customers"]})
        for f in g.get("flagged_destinations") or []:
            self._add(tool, "FLAGGED_DESTINATION", "HIGH",
                      f"Destination {f['destination']} is flagged ({f['reason'] or 'prior fraud'}); it received {f['payment_count']} payments totalling ${f['total_amount']:,.2f} from {len(f['customers'])} accounts.",
                      {"destination": f["destination"], "customers": f["customers"]})
        for c in g.get("cycles") or []:
            self._add(tool, "CIRCULAR_PAYMENTS", "HIGH",
                      f"Customer is part of a {c['length']}-account circular payment loop ({' -> '.join(c['customers'] + [c['customers'][0]])}) moving ${c['total_amount']:,.2f}.",
                      {"customers": c["customers"]})
        cl = g.get("cluster")
        if cl and cl.get("suspicious"):
            self._add(tool, "SUSPICIOUS_CLUSTER", "HIGH" if len(cl["customers"]) >= 4 else "MEDIUM",
                      f"Customer belongs to cluster #{cl['cluster_id']} of {len(cl['customers'])} linked accounts: {'; '.join(cl['reasons'])}.",
                      {"cluster_id": cl["cluster_id"], "customers": cl["customers"]})
        if not any(g.get(k) for k in ("shared_devices", "flagged_destinations", "cycles")) and not (cl and cl.get("suspicious")) and "accounts" not in g and "payer_count" not in g:
            self._add(tool, "GRAPH_CLEAN", "INFO", "No shared-device rings, flagged destinations or circular payments linked to this customer.", mitigating=True)
        if "accounts" in g:
            n = len(g["accounts"])
            self._add(tool, "DEVICE_ACCOUNTS", "HIGH" if n >= 3 else "INFO", f"Device {g['device']} is linked to {n} account(s): {', '.join(g['accounts'][:8])}.", {"accounts": g["accounts"]})
        if "payer_count" in g:
            self._add(tool, "DESTINATION_PAYERS", "HIGH" if g["flagged"] else "INFO",
                      f"Destination {g['destination']} receives funds from {g['payer_count']} account(s){' and is flagged' if g['flagged'] else ''}.", {"payers": g["payers"]})

    def from_merchant(self, m: dict) -> None:
        if m["high_risk_category"]:
            self._add("MerchantRiskTool", "MERCHANT_RISK", "MEDIUM",
                      f"Merchant {m['name']} operates in a high-risk category ({m['category']}) with risk score {m['risk_score']:.2f} and chargeback rate {m['chargeback_rate']:.1%}.")
        else:
            self._add("MerchantRiskTool", "MERCHANT_RISK", "INFO",
                      f"Merchant {m['name']} ({m['category']}) is standard risk (score {m['risk_score']:.2f}).", mitigating=True)

    def keys(self) -> set[str]:
        return {e["key"] for e in self.items}


# 7 ------------------------------------------------------------------------------------------
RECOMMENDATIONS = ("APPROVE", "HOLD_FOR_REVIEW", "REJECT", "ESCALATE")


def investigation_report_tool(draft: dict, evidence: EvidenceCollectionTool, mode: str, transaction_id: str) -> dict:
    """InvestigationReportTool: validates a report draft against collected evidence.
    Findings that cite no valid evidence key are removed and listed as rejected."""
    valid = evidence.keys()
    accepted, rejected = [], []
    for f in draft.get("findings") or []:
        keys = [k for k in (f.get("evidence_keys") or []) if k in valid]
        if keys and f.get("statement"):
            accepted.append({"statement": str(f["statement"])[:500], "evidence_keys": keys})
        else:
            rejected.append({"statement": str(f.get("statement"))[:300], "reason": "cites no valid evidence key"})
    rec = draft.get("recommendation")
    if rec not in RECOMMENDATIONS:
        rejected.append({"statement": f"recommendation={rec}", "reason": "invalid recommendation; defaulted to HOLD_FOR_REVIEW"})
        rec = "HOLD_FOR_REVIEW"
    risk = draft.get("risk_level") if draft.get("risk_level") in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else None
    if not accepted:
        raise ToolError("Report has no findings backed by evidence")
    return {
        "transaction_id": transaction_id,
        "mode": mode,
        "risk_level": risk,
        "summary": str(draft.get("summary") or "")[:1200],
        "findings": accepted,
        "recommendation": rec,
        "rationale": str(draft.get("rationale") or "")[:1200],
        "rejected_findings": rejected,
        "evidence_count": len(evidence.items),
        "notice": "Recommendation only. The agent cannot capture, refund or reject payments; a human reviewer decides.",
    }
