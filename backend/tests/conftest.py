"""Test fixtures. Tests run against an isolated SQLite database and a mock PayPal transport.

The mock transport is a test double that emulates PayPal Sandbox REST semantics (OAuth, Orders v2,
capture idempotency via PayPal-Request-Id, webhook signature verification) so the gateway logic
can be verified offline. The application itself never uses it.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

_tmp = Path(tempfile.mkdtemp(prefix="sentinel-test-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{(_tmp / 'test.db').as_posix()}",
    "MODEL_DIR": str(_tmp / "models"),
    "PAYPAL_CLIENT_ID": "test-client-id",
    "PAYPAL_CLIENT_SECRET": "test-client-secret",
    "PAYPAL_WEBHOOK_ID": "WH-TEST",
    "GROQ_API_KEY": "",
    "REDIS_URL": "",
    "RATE_LIMIT_PER_MINUTE": "10000",
    "JWT_SECRET": "test-secret-key-that-is-long-enough-for-hs256",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402
from app.paypal.client import PayPalClient, set_paypal  # noqa: E402

PASSWORD = get_settings().seed_password


class FakePayPal:
    """Stateful emulation of the PayPal Sandbox endpoints Sentinel uses."""

    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.capture_calls: list[str] = []
        self.request_ids: dict[str, dict] = {}
        self.amount_override: str | None = None
        self.n = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "A21-test", "expires_in": 3600})
        if request.headers.get("authorization") != "Bearer A21-test":
            return httpx.Response(401, json={"name": "AUTHENTICATION_FAILURE"})
        rid = request.headers.get("paypal-request-id")
        if path == "/v2/checkout/orders" and request.method == "POST":
            if rid and rid in self.request_ids:
                return httpx.Response(200, json=self.request_ids[rid])
            body = json.loads(request.content)
            self.n += 1
            oid = f"5O1901{self.n:05d}TEST"
            pu = body["purchase_units"][0]
            order = {"id": oid, "status": "CREATED", "intent": "CAPTURE",
                     "purchase_units": [{"reference_id": pu["reference_id"], "amount": pu["amount"]}]}
            self.orders[oid] = order
            if rid:
                self.request_ids[rid] = order
            return httpx.Response(201, json=order, headers={"paypal-debug-id": "dbg-create"})
        if path.startswith("/v2/checkout/orders/"):
            parts = path.split("/")
            oid = parts[4]
            order = self.orders.get(oid)
            if not order:
                return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND"})
            if request.method == "GET":
                out = json.loads(json.dumps(order))
                if self.amount_override:
                    out["purchase_units"][0]["amount"]["value"] = self.amount_override
                return httpx.Response(200, json=out)
            if parts[-1] == "capture":
                self.capture_calls.append(oid)
                if rid and rid in self.request_ids:
                    return httpx.Response(201, json=self.request_ids[rid])
                if order["status"] == "COMPLETED":
                    return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY",
                                                     "details": [{"issue": "ORDER_ALREADY_CAPTURED"}]})
                if order["status"] != "APPROVED":
                    return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY",
                                                     "details": [{"issue": "ORDER_NOT_APPROVED"}]})
                order["status"] = "COMPLETED"
                order["purchase_units"][0]["payments"] = {"captures": [
                    {"id": f"CAP{oid[-9:]}", "status": "COMPLETED", "amount": order["purchase_units"][0]["amount"]}]}
                if rid:
                    self.request_ids[rid] = order
                return httpx.Response(201, json=order, headers={"paypal-debug-id": "dbg-capture"})
        if path == "/v1/notifications/verify-webhook-signature":
            body = json.loads(request.content)
            ok = body["transmission_sig"] == "valid-signature" and body["webhook_id"] == "WH-TEST"
            return httpx.Response(200, json={"verification_status": "SUCCESS" if ok else "FAILURE"})
        return httpx.Response(404, json={"name": "NOT_FOUND"})

    def approve(self, oid: str) -> None:
        """Simulates the buyer approving the order in the PayPal popup."""
        self.orders[oid]["status"] = "APPROVED"
        self.orders[oid]["payer"] = {"email_address": "buyer@personal.example.com", "payer_id": "PAYERTEST"}


@pytest.fixture(scope="session")
def fake_paypal():
    fake = FakePayPal()
    set_paypal(PayPalClient(transport=httpx.MockTransport(fake.handler)))
    return fake


@pytest.fixture(scope="session")
def client(fake_paypal):
    with TestClient(app) as c:  # lifespan runs migrations + seed + training
        yield c


def login(client, email: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def reviewer(client):
    return login(client, "reviewer@sentinel.dev")


@pytest.fixture(scope="session")
def admin(client):
    return login(client, "admin@sentinel.dev")


@pytest.fixture(scope="session")
def ava(client):
    return login(client, "ava@shopper.sentinel.dev")


@pytest.fixture(scope="session")
def ben(client):
    return login(client, "ben@shopper.sentinel.dev")


@pytest.fixture(scope="session")
def cara(client):
    return login(client, "cara@shopper.sentinel.dev")
