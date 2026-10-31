# Testing and Results

Every result below was produced on the development machine (Windows 11, Python 3.13, Node 24) on 31 October 2026. Items that could not be run are marked **NOT TESTED** with the reason. No metric or result here is estimated.

## 1. Summary

| Area | Status | Evidence |
|---|---|---|
| Backend automated tests | **PASS** (24/24) | `pytest -v`, section 2 |
| Frontend type check | **PASS** | `tsc -b` |
| Frontend production build | **PASS** | `vite build` (built in 34 s) |
| Live API smoke tests | **PASS** | section 3 |
| ML evaluation | **DONE** | hold-out metrics, section 4 |
| Risk scoring scenarios A/B/C | **PASS** | section 5 |
| Graph detection | **PASS** | section 6 |
| AI agent tool execution (fallback mode) | **PASS** | section 7 |
| AI agent with Groq LLM | **NOT TESTED** | No `GROQ_API_KEY` available |
| PayPal flow against mock transport | **PASS** | tests in section 2 |
| PayPal flow against live Sandbox | **NOT TESTED** | Sandbox credentials were not present on the build machine |
| PayPal webhooks (live) | **NOT TESTED** | Needs a public URL and `PAYPAL_WEBHOOK_ID` |
| Docker Compose / PostgreSQL runtime | **NOT TESTED** | Docker daemon not running; PostgreSQL DDL generation only (section 8) |
| Render deployment | **NOT TESTED** | Not deployed |
| Frontend automated tests | **NOT TESTED** | None written; manual checks in section 9 |
| Load / performance testing | **NOT TESTED** | Out of scope for the prototype |

## 2. Backend automated tests

Command: `backend\.venv\Scripts\python -m pytest -v backend\tests`
Result: **24 passed, 0 failed** (34.7 s in the latest run, which includes seeding and training a fresh test database).

The tests use an isolated SQLite database and an `httpx.MockTransport` test double that emulates PayPal Sandbox (OAuth, Orders v2 create/get/capture with `PayPal-Request-Id` idempotency, `ORDER_ALREADY_CAPTURED`, webhook signature verification). The application never uses the mock.

| Test | What it proves | Result |
|---|---|---|
| test_models_trained_with_honest_metrics | 4 models trained; metrics in [0,1]; confusion matrix sums to test size; primary has best PR-AUC | PASSED |
| test_ml_prediction_structure | Probability and anomaly in [0,1]; SHAP for all 26 features; missing values kept as null | PASSED |
| test_risk_classification_policy | Threshold mapping; escalation never lowers risk | PASSED |
| test_transaction_creation_and_assessment | 401 without auth, 403 for shopper; risk payload; audit entry; 422 for negative amount | PASSED |
| test_anomalous_amount_escalates | Demo B is held at MEDIUM or higher | PASSED |
| test_graph_detects_fraud_structures | Shared device, 4-account cycle, both mule wallets; clean customer has no signals | PASSED |
| test_incremental_graph_matches_full_rebuild | In-place graph updates equal a full rebuild | PASSED |
| test_agent_tools_return_real_records | Tools read real records; invented and uncited findings removed | PASSED |
| test_investigation_workflow_deterministic_fallback | All 7 tools run; fallback labelled; findings cite real keys; no money moved | PASSED |
| test_rbac_and_auth | Role rules; forged token rejected | PASSED |
| test_audit_chain_detects_tampering | Modified row detected at the correct ID | PASSED |
| test_investigations_persisted | Evidence stored; "recommendation only" notice present | PASSED |
| test_create_order_uses_server_side_prices | PayPal status CREATED; server price used | PASSED |
| test_create_order_idempotency_key_replays | Same key gives the same order; no second PayPal order | PASSED |
| test_cart_validation | Unknown product, mixed sellers, quantity 99 rejected | PASSED |
| test_staff_cannot_create_checkout | 403 | PASSED |
| test_capture_requires_buyer_approval | 409 when not approved | PASSED |
| test_low_risk_payment_is_captured_once | Captured; replays never call PayPal capture again (exactly 1 call) | PASSED |
| test_payment_ownership_enforced | Other shopper gets 403 | PASSED |
| test_amount_mismatch_blocks_capture | 409; no capture | PASSED |
| test_high_risk_payment_cannot_bypass_review | Held, not captured, investigation started; direct capture refused | PASSED |
| test_reviewer_decision_controls | Wrong password 401, wrong confirmation 422, short reason 422, escalation needs ADMIN, approve captures once | PASSED |
| test_reject_decision_never_captures | PayPal order stays APPROVED, uncaptured | PASSED |
| test_webhook_signature_verification_and_dedupe | Forged/missing signature 400; duplicate ignored | PASSED |

## 3. Live API smoke tests (running backend, no PayPal or Groq keys)

| Check | Expected | Actual |
|---|---|---|
| `GET /api/health` | ok | `{"status":"ok","paypal_configured":false,"groq_configured":false}` |
| `GET /api/paypal/config` | not configured, sandbox | `configured: false, environment: sandbox` |
| `GET /api/transactions` without token | 401 | 401 |
| Login with wrong password | 401 | 401 |
| Login with invalid email body | 422 | 422 |
| Shopper token on `/api/dashboard/metrics` | 403 | 403 |
| `POST /api/paypal/create-order` without PayPal keys | 503, no fake order | 503 "PayPal Sandbox is not configured on the server" |
| `POST /api/paypal/webhook` without webhook ID | 503 | 503 "PAYPAL_WEBHOOK_ID is not set; webhooks cannot be verified" |
| `GET /api/audit/verify` | valid chain | `{"valid":true,"checked":36,"broken_at_id":null}` |

## 4. ML evaluation (model v1, synthetic data)

1,500 training rows and 500 hold-out rows (36 frauds). Threshold 0.5 for supervised models; contamination threshold for Isolation Forest.

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC | TN / FP / FN / TP |
|---|---|---|---|---|---|---|
| Random Forest (primary) | 0.941 | 0.889 | 0.914 | 0.939 | 0.897 | 462 / 2 / 4 / 32 |
| Logistic Regression | 0.744 | 0.889 | 0.810 | 0.952 | 0.893 | 453 / 11 / 4 / 32 |
| XGBoost | 0.914 | 0.889 | 0.901 | 0.951 | 0.886 | 461 / 3 / 4 / 32 |
| Isolation Forest | 0.700 | 0.778 | 0.737 | 0.940 | 0.830 | 452 / 12 / 8 / 28 |

These describe the synthetic data generated by the project. They are not evidence of real-world accuracy.

## 5. Risk scoring scenarios

**On a freshly seeded database** (the values used in the documentation):

| Scenario | ML score | Anomaly pct | Final level | Status | Escalation note |
|---|---|---|---|---|---|
| A: Ava, $76, known device | 0.006 | not recorded | LOW | CLEARED | none |
| B: Ben, $1,849, new device | 0.098 | 0.955 | MEDIUM | HELD_FOR_VERIFICATION | Amount is 43.4x customer average |
| C: Cara, $500 gift card, shared emulator | 0.313 | 0.950 | HIGH | HELD_FOR_REVIEW | Device shared by 4 accounts, so at least HIGH |

**Repeat run on the same database** (after several earlier demo runs):

| Scenario | ML score | Anomaly pct | Level | Status |
|---|---|---|---|---|
| A | 0.072 | 0.251 | LOW | CLEARED |
| B | 0.237 | 0.949 | MEDIUM ("Amount is 14.4x customer average") | HELD_FOR_VERIFICATION |
| C | 0.280 | 0.948 | HIGH (graph policy) | HELD_FOR_REVIEW, investigation started |

The levels and decisions were the same on both runs, but the scores moved. Every demo run adds to the customer's history: Ben's earlier $1,849 purchase raised his average, so the ratio dropped from 43.4x to 14.4x. **Reset the database before recording a demo** (see the README).

## 6. Graph detection

From `GET /api/graph/overview`: 2,330 entities and 8,127 relationships (seed data plus demo transactions); 2 shared devices; 1 cycle; 8 clusters, 4 suspicious; 2 flagged destinations.

| Finding | Detail |
|---|---|
| DEV_0147 | Shared by CUS_0003, CUS_0091, CUS_0093, CUS_0097 |
| DEV_0148 | Shared by CUS_0090, CUS_0094, CUS_0096 |
| Cycle | CUS_0081 → 0082 → 0083 → 0080, $16,064.37 |
| DST_MULE_01 / DST_MULE_02 | 16 payments, $11,238.59, 7 accounts / 18 payments, $9,831.23, 9 accounts |

## 7. AI agent tool execution (deterministic fallback)

A recorded run on Demo C (investigation INV_56SIO2YBF0):

| Step | Tool | Duration | Output |
|---|---|---|---|
| Retrieve transaction | TransactionHistoryTool | 28.9 ms | 9 transactions on record |
| Customer behaviour | CustomerBehaviourTool | 12.7 ms | average $349.12, 2 devices |
| ML prediction | FraudPredictionTool | 11.5 ms | 0.313, anomaly 0.950 |
| Graph | GraphInvestigationTool | 706.8 ms | shared device, flagged destination, cluster #1 |
| Merchant | MerchantRiskTool | 12.3 ms | VaultGift Digital, risk 0.72 |
| Evidence | EvidenceCollectionTool | 6.1 ms | 9 items, 4 high severity |
| Analysis | RuleEngine (fallback) | 5.1 ms | Groq not configured |
| Report | InvestigationReportTool | 19.3 ms | REJECT, 6 evidence-backed findings |
| Route | ReviewQueue | 12.1 ms | sent to reviewer queue |

The reviewer then rejected the transaction through the UI with re-authentication and typed confirmation; the decision and its audit entries were recorded.

## 8. Database operations

- Alembic migration `0001_initial_schema` applied to SQLite on every start and in the test suite.
- `alembic upgrade head --sql` with a PostgreSQL URL generated DDL for 18 tables plus `alembic_version`, without errors. This was **not executed against a running PostgreSQL server**.
- Constraint behaviour (unique idempotency key, capture lock, amount checks) is covered by the payment tests.

## 9. Frontend functional checks (manual, in a browser)

| Screen | Checked |
|---|---|
| Login, role redirect | Yes |
| Storefront catalogue, product, cart, single-seller rule | Yes |
| Checkout without PayPal keys shows setup message (no fake payment) | Yes |
| Command Centre KPIs, charts, demo launcher, live event stream | Yes |
| Live Transactions (AG Grid): filter chips, search, pagination, row click | Yes |
| Fraud Intelligence: queue, SHAP chart, decision buttons | Yes |
| Network Graph: overview, entity search, inspector | Yes |
| Investigation workspace: INVESTIGATE, live steps, report, evidence timeline | Yes |
| Reviewer decision modal (re-auth + confirm) | Yes, REJECT exercised |
| PayPal Payments, Model Analytics, Audit (verify chain), Settings | Yes |

Bugs found and fixed during these checks:

- Modal trapped inside a card (fixed with a portal).
- Graph cropped before nodes were measured.
- Wrong shell syntax in the README.
- Blank `.env` values breaking start-up.

## 10. Latency micro-benchmark

Measured on 1 Nov 2026 on the development laptop: 8 consecutive DEMO assessments for one customer, timed in-process (features + model + SHAP + policy + graph update).

| Version | Median per assessment | Notes |
|---|---|---|
| Before: graph rebuilt from the DB after every transaction | ~700–1,000 ms | ~200 ms scoring + ~500 ms graph rebuild on the next request |
| After: incremental graph update (`GraphEngine.apply_transaction`) | **174 ms** (stored latency), 196 ms including graph sync | The first call after start-up is ~700 ms (model and explainer load) |

`test_incremental_graph_matches_full_rebuild` checks that the incrementally updated graph gives the same summary, shared devices, flagged destinations and customer graph scores as a fresh rebuild. This is a micro-benchmark, not a load test.

## 11. Security checks

| Check | Result |
|---|---|
| Secret scan of tracked files and full git history | No API keys, secrets or `.env` files found |
| PayPal secret exposure to browser | Only the client ID is returned by `/api/paypal/config` |
| Auth/RBAC | Covered by tests; smoke tests return 401/403 as expected |
| Fake payment prevention | Without keys, create-order returns 503; tests assert PayPal status comes only from PayPal responses |
| Bypass prevention | Direct capture without LOW/APPROVE refused (test) |
| Audit tampering | Detected (test) |
