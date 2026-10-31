"""SQLAlchemy ORM models. Identifiers for domain entities are readable strings (TXN_..., CUS_...)."""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


ROLES = ("ADMIN", "REVIEWER", "ANALYST", "CUSTOMER")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), index=True)
    city: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(2))
    home_lat: Mapped[float] = mapped_column(Float)
    home_lon: Mapped[float] = mapped_column(Float)
    segment: Mapped[str] = mapped_column(String(40), default="RETAIL")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class Merchant(TimestampMixin, Base):
    __tablename__ = "merchants"
    __table_args__ = (CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_merchant_risk"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60))
    country: Mapped[str] = mapped_column(String(2))
    risk_score: Mapped[float] = mapped_column(Float, default=0.1)
    high_risk_category: Mapped[bool] = mapped_column(Boolean, default=False)
    chargeback_rate: Mapped[float] = mapped_column(Float, default=0.0)
    payout_destination_id: Mapped[str | None] = mapped_column(ForeignKey("payment_destinations.id"), nullable=True)


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    device_type: Mapped[str] = mapped_column(String(30))
    os: Mapped[str] = mapped_column(String(40))
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)


class PaymentDestination(TimestampMixin, Base):
    """Where funds ultimately land: merchant payout accounts or peer wallets."""

    __tablename__ = "payment_destinations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # MERCHANT_PAYOUT | WALLET
    owner_customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price > 0", name="ck_product_price"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60))
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    image: Mapped[str] = mapped_column(String(40))  # icon key rendered by the frontend
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    stock: Mapped[int] = mapped_column(Integer, default=100)

    merchant: Mapped[Merchant] = relationship()


TXN_STATUSES = (
    "COMPLETED", "FAILED",  # historical synthetic outcomes
    "AWAITING_APPROVAL", "ASSESSING", "CLEARED", "HELD_FOR_VERIFICATION", "HELD_FOR_REVIEW",
    "ESCALATED", "APPROVED", "REJECTED", "CAPTURED", "CAPTURE_FAILED",
)


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_txn_amount_positive"),
        CheckConstraint(f"status IN {TXN_STATUSES}", name="ck_txn_status"),
        Index("ix_txn_customer_time", "customer_id", "created_at"),
        Index("ix_txn_device_time", "device_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("merchants.id"), index=True, nullable=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("payment_destinations.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    channel: Mapped[str] = mapped_column(String(30))  # SYNTHETIC_HISTORY | SIMULATOR | DEMO | PAYPAL_CHECKOUT
    status: Mapped[str] = mapped_column(String(30), index=True)
    risk_level: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)
    review_status: Mapped[str] = mapped_column(String(20), default="NONE", index=True)
    # Ground-truth label exists only for synthetic history (used for training); never for live payments.
    is_fraud: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    scenario: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    customer: Mapped[Customer] = relationship()
    merchant: Mapped[Merchant | None] = relationship()
    device: Mapped[Device] = relationship()
    destination: Mapped[PaymentDestination] = relationship()


class ModelVersion(TimestampMixin, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("version", "algorithm", name="uq_model_version_algo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(20), index=True)
    algorithm: Mapped[str] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics: Mapped[dict] = mapped_column(JSON)
    feature_names: Mapped[list] = mapped_column(JSON)
    artifact_path: Mapped[str] = mapped_column(String(255))
    training_rows: Mapped[int] = mapped_column(Integer)
    test_rows: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FraudPrediction(TimestampMixin, Base):
    __tablename__ = "fraud_predictions"
    __table_args__ = (
        CheckConstraint("fraud_probability >= 0 AND fraud_probability <= 1", name="ck_pred_prob"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    fraud_probability: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float] = mapped_column(Float)
    graph_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(10), index=True)
    recommended_action: Mapped[str] = mapped_column(String(30))
    top_risk_factors: Mapped[list] = mapped_column(JSON)
    shap_values: Mapped[dict] = mapped_column(JSON)
    features: Mapped[dict] = mapped_column(JSON)
    policy_notes: Mapped[list] = mapped_column(JSON, default=list)
    latency_ms: Mapped[float] = mapped_column(Float)

    model_version: Mapped[ModelVersion] = relationship()


class Investigation(TimestampMixin, Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")  # RUNNING | COMPLETED | FAILED
    mode: Mapped[str] = mapped_column(String(30))  # LLM_AGENT | DETERMINISTIC_FALLBACK
    llm_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evidence: Mapped[list["InvestigationEvidence"]] = relationship(
        back_populates="investigation", order_by="InvestigationEvidence.id", cascade="all, delete-orphan"
    )


class InvestigationEvidence(TimestampMixin, Base):
    __tablename__ = "investigation_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), index=True)
    evidence_key: Mapped[str] = mapped_column(String(20))  # E1, E2 ... cited by the report
    tool_name: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))  # INFO | LOW | MEDIUM | HIGH
    summary: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON)

    investigation: Mapped[Investigation] = relationship(back_populates="evidence")


class GraphEntity(TimestampMixin, Base):
    __tablename__ = "graph_entities"
    __table_args__ = (UniqueConstraint("entity_type", "ref_id", name="uq_graph_entity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True)  # CUSTOMER | MERCHANT | DEVICE | DESTINATION | TRANSACTION
    ref_id: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(160))
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)


class GraphRelationship(TimestampMixin, Base):
    __tablename__ = "graph_relationships"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "rel_type", name="uq_graph_rel"),
        Index("ix_graph_rel_target", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("graph_entities.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("graph_entities.id", ondelete="CASCADE"))
    rel_type: Mapped[str] = mapped_column(String(30))  # USES_DEVICE | MADE_PAYMENT | PAID_MERCHANT | PAID_TO | OWNS_WALLET
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class PayPalOrder(TimestampMixin, Base):
    __tablename__ = "paypal_orders"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_ppo_amount"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paypal_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    items: Mapped[list] = mapped_column(JSON)
    create_idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    # PayPal's view of the order (CREATED, APPROVED, COMPLETED, VOIDED...) - only ever set from PayPal responses
    paypal_status: Mapped[str] = mapped_column(String(30))
    # Sentinel's risk/decision view - independent of PayPal
    sentinel_status: Mapped[str] = mapped_column(String(30), default="PENDING_RISK")
    # Local capture lock: NONE -> IN_PROGRESS -> DONE | FAILED. Guarantees a single capture attempt.
    capture_state: Mapped[str] = mapped_column(String(20), default="NONE")
    capture_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    capture_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_paypal_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    transaction: Mapped[Transaction] = relationship()


class PaymentEvent(TimestampMixin, Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(20))  # PAYPAL_API | PAYPAL_WEBHOOK | SENTINEL
    event_type: Mapped[str] = mapped_column(String(80))
    webhook_event_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    signature_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paypal_debug_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)


class ReviewerDecision(TimestampMixin, Base):
    __tablename__ = "reviewer_decisions"
    __table_args__ = (CheckConstraint("decision IN ('APPROVE','REJECT','ESCALATE')", name="ck_decision"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    investigation_id: Mapped[str | None] = mapped_column(ForeignKey("investigations.id"), nullable=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    risk_level_at_decision: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_outcome: Mapped[str | None] = mapped_column(String(60), nullable=True)

    reviewer: Mapped[User] = relationship()


class AuditLog(TimestampMixin, Base):
    """Append-only, hash-chained audit trail (each row commits to the previous row's hash)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_label: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
