## 19.5 PayPal integration questions (15)

### Q81. How does PayPal Sandbox work?
**Short answer:** It is PayPal's test environment with test business and personal accounts and the same REST APIs, but no real money.
**Deeper explanation:** You create a Sandbox REST app for a client ID and secret, and approve payments with a Sandbox personal account.

### Q82. What is the difference between order creation and payment capture?
**Short answer:** Creation defines what will be paid; capture actually moves the money after the buyer approves.
**Deeper explanation:** Created, then Approved (buyer), then Completed (capture). Sentinel's risk check sits between approval and capture.

### Q83. Which PayPal APIs do you call?
**Short answer:** OAuth token, Orders v2 create, get and capture, and webhook signature verification.
**Deeper explanation:** `/v1/oauth2/token`, `/v2/checkout/orders`, `/v2/checkout/orders/{id}`, `/v2/checkout/orders/{id}/capture`, `/v1/notifications/verify-webhook-signature`.

### Q84. Where does the PayPal secret live?
**Short answer:** Only in the backend environment.
**Deeper explanation:** The browser gets only the public client ID from `/api/paypal/config`.

### Q85. Why intent CAPTURE and not AUTHORIZE?
**Short answer:** It is simpler and the approval-then-capture gap is enough to gate risk.
**Deeper explanation:** AUTHORIZE would hold funds longer and allow an explicit void on rejection. It is listed as future scope.

### Q86. What does PayPal-Request-Id do?
**Short answer:** It makes a PayPal POST idempotent: repeating it returns the original result.
**Deeper explanation:** Sentinel uses the client's Idempotency-Key for creation and `capture-{order_id}` for capture.

### Q87. How do you verify the order before capture?
**Short answer:** GET the order from PayPal and check status, amount, currency, reference and ownership.
**Deeper explanation:** Status must be APPROVED; a mismatch returns 409 and nothing is captured.

### Q88. How are webhooks verified?
**Short answer:** By calling PayPal's verify-webhook-signature API with the transmission headers and webhook ID.
**Deeper explanation:** Only `verification_status = SUCCESS` is accepted; event IDs are de-duplicated.

### Q89. Which webhook events are handled?
**Short answer:** Order approved and capture completed, denied, pending, refunded and reversed.
**Deeper explanation:** They update `paypal_status` and `capture_status`, and are stored in `payment_events`.

### Q90. What if the buyer cancels in PayPal?
**Short answer:** No approval happens, so nothing is assessed or captured.
**Deeper explanation:** The checkout shows "Checkout cancelled in PayPal. Nothing was charged."

### Q91. What if capture returns PENDING?
**Short answer:** Sentinel records PENDING and does not mark the transaction captured.
**Deeper explanation:** A later `PAYMENT.CAPTURE.COMPLETED` webhook would complete it.

### Q92. Did you test against live Sandbox?
**Short answer:** Not yet: the credentials were not available on the build machine.
**Deeper explanation:** The flow is fully tested against a mock transport. Running demos A and C with real Sandbox credentials is the next verification step.

### Q93. Do you use PayPal's fraud tools?
**Short answer:** No. Sentinel is a merchant-side layer using public APIs.
**Deeper explanation:** It complements, and does not replace or access, PayPal's own risk systems.

### Q94. How would you add refunds?
**Short answer:** Call the Captures refund API for a captured payment and handle refund webhooks.
**Deeper explanation:** Refund status would be stored as a PayPal-sourced field, with a reviewer action and an audit entry.

### Q95. Why is PayPal central rather than optional?
**Short answer:** The risk decision only matters because it controls a real capture.
**Deeper explanation:** PayPal's separation of approval and capture, request IDs and signed webhooks are part of the safety design.

## 19.6 AI agent and graph intelligence questions (15)

### Q96. What is LangGraph?
**Short answer:** A library for building LLM workflows as state machines with nodes and edges.
**Deeper explanation:** Sentinel's graph has nine nodes, from retrieving the transaction to routing the report to a reviewer, with a typed shared state.

### Q97. How does your AI agent use tools?
**Short answer:** Core tools always run in fixed steps; in LLM mode Groq can call extra tools before submitting a structured report.
**Deeper explanation:** Tool results become evidence keys, which the report must cite.

### Q98. What happens if Groq is unavailable?
**Short answer:** A deterministic rule-based report is produced and clearly labelled as not LLM-generated.
**Deeper explanation:** The reason (not configured, or the error) is stored in the report and shown in the UI.

### Q99. How do you prevent AI hallucinations?
**Short answer:** Evidence comes from tools, not the LLM, and the report validator removes any finding that does not cite a valid evidence key.
**Deeper explanation:** Invalid recommendations are normalised; if nothing valid remains, the rule-based report is used. Tests check that invented keys are removed.

### Q100. What is a structured output here?
**Short answer:** The `submit_investigation_report` tool call with a fixed schema.
**Deeper explanation:** risk_level, summary, findings with evidence_keys, recommendation from four allowed values, and rationale.

### Q101. Why can't the agent capture or reject payments?
**Short answer:** Those are irreversible financial actions and LLMs can be wrong.
**Deeper explanation:** The agent has no payment tools; humans decide with step-up authentication.

### Q102. What evidence categories exist?
**Short answer:** ML score, anomaly, SHAP drivers, amount, device, geography, impossible travel, card testing, velocity, shared device, flagged destination, circular payments, cluster and merchant risk.
**Deeper explanation:** Each has a severity, and some are marked mitigating, such as a known device or a normal amount.

### Q103. How does your graph detect suspicious relationships?
**Short answer:** Shared devices (3 or more accounts), money loops via `simple_cycles`, flagged-destination payments and connected clusters.
**Deeper explanation:** Merchant hubs are excluded from clustering so popular shops do not link everyone.

### Q104. Why exclude merchants from clusters?
**Short answer:** Almost every customer pays popular merchants, which would merge everyone into one component.
**Deeper explanation:** Devices and wallets are much stronger signals of common control.

### Q105. Did you implement community detection?
**Short answer:** No, connected components only.
**Deeper explanation:** Louvain or Leiden would find sub-communities inside large components; it is future scope.

### Q106. How is a circular payment found?
**Short answer:** Build a customer-to-customer graph from wallet transfers and search for cycles of length 3 to 6.
**Deeper explanation:** The synthetic loop CUS_0081 to 0082 to 0083 to 0080 moved $16,064.37.

### Q107. How does the graph affect the risk level?
**Short answer:** Graph signals raise risk to at least HIGH.
**Deeper explanation:** Triggers are a payment to a flagged destination, a device shared by 3 or more accounts, or a cycle member. A graph risk score is also stored.

### Q108. How is the graph kept current?
**Short answer:** Each assessed transaction is written to the graph tables and folded into the in-memory NetworkX engine incrementally.
**Deeper explanation:** Rebuilding from the database took about 500 ms, so the engine now updates in place under a lock and only re-runs the detection pass. A test checks that the result matches a full rebuild. At large scale you would still move to a graph store.

### Q109. What would a graph neural network add?
**Short answer:** Learned patterns over neighbourhoods instead of hand-written rules.
**Deeper explanation:** It needs more and real labelled data; it is future scope.

### Q110. What would you improve with six more months?
**Short answer:** Live PayPal and Groq validation, real data, calibration, monitoring and scale.
**Deeper explanation:** Also AUTHORIZE flow, community detection, step-up customer verification, frontend tests and a security review.

# PART 20: Personal Project Explanation

## 20.1 30-second elevator pitch

"I built Sentinel for the PayPal AI Hackathon. It protects PayPal checkouts by checking each payment after the buyer approves it but before the money is captured. It combines a machine-learning risk model, a graph that spots fraud rings through shared devices and mule wallets, and an AI investigator that writes an evidence-backed report. Normal payments go straight through; risky ones are held until a reviewer approves them. Everything is explained and audited."

## 20.2 Two-minute explanation

"Most fraud checks give you a score for one payment. Two things are missing: organised fraud looks normal one payment at a time, and a score without reasons still leaves someone to investigate.

Sentinel is a payment layer on top of PayPal. Our demo shop creates a real PayPal Sandbox order on the server. After the buyer approves, and before we capture, we fetch the order from PayPal, check the amount and that it belongs to the shopper, and score it. The score uses 26 features computed only from earlier transactions, from a Random Forest that was picked automatically because it had the best PR-AUC on held-out data, plus an Isolation Forest for anomalies and SHAP to explain the result.

Then the graph. We store every relationship between customers, devices, wallets and merchants, and NetworkX finds shared devices, money loops and clusters. In our third demo the model only gave about 0.33, but the device was shared with three other accounts paying flagged wallets, so the policy raised it to HIGH.

High-risk payments get an AI investigation built with LangGraph: seven tools collect evidence, and every finding has to cite an evidence item or it is removed. The agent can only recommend. A reviewer re-enters their password and approves, rejects or escalates, and only an approval lets PayPal capture. There are 26 automated tests, including ones that prove a high-risk payment can't be captured without approval and nothing is captured twice."

## 20.3 Five-minute technical explanation

"Let me walk through the stack and the guarantees.

**Frontend:** React and TypeScript with Vite and Tailwind. TanStack Query handles data, and one WebSocket invalidates queries so the console is live. React Flow draws the graph, Recharts the charts, AG Grid the transaction table, and the PayPal React SDK renders the buttons with only the public client ID.

**Backend:** FastAPI with Pydantic validation, SQLAlchemy and Alembic, PostgreSQL for deployment and SQLite locally. JWT auth with four roles.

**Payment lifecycle:** create-order recalculates prices on the server, creates a transaction and calls Orders v2 with intent CAPTURE, using the client's Idempotency-Key as PayPal-Request-Id. On capture-order we GET the order, require APPROVED, match amount, currency, reference and owner, then run risk. PayPal status is only written from PayPal responses; Sentinel status is separate. Capture uses a compare-and-set update so only one request proceeds, plus a stable PayPal-Request-Id and reconciliation if PayPal says it was already captured. The capture function re-checks authorisation: LOW risk, or a stored APPROVE decision.

**ML:** a deterministic synthetic world with labelled fraud patterns plus deliberate noise. Point-in-time features via one FeatureState class for training and serving. Stratified 75/25 split, class weights, four models, metrics on the hold-out only. Random Forest won with PR-AUC 0.914; XGBoost was third. SHAP gives per-payment explanations.

**Policy:** thresholds map to LOW, MEDIUM, HIGH or CRITICAL; escalations for anomaly, 10x amount and graph signals only raise risk.

**Graph:** relationships persisted in tables, loaded into NetworkX, transaction nodes collapsed into an entity projection. Shared devices, simple_cycles for loops, connected components excluding merchant hubs for clusters.

**Agent:** a nine-node LangGraph workflow. Evidence is generated deterministically from tool outputs; Groq can call more tools and must submit a structured report; a validator drops uncited findings; if Groq isn't available there's a labelled rule-based fallback.

**Audit and tests:** a SHA-256 hash-chained audit log with verification. 26 pytest tests with a mock PayPal transport. What I haven't verified yet is live Sandbox and live Groq, because I didn't have credentials on the build machine, and the models are only validated on synthetic data."

## 20.4 Resume description

**Sentinel: AI payment risk platform on PayPal (PayPal AI Hackathon 2026).** Built a full-stack payment protection layer (FastAPI, React/TypeScript) that risk-gates PayPal Orders v2 captures. Implemented point-in-time feature engineering and compared Random Forest, XGBoost, Logistic Regression and Isolation Forest (primary selected by hold-out PR-AUC 0.914 on synthetic data) with SHAP explanations; NetworkX graph detection of shared-device rings and circular payments; a LangGraph investigation agent with evidence-validated reports; idempotent, bypass-proof capture; and a hash-chained audit log. 26 automated tests.

## 20.5 LinkedIn description

I built Sentinel for the PayPal AI Hackathon 2026: a payment protection layer that checks every PayPal checkout between buyer approval and capture. It combines an ML risk model with SHAP explanations, graph analysis that finds fraud rings through shared devices and mule wallets, and a LangGraph AI investigator whose every claim must cite real evidence. Risky payments are held until a reviewer approves, and nothing can be captured twice. Built with FastAPI, React, scikit-learn, XGBoost, NetworkX, LangGraph and the PayPal Orders API on Sandbox with synthetic data.

## 20.6 GitHub repository description

Sentinel: AI-powered payment risk intelligence on PayPal Sandbox. ML + SHAP, NetworkX graph intelligence, LangGraph investigation agent, human-in-the-loop capture gating, hash-chained audit. FastAPI + React. Synthetic data.

## 20.7 Hackathon submission summary

Sentinel is a payment protection layer for PayPal checkouts. Between buyer approval and capture, it verifies the PayPal order, scores risk with an ML model (Random Forest selected by hold-out PR-AUC, explained with SHAP) and an anomaly detector, and checks a relationship graph for shared devices, mule wallets and money loops. LOW-risk payments are captured automatically; others are held, investigated by a LangGraph agent whose findings must cite tool-produced evidence, and decided by a re-authenticated human reviewer. Captures are idempotent and cannot bypass review, PayPal status and Sentinel status are kept separate, and every action is recorded in a hash-chained audit log. Built with FastAPI, React, scikit-learn, XGBoost, SHAP, NetworkX, LangGraph/Groq and PayPal Orders v2 on Sandbox, using synthetic data only.
