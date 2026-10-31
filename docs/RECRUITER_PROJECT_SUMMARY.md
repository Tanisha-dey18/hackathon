# Sentinel: Recruiter-Friendly Project Summary

## 1. 30-second pitch

"For the PayPal AI Hackathon I built Sentinel, a risk layer for PayPal checkouts. After a buyer approves a payment, and before the money is captured, it scores the payment with a machine-learning model, checks a graph of shared devices and wallets for fraud rings, and holds anything risky for a human. An AI agent builds an evidence-backed case file, but only a reviewer can approve the capture, and every step goes into a tamper-evident audit log."

## 2. 60-second technical explanation

"It's a FastAPI backend with a React and TypeScript frontend. The storefront creates real PayPal Orders v2 orders on the server. When the buyer approves, the backend fetches the order from PayPal, checks the amount and that it belongs to the shopper, and computes 26 point-in-time features. It scores them with the primary model. I train Logistic Regression, Random Forest and XGBoost and pick the one with the best hold-out PR-AUC, which turned out to be Random Forest at 0.914 on synthetic data. There's also an Isolation Forest and SHAP explanations. NetworkX detects shared devices, money loops and clusters, and those signals can push a payment to HIGH. Captures are exactly-once thanks to a database compare-and-set lock plus PayPal-Request-Id. The capture function itself refuses anything that isn't LOW risk or reviewer-approved. High-risk payments go to a LangGraph agent whose findings must cite tool-produced evidence. There are 25 pytest tests, including the payment safety rules."

## 3. Two-minute interview explanation

"The problem I wanted to solve is that fraud checks usually score one payment at a time, and organised fraud is designed to look normal at that level. Also, a score with no explanation still leaves a person to investigate.

PayPal's Orders API separates buyer approval from capture, and that gap is where I put Sentinel. On approval, I fetch the order back from PayPal and verify it. Then I run three kinds of analysis. First, a supervised model on point-in-time features; I was careful to compute features only from earlier transactions and to use the same code for training and serving. Second, an anomaly percentile from an Isolation Forest. Third, graph signals from NetworkX. A policy maps the score to LOW, MEDIUM, HIGH or CRITICAL, and escalation rules can only raise risk.

The part I'm proudest of is the safety design. A payment can't be captured twice: the database lock means only one request ever calls PayPal, and the stable request ID covers retries. It can't bypass review either, because the capture function re-checks authorisation itself, and there are tests that call it directly to prove that. PayPal's status and my risk status are stored separately, so a held payment never looks paid.

For the AI investigator I used LangGraph. The tools generate evidence items, the LLM can only cite them, and a validator removes uncited claims. Without an API key it falls back to a rule-based report and labels it that way.

The limitations are honest ones. The data is synthetic, and I still need to run the live Sandbox and Groq paths with real credentials. Next I'd validate on real data, calibrate the scores and move the in-process caches to Redis so it can scale."

## 4. Resume bullets

- Built **Sentinel**, a FastAPI + React payment risk layer that gates **PayPal Orders v2** captures. It provides exactly-once capture (DB compare-and-set lock + PayPal-Request-Id), ownership and amount verification, and human approval for high-risk payments; backed by 25 automated tests.
- Engineered 26 **point-in-time features** and compared Random Forest, XGBoost, Logistic Regression and Isolation Forest, selecting by hold-out **PR-AUC (0.914 on synthetic data)**, with **SHAP** explanations rendered as reviewer-readable reasons.
- Implemented **NetworkX** fraud-ring detection (shared devices, money cycles, clusters) and a **LangGraph** investigation agent with 7 tools and evidence-validated reports; added a SHA-256 hash-chained audit log.

## 5. LinkedIn project description

**Sentinel: AI payment risk intelligence on PayPal (PayPal AI Hackathon 2026)**
I built a risk layer that sits between a buyer approving a PayPal payment and the merchant capturing it. It combines an ML model with SHAP explanations, an anomaly detector, and graph analysis that finds fraud rings through shared devices and mule wallets. A LangGraph AI investigator writes reports in which every claim has to cite real evidence. Risky payments are held until a reviewer approves, captures are exactly-once, and everything is recorded in a tamper-evident audit log.
Stack: FastAPI, SQLAlchemy, React/TypeScript, scikit-learn, XGBoost, SHAP, NetworkX, LangGraph, PayPal Orders API (Sandbox), AG Grid, React Flow. Built on synthetic data.

## 6. GitHub repository description

AI payment risk layer for PayPal Sandbox: ML + SHAP, graph fraud-ring detection, LangGraph investigator, human-approved capture, hash-chained audit. FastAPI + React.

## 7. Individual technical contributions (repository evidence)

What the repository shows:

- All commits are authored by **Tanisha Dey**; the README Team table lists her as the sole developer.
- Commit trailers record that the code was written with **AI pair-programming assistance (Claude)**.

Areas you can present as your work, and should be able to explain line by line:

| Area | Evidence in repo |
|---|---|
| Backend API design (REST + WebSocket, RBAC) | `backend/app/main.py`, `routers/`, `security.py` |
| PayPal payment lifecycle and capture safety | `backend/app/paypal/client.py`, `services/payments.py`, `tests/test_payments.py` |
| ML pipeline and explanations | `backend/app/ml/` (features, train, explain, predictor) |
| Graph intelligence | `backend/app/graph/engine.py` |
| Agentic AI investigator | `backend/app/agent/tools.py`, `agent/workflow.py` |
| Data model and migrations | `backend/app/models.py`, `alembic/versions/0001_initial_schema.py` |
| Frontend product | `frontend/src/pages/`, `components/GraphView.tsx` |

> Honesty note: the hackathon rules allow third-party technical assistance but require the submission to be your own ideas and work product, and winners' roles are verified. In interviews, be ready to explain every design decision. If you are asked how you built the project, say plainly that you used an AI coding assistant.
