"""End-to-end payment lifecycle tests: create -> buyer approval -> Sentinel risk -> capture/hold -> review."""
import uuid

from app.db import SessionLocal
from app.models import AuditLog, PayPalOrder
from app.services.payments import execute_capture
from fastapi import HTTPException
from sqlalchemy import select

from .conftest import PASSWORD


def create_order(client, headers, items, fp, geo=None, key=None):
    return client.post("/api/paypal/create-order", headers={**headers, "Idempotency-Key": key or str(uuid.uuid4())},
                       json={"items": items, "device_fingerprint": fp, "geo": geo})


def test_create_order_uses_server_side_prices(client, ava, fake_paypal):
    r = create_order(client, ava, [{"product_id": "PRD_005", "quantity": 2}], "fp-ava-macbook-air")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["paypal_status"] == "CREATED"  # straight from the PayPal response
    assert body["sentinel_status"] == "AWAITING_BUYER_APPROVAL"
    assert body["amount"] == 96.0  # 2 x $48 from the catalogue, not from the client
    assert body["capture_status"] is None
    assert fake_paypal.orders[body["paypal_order_id"]]["purchase_units"][0]["amount"]["value"] == "96.00"


def test_create_order_idempotency_key_replays(client, ava, fake_paypal):
    key = str(uuid.uuid4())
    a = create_order(client, ava, [{"product_id": "PRD_011", "quantity": 1}], "fp-ava-macbook-air", key=key).json()
    n = len(fake_paypal.orders)
    b = create_order(client, ava, [{"product_id": "PRD_011", "quantity": 1}], "fp-ava-macbook-air", key=key).json()
    assert a["paypal_order_id"] == b["paypal_order_id"] and b["idempotent_replay"] is True
    assert len(fake_paypal.orders) == n


def test_cart_validation(client, ava):
    assert create_order(client, ava, [{"product_id": "PRD_999", "quantity": 1}], "fp-ava-macbook-air").status_code == 422
    mixed = [{"product_id": "PRD_001", "quantity": 1}, {"product_id": "PRD_005", "quantity": 1}]
    assert create_order(client, ava, mixed, "fp-ava-macbook-air").status_code == 422
    assert create_order(client, ava, [{"product_id": "PRD_005", "quantity": 99}], "fp-ava-macbook-air").status_code == 422


def test_staff_cannot_create_checkout(client, reviewer):
    assert create_order(client, reviewer, [{"product_id": "PRD_005", "quantity": 1}], "fp-x-12345678").status_code == 403


def test_capture_requires_buyer_approval(client, ava):
    o = create_order(client, ava, [{"product_id": "PRD_011", "quantity": 1}], "fp-ava-macbook-air").json()
    r = client.post("/api/paypal/capture-order", headers=ava, json={"order_id": o["paypal_order_id"]})
    assert r.status_code == 409 and "approval" in r.text


def test_low_risk_payment_is_captured_once(client, ava, fake_paypal):
    o = create_order(client, ava, [{"product_id": "PRD_005", "quantity": 1}, {"product_id": "PRD_006", "quantity": 1}],
                     "fp-ava-macbook-air").json()
    oid = o["paypal_order_id"]
    fake_paypal.approve(oid)
    r = client.post("/api/paypal/capture-order", headers=ava, json={"order_id": oid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["risk"]["risk_level"] == "LOW"
    assert body["paypal_status"] == "COMPLETED" and body["capture_status"] == "COMPLETED"
    assert body["capture_id"].startswith("CAP")
    assert body["sentinel_status"] == "APPROVED_AUTO"
    # Duplicate capture prevention: retrying never calls PayPal capture again
    calls = fake_paypal.capture_calls.count(oid)
    again = client.post("/api/paypal/capture-order", headers=ava, json={"order_id": oid})
    assert again.status_code == 200 and again.json()["idempotent_replay"] is True
    assert fake_paypal.capture_calls.count(oid) == calls == 1
    with SessionLocal() as db:
        order = db.execute(select(PayPalOrder).where(PayPalOrder.paypal_order_id == oid)).scalar()
        assert execute_capture(db, order, "AUTO_POLICY")["idempotent_replay"] is True
    assert fake_paypal.capture_calls.count(oid) == 1


def test_payment_ownership_enforced(client, ava, ben, fake_paypal):
    o = create_order(client, ava, [{"product_id": "PRD_011", "quantity": 1}], "fp-ava-macbook-air").json()
    fake_paypal.approve(o["paypal_order_id"])
    r = client.post("/api/paypal/capture-order", headers=ben, json={"order_id": o["paypal_order_id"]})
    assert r.status_code == 403
    assert client.get(f"/api/paypal/order/{o['paypal_order_id']}", headers=ben).status_code == 403


def test_amount_mismatch_blocks_capture(client, ava, fake_paypal):
    o = create_order(client, ava, [{"product_id": "PRD_011", "quantity": 1}], "fp-ava-macbook-air").json()
    fake_paypal.approve(o["paypal_order_id"])
    fake_paypal.amount_override = "1.00"
    try:
        r = client.post("/api/paypal/capture-order", headers=ava, json={"order_id": o["paypal_order_id"]})
    finally:
        fake_paypal.amount_override = None
    assert r.status_code == 409
    assert o["paypal_order_id"] not in fake_paypal.capture_calls


def test_high_risk_payment_cannot_bypass_review(client, cara, reviewer, fake_paypal):
    o = create_order(client, cara, [{"product_id": "PRD_013", "quantity": 1}], "fp-ring-emulator-01",
                     geo={"lat": 25.79, "lon": -80.22}).json()
    oid = o["paypal_order_id"]
    fake_paypal.approve(oid)
    r = client.post("/api/paypal/capture-order", headers=cara, json={"order_id": oid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["risk"]["risk_level"] in ("HIGH", "CRITICAL")
    assert body["sentinel_status"] == "HELD_FOR_REVIEW"
    assert body["capture_status"] is None and body["paypal_status"] == "APPROVED"  # approved, NOT captured
    assert body.get("investigation_id")
    assert oid not in fake_paypal.capture_calls
    # Retrying from the client never captures
    client.post("/api/paypal/capture-order", headers=cara, json={"order_id": oid})
    assert oid not in fake_paypal.capture_calls
    # Policy-level guard: auto capture is refused for non-LOW risk, even if called directly
    with SessionLocal() as db:
        order = db.execute(select(PayPalOrder).where(PayPalOrder.paypal_order_id == oid)).scalar()
        for auth in ("AUTO_POLICY", "REVIEWER"):
            try:
                execute_capture(db, order, auth)
                raise AssertionError("capture should have been refused")
            except HTTPException as exc:
                assert exc.status_code == 409
    assert oid not in fake_paypal.capture_calls


def test_reviewer_decision_controls(client, cara, reviewer, admin, fake_paypal):
    o = create_order(client, cara, [{"product_id": "PRD_014", "quantity": 1}], "fp-ring-emulator-01").json()
    oid, txn = o["paypal_order_id"], o["transaction_id"]
    fake_paypal.approve(oid)
    client.post("/api/paypal/capture-order", headers=cara, json={"order_id": oid})
    url = f"/api/reviews/{txn}/decision"
    good = {"decision": "APPROVE", "reason": "Verified with customer by phone; device shared with spouse.",
            "password": PASSWORD, "confirm_transaction_id": txn}
    assert client.post(url, headers=cara, json=good).status_code == 403  # shoppers cannot review
    assert client.post(url, headers=reviewer, json={**good, "password": "wrong"}).status_code == 401
    assert client.post(url, headers=reviewer, json={**good, "confirm_transaction_id": "TXN_OTHER"}).status_code == 422
    assert client.post(url, headers=reviewer, json={**good, "reason": "ok fine"}).status_code == 422  # too short for HIGH
    # Escalate, then a REVIEWER can no longer decide - only ADMIN
    esc = client.post(url, headers=reviewer, json={**good, "decision": "ESCALATE", "reason": "Needs senior sign-off"})
    assert esc.status_code == 200 and esc.json()["transaction_status"] == "ESCALATED"
    assert client.post(url, headers=reviewer, json=good).status_code == 403
    assert oid not in fake_paypal.capture_calls
    r = client.post(url, headers=admin, json=good)
    assert r.status_code == 200, r.text
    assert r.json()["paypal"]["capture_status"] == "COMPLETED"
    assert fake_paypal.capture_calls.count(oid) == 1
    # Decision is final; repeating it is rejected and does not capture again
    assert client.post(url, headers=admin, json=good).status_code == 409
    assert fake_paypal.capture_calls.count(oid) == 1
    with SessionLocal() as db:
        actions = [a.action for a in db.execute(select(AuditLog).where(AuditLog.entity_id.in_([txn, oid]))).scalars()]
    assert "REVIEW_DECISION" in actions and "PAYPAL_CAPTURE" in actions and "PAYMENT_HELD" in actions


def test_reject_decision_never_captures(client, cara, reviewer, fake_paypal):
    o = create_order(client, cara, [{"product_id": "PRD_013", "quantity": 1}], "fp-ring-emulator-02").json()
    oid, txn = o["paypal_order_id"], o["transaction_id"]
    fake_paypal.approve(oid)
    client.post("/api/paypal/capture-order", headers=cara, json={"order_id": oid})
    r = client.post(f"/api/reviews/{txn}/decision", headers=reviewer, json={
        "decision": "REJECT", "reason": "Ring device and mule destination", "password": PASSWORD, "confirm_transaction_id": txn})
    assert r.status_code == 200
    assert "NOT_CAPTURED" in r.json()["payment_outcome"]
    assert oid not in fake_paypal.capture_calls
    order = client.get(f"/api/paypal/order/{oid}", headers=reviewer).json()
    assert order["sentinel_status"] == "REJECTED" and order["paypal_status"] == "APPROVED" and order["capture_status"] is None


def _webhook(client, headers, event):
    return client.post("/api/paypal/webhook", json=event, headers={
        "paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
        "paypal-transmission-id": "tx-1", "paypal-transmission-time": "2026-10-31T10:00:00Z", **headers})


def test_webhook_signature_verification_and_dedupe(client, ava, fake_paypal):
    o = create_order(client, ava, [{"product_id": "PRD_010", "quantity": 1}], "fp-ava-macbook-air").json()
    event = {"id": "WH-EVT-1", "event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": o["paypal_order_id"]}}
    assert _webhook(client, {"paypal-transmission-sig": "forged"}, event).status_code == 400
    assert _webhook(client, {}, {**event, "id": "WH-EVT-0"}).status_code == 400  # missing signature headers
    r = _webhook(client, {"paypal-transmission-sig": "valid-signature"}, event)
    assert r.status_code == 200 and r.json()["status"] == "processed"
    assert _webhook(client, {"paypal-transmission-sig": "valid-signature"}, event).json()["status"] == "duplicate"
    rows = client.get("/api/paypal/orders", headers=ava).json()
    assert next(x for x in rows if x["paypal_order_id"] == o["paypal_order_id"])["paypal_status"] == "APPROVED"
