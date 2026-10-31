# SENTINEL

**Autonomous AI-powered payment risk intelligence and protection on PayPal.**
*Every transaction. Every connection. Every risk. Understood.*

![License: MIT](https://img.shields.io/badge/license-MIT-blue) ![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB) ![React 18](https://img.shields.io/badge/react-18-61DAFB) ![PayPal Sandbox](https://img.shields.io/badge/PayPal-Sandbox-003087) ![Tests: 23 passing](https://img.shields.io/badge/tests-23%20passing-2ea44f)

Sentinel is a payment protection layer that sits between a buyer approving a PayPal checkout and the merchant capturing the money. It verifies the PayPal order, scores the payment with machine learning and graph intelligence, captures low-risk payments automatically, and **holds everything else until a human reviewer approves it**, with an AI investigation report that cites its evidence.

Built for the **PayPal AI Hackathon 2026**.

> Hackathon prototype. It runs on **PayPal Sandbox** with **synthetic data** only and does not access PayPal's internal fraud systems or real customer data.

---

## Contents

1. [Problem](#1-problem) · 2. [Why it matters](#2-why-it-matters) · 3. [Solution](#3-solution) · 4. [Key features](#4-key-features) · 5. [Transaction lifecycle](#5-transaction-lifecycle) · 6. [Architecture](#6-architecture) · 7. [Tech stack](#7-tech-stack) · 8. [ML methodology](#8-machine-learning-methodology) · 9. [Graph detection](#9-graph-based-fraud-detection) · 10. [AI agent](#10-ai-investigation-agent) · 11. [PayPal integration](#11-paypal-sandbox-integration) · 12. [Human review](#12-human-in-the-loop-review) · 13. [Database](#13-database-architecture) · 14. [API](#14-api-overview) · 15. [Installation](#15-installation) · 16. [Environment variables](#16-environment-variables) · 17. [Running locally](#17-running-locally) · 18. [ML training and inference](#18-ml-training-and-inference) · 19. [Demo scenarios](#19-demo-scenarios) · 20. [Testing](#20-testing) · 21. [Security](#21-security) · 22. [Limitations](#22-current-limitations) · 23. [Future work](#23-future-improvements) · 24. [Screenshots](#24-screenshots) · 25. [Documentation](#25-documentation) · 26. [Team](#26-team) · 27. [License](#27-license)

---

## 1. Problem

Most fraud checks score one payment at a time and return a number with no reason. That fails in two ways:

- **Organised fraud is invisible one payment at a time.** Accounts that share a phone and send money to the same wallet each look normal on their own.
- **A score is not a decision.** Someone still has to work out *why* a payment was flagged, often after the money has already been captured.

## 2. Why it matters

A fraudulent capture usually comes back as a chargeback: the merchant loses the goods, the money and a fee. Blocking too aggressively is just as costly, because genuine customers leave. Payment decisions also affect real people, so reviewers and auditors need to see the reasons, not just a score.

## 3. Solution

Sentinel uses the gap that PayPal's Orders API already provides between **buyer approval** and **payment capture**:

1. The storefront creates a real PayPal Sandbox order on the server, using server-side prices.
2. The buyer approves in PayPal. No money moves yet.
3. Sentinel fetches the order from PayPal, checks status, amount and ownership, then scores the risk with an ML model, an anomaly detector and a relationship graph.
4. **LOW** risk is captured automatically. **MEDIUM / HIGH / CRITICAL** is held: approved in PayPal, but not captured.
5. For high-risk payments a LangGraph agent investigates with seven tools and writes a report in which every finding cites tool-produced evidence.
6. A reviewer re-enters their password and approves, rejects or escalates. Only approval triggers the PayPal capture.
7. Every step is written to a hash-chained audit log.

## 4. Key features

| Feature | Status |
|---|---|
| Demo storefront (SENTINEL MERCHANT) with PayPal JS SDK Buttons | Implemented |
| PayPal Orders v2 create / get / capture, OAuth, webhook signature verification | Implemented; tested with a mock PayPal transport; **live Sandbox run not yet verified** |
| Risk-gated capture with idempotency and bypass protection | Implemented and tested |
| ML risk model (Random Forest / XGBoost / Logistic Regression) + Isolation Forest + SHAP | Implemented and evaluated on synthetic data |
| Graph intelligence: shared devices, money loops, clusters, flagged destinations (NetworkX) | Implemented |
| LangGraph investigation agent with 7 tools and evidence validation | Implemented; Groq LLM path **not yet run** (no key); labelled rule-based fallback tested |
| Human review with re-authentication, typed confirmation and escalation | Implemented and tested |
| Hash-chained audit log with verification | Implemented and tested |
| Command Centre dashboard, live WebSocket updates, AG Grid transaction table, React Flow graph explorer | Implemented |
| Three demo scenarios + synthetic traffic simulator | Implemented |
| Docker Compose / Render deployment | Configured; **not run** (no Docker daemon on build machine, not deployed) |
| Community detection, AUTHORIZE-intent flow, refunds | Future work |

## 5. Transaction lifecycle

```mermaid
sequenceDiagram
  participant B as Buyer
  participant S as Storefront (React)
  participant A as Sentinel API (FastAPI)
  participant R as Risk engine (ML + graph)
  participant P as PayPal Sandbox
  participant V as Reviewer
  B->>S: Checkout with PayPal
  S->>A: POST /api/paypal/create-order (Idempotency-Key)
  A->>P: POST /v2/checkout/orders (intent CAPTURE, server prices)
  P-->>A: order CREATED
  B->>P: Approves in PayPal popup
  S->>A: POST /api/paypal/capture-order
  A->>P: GET /v2/checkout/orders/{id}
  P-->>A: APPROVED (amount, reference)
  A->>R: features, ML score, anomaly, graph signals
  R-->>A: risk level + explanation
  alt LOW
    A->>P: POST /capture (PayPal-Request-Id, DB compare-and-set lock)
    P-->>A: COMPLETED + capture id
  else MEDIUM / HIGH / CRITICAL
    A->>A: hold (not captured); start AI investigation for HIGH+
    V->>A: APPROVE / REJECT / ESCALATE (password + typed txn id)
    A->>P: capture only on APPROVE
  end
  P-->>A: webhook (verified via verify-webhook-signature)
```

PayPal's status (`CREATED`, `APPROVED`, `COMPLETED`) is only ever written from PayPal responses. Sentinel's decision (`CLEARED`, `HELD_FOR_REVIEW`, `REJECTED`, ...) is stored separately, so a held payment is never shown as paid.

## 6. Architecture

```mermaid
flowchart LR
  subgraph Browser
    SHOP[SENTINEL MERCHANT<br/>React + PayPal JS SDK]
    CON[Console<br/>Recharts · React Flow · AG Grid]
  end
  subgraph Backend[FastAPI backend]
    API[REST + WebSocket<br/>JWT · RBAC · rate limits]
    GW[Payment gateway<br/>capture state machine]
    RISK[Risk engine<br/>thresholds + escalations]
    ML[ML predictor<br/>RF · XGB · LR · IsoForest · SHAP]
    GRAPH[Graph engine<br/>NetworkX]
    AGENT[LangGraph agent<br/>7 tools]
    REV[Review service]
    AUD[Hash-chained audit log]
  end
  PP[(PayPal Sandbox)]
  GROQ[(Groq API - optional)]
  DB[(PostgreSQL / SQLite)]
  RED[(Redis - optional)]
  SHOP --> API
  CON <--> API
  API --> GW --> PP
  PP -. webhooks .-> API
  GW --> RISK --> ML
  RISK --> GRAPH
  RISK --> AGENT --> GROQ
  API --> REV --> GW
  API --> AUD
  Backend --> DB
  API -.-> RED
```

More diagrams (ER diagram, ML flow, agent tool-calling, security boundaries): [docs/SENTINEL_TECHNICAL_ARCHITECTURE.md](docs/SENTINEL_TECHNICAL_ARCHITECTURE.md).

## 7. Tech stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 18, TypeScript, Vite 6, Tailwind CSS | Typed components, fast builds, consistent dark design system |
| Data fetching | TanStack Query + one WebSocket | Cached API state; WebSocket events invalidate queries, so screens update live |
| Visualisation | Recharts, React Flow (@xyflow/react), Framer Motion | Dashboard and model charts; interactive relationship graph; transitions |
| Data grid | AG Grid Community (sponsor tool) | Filtering, sorting, quick search, pagination and CSV export over 2,000+ transactions |
| Payments | PayPal JS SDK (`@paypal/react-paypal-js`), Orders API v2, Webhooks | The capture step that Sentinel risk-gates |
| API | FastAPI, Pydantic v2 | Typed validation, automatic Swagger, WebSockets |
| Persistence | SQLAlchemy 2, Alembic, PostgreSQL (Docker/Render), SQLite (local) | Constraints and migrations; zero-setup local runs |
| Auth | bcrypt, PyJWT | Hashed passwords, signed tokens, role checks |
| ML | scikit-learn, XGBoost, SHAP, pandas, NumPy | Tabular fraud models with per-prediction explanations |
| Graph | NetworkX | Shared devices, cycles and components on a few thousand nodes |
| Agent | LangGraph, Groq SDK (`llama-3.3-70b-versatile` by default) | Inspectable multi-step workflow with LLM tool calling |
| Infra | Docker, Docker Compose, Render Blueprint, Redis (optional) | Reproducible environments; shared rate limiting |

## 8. Machine learning methodology

- **Data**: a deterministic synthetic world (seed 2026) of 100 customers, 25 merchants, 150 devices and 2,000 transactions with 142 labelled frauds (7.1%). It covers a device-farm ring, a circular wallet ring, account takeover and card testing, plus deliberately hard cases (16 "friendly fraud" and 22 legitimate large purchases).
- **Features**: 26 **point-in-time** features (amount vs. customer average, velocity, device sharing, geo distance and speed, failures, destination fan-in, merchant risk, time of day). The same `FeatureState` class is used for training and live scoring, so there is no train/serve skew.
- **Training**: median imputation inside each pipeline, stratified 75/25 split, class weights or `scale_pos_weight` for imbalance.
- **Selection**: the primary model is chosen automatically by **hold-out PR-AUC**, not accuracy.
- **Explanations**: SHAP (`TreeExplainer` / `LinearExplainer`) turns each prediction into readable factors such as *"Amount is 43.4x the customer's historical average"*.

Hold-out results (model v1, 500 test rows, **synthetic data**, threshold 0.5):

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|
| **Random Forest (primary)** | 0.941 | 0.889 | 0.914 | 0.939 | **0.897** |
| Logistic Regression | 0.744 | 0.889 | 0.810 | 0.952 | 0.893 |
| XGBoost | 0.914 | 0.889 | 0.901 | 0.951 | 0.886 |
| Isolation Forest (unsupervised) | 0.700 | 0.778 | 0.737 | 0.940 | 0.830 |

These numbers show that the pipeline is correct and evaluated honestly. They say nothing about real-world accuracy.

**Risk policy**: LOW < 0.30 ≤ MEDIUM < 0.70 ≤ HIGH < 0.90 ≤ CRITICAL. Escalations can only raise risk: anomaly percentile ≥ 0.98 or amount ≥ 10× average gives at least MEDIUM; graph signals give at least HIGH. Thresholds are editable by ADMIN and every change is audited.

## 9. Graph-based fraud detection

Every transaction writes relationships (customer→device, customer→transaction, transaction→merchant/destination, owner→wallet) into `graph_entities` / `graph_relationships`. NetworkX then detects:

- **Shared devices**: one device used by 3 or more customers.
- **Circular payments**: `simple_cycles` on a customer-to-customer money-flow graph.
- **Suspicious clusters**: connected components over customers, devices and wallets, excluding merchant hubs.
- **Flagged destinations**: payments to wallets on the synthetic watch list.

In the seeded data it finds 2 shared devices, a 4-account loop that moved $16,064.37, 2 flagged mule wallets and 4 suspicious clusters. Findings become evidence items and appear as red, clickable edges in the explorer.

## 10. AI investigation agent

A LangGraph state machine with nine nodes:
`retrieve_transaction → customer_behaviour → ml_prediction → graph_investigation → merchant_risk → collect_evidence → analyse → generate_report → route_to_reviewer`

- **7 tools**: TransactionHistory, CustomerBehaviour, FraudPrediction, GraphInvestigation, MerchantRisk, EvidenceCollection, InvestigationReport.
- **Evidence first**: evidence (E1…En) is derived deterministically from tool outputs, never by the LLM.
- **LLM mode** (`GROQ_API_KEY` set): Groq may call tools on related entities and must submit a structured report.
- **Validation**: findings without a valid evidence key are removed, and recommendations are limited to `APPROVE / HOLD_FOR_REVIEW / REJECT / ESCALATE`.
- **Fallback**: without Groq, or if it fails, a rule-based report is produced and **labelled** `DETERMINISTIC_FALLBACK`.
- **No payment tools**: the agent can only recommend.

## 11. PayPal Sandbox integration

| Call | Purpose |
|---|---|
| `POST /v1/oauth2/token` | Client-credentials token (server-side secret only) |
| `POST /v2/checkout/orders` | Create order: `intent=CAPTURE`, item breakdown, `reference_id` = Sentinel transaction, `PayPal-Request-Id` from the client's `Idempotency-Key` |
| `GET /v2/checkout/orders/{id}` | Verify APPROVED, amount, currency, reference before risk scoring |
| `POST /v2/checkout/orders/{id}/capture` | Capture with stable `PayPal-Request-Id: capture-{order_id}` |
| `POST /v1/notifications/verify-webhook-signature` | Verify webhooks (`PAYMENT.CAPTURE.*`, `CHECKOUT.ORDER.APPROVED`) |

**Exactly-once capture**: a database compare-and-set moves the capture state from `NONE/FAILED` to `IN_PROGRESS`, so only one request can call PayPal. The stable request ID and `ORDER_ALREADY_CAPTURED` reconciliation cover retries.

**No bypass**: the capture function itself requires a LOW assessment or a stored APPROVE decision.

## 12. Human-in-the-loop review

Held payments appear in the review queue (Fraud Intelligence) and in the investigation workspace. A decision requires:

- the REVIEWER or ADMIN role,
- **re-entering the password**,
- **typing the transaction ID**,
- a reason of at least 20 characters to approve HIGH or CRITICAL payments.

Escalated cases need an ADMIN. APPROVE captures through PayPal. REJECT leaves the PayPal order uncaptured. Every decision is stored and audited.

## 13. Database architecture

18 tables created by Alembic migration `0001_initial_schema`:

| Group | Tables |
|---|---|
| Core domain | `users`, `customers`, `merchants`, `devices`, `payment_destinations`, `products`, `transactions` |
| ML | `fraud_predictions`, `model_versions` |
| Agent | `investigations`, `investigation_evidence` |
| Graph | `graph_entities`, `graph_relationships` |
| Payments | `paypal_orders`, `payment_events` |
| Governance | `reviewer_decisions`, `audit_logs`, `system_settings` |

The schema uses foreign keys throughout, plus check and unique constraints. Examples: `amount > 0`, allowed status and role values, and unique PayPal order ID, capture ID, idempotency key and webhook event ID. No card numbers or PayPal credentials are stored.

## 14. API overview

Interactive docs at **http://localhost:8000/docs** (Swagger). Main groups:

| Group | Endpoints |
|---|---|
| Auth | `POST /api/auth/login`, `GET /api/auth/me` |
| Transactions & risk | `POST/GET /api/transactions`, `GET /api/transactions/{id}`, `POST /api/risk/assess`, `GET /api/risk/metrics` |
| Investigations | `POST /api/investigations/start`, `GET /api/investigations`, `GET /api/investigations/{id}` |
| Graph | `GET /api/graph/overview`, `/api/graph/entity/{id}`, `/api/graph/transaction/{id}` |
| PayPal | `GET /api/paypal/config`, `POST /api/paypal/create-order`, `POST /api/paypal/capture-order`, `GET /api/paypal/order/{id}`, `GET /api/paypal/orders`, `GET /api/paypal/events`, `POST /api/paypal/webhook` |
| Review | `POST /api/reviews/{txn}/decision`, `GET /api/reviews/queue` |
| Ops | `GET /api/dashboard/metrics`, `GET /api/audit`, `GET /api/audit/verify`, `GET /api/models`, `POST /api/models/retrain`, `GET/PUT /api/settings/risk-policy`, `GET /api/settings/integrations` |
| Demo & shop | `GET /api/demo/scenarios`, `POST /api/demo/scenarios/{A,B,C}/run`, `GET/POST /api/demo/simulator`, `GET /api/shop/products`, `GET /api/shop/demo-presets` |
| Live | `WS /ws/transactions?token=<JWT>` (staff) |

## 15. Installation

Prerequisites: **Python 3.12+**, **Node.js 20+**, Git. Docker is optional.

Run everything from the repository root (the commands work in PowerShell, cmd and bash; on macOS/Linux replace `backend\.venv\Scripts\` with `backend/.venv/bin/`):

```bash
git clone https://github.com/Tanisha-dey18/hackathon.git
```

```bash
cd hackathon
```

```bash
python -m venv backend\.venv
```

```bash
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

```bash
npm --prefix frontend install
```

## 16. Environment variables

Copy the template and fill in what you have. **Blank values fall back to safe defaults**, so the app runs with no keys at all: SQLite, no PayPal, rule-based agent.

```bash
cp .env.example .env
```

| Variable | Required | Purpose |
|---|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | For real checkout | Sandbox REST app credentials (developer.paypal.com → Apps & Credentials → Sandbox) |
| `PAYPAL_WEBHOOK_ID` | For webhooks | ID of the webhook configured on the Sandbox app (needs a public URL) |
| `PAYPAL_BASE_URL` | No | Defaults to `https://api-m.sandbox.paypal.com` |
| `GROQ_API_KEY`, `GROQ_MODEL` | No | Enables the LLM agent; otherwise the labelled fallback runs |
| `DATABASE_URL` | No | Blank = local SQLite; e.g. `postgresql://user:pass@host:5432/sentinel` |
| `REDIS_URL` | No | Shared rate limiting; blank = in-memory |
| `JWT_SECRET` | Yes in any shared deployment | Long random string |
| `SEED_PASSWORD` | No | Password for the synthetic demo accounts (default `SentinelDemo!2026`) |
| `CORS_ORIGINS`, `RATE_LIMIT_PER_MINUTE`, `AUTO_SEED` | No | Deployment tuning |

Never commit `.env`; it is git-ignored.

## 17. Running locally

Terminal 1 (backend; the first start migrates, seeds, trains and scores history in about 30–60 s):

```bash
backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --port 8000
```

Terminal 2 (frontend):

```bash
npm --prefix frontend run dev
```

| URL | What |
|---|---|
| http://localhost:5173/shop | Storefront |
| http://localhost:5173/console | Console (staff) |
| http://localhost:8000/docs | Swagger |

Demo accounts (all synthetic, password `SentinelDemo!2026`): `reviewer@sentinel.dev`, `admin@sentinel.dev`, `analyst@sentinel.dev`, `ava@shopper.sentinel.dev`, `ben@shopper.sentinel.dev`, `cara@shopper.sentinel.dev`.

**Reset to a clean state** (recommended before recording a demo, because every demo run adds history and shifts later scores): stop the backend, delete `backend/sentinel.db*` and `backend/model_store/`, then start it again.

**Docker (PostgreSQL + Redis + nginx):**

```bash
docker compose up --build
```

The frontend is then at http://localhost:8080. The Compose setup is written but was not run on the build machine.

## 18. ML training and inference

- **Training** happens automatically on first start. To retrain later, sign in as ADMIN and use **Model Analytics → Retrain models** (or `POST /api/models/retrain`). Retraining also learns from reviewer decisions (REJECT = fraud, APPROVE = legitimate).
- **Inference** runs on every assessment. Trigger it with checkout, a demo scenario, the simulator, `POST /api/transactions` or `POST /api/risk/assess`.
- Model files are stored in `backend/model_store/v{n}/bundle.joblib`. If the active file is missing at start-up, the backend retrains automatically.

## 19. Demo scenarios

Launch from **Command Centre → Demonstration scenarios**. "Run risk pipeline" uses the real engine without PayPal. "PayPal checkout" opens the real Sandbox checkout for that persona.

| | Scenario | Result observed on a fresh database |
|---|---|---|
| A | Ava buys $76 of coffee gear on her usual laptop | ML 0.006 → **LOW**, cleared for automatic capture |
| B | Ben (avg ≈ $38) buys a $1,849 ultrabook on a new device | ML 0.098, but 43.4× his average → **MEDIUM**, held for verification, SHAP explains why |
| C | Cara buys a $500 gift card on an emulator shared by 4 accounts | ML 0.313, graph policy → **HIGH**, agent recommends **REJECT** with 6 evidence-backed findings |

Exact scores change slightly after repeated runs because each run adds history (reset the database for consistent numbers).

## 20. Testing

```bash
backend\.venv\Scripts\python -m pytest -q backend\tests
```

**Latest result: 23 passed, 0 failed.** The tests run against an isolated database and a **mock PayPal transport** (test-only) and cover:

- order creation with server prices
- idempotency
- capture exactly once
- ownership and amount-mismatch protection
- high-risk bypass prevention
- reviewer controls
- webhook signature verification and dedupe
- ML metrics and predictions
- graph detection
- agent tools and evidence validation
- RBAC
- audit-chain tamper detection

Frontend: `tsc -b` and `vite build` pass. Full evidence, including what is **not tested**: [docs/TESTING_AND_RESULTS.md](docs/TESTING_AND_RESULTS.md).

## 21. Security

- **Secrets**: environment-only; `.env` is git-ignored; the PayPal secret never reaches the browser; logs redact tokens and secrets.
- **Auth**: bcrypt passwords, JWT with expiry, four roles, step-up re-authentication for decisions.
- **Payments**: server-side pricing, ownership checks, amount verification, idempotency, compare-and-set capture lock, webhook signature verification.
- **Requests**: Pydantic validation, rate limits (Redis or memory), security headers, CORS allow-list.
- **Audit**: SHA-256 hash-chained audit log with tamper detection.
- **Data**: synthetic only; no card or bank data stored.

## 22. Current limitations

- Models are trained and evaluated on **synthetic** data; probabilities are not calibrated.
- **Live PayPal Sandbox checkout, webhooks and the Groq LLM path have not been executed yet** (no credentials on the build machine).
- Docker Compose and Render configurations are written but not run or deployed; there is **no hosted demo URL**.
- Single-process caches (feature state, graph, WebSocket fan-out). The graph cache is rebuilt after each new transaction, so live assessments currently average around 1 s.
- CAPTURE intent means held orders must be decided within PayPal's approval window.
- JWT is stored in `sessionStorage`. There is no MFA, no frontend automated tests and no load testing.

## 23. Future improvements

- Validate on real or public fraud data with out-of-time splits, then calibrate scores and add drift monitoring.
- Community detection (Louvain/Leiden), incremental graph updates and a graph store.
- AUTHORIZE-intent flow (authorise, then capture or void), refunds and disputes.
- Redis pub/sub or a queue for events and investigations; a shared feature store.
- Step-up customer verification for MEDIUM payments; MFA for reviewers; httpOnly cookie sessions.

## 24. Screenshots

All screenshots are real captures of the running app. More are in [SENTINEL_DOCUMENTATION/assets](SENTINEL_DOCUMENTATION/assets).

| Command Centre | Investigation workspace |
|---|---|
| ![Command Centre](SENTINEL_DOCUMENTATION/assets/01_command_centre.jpg) | ![Investigation workspace](SENTINEL_DOCUMENTATION/assets/06_workspace_top.jpg) |
| **Network Graph** | **Fraud Intelligence** |
| ![Network graph](SENTINEL_DOCUMENTATION/assets/04_network_overview.jpg) | ![Fraud Intelligence](SENTINEL_DOCUMENTATION/assets/03_fraud_intelligence.jpg) |
| **Live Transactions (AG Grid)** | **Model Analytics** |
| ![Live transactions](SENTINEL_DOCUMENTATION/assets/02_live_transactions.jpg) | ![Model analytics](SENTINEL_DOCUMENTATION/assets/11_model_analytics.jpg) |

## 25. Documentation

| Document | Purpose |
|---|---|
| [docs/DEVPOST_SUBMISSION.md](docs/DEVPOST_SUBMISSION.md) | Ready-to-paste Devpost fields |
| [docs/SENTINEL_TECHNICAL_ARCHITECTURE.md](docs/SENTINEL_TECHNICAL_ARCHITECTURE.md) | Architecture with Mermaid diagrams |
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | Design rationale and implementation notes |
| [docs/TESTING_AND_RESULTS.md](docs/TESTING_AND_RESULTS.md) | Test evidence |
| [docs/DEMO_VIDEO_SCRIPT.md](docs/DEMO_VIDEO_SCRIPT.md) | 3-minute video script |
| [docs/FINAL_SUBMISSION_CHECKLIST.md](docs/FINAL_SUBMISSION_CHECKLIST.md) | Submission audit |
| [SENTINEL_DOCUMENTATION/](SENTINEL_DOCUMENTATION/) | PDF report set (complete report, technical architecture, quick overview, viva guide) |

## 26. Team

| Name | Role |
|---|---|
| Tanisha Dey | Developer |

## 27. License

[MIT](LICENSE) © 2026 Tanisha Dey
