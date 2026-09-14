"""
Generate charts from the warehouse for the README (assets/*.png).
Run after build_warehouse.py.
"""
import os
import duckdb
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(REPO_ROOT, "warehouse.duckdb")
ASSETS = REPO_ROOT

plt.rcParams.update({
    "figure.dpi": 120, "axes.grid": True, "grid.alpha": 0.25,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.titleweight": "bold", "axes.titlesize": 13,
})
BLUE = "#2874A6"

con = duckdb.connect(DB, read_only=True)

# ---------------------------------------------------------- 1) revenue trend
df = con.execute("""
    SELECT d.year_month AS ym, SUM(f.net_revenue) AS rev
    FROM fact_order_items f JOIN dim_date d ON f.order_date = d.date
    GROUP BY d.year_month ORDER BY d.year_month
""").df()
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(df["ym"], df["rev"], marker="o", lw=2, color=BLUE)
ax.set_title("Monthly Net Revenue")
ax.set_xlabel("Month"); ax.set_ylabel("Net revenue")
ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
ax.set_xticks(df["ym"][::2]); plt.xticks(rotation=45, ha="right")
plt.tight_layout(); plt.savefig(os.path.join(ASSETS, "revenue_trend.png")); plt.close()

# ------------------------------------------------------ 2) category revenue
df = con.execute("""
    SELECT p.category AS cat, SUM(f.net_revenue) AS rev,
           100.0*SUM(f.gross_profit)/NULLIF(SUM(f.net_revenue),0) AS margin
    FROM fact_order_items f JOIN dim_product p ON f.product_id = p.product_id
    GROUP BY p.category ORDER BY rev DESC
""").df()
fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.barh(df["cat"][::-1], df["rev"][::-1], color=BLUE, alpha=0.85)
ax.set_title("Net Revenue by Category (labels show gross margin %)")
ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
for b, m in zip(bars, df["margin"][::-1]):
    ax.text(b.get_width(), b.get_y() + b.get_height()/2,
            f"  {m:.0f}% margin", va="center", fontsize=9)
plt.tight_layout(); plt.savefig(os.path.join(ASSETS, "category_revenue.png")); plt.close()

# -------------------------------------------------- 3) cohort retention heatmap
df = con.execute("""
    WITH fo AS (SELECT customer_id, DATE_TRUNC('month', MIN(order_date)) cm
                FROM fact_order_items GROUP BY customer_id),
    act AS (SELECT DISTINCT f.customer_id, fo.cm,
                   DATEDIFF('month', fo.cm, DATE_TRUNC('month', f.order_date)) moff
            FROM fact_order_items f JOIN fo ON f.customer_id = fo.customer_id),
    sz AS (SELECT cm, COUNT(*) n FROM fo GROUP BY cm)
    SELECT act.cm AS cohort, moff,
           100.0*COUNT(DISTINCT act.customer_id)/sz.n AS pct
    FROM act JOIN sz ON act.cm = sz.cm
    WHERE moff <= 5
    GROUP BY act.cm, moff, sz.n ORDER BY act.cm, moff
""").df()
piv = df.pivot(index="cohort", columns="moff", values="pct")
# keep cohorts with enough history, drop the tiny earliest ones
piv = piv[piv.index >= np.datetime64("2023-06-01")]
fig, ax = plt.subplots(figsize=(9, 7))
im = ax.imshow(piv.values, cmap="Blues", aspect="auto", vmin=0, vmax=60)
ax.set_xticks(range(len(piv.columns)))
ax.set_xticklabels([f"M{c}" for c in piv.columns])
ax.set_yticks(range(len(piv.index)))
ax.set_yticklabels([str(d)[:7] for d in piv.index])
ax.set_title("Cohort Retention - % of signup cohort ordering again")
ax.set_xlabel("Months since first order"); ax.set_ylabel("Cohort (first-order month)")
for i in range(len(piv.index)):
    for j in range(len(piv.columns)):
        v = piv.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8,
                    color="white" if v > 35 else "black")
fig.colorbar(im, ax=ax, label="% retained")
plt.tight_layout(); plt.savefig(os.path.join(ASSETS, "cohort_retention.png")); plt.close()

# ----------------------------------------------------- 4) channel mix over time
df = con.execute("""
    SELECT d.year_month AS ym, f.channel AS ch, SUM(f.net_revenue) AS rev
    FROM fact_order_items f JOIN dim_date d ON f.order_date = d.date
    GROUP BY d.year_month, f.channel ORDER BY d.year_month
""").df()
piv = df.pivot(index="ym", columns="ch", values="rev").fillna(0)
piv_pct = piv.div(piv.sum(axis=1), axis=0) * 100
fig, ax = plt.subplots(figsize=(11, 5))
bottom = np.zeros(len(piv_pct))
colors = {"Web": "#2874A6", "Mobile": "#5DADE2", "In-Store": "#AED6F1"}
for ch in ["Web", "Mobile", "In-Store"]:
    if ch in piv_pct.columns:
        ax.bar(piv_pct.index, piv_pct[ch], bottom=bottom, label=ch,
               color=colors.get(ch))
        bottom += piv_pct[ch].values
ax.set_title("Sales Channel Mix Over Time (% of monthly revenue)")
ax.set_ylabel("% of month"); ax.set_xlabel("Month")
ax.yaxis.set_major_formatter(mtick.PercentFormatter())
ax.set_xticks(piv_pct.index[::2]); plt.xticks(rotation=45, ha="right")
ax.legend(frameon=False, ncol=3, loc="lower center")
plt.tight_layout(); plt.savefig(os.path.join(ASSETS, "channel_mix.png")); plt.close()

con.close()
print("Wrote charts:")
for f in sorted(os.listdir(ASSETS)):
    if f.endswith(".png"):
        print(" ", f)
