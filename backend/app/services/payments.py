"""SENTINEL payment gateway: PayPal order lifecycle gated by the risk engine.

Invariants
- PayPal status fields are only ever written from real PayPal API/webhook responses.
- Sentinel risk/decision status is tracked separately (`sentinel_status`).
- A capture is attempted at most once per order (DB compare-and-set + PayPal-Request-Id).
- Capture requires either a LOW risk assessment (auto policy) or an APPROVE reviewer decision.
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import audit
from ..infra import ws_manager
from ..models import (
    Customer,
    FraudPrediction,
    PaymentDestination,
    PaymentEvent,
    PayPalOrder,
    Product,
    ReviewerDecision,
    Transaction,
    User,
)
from ..paypal.client import PayPalError, PayPalNotConfigured, get_paypal
from .transactions import assess_and_route, create_transaction, resolve_device, should_auto_investigate

log = logging.getLogger("sentinel.payments")


def _money(v) -> str:
    return str(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _event(db: Session, order_id: str | None, source: str, event_type: str, payload: dict,
           http_status: int | None = None, debug_id: str | None = None, webhook_event_id: str | None = None,
           verified: bool | None = None) -> PaymentEvent:
    ev = PaymentEvent(paypal_order_id=order_id, source=source, event_type=event_type, payload=payload,
                      http_status=http_status, paypal_debug_id=debug_id, webhook_event_id=webhook_event_id,
                      signature_verified=verified)
    db.add(ev)
    db.flush()
    return ev


def _paypal_or_503():
    pp = get_paypal()
    if not pp.configured:
        raise HTTPException(503, "PayPal Sandbox is not configured on the server (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET).")
    return pp


def _paypal_http_error(db: Session, order_id: str | None, op: str, exc: PayPalError) -> HTTPException:
    _event(db, order_id, "PAYPAL_API", f"{op}.ERROR", exc.body if isinstance(exc.body, dict) else {"body": exc.body},
           http_status=exc.status, debug_id=exc.debug_id)
    db.commit()
    return HTTPException(502, {"message": f"PayPal {op} failed", "paypal_status": exc.status,
                               "issue": exc.issue, "debug_id": exc.debug_id})


def order_view(o: PayPalOrder) -> dict:
    t = o.transaction
    return {
        "paypal_order_id": o.paypal_order_id,
        "transaction_id": o.transaction_id,
        "amount": float(o.amount),
        "currency": o.currency,
        "items": o.items,
        "paypal_status": o.paypal_status,
        "sentinel_status": o.sentinel_status,
        "capture_state": o.capture_state,
        "capture_id": o.capture_id,
        "capture_status": o.capture_status,
        "payer_email": o.payer_email,
        "risk_level": t.risk_level if t else None,
        "transaction_status": t.status if t else None,
        "review_status": t.review_status if t else None,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


# ----------------------------------------------------------------------------- create
def create_order(db: Session, user: User, items: list[dict], device_fingerprint: str, idempotency_key: str,
                 geo: dict | None = None) -> dict:
    if user.role != "CUSTOMER" or not user.customer_id:
        raise HTTPException(403, "Only shopper accounts can create checkout orders")
    existing = db.execute(select(PayPalOrder).where(PayPalOrder.create_idempotency_key == idempotency_key)).scalar()
    if existing:
        if existing.user_id != user.id:
            raise HTTPException(409, "Idempotency key already used")
        return {**order_view(existing), "idempotent_replay": True}

    pp = _paypal_or_503()
    if not items:
        raise HTTPException(422, "Cart is empty")
    products = {p.id: p for p in db.execute(select(Product).where(Product.id.in_([i["product_id"] for i in items]))).scalars()}
    lines, total = [], Decimal("0")
    merchants = set()
    for i in items:
        p = products.get(i["product_id"])
        if not p:
            raise HTTPException(422, f"Unknown product {i['product_id']}")
        qty = int(i["quantity"])
        if not 1 <= qty <= 10:
            raise HTTPException(422, "Quantity must be between 1 and 10")
        price = Decimal(str(p.price))  # server-side price; client prices are never trusted
        total += price * qty
        merchants.add(p.merchant_id)
        lines.append({"product_id": p.id, "name": p.name, "quantity": qty, "unit_price": float(price)})
    if len(merchants) != 1:
        raise HTTPException(422, "A checkout can only contain items from a single seller")
    merchant = products[items[0]["product_id"]].merchant
    customer = db.get(Customer, user.customer_id)
    device = resolve_device(db, device_fingerprint)
    lat = lon = None
    if geo:
        lat, lon = float(geo["lat"]), float(geo["lon"])

    dest = db.get(PaymentDestination, merchant.payout_destination_id)
    txn = create_transaction(
        db, customer=customer, amount=float(total), device=device, merchant=merchant, destination=dest,
        channel="PAYPAL_CHECKOUT", lat=lat, lon=lon, status="AWAITING_APPROVAL",
        description=", ".join(f"{l['quantity']}x {l['name']}" for l in lines)[:255], actor=user,
    )
    pp_items = [{
        "name": l["name"][:127], "quantity": str(l["quantity"]), "sku": l["product_id"], "category": "PHYSICAL_GOODS",
        "unit_amount": {"currency_code": "USD", "value": _money(l["unit_price"])},
    } for l in lines]
    try:
        body, resp = pp.create_order(reference_id=txn.id, amount=_money(total), currency="USD", items=pp_items,
                                     request_id=f"create-{idempotency_key}", description=f"SENTINEL MERCHANT order {txn.id}")
    except PayPalError as exc:
        txn.status = "FAILED"
        raise _paypal_http_error(db, None, "create_order", exc)
    except PayPalNotConfigured as exc:
        raise HTTPException(503, str(exc))

    order = PayPalOrder(
        paypal_order_id=body["id"], transaction_id=txn.id, user_id=user.id, amount=float(total), currency="USD",
        items=lines, create_idempotency_key=idempotency_key, paypal_status=body.get("status", "UNKNOWN"),
        sentinel_status="AWAITING_BUYER_APPROVAL", last_paypal_response=body,
    )
    db.add(order)
    _event(db, body["id"], "PAYPAL_API", "ORDER.CREATED", body, http_status=resp.status_code,
           debug_id=resp.headers.get("paypal-debug-id"))
    audit.record(db, "PAYPAL_ORDER_CREATED", "paypal_order", body["id"],
                 {"transaction_id": txn.id, "amount": _money(total), "paypal_status": order.paypal_status}, actor=user)
    db.commit()
    ws_manager.broadcast("payment.updated", {"paypal_order_id": order.paypal_order_id, "paypal_status": order.paypal_status,
                                             "transaction_id": txn.id})
    return order_view(order)


# ----------------------------------------------------------------------------- approve -> assess -> branch
def process_approved_order(db: Session, user: User, paypal_order_id: str) -> dict:
    """Called after the buyer approves in PayPal. Verifies the order with PayPal, runs Sentinel,
    and captures only when policy allows. Safe to call repeatedly."""
    order = db.execute(select(PayPalOrder).where(PayPalOrder.paypal_order_id == paypal_order_id)).scalar()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.user_id != user.id and user.role not in ("ADMIN",):
        raise HTTPException(403, "This order does not belong to you")
    if order.capture_state in ("DONE", "IN_PROGRESS") or order.sentinel_status not in ("AWAITING_BUYER_APPROVAL",):
        return {**order_view(order), "idempotent_replay": True, "message": _status_message(order)}

    pp = _paypal_or_503()
    try:
        body, resp = pp.get_order(paypal_order_id)
    except PayPalError as exc:
        raise _paypal_http_error(db, paypal_order_id, "get_order", exc)
    _event(db, paypal_order_id, "PAYPAL_API", "ORDER.RETRIEVED", body, http_status=resp.status_code,
           debug_id=resp.headers.get("paypal-debug-id"))
    order.paypal_status = body.get("status", order.paypal_status)
    order.last_paypal_response = body
    payer = body.get("payer") or {}
    order.payer_email = payer.get("email_address")
    order.payer_id = payer.get("payer_id")

    # Validate order state and amount against what we created
    pu = (body.get("purchase_units") or [{}])[0]
    amt = (pu.get("amount") or {})
    if amt.get("value") != _money(order.amount) or amt.get("currency_code") != order.currency:
        order.sentinel_status = "INTEGRITY_FAILED"
        audit.record(db, "PAYPAL_ORDER_MISMATCH", "paypal_order", paypal_order_id,
                     {"expected": _money(order.amount), "paypal": amt}, actor=user)
        db.commit()
        raise HTTPException(409, "PayPal order amount does not match the Sentinel record")
    if pu.get("reference_id") not in (None, order.transaction_id):
        raise HTTPException(409, "PayPal order reference does not match this transaction")
    if order.paypal_status == "COMPLETED":
        _reconcile_capture(order, body)
        db.commit()
        return {**order_view(order), "message": "Order already captured at PayPal"}
    if order.paypal_status != "APPROVED":
        db.commit()
        raise HTTPException(409, f"PayPal order is {order.paypal_status}, buyer approval is required before capture")

    txn = order.transaction
    txn.status = "ASSESSING"
    fp, action = assess_and_route(db, txn, actor=user)
    investigate = should_auto_investigate(db, txn, fp)
    if fp.risk_level == "LOW":
        order.sentinel_status = "CLEARED"
        db.commit()
        result = execute_capture(db, order, authorized_by="AUTO_POLICY")
    else:
        order.sentinel_status = "HELD_FOR_VERIFICATION" if fp.risk_level == "MEDIUM" else "HELD_FOR_REVIEW"
        audit.record(db, "PAYMENT_HELD", "paypal_order", paypal_order_id,
                     {"risk_level": fp.risk_level, "reason": "Risk policy requires human review before capture",
                      "paypal_status": order.paypal_status}, actor_label="sentinel-policy-engine")
        db.commit()
        result = order_view(order)
    if investigate:
        from ..agent.workflow import launch_investigation
        result["investigation_id"] = launch_investigation(txn.id, None)
    result["risk"] = {"risk_level": fp.risk_level, "fraud_probability": fp.fraud_probability,
                      "recommended_action": fp.recommended_action}
    result["message"] = _status_message(order)
    ws_manager.broadcast("payment.updated", {"paypal_order_id": paypal_order_id, "paypal_status": order.paypal_status,
                                             "sentinel_status": order.sentinel_status, "transaction_id": txn.id})
    return result


def _status_message(o: PayPalOrder) -> str:
    if o.capture_status == "COMPLETED":
        return "Payment captured by PayPal."
    if o.capture_status:
        return f"PayPal capture status: {o.capture_status}."
    return {
        "HELD_FOR_REVIEW": "Payment approved by buyer but held by Sentinel for human review. Funds have NOT been captured.",
        "HELD_FOR_VERIFICATION": "Payment approved by buyer and awaiting additional verification. Funds have NOT been captured.",
        "ESCALATED": "Payment escalated to a senior reviewer. Funds have NOT been captured.",
        "REJECTED": "Payment rejected by Sentinel review. Funds were not captured.",
        "AWAITING_BUYER_APPROVAL": "Waiting for buyer approval in PayPal.",
    }.get(o.sentinel_status, o.sentinel_status)


# ----------------------------------------------------------------------------- capture
def _capture_authorized(db: Session, order: PayPalOrder, authorized_by: str) -> None:
    latest = db.execute(select(FraudPrediction).where(FraudPrediction.transaction_id == order.transaction_id)
                        .order_by(FraudPrediction.id.desc())).scalar()
    if not latest:
        raise HTTPException(409, "Cannot capture: transaction has not been risk-assessed")
    if authorized_by == "AUTO_POLICY":
        if latest.risk_level != "LOW":
            raise HTTPException(409, f"Policy violation: {latest.risk_level} risk payments require reviewer approval")
        return
    if authorized_by == "REVIEWER":
        d = db.execute(select(ReviewerDecision).where(ReviewerDecision.transaction_id == order.transaction_id)
                       .order_by(ReviewerDecision.id.desc())).scalar()
        if not d or d.decision != "APPROVE":
            raise HTTPException(409, "Policy violation: no reviewer approval recorded for this payment")
        return
    raise HTTPException(409, "Unknown capture authorization")


def _reconcile_capture(order: PayPalOrder, body: dict) -> None:
    caps = (((body.get("purchase_units") or [{}])[0].get("payments") or {}).get("captures") or [])
    order.paypal_status = body.get("status", order.paypal_status)
    if caps:
        order.capture_id = caps[0].get("id")
        order.capture_status = caps[0].get("status")
        order.capture_state = "DONE"
        if order.transaction:
            order.transaction.status = "CAPTURED" if order.capture_status == "COMPLETED" else order.transaction.status


def execute_capture(db: Session, order: PayPalOrder, authorized_by: str, actor: User | None = None) -> dict:
    _capture_authorized(db, order, authorized_by)
    # Compare-and-set lock: only one request can move NONE/FAILED -> IN_PROGRESS.
    res = db.execute(
        update(PayPalOrder)
        .where(PayPalOrder.id == order.id, PayPalOrder.capture_state.in_(("NONE", "FAILED")))
        .values(capture_state="IN_PROGRESS")
    )
    db.commit()
    if res.rowcount != 1:
        db.refresh(order)
        return {**order_view(order), "idempotent_replay": True, "message": "Capture already performed or in progress"}
    db.refresh(order)
    pp = _paypal_or_503()
    request_id = f"capture-{order.paypal_order_id}"  # stable: PayPal dedupes retries of the same capture
    try:
        body, resp = pp.capture_order(order.paypal_order_id, request_id=request_id)
    except PayPalError as exc:
        if exc.issue == "ORDER_ALREADY_CAPTURED":
            body, resp = pp.get_order(order.paypal_order_id)
            _reconcile_capture(order, body)
            _event(db, order.paypal_order_id, "PAYPAL_API", "ORDER.ALREADY_CAPTURED", body, http_status=resp.status_code)
            db.commit()
            return {**order_view(order), "message": "Order was already captured at PayPal; state reconciled"}
        order.capture_state = "FAILED"
        order.sentinel_status = "CAPTURE_FAILED"
        order.transaction.status = "CAPTURE_FAILED"
        audit.record(db, "PAYPAL_CAPTURE_FAILED", "paypal_order", order.paypal_order_id,
                     {"status": exc.status, "issue": exc.issue, "debug_id": exc.debug_id}, actor=actor,
                     actor_label=None if actor else "sentinel-gateway")
        raise _paypal_http_error(db, order.paypal_order_id, "capture", exc)

    _event(db, order.paypal_order_id, "PAYPAL_API", "ORDER.CAPTURED", body, http_status=resp.status_code,
           debug_id=resp.headers.get("paypal-debug-id"))
    order.last_paypal_response = body
    _reconcile_capture(order, body)
    order.sentinel_status = "APPROVED_AUTO" if authorized_by == "AUTO_POLICY" else "APPROVED_BY_REVIEWER"
    if order.capture_status != "COMPLETED":
        order.transaction.status = "APPROVED"  # captured but pending at PayPal - do not claim completion
    audit.record(db, "PAYPAL_CAPTURE", "paypal_order", order.paypal_order_id, {
        "capture_id": order.capture_id, "capture_status": order.capture_status, "paypal_status": order.paypal_status,
        "authorized_by": authorized_by, "debug_id": resp.headers.get("paypal-debug-id"),
    }, actor=actor, actor_label=None if actor else "sentinel-gateway")
    db.commit()
    ws_manager.broadcast("payment.updated", {"paypal_order_id": order.paypal_order_id, "paypal_status": order.paypal_status,
                                             "capture_status": order.capture_status, "transaction_id": order.transaction_id})
    return {**order_view(order), "message": _status_message(order)}


def refresh_order(db: Session, order: PayPalOrder) -> dict:
    pp = _paypal_or_503()
    try:
        body, resp = pp.get_order(order.paypal_order_id)
    except PayPalError as exc:
        raise _paypal_http_error(db, order.paypal_order_id, "get_order", exc)
    _event(db, order.paypal_order_id, "PAYPAL_API", "ORDER.RETRIEVED", body, http_status=resp.status_code)
    order.last_paypal_response = body
    if body.get("status") == "COMPLETED":
        _reconcile_capture(order, body)
    else:
        order.paypal_status = body.get("status", order.paypal_status)
    db.commit()
    return {**order_view(order), "paypal_response": body}


# ----------------------------------------------------------------------------- webhooks
HANDLED_EVENTS = {"CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.DENIED",
                  "PAYMENT.CAPTURE.PENDING", "PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"}


def handle_webhook(db: Session, headers: dict, event: dict) -> dict:
    pp = get_paypal()
    try:
        verified = pp.verify_webhook(headers, event)
    except PayPalNotConfigured as exc:
        raise HTTPException(503, str(exc))
    except PayPalError as exc:
        raise HTTPException(502, f"Webhook verification call failed: {exc.issue}")
    event_id = event.get("id")
    etype = event.get("event_type", "UNKNOWN")
    if not verified:
        audit.record(db, "WEBHOOK_REJECTED", "webhook", event_id or "unknown",
                     {"event_type": etype, "reason": "signature verification failed"}, actor_label="paypal-webhook")
        db.commit()
        raise HTTPException(400, "Webhook signature verification failed")
    if event_id and db.execute(select(PaymentEvent).where(PaymentEvent.webhook_event_id == event_id)).scalar():
        return {"status": "duplicate", "event_id": event_id}

    resource = event.get("resource") or {}
    order_id = None
    if etype.startswith("CHECKOUT.ORDER"):
        order_id = resource.get("id")
    else:
        order_id = ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")
    _event(db, order_id, "PAYPAL_WEBHOOK", etype, event, webhook_event_id=event_id, verified=True)
    order = db.execute(select(PayPalOrder).where(PayPalOrder.paypal_order_id == order_id)).scalar() if order_id else None
    if order and etype in HANDLED_EVENTS:
        if etype == "CHECKOUT.ORDER.APPROVED" and order.paypal_status == "CREATED":
            order.paypal_status = "APPROVED"
        elif etype.startswith("PAYMENT.CAPTURE."):
            order.capture_id = order.capture_id or resource.get("id")
            order.capture_status = resource.get("status") or etype.rsplit(".", 1)[-1]
            if etype == "PAYMENT.CAPTURE.COMPLETED":
                order.paypal_status = "COMPLETED"
                order.capture_state = "DONE"
                order.transaction.status = "CAPTURED"
            elif etype == "PAYMENT.CAPTURE.DENIED":
                order.transaction.status = "CAPTURE_FAILED"
    audit.record(db, "WEBHOOK_PROCESSED", "webhook", event_id or "unknown",
                 {"event_type": etype, "paypal_order_id": order_id, "matched_order": bool(order)}, actor_label="paypal-webhook")
    db.commit()
    if order:
        ws_manager.broadcast("payment.updated", {"paypal_order_id": order.paypal_order_id, "paypal_status": order.paypal_status,
                                                 "capture_status": order.capture_status, "transaction_id": order.transaction_id})
    return {"status": "processed", "event_id": event_id, "event_type": etype}
