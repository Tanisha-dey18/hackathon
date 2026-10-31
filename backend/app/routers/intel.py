"""Investigations and graph intelligence endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.workflow import launch_investigation
from ..db import get_db
from ..graph.engine import get_engine
from ..ml.features import aware
from ..models import Investigation, Transaction, User
from ..security import require_staff

router = APIRouter()


class InvestigateIn(BaseModel):
    transaction_id: str = Field(pattern=r"^TXN_\w+$")


def inv_view(i: Investigation) -> dict:
    return {
        "id": i.id, "transaction_id": i.transaction_id, "status": i.status, "mode": i.mode, "llm_model": i.llm_model,
        "steps": i.steps, "report": i.report, "recommendation": i.recommendation, "risk_level": i.risk_level,
        "error": i.error, "created_at": aware(i.created_at),
        "completed_at": aware(i.completed_at) if i.completed_at else None,
        "evidence": [{"key": e.evidence_key, "tool": e.tool_name, "category": e.category, "severity": e.severity,
                      "summary": e.summary, "data": e.data} for e in i.evidence],
    }


@router.post("/api/investigations/start", tags=["investigations"],
             summary="Start the LangGraph investigation agent for a transaction (runs asynchronously)")
def start(body: InvestigateIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    if not db.get(Transaction, body.transaction_id):
        raise HTTPException(404, "Transaction not found")
    return {"investigation_id": launch_investigation(body.transaction_id, user.id)}


@router.get("/api/investigations", tags=["investigations"])
def list_investigations(db: Session = Depends(get_db), _: User = Depends(require_staff),
                        limit: int = Query(100, le=500)):
    rows = db.execute(select(Investigation).order_by(Investigation.created_at.desc()).limit(limit)).scalars()
    return [{"id": i.id, "transaction_id": i.transaction_id, "status": i.status, "mode": i.mode,
             "recommendation": i.recommendation, "risk_level": i.risk_level, "created_at": aware(i.created_at),
             "findings": len((i.report or {}).get("findings", []))} for i in rows]


@router.get("/api/investigations/{inv_id}", tags=["investigations"])
def get_investigation(inv_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    i = db.get(Investigation, inv_id)
    if not i:
        raise HTTPException(404, "Investigation not found")
    db.refresh(i)
    return inv_view(i)


# ------------------------------------------------------------------------------- graph
@router.get("/api/graph/overview", tags=["graph"], summary="Suspicious clusters, rings and flagged destinations")
def graph_overview(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    eng = get_engine(db)
    return {"summary": eng.summary(), "clusters": [c for c in eng.clusters if c["suspicious"]],
            "shared_devices": eng.shared_devices, "cycles": eng.cycles,
            "flagged_destinations": eng.flagged_destinations, "graph": eng.overview()}


@router.get("/api/graph/entity/{entity_id}", tags=["graph"])
def graph_entity(entity_id: str, hops: int = Query(2, ge=1, le=3), db: Session = Depends(get_db),
                 _: User = Depends(require_staff)):
    view = get_engine(db).entity_view(entity_id, hops=hops)
    if view is None:
        raise HTTPException(404, "Entity not found in graph")
    return view


@router.get("/api/graph/transaction/{txn_id}", tags=["graph"])
def graph_transaction(txn_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    view = get_engine(db).transaction_view(txn_id)
    if view is None:
        raise HTTPException(404, "Transaction not found in graph")
    return view
