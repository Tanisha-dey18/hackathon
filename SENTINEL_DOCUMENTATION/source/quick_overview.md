# Sentinel at a Glance

> A payment protection layer for PayPal checkouts: it decides, with evidence, whether money should move, and keeps a human in charge of irreversible decisions. Hackathon prototype on PayPal Sandbox and synthetic data.

## The problem

Fraud checks usually score one payment at a time and give no reasons. Organised fraud is designed to look normal payment by payment, and a bare score still leaves an analyst to investigate while the customer waits.

## What Sentinel does

1. The demo shop (SENTINEL MERCHANT) creates a real PayPal Orders v2 order on the server, with server-side prices.
2. The buyer approves in PayPal. No money has moved yet.
3. Sentinel fetches the order from PayPal, checks status, amount and ownership, and scores the risk.
4. LOW risk is captured automatically. Anything else is **held**: approved in PayPal, but not captured.
5. For HIGH risk, an AI agent investigates with seven tools and writes an evidence-cited report.
6. A reviewer re-authenticates and approves, rejects or escalates. Only approval triggers capture.
7. Every step is written to a hash-chained audit log.

[[DIAGRAM:architecture]]

## Key results (actual)

| Item | Result |
|---|---|
| Primary model (selected by hold-out PR-AUC) | Random Forest: precision 0.941, recall 0.889, F1 0.914, ROC-AUC 0.939, PR-AUC 0.897 (500-row test set, synthetic) |
| Other models | XGBoost PR-AUC 0.886; Logistic Regression 0.893; Isolation Forest 0.830 |
| Graph findings | 2 shared devices, 1 four-account money loop ($16,064), 2 flagged mule wallets, 4 suspicious clusters |
| Demo C | ML score 0.313 alone; graph raised it to HIGH; agent recommended REJECT with 6 evidence-backed findings |
| Automated tests | 23 passed, 0 failed |

## What makes it different

- Risk is enforced at the PayPal capture step, with idempotency and bypass protection.
- ML, anomaly detection and graph intelligence feed one explainable policy.
- The AI agent must cite evidence and can only recommend.
- PayPal status and Sentinel status are kept separate, so a held payment is never shown as paid.

## Technology

React, TypeScript, Vite, Tailwind, Recharts, React Flow, AG Grid, TanStack Query, PayPal JS SDK · FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL/SQLite, Redis (optional) · scikit-learn, XGBoost, SHAP, pandas, NumPy · NetworkX · LangGraph, Groq · Docker, Render.

## Honest status

| Verified | Not yet verified |
|---|---|
| Full app running locally; 23 tests; UI walkthrough; hold-out ML metrics; PostgreSQL DDL generation | Live PayPal Sandbox capture (no credentials on build machine); Groq LLM path (fallback used); Docker/Render runtime |
