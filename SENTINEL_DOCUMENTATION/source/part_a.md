# PART 1: Executive Overview

## 1.1 What is Sentinel?

Sentinel is a payment protection layer that sits between a customer approving a payment in PayPal and the moment the merchant actually collects the money. It looks at each payment, decides how risky it is, explains why, and only lets PayPal collect the funds when that is safe or when a human reviewer has approved it.

The project has two faces:

- **SENTINEL MERCHANT**: a demo online shop where a shopper picks products and pays with PayPal (Sandbox).
- **The Sentinel console**: a dashboard used by risk analysts and reviewers to watch transactions, see why something was flagged, explore relationships between accounts, run an AI investigation and approve or reject held payments.

> In one sentence: Sentinel decides, with evidence, whether money should move, and keeps a human in charge of the decisions that cannot be undone.

## 1.2 Why was Sentinel created?

Online payments are fast, and fraud is fast too. Many fraud checks look at one payment at a time and return a score with no explanation. That leaves two problems. First, organised fraud is often invisible at the level of a single payment: ten accounts that share one phone and send money to the same wallet each look normal on their own. Second, when a payment is flagged, someone still has to work out why, which takes time while the customer waits.

Sentinel was built for the PayPal AI Hackathon 2026 to show how payment infrastructure, machine learning, graph analysis and an AI investigator can work together in one coherent workflow.

## 1.3 What problem does it solve?

Inside this prototype, Sentinel solves a specific, well-defined problem: *"Before PayPal captures an approved payment, decide whether it is safe to capture, explain the decision, and make sure risky payments cannot be captured without an authenticated human approval."*

## 1.4 Who would benefit?

| Who | Benefit |
|---|---|
| Merchants | Fewer fraudulent captures and the chargebacks that follow; fewer genuine customers wrongly declined, because flagged payments are reviewed rather than auto-rejected. |
| Risk reviewers and analysts | A ready-made case file: transaction details, customer history, model explanation, relationship graph and an evidence-cited recommendation. |
| Genuine customers | Normal purchases go through automatically; unusual ones are checked by a person instead of being silently blocked. |
| Engineering and compliance teams | Every decision is recorded in a tamper-evident audit log. |

## 1.5 How does it work? (simple version)

1. A shopper adds items to the cart and clicks the PayPal button.
2. Sentinel's server creates a real PayPal order with prices taken from its own catalogue.
3. The shopper approves the payment in the PayPal window.
4. Before any money is collected, Sentinel asks PayPal for the order, checks the amount and that it belongs to this shopper, and then scores the risk.
5. Low-risk payments are captured automatically. Anything else is **held**, which means PayPal has the buyer's approval but no money has been collected.
6. For high-risk payments an AI investigator collects evidence and writes a report with a recommendation.
7. A reviewer signs in again, reads the evidence and approves, rejects or escalates. Only an approval can trigger the PayPal capture.

## 1.6 What makes it different?

- **Risk is enforced at the exact point where money moves.** The capture step itself checks that the payment was either LOW risk or approved by a reviewer.
- **Three kinds of intelligence, one decision.** A supervised ML model, an unsupervised anomaly detector and a relationship graph each contribute, and the policy explains which one raised the risk.
- **An AI investigator that cannot make things up.** Every finding in its report must cite an evidence item produced by a tool; anything else is removed automatically.
- **A clear separation of truth.** PayPal's payment status is only ever copied from PayPal. Sentinel's risk decision is stored separately, so a held payment is never shown as paid.

## 1.7 Why PayPal integration is important

Without a real payment system, a fraud model is just a classifier. With PayPal, Sentinel controls a real lifecycle: order creation, buyer approval and capture. The risk decision has a concrete consequence (capture or do not capture), and PayPal's own idempotency and webhook signature verification are part of the safety design.

## 1.8 Where AI fits

| AI component | What it does in Sentinel |
|---|---|
| Machine learning (Random Forest, XGBoost, Logistic Regression) | Estimates the probability that a payment is fraudulent from 26 behavioural features. |
| Anomaly detection (Isolation Forest) | Measures how unusual a payment is compared with all training payments, without using labels. |
| Explainable AI (SHAP) | Shows which features pushed the score up or down for each individual payment. |
| Graph intelligence (NetworkX) | Finds shared devices, money loops and clusters of linked accounts. |
| Agentic AI (LangGraph + Groq) | Runs a multi-step investigation with tools and writes an evidence-backed report. A rule-based fallback is used, and labelled, when Groq is not configured. |

## 1.9 The one-minute explanation

> "Sentinel protects PayPal checkouts. When a shopper pays, our server creates a real PayPal Sandbox order. After the shopper approves it, and before we capture any money, Sentinel scores the payment with a machine-learning model, checks how unusual it is, and looks at a graph of which accounts share devices or send money to the same wallets. Normal payments are captured straight away. Suspicious ones are held: PayPal shows the order as approved, but nothing is collected. An AI agent then gathers evidence with seven tools and writes a report where every claim points to a piece of evidence. A reviewer re-enters their password and approves, rejects or escalates, and only an approval lets PayPal capture the money. Everything is recorded in a hash-chained audit log. It all runs on synthetic data and PayPal Sandbox, so no real customers or money are involved."

# PART 2: Problem Statement

## 2.1 The broader problem

Digital payments keep growing, and so does the attack surface. The patterns below are widely discussed in the payments industry; they are described here as general context, not as statistics measured by this project.

- **Suspicious payment behaviour**: purchases far above a customer's normal spending, at unusual hours, or in quick bursts.
- **Account takeover (ATO)**: a criminal logs into a real customer's account from a new device, often from a far-away location, and buys high-value, resellable goods.
- **Card testing**: many tiny failed payments to check which stolen details work, followed by a large purchase.
- **Coordinated fraud networks**: many accounts controlled by the same group share devices and move money to the same "mule" destinations, or pass money around in circles.
- **Rule-based limits**: fixed rules (for example "block anything above $1,000") are easy to explain but easy to evade, and they block many genuine customers.
- **False positives**: every genuine customer wrongly declined is lost revenue and a damaged relationship.
- **Detection is not enough**: a score with no explanation still leaves an analyst to rebuild the story by hand.
- **Explainability matters**: payment decisions affect real people; reviewers, auditors and customers need to understand why a payment was held.

## 2.2 A realistic hypothetical example

Cara's account has a short purchase history. On a Tuesday afternoon she buys a $500 digital gift card. On its own that is not alarming: the amount is about 1.5 times her average, and she has used this phone before. But that phone is also used by three other accounts, and those accounts have repeatedly sent money to two external wallets that are known to have received funds linked to chargebacks. A model that only looks at Cara's payment sees an ordinary purchase. A system that looks at the relationships sees a likely fraud ring. This exact situation is reproduced as Demo Scenario C (Part 14), where the ML model scored the payment at about 0.33 but the graph policy raised it to HIGH.

## 2.3 Industry challenges versus what this prototype solves

| General industry challenge | What Sentinel's prototype actually does |
|---|---|
| Fraud at very large scale | Not addressed. The prototype processes a few thousand synthetic transactions in one process. |
| Individual anomalous payments | Addressed: ML score, anomaly percentile, amount-versus-average escalation, SHAP explanation. |
| Coordinated networks | Addressed for shared devices, flagged destinations, circular wallet transfers and linked clusters on synthetic data. |
| Unexplained decisions | Addressed: SHAP factors, policy notes and evidence-cited reports. |
| Money moving before review | Addressed: capture is gated and protected against bypass and duplication. |
| Real-world model accuracy | Not demonstrated. Models are trained and evaluated on synthetic data only. |

## 2.4 Formal problem statement

> Given a PayPal order that a buyer has approved but that has not yet been captured, determine (a) whether the order is authentic and belongs to the requesting customer, (b) the risk that the payment is fraudulent, using the customer's history, the payment's context and the customer's relationships to other accounts, devices and destinations, and (c) whether the order may be captured automatically or must be held for an authenticated human decision, while producing an explanation and an auditable record for every step, and guaranteeing that a held order can never be captured without approval and that no order is captured twice.

# PART 3: Project Objectives

## 3.1 Primary objectives

| Objective | How it is met in the code | Why it matters |
|---|---|---|
| Detect suspicious transactions | Every transaction is scored by the primary ML model, the Isolation Forest and graph signals (`services/risk.py`). | Catches risky payments before money moves. |
| Estimate transaction risk | Fraud probability is mapped to LOW / MEDIUM / HIGH / CRITICAL by configurable thresholds, with escalation rules. | Lets the business choose how cautious to be. |
| Identify suspicious financial relationships | NetworkX graph over stored relationships detects shared devices, cycles, flagged destinations and suspicious clusters (`graph/engine.py`). | Organised fraud is invisible one payment at a time. |
| Investigate suspicious activity using AI | LangGraph workflow with seven tools; Groq LLM when configured, labelled rule-based fallback otherwise (`agent/`). | Saves analyst time and produces a consistent case file. |
| Integrate payment protection with PayPal Sandbox | Orders v2 create, get and capture; webhook verification; idempotency (`paypal/client.py`, `services/payments.py`). | Makes the risk decision consequential. |
| Provide explainable recommendations | SHAP top factors, policy notes, evidence keys E1...En in reports. | Reviewers and auditors can verify every claim. |
| Maintain a complete audit trail | SHA-256 hash-chained `audit_logs` table with a verification endpoint (`audit.py`). | Proves what happened and detects tampering. |

## 3.2 Secondary objectives

- Real-time visibility: WebSocket event stream that refreshes the console.
- Role-based operation: ADMIN, REVIEWER, ANALYST and CUSTOMER roles.
- Reproducible demos: three scenarios that can be launched from the console.
- Honest evaluation: hold-out metrics only, primary model chosen by PR-AUC.
- Deployability: Docker Compose, Render Blueprint, Alembic migrations.

# PART 4: Proposed Solution

## 4.1 The customer journey, step by step

1. **Customer selects a product.** The storefront lists 16 synthetic products from synthetic sellers. A cart can only contain items from one seller, because each checkout pays one merchant.
2. **Customer initiates PayPal Checkout.** The PayPal JavaScript SDK renders the PayPal button. Clicking it calls Sentinel's `POST /api/paypal/create-order` with the cart, a device identifier and an `Idempotency-Key`.
3. **Backend creates a PayPal order.** The server recalculates prices from its own catalogue, creates a Sentinel transaction with status `AWAITING_APPROVAL`, and calls PayPal `POST /v2/checkout/orders` with `intent = CAPTURE`. The PayPal order ID is returned to the browser.
4. **Customer approves in PayPal.** The buyer logs in to a PayPal Sandbox personal account and approves. No money has moved yet.
5. **Sentinel assesses risk before capture.** The browser calls `POST /api/paypal/capture-order`. The server fetches the order from PayPal, checks it is `APPROVED`, that amount, currency and reference match, and that the caller owns it.
6. **ML models analyse the transaction.** 26 point-in-time features are computed and scored by the primary model; the Isolation Forest gives an anomaly percentile; SHAP explains the score.
7. **Graph intelligence examines relationships.** The customer, device and destination are checked for shared-device rings, flagged destinations, circular loops and suspicious clusters.
8. **The AI agent investigates.** For HIGH and CRITICAL payments (by default) an investigation starts automatically in the background.
9. **A human reviewer examines the evidence.** The reviewer approves, rejects or escalates after re-entering their password and typing the transaction ID.
10. **Payment is captured or not.** LOW risk is captured automatically. An APPROVE decision triggers the capture. REJECT leaves the PayPal order uncaptured.
11. **Everything is recorded.** PayPal responses go to `payment_events`, decisions to `reviewer_decisions`, and every action to the hash-chained `audit_logs`.

## 4.2 Normal, medium-risk and high-risk scenarios

| Scenario | Policy outcome | PayPal outcome | Human involvement |
|---|---|---|---|
| Normal (LOW) | `CLEARED`, then capture | Capture called with a stable `PayPal-Request-Id`; status `COMPLETED` comes from PayPal | None |
| Medium | `HELD_FOR_VERIFICATION` | Order stays `APPROVED`; nothing captured | Reviewer verifies and decides |
| High / Critical | `HELD_FOR_REVIEW`, AI investigation started | Order stays `APPROVED`; nothing captured | Reviewer decides; escalated cases need an ADMIN |

> Important: a held payment is not a failed payment. The buyer has approved it in PayPal, but Sentinel has not asked PayPal to collect the money. The interface shows PayPal status and Sentinel status side by side so this is never confused.

# PART 5: System Architecture

## 5.1 High-level architecture

[[DIAGRAM:architecture]]

The system has three tiers. The **browser** runs a single React application with two areas: the SENTINEL MERCHANT storefront (shoppers) and the console (staff). The **FastAPI backend** exposes REST endpoints and one WebSocket, and contains the payment gateway, risk engine, ML predictor, graph engine, investigation agent and audit log. The **external services** are PayPal Sandbox (always used for real payments), Groq (optional, for the LLM agent), the database (PostgreSQL in Docker/Render, SQLite locally) and Redis (optional, for shared rate limiting).

Data flow in one sentence: the browser calls the API; the API stores state in the database, talks to PayPal for every payment operation, calls the risk engine (which uses the ML model and the graph), starts the agent for high-risk payments, records every step in the audit log, and pushes events back to the console over the WebSocket.

## 5.2 Frontend architecture

- **Routing** (`react-router-dom`): `/shop/*` for the storefront, `/console/*` for the console, `/login`.
- **State and data**: TanStack Query caches every API call. The `LiveProvider` opens one authenticated WebSocket and invalidates the relevant queries when events arrive, so every screen updates without manual refresh.
- **Auth**: `AuthProvider` stores the JWT in `sessionStorage` and exposes the current user and role. Console routes require a staff role.
- **Visualisation**: Recharts (dashboard and model charts), React Flow (relationship graph), AG Grid Community (transactions table), Framer Motion (transitions).
- **Payments**: `@paypal/react-paypal-js` renders PayPal Buttons using the public client ID returned by `GET /api/paypal/config`. The secret never reaches the browser.

## 5.3 Backend architecture

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI app, lifespan (migrations, first-run seeding and training, model artifact recovery), CORS, security headers, WebSocket. |
| `routers/` | `auth`, `transactions` (transactions, risk, reviews), `intel` (investigations, graph), `paypal` (checkout, webhook, storefront), `ops` (dashboard, audit, models, settings, demos). |
| `services/payments.py` | PayPal order lifecycle, capture state machine, webhook handling. |
| `services/risk.py` | Feature state, scoring, policy thresholds and escalations. |
| `services/review.py` | Reviewer decisions with re-authentication and RBAC. |
| `services/transactions.py` | Transaction creation and risk routing. |
| `ml/` | Feature engineering, training, SHAP explanation, prediction. |
| `graph/engine.py` | Graph persistence, NetworkX analysis, explorer views. |
| `agent/` | Seven investigation tools and the LangGraph workflow. |
| `audit.py` | Hash-chained audit log and chain verification. |
| `infra.py` | Rate limiter (Redis or memory) and WebSocket broadcaster. |

## 5.4 Payment processing sequence

[[DIAGRAM:sequence]]

The sequence shows the two independent approvals in the lifecycle: the buyer's approval in PayPal, and Sentinel's risk approval. The capture call to PayPal only happens if both exist. If the risk policy holds the payment, the reviewer's APPROVE decision replaces the automatic approval, and the same capture function is used, with the same protections.

## 5.5 Real-time communication

`ws://<host>/ws/transactions?token=<JWT>` accepts staff tokens only. The backend broadcasts `transaction.created`, `transaction.assessed`, `transaction.updated`, `payment.updated`, `investigation.step`, `investigation.completed` and `decision.made`. Because many events come from background threads (the agent, the simulator), the broadcaster uses `asyncio.run_coroutine_threadsafe` with the server's event loop.

## 5.6 Deployment architecture

[[DIAGRAM:deployment]]

Three supported ways to run Sentinel:

| Mode | Components | Status |
|---|---|---|
| Local | Uvicorn + Vite dev server, SQLite, in-memory rate limiting | Run and verified during development |
| Docker Compose | PostgreSQL 16, Redis 7, backend container, nginx serving the built frontend and proxying `/api` and `/ws` | Configuration written; not run during development because Docker was not running on the build machine |
| Render Blueprint | Managed PostgreSQL, Docker web service for the API, static site for the frontend | Configuration written; not deployed |

On hosts with ephemeral disks, the backend retrains automatically at start-up if the active model file is missing.

# PART 6: Technology Stack Explained

## 6.1 Frontend

| Technology | What it is | Why chosen / problem solved | Where used | Talks to |
|---|---|---|---|---|
| React 18 | UI component library | Component model for two applications in one bundle | All screens | TanStack Query, router |
| TypeScript 5.8 | Typed JavaScript | Catches API shape mistakes at build time | Entire frontend | Compiler only |
| Vite 6 | Build tool and dev server | Fast reloads; dev proxy for `/api` and `/ws` | Build and dev | Proxies to FastAPI |
| Tailwind CSS 3.4 | Utility CSS framework | Consistent dark fintech design tokens | All styling | Build step |
| Framer Motion 12 | Animation library | Smooth panel and list transitions | Cards, modals, feeds | React |
| Recharts 2 | Chart library | Area, bar, line, pie, ROC/PR and SHAP charts | Command Centre, Fraud Intelligence, Model Analytics | API data via TanStack Query |
| React Flow (@xyflow/react 12) | Interactive node graph | Pan, zoom, hover and click on relationship graphs | Network Graph, Investigation workspace | `/api/graph/*` |
| AG Grid Community 33 | Data grid | Filtering, sorting, quick search, pagination and CSV export over 2,000+ rows | Live Transactions | `/api/transactions` |
| TanStack Query 5 | Server-state cache | Caching, polling, invalidation from WebSocket events | All data access | REST API |
| Lucide React | Icon set | Consistent icons | Everywhere | n/a |
| PayPal React SDK (@paypal/react-paypal-js 8) | Wrapper for PayPal JS SDK | Renders PayPal Buttons, handles approval popup | Checkout | PayPal + Sentinel API |

AG Grid was evaluated as the brief asked: it adds real value for filtering and searching thousands of rows. Row grouping is an Enterprise feature, so risk "grouping" is done with filter chips instead.

## 6.2 Backend, data and infrastructure

| Technology | What it is | Why chosen / problem solved | Where used |
|---|---|---|---|
| Python 3.13 | Language | Same language for API, ML and graph code | Backend |
| FastAPI 0.115 | Async web framework | Typed endpoints, automatic OpenAPI/Swagger, native WebSockets | `main.py`, `routers/` |
| Pydantic 2 / pydantic-settings | Validation and settings | Strict request validation; secrets loaded from environment | Request models, `config.py` |
| SQLAlchemy 2 | ORM | One model layer for PostgreSQL and SQLite; atomic compare-and-set updates | `models.py`, services |
| Alembic 1.15 | Migrations | Versioned schema changes | `alembic/versions/0001_initial_schema.py` |
| PostgreSQL 16 | Relational database | Production database in Docker/Render | `docker-compose.yml`, `render.yaml` |
| SQLite | Embedded database | Zero-setup local development | Default `DATABASE_URL` |
| Redis 7 (optional) | In-memory store | Shared rate-limit counters across instances; falls back to memory if absent | `infra.py` |
| httpx | HTTP client | PayPal REST calls; injectable transport for tests | `paypal/client.py` |
| PyJWT, bcrypt | Auth libraries | Signed tokens, salted password hashing | `security.py` |
| Docker, Docker Compose | Containers | Reproducible multi-service environment | `Dockerfile`s, compose |
| Render | Cloud platform | Blueprint deployment of DB, API and static site | `render.yaml` |
| WebSockets (FastAPI/Starlette) | Push channel | Live console updates | `/ws/transactions` |

## 6.3 Machine learning, graph and AI

| Technology | Where used | Role |
|---|---|---|
| pandas 3, NumPy 2 | `ml/train.py`, `ml/predictor.py` | Feature tables, metrics computation |
| scikit-learn 1.9 | `ml/train.py` | Logistic Regression, Random Forest, Isolation Forest, imputation, scaling, metrics, stratified split |
| XGBoost 3.4 | `ml/train.py` | Gradient-boosted tree classifier |
| SHAP 0.54 | `ml/explain.py` | TreeExplainer / LinearExplainer attributions per prediction and globally |
| joblib | `ml/train.py` | Model bundle persistence |
| NetworkX 3.7 | `graph/engine.py` | Graph construction, connected components, `simple_cycles`, Kamada-Kawai layout |
| LangGraph 1.2 | `agent/workflow.py` | State-machine orchestration of the investigation |
| Groq SDK 1.7 | `agent/workflow.py` | LLM tool calling (default model `llama-3.3-70b-versatile`, configurable) |

## 6.4 Payment

| Component | Where used |
|---|---|
| PayPal JavaScript SDK (Buttons) | `frontend/src/pages/shop/Checkout.tsx` |
| OAuth 2.0 client credentials | `PayPalClient._access_token()` |
| Orders API v2: create, get, capture | `PayPalClient.create_order / get_order / capture_order` |
| Webhook signature verification API | `PayPalClient.verify_webhook()` |
| PayPal Sandbox | Default `PAYPAL_BASE_URL = https://api-m.sandbox.paypal.com` |
