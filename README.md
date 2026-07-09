# Retail Analytics Warehouse — SQL from Raw Data to Business Answers

![SQL](https://img.shields.io/badge/SQL-DuckDB-yellow)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

An end-to-end analytics project: generate a realistic multi-table retail dataset, **clean it**, model it into a **star schema**, and answer ten business questions in **pure SQL** — cohort retention, customer lifetime value, RFM segmentation, channel mix, revenue trends, and a data-quality audit. Built on **DuckDB** so the entire thing runs with zero database setup — clone it, run one command, and every query executes against a real warehouse.

The focus is the two skills analytics and data-management interviews actually screen for: **writing non-trivial SQL** (window functions, cohort logic, ranked partitions) and **modeling messy operational data into a clean, queryable structure**.

```bash
pip install -r requirements.txt
python run_all.py          # generates data, builds the warehouse, runs every query
```

## The data model

Four raw operational tables (`customers`, `products`, `orders`, `order_items`) are cleaned and modeled into a star schema: one **fact table** at transaction grain surrounded by **conformed dimensions**. Analysts query this shape constantly because it makes time-based grouping, segmentation, and joins trivial — the date parsing and string cleaning happen *once*, at build time, not in every query.

![Star schema](assets/star_schema.svg)

The build step (`scripts/build_warehouse.py`) does real cleaning along the way:
- **Inconsistent country values** (`  UNITED STATES  `, `united states`) → normalized to clean Title Case.
- **Mixed date formats** — order dates arrive as both `YYYY-MM-DD` and `MM/DD/YYYY`; both are parsed via coalesced `TRY_STRPTIME` (0 unparseable after cleaning).
- **A pre-computed date dimension** so no query re-parses dates.
- **Money columns** (`net_revenue`, `gross_profit`) computed once in the fact table.

## What the analysis found

A few headline results from the ten queries (full tables below, all reproducible):

- **Revenue grew from ~$5K/month to ~$820K/month** over two years, with pronounced **Nov/Dec seasonal spikes** — the holiday bump is clearly visible.
- **Electronics drives revenue** ($1.86M, ~53% of total) **and** carries the best gross margin (~41%), so it's both the biggest and one of the most profitable categories — not always the case.
- **Returning customers make up ~50–65% of monthly revenue** in the mature months, a sign the business isn't running purely on new-customer acquisition.
- **Cohort retention decays to ~15–30% by month 3** — typical for retail, and the kind of curve that anchors any retention conversation.

![Revenue trend](assets/revenue_trend.png)

![Cohort retention](assets/cohort_retention.png)

![Category revenue](assets/category_revenue.png)

![Channel mix](assets/channel_mix.png)

## The ten business questions

Each lives in `sql/` as a standalone, commented query. Question → what it demonstrates → result.

### 1. Monthly revenue with month-over-month growth
*Window functions (`LAG`) over an ordered monthly aggregate.* Tracks the revenue trend and flags which months accelerated or slipped.

### 2. Revenue and margin by category
*Dimensional slice + margin ratio.* Separates "big" categories from "profitable" ones — revenue and margin aren't the same thing.

| category | orders | units | net_revenue | gross_profit | margin_pct |
|:--|--:|--:|--:|--:|--:|
| Electronics | 1435 | 4425 | 1,858,774 | 763,586 | 41.1 |
| Sports & Outdoors | 1712 | 5523 | 600,017 | 252,704 | 42.1 |
| Home & Kitchen | 1729 | 5511 | 556,641 | 195,396 | 35.1 |
| Apparel | 2033 | 7064 | 324,269 | 124,969 | 38.5 |
| Beauty | 612 | 1617 | 74,530 | 26,574 | 35.7 |
| Books | 1107 | 3128 | 72,231 | 27,061 | 37.5 |

### 3. Top customers by lifetime value
*Per-customer rollup + `CASE` segmentation + `RANK`.* Identifies the most valuable customers and how concentrated revenue is.

### 4. Cohort retention *(the flagship query)*
*First-purchase cohorting, month-offset date differencing, and a conditional-aggregation pivot.* Of the customers who first ordered in a given month, what share returned 1/2/3 months later? This is the query that most separates real analysts from beginners — and the math is **verified by hand** against the raw data in the build notes.

| cohort_month | size | M0 | M1 | M2 | M3 |
|:--|--:|--:|--:|--:|--:|
| 2023-07 | 23 | 100% | 13% | 13% | 17% |
| 2023-08 | 28 | 100% | 7% | 14% | 32% |
| 2023-09 | 32 | 100% | 16% | 19% | 34% |
| 2023-10 | 40 | 100% | 15% | 18% | 10% |
| 2023-11 | 40 | 100% | 23% | 13% | 13% |
| 2023-12 | 68 | 100% | 7% | 10% | 15% |

### 5. Per-customer purchase sequence
*Partitioned window functions: running `SUM` for cumulative spend, `LAG` on date for the gap between orders.* The canonical window-function showcase, applied to one repeat customer's full order history.

### 6. Channel mix over time
*Windowed ratio-to-total (`SUM() OVER (PARTITION BY month)`).* Turns absolute channel revenue into share-of-month to reveal whether the Web/Mobile/In-Store mix is shifting.

### 7. New vs. returning revenue
*First-order tagging + conditional aggregation.* Splits each month's revenue into new-customer vs. returning — a core growth-quality metric.

### 8. Top 3 products per category
*`RANK() OVER (PARTITION BY category)` then filter.* The "top-N-per-group" pattern that's awkward without window functions and clean with them.

### 9. RFM segmentation
*Recency/Frequency/Monetary scored into quartiles with `NTILE`, combined into a targetable grade.* Turns raw transactions into a marketing segmentation scheme (Champions, Loyal, At-risk…).

### 10. Data-quality audit *(the data-management piece)*
*A single `UNION ALL` health report: null rates, orphaned foreign keys, duplicate detection, range checks.* Signals data-governance maturity — the checks an analytics-engineering team runs continuously. It correctly catches the 85 missing emails and 8 duplicate customers intentionally seeded into the raw data.

| check_name | failing_rows |
|:--|--:|
| customers: missing email | 85 |
| customers: duplicate email root | 8 |
| orders: fact rows with no matching customer | 0 |
| order_items: non-positive quantity | 0 |
| order_items: negative net revenue | 0 |
| order_items: discount outside [0,1] | 0 |

## Repository structure

```
.
├── run_all.py                  # one command: data -> warehouse -> charts -> queries
├── scripts/
│   ├── generate_data.py        # synthetic raw data (deterministic, with real dirtiness)
│   ├── build_warehouse.py      # clean + model into the star schema (DuckDB)
│   ├── run_queries.py          # execute every sql/ file; --markdown for report tables
│   └── make_charts.py          # render the assets/*.png charts
├── sql/                        # the ten business-question queries, one file each
│   ├── 01_monthly_revenue_growth.sql
│   ├── ...
│   └── 10_data_quality_audit.sql
├── data/                       # generated raw CSVs (created by run_all.py)
├── assets/                     # schema diagram + charts
├── requirements.txt
├── LICENSE
└── README.md
```

## Running individual pieces

```bash
python scripts/build_warehouse.py     # rebuild just the database
python scripts/run_queries.py         # run all queries, pretty-printed
python scripts/run_queries.py 04      # run just the cohort-retention query
python scripts/run_queries.py --markdown   # emit Markdown tables
```

You can also open `warehouse.duckdb` in any DuckDB client and run the `sql/` files directly.

## Notes and honest scope

The dataset is **synthetically generated**, not scraped from a real company — this is deliberate: it lets the project ship with a reproducible, shareable dataset that has known-correct answers (so the cohort math can be verified) and controlled data-quality issues (so the cleaning and audit steps have something real to do). The generation logic builds in believable structure — time-varying acquisition, seasonality, heavy-tailed purchase frequency, category price bands — rather than uniform noise. The SQL techniques, schema design, and analyses are exactly what they'd be against real data; only the source is synthetic. Swapping in a real dataset (e.g., the UCI Online Retail set) would mean rewriting the loader in `build_warehouse.py` and leaving the `sql/` queries essentially unchanged.

## Development notes

Developed with AI-assisted coding. The schema design, the choice and construction of each business question, the data-quality checks, and the interpretation of results are my own, and the SQL is documented at the level I can explain in conversation. The cohort-retention calculation was independently verified against the raw records rather than trusted from the query output alone.

## Author

**Don Montilla** — B.S. Business Economics, UC San Diego · [LinkedIn](https://www.linkedin.com/in/donalfonso/)

Licensed under the [MIT License](LICENSE).
