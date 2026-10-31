"""Point-in-time feature engineering.

The same `FeatureState` is used for training (replaying history chronologically) and for live
scoring (state built from the database), which removes train/serve skew: a feature for a
transaction is computed only from transactions that happened before it.
"""
from __future__ import annotations

import math
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

FEATURE_NAMES: list[str] = [
    "amount",
    "log_amount",
    "txn_count_1h",
    "txn_count_24h",
    "txn_count_7d",
    "hours_since_prev",
    "cust_avg_amount",
    "amount_to_avg_ratio",
    "amount_zscore",
    "merchant_risk_score",
    "merchant_high_risk_category",
    "is_p2p_transfer",
    "device_distinct_customers",
    "device_new_for_customer",
    "customer_distinct_devices_30d",
    "geo_distance_prev_km",
    "geo_velocity_kmh",
    "distance_from_home_km",
    "failed_count_24h",
    "failed_count_7d",
    "destination_distinct_customers",
    "destination_flagged",
    "customer_flagged_dest_interactions",
    "hour_of_day",
    "is_night",
    "is_first_txn",
]

# Human-readable descriptions used for SHAP explanations and investigation evidence.
FEATURE_LABELS: dict[str, str] = {
    "amount": "Transaction amount",
    "log_amount": "Transaction amount (log scale)",
    "txn_count_1h": "Transactions in past hour",
    "txn_count_24h": "Transactions in past 24h",
    "txn_count_7d": "Transactions in past 7 days",
    "hours_since_prev": "Hours since previous transaction",
    "cust_avg_amount": "Customer historical average amount",
    "amount_to_avg_ratio": "Amount vs. customer average",
    "amount_zscore": "Deviation from normal spending (z-score)",
    "merchant_risk_score": "Merchant risk score",
    "merchant_high_risk_category": "High-risk merchant category",
    "is_p2p_transfer": "Peer-to-peer wallet transfer",
    "device_distinct_customers": "Accounts sharing this device",
    "device_new_for_customer": "New device for customer",
    "customer_distinct_devices_30d": "Devices used by customer (30d)",
    "geo_distance_prev_km": "Distance from previous transaction",
    "geo_velocity_kmh": "Implied travel speed",
    "distance_from_home_km": "Distance from home location",
    "failed_count_24h": "Failed attempts (24h)",
    "failed_count_7d": "Failed attempts (7d)",
    "destination_distinct_customers": "Accounts paying this destination",
    "destination_flagged": "Destination previously flagged",
    "customer_flagged_dest_interactions": "Prior payments to flagged destinations",
    "hour_of_day": "Hour of day (UTC)",
    "is_night": "Night-time transaction",
    "is_first_txn": "No prior customer history",
}


def describe_factor(name: str, value: float | None) -> str:
    """Turn a feature value into a sentence a reviewer can verify."""
    v = value
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return f"{FEATURE_LABELS.get(name, name)}: no history available"
    match name:
        case "amount" | "log_amount":
            amt = v if name == "amount" else math.expm1(v)
            return f"Transaction amount ${amt:,.2f}"
        case "amount_to_avg_ratio":
            return f"Amount is {v:.1f}x the customer's historical average"
        case "amount_zscore":
            return f"Amount is {v:.1f} standard deviations from the customer's normal spending"
        case "cust_avg_amount":
            return f"Customer historical average is ${v:,.2f}"
        case "txn_count_1h":
            return f"{int(v)} prior transactions by this customer in the past hour"
        case "txn_count_24h":
            return f"{int(v)} prior transactions by this customer in the past 24 hours"
        case "txn_count_7d":
            return f"{int(v)} prior transactions by this customer in the past 7 days"
        case "hours_since_prev":
            return f"{v:.2f} hours since the customer's previous transaction"
        case "merchant_risk_score":
            return f"Merchant risk score is {v:.2f}"
        case "merchant_high_risk_category":
            return "Merchant operates in a high-risk category" if v else "Merchant is in a standard-risk category"
        case "is_p2p_transfer":
            return "Peer-to-peer transfer to a wallet" if v else "Merchant purchase"
        case "device_distinct_customers":
            return f"Device has been used by {int(v)} distinct accounts"
        case "device_new_for_customer":
            return "First time this customer has used this device" if v else "Device is known for this customer"
        case "customer_distinct_devices_30d":
            return f"Customer used {int(v)} distinct devices in 30 days"
        case "geo_distance_prev_km":
            return f"{v:,.0f} km from the previous transaction location"
        case "geo_velocity_kmh":
            return f"Implied travel speed of {v:,.0f} km/h since previous transaction"
        case "distance_from_home_km":
            return f"{v:,.0f} km from the customer's home location"
        case "failed_count_24h":
            return f"{int(v)} failed payment attempts in the past 24 hours"
        case "failed_count_7d":
            return f"{int(v)} failed payment attempts in the past 7 days"
        case "destination_distinct_customers":
            return f"Payment destination has received funds from {int(v)} distinct accounts"
        case "destination_flagged":
            return "Payment destination is on the flagged list" if v else "Payment destination is not flagged"
        case "customer_flagged_dest_interactions":
            return f"{int(v)} prior payments by this customer to flagged destinations"
        case "hour_of_day":
            return f"Transaction at {int(v):02d}:00 UTC"
        case "is_night":
            return "Transaction during night hours (00:00-05:00)" if v else "Transaction during daytime hours"
        case "is_first_txn":
            return "Customer has no prior transaction history" if v else "Customer has prior history"
    return f"{FEATURE_LABELS.get(name, name)} = {v}"


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


@dataclass(slots=True)
class TxnRecord:
    id: str
    customer_id: str
    merchant_id: str | None
    device_id: str
    destination_id: str
    amount: float
    lat: float
    lon: float
    ts: datetime
    failed: bool


@dataclass(slots=True)
class StaticContext:
    merchants: dict[str, tuple[float, bool]]  # id -> (risk_score, high_risk_category)
    destinations: dict[str, bool]  # id -> flagged
    homes: dict[str, tuple[float, float]]  # customer -> (lat, lon)


NAN = float("nan")


class FeatureState:
    def __init__(self, ctx: StaticContext) -> None:
        self.ctx = ctx
        self.cust_txns: dict[str, list[TxnRecord]] = defaultdict(list)
        self.device_customers: dict[str, set[str]] = defaultdict(set)
        self.dest_customers: dict[str, set[str]] = defaultdict(set)
        self.cust_flagged_dest: dict[str, int] = defaultdict(int)
        self.seen_ids: set[str] = set()
        self.lock = threading.RLock()

    def features(self, t: TxnRecord) -> dict[str, float]:
        with self.lock:
            ts = aware(t.ts)
            hist = [h for h in self.cust_txns.get(t.customer_id, []) if aware(h.ts) < ts and h.id != t.id]
            ok_hist = [h for h in hist if not h.failed]
            amounts = [h.amount for h in ok_hist]
            prev = hist[-1] if hist else None

            def count_since(delta: timedelta, failed: bool | None = None) -> int:
                cutoff = ts - delta
                return sum(
                    1 for h in hist if aware(h.ts) >= cutoff and (failed is None or h.failed == failed)
                )

            avg = sum(amounts) / len(amounts) if amounts else NAN
            if len(amounts) >= 3:
                mean = avg
                var = sum((a - mean) ** 2 for a in amounts) / (len(amounts) - 1)
                std = max(math.sqrt(var), 1.0)
                z = (t.amount - mean) / std
            else:
                z = NAN

            merchant_risk, high_risk = self.ctx.merchants.get(t.merchant_id or "", (0.0, False))
            dev_custs = self.device_customers.get(t.device_id, set())
            dest_custs = self.dest_customers.get(t.destination_id, set())
            known_devices = {h.device_id for h in hist}
            devices_30d = {h.device_id for h in hist if aware(h.ts) >= ts - timedelta(days=30)} | {t.device_id}

            if prev is not None:
                dist_prev = haversine_km(prev.lat, prev.lon, t.lat, t.lon)
                hours = max((ts - aware(prev.ts)).total_seconds() / 3600.0, 1e-3)
                velocity = min(dist_prev / hours, 5000.0) if dist_prev > 1 else 0.0
                hours_since = (ts - aware(prev.ts)).total_seconds() / 3600.0
            else:
                dist_prev = velocity = hours_since = NAN

            home = self.ctx.homes.get(t.customer_id)
            dist_home = haversine_km(home[0], home[1], t.lat, t.lon) if home else NAN

            return {
                "amount": float(t.amount),
                "log_amount": math.log1p(float(t.amount)),
                "txn_count_1h": count_since(timedelta(hours=1)),
                "txn_count_24h": count_since(timedelta(hours=24)),
                "txn_count_7d": count_since(timedelta(days=7)),
                "hours_since_prev": hours_since,
                "cust_avg_amount": avg,
                "amount_to_avg_ratio": (t.amount / avg) if amounts and avg > 0 else NAN,
                "amount_zscore": z,
                "merchant_risk_score": float(merchant_risk),
                "merchant_high_risk_category": float(high_risk),
                "is_p2p_transfer": 0.0 if t.merchant_id else 1.0,
                "device_distinct_customers": float(len(dev_custs | {t.customer_id})),
                "device_new_for_customer": float(bool(hist) and t.device_id not in known_devices),
                "customer_distinct_devices_30d": float(len(devices_30d)),
                "geo_distance_prev_km": dist_prev,
                "geo_velocity_kmh": velocity,
                "distance_from_home_km": dist_home,
                "failed_count_24h": count_since(timedelta(hours=24), failed=True),
                "failed_count_7d": count_since(timedelta(days=7), failed=True),
                "destination_distinct_customers": float(len(dest_custs | {t.customer_id})),
                "destination_flagged": float(self.ctx.destinations.get(t.destination_id, False)),
                "customer_flagged_dest_interactions": float(self.cust_flagged_dest.get(t.customer_id, 0)),
                "hour_of_day": float(ts.hour),
                "is_night": float(ts.hour < 5),
                "is_first_txn": float(not hist),
            }

    def add(self, t: TxnRecord) -> None:
        with self.lock:
            if t.id in self.seen_ids:
                return
            self.seen_ids.add(t.id)
            lst = self.cust_txns[t.customer_id]
            lst.append(t)
            if len(lst) > 1 and aware(lst[-2].ts) > aware(t.ts):
                lst.sort(key=lambda r: aware(r.ts))
            self.device_customers[t.device_id].add(t.customer_id)
            self.dest_customers[t.destination_id].add(t.customer_id)
            if self.ctx.destinations.get(t.destination_id, False):
                self.cust_flagged_dest[t.customer_id] += 1


def record_from_txn(txn) -> TxnRecord:
    return TxnRecord(
        id=txn.id,
        customer_id=txn.customer_id,
        merchant_id=txn.merchant_id,
        device_id=txn.device_id,
        destination_id=txn.destination_id,
        amount=float(txn.amount),
        lat=txn.lat,
        lon=txn.lon,
        ts=aware(txn.created_at),
        failed=txn.status in ("FAILED", "CAPTURE_FAILED"),
    )
