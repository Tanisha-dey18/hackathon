# SENTINEL Technical Architecture

This document describes the system as implemented in this repository (`backend/app`, `frontend/src`). Every diagram matches the code. Items that are configured but not executed, or not implemented, are marked as such.

## 1. High-level architecture

```mermaid
flowchart LR
  subgraph Browser["Browser (React SPA)"]
    SHOP["SENTINEL MERCHANT<br/>catalogue, cart, PayPal Buttons"]
    CON["Console<br/>dashboard, workspace, graph, models, audit"]
  end
  subgraph API["FastAPI backend"]
    R["Routers: auth, transactions, intel, paypal, ops"]
    GW["services/payments.py<br/>order lifecycle, capture lock"]
    RK["services/risk.py<br/>features, scoring, policy"]
    ML["ml/<br/>predictor + SHAP"]
    GE["graph/engine.py<br/>NetworkX"]
    AG["agent/<br/>LangGraph + tools"]
    RV["services/review.py"]
    AU["audit.py<br/>hash chain"]
    WS["infra.py<br/>WebSocket + rate limiter"]
  end
  PP[("PayPal Sandbox REST")]
  GQ[("Groq API (optional)")]
  DB[("PostgreSQL / SQLite")]
  RD[("Redis (optional)")]
  SHOP -->|REST| R
  CON -->|REST + WS| R
  R --> GW --> PP
  R --> RV --> GW
  GW --> RK --> ML
  RK --> GE
  R --> AG --> GQ
  AG --> ML
  AG --> GE
  R --> AU
  R --> WS
  API --> DB
  WS -.-> RD
```

<!-- pdf:DIAGRAM:architecture -->

The browser runs one React application with two areas: the storefront for shoppers and the console for staff. The FastAPI backend holds all business logic and is the only component that talks to PayPal and Groq. State lives in a relational database: PostgreSQL in Docker/Render, SQLite for local development. Redis is optional and only used for shared rate-limit counters.

## 2. Transaction lifecycle

```mermaid
sequenceDiagram
  autonumber
  participant B as Buyer
  participant S as Storefront
  participant A as Sentinel API
  participant R as Risk + Graph
  participant P as PayPal Sandbox
  participant V as Reviewer
  B->>S: Click PayPal button
  S->>A: POST /api/paypal/create-order {items, device_fingerprint} + Idempotency-Key
  A->>A: server-side prices, Transaction AWAITING_APPROVAL
  A->>P: POST /v2/checkout/orders (intent CAPTURE, PayPal-Request-Id)
  P-->>A: 201 CREATED {id}
  A-->>S: paypal_order_id
  B->>P: Approve in popup (Sandbox personal account)
  S->>A: POST /api/paypal/capture-order {order_id}
  A->>P: GET /v2/checkout/orders/{id}
  P-->>A: APPROVED, amount, reference_id
  A->>A: verify owner, amount, currency, reference
  A->>R: assess_transaction()
  R-->>A: level + SHAP factors + policy notes
  alt LOW
    A->>A: UPDATE capture_state NONE to IN_PROGRESS (compare-and-set)
    A->>P: POST /capture (PayPal-Request-Id capture-{id})
    P-->>A: COMPLETED + capture id
  else MEDIUM / HIGH / CRITICAL
    A->>A: sentinel_status HELD, investigation started for HIGH+
    V->>A: POST /api/reviews/{txn}/decision (password, confirm id)
    A->>P: capture only if APPROVE
  end
```

<!-- pdf:DIAGRAM:sequence -->

## 3. Component interaction

```mermaid
flowchart TB
  CO["POST /capture-order"] --> PO["process_approved_order()"]
  PO --> GO["PayPalClient.get_order()"]
  PO --> AR["assess_and_route()"]
  AR --> AT["assess_transaction()"]
  AT --> FS["FeatureState.features()"]
  AT --> PF["predict_frame()<br/>model + IsoForest + SHAP"]
  AT --> CS["GraphEngine.customer_signals()"]
  AT --> FP[("fraud_predictions")]
  AR --> BR["apply_risk_branch()"]
  BR --> SY["sync_transaction() to graph tables"]
  PO -->|LOW| EC["execute_capture(AUTO_POLICY)"]
  PO -->|HIGH+| LI["launch_investigation() thread"]
  DEC["POST /reviews/{txn}/decision"] --> RD["review.decide()"] --> EC2["execute_capture(REVIEWER)"]
  EC --> CA["_capture_authorized()"]
  EC2 --> CA
  CA --> CAS["compare-and-set lock"] --> PC["PayPalClient.capture_order()"]
```

Both capture paths go through the same `execute_capture()`. That function re-checks authorisation itself (a LOW assessment for `AUTO_POLICY`, or a stored APPROVE decision for `REVIEWER`) before it takes the lock and calls PayPal.

## 4. Database ER diagram

```mermaid
erDiagram
  customers ||--o{ transactions : makes
  customers ||--o{ payment_destinations : owns
  customers ||--o| users : "shopper login"
  merchants ||--o{ transactions : receives
  merchants ||--o{ products : sells
  payment_destinations ||--o{ transactions : "paid to"
  payment_destinations ||--o| merchants : payout
  devices ||--o{ transactions : "made on"
  transactions ||--o{ fraud_predictions : scored
  model_versions ||--o{ fraud_predictions : produced
  transactions ||--o{ investigations : investigated
  investigations ||--o{ investigation_evidence : collects
  transactions ||--o| paypal_orders : "paid via"
  users ||--o{ paypal_orders : owns
  transactions ||--o{ reviewer_decisions : decided
  users ||--o{ reviewer_decisions : reviewer
  users ||--o{ audit_logs : actor
  graph_entities ||--o{ graph_relationships : source
```

<!-- pdf:DIAGRAM:erd -->

Key constraints: `transactions.amount > 0`, allowed status lists, unique `paypal_orders.paypal_order_id` / `transaction_id` / `create_idempotency_key` / `capture_id`, unique `payment_events.webhook_event_id`, unique `audit_logs.hash`, and composite indexes on customer+time and device+time. `payment_events` and `system_settings` have no foreign keys (events are keyed by PayPal order ID).

## 5. API communication flow

```mermaid
flowchart LR
  UI["React page"] -->|TanStack Query fetch + JWT| EP["FastAPI endpoint"]
  EP -->|Depends| AUTH["get_current_user / require_role"]
  EP -->|Depends| RL["rate_limit"]
  EP --> SV["service layer"]
  SV --> DB[("DB session")]
  SV --> AUD["audit.record()"]
  SV --> BC["ws_manager.broadcast()"]
  BC -->|WebSocket event| LP["LiveProvider"]
  LP -->|invalidateQueries| UI
```

Requests carry `Authorization: Bearer <JWT>`. Validation errors return 422 with a structured list. PayPal errors return 502 with PayPal's `debug_id`. A missing PayPal configuration returns 503. Background work (investigations, simulator, retraining) runs in threads and pushes WebSocket events with `asyncio.run_coroutine_threadsafe`.

## 6. ML inference flow

```mermaid
flowchart LR
  T["Transaction"] --> F["FeatureState.features()<br/>26 point-in-time features"]
  F --> M["primary model<br/>fraud_probability"]
  F --> I["Isolation Forest<br/>anomaly percentile"]
  M --> S["SHAP<br/>top factors as sentences"]
  G["GraphEngine signals"] --> P
  M --> P["Policy<br/>thresholds + escalations"]
  I --> P
  P --> O["fraud_predictions row<br/>+ audit + WS event"]
```

<!-- pdf:DIAGRAM:mlpipeline -->

Training replays history chronologically through the same `FeatureState`, uses a stratified 75/25 split and class weighting, trains four models and selects the primary by hold-out PR-AUC (v1: Random Forest, PR-AUC 0.897 on synthetic data).

## 7. AI agent tool-calling flow

```mermaid
flowchart TB
  S((start)) --> N1[retrieve_transaction<br/>TransactionHistoryTool]
  N1 --> N2[customer_behaviour<br/>CustomerBehaviourTool]
  N2 --> N3[ml_prediction<br/>FraudPredictionTool]
  N3 --> N4[graph_investigation<br/>GraphInvestigationTool]
  N4 --> N5[merchant_risk<br/>MerchantRiskTool]
  N5 --> N6[collect_evidence<br/>EvidenceCollectionTool E1..En]
  N6 --> N7{GROQ_API_KEY?}
  N7 -->|yes| L[Groq chat + tools<br/>transaction_history, customer_behaviour,<br/>graph_investigation, merchant_risk,<br/>submit_investigation_report]
  L -->|tool results become new evidence| L
  N7 -->|no or error| D[Rule-based draft<br/>DETERMINISTIC_FALLBACK]
  L --> N8[generate_report<br/>InvestigationReportTool validator]
  D --> N8
  N8 --> N9[route_to_reviewer<br/>review queue + audit]
```

<!-- pdf:DIAGRAM:agent -->

The validator drops findings that cite no valid evidence key, normalises the recommendation, and falls back to the rule-based report if no supported findings remain. The agent has no payment tools. **The Groq path is implemented but has not been executed** (no API key was available); all recorded investigations used the labelled fallback.

## 8. Graph intelligence

<!-- pdf:DIAGRAM:graph -->

```mermaid
flowchart LR
  TX["transactions"] -->|sync_transaction / rebuild| GT[("graph_entities<br/>graph_relationships")]
  GT --> NX["NetworkX DiGraph"]
  NX --> PJ["Entity projection<br/>customer-device-destination-merchant"]
  PJ --> SD["shared devices (>= 3 customers)"]
  PJ --> CY["simple_cycles on money flow"]
  PJ --> CC["connected components<br/>(merchant hubs excluded)"]
  PJ --> FD["flagged destination interactions"]
  SD & CY & CC & FD --> SIG["customer_signals() to risk policy + agent evidence"]
  PJ --> VW["explorer views (Kamada-Kawai layout) to React Flow"]
```

Community detection is **not implemented**; connected components are used instead.

## 9. PayPal payment flow and state

```mermaid
stateDiagram-v2
  [*] --> AWAITING_BUYER_APPROVAL: create-order (PayPal CREATED)
  AWAITING_BUYER_APPROVAL --> CLEARED: approved + LOW
  AWAITING_BUYER_APPROVAL --> HELD_FOR_VERIFICATION: approved + MEDIUM
  AWAITING_BUYER_APPROVAL --> HELD_FOR_REVIEW: approved + HIGH/CRITICAL
  AWAITING_BUYER_APPROVAL --> INTEGRITY_FAILED: amount/reference mismatch
  CLEARED --> APPROVED_AUTO: capture COMPLETED
  HELD_FOR_VERIFICATION --> ESCALATED
  HELD_FOR_REVIEW --> ESCALATED
  HELD_FOR_VERIFICATION --> APPROVED_BY_REVIEWER: APPROVE + capture
  HELD_FOR_REVIEW --> APPROVED_BY_REVIEWER: APPROVE + capture
  ESCALATED --> APPROVED_BY_REVIEWER: ADMIN APPROVE + capture
  HELD_FOR_VERIFICATION --> REJECTED: REJECT (not captured)
  HELD_FOR_REVIEW --> REJECTED
  ESCALATED --> REJECTED
  CLEARED --> CAPTURE_FAILED: PayPal error
```

This diagram shows `sentinel_status`. `paypal_status` / `capture_status` are separate fields written only from PayPal responses and verified webhooks.

## 10. Security boundaries and data flow

```mermaid
flowchart LR
  subgraph Public["Untrusted: browser"]
    U["User input, cart, device id"]
  end
  subgraph Server["Trusted: backend"]
    V["Pydantic validation + rate limits"]
    A["JWT + role checks + ownership"]
    L["Business logic: server prices, risk, capture lock"]
    S["Secrets from env: PayPal secret, Groq key, JWT secret"]
    LG["Logs (token/secret redaction)"]
  end
  subgraph External["External services"]
    P["PayPal (OAuth over HTTPS)"]
    G["Groq (HTTPS)"]
  end
  U -->|HTTPS + JWT| V --> A --> L
  S --> L
  L --> P
  L --> G
  L --> LG
  P -->|webhook + signature| V
```

| Boundary | Control |
|---|---|
| Browser to API | JWT, RBAC, Pydantic validation, rate limits, CORS allow-list, security headers |
| Client-supplied prices | Ignored; recalculated server-side, then re-verified against PayPal |
| Order ownership | Every order endpoint checks `user_id` (or staff role where allowed) |
| PayPal secret | Server environment only; browser receives only the client ID |
| Webhooks | Accepted only after PayPal's verify-webhook-signature returns SUCCESS; event IDs de-duplicated |
| Irreversible actions | Only humans (re-authenticated) can approve held captures; the agent has no payment tools |
| Audit | Hash-chained rows; `/api/audit/verify` detects modification |

## 11. Deployment

<!-- pdf:DIAGRAM:deployment -->

| Mode | Status |
|---|---|
| Local: Uvicorn + Vite, SQLite, in-memory limits | Running and verified |
| Docker Compose: postgres:16, redis:7, backend, nginx frontend | Configured, not run on the build machine |
| Render Blueprint: managed PostgreSQL, Docker API, static site | Configured, not deployed |
