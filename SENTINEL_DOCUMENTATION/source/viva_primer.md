# VIVA PRIMER: Sentinel in Plain Language

## Sentinel in simple words

When you pay with PayPal online, two things happen: you **approve** the payment, and later the shop **captures** the money. Sentinel works in the gap between them. It checks whether the payment looks safe. Safe payments are captured straight away. Risky ones wait until a person has looked at the evidence and said yes. An AI assistant prepares that evidence, but it is never allowed to move money itself.

## Every technology, and why it was chosen

| Technology | What it is | Why Sentinel uses it |
|---|---|---|
| React + TypeScript | UI library + typed JavaScript | Two apps (shop and console) in one codebase; types catch API mistakes |
| Vite | Build tool | Fast dev server; proxies `/api` and `/ws` to the backend |
| Tailwind CSS | Utility CSS | Consistent dark design quickly |
| TanStack Query | Server-state cache | Caching and automatic refresh when WebSocket events arrive |
| Recharts | Charts | Dashboard, ROC/PR curves, SHAP bars |
| React Flow | Graph UI | Pan, zoom and click on the relationship graph |
| AG Grid Community | Data grid | Filter, sort and search 2,000+ transactions; CSV export |
| PayPal JS SDK | PayPal Buttons | Real Sandbox checkout without exposing the secret |
| FastAPI + Pydantic | Python web framework + validation | Typed endpoints, Swagger, WebSockets, same language as the ML code |
| SQLAlchemy + Alembic | ORM + migrations | One model layer for PostgreSQL and SQLite; versioned schema |
| PostgreSQL / SQLite | Databases | Postgres for deployment; SQLite for zero-setup local runs |
| Redis (optional) | In-memory store | Shared rate-limit counters across instances |
| scikit-learn, XGBoost | ML libraries | Standard, strong models for tabular fraud data |
| SHAP | Explainability | Explains each prediction feature by feature |
| NetworkX | Graph library | Finds shared devices, cycles and clusters |
| LangGraph | Agent workflow library | Clear, testable multi-step investigation |
| Groq | LLM API (optional) | Fast tool-calling LLM for the analysis step |
| bcrypt, PyJWT | Security libraries | Password hashing, signed login tokens |
| Docker, Render | Deployment | Reproducible environment; one-click cloud blueprint (configured, not deployed) |

## The ML models in one paragraph each

**Logistic Regression** adds up weighted features and turns the total into a probability. It is simple and transparent, but it only draws straight-line boundaries. **Random Forest** grows hundreds of decision trees on random samples and lets them vote. It is robust, and it is Sentinel's primary model because it had the best PR-AUC (0.897 on synthetic data). **XGBoost** builds trees one after another, each fixing the previous one's errors. It is often the strongest on tabular data; here it came third (0.886), and the project reports that honestly. **Isolation Forest** finds unusual points by how quickly random cuts can isolate them. It uses no labels and gives an "anomaly percentile". **SHAP** explains a single prediction by sharing out the model's output among the features.

Key ideas: **precision** (of what we flagged, how much was fraud), **recall** (of all fraud, how much we flagged), **PR-AUC** (the best single number when fraud is rare), **point-in-time features** (computed only from earlier transactions, so there is no peeking at the future), and **class weights** (making the rare fraud class count more).

## Graph intelligence in one paragraph

Each payment links a customer to a device, a merchant and a destination wallet. Sentinel stores these links and builds a graph. A device used by three or more accounts is a "shared device". Money going A to B to C to D and back to A is a "cycle". Groups of accounts connected through devices and wallets are "clusters" (shops are left out, because everyone shops at the same places). Wallets on a synthetic watch list are "flagged destinations". Any of these can push a payment to HIGH risk and becomes evidence for the investigator.

## Agentic AI in one paragraph

An agent is an AI that uses tools to look things up, instead of answering from memory. Sentinel's agent is a LangGraph workflow: retrieve the transaction, study the customer, read the ML prediction, check the graph, check the merchant, collect evidence, analyse, write the report, send it to a reviewer. Tools create numbered evidence (E1, E2 ...), and the report may only cite those numbers; anything else is deleted. If no LLM key is configured, a rule-based analysis is used and clearly labelled. The agent can recommend APPROVE, HOLD_FOR_REVIEW, REJECT or ESCALATE, but it cannot capture or reject a payment.

## PayPal integration in one paragraph

The server gets an OAuth token with its secret, creates an order with Orders API v2 (`intent=CAPTURE`), and the buyer approves it in PayPal. On approval the server reads the order back and checks it is APPROVED, for the right amount and the right shopper. It captures only if the risk is LOW or a reviewer approved. A database lock and a fixed `PayPal-Request-Id` mean it can never capture twice. Webhooks are accepted only after PayPal's signature-verification API says they are genuine. PayPal's status and Sentinel's status are stored separately. Everything runs on the Sandbox; the live Sandbox run still needs to be performed with real credentials.

## Backend, API and database in one paragraph

FastAPI routers (auth, transactions, intel, paypal, ops) call service modules (payments, risk, review, transactions, demo). Every request is validated by Pydantic and checked for role and ownership. Swagger is at `/docs`. One WebSocket pushes live events to the console. The database has 18 tables: core domain (customers, merchants, devices, destinations, products, transactions), ML (predictions, model versions), agent (investigations, evidence), graph (entities, relationships), payments (PayPal orders, payment events) and governance (reviewer decisions, audit logs, settings). Constraints protect integrity, for example amount > 0, a unique idempotency key and a unique capture ID.

## Security in one paragraph

Secrets live only in environment variables. The browser never sees the PayPal secret. Passwords are hashed with bcrypt. Logins give a JWT with a role. Reviewers must re-enter their password and type the transaction ID to decide. Prices are calculated on the server. Every order checks ownership. Rate limits slow down abuse. The audit log is hash-chained, so editing any row is detectable.

## Limitations to state honestly

Synthetic data only; scores are not calibrated; live PayPal Sandbox, webhooks and the Groq path not yet executed; Docker/Render configured but not run; single-process caches; no frontend tests, MFA or load tests.
