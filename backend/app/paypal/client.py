"""Minimal, explicit PayPal REST client (Orders v2, Capture, Webhook signature verification).

Secrets stay on the server. Every call returns the real PayPal response; nothing is synthesised.
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

from ..config import get_settings

log = logging.getLogger("sentinel.paypal")


class PayPalNotConfigured(Exception):
    pass


class PayPalError(Exception):
    def __init__(self, status: int, body: dict | str, debug_id: str | None = None):
        self.status = status
        self.body = body
        self.debug_id = debug_id
        name = body.get("name") if isinstance(body, dict) else None
        details = body.get("details") if isinstance(body, dict) else None
        self.issue = (details[0].get("issue") if details else None) or name
        super().__init__(f"PayPal API error {status}: {self.issue or body}")


class PayPalClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        s = get_settings()
        self.client_id = s.paypal_client_id
        self.secret = s.paypal_client_secret
        self.webhook_id = s.paypal_webhook_id
        self.http = httpx.Client(base_url=s.paypal_base_url, timeout=20.0, transport=transport)
        self._token: str | None = None
        self._token_exp = 0.0
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.secret)

    def _access_token(self) -> str:
        if not self.configured:
            raise PayPalNotConfigured("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not set")
        with self._lock:
            if self._token and time.time() < self._token_exp - 60:
                return self._token
            r = self.http.post(
                "/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.secret),
                headers={"Accept": "application/json"},
            )
            if r.status_code != 200:
                raise PayPalError(r.status_code, _json(r), r.headers.get("paypal-debug-id"))
            body = r.json()
            self._token = body["access_token"]
            self._token_exp = time.time() + int(body.get("expires_in", 300))
            return self._token

    def _request(self, method: str, path: str, *, json: dict | None = None, request_id: str | None = None) -> tuple[dict, httpx.Response]:
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if request_id:
            headers["PayPal-Request-Id"] = request_id  # PayPal-side idempotency
        r = self.http.request(method, path, json=json, headers=headers)
        if r.status_code >= 400:
            raise PayPalError(r.status_code, _json(r), r.headers.get("paypal-debug-id"))
        return _json(r), r

    # ---------------------------------------------------------------- Orders v2
    def create_order(self, *, reference_id: str, amount: str, currency: str, items: list[dict], request_id: str,
                     description: str) -> tuple[dict, httpx.Response]:
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": reference_id,
                "custom_id": reference_id,
                "invoice_id": f"{reference_id}-{int(time.time())}",
                "description": description[:127],
                "amount": {
                    "currency_code": currency,
                    "value": amount,
                    "breakdown": {"item_total": {"currency_code": currency, "value": amount}},
                },
                "items": items,
            }],
            "payment_source": {"paypal": {"experience_context": {
                "brand_name": "SENTINEL MERCHANT",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
            }}},
        }
        return self._request("POST", "/v2/checkout/orders", json=payload, request_id=request_id)

    def get_order(self, order_id: str) -> tuple[dict, httpx.Response]:
        return self._request("GET", f"/v2/checkout/orders/{order_id}")

    def capture_order(self, order_id: str, request_id: str) -> tuple[dict, httpx.Response]:
        return self._request("POST", f"/v2/checkout/orders/{order_id}/capture", json={}, request_id=request_id)

    # ---------------------------------------------------------------- Webhooks
    def verify_webhook(self, headers: dict[str, str], event: dict) -> bool:
        if not self.webhook_id:
            raise PayPalNotConfigured("PAYPAL_WEBHOOK_ID is not set; webhooks cannot be verified")
        h = {k.lower(): v for k, v in headers.items()}
        required = ["paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig",
                    "paypal-transmission-time"]
        if any(not h.get(k) for k in required):
            return False
        body = {
            "auth_algo": h["paypal-auth-algo"],
            "cert_url": h["paypal-cert-url"],
            "transmission_id": h["paypal-transmission-id"],
            "transmission_sig": h["paypal-transmission-sig"],
            "transmission_time": h["paypal-transmission-time"],
            "webhook_id": self.webhook_id,
            "webhook_event": event,
        }
        data, _ = self._request("POST", "/v1/notifications/verify-webhook-signature", json=body)
        return data.get("verification_status") == "SUCCESS"


def _json(r: httpx.Response) -> dict:
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text[:500]}


_client: PayPalClient | None = None


def get_paypal() -> PayPalClient:
    global _client
    if _client is None:
        _client = PayPalClient()
    return _client


def set_paypal(client: PayPalClient | None) -> None:
    """Test hook to inject a client with a mock transport."""
    global _client
    _client = client
