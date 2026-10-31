"""LangGraph investigation workflow.

retrieve_transaction -> customer_behaviour -> ml_prediction -> graph_investigation -> merchant_risk
-> collect_evidence -> analyse (Groq LLM with tool calling, or labelled deterministic fallback)
-> generate_report (evidence-validated) -> route_to_reviewer

The agent never executes payment operations; it can only recommend.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import SessionLocal
from ..infra import ws_manager
from ..models import FraudPrediction, Investigation, InvestigationEvidence, Transaction, utcnow
from ..services.transactions import new_id
from .tools import (
    RECOMMENDATIONS,
    EvidenceCollectionTool,
    ToolError,
    customer_behaviour_tool,
    fraud_prediction_tool,
    graph_investigation_tool,
    investigation_report_tool,
    merchant_risk_tool,
    transaction_history_tool,
)

log = logging.getLogger("sentinel.agent")


class InvState(TypedDict, total=False):
    transaction_id: str
    customer_id: str
    merchant_id: str | None
    device_id: str
    destination_id: str
    outputs: dict[str, Any]
    draft: dict
    report: dict
    mode: str
    llm_note: str | None


SYSTEM_PROMPT = """You are SENTINEL's payment fraud investigation analyst.
Rules you must follow:
1. Use ONLY facts contained in the evidence items and tool results you are given. Never invent transactions, amounts, accounts, devices, or evidence.
2. Every finding must cite one or more evidence keys (e.g. "E3"). Findings without valid keys are discarded.
3. You may call the investigation tools to examine related entities (other customers, devices, destinations, merchants) before concluding. New evidence keys are returned when you do.
4. You cannot move money. You may only recommend one of: APPROVE, HOLD_FOR_REVIEW, REJECT, ESCALATE. A human reviewer makes the final decision.
5. Weigh mitigating evidence (marked mitigating) as well as risk evidence. Be concise and factual.
6. Finish by calling submit_investigation_report exactly once."""

LLM_TOOLS = [
    {"type": "function", "function": {
        "name": "transaction_history", "description": "Recent transactions for a customer.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {
        "name": "customer_behaviour", "description": "Spending baseline, devices and failures for a customer.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {
        "name": "graph_investigation", "description": "Graph relationships for an entity id (CUS_..., DEV_..., DST_...).",
        "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}}},
    {"type": "function", "function": {
        "name": "merchant_risk", "description": "Risk profile of a merchant (MER_...).",
        "parameters": {"type": "object", "properties": {"merchant_id": {"type": "string"}}, "required": ["merchant_id"]}}},
    {"type": "function", "function": {
        "name": "submit_investigation_report", "description": "Submit the final structured investigation report.",
        "parameters": {"type": "object", "properties": {
            "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            "summary": {"type": "string", "description": "2-4 sentence executive summary"},
            "findings": {"type": "array", "items": {"type": "object", "properties": {
                "statement": {"type": "string"},
                "evidence_keys": {"type": "array", "items": {"type": "string"}}},
                "required": ["statement", "evidence_keys"]}},
            "recommendation": {"type": "string", "enum": list(RECOMMENDATIONS)},
            "rationale": {"type": "string"}},
            "required": ["risk_level", "summary", "findings", "recommendation", "rationale"]}}},
]


def deterministic_draft(ev: EvidenceCollectionTool, prediction: dict | None) -> dict:
    """Rule-based report used when Groq is not configured or fails. Clearly labelled as such."""
    high = [e for e in ev.items if e["severity"] == "HIGH" and not e["mitigating"]]
    med = [e for e in ev.items if e["severity"] == "MEDIUM" and not e["mitigating"]]
    mitig = [e for e in ev.items if e["mitigating"]]
    graph_high = [e for e in high if e["tool"] == "GraphInvestigationTool"]
    ml_level = prediction["risk_level"] if prediction else "MEDIUM"
    if graph_high and len(high) >= 3:
        rec, level = "REJECT", "CRITICAL" if ml_level in ("HIGH", "CRITICAL") else "HIGH"
    elif ml_level == "LOW" and graph_high:
        rec, level = "ESCALATE", "HIGH"
    elif high or ml_level in ("HIGH", "CRITICAL"):
        rec, level = "HOLD_FOR_REVIEW", ml_level if ml_level in ("HIGH", "CRITICAL") else "HIGH"
    elif med:
        rec, level = "HOLD_FOR_REVIEW", "MEDIUM"
    else:
        rec, level = "APPROVE", "LOW"
    findings = [{"statement": e["summary"], "evidence_keys": [e["key"]]} for e in (high + med)[:8]]
    if not findings:
        findings = [{"statement": e["summary"], "evidence_keys": [e["key"]]} for e in mitig[:4]]
    return {
        "risk_level": level,
        "summary": (f"Deterministic rule-based analysis: {len(high)} high-severity and {len(med)} medium-severity "
                    f"evidence items, {len(mitig)} mitigating. ML risk level {ml_level}."),
        "findings": findings,
        "recommendation": rec,
        "rationale": {
            "REJECT": "Multiple high-severity indicators including network (graph) evidence.",
            "ESCALATE": "ML score is low but graph intelligence shows high-severity links; signals conflict.",
            "HOLD_FOR_REVIEW": "Risk indicators present; a human reviewer should verify before capture.",
            "APPROVE": "No material risk indicators found.",
        }[rec],
    }


class _Recorder:
    def __init__(self, db: Session, inv: Investigation) -> None:
        self.db, self.inv = db, inv

    def run(self, name: str, tool: str, fn):
        started = utcnow()
        t0 = time.perf_counter()
        step = {"name": name, "tool": tool, "status": "RUNNING", "started_at": started.isoformat()}
        self._push(step)
        try:
            summary, update = fn()
            step.update(status="COMPLETED", summary=summary)
        except ToolError as exc:
            update = {}
            step.update(status="ERROR", summary=str(exc))
        step["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        self._push(step, replace=True)
        return update

    def _push(self, step: dict, replace: bool = False) -> None:
        steps = list(self.inv.steps or [])
        if replace and steps and steps[-1]["name"] == step["name"]:
            steps[-1] = dict(step)
        else:
            steps.append(dict(step))
        self.inv.steps = steps
        self.db.commit()
        ws_manager.broadcast("investigation.step", {"investigation_id": self.inv.id, "step": step,
                                                    "transaction_id": self.inv.transaction_id})


def build_workflow(db: Session, inv: Investigation):
    rec = _Recorder(db, inv)
    ev = EvidenceCollectionTool()
    s = get_settings()

    def retrieve_transaction(state: InvState) -> InvState:
        def go():
            out = transaction_history_tool(db, transaction_id=state["transaction_id"])
            t = out["transaction"]
            return out["summary"], {"outputs": {"transaction_history": out}, "customer_id": out["customer_id"],
                                    "merchant_id": t["merchant_id"], "device_id": t["device_id"],
                                    "destination_id": t["destination_id"]}
        return rec.run("Retrieve transaction", "TransactionHistoryTool", go)

    def customer_behaviour(state: InvState) -> InvState:
        def go():
            out = customer_behaviour_tool(db, state["customer_id"], state["transaction_id"])
            return out["summary"], {"outputs": {**state["outputs"], "customer_behaviour": out}}
        return rec.run("Analyse customer behaviour", "CustomerBehaviourTool", go)

    def ml_prediction(state: InvState) -> InvState:
        def go():
            if not db.execute(select(FraudPrediction.id).where(FraudPrediction.transaction_id == state["transaction_id"])).first():
                from ..services.risk import assess_transaction
                assess_transaction(db, db.get(Transaction, state["transaction_id"]))
                db.commit()
            out = fraud_prediction_tool(db, state["transaction_id"])
            return out["summary"], {"outputs": {**state["outputs"], "fraud_prediction": out}}
        return rec.run("Retrieve ML prediction + SHAP", "FraudPredictionTool", go)

    def graph_investigation(state: InvState) -> InvState:
        def go():
            out = graph_investigation_tool(db, state["customer_id"], state["transaction_id"])
            return out["summary"], {"outputs": {**state["outputs"], "graph": out}}
        return rec.run("Investigate graph connections", "GraphInvestigationTool", go)

    def merchant_risk(state: InvState) -> InvState:
        def go():
            if state.get("merchant_id"):
                out = merchant_risk_tool(db, state["merchant_id"])
                return out["summary"], {"outputs": {**state["outputs"], "merchant": out}}
            out = graph_investigation_tool(db, state["destination_id"])
            return "Peer-to-peer transfer; analysed destination instead. " + out["summary"], \
                {"outputs": {**state["outputs"], "destination": out}}
        return rec.run("Assess merchant / destination risk", "MerchantRiskTool", go)

    def collect_evidence(state: InvState) -> InvState:
        def go():
            o = state["outputs"]
            if "fraud_prediction" in o:
                ev.from_prediction(o["fraud_prediction"])
            if "customer_behaviour" in o:
                ev.from_behaviour(o["customer_behaviour"])
            if "graph" in o:
                ev.from_graph(o["graph"])
            if "merchant" in o:
                ev.from_merchant(o["merchant"])
            if "destination" in o:
                ev.from_graph(o["destination"])
            hi = sum(1 for e in ev.items if e["severity"] == "HIGH" and not e["mitigating"])
            return f"Collected {len(ev.items)} evidence items ({hi} high severity).", {}
        return rec.run("Collect evidence", "EvidenceCollectionTool", go)

    def analyse(state: InvState) -> InvState:
        prediction = state["outputs"].get("fraud_prediction")
        if s.groq_configured:
            def go_llm():
                draft, note = _llm_analyse(db, state, ev, s)
                return f"Groq {s.groq_model} produced a draft report ({len(draft.get('findings') or [])} findings). {note}", \
                    {"draft": draft, "mode": "LLM_AGENT"}
            try:
                return rec.run("AI analysis (LLM tool-calling)", f"Groq:{s.groq_model}", go_llm)
            except Exception as exc:  # network/API/format failure -> labelled fallback
                log.warning("Groq analysis failed: %s", exc)
                note = f"Groq call failed ({type(exc).__name__}: {str(exc)[:160]}); deterministic fallback used."
                steps = list(inv.steps)
                steps[-1] = {**steps[-1], "status": "ERROR", "summary": note}
                inv.steps = steps
                db.commit()
                return rec.run("Deterministic analysis (fallback)", "RuleEngine",
                               lambda: ("Rule-based analysis (not LLM-generated).",
                                        {"draft": deterministic_draft(ev, prediction), "mode": "DETERMINISTIC_FALLBACK",
                                         "llm_note": note}))
        return rec.run("Deterministic analysis (Groq not configured)", "RuleEngine",
                       lambda: ("Rule-based analysis (not LLM-generated): GROQ_API_KEY not set.",
                                {"draft": deterministic_draft(ev, prediction), "mode": "DETERMINISTIC_FALLBACK"}))

    def generate_report(state: InvState) -> InvState:
        def go():
            try:
                report = investigation_report_tool(state["draft"], ev, state["mode"], state["transaction_id"])
            except ToolError:
                # LLM draft had no evidence-backed findings: fall back rather than publish unsupported claims
                report = investigation_report_tool(deterministic_draft(ev, state["outputs"].get("fraud_prediction")), ev,
                                                   "DETERMINISTIC_FALLBACK", state["transaction_id"])
                report["fallback_reason"] = "LLM draft contained no evidence-backed findings"
            if state.get("llm_note"):
                report["fallback_reason"] = state["llm_note"]
            report["evidence"] = [{k: v for k, v in e.items() if k != "data"} for e in ev.items]
            for e in ev.items:
                db.add(InvestigationEvidence(investigation_id=inv.id, evidence_key=e["key"], tool_name=e["tool"],
                                             category=e["category"], severity=e["severity"], summary=e["summary"],
                                             data={**e["data"], "mitigating": e["mitigating"]}))
            inv.report = report
            inv.mode = report["mode"]
            inv.recommendation = report["recommendation"]
            inv.risk_level = report["risk_level"]
            db.commit()
            return (f"Report generated: {report['recommendation']} ({len(report['findings'])} evidence-backed findings"
                    f"{', ' + str(len(report['rejected_findings'])) + ' rejected' if report['rejected_findings'] else ''})."), \
                {"report": report}
        return rec.run("Generate investigation report", "InvestigationReportTool", go)

    def route_to_reviewer(state: InvState) -> InvState:
        def go():
            txn = db.get(Transaction, state["transaction_id"])
            r = state["report"]
            msg = f"Recommendation {r['recommendation']} sent to reviewer queue."
            if txn.status in ("CLEARED", "COMPLETED") and r["recommendation"] != "APPROVE":
                txn.status = "HELD_FOR_REVIEW"
                txn.review_status = "PENDING_REVIEW"
                msg += " Transaction referred for retrospective human review."
            elif txn.status in ("CAPTURED", "APPROVED", "REJECTED"):
                msg = f"Recommendation {r['recommendation']} recorded; transaction already {txn.status}."
            audit.record(db, "INVESTIGATION_COMPLETED", "investigation", inv.id, {
                "transaction_id": txn.id, "recommendation": r["recommendation"], "mode": r["mode"],
                "findings": len(r["findings"]), "evidence_items": r["evidence_count"]}, actor_label="sentinel-agent")
            db.commit()
            return msg, {}
        return rec.run("Route to human reviewer", "ReviewQueue", go)

    g = StateGraph(InvState)
    nodes = [("retrieve_transaction", retrieve_transaction), ("customer_behaviour", customer_behaviour),
             ("ml_prediction", ml_prediction), ("graph_investigation", graph_investigation),
             ("merchant_risk", merchant_risk), ("collect_evidence", collect_evidence), ("analyse", analyse),
             ("generate_report", generate_report), ("route_to_reviewer", route_to_reviewer)]
    for name, fn in nodes:
        g.add_node(name, fn)
    g.set_entry_point(nodes[0][0])
    for (a, _), (b, _) in zip(nodes, nodes[1:]):
        g.add_edge(a, b)
    g.add_edge(nodes[-1][0], END)
    return g.compile()


def _llm_analyse(db: Session, state: InvState, ev: EvidenceCollectionTool, s) -> tuple[dict, str]:
    from groq import Groq

    client = Groq(api_key=s.groq_api_key, timeout=30.0)
    th = state["outputs"]["transaction_history"]["transaction"]
    case = {
        "transaction": {k: th.get(k) for k in ("id", "amount", "customer_name", "customer_city", "merchant_name",
                                               "merchant_id", "destination_id", "destination_label", "device_id",
                                               "created_at", "channel", "description")},
        "customer_id": state["customer_id"],
        "evidence": [{k: e[k] for k in ("key", "tool", "category", "severity", "summary", "mitigating")} for e in ev.items],
    }
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Investigate this transaction. Case file (from tool outputs):\n" + json.dumps(case, default=str)},
    ]
    extra_calls = 0
    for _ in range(6):
        resp = client.chat.completions.create(model=s.groq_model, messages=messages, tools=LLM_TOOLS,
                                              tool_choice="auto", temperature=0.1, max_tokens=1500)
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": c.id, "type": "function",
                                         "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]}
                        if calls else {"role": "assistant", "content": msg.content or ""})
        if not calls:
            messages.append({"role": "user", "content": "Call submit_investigation_report now."})
            continue
        for c in calls:
            args = json.loads(c.function.arguments or "{}")
            if c.function.name == "submit_investigation_report":
                return args, f"{extra_calls} additional tool call(s) made by the agent."
            before = len(ev.items)
            try:
                if c.function.name == "transaction_history":
                    out = transaction_history_tool(db, customer_id=args["customer_id"], limit=10)
                elif c.function.name == "customer_behaviour":
                    out = customer_behaviour_tool(db, args["customer_id"])
                elif c.function.name == "graph_investigation":
                    out = graph_investigation_tool(db, args["entity_id"])
                    ev.from_graph(out)
                elif c.function.name == "merchant_risk":
                    out = merchant_risk_tool(db, args["merchant_id"])
                    ev.from_merchant(out)
                else:
                    raise ToolError(f"Unknown tool {c.function.name}")
                extra_calls += 1
                new_items = ev.items[before:]
                if not new_items:  # make raw tool facts citable
                    ev._add(out.get("tool", c.function.name), "TOOL_RESULT", "INFO", out["summary"])
                    new_items = ev.items[before:]
                content = {"summary": out["summary"],
                           "new_evidence": [{k: e[k] for k in ("key", "severity", "summary")} for e in new_items]}
            except (ToolError, KeyError) as exc:
                content = {"error": str(exc)}
            messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(content, default=str)[:6000]})
    raise RuntimeError("LLM did not submit a report within the step budget")


def run_investigation(inv_id: str) -> None:
    db = SessionLocal()
    try:
        inv = db.get(Investigation, inv_id)
        wf = build_workflow(db, inv)
        wf.invoke({"transaction_id": inv.transaction_id, "outputs": {}, "mode": "DETERMINISTIC_FALLBACK"})
        inv.status = "COMPLETED"
        inv.completed_at = utcnow()
        db.commit()
        ws_manager.broadcast("investigation.completed", {"investigation_id": inv.id, "transaction_id": inv.transaction_id,
                                                         "recommendation": inv.recommendation})
    except Exception as exc:
        log.exception("Investigation %s failed", inv_id)
        db.rollback()
        inv = db.get(Investigation, inv_id)
        if inv:
            inv.status = "FAILED"
            inv.error = f"{type(exc).__name__}: {exc}"[:2000]
            inv.completed_at = utcnow()
            db.commit()
            ws_manager.broadcast("investigation.completed", {"investigation_id": inv.id, "status": "FAILED"})
    finally:
        db.close()


def launch_investigation(transaction_id: str, user_id: int | None, background: bool = True) -> str:
    db = SessionLocal()
    try:
        running = db.execute(select(Investigation).where(Investigation.transaction_id == transaction_id,
                                                         Investigation.status == "RUNNING")).scalar()
        if running:
            return running.id
        s = get_settings()
        inv = Investigation(id=new_id("INV"), transaction_id=transaction_id, status="RUNNING",
                            mode="LLM_AGENT" if s.groq_configured else "DETERMINISTIC_FALLBACK",
                            llm_model=s.groq_model if s.groq_configured else None, steps=[], started_by_id=user_id)
        db.add(inv)
        audit.record(db, "INVESTIGATION_STARTED", "investigation", inv.id, {"transaction_id": transaction_id},
                     actor_label=f"user:{user_id}" if user_id else "sentinel-policy-engine")
        db.commit()
        inv_id = inv.id
    finally:
        db.close()
    if background:
        threading.Thread(target=run_investigation, args=(inv_id,), daemon=True, name=f"inv-{inv_id}").start()
    else:
        run_investigation(inv_id)
    return inv_id
