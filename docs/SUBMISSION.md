# SENTINEL — Hackathon submission package

## A. Project description

**Problem.** Payment platforms decide in milliseconds whether to take a customer's money. Rule engines catch
yesterday's fraud; per-transaction ML misses coordinated rings whose individual payments look normal; and when a
payment is suspicious, analysts spend minutes stitching together history, devices and counterparties before they can
decide. Meanwhile, the money has often already been captured.

**Solution.** SENTINEL is a payment protection layer that sits between PayPal buyer approval and PayPal capture.
For every checkout it:

1. Creates a real PayPal order (Orders API v2, Sandbox) with server-side prices.
2. After the buyer approves, retrieves the order from PayPal and verifies state, amount and ownership.
3. Scores the payment with an ML ensemble (Random Forest / XGBoost / Logistic Regression + Isolation Forest), explains it with SHAP, and checks financial-graph signals (shared devices, mule destinations, circular payment loops).
4. Applies an auditable policy: LOW risk is captured automatically; anything else is **held and not captured**.
5. Launches an autonomous LangGraph investigation agent that gathers evidence with seven tools and writes an evidence-cited report with a recommendation.
6. A human reviewer approves, rejects or escalates with password re-authentication; only an approval can trigger the PayPal capture.

**Innovation.**
- *Capture gating*: risk decisions are enforced at the exact point money moves, with a compare-and-set capture lock so nothing is captured twice or without authorisation.
- *Graph + ML together*: the coordinated-fraud demo payment scores only ~0.31 on the ML model (it looks like normal behaviour for that account), but graph intelligence finds a 4-account emulator device and flagged mule destinations and escalates it to HIGH.
- *Grounded agent*: every finding the AI makes must cite an evidence key produced by a tool; unsupported claims are removed automatically, and a labelled deterministic fallback keeps the system honest when no LLM is available.
- *Tamper-evident audit*: a hash-chained log covering risk scores, policy actions, PayPal responses, agent steps and human decisions.

**PayPal integration.** PayPal JS SDK buttons; Orders v2 create/get/capture; `PayPal-Request-Id` idempotency;
webhook signature verification via PayPal's verification API; every PayPal response stored with its debug ID; PayPal
status and Sentinel risk status tracked separately so a held payment is never shown as paid.

**AI integration.** Supervised ML with SHAP explanations, unsupervised anomaly detection, NetworkX graph analytics,
and a LangGraph agent using Groq tool calling with structured output and evidence validation.

**Architecture.** React/TypeScript console and storefront → FastAPI (REST + WebSocket, JWT/RBAC, rate limiting) →
risk engine, ML, graph and agent services → PostgreSQL (SQLite locally) and PayPal Sandbox. See the diagrams in the README.

**Real-world impact.** Fewer fraudulent captures (and the chargebacks that follow), fewer false declines because
reviewers see *why* a payment was flagged, and much faster investigations: the agent assembles the case file that an
analyst would otherwise build by hand, while humans remain in control of irreversible actions.

## B. Repository checklist

- [x] Complete source (`backend/`, `frontend/`)
- [x] README with architecture diagrams, setup, environment, API summary, testing and deployment
- [x] MIT `LICENSE` at the repository root
- [x] `.env.example` (no secrets committed; `.env` git-ignored)
- [x] Alembic migrations, Docker Compose, Dockerfiles, Render Blueprint
- [x] Automated tests (`backend/tests`, 23 tests)
- [x] Technical documentation (`docs/TECHNICAL.md`)

## C. Three-minute demo video script

**Before recording:** PayPal Sandbox credentials in `.env`, backend + frontend running, a Sandbox *Personal* buyer
account ready, browser at 1440×900. Open two tabs: storefront and console (logged in as reviewer).

| Time | Screen | Action | Voice-over |
|---|---|---|---|
| 0:00–0:15 | Command Centre | Slow pan over KPIs and charts | "This is SENTINEL. It sits between PayPal approval and PayPal capture and decides, with evidence, whether money should move. Every number here comes from the backend; the history is labelled synthetic." |
| 0:15–0:45 | Demo A → PayPal checkout | Click **PayPal checkout** on A, sign in as Ava, pay with the Sandbox buyer | "Ava buys coffee gear on her usual laptop. Our backend created a real PayPal Sandbox order. When she approves, Sentinel fetches the order from PayPal, verifies the amount and ownership, and scores it." |
| 0:45–0:55 | Checkout result | Point at the two status panels | "Low risk, so the policy captured it automatically. On the left is PayPal's own status — COMPLETED with a capture ID. On the right, Sentinel's decision." |
| 0:55–1:25 | Demo B → workspace | Click **Run risk pipeline** on B, open workspace | "Ben normally spends about thirty-eight dollars. Now: an eighteen-hundred-dollar laptop from a new device. The model's SHAP drivers show exactly why — amount is 43 times his average, new device — and the policy holds it for verification. Nothing is captured." |
| 1:25–2:20 | Demo C → PayPal checkout → workspace | Check out as Cara with the gift card; result shows *under review*; open the transaction in the console | "Cara's payment looks ordinary to the ML model. But the graph shows her phone is an emulator shared with three other accounts, all paying flagged mule wallets. Sentinel escalates to HIGH, holds the payment — PayPal status APPROVED, not captured — and the investigation agent runs." Click through the steps, hover the red edges, show findings with E-keys. "Every finding cites evidence a tool produced. The agent recommends reject — but it cannot move money." |
| 2:20–2:45 | Decision modal | Click **Reject**, write reason, re-enter password, type the transaction ID | "A reviewer decides, with re-authentication and confirmation. Rejected: the PayPal order is never captured." |
| 2:45–3:00 | Audit Centre, PayPal Payments | Click **Verify hash chain**; show PayPal events | "Every step — PayPal responses, risk scores, agent actions, human decisions — is in a hash-chained audit log. Sentinel: every transaction, every connection, every risk, understood." |

*No PayPal credentials?* Use **Run risk pipeline** for A, B and C; the narrative is identical except the
PayPal capture panels, which the UI clearly marks as not configured.

## D. Technical documentation

See [TECHNICAL.md](TECHNICAL.md): technology rationale, ML pipeline, graph intelligence, agent design, PayPal
integration, payment state management, security decisions and current limitations.
