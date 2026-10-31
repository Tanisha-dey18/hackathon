"""PayPal checkout endpoints (Orders v2, capture, webhooks) and the shopper storefront."""
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..infra import rate_limit
from ..ml.features import aware
from ..models import PaymentEvent, PayPalOrder, Product, User
from ..security import STAFF, get_current_user, require_staff
from ..services import payments

router = APIRouter()


class CartItem(BaseModel):
    product_id: str = Field(pattern=r"^PRD_\w+$")
    quantity: int = Field(ge=1, le=10)


class Geo(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class CreateOrderIn(BaseModel):
    items: list[CartItem] = Field(min_length=1, max_length=20)
    device_fingerprint: str = Field(min_length=8, max_length=128)
    geo: Geo | None = None


class CaptureIn(BaseModel):
    order_id: str = Field(min_length=5, max_length=64, pattern=r"^[A-Z0-9]+$")


@router.get("/api/paypal/config", tags=["paypal"], summary="Public client configuration (no secrets)")
def paypal_config():
    s = get_settings()
    return {"configured": s.paypal_configured, "client_id": s.paypal_client_id if s.paypal_configured else None,
            "currency": s.paypal_currency, "environment": "sandbox" if "sandbox" in s.paypal_base_url else "live",
            "webhook_verification": bool(s.paypal_webhook_id)}


@router.post("/api/paypal/create-order", tags=["paypal"], dependencies=[Depends(rate_limit(20, "create-order"))])
def create_order(body: CreateOrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user),
                 idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=80)):
    return payments.create_order(db, user, [i.model_dump() for i in body.items], body.device_fingerprint,
                                 idempotency_key, body.geo.model_dump() if body.geo else None)


@router.post("/api/paypal/capture-order", tags=["paypal"], dependencies=[Depends(rate_limit(20, "capture"))],
             summary="Buyer approved: verify with PayPal, run Sentinel risk policy, capture only if permitted")
def capture_order(body: CaptureIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return payments.process_approved_order(db, user, body.order_id)


@router.get("/api/paypal/order/{order_id}", tags=["paypal"], summary="Refresh order state from PayPal")
def get_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.execute(select(PayPalOrder).where(PayPalOrder.paypal_order_id == order_id)).scalar()
    if not o:
        raise HTTPException(404, "Order not found")
    if o.user_id != user.id and user.role not in STAFF:
        raise HTTPException(403, "This order does not belong to you")
    return payments.refresh_order(db, o)


@router.get("/api/paypal/orders", tags=["paypal"])
def list_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(PayPalOrder).order_by(PayPalOrder.created_at.desc())
    if user.role not in STAFF:
        q = q.where(PayPalOrder.user_id == user.id)
    return [payments.order_view(o) for o in db.execute(q.limit(500)).scalars()]


@router.get("/api/paypal/events", tags=["paypal"])
def list_events(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    rows = db.execute(select(PaymentEvent).order_by(PaymentEvent.id.desc()).limit(300)).scalars()
    return [{"id": e.id, "paypal_order_id": e.paypal_order_id, "source": e.source, "event_type": e.event_type,
             "http_status": e.http_status, "debug_id": e.paypal_debug_id, "verified": e.signature_verified,
             "webhook_event_id": e.webhook_event_id, "created_at": aware(e.created_at), "payload": e.payload} for e in rows]


@router.post("/api/paypal/webhook", tags=["paypal"], dependencies=[Depends(rate_limit(300, "webhook"))],
             summary="PayPal webhook receiver (signature verified via PayPal verify-webhook-signature API)")
async def webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if len(raw) > 256_000:
        raise HTTPException(413, "Payload too large")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Invalid JSON")
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(payments.handle_webhook, db, dict(request.headers), event)


# ------------------------------------------------------------------------------- storefront
def product_view(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "category": p.category, "price": float(p.price),
            "image": p.image, "merchant_id": p.merchant_id, "merchant_name": p.merchant.name, "stock": p.stock}


@router.get("/api/shop/products", tags=["shop"])
def products(db: Session = Depends(get_db)):
    return [product_view(p) for p in db.execute(select(Product).order_by(Product.id)).scalars()]


@router.get("/api/shop/demo-presets", tags=["shop"], summary="Shopper-side presets for the three demo scenarios")
def demo_presets(db: Session = Depends(get_db)):
    from ..services.demo import scenario_list
    return [{k: s[k] for k in ("key", "title", "shopper_email", "device_fingerprint", "geo", "products")}
            for s in scenario_list(db)]


@router.get("/api/shop/products/{product_id}", tags=["shop"])
def product(product_id: str, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    return product_view(p)
