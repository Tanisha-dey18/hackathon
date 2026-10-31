"""Financial relationship graph built with NetworkX from the persisted graph_entities /
graph_relationships tables. Detects shared devices, circular payments, suspicious clusters and
repeated interactions with flagged destinations, and produces explorer views with evidence."""
from __future__ import annotations

import functools
import threading
from collections import defaultdict
from datetime import datetime

import networkx as nx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..ml.features import aware
from ..models import (
    Customer,
    Device,
    FraudPrediction,
    GraphEntity,
    GraphRelationship,
    Merchant,
    PaymentDestination,
    Transaction,
)

SHARED_DEVICE_MIN = 3
NODE_TYPES = ("CUSTOMER", "MERCHANT", "DEVICE", "DESTINATION", "TRANSACTION")


def key(entity_type: str, ref_id: str) -> str:
    return f"{entity_type}:{ref_id}"


def type_of_ref(ref_id: str) -> str:
    prefix = ref_id.split("_")[0]
    return {"CUS": "CUSTOMER", "MER": "MERCHANT", "DEV": "DEVICE", "DST": "DESTINATION", "TXN": "TRANSACTION"}.get(
        prefix, "UNKNOWN"
    )


# --------------------------------------------------------------------------- persistence
def _txn_edges(t: Transaction) -> list[tuple[str, str, str, str, str]]:
    """(source_type, source_ref, target_type, target_ref, rel_type)"""
    edges = [
        ("CUSTOMER", t.customer_id, "DEVICE", t.device_id, "USES_DEVICE"),
        ("CUSTOMER", t.customer_id, "TRANSACTION", t.id, "MADE_PAYMENT"),
        ("TRANSACTION", t.id, "DEVICE", t.device_id, "VIA_DEVICE"),
        ("TRANSACTION", t.id, "DESTINATION", t.destination_id, "PAID_TO"),
    ]
    if t.merchant_id:
        edges.append(("TRANSACTION", t.id, "MERCHANT", t.merchant_id, "PAID_MERCHANT"))
    return edges


def rebuild_graph_tables(db: Session) -> dict:
    db.execute(delete(GraphRelationship))
    db.execute(delete(GraphEntity))
    db.flush()
    entities: dict[tuple[str, str], GraphEntity] = {}

    def ent(t: str, ref: str, label: str, flagged: bool = False, risk: float = 0.0) -> None:
        if (t, ref) not in entities:
            entities[(t, ref)] = GraphEntity(entity_type=t, ref_id=ref, label=label, flagged=flagged, risk_score=risk)

    for c in db.execute(select(Customer)).scalars():
        ent("CUSTOMER", c.id, c.name)
    for m in db.execute(select(Merchant)).scalars():
        ent("MERCHANT", m.id, m.name, risk=m.risk_score)
    for d in db.execute(select(Device)).scalars():
        ent("DEVICE", d.id, f"{d.device_type} · {d.os}", flagged=d.is_flagged)
    for p in db.execute(select(PaymentDestination)).scalars():
        ent("DESTINATION", p.id, p.label, flagged=p.is_flagged)
    txns = list(db.execute(select(Transaction)).scalars())
    for t in txns:
        ent("TRANSACTION", t.id, f"${float(t.amount):,.2f}")
    db.add_all(entities.values())
    db.flush()
    ids = {k: e.id for k, e in entities.items()}

    rels: dict[tuple[int, int, str], float] = defaultdict(float)
    for p in db.execute(select(PaymentDestination).where(PaymentDestination.owner_customer_id.is_not(None))).scalars():
        rels[(ids[("CUSTOMER", p.owner_customer_id)], ids[("DESTINATION", p.id)], "OWNS_WALLET")] += 1
    for t in txns:
        for st, sr, tt, tr, rt in _txn_edges(t):
            rels[(ids[(st, sr)], ids[(tt, tr)], rt)] += 1
    db.add_all(GraphRelationship(source_id=s, target_id=d, rel_type=r, weight=w) for (s, d, r), w in rels.items())
    db.flush()
    invalidate()
    return {"entities": len(entities), "relationships": len(rels)}


def _get_or_create_entity(db: Session, t: str, ref: str, label: str, flagged: bool = False) -> GraphEntity:
    e = db.execute(select(GraphEntity).where(GraphEntity.entity_type == t, GraphEntity.ref_id == ref)).scalar()
    if not e:
        e = GraphEntity(entity_type=t, ref_id=ref, label=label, flagged=flagged)
        db.add(e)
        db.flush()
    return e


def sync_transaction(db: Session, t: Transaction) -> None:
    """Incrementally add one transaction's relationships to the stored graph."""
    labels = {
        "CUSTOMER": lambda r: db.get(Customer, r).name,
        "DEVICE": lambda r: (lambda d: f"{d.device_type} · {d.os}")(db.get(Device, r)),
        "MERCHANT": lambda r: db.get(Merchant, r).name,
        "DESTINATION": lambda r: db.get(PaymentDestination, r).label,
        "TRANSACTION": lambda r: f"${float(t.amount):,.2f}",
    }
    cache: dict[tuple[str, str], GraphEntity] = {}
    node_info: dict[str, tuple[str, str, str, bool]] = {}
    for st, sr, tt, tr, rt in _txn_edges(t):
        for et, er in ((st, sr), (tt, tr)):
            if (et, er) not in cache:
                cache[(et, er)] = _get_or_create_entity(db, et, er, labels[et](er))
                e = cache[(et, er)]
                node_info[key(et, er)] = (et, er, e.label, e.flagged)
        s, d = cache[(st, sr)], cache[(tt, tr)]
        rel = db.execute(select(GraphRelationship).where(
            GraphRelationship.source_id == s.id, GraphRelationship.target_id == d.id, GraphRelationship.rel_type == rt
        )).scalar()
        if rel:
            rel.weight += 1
        else:
            db.add(GraphRelationship(source_id=s.id, target_id=d.id, rel_type=rt, weight=1))
    db.flush()
    prob = db.execute(select(FraudPrediction.fraud_probability).where(FraudPrediction.transaction_id == t.id)
                      .order_by(FraudPrediction.id.desc()).limit(1)).scalar()
    _apply_incremental(t, prob, node_info)


# --------------------------------------------------------------------------- analysis
_state_lock = threading.Lock()
_version = 0
_engine: "GraphEngine | None" = None


def invalidate() -> None:
    global _version
    with _state_lock:
        _version += 1


def _apply_incremental(t: Transaction, prob: float | None, node_info: dict) -> None:
    """Fold one new transaction into the cached engine (about 10 ms) instead of rebuilding from the
    database (about 500 ms). If no engine is cached yet, the next get_engine() builds one from the DB."""
    with _state_lock:
        if _engine is not None and _engine.version == _version:
            _engine.apply_transaction(t, prob, node_info)


def get_engine(db: Session) -> "GraphEngine":
    global _engine
    with _state_lock:
        v = _version
        if _engine is None or _engine.version != v:
            _engine = GraphEngine(db, v)
        return _engine


def _locked(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return fn(self, *args, **kwargs)
    return wrapper


class GraphEngine:
    def __init__(self, db: Session, version: int) -> None:
        self.version = version
        self.built_at = datetime.utcnow()
        self.lock = threading.RLock()  # guards in-place updates against concurrent readers
        self.G = nx.DiGraph()
        ents = {e.id: e for e in db.execute(select(GraphEntity)).scalars()}
        for e in ents.values():
            self.G.add_node(key(e.entity_type, e.ref_id), type=e.entity_type, ref_id=e.ref_id, label=e.label,
                            flagged=e.flagged, base_risk=e.risk_score)
        for r in db.execute(select(GraphRelationship)).scalars():
            s, d = ents.get(r.source_id), ents.get(r.target_id)
            if s and d:
                self.G.add_edge(key(s.entity_type, s.ref_id), key(d.entity_type, d.ref_id), rel=r.rel_type, weight=r.weight)

        # transaction facts used for evidence and risk colouring
        latest = (select(FraudPrediction.transaction_id, func.max(FraudPrediction.id).label("pid"))
                  .group_by(FraudPrediction.transaction_id).subquery())
        probs = dict(db.execute(
            select(FraudPrediction.transaction_id, FraudPrediction.fraud_probability)
            .join(latest, FraudPrediction.id == latest.c.pid)
        ).all())
        self.txn: dict[str, dict] = {}
        for t in db.execute(select(Transaction)).scalars():
            self.txn[t.id] = {
                "customer": t.customer_id, "merchant": t.merchant_id, "device": t.device_id,
                "destination": t.destination_id, "amount": float(t.amount), "ts": aware(t.created_at).isoformat(),
                "prob": probs.get(t.id), "status": t.status, "risk_level": t.risk_level,
                "rejected": t.review_status == "REJECTED",
            }
        self.dest_owner = {p.id: p.owner_customer_id for p in db.execute(select(PaymentDestination)).scalars()}
        self.dest_kind = {p.id: p.kind for p in db.execute(select(PaymentDestination)).scalars()}
        self.flag_reason = {p.id: p.flag_reason for p in db.execute(select(PaymentDestination)).scalars()}
        self._project()
        self._customer_risk()
        self._analyze()

    # -------------------------------------------------- entity projection (collapse transaction nodes)
    def _project(self) -> None:
        self.P = nx.Graph()
        for n, a in self.G.nodes(data=True):
            if a["type"] != "TRANSACTION":
                self.P.add_node(n, **a)
        for tid, t in self.txn.items():
            self._project_txn(tid, t)
        for dst, owner in self.dest_owner.items():
            if owner:
                self._pbump(key("CUSTOMER", owner), key("DESTINATION", dst), "OWNS_WALLET")

    def _project_txn(self, tid: str, t: dict) -> None:
        c = key("CUSTOMER", t["customer"])
        self._pbump(c, key("DEVICE", t["device"]), "USES_DEVICE", tid)
        self._pbump(c, key("DESTINATION", t["destination"]), "PAID_TO", tid, t["amount"])
        if t["merchant"]:
            self._pbump(c, key("MERCHANT", t["merchant"]), "PAID_MERCHANT", tid, t["amount"])

    def _pbump(self, u: str, v: str, rel: str, tid: str | None = None, amount: float = 0.0) -> None:
        """Aggregate one relationship onto the projection edge u-v (first relationship type is primary)."""
        P = self.P
        if not (P.has_node(u) and P.has_node(v)):
            return
        if P.has_edge(u, v):
            d = P[u][v]
            if d["rel"] != rel:
                extra = d.setdefault("extra", [])
                d = next((e for e in extra if e["rel"] == rel), None)
                if d is None:
                    d = {"rel": rel, "count": 0, "amount": 0.0, "txn_ids": []}
                    extra.append(d)
        else:
            P.add_edge(u, v, rel=rel, count=0, amount=0.0, txn_ids=[])
            d = P[u][v]
        d["count"] += 1
        d["amount"] += amount
        if tid and len(d["txn_ids"]) < 25:
            d["txn_ids"].append(tid)

    def apply_transaction(self, t: Transaction, prob: float | None, node_info: dict) -> None:
        with self.lock:
            for n, (etype, ref, label, flagged) in node_info.items():
                if not self.G.has_node(n):
                    self.G.add_node(n, type=etype, ref_id=ref, label=label, flagged=flagged, base_risk=0.0)
                    if etype != "TRANSACTION":
                        self.P.add_node(n, **self.G.nodes[n])
            for st, sr, tt, tr, rt in _txn_edges(t):
                u, v = key(st, sr), key(tt, tr)
                if self.G.has_edge(u, v):
                    self.G[u][v]["weight"] += 1
                else:
                    self.G.add_edge(u, v, rel=rt, weight=1)
            rec = {
                "customer": t.customer_id, "merchant": t.merchant_id, "device": t.device_id,
                "destination": t.destination_id, "amount": float(t.amount), "ts": aware(t.created_at).isoformat(),
                "prob": prob, "status": t.status, "risk_level": t.risk_level, "rejected": t.review_status == "REJECTED",
            }
            self.txn[t.id] = rec
            self._project_txn(t.id, rec)
            if prob is not None:
                c = key("CUSTOMER", t.customer_id)
                self.customer_risk[c] = max(self.customer_risk[c], prob)
            self._analyze()

    def _customer_risk(self) -> None:
        """Customer risk = highest model score among the customer's transactions."""
        self.customer_risk: dict[str, float] = defaultdict(float)
        for t in self.txn.values():
            if t["prob"] is not None:
                c = key("CUSTOMER", t["customer"])
                self.customer_risk[c] = max(self.customer_risk[c], t["prob"])

    # -------------------------------------------------- detection
    def _analyze(self) -> None:
        P = self.P
        self.shared_devices = []
        for n, a in P.nodes(data=True):
            if a["type"] != "DEVICE":
                continue
            custs = [m for m in P.neighbors(n) if P.nodes[m]["type"] == "CUSTOMER"]
            if len(custs) >= SHARED_DEVICE_MIN:
                txn_ids = [tid for c in custs for tid in P[n][c].get("txn_ids", [])]
                self.shared_devices.append({
                    "device": a["ref_id"], "customers": sorted(P.nodes[c]["ref_id"] for c in custs),
                    "account_count": len(custs), "transaction_ids": txn_ids[:40],
                    "high_risk_accounts": sum(1 for c in custs if self.customer_risk.get(c, 0) >= 0.7),
                })

        # circular payments: customer -> owner of the wallet they paid
        flow = nx.DiGraph()
        for tid, t in self.txn.items():
            owner = self.dest_owner.get(t["destination"])
            if owner and owner != t["customer"]:
                if flow.has_edge(t["customer"], owner):
                    flow[t["customer"]][owner]["txn_ids"].append(tid)
                    flow[t["customer"]][owner]["amount"] += t["amount"]
                else:
                    flow.add_edge(t["customer"], owner, txn_ids=[tid], amount=t["amount"])
        self.cycles = []
        for cyc in nx.simple_cycles(flow, length_bound=6):
            if len(cyc) < 3:
                continue
            hops = []
            for i, u in enumerate(cyc):
                v = cyc[(i + 1) % len(cyc)]
                e = flow[u][v]
                hops.append({"from": u, "to": v, "transfers": len(e["txn_ids"]), "amount": round(e["amount"], 2),
                             "transaction_ids": e["txn_ids"][:10]})
            self.cycles.append({"customers": cyc, "length": len(cyc), "hops": hops,
                                "total_amount": round(sum(h["amount"] for h in hops), 2)})
        self.cycle_members = {c for cyc in self.cycles for c in cyc["customers"]}

        # flagged destinations
        self.flagged_destinations = []
        for n, a in P.nodes(data=True):
            if a["type"] == "DESTINATION" and a["flagged"]:
                custs = [m for m in P.neighbors(n) if P.nodes[m]["type"] == "CUSTOMER" and P[n][m]["rel"] == "PAID_TO"]
                txn_ids = [tid for c in custs for tid in P[n][c]["txn_ids"]]
                self.flagged_destinations.append({
                    "destination": a["ref_id"], "label": a["label"], "reason": self.flag_reason.get(a["ref_id"]),
                    "customers": sorted(P.nodes[c]["ref_id"] for c in custs),
                    "payment_count": sum(P[n][c]["count"] for c in custs),
                    "total_amount": round(sum(P[n][c]["amount"] for c in custs), 2),
                    "transaction_ids": txn_ids[:40],
                })
        flagged_dest_refs = {f["destination"] for f in self.flagged_destinations}
        shared_dev_refs = {s["device"] for s in self.shared_devices}

        # clusters: components linking accounts through devices / wallets (merchant hubs excluded)
        core = P.subgraph(
            n for n, a in P.nodes(data=True)
            if a["type"] in ("CUSTOMER", "DEVICE") or (a["type"] == "DESTINATION" and self.dest_kind.get(a["ref_id"]) == "WALLET")
        )
        self.clusters = []
        self.cluster_of: dict[str, int] = {}
        for comp in nx.connected_components(core):
            custs = [n for n in comp if P.nodes[n]["type"] == "CUSTOMER"]
            if len(custs) < 3:
                continue
            refs = {P.nodes[n]["ref_id"] for n in comp}
            reasons = []
            sd = sorted(refs & shared_dev_refs)
            fd = sorted(refs & flagged_dest_refs)
            cyc = sorted({P.nodes[c]["ref_id"] for c in custs} & self.cycle_members)
            if sd:
                reasons.append(f"{len(sd)} device(s) shared by {SHARED_DEVICE_MIN}+ accounts")
            if fd:
                reasons.append(f"{len(fd)} flagged payment destination(s)")
            if cyc:
                reasons.append(f"{len(cyc)} accounts in circular payment loop")
            risks = [self.customer_risk.get(c, 0.0) for c in custs]
            mean_risk = sum(risks) / len(risks)
            if mean_risk >= 0.5:
                reasons.append(f"mean account risk {mean_risk:.2f}")
            cid = len(self.clusters) + 1
            cluster = {
                "cluster_id": cid,
                "customers": sorted(P.nodes[c]["ref_id"] for c in custs),
                "devices": sorted(r for r in refs if r.startswith("DEV_")),
                "destinations": sorted(r for r in refs if r.startswith("DST_")),
                "shared_devices": sd, "flagged_destinations": fd, "cycle_members": cyc,
                "mean_risk": round(mean_risk, 3), "max_risk": round(max(risks), 3),
                "suspicious": bool(sd or fd or cyc or mean_risk >= 0.5),
                "reasons": reasons,
            }
            self.clusters.append(cluster)
            for c in custs:
                self.cluster_of[P.nodes[c]["ref_id"]] = cid

    # -------------------------------------------------- per-entity signals (used by risk policy + agent)
    @_locked
    def customer_signals(self, customer_id: str, device_id: str | None = None, destination_id: str | None = None) -> dict:
        cid = self.cluster_of.get(customer_id)
        cluster = next((c for c in self.clusters if c["cluster_id"] == cid), None)
        devs = [s for s in self.shared_devices if customer_id in s["customers"] or s["device"] == device_id]
        fdest = [f for f in self.flagged_destinations if customer_id in f["customers"] or f["destination"] == destination_id]
        cycles = [c for c in self.cycles if customer_id in c["customers"]]
        P = self.P
        dev_accounts = 0
        if device_id and P.has_node(key("DEVICE", device_id)):
            n = key("DEVICE", device_id)
            dev_accounts = len({m for m in P.neighbors(n) if P.nodes[m]["type"] == "CUSTOMER"} | {key("CUSTOMER", customer_id)})
        score = 0.0
        if cluster and cluster["suspicious"]:
            score = max(score, 0.5 + 0.5 * cluster["mean_risk"])
        if devs:
            score = max(score, 0.6 + 0.05 * min(max(d["account_count"] for d in devs), 8))
        if fdest:
            score = max(score, 0.85)
        if cycles:
            score = max(score, 0.9)
        return {
            "graph_risk_score": round(min(score, 1.0), 3),
            "cluster": cluster,
            "shared_devices": devs,
            "flagged_destinations": fdest,
            "cycles": cycles,
            "device_account_count": dev_accounts,
        }

    @_locked
    def summary(self) -> dict:
        types = defaultdict(int)
        for _, a in self.G.nodes(data=True):
            types[a["type"]] += 1
        return {
            "nodes": self.G.number_of_nodes(), "edges": self.G.number_of_edges(), "node_types": dict(types),
            "shared_devices": len(self.shared_devices), "cycles": len(self.cycles),
            "clusters": len(self.clusters), "suspicious_clusters": sum(c["suspicious"] for c in self.clusters),
            "flagged_destinations": len(self.flagged_destinations),
        }

    # -------------------------------------------------- explorer views
    def _node_payload(self, n: str) -> dict:
        a = self.P.nodes[n] if self.P.has_node(n) else self.G.nodes[n]
        ref = a["ref_id"]
        t = a["type"]
        risk = a.get("base_risk", 0.0)
        details: dict = {}
        flags: list[str] = []
        if t == "CUSTOMER":
            risk = self.customer_risk.get(n, 0.0)
            details["transactions"] = sum(1 for x in self.txn.values() if x["customer"] == ref)
            if ref in self.cycle_members:
                flags.append("Member of circular payment loop")
            if ref in self.cluster_of and self.clusters[self.cluster_of[ref] - 1]["suspicious"]:
                flags.append(f"Member of suspicious cluster #{self.cluster_of[ref]}")
        elif t == "DEVICE":
            sd = next((s for s in self.shared_devices if s["device"] == ref), None)
            n_accounts = len([m for m in self.P.neighbors(n) if self.P.nodes[m]["type"] == "CUSTOMER"])
            details["accounts"] = n_accounts
            if sd:
                flags.append(f"Shared by {sd['account_count']} accounts")
                risk = max(risk, min(1.0, 0.5 + 0.08 * sd["account_count"]))
        elif t == "DESTINATION":
            details["kind"] = self.dest_kind.get(ref)
            if a["flagged"]:
                flags.append(self.flag_reason.get(ref) or "Flagged destination")
                risk = 1.0
            owner = self.dest_owner.get(ref)
            if owner:
                details["owner"] = owner
        elif t == "TRANSACTION":
            x = self.txn.get(ref, {})
            risk = x.get("prob") or 0.0
            details = {"amount": x.get("amount"), "status": x.get("status"), "risk_level": x.get("risk_level"),
                       "created_at": x.get("ts")}
        if a.get("flagged") and t != "DESTINATION":
            flags.append("Flagged")
        return {"id": n, "type": t, "ref_id": ref, "label": a["label"], "risk": round(float(risk), 3),
                "flagged": bool(flags), "flags": flags, "details": details}

    def _edge_payload(self, u: str, v: str, d: dict) -> dict:
        rel = d["rel"]
        evidence: list[str] = []
        suspicious = False
        nu, nv = self.P.nodes[u], self.P.nodes[v]
        dev = u if nu["type"] == "DEVICE" else v if nv["type"] == "DEVICE" else None
        dst = u if nu["type"] == "DESTINATION" else v if nv["type"] == "DESTINATION" else None
        if dev:
            sd = next((s for s in self.shared_devices if s["device"] == self.P.nodes[dev]["ref_id"]), None)
            if sd:
                suspicious = True
                evidence.append(f"Device {sd['device']} is shared by {sd['account_count']} accounts: {', '.join(sd['customers'][:8])}")
        if dst and self.P.nodes[dst]["flagged"] and rel == "PAID_TO":
            suspicious = True
            evidence.append(f"{d['count']} payment(s) totalling ${d['amount']:,.2f} to flagged destination {self.P.nodes[dst]['ref_id']}")
        if rel == "PAID_TO" and dst:
            owner = self.dest_owner.get(self.P.nodes[dst]["ref_id"])
            cust = u if nu["type"] == "CUSTOMER" else v
            if owner and owner in self.cycle_members and self.P.nodes[cust]["ref_id"] in self.cycle_members:
                suspicious = True
                evidence.append("Transfer is part of a circular payment loop")
        return {"id": f"{u}|{v}|{rel}", "source": u, "target": v, "type": rel, "count": d.get("count", 1),
                "amount": round(d.get("amount", 0.0), 2), "suspicious": suspicious, "evidence": evidence,
                "transaction_ids": d.get("txn_ids", [])[:10]}

    def _layout(self, nodes: list[str], edges: list[tuple[str, str]], center: str | None = None) -> dict[str, tuple[float, float]]:
        H = nx.Graph()
        H.add_nodes_from(nodes)
        H.add_edges_from(edges)
        fixed = None
        init = None
        if center and center in H:
            init = {center: (0.0, 0.0)}
            fixed = [center]
        if len(nodes) <= 220:
            # Kamada-Kawai per connected component gives readable, evenly spaced layouts
            pos = {}
            comps = sorted(nx.connected_components(H), key=len, reverse=True)
            offset_x = 0.0
            for comp in comps:
                sub = H.subgraph(comp)
                if len(comp) == 1:
                    p = {next(iter(comp)): (0.0, 0.0)}
                else:
                    p = nx.kamada_kawai_layout(sub, scale=1.0)
                xs = [v[0] for v in p.values()]
                width = (max(xs) - min(xs)) if len(xs) > 1 else 0.2
                for n, (x, y) in p.items():
                    pos[n] = (x - min(xs) + offset_x, y)
                offset_x += width + 0.6
            if center and center in pos:
                cx, cy = pos[center]
                pos = {n: (x - cx, y - cy) for n, (x, y) in pos.items()}
        else:
            pos = nx.spring_layout(H, seed=7, k=1.6 / max(len(nodes), 1) ** 0.5, iterations=200, pos=init, fixed=fixed)
        unit = 95 * max(len(nodes), 4) ** 0.5  # pixels per layout unit, grows with graph size
        return {n: (float(p[0] * unit), float(p[1] * unit)) for n, p in pos.items()}

    def _render(self, nodes: set[str], focus: list[str], center: str | None = None, extra_nodes: list[dict] | None = None,
                extra_edges: list[dict] | None = None) -> dict:
        P = self.P
        edge_list = [(u, v, d) for u, v, d in P.subgraph(nodes).edges(data=True)]
        node_payloads = [self._node_payload(n) for n in nodes]
        edge_payloads = [self._edge_payload(u, v, d) for u, v, d in edge_list]
        all_nodes = [n["id"] for n in node_payloads] + [n["id"] for n in (extra_nodes or [])]
        all_edges = [(e["source"], e["target"]) for e in edge_payloads + (extra_edges or [])]
        pos = self._layout(all_nodes, all_edges, center)
        for n in node_payloads + (extra_nodes or []):
            n["x"], n["y"] = pos[n["id"]]
            n["focus"] = n["id"] in focus
        return {"nodes": node_payloads + (extra_nodes or []), "edges": edge_payloads + (extra_edges or [])}

    def _expand(self, seeds: list[str], hops: int, limit: int) -> set[str]:
        P = self.P
        nodes = set(s for s in seeds if P.has_node(s))
        frontier = set(nodes)
        for _ in range(hops):
            nxt = set()
            for n in frontier:
                if P.nodes[n]["type"] == "MERCHANT":
                    continue  # merchants are hubs; don't traverse through them
                if P.nodes[n]["type"] == "DESTINATION" and self.dest_kind.get(P.nodes[n]["ref_id"]) == "MERCHANT_PAYOUT":
                    continue
                nbrs = sorted(P.neighbors(n), key=lambda m: -P[n][m].get("count", 1))
                for m in nbrs:
                    if m not in nodes:
                        nxt.add(m)
            for m in sorted(nxt, key=lambda m: -self.customer_risk.get(m, 0.0)):
                if len(nodes) >= limit:
                    break
                nodes.add(m)
            frontier = nxt
        return nodes

    @_locked
    def entity_view(self, ref_id: str, hops: int = 2, limit: int = 70) -> dict | None:
        n = key(type_of_ref(ref_id), ref_id)
        if not self.P.has_node(n):
            return None
        nodes = self._expand([n], hops, limit)
        out = self._render(nodes, [n], center=n)
        out["focus"] = n
        return out

    @_locked
    def transaction_view(self, txn_id: str, limit: int = 60) -> dict | None:
        t = self.txn.get(txn_id)
        if not t:
            return None
        seeds = [key("CUSTOMER", t["customer"]), key("DEVICE", t["device"]), key("DESTINATION", t["destination"])]
        if t["merchant"]:
            seeds.append(key("MERCHANT", t["merchant"]))
        nodes = self._expand(seeds, 2, limit)
        tnode = key("TRANSACTION", txn_id)
        txn_node = {"id": tnode, "type": "TRANSACTION", "ref_id": txn_id, "label": f"${t['amount']:,.2f}",
                    "risk": round(t["prob"] or 0.0, 3), "flagged": False, "flags": [],
                    "details": {"amount": t["amount"], "status": t["status"], "risk_level": t["risk_level"],
                                "created_at": t["ts"]}}
        extra_edges = [
            {"id": f"{s}|{tnode}", "source": s if s.startswith("CUSTOMER") else tnode,
             "target": tnode if s.startswith("CUSTOMER") else s,
             "type": {"CUSTOMER": "MADE_PAYMENT", "DEVICE": "VIA_DEVICE", "DESTINATION": "PAID_TO", "MERCHANT": "PAID_MERCHANT"}[s.split(":")[0]],
             "count": 1, "amount": t["amount"], "suspicious": False, "evidence": [], "transaction_ids": [txn_id]}
            for s in seeds if self.P.has_node(s)
        ]
        out = self._render(nodes, seeds + [tnode], center=tnode, extra_nodes=[txn_node], extra_edges=extra_edges)
        out["focus"] = tnode
        return out

    @_locked
    def overview(self, limit: int = 160) -> dict:
        nodes: set[str] = set()
        for c in sorted(self.clusters, key=lambda c: -c["mean_risk"]):
            if not c["suspicious"]:
                continue
            for ref in c["customers"] + c["devices"] + c["destinations"]:
                if len(nodes) < limit:
                    nodes.add(key(type_of_ref(ref), ref))
        for f in self.flagged_destinations:
            nodes.add(key("DESTINATION", f["destination"]))
        # include the high-risk merchants these accounts pay for context
        for n in list(nodes):
            if self.P.nodes[n]["type"] == "CUSTOMER":
                for m in self.P.neighbors(n):
                    if self.P.nodes[m]["type"] == "MERCHANT" and self.P.nodes[m].get("base_risk", 0) >= 0.4 and len(nodes) < limit + 10:
                        nodes.add(m)
        out = self._render(nodes, [])
        out["focus"] = None
        return out
