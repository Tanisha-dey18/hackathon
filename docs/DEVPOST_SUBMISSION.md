# Devpost Submission: Ready-to-Copy Content

Paste each section into the matching Devpost field. Everything here matches the repository. Two statements depend on what you verify before submitting; they are marked **[UPDATE IF VERIFIED]**.

---

## Project name

SENTINEL: Autonomous AI-Powered Payment Risk Intelligence

## Tagline (one line)

Holds risky PayPal payments before capture, explains why with ML, graph analysis and an evidence-citing AI investigator, and lets a human decide.

## Short summary

Sentinel is a risk layer for PayPal checkouts. After a buyer approves a PayPal Sandbox order, and before any money is captured, Sentinel verifies the order with PayPal and scores it. The scoring uses a machine-learning model with SHAP explanations, an anomaly detector and a relationship graph that spots fraud rings. Low-risk payments are captured automatically. Risky ones are held, investigated by a LangGraph agent whose every finding must cite real evidence, and decided by a re-authenticated human reviewer.

---

## Full project description

### The problem we are solving

Most fraud checks give each payment a score and move on. That breaks down in two places. First, organised fraud is built to look normal one payment at a time: a handful of accounts sharing one emulator phone and paying the same wallet each look harmless on their own. Second, a score is not a decision. Someone still has to dig through history, devices and counterparties to understand *why* a payment looks risky, and by then the money has often already been captured. Merchants then pay twice: chargebacks when fraud gets through, and lost customers when genuine payments are blocked.

### What inspired us

PayPal's Orders API separates two moments that most people think of as one: the buyer *approving* a payment and the merchant *capturing* it. That gap is the safest place to make a risk decision, because nothing has moved yet and nothing needs to be refunded. We wanted to see how much intelligence we could put into that gap, and how to do it without letting an AI make irreversible money decisions on its own.

### What it does

1. **SENTINEL MERCHANT**, our demo storefront, creates a real PayPal Sandbox order on the server, with prices taken from the server catalogue rather than the browser.
2. The buyer approves in the PayPal popup.
3. Sentinel fetches the order back from PayPal and checks that it is `APPROVED`, that the amount and reference match, and that it belongs to the signed-in shopper.
4. The **risk engine** computes 26 point-in-time behavioural features and scores them with the primary ML model (selected by hold-out PR-AUC). It adds an Isolation Forest anomaly percentile and checks the **relationship graph** for shared devices, flagged mule wallets and circular money flows.
5. **LOW** risk is captured automatically. **MEDIUM, HIGH and CRITICAL** payments are **held**: approved in PayPal, but not captured.
6. For high-risk payments, an **AI investigation agent** (LangGraph) runs seven tools. It writes a report where each finding must cite an evidence item produced by a tool; anything uncited is removed automatically.
7. A **human reviewer** re-enters their password, types the transaction ID and approves, rejects or escalates. Only an approval triggers the PayPal capture.
8. Every step, from PayPal responses and risk scores to agent actions and human decisions, goes into a **hash-chained audit log**.

### How we built it

- **Backend**: FastAPI with Pydantic, SQLAlchemy 2 and Alembic. PostgreSQL for deployment, SQLite for zero-setup local runs. JWT auth with four roles. One WebSocket streams live events to the console.
- **Frontend**: React, TypeScript, Vite and Tailwind. TanStack Query for data, Recharts for the dashboards, React Flow for the interactive graph, AG Grid for the transaction table, and the PayPal React SDK for checkout buttons.
- **ML**: scikit-learn, XGBoost and SHAP on a deterministic synthetic dataset (2,000 transactions, 142 labelled frauds) with a stratified hold-out set.
- **Graph**: NetworkX over relationships stored in the database.
- **Agent**: LangGraph state machine; Groq tool calling when a key is configured, a clearly labelled rule-based fallback otherwise.
- **Tests**: 24 pytest tests, including the payment safety rules, run against a mock PayPal transport.

### How we use AI

- **Supervised ML**: Logistic Regression, Random Forest and XGBoost are trained on every run; the best by PR-AUC becomes the primary model. In our current version that is Random Forest (hold-out PR-AUC 0.897 on synthetic data). XGBoost came third, and we report that rather than hiding it.
- **Unsupervised ML**: Isolation Forest gives an anomaly percentile that can raise risk.
- **Explainable AI**: SHAP turns each score into sentences a reviewer can check, such as *"Amount is 43.4x the customer's historical average"*.
- **Agentic AI**: a LangGraph workflow with seven tools that writes an evidence-cited report. Hallucination control is built in: evidence comes from tools, a validator removes uncited claims, and the agent can only recommend. **[UPDATE IF VERIFIED]** The Groq LLM path is implemented; in our recorded runs the agent used its labelled rule-based fallback because no Groq key was configured.

### How we use PayPal

PayPal is the core of the product, not a payment button bolted on at the end. Sentinel's main guarantee is that **risky money does not move without a human**, and that guarantee exists because of how PayPal's Orders API works:

- **Orders API v2 create** with `intent=CAPTURE`, server-side item breakdown, our transaction ID as `reference_id`, and the client's idempotency key forwarded as `PayPal-Request-Id`.
- **Orders API v2 get** to verify the approved order (status, amount, currency, reference) before scoring.
- **Orders API v2 capture**, gated by the risk policy or a reviewer approval, with a stable `PayPal-Request-Id` and a database compare-and-set lock, so a payment can never be captured twice.
- **Webhooks** verified through PayPal's verify-webhook-signature API and de-duplicated by event ID.
- **PayPal JavaScript SDK** buttons on the storefront, loaded with only the public client ID.
- PayPal's status and Sentinel's decision are stored separately, so a held payment shows as "approved in PayPal, not captured", never as paid.

Sentinel runs entirely on the PayPal **Sandbox**. It does not access PayPal's internal fraud systems or any production data; it is a merchant-side layer built on public APIs.

**[UPDATE IF VERIFIED]** The full flow is covered by automated tests against a mock PayPal transport. Replace this sentence after you run Demo A and Demo C through a real Sandbox checkout, for example: "We verified the complete flow on PayPal Sandbox: a low-risk order captured automatically and a high-risk order held without capture."

### Main features

- PayPal Sandbox checkout with risk-gated, exactly-once capture
- ML risk scoring with SHAP explanations and hold-out evaluation of four models
- Graph intelligence: shared devices, circular payments, suspicious clusters, flagged destinations
- LangGraph investigation agent with evidence-validated reports
- Human review with re-authentication, typed confirmation and escalation to admin
- Live Command Centre, AG Grid transaction explorer, React Flow network graph, model analytics
- Hash-chained, verifiable audit trail
- Three one-click demo scenarios and a synthetic traffic simulator

### Challenges we faced

- **Making capture truly safe.** Double clicks, retries and a reviewer approving at the same time as a retry can all cause double captures. We ended up with three layers: a database compare-and-set lock, PayPal request IDs, and a capture function that re-checks authorisation itself.
- **Keeping the AI honest.** Our first idea was to let the LLM write the report directly. We changed it so tools produce the evidence, the LLM can only cite it, and a validator deletes anything uncited.
- **Avoiding data leakage.** Fraud features such as "how many accounts use this device" are easy to compute with future data by accident. We wrote one point-in-time feature class used for both training and live scoring.
- **Honest metrics.** It was tempting to make XGBoost the headline model. We let PR-AUC pick instead, and we label every metric as synthetic.
- **Showing two truths at once.** The UI needed to show "PayPal says APPROVED" and "Sentinel says HELD" without confusing anyone.

### What we learned

Payment safety is mostly about state management and idempotency, not models. The graph caught what the model missed: in our fraud-ring demo, the ML score was only 0.31, and the shared emulator device pushed the payment to HIGH. AI is most useful when it is constrained, cites evidence and leaves irreversible actions to people.

### What's next for Sentinel

- Run and record the full live PayPal Sandbox flow and the Groq agent path
- Validate on real or public fraud data with time-based splits; calibrate scores; add drift monitoring
- AUTHORIZE-intent flow (authorise, then capture or void), refunds and disputes
- Community detection and incremental graph updates for scale
- Step-up customer verification for medium-risk payments

### Built with

python, fastapi, pydantic, sqlalchemy, alembic, postgresql, sqlite, redis, scikit-learn, xgboost, shap, pandas, numpy, networkx, langgraph, groq, react, typescript, vite, tailwindcss, recharts, react-flow, ag-grid, tanstack-query, framer-motion, paypal, paypal-orders-api, paypal-javascript-sdk, websockets, docker, render

### Categories / tags to select

- Grand Prize (all eligible)
- Best Use of PayPal + AI
- Best Use of Agentic Commerce (the agent investigates payments but only recommends; frame it honestly)
- Best Use of AG Grid (sponsor prize: AG Grid powers the Live Transactions explorer)
- Best Use of Render: **only if you actually deploy** with the included `render.yaml`

Tags: fintech, fraud-detection, payments, explainable-ai, graph-analytics, agentic-ai, human-in-the-loop

### Final pitch

Sentinel works in the moment between "the buyer said yes" and "the money moved". It reads that moment with three kinds of intelligence: a model that scores the payment, an anomaly detector, and a graph that sees who the payer is connected to. Normal payments go straight through. Risky ones wait while an AI investigator builds a case file in which every claim points to evidence, and a person makes the call. It is a prototype on synthetic data and PayPal Sandbox, but the safety guarantees are real and tested: nothing is captured twice, and nothing risky is captured without a human.

---

## Links to fill in

| Field | Value |
|---|---|
| Public repository | https://github.com/Tanisha-dey18/hackathon |
| Demo video (YouTube, public, under 3 min) | **TODO**: upload and paste link |
| Hosted demo URL | None. Judges run it locally using the README (allowed by the rules) |
| License | MIT (repository root) |

## Testing instructions (paste into Devpost)

1. Follow README sections 15–17: install the Python and Node dependencies, copy `.env.example` to `.env`, start the backend and the frontend.
2. Open http://localhost:5173/login. All demo accounts use the password `SentinelDemo!2026` (synthetic accounts).
3. Sign in as `reviewer@sentinel.dev`, open **Command Centre** and click **Run risk pipeline** on scenarios A, B and C. Open the investigation workspace for C, review the evidence and use **Reject** or **Approve** (re-enter the password and type the transaction ID).
4. **PayPal checkout**: create a free Sandbox REST app at developer.paypal.com, put its Client ID and Secret in `.env`, restart the backend, then click **PayPal checkout** on scenario A or C and approve with a Sandbox *personal* account. **[Optionally provide your own Sandbox app credentials and a Sandbox buyer login in the private Devpost testing field. Never put them in the repository.]**
5. Swagger: http://localhost:8000/docs. Tests: `backend\.venv\Scripts\python -m pytest -q backend\tests`.
