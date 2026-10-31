# Demo Video Script (under 3 minutes)

The rules require a **public YouTube video under 3 minutes** showing the project working. Judges are not required to watch past 3:00, so aim for **2:45**.

Everything below uses features that exist in the app. Segment 2 has two versions:

- **Version A (preferred)** needs PayPal Sandbox credentials in `.env`.
- **Version B** is honest about PayPal not being configured. If you use it, say so on camera.

## Before recording

1. **Reset the data** so the numbers match this script. Stop the backend, delete `backend/sentinel.db*` and `backend/model_store/`, then start it again and wait about 60 seconds for seeding.
2. Start the frontend. Use a 1440×900 or 1920×1080 browser window at 100% zoom, in a clean profile with no bookmarks bar.
3. Open two tabs:
   - **Tab 1**: http://localhost:5173/console, signed in as `reviewer@sentinel.dev`.
   - **Tab 2**: http://localhost:5173/shop.
4. For Version A: have your Sandbox **personal** buyer login ready. **Never show the `.env` file, the PayPal secret or the Developer Dashboard credentials page on screen.**
5. Close notifications and hide the taskbar if you can. Record the narration separately if your environment is noisy.

---

## 0:00–0:20 | The problem and Sentinel

| | |
|---|---|
| On screen | Command Centre (Tab 1). Slowly hover over the KPI row and the 30-day volume chart. |
| Action | None, or a slow scroll. |
| Say | "Most fraud checks give a payment a score and move on. But fraud rings are designed to look normal one payment at a time, and a score alone doesn't tell anyone *why*. Sentinel sits between a buyer approving a PayPal payment and the money actually being captured. It decides, with evidence, whether that money should move." |
| Visible result | KPIs, volume chart and the "SYNTHETIC DEMO DATA" label. |
| Tip | Keep the cursor still while you talk. Mention once that the data is synthetic. |

## 0:20–0:45 | Marketplace and PayPal checkout (Demo A)

**Version A (Sandbox configured)**

| | |
|---|---|
| On screen | Command Centre → Demo A → **PayPal checkout**. Sign in as Ava (click her account on the login page). The checkout page shows a total of $76. |
| Action | Click the PayPal button, sign in with the Sandbox buyer and approve. |
| Say | "This is our demo shop. When Ava checks out, our server creates a real PayPal Sandbox order using its own prices. She approves in PayPal, and only then does Sentinel fetch the order back from PayPal, check the amount and that it's hers, and score it. It's low risk, so Sentinel captures it." |
| Visible result | Result page: **PayPal status COMPLETED** with a capture ID on the left, **Sentinel: APPROVED_AUTO, LOW** on the right. |
| Tip | Pre-type nothing. Let the PayPal popup load fully before clicking, and cut out any waiting in editing. |

**Version B (no Sandbox credentials)**

| | |
|---|---|
| On screen | Storefront catalogue, then checkout as Ava showing "PayPal Sandbox is not configured". Then Command Centre → Demo A → **Run risk pipeline**. |
| Say | "In this recording PayPal Sandbox keys aren't configured, and Sentinel never fakes a payment, so the checkout says so. The same risk engine runs here: Ava's $76 order scores 0.006, low risk, cleared for automatic capture." |
| Visible result | Result card: LOW, CLEARED. |

## 0:45–1:15 | Risk scoring and ML explanation (Demo B)

| | |
|---|---|
| On screen | Command Centre → Demo B → **Run risk pipeline** → "Open investigation workspace". |
| Action | Point at the ML risk panel and the SHAP chart on the left. |
| Say | "Ben usually spends about thirty-eight dollars. Now he's buying an eighteen-hundred-dollar laptop on a device he's never used. The model alone says 0.098, which is low. But the policy sees the amount is forty-three times his average and raises it to medium, and SHAP shows exactly which features drove the score. The payment is held for verification. Nothing is captured." |
| Visible result | MEDIUM badge, HELD FOR VERIFICATION, policy note "Amount is 43.4x customer average", SHAP bars. |
| Tip | Zoom in on the SHAP chart in editing so it's readable. |

## 1:15–1:40 | Graph intelligence (Demo C)

| | |
|---|---|
| On screen | Command Centre → Demo C → **Run risk pipeline** → open the workspace. Hover the red dashed edges in the centre graph and click the DEV_0147 node. |
| Say | "Cara's $500 gift card looks fairly ordinary to the model, about 0.31. But the graph shows her phone is an emulator shared with three other accounts, and those accounts send money to flagged mule wallets. The graph policy raises this to high." |
| Visible result | HIGH badge; red suspicious edges; inspector text "Shared by 4 accounts". |
| Tip | Optionally show the Network Graph page for two seconds to reveal the whole ring and the circular payment loop. |

## 1:40–2:05 | AI investigation (Demo C, right panel)

| | |
|---|---|
| On screen | Right panel: the agent steps appear one by one, then the report. Click **INVESTIGATE** if you want to show a fresh run. |
| Say | "High-risk payments are investigated automatically. The agent runs seven tools: transaction history, customer behaviour, the ML prediction, the graph, merchant risk, evidence collection and the report. Every finding has to cite an evidence item a tool produced, and anything that doesn't is removed. It recommends reject, but it can't move money." |
| Visible result | Steps with durations; findings with E-keys; recommendation REJECT. |
| Honesty | If Groq isn't configured, the panel shows "DETERMINISTIC FALLBACK". Say: "Here it's using its rule-based fallback because no LLM key is configured, and it labels that clearly." |

## 2:05–2:35 | Human review and payment decision

| | |
|---|---|
| On screen | Scroll to **Decision & history**. Click **Reject**, type a reason, re-enter the password and type the transaction ID. |
| Say | "A reviewer makes the final call. They re-enter their password and type the transaction ID, so decisions can't happen by accident. If this were a PayPal order, rejecting means it's never captured, and approving is the only way the money moves." |
| Visible result | Decision card: REJECTED, with the reason and outcome. |
| Tip | Speed up the typing in editing, and blur the password field even though it's a demo password. |

## 2:35–3:00 | Audit trail and impact

| | |
|---|---|
| On screen | Audit Centre → **Verify hash chain** ("Chain intact"). Optionally show Model Analytics for 2 seconds. |
| Say | "Every step is in a hash-chained audit log: PayPal responses, risk scores, agent actions and human decisions. If anyone edits a row, verification fails. Sentinel is a prototype on synthetic data and PayPal Sandbox, but the guarantees are tested: nothing is captured twice, and nothing risky is captured without a human." |
| Visible result | Green "Chain intact: N entries verified". |
| End card | Project name, repository URL, "Built for the PayPal AI Hackathon 2026". |

---

## Recording checklist

- [ ] Under 3:00 (target 2:45)
- [ ] Database reset before recording, so the numbers match
- [ ] No secrets, `.env` or Developer Dashboard credentials on screen
- [ ] Synthetic-data disclosure said once
- [ ] PayPal segment: real Sandbox flow, or explicitly stated as not configured
- [ ] Agent mode (LLM or fallback) stated truthfully
- [ ] No copyrighted music; no third-party logos beyond what the app shows
- [ ] Uploaded to YouTube as **Public**; link pasted into Devpost
