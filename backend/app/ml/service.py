"""Train from the database and register model versions."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..models import ModelVersion, ReviewerDecision, Transaction, User
from .features import record_from_txn
from .train import build_dataset, clean, train_all


def _labels(db: Session, txns: list[Transaction]) -> list[int | None]:
    """Ground truth for synthetic history; reviewer decisions provide labels for live payments."""
    decisions = {}
    for d in db.execute(select(ReviewerDecision).order_by(ReviewerDecision.id)).scalars():
        if d.decision in ("APPROVE", "REJECT"):
            decisions[d.transaction_id] = 1 if d.decision == "REJECT" else 0
    return [int(t.is_fraud) if t.is_fraud is not None else decisions.get(t.id) for t in txns]


def train_from_db(db: Session, actor: User | None = None, notes: str | None = None) -> dict:
    from ..services.risk import reset_feature_state, static_context

    txns = list(db.execute(select(Transaction).order_by(Transaction.created_at)).scalars())
    records = [record_from_txn(t) for t in txns]
    X, y, ids, _ = build_dataset(records, _labels(db, txns), static_context(db))
    Xc, yc, report = clean(X, y, ids)
    existing = {v for (v,) in db.execute(select(ModelVersion.version)).all()}
    version = f"v{len(existing) + 1}"
    summary = train_all(Xc, yc, version, get_settings().model_dir, report)

    db.execute(update(ModelVersion).values(is_active=False, is_primary=False))
    for algo, metrics in summary["results"].items():
        db.add(ModelVersion(
            version=version, algorithm=algo, is_active=True, is_primary=(algo == summary["primary"]),
            metrics={k: v for k, v in metrics.items()} | (
                {"global_importance": summary["global_importance"]} if algo == summary["primary"] else {}),
            feature_names=list(Xc.columns), artifact_path=summary["artifact_path"],
            training_rows=summary["train_rows"], test_rows=summary["test_rows"],
            notes=notes or f"Primary selected by hold-out PR-AUC. Positive rate {summary['positive_rate']:.2%}.",
        ))
    audit.record(db, "MODEL_TRAINED", "model_version", version, {
        "primary": summary["primary"], "pr_auc": summary["results"][summary["primary"]]["pr_auc"],
        "train_rows": summary["train_rows"], "test_rows": summary["test_rows"],
    }, actor=actor)
    db.commit()
    reset_feature_state()
    summary["_X"] = X
    summary["_ids"] = ids
    return summary
