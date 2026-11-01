# PART 13: User Interface and Product Workflow

All screenshots in this part were captured from the running application on the development machine (1440 x 900 viewport). PayPal and Groq were not configured at the time, which is visible on some screens.

## 13.1 Sign-in

[[IMG:17_login|Sign-in page with the list of synthetic demo accounts.]]

A single sign-in page serves staff and shoppers. Clicking a demo account fills the form. After sign-in, shoppers go to the storefront and staff to the console.

## 13.2 Customer marketplace (SENTINEL MERCHANT)

[[IMG:14_shop_catalog|Storefront catalogue with category filters.]]

Shoppers browse 16 synthetic products from synthetic sellers and filter by category. The banner states that every checkout is risk-assessed before capture.

[[IMG:15_product_detail|Product detail page.]]

The product page shows the seller, price and description, and explains that PayPal processes the payment while Sentinel reviews risk before funds are captured. If a shopper adds an item from a different seller, the cart refuses and explains that checkout is per seller.

## 13.3 Shopping cart and PayPal checkout

[[IMG:16_checkout|Checkout for Demo B with PayPal not configured: the page explains the setup instead of faking a payment.]]

The checkout summarises the order, explains the four protection steps and shows the device context. When PayPal is configured, PayPal Buttons appear here. When it is not, as in this screenshot, the page says so explicitly. After approval, a result screen shows **PayPal status** (order, capture, capture ID) and **Sentinel status** (decision, risk level, investigation) side by side.

## 13.4 Command Centre

[[IMG:01_command_centre|Command Centre with KPIs, 30-day volume by risk level, and the demonstration launcher.]]

The landing page for staff. KPI tiles: transactions analysed, suspicious, critical, awaiting review, PayPal captured, rejected and average processing time. Charts: 30-day volume stacked by risk level, risk distribution, fraud-probability histogram, fraud trend, PayPal and Sentinel status distributions, network summary, model performance and a live event stream. Every number comes from `GET /api/dashboard/metrics`. The demonstration panel runs scenarios A, B and C and starts or stops the synthetic traffic simulator.

## 13.5 Live Transactions

[[IMG:02_live_transactions|Live Transactions grid (AG Grid) with risk chips, quick search and pagination.]]

An AG Grid table of all transactions with column filters, sorting, quick search, risk-level chips, an "awaiting review only" toggle and CSV export. Clicking a row opens the investigation workspace.

## 13.6 Fraud Intelligence

[[IMG:03_fraud_intelligence|Fraud Intelligence: review queue, per-transaction explanation and decision buttons.]]

The review queue lists every payment awaiting a decision. Selecting one shows its fraud probability, anomaly percentile, policy notes, top risk factors and a SHAP chart, plus the Approve / Reject / Escalate buttons. Below, a global chart ranks the model's features by mean absolute SHAP value.

## 13.7 Network Graph

[[IMG:05_network_device|Neighbourhood of device DEV_0147: red dashed edges are suspicious links.]]

The Network Graph page starts with the overview of suspicious clusters (shown in Part 8) and lets a user search any customer, device or destination ID. Node colour shows risk; icons show type; red animated edges carry evidence. Hovering a node shows its details; clicking a node or edge opens an inspector with evidence and links to the underlying transactions. Side panels list suspicious clusters, shared devices, circular loops and flagged destinations.

## 13.8 AI Investigation workspace

[[IMG:06_workspace_top|Investigation workspace: transaction (left), relationship graph (centre), AI report steps (right).]]

The signature screen. Left: transaction details and ML assessment. Centre: the relationship graph around the transaction. Right: the AI investigation with every step, its tool, duration and summary. The INVESTIGATE button starts a new run.

[[IMG:07_workspace_steps|Workspace (scrolled): SHAP drivers on the left; agent steps and the start of the report on the right.]]

[[IMG:08_workspace_report|Workspace (bottom): evidence-cited findings, the REJECT recommendation, the evidence timeline and the decision history.]]

The bottom panels show the evidence timeline (E1...En with severity and mitigating flags), the decision buttons, the PayPal order block when one exists, recorded decisions and the audit trail with hash prefixes.

## 13.9 AI Investigations list

[[IMG:09_investigations|AI Investigations: agent pipeline and completed runs.]]

Shows the agent pipeline, the current mode (LLM or deterministic fallback) and every investigation with its recommendation and number of findings.

## 13.10 PayPal Payments

[[IMG:10_paypal_payments|PayPal Payments page: empty because PayPal was not configured during development.]]

When PayPal is configured, this page lists every order with PayPal status, capture status and capture ID, Sentinel status and risk, plus a "Sync" button that refreshes from PayPal. Below, every PayPal API response and verified webhook is listed with HTTP status and debug ID. It is empty in this screenshot because no live Sandbox orders were created.

## 13.11 Model Analytics

[[IMG:11_model_analytics|Model Analytics: hold-out metrics, confusion matrices, ROC and precision-recall curves.]]

Compares the four models, marks the primary, shows confusion matrices and ROC / PR curves, and lets an ADMIN retrain.

## 13.12 Audit Centre and Settings

[[IMG:12_audit_centre|Audit Centre: hash-chained log of every action.]]

The audit log can be filtered by action or entity ID. "Verify hash chain" recomputes every hash; at capture time it reported "Chain intact: 18 entries verified".

[[IMG:13_settings|Settings: integration status and the risk policy editor.]]

Settings shows the PayPal, webhook, Groq, database and rate-limiter status, setup steps for PayPal, and the risk policy (editable by ADMIN; all changes are audited).

# PART 14: Demonstration Scenarios

Scenarios are launched from the Command Centre. **"Run risk pipeline"** sends a DEMO transaction through the real risk engine without creating a PayPal order. **"PayPal checkout"** sets the shopper persona and device and opens the real checkout (requires Sandbox credentials). The outputs below are from actual runs of "Run risk pipeline" on the development machine.

## Scenario A: Normal payment

| Aspect | Detail |
|---|---|
| Initial conditions | Ava Thompson (CUS_0001), San Francisco, 22 prior purchases averaging about $55, always on her laptop. |
| User action | Buys a Ceramic Pour-Over Set ($48) and Single-Origin Sampler ($28): $76.00, same laptop, at home. |
| Backend processing | Transaction created, 26 features computed, prediction stored, policy applied. |
| ML analysis | Fraud probability 0.000, LOW. No escalation rules triggered. |
| Graph analysis | No shared devices, cycles or flagged destinations. |
| AI investigation | Not triggered (LOW). |
| Payment workflow | Status CLEARED. Through PayPal checkout, Sentinel would call capture automatically. |
| Final result | Cleared for capture. Audit entries: TRANSACTION_CREATED, RISK_ASSESSED, RISK_POLICY_APPLIED. |

## Scenario B: Unusual transaction

| Aspect | Detail |
|---|---|
| Initial conditions | Ben Carter (CUS_0002), Chicago, 20 prior purchases averaging about $38. |
| User action | Buys a Vector 14" Ultrabook, $1,849.00, from a device he has never used. |
| ML analysis | Fraud probability 0.066 (would be LOW on its own). Anomaly percentile 0.954. Top SHAP factors: transaction amount $1,849.00; amount is 43.4x the customer's historical average; first time this customer has used this device. |
| Policy | "Amount is 43.4x customer average (>= 10.0x) -> at least MEDIUM". |
| Graph analysis | Nothing suspicious. |
| AI investigation | Not auto-triggered at MEDIUM (configurable); can be started with INVESTIGATE. |
| Payment workflow | HELD_FOR_VERIFICATION, review status PENDING_REVIEW. Through checkout, PayPal would show APPROVED and not captured. |
| Final result | Waits in the review queue for a human. |

This scenario shows why policy rules complement the model: the model, trained on synthetic data that includes legitimate large purchases, gave a low score, and the explicit amount rule plus the explanation put it in front of a reviewer.

## Scenario C: Coordinated synthetic fraud network

| Aspect | Detail |
|---|---|
| Initial conditions | Cara Novak (CUS_0003) is part of a 9-account cluster; the emulator device DEV_0147 is shared by 4 accounts; the cluster sent money to flagged wallets DST_MULE_01 and DST_MULE_02. |
| User action | Buys a $500 Universal Gift Card (VaultGift Digital, high-risk category) on the emulator device. |
| ML analysis | Fraud probability 0.333, MEDIUM by threshold. Anomaly percentile 0.947. |
| Graph analysis | "Graph policy: device shared by 4 accounts -> at least HIGH". Graph risk score 0.997. |
| AI investigation | Started automatically. 8 evidence items, 4 high severity; deterministic fallback report (Groq not configured); recommendation REJECT; 5 evidence-backed findings (Part 9.7). |
| Human decision | Reviewer re-authenticated, typed the transaction ID and rejected: "Shared emulator device with 4 ring accounts and flagged mule destination (E5, E6)." |
| Payment workflow | Transaction REJECTED. Through PayPal checkout the order would remain APPROVED and never be captured. |
| Audit trail | TRANSACTION_CREATED, RISK_ASSESSED, RISK_POLICY_APPLIED, INVESTIGATION_STARTED, INVESTIGATION_COMPLETED, REVIEW_DECISION. |

This is the clearest demonstration of the project's thesis: the transaction looked only moderately risky on its own, and the relationships revealed the fraud.

# PART 15: Testing and Results

## 15.1 Automated test suite

The backend has 26 automated tests (`pytest`) in `backend/tests`. They run against an isolated SQLite database that is seeded, trained and scored from scratch, and a **mock PayPal transport** that emulates Sandbox behaviour (OAuth, Orders v2, capture with `PayPal-Request-Id`, `ORDER_ALREADY_CAPTURED`, webhook verification). The mock is only used by tests.

Latest run: **26 passed, 0 failed (31.0 s)**.

| Test | Area | Checks |
|---|---|---|
| test_models_trained_with_honest_metrics | ML evaluation | All 4 models trained; metrics in [0,1]; confusion matrix sums to test rows; primary has best PR-AUC |
| test_ml_prediction_structure | ML prediction | Probability and anomaly in [0,1]; SHAP for every feature; positive top factors; missing values kept as null |
| test_baked_image_data_shifts_to_today | Deployment | Data baked into the image is shifted to end today, exactly |
| test_synthetic_world_is_independent_of_seed_time | Reproducibility | Same data whatever day or time the database is seeded |
| test_risk_classification_policy | Risk classification | Threshold mapping; escalation never lowers risk |
| test_transaction_creation_and_assessment | API | 401 unauthenticated, 403 shopper; risk payload; CLEARED status; audit entry; 422 on negative amount |
| test_anomalous_amount_escalates | Risk policy | Demo B is MEDIUM or higher and held; amount factor present |
| test_graph_detects_fraud_structures | Graph | DEV_0147 shared; 4-account cycle; both mule wallets; clean customer has no signals; evidence on edges; 404 unknown entity |
| test_incremental_graph_matches_full_rebuild | Graph | In-place graph updates match a full rebuild from the database |
| test_agent_tools_return_real_records | AI tools | Tools return real records; ToolError on unknown IDs; report tool drops invented and uncited findings; invalid recommendation normalised |
| test_investigation_workflow_deterministic_fallback | Agent workflow | All 7 tools run; labelled fallback; findings cite real keys; agent does not move money |
| test_rbac_and_auth | Security | 401 / 403 rules; forged token rejected; admin-only policy update |
| test_audit_chain_detects_tampering | Audit | Chain valid; modified row detected at the right ID; valid again after restore |
| test_investigations_persisted | Persistence | Completed investigation has evidence and the "recommendation only" notice |
| test_create_order_uses_server_side_prices | Payment | PayPal status CREATED; server price used |
| test_create_order_idempotency_key_replays | Idempotency | Same key returns same order; no second PayPal order |
| test_cart_validation | Input validation | Unknown product, mixed sellers, quantity 99 rejected |
| test_staff_cannot_create_checkout | RBAC | 403 for staff |
| test_capture_requires_buyer_approval | Payment state | 409 when order not approved |
| test_low_risk_payment_is_captured_once | Capture, duplicates | LOW captured; replays never call PayPal capture again (exactly 1 call) |
| test_payment_ownership_enforced | Ownership | Another shopper gets 403 |
| test_amount_mismatch_blocks_capture | Integrity | Tampered amount gives 409; no capture |
| test_high_risk_payment_cannot_bypass_review | Policy | HIGH held, APPROVED not captured, investigation started; direct capture refused (409) |
| test_reviewer_decision_controls | Review | Shopper 403, wrong password 401, wrong confirmation 422, short reason 422, escalation requires ADMIN, approve captures once, repeat 409 |
| test_reject_decision_never_captures | Review | REJECT leaves PayPal order APPROVED, uncaptured |
| test_webhook_signature_verification_and_dedupe | Webhooks | Forged or missing signature 400; valid processed; duplicate ignored |

## 15.2 Other verification performed

| Check | Result |
|---|---|
| Frontend type check (`tsc -b`) | Passed |
| Frontend production build (`vite build`) | Passed |
| Manual UI walkthrough in a browser | All 9 console sections, the investigation workspace, storefront, checkout (unconfigured) and a reviewer decision exercised |
| PostgreSQL DDL generation (`alembic upgrade head --sql`) | 18 tables generated for the PostgreSQL dialect |
| ML evaluation | Hold-out metrics in Part 7.6 |

## 15.3 Not yet verified

| Item | Reason |
|---|---|
| Live PayPal Sandbox order, approval and capture | Sandbox credentials were not available on the build machine |
| Live webhooks | Requires a public URL and webhook ID |
| Groq LLM investigation | No API key; fallback path tested instead |
| Docker Compose and PostgreSQL at runtime | Docker daemon was not running on the build machine |
| PayPal / Groq on the hosted deployment | Keys not configured on Render |
| Load and performance testing | Not performed |
| Frontend automated tests | None written |

# PART 16: Innovation and Differentiation

| Compared with | What Sentinel adds |
|---|---|
| Basic fraud detection (a single score) | Combines a supervised score, an anomaly percentile and graph signals; explains each payment with SHAP and policy notes; holds payments instead of auto-declining. |
| Traditional rule-based systems | Rules are kept, but as transparent escalations on top of learned models; thresholds are configurable and audited. |
| Basic AI chatbots | The agent works on real records through tools, must cite evidence, has a validator that removes unsupported claims, and cannot take irreversible actions. |
| Standalone payment apps | Risk decisions are enforced at PayPal's capture step with idempotency, ownership checks and bypass protection. |

The combination is the contribution: PayPal payment infrastructure, ML risk prediction, graph intelligence, an autonomous but bounded investigator, explainable recommendations and human-supervised decisions in one workflow.

**Limits of these claims:** Sentinel is a hackathon prototype. Commercial fraud platforms already combine many of these techniques at far larger scale with real data. We make no claim that Sentinel is the first or the best system of its kind, or that its accuracy would hold on real payments.

# PART 17: Limitations and Future Scope

## 17.1 Current limitations (implemented system)

- **Synthetic training data.** Patterns were designed by the author; some features (for example hour of day) are strong because of how the generator works.
- **No production validation.** Live PayPal Sandbox and Groq paths are implemented but were not executed during development.
- **Uncalibrated probabilities.** Class weighting shifts scores; they are risk scores rather than calibrated probabilities.
- **Single-process design.** WebSocket fan-out, feature state and graph cache live in one process.
- **CAPTURE intent.** Held orders must be decided within PayPal's approval window.
- **Simplified context.** Device identity is a random browser ID; checkout location defaults to the customer's home city unless a demo provides one.
- **In-sample history scores.** Historical transactions are scored by a model that was trained on most of them; only hold-out metrics measure quality.
- **No frontend tests**, no load testing and no formal security review.

## 17.2 Future scope (not implemented)

| Area | Proposed improvement |
|---|---|
| Data | Train and validate on real or public fraud datasets; time-based (out-of-time) validation. |
| Calibration | Isotonic or Platt calibration; cost-based threshold selection. |
| Monitoring | Feature drift, score drift and alerting; champion/challenger models. |
| Graph | Community detection (Louvain / Leiden), graph embeddings, graph neural networks, a graph database for scale. |
| Scale | Redis pub/sub or a message queue for events, a shared feature store, horizontal API scaling, streaming ingestion. |
| PayPal | AUTHORIZE-intent flow (authorise, then capture or void), refunds, disputes API, live webhook subscriptions, Vault. |
| Identity | Step-up verification for MEDIUM payments (one-time codes), stronger device intelligence. |
| Security | httpOnly cookie sessions, MFA for reviewers, penetration testing, secrets manager. |
| AI agent | Live Groq evaluation, prompt and report quality evaluation, multiple-model comparison. |
| Product | Case management, reviewer workload metrics, customer communication templates. |

# PART 18: Conclusion

Sentinel demonstrates that payment infrastructure and AI work best together when each does what it is good at. PayPal provides a real, idempotent payment lifecycle with a clear separation between a buyer's approval and the capture of funds. Machine learning estimates risk and, with SHAP, explains it. Graph analysis reveals coordinated behaviour that single-payment models miss, as Scenario C showed. An agentic investigator assembles the case file, but only from evidence that tools produced, and it can only recommend. Humans make the irreversible decisions, and everything is written to a tamper-evident log.

The engineering concepts combined are payment state machines and idempotency, point-in-time feature engineering, imbalanced classification and honest evaluation, explainable AI, graph algorithms, tool-using LLM agents with validation, role-based security and auditability.

The same pattern of "score, connect, investigate, explain, then let a human decide before money moves" could apply to marketplace payouts, peer-to-peer transfers, refund abuse or merchant onboarding. Sentinel is a prototype on synthetic data, but its architecture is a credible starting point for those problems.
