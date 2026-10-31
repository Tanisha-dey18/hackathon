# SENTINEL — Technical documentation

## 1. Technology choices

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | Typed validation at every boundary, automatic OpenAPI/Swagger, native WebSockets. |
| Persistence | SQLAlchemy 2 + Alembic; PostgreSQL (Docker/Render), SQLite fallback | Real FKs, check constraints, indexes and migrations; SQLite keeps local setup to zero dependencies. |
| Cache / limits | Redis (optional) | Shared rate-limit counters across instances; the app degrades to in-memory limits if Redis is absent so payments never depend on it. |
| ML | scikit-learn, XGBoost, SHAP, pandas/NumPy | Industry-standard tabular fraud stack; SHAP gives per-decision attributions reviewers can check. |
| Graph | NetworkX | Shared-device, cycle and component analysis on a few thousand nodes runs in well under a second; no graph DB to operate. |
| Agent | LangGraph + Groq (tool calling) | Explicit, inspectable state machine; Groq gives fast tool-calling LLM inference on a free tier. |
| Payments | PayPal JS SDK + Orders v2 + Capture + Webhooks (Sandbox) | The product's purpose: risk-gate the capture step of real PayPal orders. |
| UI | React + TypeScript + Vite, Tailwind, Framer Motion, Recharts, React Flow, TanStack Query | Fast iteration, typed data access, live cache invalidation from WebSocket events. |
| Data grid | AG Grid Community | Adds real value on Live Transactions: column filters, multi-sort, quick search across 2,000+ rows, pagination and CSV export. Row grouping is an Enterprise feature, so risk "grouping" is done with risk-level filter chips instead. |

## 2. ML pipeline (`backend/app/ml`)

**Point-in-time features** (`features.py`). A `FeatureState` replays history chronologically; each transaction's
features are computed only from transactions *before* it. The same class is used for training and live scoring,
which removes train/serve skew. 26 features:

- amount, log amount, frequency (1h/24h/7d), hours since previous transaction
- customer historical average, amount ÷ average, z-score vs. normal spending
- merchant risk score, high-risk category, P2P flag
- device usage: accounts per device, new-device-for-customer, devices per customer (30d)
- geography: distance from previous transaction, implied travel speed, distance from home
- failed attempts (24h / 7d)
- network: accounts paying the destination, destination flagged, prior payments to flagged destinations
- hour of day, night flag, first-transaction flag

**Training** (`train.py`):

1. Cleaning: drop unlabeled rows, duplicates and non-positive amounts; clip extreme ratios/speeds.
2. Missing values: kept as NaN (first transactions have no history) and imputed with the training median inside each model pipeline, so imputation statistics never leak from the test set.
3. Split: stratified 75/25 hold-out (`random_state=42`).
4. Imbalance: `class_weight="balanced"` (LR), `balanced_subsample` (RF), `scale_pos_weight = neg/pos` (XGBoost).
5. Models: Logistic Regression (scaled), Random Forest, XGBoost, Isolation Forest (unsupervised, fit without labels).
6. Evaluation on the hold-out set only: precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix, best-F1 threshold, ROC and PR curves.
7. Selection: the **primary** model is the supervised model with the highest **PR-AUC** (accuracy is meaningless at a ~7% positive rate).
8. Persistence: one `joblib` bundle per version + a `model_versions` row per algorithm with its metrics.

Results on the seeded synthetic dataset at the time of writing (500-row hold-out, 36 positives) — the live numbers
are always on the Model Analytics page:

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|
| Random Forest (primary) | 0.941 | 0.889 | 0.914 | 0.939 | 0.897 |
| Logistic Regression | 0.744 | 0.889 | 0.810 | 0.952 | 0.893 |
| XGBoost | 0.914 | 0.889 | 0.901 | 0.951 | 0.886 |
| Isolation Forest | 0.700 | 0.778 | 0.737 | 0.940 | 0.830 |

The synthetic generator deliberately includes "friendly fraud" (fraud that looks normal) and legitimate large
purchases, so metrics are not perfect. They describe performance on synthetic data only.

**Scoring** (`predictor.py`): fraud probability from the primary model, Isolation Forest anomaly score expressed
as a percentile of training anomaly scores, and SHAP values (`TreeExplainer` / `LinearExplainer`) for the primary
model. Positive SHAP contributions are turned into reviewer-readable factors (e.g. "Amount is 43.4x the customer's
historical average"). XGBoost/LR SHAP values are in log-odds space; Random Forest values are in probability space —
the space is returned with every explanation.

**Feedback loop**: retraining (`POST /api/models/retrain`) uses ground-truth labels for synthetic history and
reviewer decisions (REJECT = fraud, APPROVE = legitimate) for live payments.

## 3. Risk policy (`services/risk.py`)

`probability → level`: LOW < 0.30 ≤ MEDIUM < 0.70 ≤ HIGH < 0.90 ≤ CRITICAL (editable by ADMIN, audited).
Escalations can only raise risk:

- Isolation Forest percentile ≥ 0.98 → at least MEDIUM
- amount ≥ 10× customer average → at least MEDIUM
- graph: payment to a flagged destination, a device shared by ≥ 3 accounts, or membership in a circular loop → at least HIGH

Actions: LOW → automatic capture; MEDIUM → held for additional verification; HIGH/CRITICAL → held for review,
with an automatic AI investigation for PayPal and demo payments.

## 4. Graph intelligence (`graph/engine.py`)

Every transaction materialises relationships into `graph_entities` / `graph_relationships`
(`USES_DEVICE`, `MADE_PAYMENT`, `VIA_DEVICE`, `PAID_TO`, `PAID_MERCHANT`, `OWNS_WALLET`). The engine loads these
tables into a NetworkX `DiGraph`, then builds an entity projection that collapses transaction nodes into
aggregated customer↔device / customer↔destination / customer↔merchant edges (with counts, amounts and transaction IDs).

Detections:

- **Shared devices**: device nodes linked to ≥ 3 customers.
- **Circular payments**: a customer→customer money-flow digraph (payer → owner of the wallet paid) searched with `nx.simple_cycles(length_bound=6)`.
- **Clusters**: connected components over customers, devices and wallets (merchant hubs excluded so everyone isn't connected), flagged as suspicious when they contain shared devices, flagged destinations, cycles or high mean model risk.
- **Flagged destination interactions**: all accounts and payments reaching flagged wallets.

Explorer views (`/api/graph/transaction/{id}`, `/api/graph/entity/{id}`, `/api/graph/overview`) expand two hops
(never through merchant hubs), lay out each component with Kamada-Kawai, and attach evidence strings and transaction
IDs to suspicious edges. The engine is cached and rebuilt whenever relationships change.

## 5. AI investigation agent (`agent/`)

A LangGraph `StateGraph` with nodes:
`retrieve_transaction → customer_behaviour → ml_prediction → graph_investigation → merchant_risk → collect_evidence → analyse → generate_report → route_to_reviewer`.

Tools: `TransactionHistoryTool`, `CustomerBehaviourTool`, `FraudPredictionTool`, `GraphInvestigationTool`,
`MerchantRiskTool`, `EvidenceCollectionTool`, `InvestigationReportTool`. Each reads real database records.

Guarantees against fabrication:

1. **Evidence is derived deterministically** from tool outputs by `EvidenceCollectionTool` and keyed `E1…En` (including mitigating evidence).
2. In **LLM mode**, Groq receives only the case file (transaction + evidence) and may call tools for related entities; their outputs become new evidence keys. It must finish with a structured `submit_investigation_report` tool call.
3. `InvestigationReportTool` **drops every finding that does not cite a valid evidence key**, normalises the recommendation to one of `APPROVE | HOLD_FOR_REVIEW | REJECT | ESCALATE`, and refuses a report with no supported findings (falling back to the rule engine).
4. If Groq is not configured or fails, a rule-based report is produced and labelled `DETERMINISTIC_FALLBACK` with the reason.
5. The agent has no payment tools. It can only route a recommendation to the review queue.

Each step is persisted (`investigations.steps`) and broadcast over WebSocket so the workspace shows progress live.

## 6. PayPal integration (`paypal/client.py`, `services/payments.py`)

- OAuth2 client-credentials token, cached until expiry; secrets only on the server.
- `POST /v2/checkout/orders` with `intent=CAPTURE`, server-computed item breakdown, `reference_id/custom_id` = Sentinel transaction ID, and `PayPal-Request-Id` derived from the client's `Idempotency-Key`.
- On approval: `GET /v2/checkout/orders/{id}` → must be `APPROVED`, amount/currency and reference must match the stored order, and the caller must own the order.
- Capture: `POST /v2/checkout/orders/{id}/capture` with a stable `PayPal-Request-Id = capture-{order_id}`.
- Webhooks: verified with `POST /v1/notifications/verify-webhook-signature` using `PAYPAL_WEBHOOK_ID`; de-duplicated by event ID; `PAYMENT.CAPTURE.*` and `CHECKOUT.ORDER.APPROVED` update state.
- Every PayPal response (including errors with `paypal-debug-id`) is stored in `payment_events`.

## 7. Payment state management

Two independent state fields on `paypal_orders`:

- `paypal_status` — only ever written from PayPal API/webhook responses (`CREATED`, `APPROVED`, `COMPLETED`, …), plus `capture_status`/`capture_id` from the capture object.
- `sentinel_status` — Sentinel's decision: `AWAITING_BUYER_APPROVAL → CLEARED | HELD_FOR_VERIFICATION | HELD_FOR_REVIEW → ESCALATED → APPROVED_AUTO | APPROVED_BY_REVIEWER | REJECTED | CAPTURE_FAILED`.

A held order shows `paypal_status=APPROVED` and no capture — it is never presented as paid.

**Exactly-once capture**: `capture_state` moves `NONE/FAILED → IN_PROGRESS` with a compare-and-set `UPDATE … WHERE capture_state IN (…)`; only the request that wins the update calls PayPal. Combined with the stable `PayPal-Request-Id` and `ORDER_ALREADY_CAPTURED` reconciliation, retries and double clicks never double-capture.

**No bypass**: `execute_capture` re-checks authorisation itself: `AUTO_POLICY` requires the latest assessment to be LOW; `REVIEWER` requires a stored APPROVE decision. Tests assert both.

## 8. Security decisions

- bcrypt password hashing, short-lived HS256 JWTs, role-based dependencies (ADMIN, REVIEWER, ANALYST, CUSTOMER).
- Reviewer decisions require password re-authentication, typed transaction-ID confirmation and a justification (≥ 20 chars to approve HIGH/CRITICAL); escalated cases require ADMIN.
- Server-side pricing; ownership checks on every order endpoint; Pydantic validation with strict patterns for IDs.
- Rate limiting (Redis or in-memory) with tighter limits on login, order creation and capture.
- Secrets from environment only; `.env` is git-ignored; a logging filter redacts bearer tokens and client secrets.
- Security headers (`nosniff`, `DENY` framing, `no-referrer`); generic 500 responses.
- Append-only audit trail with SHA-256 hash chaining (`/api/audit/verify` detects modified or deleted rows).
- No card numbers or payment credentials are stored; PayPal handles all payment instruments. Device "fingerprints" are random per-browser identifiers.

## 9. Current limitations

- Models are trained and evaluated on **synthetic** data; real deployment would need real labelled data, calibration and drift monitoring.
- Probabilities from class-weighted models are risk scores, not calibrated probabilities.
- CAPTURE-intent orders held for review must be decided within PayPal's approval window; an AUTHORIZE-intent flow (authorise, then capture/void) would hold funds longer and allow explicit voiding on reject.
- Webhooks require a public HTTPS URL (Render or a tunnel) and `PAYPAL_WEBHOOK_ID`.
- Device context is a browser-generated identifier; demo scenarios set it explicitly. Geolocation for checkout defaults to the customer's home city (or a demo-provided value) rather than IP geolocation.
- WebSocket fan-out and the feature/graph caches are per process; horizontal scaling would need Redis pub/sub and a shared feature store.
- Historical transactions are scored in-sample at seed time (honest model quality is the hold-out metrics).
- The LLM path is implemented against Groq's OpenAI-compatible tool-calling API but was not exercised in this build environment without a key; the deterministic fallback is fully tested.
