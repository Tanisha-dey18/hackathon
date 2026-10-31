"""Architecture diagrams for the Sentinel documentation, drawn with reportlab.graphics.

Every diagram reflects the implemented system (see backend/app and frontend/src)."""
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String, Group, Circle
from reportlab.lib.colors import HexColor, white

NAVY = HexColor("#0B1A33")
NAVY2 = HexColor("#16305A")
CYAN = HexColor("#00A9CC")
CYAN_L = HexColor("#E3F6FB")
GREY = HexColor("#5B6B82")
LINE = HexColor("#9FB0C6")
SOFT = HexColor("#F2F6FA")
AMBER = HexColor("#D98A00")
AMBER_L = HexColor("#FFF4DD")
RED = HexColor("#D2344D")
RED_L = HexColor("#FDE8EC")
GREEN = HexColor("#1F9D6B")
GREEN_L = HexColor("#E3F6EE")

F, FB, FM = "Body", "Body-Bold", "Mono"


def _text(d, x, y, s, size=7.5, font=F, color=NAVY, anchor="middle", bg=False):
    if bg:  # white backing so lines never cross a label
        from reportlab.pdfbase.pdfmetrics import stringWidth
        w = stringWidth(s, font, size)
        x0 = x - w / 2 if anchor == "middle" else x - w if anchor == "end" else x
        d.add(Rect(x0 - 1.5, y - 2, w + 3, size + 1.5, fillColor=white, strokeColor=None, strokeWidth=0))
    d.add(String(x, y, s, fontName=font, fontSize=size, fillColor=color, textAnchor=anchor))


def box(d, x, y, w, h, title, lines=(), fill=SOFT, stroke=NAVY2, title_color=NAVY, size=7.6, radius=4):
    d.add(Rect(x, y, w, h, rx=radius, ry=radius, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))
    n = len(lines)
    total = 10 + n * 8.6
    ty = y + h / 2 + total / 2 - 8
    _text(d, x + w / 2, ty, title, size, FB, title_color)
    for i, ln in enumerate(lines):
        _text(d, x + w / 2, ty - 10 - i * 8.6, ln, size - 1.1, F, GREY)


def arrow(d, x1, y1, x2, y2, color=GREY, width=0.9, label=None, label_dx=0, label_dy=3, dash=None, both=False):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width, strokeDashArray=dash))
    import math
    ang = math.atan2(y2 - y1, x2 - x1)

    def head(px, py, a):
        s = 4.2
        p1 = (px - s * math.cos(a - 0.4), py - s * math.sin(a - 0.4))
        p2 = (px - s * math.cos(a + 0.4), py - s * math.sin(a + 0.4))
        d.add(Polygon([px, py, p1[0], p1[1], p2[0], p2[1]], fillColor=color, strokeColor=color, strokeWidth=0.3))

    head(x2, y2, ang)
    if both:
        head(x1, y1, ang + math.pi)
    if label:
        _text(d, (x1 + x2) / 2 + label_dx, (y1 + y2) / 2 + label_dy, label, 6.3, F, GREY, bg=True)


def panel(d, x, y, w, h, title, fill=white):
    d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=LINE, strokeWidth=0.8, strokeDashArray=[3, 2]))
    _text(d, x + 8, y + h - 12, title, 8, FB, CYAN, anchor="start")


# --------------------------------------------------------------------------- 1
def architecture(W=482):
    d = Drawing(W, 330)
    panel(d, 4, 4, 120, 322, "BROWSER")
    box(d, 14, 214, 100, 70, "SENTINEL MERCHANT", ["Catalogue, cart", "PayPal JS SDK", "Buttons"], fill=CYAN_L)
    box(d, 14, 104, 100, 90, "Sentinel console", ["Command Centre", "Investigation", "workspace", "Graph, models, audit"], fill=CYAN_L)
    box(d, 14, 24, 100, 60, "React + TS", ["TanStack Query", "React Flow, Recharts", "AG Grid"], fill=white)

    panel(d, 136, 4, 214, 322, "FASTAPI BACKEND")
    box(d, 146, 272, 194, 36, "REST API + WebSocket /ws/transactions", ["JWT auth, RBAC, rate limits, validation"], fill=white)
    box(d, 146, 214, 94, 46, "Payment gateway", ["capture state machine", "idempotency"], fill=AMBER_L)
    box(d, 246, 214, 94, 46, "Risk engine", ["thresholds +", "escalations"], fill=AMBER_L)
    box(d, 146, 156, 94, 46, "ML predictor", ["RF / XGB / LR", "IsoForest + SHAP"])
    box(d, 246, 156, 94, 46, "Graph engine", ["NetworkX", "rings, loops, clusters"])
    box(d, 146, 98, 94, 46, "Review service", ["re-auth, RBAC", "approve/reject/esc."])
    box(d, 246, 98, 94, 46, "Investigation agent", ["LangGraph, 7 tools", "Groq or fallback"])
    box(d, 146, 24, 194, 60, "Hash-chained audit log", ["every risk, payment, agent and", "reviewer action (SHA-256 chain)"], fill=GREEN_L)

    panel(d, 362, 4, 116, 322, "EXTERNAL")
    box(d, 372, 236, 96, 64, "PayPal Sandbox", ["OAuth, Orders v2", "Capture, Webhook", "verification"], fill=AMBER_L)
    box(d, 372, 160, 96, 56, "Groq API", ["LLM tool calling", "(optional)"])
    box(d, 372, 84, 96, 56, "Database", ["PostgreSQL (Docker,", "Render) / SQLite"])
    box(d, 372, 24, 96, 44, "Redis", ["rate limits (optional)"])

    arrow(d, 114, 249, 146, 290, CYAN, label="")
    arrow(d, 114, 149, 146, 283, CYAN)
    arrow(d, 146, 278, 114, 160, CYAN, dash=[2, 2])
    _text(d, 128, 222, "REST", 6, F, CYAN, bg=True)
    _text(d, 128, 172, "WS", 6, F, CYAN, bg=True)
    arrow(d, 240, 237, 246, 237)
    arrow(d, 293, 214, 293, 202)
    arrow(d, 193, 214, 193, 202)
    arrow(d, 280, 214, 223, 202)
    arrow(d, 293, 144, 293, 156)
    arrow(d, 270, 144, 215, 156)
    arrow(d, 340, 237, 372, 262, AMBER, label="")
    arrow(d, 372, 248, 340, 228, AMBER, dash=[2, 2])
    _text(d, 356, 262, "HTTPS", 6, F, AMBER, bg=True)
    arrow(d, 340, 121, 372, 180, GREY)
    arrow(d, 340, 54, 372, 108, GREY)
    arrow(d, 340, 290, 372, 46, GREY, dash=[2, 2])
    return d


# --------------------------------------------------------------------------- 2
def sequence(W=482):
    actors = ["Buyer", "Storefront", "Sentinel API", "Risk + Graph", "PayPal", "Reviewer"]
    H = 430
    d = Drawing(W, H)
    xs = [40 + i * (W - 80) / (len(actors) - 1) for i in range(len(actors))]
    for x, a in zip(xs, actors):
        box(d, x - 36, H - 26, 72, 20, a, fill=CYAN_L if a != "PayPal" else AMBER_L)
        d.add(Line(x, H - 26, x, 14, strokeColor=LINE, strokeWidth=0.7, strokeDashArray=[3, 2]))
    msgs = [
        (0, 1, "Checkout (PayPal button)"),
        (1, 2, "POST create-order + Idempotency-Key"),
        (2, 4, "POST /v2/checkout/orders (server prices)"),
        (4, 2, "order CREATED"),
        (0, 4, "Approves in PayPal popup"),
        (1, 2, "POST capture-order {order_id}"),
        (2, 4, "GET /v2/checkout/orders/{id}"),
        (4, 2, "APPROVED (amount, reference)"),
        (2, 3, "features, ML, anomaly, graph"),
        (3, 2, "risk level + explanation"),
    ]
    y = H - 46
    for a, b, label in msgs:
        col = AMBER if 4 in (a, b) else NAVY2
        arrow(d, xs[a], y, xs[b], y, col, label=label, label_dy=3)
        y -= 25
    # alt LOW
    d.add(Rect(18, y - 26, W - 36, 30, fillColor=GREEN_L, strokeColor=GREEN, strokeWidth=0.6))
    _text(d, 24, y - 4, "alt LOW", 6.6, FB, GREEN, anchor="start")
    arrow(d, xs[2], y - 14, xs[4], y - 14, AMBER, label="POST capture (PayPal-Request-Id, CAS lock) -> COMPLETED", label_dy=3)
    y -= 40
    d.add(Rect(18, y - 74, W - 36, 78, fillColor=AMBER_L, strokeColor=AMBER, strokeWidth=0.6))
    _text(d, 24, y - 4, "else MEDIUM / HIGH / CRITICAL", 6.6, FB, AMBER, anchor="start")
    _text(d, xs[2] + 4, y - 16, "hold: PayPal stays APPROVED, nothing captured; agent investigates", 6.4, F, GREY, anchor="start")
    arrow(d, xs[5], y - 34, xs[2], y - 34, NAVY2, label="APPROVE / REJECT / ESCALATE (password + confirm)", label_dy=3)
    arrow(d, xs[2], y - 58, xs[4], y - 58, AMBER, label="capture only on APPROVE", label_dy=3)
    y -= 92
    arrow(d, xs[4], y, xs[2], y, AMBER, dash=[3, 2], label="signed webhook -> verify-webhook-signature", label_dy=3)
    return d


# --------------------------------------------------------------------------- 3
def mlpipeline(W=482):
    d = Drawing(W, 250)
    _text(d, 6, 238, "TRAINING (seed / retrain)", 7.5, FB, CYAN, anchor="start")
    steps = [("Synthetic", ["2,000 labelled", "transactions"]), ("Point-in-time", ["26 features", "FeatureState"]),
             ("Cleaning", ["dedupe, clip,", "keep NaN"]), ("Split", ["stratified", "75 / 25"]),
             ("Train 4 models", ["class weights", "median impute"]), ("Evaluate", ["hold-out only", "P/R/F1/ROC/PR"]),
             ("Select", ["best PR-AUC", "-> primary"])]
    bw, gap = 61, 7.5
    for i, (t, ls) in enumerate(steps):
        x = 4 + i * (bw + gap)
        box(d, x, 176, bw, 50, t, ls, fill=CYAN_L if i in (1, 6) else SOFT, size=7)
        if i:
            arrow(d, x - gap, 201, x, 201)
    box(d, 140, 120, 200, 40, "Models trained every run", ["Logistic Regression · Random Forest · XGBoost", "Isolation Forest (unsupervised)"], fill=white, size=7)
    arrow(d, 4 + 4 * (bw + gap) + bw / 2, 176, 300, 160)
    box(d, 360, 120, 118, 40, "joblib bundle", ["model_versions rows", "metrics + SHAP importance"], fill=GREEN_L, size=7)
    arrow(d, 4 + 6 * (bw + gap) + bw / 2, 176, 420, 160)

    _text(d, 6, 100, "LIVE SCORING (every assessment)", 7.5, FB, CYAN, anchor="start")
    live = [("Transaction", ["checkout / demo /", "simulator"]), ("Features", ["same FeatureState", "history only"]),
            ("Primary model", ["fraud probability"]), ("IsoForest", ["anomaly", "percentile"]), ("SHAP", ["top factors", "as sentences"]),
            ("Policy", ["thresholds +", "escalations"]), ("Store + audit", ["fraud_predictions", "WebSocket event"])]
    for i, (t, ls) in enumerate(live):
        x = 4 + i * (bw + gap)
        box(d, x, 34, bw, 50, t, ls, fill=AMBER_L if i == 5 else SOFT, size=7)
        if i:
            arrow(d, x - gap, 59, x, 59)
    _text(d, W / 2, 14, "Graph signals (shared device, flagged destination, cycle) enter at the Policy step and can only raise risk.", 6.6, F, GREY)
    return d


# --------------------------------------------------------------------------- 4
def agent(W=482):
    d = Drawing(W, 360)
    nodes = [("retrieve_transaction", "TransactionHistoryTool"), ("customer_behaviour", "CustomerBehaviourTool"),
             ("ml_prediction", "FraudPredictionTool"), ("graph_investigation", "GraphInvestigationTool"),
             ("merchant_risk", "MerchantRiskTool"), ("collect_evidence", "EvidenceCollectionTool  ->  E1..En"),
             ("analyse", "Groq LLM tool-calling  |  RuleEngine fallback"), ("generate_report", "InvestigationReportTool (validator)"),
             ("route_to_reviewer", "ReviewQueue + audit")]
    x, w, h, gap = 18, 210, 30, 7.5
    y = 360 - 8 - h
    centers = []
    for i, (n, tool) in enumerate(nodes):
        fill = AMBER_L if n == "analyse" else GREEN_L if n == "generate_report" else CYAN_L if n == "route_to_reviewer" else SOFT
        box(d, x, y, w, h, n, [tool], fill=fill, size=7.2)
        centers.append((x + w, y + h / 2))
        if i:
            arrow(d, x + w / 2, y + h + gap, x + w / 2, y + h)
        y -= h + gap
    # side panels
    box(d, 262, 214, 214, 110, "LLM mode (GROQ_API_KEY set)", [
        "Case file = transaction + evidence list", "Tools: transaction_history, customer_behaviour,",
        "graph_investigation, merchant_risk", "New tool results -> new evidence keys",
        "Must call submit_investigation_report", "(max 6 rounds, temperature 0.1)"], fill=AMBER_L, size=7.2)
    arrow(d, 262, 269, centers[6][0], centers[6][1] + 4, AMBER, dash=[2, 2])
    box(d, 262, 108, 214, 92, "Validator guarantees", [
        "drop findings without a valid evidence key", "normalise recommendation to APPROVE /",
        "HOLD_FOR_REVIEW / REJECT / ESCALATE", "no supported findings -> rule-based report",
        "fallback is always labelled"], fill=GREEN_L, size=7.2)
    arrow(d, 262, 150, centers[7][0], centers[7][1], GREEN, dash=[2, 2])
    box(d, 262, 18, 214, 74, "Human in the loop", [
        "agent has NO payment tools", "reviewer re-enters password + types txn ID",
        "only APPROVE can trigger PayPal capture"], fill=RED_L, stroke=RED, title_color=RED, size=7.2)
    arrow(d, 262, 55, centers[8][0], centers[8][1], RED, dash=[2, 2])
    return d


# --------------------------------------------------------------------------- 5
def graph(W=482):
    d = Drawing(W, 300)

    def node(x, y, label, kind, risk):
        col = {"hi": RED, "mid": AMBER, "lo": GREEN, "m": GREY}[risk]
        fill = {"hi": RED_L, "mid": AMBER_L, "lo": GREEN_L, "m": SOFT}[risk]
        if kind == "C":
            d.add(Circle(x, y, 13, fillColor=fill, strokeColor=col, strokeWidth=1.3))
        elif kind == "D":
            d.add(Rect(x - 12, y - 12, 24, 24, rx=3, ry=3, fillColor=fill, strokeColor=col, strokeWidth=1.3))
        elif kind == "W":
            d.add(Polygon([x, y + 14, x + 14, y, x, y - 14, x - 14, y], fillColor=fill, strokeColor=col, strokeWidth=1.3))
        else:
            d.add(Rect(x - 16, y - 10, 32, 20, fillColor=fill, strokeColor=col, strokeWidth=1.1))
        _text(d, x, y - 3, kind, 7, FB, col)
        _text(d, x, y - 24, label, 6.4, FM, NAVY, bg=True)

    def edge(a, b, sus=False):
        d.add(Line(a[0], a[1], b[0], b[1], strokeColor=RED if sus else LINE, strokeWidth=1.3 if sus else 0.8,
                   strokeDashArray=[3, 2] if sus else None))

    _text(d, 6, 288, "Example from the synthetic data: device-farm ring (Demo C)", 7.5, FB, CYAN, anchor="start")
    dev = (150, 170)
    cara = (60, 230)
    cs = [cara, (60, 110), (240, 230), (240, 110)]
    names = ["CUS_0003", "CUS_0091", "CUS_0093", "CUS_0097"]
    mule = (150, 50)
    merch = (40, 170)
    for c in cs:
        edge(c, dev, True)
        edge(c, mule, True)
    edge(cara, merch)
    node(*dev, "DEV_0147", "D", "hi")
    for c, n in zip(cs, names):
        node(*c, n, "C", "hi")
    node(*mule, "DST_MULE_02", "W", "hi")
    node(*merch, "MER_021", "M", "m")
    _text(d, 150, 200, "shared by 4 accounts", 6.4, F, RED, bg=True)
    _text(d, 205, 70, "flagged mule wallet", 6.4, F, RED, bg=True)

    _text(d, 300, 288, "Circular payment loop ($16,064.37)", 7.5, FB, CYAN, anchor="start")
    loop = [(330, 230), (440, 230), (440, 140), (330, 140)]
    ln = ["CUS_0081", "CUS_0082", "CUS_0083", "CUS_0080"]
    for i in range(4):
        a, b = loop[i], loop[(i + 1) % 4]
        arrow(d, a[0] + (b[0] - a[0]) * 0.18, a[1] + (b[1] - a[1]) * 0.18, a[0] + (b[0] - a[0]) * 0.82,
              a[1] + (b[1] - a[1]) * 0.82, RED, width=1.2)
    for p, n in zip(loop, ln):
        node(*p, n, "C", "hi")
    box(d, 300, 18, 176, 92, "Detections (NetworkX)", [
        "shared device: >= 3 customers on a device", "loops: simple_cycles(length_bound=6)",
        "clusters: connected components", "(merchant hubs excluded)", "flagged-destination interactions"], fill=SOFT, size=7)
    _text(d, 6, 10, "C customer   D device   W wallet destination   M merchant   red dashed = suspicious link with evidence", 6.4, F, GREY, anchor="start")
    return d


# --------------------------------------------------------------------------- 6
def erd(W=482):
    d = Drawing(W, 360)
    T = {}

    def table(key, x, y, cols, fill=SOFT, w=104):
        h = 19 + 8.4 * len(cols)
        d.add(Rect(x, y, w, h, fillColor=white, strokeColor=NAVY2, strokeWidth=0.8))
        d.add(Rect(x, y + h - 13, w, 13, fillColor=NAVY, strokeColor=NAVY, strokeWidth=0.8))
        _text(d, x + 4, y + h - 9.5, key, 7, FB, white, anchor="start")
        for i, c in enumerate(cols):
            _text(d, x + 4, y + h - 22 - i * 8.4, c, 6, FM, GREY, anchor="start")
        T[key] = (x, y, w, h)

    def c(key, side):
        x, y, w, h = T[key]
        return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[side]

    def fk(a, sa, b, sb):
        p, q = c(a, sa), c(b, sb)
        d.add(Line(p[0], p[1], q[0], q[1], strokeColor=CYAN, strokeWidth=0.8))
        d.add(Circle(q[0], q[1], 1.8, fillColor=CYAN, strokeColor=CYAN))

    table("users", 6, 286, ["id PK", "email UQ", "role CK", "customer_id FK"])
    table("customers", 126, 286, ["id PK (CUS_)", "name, city", "home_lat/lon"])
    table("payment_destinations", 246, 286, ["id PK (DST_)", "kind, is_flagged", "owner_customer_id FK"])
    table("merchants", 370, 286, ["id PK (MER_)", "risk_score CK", "payout_destination FK"])
    table("devices", 6, 196, ["id PK (DEV_)", "fingerprint UQ"])
    table("transactions", 126, 172, ["id PK (TXN_)", "customer/merchant FK", "device/destination FK", "amount CK>0", "status CK, risk_level", "review_status, is_fraud"], w=116)
    table("products", 370, 206, ["id PK (PRD_)", "price CK>0", "merchant_id FK"])
    table("fraud_predictions", 6, 84, ["transaction_id FK", "model_version_id FK", "probability CK", "shap, features JSON"])
    table("model_versions", 6, 12, ["version+algo UQ", "metrics JSON", "is_primary"])
    table("paypal_orders", 254, 100, ["paypal_order_id UQ", "transaction_id FK UQ", "user_id FK", "paypal_status", "sentinel_status", "capture_state, id UQ"], w=110)
    table("payment_events", 372, 110, ["paypal_order_id", "webhook_event_id UQ", "payload JSON"])
    table("investigations", 126, 84, ["id PK (INV_)", "transaction_id FK", "steps, report JSON"], w=116)
    table("investigation_evidence", 126, 12, ["investigation_id FK", "evidence_key E1..", "severity, summary"], w=116)
    table("reviewer_decisions", 254, 12, ["transaction_id FK", "reviewer_id FK", "decision CK"], w=110)
    table("audit_logs", 372, 30, ["prev_hash", "hash UQ", "actor_id FK", "details JSON"])

    fk("users", "r", "customers", "l")
    fk("payment_destinations", "l", "customers", "r")
    fk("merchants", "l", "payment_destinations", "r")
    fk("transactions", "t", "customers", "b")
    fk("transactions", "l", "devices", "r")
    fk("transactions", "r", "merchants", "b")
    fk("products", "t", "merchants", "b")
    fk("fraud_predictions", "r", "transactions", "l")
    fk("fraud_predictions", "b", "model_versions", "t")
    fk("paypal_orders", "l", "transactions", "r")
    fk("investigations", "t", "transactions", "b")
    fk("investigation_evidence", "t", "investigations", "b")
    fk("reviewer_decisions", "t", "transactions", "r")
    _text(d, W - 4, 4, "Also: graph_entities / graph_relationships, system_settings", 6.3, F, GREY, anchor="end")
    return d


# --------------------------------------------------------------------------- 7
def deployment(W=482):
    d = Drawing(W, 220)
    cols = [("LOCAL (verified)", GREEN_L, [("Vite dev :5173", "proxies /api, /ws"), ("Uvicorn :8000", "FastAPI app"),
                                             ("SQLite", "backend/sentinel.db"), ("In-memory", "rate limiter")]),
            ("DOCKER COMPOSE (configured)", SOFT, [("nginx :8080", "static build + proxy"), ("backend :8000", "python:3.13-slim"),
                                                   ("postgres:16", "volume pgdata"), ("redis:7", "rate limits")]),
            ("RENDER BLUEPRINT (configured)", SOFT, [("Static site", "sentinel-web"), ("Docker web service", "sentinel-api"),
                                                     ("Managed PostgreSQL", "sentinel-db"), ("Env secrets", "PayPal, Groq, JWT")])]
    cw = (W - 24) / 3
    for i, (title, fill, items) in enumerate(cols):
        x = 4 + i * (cw + 8)
        panel(d, x, 30, cw, 186, title, fill=fill)
        y = 160
        for j, (t, s) in enumerate(items):
            box(d, x + 10, y, cw - 20, 32, t, [s], fill=white, size=7.2)
            if j:
                arrow(d, x + cw / 2, y + 32 + 8, x + cw / 2, y + 32)
            y -= 40
    box(d, 120, 2, 242, 22, "PayPal Sandbox API + optional Groq API (HTTPS from backend)", fill=AMBER_L, size=7)
    return d


DIAGRAMS = {
    "architecture": (architecture, "High-level system architecture"),
    "sequence": (sequence, "Payment processing sequence (Orders v2 with Sentinel risk gating)"),
    "mlpipeline": (mlpipeline, "Machine-learning fraud detection pipeline"),
    "agent": (agent, "LangGraph investigation agent workflow"),
    "graph": (graph, "Graph intelligence: suspicious structures found in the synthetic data"),
    "erd": (erd, "Database relationships (main tables and foreign keys)"),
    "deployment": (deployment, "Deployment architecture"),
}
