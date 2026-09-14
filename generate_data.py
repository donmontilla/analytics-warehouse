"""
Generate a realistic synthetic retail dataset for the analytics warehouse.

Design goals:
- Multiple related tables (customers, products, orders, order_items) so the
  star-schema modeling step is meaningful.
- Believable business structure: customer acquisition spread over time, repeat
  purchasing, product categories with different price bands, seasonality, and a
  realistic long-tail of one-time vs. high-value customers.
- A few *intentional* data-quality problems in the raw layer (inconsistent
  casing, whitespace, a couple of duplicate customers, some null emails, mixed
  date formats) so the cleaning pipeline has something real to fix.

Deterministic via a fixed seed so results in the README are reproducible.
"""
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# resolve data/ relative to the repo root (parent of this script's folder)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

RNG = np.random.default_rng(42)
START = datetime(2023, 1, 1)
END = datetime(2024, 12, 31)
N_CUSTOMERS = 2000
N_PRODUCTS = 120

# ----------------------------------------------------------------- products
CATEGORIES = {
    "Electronics": (80, 1200),
    "Home & Kitchen": (15, 300),
    "Apparel": (12, 150),
    "Sports & Outdoors": (20, 400),
    "Books": (8, 45),
    "Beauty": (10, 120),
}
prod_rows = []
for pid in range(1, N_PRODUCTS + 1):
    cat = RNG.choice(list(CATEGORIES.keys()), p=[0.18, 0.22, 0.25, 0.15, 0.12, 0.08])
    lo, hi = CATEGORIES[cat]
    # log-uniform-ish price within the category band
    price = float(np.round(np.exp(RNG.uniform(np.log(lo), np.log(hi))), 2))
    cost = float(np.round(price * RNG.uniform(0.45, 0.75), 2))  # gross margin varies
    prod_rows.append({
        "product_id": pid,
        "product_name": f"{cat[:3].upper()}-{pid:04d}",
        "category": cat,
        "unit_price": price,
        "unit_cost": cost,
    })
products = pd.DataFrame(prod_rows)

# ----------------------------------------------------------------- customers
COUNTRIES = ["United States", "United Kingdom", "Canada", "Germany",
             "France", "Australia", "Japan"]
COUNTRY_P = [0.42, 0.14, 0.11, 0.10, 0.08, 0.08, 0.07]
FIRST = ["James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda",
         "William","Elizabeth","David","Barbara","Wei","Yuki","Hans","Marie","Liam","Olivia"]
LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
        "Chen","Tanaka","Mueller","Dubois","Wilson","Moore","Taylor","Lee"]

def signup_date():
    # acquisition ramps up over time (more customers join later)
    span = (END - START).days
    u = RNG.beta(1.6, 1.2)  # skew toward later dates
    return START + timedelta(days=int(u * span))

cust_rows = []
for cid in range(1, N_CUSTOMERS + 1):
    fn, ln = RNG.choice(FIRST), RNG.choice(LAST)
    country = RNG.choice(COUNTRIES, p=COUNTRY_P)
    su = signup_date()
    email = f"{fn.lower()}.{ln.lower()}{cid}@example.com"
    # inject dirtiness in the RAW layer only
    if RNG.random() < 0.04:
        email = None                                   # missing email
    if RNG.random() < 0.06:
        country = f"  {country}  "                     # stray whitespace
    if RNG.random() < 0.05:
        country = country.upper()                      # inconsistent casing
    cust_rows.append({
        "customer_id": cid,
        "first_name": fn,
        "last_name": ln,
        "email": email,
        "country": country,
        "signup_date": su.strftime("%Y-%m-%d"),
    })
customers = pd.DataFrame(cust_rows)

# a couple of genuine duplicate customers (same person, new id) for entity-resolution flavor
dupes = customers.sample(8, random_state=7).copy()
dupes["customer_id"] = range(N_CUSTOMERS + 1, N_CUSTOMERS + 1 + len(dupes))
dupes["email"] = dupes["email"].apply(
    lambda e: (e.replace("@", "+dup@") if isinstance(e, str) else e))
customers = pd.concat([customers, dupes], ignore_index=True)

# ----------------------------------------------------------------- orders
# Each customer makes a Poisson number of orders after signup; some churn early,
# a few are heavy repeat buyers. Order dates respect signup and get seasonality.
def seasonal_weight(d: datetime) -> float:
    # holiday bump in Nov/Dec, mild summer dip
    m = d.month
    if m in (11, 12): return 1.8
    if m in (6, 7):   return 0.85
    return 1.0

order_rows, item_rows = [], []
order_id = 1
active_customer_ids = customers["customer_id"].tolist()
signup_lookup = dict(zip(customers["customer_id"],
                         pd.to_datetime(customers["signup_date"])))

for cid in active_customer_ids:
    su = signup_lookup[cid].to_pydatetime()
    days_available = max((END - su).days, 1)
    # heavy-tailed order counts: most buy 0-3 times, a few buy a lot
    lam = RNG.gamma(shape=1.3, scale=1.4)
    n_orders = RNG.poisson(lam)
    n_orders = min(n_orders, 40)
    for _ in range(n_orders):
        # order date after signup, seasonally weighted via rejection sampling
        for _try in range(6):
            offset = int(RNG.uniform(0, days_available))
            od = su + timedelta(days=offset)
            if RNG.random() < seasonal_weight(od) / 1.8:
                break
        # mixed date formats in the RAW layer
        if RNG.random() < 0.10:
            od_str = od.strftime("%m/%d/%Y")            # US slash format
        else:
            od_str = od.strftime("%Y-%m-%d")            # ISO
        channel = RNG.choice(["Web", "Mobile", "In-Store"], p=[0.55, 0.32, 0.13])
        order_rows.append({
            "order_id": order_id,
            "customer_id": cid,
            "order_date": od_str,
            "channel": channel,
        })
        # 1-5 line items per order
        n_items = 1 + RNG.integers(0, 5)
        chosen = RNG.choice(products["product_id"].values,
                            size=n_items, replace=False)
        for pid in chosen:
            qty = 1 + int(RNG.integers(0, 4))
            prow = products.loc[products["product_id"] == pid].iloc[0]
            # occasional discount
            disc = float(RNG.choice([0, 0, 0, 0.1, 0.15, 0.2],
                                    p=[0.55, 0.15, 0.1, 0.1, 0.06, 0.04]))
            item_rows.append({
                "order_id": order_id,
                "product_id": int(pid),
                "quantity": qty,
                "unit_price": float(prow["unit_price"]),
                "discount": disc,
            })
        order_id += 1

orders = pd.DataFrame(order_rows)
order_items = pd.DataFrame(item_rows)

# ----------------------------------------------------------------- write raw
products.to_csv(os.path.join(DATA_DIR, "raw_products.csv"), index=False)
customers.to_csv(os.path.join(DATA_DIR, "raw_customers.csv"), index=False)
orders.to_csv(os.path.join(DATA_DIR, "raw_orders.csv"), index=False)
order_items.to_csv(os.path.join(DATA_DIR, "raw_order_items.csv"), index=False)

print("Generated raw data:")
print(f"  products:    {len(products):>6,} rows")
print(f"  customers:   {len(customers):>6,} rows  ({len(dupes)} intentional duplicates)")
print(f"  orders:      {len(orders):>6,} rows")
print(f"  order_items: {len(order_items):>6,} rows")
print(f"  date range:  {START.date()} .. {END.date()}")
print(f"  revenue (gross, pre-discount check): "
      f"${(order_items['quantity']*order_items['unit_price']).sum():,.0f}")
