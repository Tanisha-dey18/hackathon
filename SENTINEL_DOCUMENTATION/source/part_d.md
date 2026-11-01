# PART 19: Interview and Viva Preparation

Each question has a **short answer** (say this first), a **deeper explanation** (use it if they want more), and sometimes a **likely follow-up**. Answers describe the implementation as it actually is, including what was not verified.

## 19.1 Non-technical questions (20)

### Q1. What is Sentinel in one sentence?
**Short answer:** A layer that checks every PayPal checkout for fraud risk before the money is collected, and holds risky payments for a human.
**Deeper explanation:** It sits between the buyer approving in PayPal and the capture. Normal payments go through automatically; suspicious ones are explained, investigated by an AI agent and decided by a reviewer.
**Follow-up:** Why between approval and capture? Because that is the last moment you can stop money moving without refunding.

### Q2. What problem are you solving?
**Short answer:** Stopping fraudulent payments before they are captured, without blocking genuine customers, and explaining every decision.
**Deeper explanation:** Single-payment scores miss organised fraud and give no reasons. Sentinel adds relationship analysis, explanations, an investigator and human control.

### Q3. Who would use it?
**Short answer:** Merchants and their risk teams.
**Deeper explanation:** Shoppers use the storefront; reviewers and analysts use the console; admins tune the policy and retrain models.

### Q4. Why does fraud matter to a merchant?
**Short answer:** Fraudulent sales usually come back as chargebacks, so the merchant loses the goods, the money and fees.
**Deeper explanation:** Blocking too much is also costly, because genuine customers leave. The goal is balance, which is why Sentinel holds rather than declines.

### Q5. What does "held" mean for the customer?
**Short answer:** They approved the payment in PayPal, but no money has been taken yet.
**Deeper explanation:** The screen says the payment is under review and funds have not been captured. If approved, it is captured; if rejected, nothing is taken.

### Q6. What makes Sentinel different from a normal fraud filter?
**Short answer:** It looks at relationships between accounts, explains itself and keeps a human in control of irreversible actions.
**Deeper explanation:** In our demo C the model scored a payment at about 0.33, but the graph showed a shared emulator device and mule wallets, and the system raised it to HIGH.

### Q7. Where is the AI?
**Short answer:** In three places: the ML risk model, the anomaly detector and the investigation agent.
**Deeper explanation:** SHAP explains the model, and graph analysis provides network signals. The agent uses tools and writes an evidence-cited report.

### Q8. Does the AI make the final decision?
**Short answer:** No. It only recommends.
**Deeper explanation:** The agent has no payment tools. Reviewers must re-enter their password and type the transaction ID to decide.

### Q9. Is this used by PayPal?
**Short answer:** No. It is a hackathon prototype built on public PayPal Sandbox APIs and synthetic data.
**Deeper explanation:** It does not use or claim access to PayPal's internal fraud systems.

### Q10. Is real customer data used?
**Short answer:** No. All customers, merchants, devices and history are generated.
**Deeper explanation:** The generator is deterministic and labels its own fraud patterns. That makes demos reproducible but means accuracy claims are limited to synthetic data.

### Q11. What was the hardest part?
**Short answer:** Making the payment flow safe: no double captures, no bypassing review, and honest status.
**Deeper explanation:** That needed a compare-and-set lock, PayPal request IDs, ownership and amount checks, and separate PayPal and Sentinel status fields.

### Q12. What does a reviewer see?
**Short answer:** The transaction, the model's reasons, a relationship graph and the AI report with evidence.
**Deeper explanation:** Plus an evidence timeline, the decision history and the audit trail, all in one workspace.

### Q13. Why not just block suspicious payments automatically?
**Short answer:** Because false positives hurt genuine customers.
**Deeper explanation:** Holding gives a human the chance to verify. The policy is configurable if a business wants a stricter setup.

### Q14. How do you know it works?
**Short answer:** 26 automated tests pass, and the models are evaluated on held-out data.
**Deeper explanation:** Hold-out PR-AUC of the primary model is 0.914 on synthetic data. Live PayPal Sandbox and Groq paths have not yet been run with real credentials.

### Q15. What happens if PayPal is down?
**Short answer:** Sentinel returns a clear error with PayPal's debug ID and never pretends a payment succeeded.
**Deeper explanation:** If credentials are missing it returns 503 and the checkout explains the setup. Failed captures are marked `CAPTURE_FAILED` and can be retried safely.

### Q16. How long does a risk check take?
**Short answer:** Each assessment's latency is measured and stored; the dashboard shows the average.
**Deeper explanation:** On the development laptop the median was about 175 ms over 8 consecutive assessments; the first one after start-up takes about 0.7 s while the model and SHAP explainer load. That's a micro-benchmark, not a load test.

### Q17. What is the audit trail and why does it matter?
**Short answer:** A record of every action that is hash-chained, so changes are detectable.
**Deeper explanation:** Each entry includes the previous entry's hash. A verify button recomputes the chain; our test proves a modified row is detected.

### Q18. What would a judge see in three minutes?
**Short answer:** A normal payment cleared, an unusual one held with explanations, and a fraud ring found by the graph, investigated and rejected.
**Deeper explanation:** With credentials, A and C run through real PayPal Sandbox checkout.

### Q19. What did you learn?
**Short answer:** That safety in payments is mostly state management, and that AI is most useful when it is constrained.
**Deeper explanation:** Evidence validation and human-in-the-loop design mattered more than the choice of model.

### Q20. What would you do next?
**Short answer:** Run live Sandbox and Groq tests, then validate on real fraud data.
**Deeper explanation:** Then calibration, monitoring, an AUTHORIZE-intent flow and scaling the event system.

## 19.2 Technical questions (30)

### Q21. Describe the architecture.
**Short answer:** A React SPA, a FastAPI backend with risk, ML, graph and agent services, a relational database, and PayPal Sandbox.
**Deeper explanation:** REST plus one WebSocket; SQLAlchemy with Alembic; PostgreSQL in Docker/Render and SQLite locally; optional Redis for rate limiting; optional Groq for the LLM.

### Q22. Why FastAPI?
**Short answer:** Typed validation with Pydantic, automatic Swagger and native WebSockets in Python.
**Deeper explanation:** Python lets the API, ML and graph code share one process and one codebase.

### Q23. How does the frontend stay live?
**Short answer:** One authenticated WebSocket; events invalidate TanStack Query caches.
**Deeper explanation:** For example a `payment.updated` event refreshes orders, events and the transaction detail.

### Q24. How do background threads push WebSocket messages?
**Short answer:** The server's event loop is saved at start-up and threads use `asyncio.run_coroutine_threadsafe`.
**Deeper explanation:** The agent and simulator run in threads, so they cannot await directly.

### Q25. How is authentication done?
**Short answer:** bcrypt-hashed passwords and HS256 JWTs.
**Deeper explanation:** Role checks are FastAPI dependencies; the WebSocket validates the token from the query string and requires a staff role.

### Q26. What roles exist?
**Short answer:** ADMIN, REVIEWER, ANALYST and CUSTOMER.
**Deeper explanation:** Analysts read and investigate, reviewers decide, admins change policy, retrain and decide escalations, customers shop.

### Q27. How do you prevent a held payment from being captured?
**Short answer:** The capture function itself checks authorisation: LOW risk for automatic, or a stored APPROVE decision.
**Deeper explanation:** Even a direct call with `REVIEWER` authorisation is refused without a decision record. A test calls it directly and expects 409.

### Q28. How do you prevent duplicate captures?
**Short answer:** A database compare-and-set lock plus a stable PayPal-Request-Id.
**Deeper explanation:** `UPDATE ... SET capture_state='IN_PROGRESS' WHERE capture_state IN ('NONE','FAILED')`; only the winner calls PayPal. `ORDER_ALREADY_CAPTURED` is reconciled by reading the order.

### Q29. What is idempotency?
**Short answer:** Doing the same request twice has the same effect as doing it once.
**Deeper explanation:** Network retries and double clicks are normal, so payment APIs must be idempotent.

### Q30. How are prices protected?
**Short answer:** The server recalculates prices from its catalogue; the client total is display-only.
**Deeper explanation:** On approval, PayPal's amount must match the stored amount, otherwise the order is marked `INTEGRITY_FAILED`.

### Q31. Why can a cart only contain one seller?
**Short answer:** Each checkout creates one PayPal purchase unit and one transaction paying one merchant.
**Deeper explanation:** That keeps merchant risk and destination features meaningful. Multi-seller carts would need split payments.

### Q32. How is the transaction ID generated?
**Short answer:** Prefix plus a base-36 timestamp plus 3 random characters, for example `TXN_56SIN7VDWC`.
**Deeper explanation:** Synthetic history uses sequential IDs like `TXN_100542`.

### Q33. How does the risk policy work?
**Short answer:** Thresholds map probability to a level; escalation rules can only raise it.
**Deeper explanation:** LOW < 0.30 <= MEDIUM < 0.70 <= HIGH < 0.90 <= CRITICAL. Anomaly >= 0.98 or amount >= 10x average gives at least MEDIUM; graph signals give at least HIGH.

### Q34. Can the policy be changed?
**Short answer:** Yes, by an ADMIN in Settings; changes are validated and audited.
**Deeper explanation:** Thresholds must be strictly increasing; old and new values are stored in the audit log.

### Q35. What is stored for each prediction?
**Short answer:** Probability, anomaly and graph scores, level, action, top factors, SHAP values, features, policy notes and latency.
**Deeper explanation:** This lets you reconstruct exactly why a decision was made, even after a model is retrained.

### Q36. How do you handle model versions?
**Short answer:** Each training run creates a version with one row per algorithm; one is marked primary.
**Deeper explanation:** Artifacts are stored as joblib bundles; old versions remain. If the active artifact is missing at start-up, the backend retrains.

### Q37. How does the audit hash chain work?
**Short answer:** Each row's hash is SHA-256 over its content and the previous hash.
**Deeper explanation:** Verification reads rows in order (bypassing cached objects) and recomputes. A modified row breaks the chain at that row.

### Q38. Why store PayPal events separately?
**Short answer:** To keep a raw record of every PayPal response and webhook.
**Deeper explanation:** It includes HTTP status and `paypal-debug-id`, which PayPal support asks for.

### Q39. How is rate limiting implemented?
**Short answer:** Fixed windows in Redis if configured, otherwise a sliding window in memory.
**Deeper explanation:** Login 10/min, create-order and capture 20/min, webhook 300/min, general default configurable.

### Q40. How do you handle CORS?
**Short answer:** An explicit allow-list from `CORS_ORIGINS`, limited methods and headers.
**Deeper explanation:** Allowed headers are Authorization, Content-Type and Idempotency-Key.

### Q41. How are secrets kept out of logs?
**Short answer:** A logging filter redacts bearer tokens, client secrets and access tokens.
**Deeper explanation:** The PayPal secret is only used for OAuth with HTTP basic auth.

### Q42. How is the system deployed?
**Short answer:** Docker Compose locally, or a Render Blueprint with managed PostgreSQL.
**Deeper explanation:** The live demo runs the backend on Render's free plan (a Docker image that seeds and trains at build time and uses SQLite) and the frontend on Netlify. Docker Compose with PostgreSQL is configured for local use but was not run on the build machine.

### Q43. What happens on first start?
**Short answer:** Migrations run, the synthetic world is generated, models are trained and history is scored.
**Deeper explanation:** About 30 to 60 seconds on the development laptop.

### Q44. How are migrations handled?
**Short answer:** Alembic, run programmatically at start-up.
**Deeper explanation:** One initial migration creates 18 tables; offline SQL generation for PostgreSQL was checked.

### Q45. How did you test PayPal without credentials?
**Short answer:** With an httpx `MockTransport` that emulates PayPal Sandbox endpoints, in tests only.
**Deeper explanation:** It implements OAuth, order create/get/capture with request-ID idempotency, already-captured errors and webhook verification. The live Sandbox path still needs a real run.

### Q46. How does the graph explorer layout work?
**Short answer:** Kamada-Kawai layout per connected component, computed on the server.
**Deeper explanation:** Coordinates are returned with the nodes; React Flow renders them and fits the view after nodes are measured.

### Q47. Why AG Grid?
**Short answer:** Filtering, sorting, quick search, pagination and CSV export over thousands of rows.
**Deeper explanation:** We used the Community edition; row grouping is Enterprise, so we used risk filter chips.

### Q48. What would break first at scale?
**Short answer:** The in-process feature state, graph cache and WebSocket fan-out.
**Deeper explanation:** They assume one process. You would need a shared feature store, a graph store and pub/sub.

### Q49. How would you scale to millions of transactions?
**Short answer:** Stream ingestion, a shared online feature store, a model-serving tier, incremental graph updates in a graph database, and a message bus for events.
**Deeper explanation:** Keep the capture lock in the database, partition by customer, cache graph signals per entity, and run investigations asynchronously from a queue.

### Q50. What is the biggest technical debt?
**Short answer:** Single-process caches and untested live integrations.
**Deeper explanation:** Plus no frontend tests and uncalibrated probabilities.

## 19.3 Machine learning questions (15)

### Q51. Why did you choose XGBoost?
**Short answer:** It is a strong default for tabular data, but Sentinel does not force it: the primary model is whichever has the best PR-AUC.
**Deeper explanation:** In v1 Random Forest won (0.914) narrowly over Logistic Regression (0.911) and XGBoost (0.903). We report that honestly.
**Follow-up:** Why might XGBoost lose here? The data is small (1,500 training rows), and bagging is more stable on small, noisy data.

### Q52. Why is accuracy insufficient for fraud detection?
**Short answer:** With 7% fraud, predicting "never fraud" is 93% accurate and useless.
**Deeper explanation:** Precision, recall and PR-AUC focus on the rare class.

### Q53. What is the difference between precision and recall?
**Short answer:** Precision is how many flagged payments are really fraud; recall is how much fraud we flag.
**Deeper explanation:** Raising the threshold usually increases precision and lowers recall. The primary model had precision 0.970 and recall 0.889 at 0.5.

### Q54. Why PR-AUC over ROC-AUC for selection?
**Short answer:** PR-AUC reflects performance on the rare class; ROC-AUC can look good because there are so many true negatives.
**Deeper explanation:** Logistic Regression had the best ROC-AUC (0.964) but lower precision (0.842).

### Q55. How did you handle class imbalance?
**Short answer:** Class weights for LR and RF, `scale_pos_weight` for XGBoost, and stratified splitting.
**Deeper explanation:** No oversampling such as SMOTE was used, which avoids creating synthetic minority points.

### Q56. What is data leakage and how did you avoid it?
**Short answer:** Using information that would not be available at prediction time.
**Deeper explanation:** Features use only earlier transactions; imputation is fitted on training data; labels are never features; the destination "flagged" status is external intelligence, not derived from labels.

### Q57. Explain point-in-time features.
**Short answer:** Each transaction's features are computed from history before its timestamp.
**Deeper explanation:** The same `FeatureState` class is used in training (replay) and serving (state from the database), so definitions match.

### Q58. How do you handle missing values?
**Short answer:** Keep them as NaN and impute the training median inside each pipeline.
**Deeper explanation:** First-time customers have no average, previous location or interval. `is_first_txn` makes that explicit.

### Q59. What is Isolation Forest used for?
**Short answer:** An unsupervised anomaly percentile used by the policy and shown to reviewers.
**Deeper explanation:** It is trained without labels; its PR-AUC (0.862) is reported for transparency.

### Q60. What is SHAP?
**Short answer:** A method that splits a prediction into per-feature contributions based on Shapley values.
**Deeper explanation:** TreeExplainer for tree models, LinearExplainer for LR; positive contributions become reviewer-readable sentences.
**Follow-up:** What space are the values in? Probability for Random Forest; log-odds for XGBoost and LR.

### Q61. What are the most important features?
**Short answer:** Amount, log amount, hour of day, distance from home and night-time.
**Deeper explanation:** Hour and night rank high because the synthetic ring operates at night, a generator artefact we disclose.

### Q62. Are your probabilities calibrated?
**Short answer:** No; they are risk scores.
**Deeper explanation:** Class weighting shifts them. Isotonic or Platt calibration is future work.

### Q63. What happens if the model wrongly flags a genuine customer?
**Short answer:** The payment is held, not declined, and a reviewer can approve it, which captures the payment.
**Deeper explanation:** That approval is recorded and becomes a "legitimate" label for the next retraining.

### Q64. How would you evaluate on real data?
**Short answer:** Out-of-time validation, cost-weighted metrics and monitoring after launch.
**Deeper explanation:** Train on earlier months, test on later months, and choose thresholds by expected loss rather than F1.

### Q65. How is the model retrained?
**Short answer:** ADMIN triggers `POST /api/models/retrain`; a new version is created.
**Deeper explanation:** Labels come from synthetic ground truth and reviewer decisions on live payments.

## 19.4 Backend and database questions (15)

### Q66. Why SQLAlchemy and not raw SQL?
**Short answer:** One model layer for PostgreSQL and SQLite with type safety.
**Deeper explanation:** It still allows explicit atomic updates like the capture lock.

### Q67. Why both PostgreSQL and SQLite?
**Short answer:** PostgreSQL for deployment, SQLite for zero-setup local runs.
**Deeper explanation:** Render provides `postgres://` URLs, which the config converts for the psycopg 3 driver.

### Q68. What constraints protect data integrity?
**Short answer:** Foreign keys, check constraints and unique keys.
**Deeper explanation:** Examples: amount > 0, allowed statuses, allowed roles, unique PayPal order ID, idempotency key, capture ID and webhook event ID.

### Q69. Why is `transaction_id` unique in `paypal_orders`?
**Short answer:** One Sentinel transaction maps to exactly one PayPal order.
**Deeper explanation:** It prevents two orders paying for the same transaction.

### Q70. How do you store JSON?
**Short answer:** SQLAlchemy JSON columns.
**Deeper explanation:** Used for metrics, SHAP values, features, policy notes, investigation steps, reports and raw PayPal payloads.

### Q71. How are timestamps handled?
**Short answer:** Timezone-aware UTC.
**Deeper explanation:** SQLite drops timezone info, so an `aware()` helper re-attaches UTC.

### Q72. What indexes exist?
**Short answer:** On foreign keys, statuses, risk levels and composite customer+time and device+time.
**Deeper explanation:** The composite indexes support history queries for features and tools.

### Q73. How are errors returned?
**Short answer:** Consistent JSON with appropriate HTTP status codes.
**Deeper explanation:** 422 has a structured `errors` list; 502 for PayPal errors includes the debug ID; unhandled errors return a generic 500.

### Q74. How are long-running tasks handled?
**Short answer:** Background threads for investigations, the simulator and retraining.
**Deeper explanation:** Each uses its own database session. A queue (Celery, RQ) would be the production choice.

### Q75. How do you avoid two investigations of the same transaction?
**Short answer:** If one is RUNNING, its ID is returned instead of starting another.
**Deeper explanation:** The test for demo C relies on this deduplication.

### Q76. How does `GET /api/transactions/{id}` build the case?
**Short answer:** It joins the transaction, related entities, predictions, investigations, decisions, PayPal order, events and audit rows.
**Deeper explanation:** That single call powers the workspace's left and bottom panels.

### Q77. How is the latest prediction per transaction selected?
**Short answer:** A subquery on `max(id)` grouped by transaction.
**Deeper explanation:** Used by lists, the review queue and the graph engine.

### Q78. What happens if a decision call fails halfway?
**Short answer:** Decision and audit are committed before the capture, so the record exists even if PayPal fails.
**Deeper explanation:** A failed capture sets `CAPTURE_FAILED`; the lock moves to FAILED and allows a safe retry with the same PayPal-Request-Id.

### Q79. Why is the webhook handler run in a thread pool?
**Short answer:** It reads the raw body asynchronously, then runs blocking database and HTTP code in a worker thread.
**Deeper explanation:** This keeps the event loop free.

### Q80. What found a bug late in development?
**Short answer:** Copying `.env.example` to `.env` made `DATABASE_URL` blank and broke start-up.
**Deeper explanation:** Fixed with `env_ignore_empty=True` in the settings, so blank values fall back to defaults.
