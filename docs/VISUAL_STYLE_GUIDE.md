# Visual Style Guide, Cover Brief and Diagram Brief

## 1. Visual style guide (all documents and media)

| Element | Specification | Source in the project |
|---|---|---|
| Primary dark | Midnight navy `#0B1A33` (documents), app background `#05070B` | PDF headers, app `ink-950` |
| Secondary | Navy `#16305A`, graphite cards `#0B0F16` | PDF table headers, app cards |
| Accent | Electric cyan `#00A9CC` (documents) / `#22D3EE` (app) | Rules, links, highlights |
| Risk colours | LOW `#34D399`, MEDIUM `#FBBF24`, HIGH `#FB923C`, CRITICAL `#F43F5E` | App risk badges (`lib/format.ts`) |
| Text | Ink `#1B2433` on light, `#E8EDF5` on dark; muted `#5B6B82` | |
| Typefaces | **Inter** (app UI), **Segoe UI** (PDFs, Windows), **JetBrains Mono / Consolas** for IDs, amounts and code | `index.html`, `build_pdfs.py` |
| IDs and money | Always monospace: `TXN_…`, `CUS_…`, `$1,849.00` | |
| Status language | Always separate **PayPal status** (CREATED / APPROVED / COMPLETED) from **Sentinel status** (CLEARED / HELD / REJECTED) | |
| Honesty labels | "SYNTHETIC DEMO DATA" (amber tag), "DETERMINISTIC FALLBACK", "not configured" | App tags |
| Tone | Plain, specific, confident; no "revolutionary", "first ever" or unverified numbers | |

Logo mark: a shield outline with a dot (`frontend/public/sentinel.svg`), cyan on midnight.

## 2. Project cover image brief (Devpost thumbnail, 3:2, e.g. 1500×1000)

- **Background**: midnight navy `#0B1A33` with a faint grid or dot pattern.
- **Left 55%**: "SENTINEL" in bold Inter (white). Beneath it, "Payment risk intelligence on PayPal" in cyan. One smaller line underneath: "ML · Graph intelligence · AI investigator · Human review".
- **Right 45%**: a stylised network made from the real Demo C ring: four customer nodes linked to one device node and one wallet node, with suspicious edges in `#F43F5E` dashed lines and other edges in muted blue. A small cyan shield sits over the device node.
- **Bottom strip**: a small, neutral "Built with PayPal Sandbox" text label. **Do not use the PayPal logo unless the hackathon brand guidelines allow it** (the rules prohibit third-party trademarks without permission).
- **Avoid**: stock photos of credit cards, padlocks or hooded hackers; fake dashboard numbers.
- **Fastest honest option**: crop the real Network Graph screenshot (`04_network_overview.jpg`) onto the navy background with the title text.

## 3. Architecture diagram brief (for the README / Devpost gallery)

- **Three columns, left to right**:
  - **Browser**: Storefront, Console.
  - **FastAPI backend**: API, Payment gateway, Risk engine, ML, Graph, Agent, Review, Audit.
  - **External**: PayPal Sandbox, Groq (optional), Database, Redis (optional).
- **Arrows**: browser → API (REST + WebSocket); gateway ↔ PayPal (HTTPS); PayPal → API (signed webhooks); agent → Groq; everything → database.
- **Colour coding**: amber for the payment path (gateway, risk, PayPal), green for audit, cyan for browser components.
- **Required labels**: "capture only on LOW or reviewer APPROVE", "PayPal-Request-Id + compare-and-set lock", "agent recommends only".
- **Mark as optional** (dashed outline): Groq, Redis. **Show the live deployment**: Render (backend) and Netlify (frontend).
- **Ready-made versions**: Mermaid in `docs/SENTINEL_TECHNICAL_ARCHITECTURE.md`; SVG in `SENTINEL_DOCUMENTATION/assets/diagrams/architecture.svg`.
