"""Deterministic synthetic financial environment (SYNTHETIC DEMO DATA - no real people or accounts).

Produces 100 customers, 25 merchants, 150 devices, 2,000 transactions with labelled fraud
patterns: a device-farm ring funnelling money to mule destinations, a circular wallet ring,
account takeovers, card testing, plus deliberate label noise so model metrics stay honest.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

SEED = 2026
N_CUSTOMERS = 100
N_TRANSACTIONS = 2000

CITIES = [
    ("San Francisco", "US", 37.77, -122.42), ("Chicago", "US", 41.88, -87.63), ("Miami", "US", 25.76, -80.19),
    ("New York", "US", 40.71, -74.01), ("Austin", "US", 30.27, -97.74), ("Seattle", "US", 47.61, -122.33),
    ("Boston", "US", 42.36, -71.06), ("Denver", "US", 39.74, -104.99), ("Toronto", "CA", 43.65, -79.38),
    ("London", "GB", 51.51, -0.13), ("Berlin", "DE", 52.52, 13.40), ("Dublin", "IE", 53.35, -6.26),
]
FAR_LOCATIONS = [
    ("Lagos", "NG", 6.52, 3.38), ("Bucharest", "RO", 44.43, 26.10), ("Jakarta", "ID", -6.21, 106.85),
    ("Manila", "PH", 14.60, 120.98), ("Caracas", "VE", 10.48, -66.90),
]
FIRST = ["Liam", "Noah", "Olivia", "Emma", "Mia", "Lucas", "Amara", "Ethan", "Sofia", "Kai", "Priya", "Mateo",
         "Hana", "Leo", "Zara", "Owen", "Isla", "Ravi", "Nora", "Felix", "Chloe", "Diego", "Maya", "Jonas",
         "Aisha", "Hugo", "Lena", "Omar", "Ivy", "Theo"]
LAST = ["Nguyen", "Patel", "Garcia", "Kim", "Okafor", "Silva", "Müller", "Rossi", "Haddad", "Cohen", "Walsh",
        "Tanaka", "Moreau", "Ivanova", "Mensah", "Larsen", "Costa", "Reyes", "Brooks", "Sato", "Fischer",
        "Romero", "Hughes", "Dubois", "Novak"]

# id, name, category, risk_score, high_risk_category, chargeback_rate, amount_multiplier
MERCHANTS = [
    ("MER_001", "Northwind Electronics", "Electronics", 0.18, False, 0.011, 3.5),
    ("MER_002", "Hearth & Home", "Home Goods", 0.06, False, 0.004, 1.2),
    ("MER_003", "Atlas Outfitters", "Outdoor", 0.07, False, 0.005, 1.6),
    ("MER_004", "Paper Lantern Books", "Books", 0.03, False, 0.002, 0.6),
    ("MER_005", "Ember Coffee Roasters", "Food & Beverage", 0.04, False, 0.002, 0.45),
    ("MER_006", "Lumen Beauty", "Beauty", 0.08, False, 0.006, 0.9),
    ("MER_007", "FreshCart Grocery", "Groceries", 0.03, False, 0.002, 1.0),
    ("MER_008", "Skyline Air Travel", "Travel", 0.20, False, 0.014, 6.0),
    ("MER_009", "StreamBox Media", "Digital Subscriptions", 0.09, False, 0.008, 0.25),
    ("MER_010", "Velocity Sports", "Sporting Goods", 0.07, False, 0.005, 1.4),
    ("MER_011", "Greenleaf Pharmacy", "Pharmacy", 0.05, False, 0.003, 0.7),
    ("MER_012", "Urban Plate", "Restaurants", 0.04, False, 0.003, 0.8),
    ("MER_013", "PixelForge Games", "Gaming", 0.15, False, 0.012, 0.9),
    ("MER_014", "Pawsome Pet Supply", "Pet Supplies", 0.04, False, 0.002, 0.8),
    ("MER_015", "Ledger Office Co", "Office Supplies", 0.05, False, 0.003, 1.1),
    ("MER_016", "Harbor Fashion", "Apparel", 0.09, False, 0.007, 1.3),
    ("MER_017", "Nimbus Cloud Storage", "Software", 0.06, False, 0.004, 0.4),
    ("MER_018", "Brightside Toys", "Toys", 0.05, False, 0.003, 0.9),
    ("MER_019", "Copperline Hardware", "Hardware", 0.06, False, 0.004, 1.5),
    ("MER_020", "Meridian Hotels", "Hospitality", 0.14, False, 0.010, 4.0),
    ("MER_021", "VaultGift Digital", "Gift Cards", 0.72, True, 0.061, 3.0),
    ("MER_022", "CoinBridge Exchange", "Crypto On-Ramp", 0.80, True, 0.074, 5.0),
    ("MER_023", "QuickFlip Resale", "Electronics Resale", 0.58, True, 0.043, 4.0),
    ("MER_024", "LuckyStrike Gaming", "Online Gaming Credits", 0.66, True, 0.052, 2.0),
    ("MER_025", "Orbit Mobile Top-Up", "Prepaid Mobile", 0.45, True, 0.031, 0.5),
]
NORMAL_MERCHANTS = [m[0] for m in MERCHANTS if not m[4]]
HIGH_RISK_MERCHANTS = [m[0] for m in MERCHANTS if m[4]]
MERCHANT_MULT = {m[0]: m[6] for m in MERCHANTS}

# Marketplace catalogue for SENTINEL MERCHANT (synthetic products, sold by the merchants above)
PRODUCTS = [
    ("PRD_001", "Aurora ANC Headphones", "Over-ear noise-cancelling headphones with 40h battery and adaptive transparency.", "Audio", 249.00, "headphones", "MER_001"),
    ("PRD_002", "Pulse Smartwatch S2", "Health tracking, ECG, GPS and a 7-day battery in an aluminium case.", "Wearables", 199.00, "watch", "MER_001"),
    ("PRD_003", "Vector 14\" Ultrabook", "14-inch 2.8K OLED, 32GB RAM, 1TB SSD. Built for engineers.", "Computers", 1849.00, "laptop", "MER_001"),
    ("PRD_004", "Strata 4K Action Camera", "Stabilised 4K60 action camera, waterproof to 10m.", "Cameras", 329.00, "camera", "MER_001"),
    ("PRD_005", "Ceramic Pour-Over Set", "Hand-glazed dripper, carafe and two cups.", "Kitchen", 48.00, "coffee", "MER_002"),
    ("PRD_006", "Linen Throw Blanket", "Stonewashed European linen, 130x170cm.", "Home", 64.00, "home", "MER_002"),
    ("PRD_007", "Trailblazer Running Shoes", "Lightweight trail shoes with rock plate and grippy lugs.", "Footwear", 129.00, "shoe", "MER_003"),
    ("PRD_008", "Packable Rain Shell", "2.5-layer waterproof shell that packs into its own pocket.", "Apparel", 89.00, "shirt", "MER_003"),
    ("PRD_009", "Designing Payment Systems", "A practical handbook on ledgers, idempotency and settlement.", "Books", 42.00, "book", "MER_004"),
    ("PRD_010", "The Fintech Atlas", "Illustrated guide to how money moves around the world.", "Books", 36.00, "book", "MER_004"),
    ("PRD_011", "Single-Origin Sampler", "Four 100g bags of seasonal single-origin coffee.", "Coffee", 28.00, "coffee", "MER_005"),
    ("PRD_012", "Botanical Skincare Kit", "Cleanser, serum and moisturiser, fragrance-free.", "Beauty", 58.00, "sparkles", "MER_006"),
    ("PRD_013", "Universal Gift Card $500", "Digital gift card delivered instantly by email.", "Gift Cards", 500.00, "gift", "MER_021"),
    ("PRD_014", "Gaming Gift Card $250", "Digital credits redeemable across major game stores.", "Gift Cards", 250.00, "gamepad", "MER_021"),
    ("PRD_015", "Refurbished Flagship Phone", "Grade-A refurbished flagship smartphone, unlocked.", "Phones", 699.00, "phone", "MER_023"),
    ("PRD_016", "Pro Gaming Controller", "Hall-effect sticks, remappable paddles.", "Gaming", 79.00, "gamepad", "MER_013"),
]


@dataclass
class GenCustomer:
    id: str
    name: str
    email: str
    city: str
    country: str
    lat: float
    lon: float
    avg: float
    devices: list[str] = field(default_factory=list)
    favorites: list[str] = field(default_factory=list)
    segment: str = "RETAIL"


@dataclass
class GenDevice:
    id: str
    fingerprint: str
    device_type: str
    os: str


@dataclass
class GenDestination:
    id: str
    label: str
    kind: str
    owner: str | None = None
    flagged: bool = False
    reason: str | None = None


@dataclass
class GenTxn:
    customer_id: str
    merchant_id: str | None
    device_id: str
    destination_id: str
    amount: float
    lat: float
    lon: float
    ts: datetime
    failed: bool
    is_fraud: bool
    scenario: str
    description: str
    id: str = ""


@dataclass
class SyntheticWorld:
    customers: list[GenCustomer]
    devices: list[GenDevice]
    destinations: list[GenDestination]
    transactions: list[GenTxn]
    now: datetime


def _fp(seed: str) -> str:
    return "fp-" + hashlib.sha1(seed.encode()).hexdigest()[:20]


DEMO_PERSONAS = {
    "CUS_0001": ("Ava Thompson", "ava@shopper.sentinel.dev", 0, 55.0, "fp-ava-macbook-air"),
    "CUS_0002": ("Ben Carter", "ben@shopper.sentinel.dev", 1, 38.0, "fp-ben-iphone-15"),
    "CUS_0003": ("Cara Novak", "cara@shopper.sentinel.dev", 2, 70.0, "fp-cara-pixel-8"),
}
RING_DEVICE_FPS = ["fp-ring-emulator-01", "fp-ring-emulator-02", "fp-ring-emulator-03", "fp-ring-emulator-04"]


def generate(now: datetime | None = None) -> SyntheticWorld:
    rng = random.Random(SEED)
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    start = now - timedelta(days=90)

    def jitter(lat: float, lon: float, d: float = 0.04) -> tuple[float, float]:
        return lat + rng.uniform(-d, d), lon + rng.uniform(-d, d)

    def rand_time(days_back_min: float, days_back_max: float, night: bool = False) -> datetime:
        base = now - timedelta(days=rng.uniform(days_back_min, days_back_max))
        hour = rng.randint(0, 4) if night else int(min(22, max(7, rng.gauss(15, 3.5))))
        return base.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))

    # ------------------------------------------------------------ customers
    customers: list[GenCustomer] = []
    for i in range(1, N_CUSTOMERS + 1):
        cid = f"CUS_{i:04d}"
        if cid in DEMO_PERSONAS:
            name, email, city_idx, avg, _ = DEMO_PERSONAS[cid]
            city = CITIES[city_idx]
        else:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            email = f"{name.lower().replace(' ', '.').replace('ü', 'u')}.{i}@example.test"
            city = rng.choice(CITIES)
            avg = round(math.exp(rng.gauss(math.log(60), 0.45)), 2)
        favs = rng.sample(NORMAL_MERCHANTS, rng.randint(4, 7))
        customers.append(GenCustomer(cid, name, email, city[0], city[1], city[2], city[3], avg, favorites=favs))
    by_id = {c.id: c for c in customers}

    ring_a = ["CUS_0003"] + [f"CUS_{i:04d}" for i in range(90, 98)]  # device farm + mule funnel
    ring_b = [f"CUS_{i:04d}" for i in range(80, 84)]  # circular wallet ring
    for cid in ring_a + ring_b:
        by_id[cid].segment = "NEW_ACCOUNT" if cid != "CUS_0003" else "RETAIL"
    protected = set(DEMO_PERSONAS) | set(ring_a) | set(ring_b)
    normal_pool = [c.id for c in customers if c.id not in protected]

    # ------------------------------------------------------------ devices (150)
    devices: list[GenDevice] = []
    types = [("LAPTOP", "macOS 15"), ("LAPTOP", "Windows 11"), ("MOBILE", "iOS 18"), ("MOBILE", "Android 15"), ("TABLET", "iPadOS 18")]
    for i, c in enumerate(customers, start=1):
        did = f"DEV_{i:04d}"
        fp = DEMO_PERSONAS[c.id][4] if c.id in DEMO_PERSONAS else _fp(did)
        t = rng.choice(types)
        devices.append(GenDevice(did, fp, *t))
        c.devices.append(did)
    second_owners = rng.sample(normal_pool, 30)
    for k, cid in enumerate(second_owners, start=101):
        did = f"DEV_{k:04d}"
        devices.append(GenDevice(did, _fp(did), *rng.choice(types)))
        by_id[cid].devices.append(did)
    family_pairs = rng.sample([c for c in normal_pool if c not in second_owners], 16)
    for k in range(8):  # legitimately shared household devices
        did = f"DEV_{131 + k:04d}"
        devices.append(GenDevice(did, _fp(did), "TABLET", "iPadOS 18"))
        for cid in family_pairs[2 * k: 2 * k + 2]:
            by_id[cid].devices.append(did)
    ato_devices = []
    for k in range(8):
        did = f"DEV_{139 + k:04d}"
        devices.append(GenDevice(did, _fp(did), "LAPTOP", "Linux (spoofed UA)"))
        ato_devices.append(did)
    ring_devices = []
    for k in range(4):
        did = f"DEV_{147 + k:04d}"
        devices.append(GenDevice(did, RING_DEVICE_FPS[k], "MOBILE", "Android emulator"))
        ring_devices.append(did)
    assert len(devices) == 150

    # ------------------------------------------------------------ destinations
    destinations: list[GenDestination] = []
    merchant_dest = {}
    for m in MERCHANTS:
        did = f"DST_{m[0][4:]}"
        destinations.append(GenDestination(did, f"{m[1]} payout account", "MERCHANT_PAYOUT"))
        merchant_dest[m[0]] = did
    wallet_of: dict[str, str] = {}
    wallet_owners = ring_b + rng.sample(normal_pool, 15)
    for cid in wallet_owners:
        did = f"DST_W{cid[4:]}"
        destinations.append(GenDestination(did, f"Wallet of {by_id[cid].name}", "WALLET", owner=cid))
        wallet_of[cid] = did
    mules = ["DST_MULE_01", "DST_MULE_02"]
    for k, did in enumerate(mules, start=1):
        destinations.append(GenDestination(
            did, f"External wallet #{k} (unverified)", "WALLET", flagged=True,
            reason="Received funds from accounts with confirmed chargebacks (synthetic intelligence feed)",
        ))

    txns: list[GenTxn] = []

    def normal_txn(c: GenCustomer, ts: datetime, scenario: str = "NORMAL", merchant: str | None = None,
                   amount: float | None = None, fraud: bool = False) -> GenTxn:
        m = merchant or (rng.choice(c.favorites) if rng.random() > 0.03 else rng.choice(HIGH_RISK_MERCHANTS))
        amt = amount or round(max(2.0, math.exp(rng.gauss(math.log(c.avg * MERCHANT_MULT[m] ** 0.5), 0.45))), 2)
        dev = c.devices[0] if len(c.devices) == 1 or rng.random() < 0.75 else rng.choice(c.devices[1:])
        if rng.random() < 0.05:  # legitimate travel
            city = rng.choice(CITIES)
            lat, lon = jitter(city[2], city[3])
        else:
            lat, lon = jitter(c.lat, c.lon)
        failed = rng.random() < 0.03
        return GenTxn(c.id, m, dev, merchant_dest[m], amt, lat, lon, ts, failed, fraud, scenario,
                      "Card declined (insufficient funds)" if failed else "Purchase")

    # ------------------------------------------------------------ demo personas (clean history)
    for cid, n in (("CUS_0001", 22), ("CUS_0002", 20)):
        c = by_id[cid]
        for _ in range(n):
            t = normal_txn(c, rand_time(1, 88))
            t.failed = False
            t.merchant_id = rng.choice(c.favorites)
            t.destination_id = merchant_dest[t.merchant_id]
            t.amount = round(max(4.0, rng.gauss(c.avg, c.avg * 0.3)), 2)
            t.lat, t.lon = jitter(c.lat, c.lon)
            t.device_id = c.devices[0]
            txns.append(t)

    # ------------------------------------------------------------ ring A: device farm -> mule destinations
    for idx, cid in enumerate(ring_a):
        c = by_id[cid]
        for _ in range(rng.randint(2, 3)):  # warm-up activity looks legitimate
            t = normal_txn(c, rand_time(55, 88))
            t.failed = False
            txns.append(t)
        ring_dev = ring_devices[0] if idx % 2 == 0 else ring_devices[1]
        if idx in (3, 6):
            ring_dev = ring_devices[2 + idx % 2]
        for burst in range(rng.randint(2, 3)):
            burst_start = rand_time(1, 22, night=True)
            for j in range(rng.randint(2, 3)):
                ts = burst_start + timedelta(minutes=rng.randint(4, 25) * j)
                if rng.random() < 0.5:
                    m = rng.choice(["MER_021", "MER_022", "MER_024"])
                    dest, merchant, amt, desc = merchant_dest[m], m, round(rng.uniform(220, 620), 2), "Digital goods purchase"
                else:
                    dest, merchant, amt, desc = rng.choice(mules), None, round(rng.uniform(300, 950), 2), "Wallet transfer"
                lat, lon = jitter(25.76, -80.19, 0.3)  # farm operates from one metro area
                fraud = rng.random() < 0.92
                txns.append(GenTxn(cid, merchant, ring_dev if rng.random() < 0.85 else c.devices[0], dest, amt,
                                   lat, lon, ts, False, fraud, "RING_DEVICE_FARM", desc))

    # ------------------------------------------------------------ ring B: circular wallet transfers
    for rnd in range(6):
        base = now - timedelta(days=30 - rnd * 4.5, hours=rng.randint(0, 6))
        for k, cid in enumerate(ring_b):
            nxt = ring_b[(k + 1) % len(ring_b)]
            c = by_id[cid]
            ts = base + timedelta(minutes=17 * k + rng.randint(0, 9))
            amt = round(450 + rnd * 85 + rng.uniform(-30, 30), 2)
            lat, lon = jitter(c.lat, c.lon)
            txns.append(GenTxn(cid, None, c.devices[0], wallet_of[nxt], amt, lat, lon, ts, False, True,
                               "CIRCULAR_RING", "Wallet transfer"))
        for cid in ring_b:  # light warm-up purchases
            if rnd < 2:
                txns.append(normal_txn(by_id[cid], rand_time(40, 80)))

    # ------------------------------------------------------------ legitimate P2P transfers
    legit_wallet_owners = wallet_owners[4:]
    for _ in range(32):
        payer = by_id[rng.choice(normal_pool)]
        payee = rng.choice([w for w in legit_wallet_owners if w != payer.id])
        lat, lon = jitter(payer.lat, payer.lon)
        txns.append(GenTxn(payer.id, None, payer.devices[0], wallet_of[payee], round(rng.uniform(15, 160), 2),
                           lat, lon, rand_time(1, 88), False, False, "P2P_LEGIT", "Wallet transfer"))

    # ------------------------------------------------------------ account takeover
    ato_victims = rng.sample(normal_pool, 12)
    for k, cid in enumerate(ato_victims):
        c = by_id[cid]
        for _ in range(rng.randint(1, 2)):
            home_ts = rand_time(1, 30)
            txns.append(normal_txn(c, home_ts))
            far = rng.choice(FAR_LOCATIONS)
            lat, lon = jitter(far[2], far[3], 0.2)
            m = rng.choice(["MER_001", "MER_023", "MER_008", "MER_022"])
            ts = home_ts + timedelta(minutes=rng.randint(20, 180))
            amt = round(c.avg * rng.uniform(8, 25), 2)
            txns.append(GenTxn(cid, m, ato_devices[k % len(ato_devices)], merchant_dest[m], amt, lat, lon, ts,
                               False, True, "ACCOUNT_TAKEOVER", "Purchase"))

    # ------------------------------------------------------------ card testing
    for k, cid in enumerate(rng.sample([c for c in normal_pool if c not in ato_victims], 3)):
        c = by_id[cid]
        start_ts = rand_time(2, 25, night=True)
        dev = ato_devices[(k + 4) % len(ato_devices)]
        for j in range(rng.randint(5, 8)):
            m = rng.choice(["MER_025", "MER_009"])
            txns.append(GenTxn(cid, m, dev, merchant_dest[m], round(rng.uniform(1, 9), 2), c.lat + 0.3, c.lon - 0.3,
                               start_ts + timedelta(minutes=3 * j), True, True, "CARD_TESTING", "Card declined"))
        txns.append(GenTxn(cid, "MER_023", dev, merchant_dest["MER_023"], round(rng.uniform(300, 800), 2),
                           c.lat + 0.3, c.lon - 0.3, start_ts + timedelta(minutes=40), False, True, "CARD_TESTING",
                           "Purchase"))

    # ------------------------------------------------------------ legitimate large purchases (hard negatives)
    for cid in rng.sample(normal_pool, 22):
        c = by_id[cid]
        m = rng.choice(["MER_008", "MER_020", "MER_001"])
        txns.append(normal_txn(c, rand_time(1, 85), "LEGIT_LARGE", merchant=m,
                               amount=round(c.avg * rng.uniform(6, 15), 2)))

    # ------------------------------------------------------------ fill with normal behaviour
    remaining = N_TRANSACTIONS - len(txns)
    weights = [rng.uniform(0.5, 1.5) for _ in normal_pool]
    total_w = sum(weights)
    counts = [int(remaining * w / total_w) for w in weights]
    counts[0] += remaining - sum(counts)
    for cid, n in zip(normal_pool, counts):
        c = by_id[cid]
        for _ in range(n):
            txns.append(normal_txn(c, rand_time(0.1, 89.5)))

    # Friendly fraud: labelled fraud that is behaviourally indistinguishable (keeps metrics realistic)
    normals = [t for t in txns if t.scenario == "NORMAL" and t.customer_id in normal_pool and not t.failed]
    for t in rng.sample(normals, 16):
        t.is_fraud = True
        t.scenario = "FRIENDLY_FRAUD"

    assert len(txns) == N_TRANSACTIONS, len(txns)
    for t in txns:
        t.ts = max(start, min(t.ts, now - timedelta(minutes=5)))
    txns.sort(key=lambda t: t.ts)
    for i, t in enumerate(txns, start=1):
        t.id = f"TXN_{100000 + i}"
    return SyntheticWorld(customers, devices, destinations, txns, now)
