"""Hash-chained audit logging. Every row's hash covers its content and the previous row's hash,
so any modification or deletion of historical rows is detectable by `verify_chain`."""
import hashlib
import json
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog, User, utcnow

GENESIS = "0" * 64
_lock = threading.Lock()


def _digest(prev_hash: str, actor: str, action: str, entity_type: str, entity_id: str, details: dict, ts: str) -> str:
    body = json.dumps(
        {"prev": prev_hash, "actor": actor, "action": action, "type": entity_type,
         "id": entity_id, "details": details, "ts": ts},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def record(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
    actor: User | None = None,
    actor_label: str | None = None,
) -> AuditLog:
    """Append an audit row to the current DB transaction (caller commits)."""
    details = json.loads(json.dumps(details or {}, default=str))
    label = actor_label or (f"{actor.email} ({actor.role})" if actor else "system")
    with _lock:
        last = db.execute(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)).scalar()
        # include pending (unflushed) rows from this session
        pending = [o for o in db.new if isinstance(o, AuditLog)]
        prev = pending[-1].hash if pending else (last or GENESIS)
        ts = utcnow()
        row = AuditLog(
            actor_id=actor.id if actor else None,
            actor_label=label,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details,
            prev_hash=prev,
            created_at=ts,
        )
        row.hash = _digest(prev, label, action, entity_type, str(entity_id), details, ts.isoformat())
        db.add(row)
        db.flush()
    return row


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    # populate_existing: always verify what is stored, never cached in-session objects
    for row in db.execute(select(AuditLog).order_by(AuditLog.id).execution_options(populate_existing=True)).scalars():
        ts = row.created_at
        if ts.tzinfo is None:  # SQLite drops tzinfo
            from datetime import timezone
            ts = ts.replace(tzinfo=timezone.utc)
        expected = _digest(prev, row.actor_label, row.action, row.entity_type, row.entity_id, row.details, ts.isoformat())
        if row.prev_hash != prev or row.hash != expected:
            return {"valid": False, "checked": count, "broken_at_id": row.id}
        prev = row.hash
        count += 1
    return {"valid": True, "checked": count, "broken_at_id": None}
