# Screenshot Checklist

Only screens that exist in the app are listed. ✅ means a genuine capture already exists in `SENTINEL_DOCUMENTATION/assets/` (taken from the running app on 31 Oct 2026 at 1440×900). ⬜ means it still needs capturing.

**Before capturing:** reset the database (see the README), sign in as `reviewer@sentinel.dev`, use 1440×900 or 1920×1080 at 100% zoom, and wait for the entrance animations to finish (about 2 s). Never capture `.env`, the PayPal Developer Dashboard credentials page, or a real email inbox.

| # | Screen | Route / how to reach | What must be visible | Status / file |
|---|---|---|---|---|
| 1 | Sign-in | `/login` | Demo account list | ✅ `17_login.jpg` |
| 2 | Main dashboard (Command Centre) | `/console` | KPI row, 30-day volume chart, demo launcher | ✅ `01_command_centre.jpg` |
| 3 | Marketplace | `/shop` | Hero banner, product grid | ✅ `14_shop_catalog.jpg` |
| 4 | Product detail | `/shop/product/PRD_003` | Price, seller, Sentinel note | ✅ `15_product_detail.jpg` |
| 5 | Cart | `/shop/cart` | Single-seller cart, total | ⬜ (capture failed due to rendering; retake) |
| 6 | Checkout, PayPal not configured | `/shop/checkout` as Ben | "PayPal Sandbox is not configured" | ✅ `16_checkout.jpg` |
| 7 | **PayPal Sandbox popup** | Checkout with keys configured | PayPal approval window (Sandbox) | ⬜ **needs Sandbox credentials** |
| 8 | **Payment result: captured (Demo A)** | After approving Demo A | PayPal COMPLETED + capture ID; Sentinel APPROVED_AUTO | ⬜ **needs Sandbox credentials** |
| 9 | **Payment result: held (Demo C)** | After approving Demo C | PayPal APPROVED, "not captured"; Sentinel HELD_FOR_REVIEW | ⬜ **needs Sandbox credentials** |
| 10 | Normal transaction assessment | Demo A → Run risk pipeline → workspace | LOW badge, CLEARED | ⬜ |
| 11 | High-risk assessment + ML explanation | Demo C workspace, left panel | Probability bars, policy notes, SHAP chart | ✅ `06_workspace_top.jpg`, `07_workspace_steps.jpg` |
| 12 | Anomalous transaction (Demo B) | Demo B workspace | MEDIUM, "43.4x average" note | ⬜ |
| 13 | Fraud network graph (overview) | `/console/network` | Ring cluster + circular loop | ✅ `04_network_overview.jpg` |
| 14 | Device neighbourhood | `/console/network?entity=DEV_0147` | Red suspicious edges | ✅ `05_network_device.jpg` |
| 15 | AI investigation report | Demo C workspace, right/bottom | Findings with E-keys, REJECT | ✅ `08_workspace_report.jpg` |
| 16 | Human review screen | Fraud Intelligence `/console/intelligence` | Queue, SHAP, Approve/Reject/Escalate | ✅ `03_fraud_intelligence.jpg` |
| 17 | Decision modal | Workspace → Reject | Reason, password (blurred), typed ID | ⬜ (blur the password) |
| 18 | Transaction history | `/console/transactions` | AG Grid with risk chips | ✅ `02_live_transactions.jpg` |
| 19 | AI Investigations list | `/console/investigations` | Pipeline + runs | ✅ `09_investigations.jpg` |
| 20 | PayPal Payments with real orders | `/console/payments` | Orders with PayPal vs Sentinel status, events with debug IDs | ⬜ (current capture `10_paypal_payments.jpg` is empty) |
| 21 | Model Analytics | `/console/models` | Metrics table, ROC/PR curves | ✅ `11_model_analytics.jpg` |
| 22 | Audit trail | `/console/audit` → Verify hash chain | "Chain intact" banner + log | ✅ `12_audit_centre.jpg` (retake with the banner visible) |
| 23 | Settings | `/console/settings` | Integration status, risk policy | ✅ `13_settings.jpg` |
| 24 | Shopper order history | `/shop/orders` as a shopper | Orders with both statuses | ⬜ **needs Sandbox orders** |

**Priority for Devpost (5–8 images):** 2, 8 (or 6 if PayPal is unavailable), 11, 13, 15, 16, 18, 22.

**Note on capture quality:** the existing captures are 800 px wide (downscaled by the capture tool). For the Devpost gallery, retake key screens at full resolution with the OS screenshot tool (Win+Shift+S).
