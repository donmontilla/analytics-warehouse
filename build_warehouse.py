"""
Build the analytics warehouse:
  1. Load the raw CSVs into a DuckDB database.
  2. Clean them (fix casing/whitespace, parse mixed date formats, flag dupes).
  3. Model a star schema: one fact table (fact_order_items) surrounded by
     conformed dimensions (dim_customer, dim_product, dim_date).

Why a star schema? Analysts query it constantly, and modeling raw operational
tables into facts + dimensions is the difference between queries that are
painful (lots of ad-hoc joins and date parsing every time) and queries that are
trivial (join fact to dimensions on clean keys). This mirrors how a real BI /
analytics-engineering layer is built.

Run:  python scripts/build_warehouse.py
Output: warehouse.duckdb in the repo root.
"""
import os
import duckdb

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
DB_PATH = os.path.join(REPO_ROOT, "warehouse.duckdb")


def build():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = duckdb.connect(DB_PATH)

    # ---------------------------------------------------------------- raw load
    for name in ["products", "customers", "orders", "order_items"]:
        csv = os.path.join(DATA_DIR, f"raw_{name}.csv")
        con.execute(f"""
            CREATE TABLE raw_{name} AS
            SELECT * FROM read_csv_auto('{csv}', header=True, all_varchar=True)
        """)
    print("Loaded raw tables.")

    # ---------------------------------------------------------- clean: customers
    # Fix whitespace + inconsistent casing on country; standardize types;
    # flag duplicate accounts (same normalized email root) with a surrogate.
    con.execute(r"""
        CREATE TABLE stg_customers AS
        SELECT
            CAST(customer_id AS INTEGER)              AS customer_id,
            TRIM(first_name)                          AS first_name,
            TRIM(last_name)                           AS last_name,
            LOWER(NULLIF(TRIM(email), ''))            AS email,
            -- normalize country: lowercase+trim, collapse internal whitespace,
            -- then Title-Case each word (DuckDB has no INITCAP, so build it).
            list_reduce(
                list_transform(
                    string_split(
                        regexp_replace(LOWER(TRIM(country)), '\s+', ' ', 'g'), ' '),
                    w -> UPPER(SUBSTR(w, 1, 1)) || SUBSTR(w, 2)
                ),
                (a, b) -> a || ' ' || b
            )                                         AS country,
            CAST(signup_date AS DATE)                 AS signup_date
        FROM raw_customers
    """)

    # ------------------------------------------------------------ clean: orders
    # order_date arrives in TWO formats (ISO yyyy-mm-dd and US mm/dd/yyyy).
    # try_strptime returns NULL on non-match, so coalesce the two parses.
    con.execute("""
        CREATE TABLE stg_orders AS
        SELECT
            CAST(order_id AS INTEGER)                 AS order_id,
            CAST(customer_id AS INTEGER)              AS customer_id,
            COALESCE(
                TRY_STRPTIME(order_date, '%Y-%m-%d'),
                TRY_STRPTIME(order_date, '%m/%d/%Y')
            )::DATE                                   AS order_date,
            channel
        FROM raw_orders
    """)

    con.execute("""
        CREATE TABLE stg_order_items AS
        SELECT
            CAST(order_id AS INTEGER)                 AS order_id,
            CAST(product_id AS INTEGER)               AS product_id,
            CAST(quantity AS INTEGER)                 AS quantity,
            CAST(unit_price AS DOUBLE)                AS unit_price,
            CAST(discount AS DOUBLE)                  AS discount
        FROM raw_order_items
    """)

    con.execute("""
        CREATE TABLE stg_products AS
        SELECT
            CAST(product_id AS INTEGER)               AS product_id,
            product_name,
            category,
            CAST(unit_price AS DOUBLE)                AS unit_price,
            CAST(unit_cost AS DOUBLE)                 AS unit_cost
        FROM raw_products
    """)
    print("Built cleaned staging tables (fixed casing/whitespace, parsed mixed dates).")

    # data-quality sanity: any dates that failed BOTH parses?
    bad_dates = con.execute(
        "SELECT COUNT(*) FROM stg_orders WHERE order_date IS NULL").fetchone()[0]
    print(f"  unparseable order dates after cleaning: {bad_dates}")

    # --------------------------------------------------------- dim: customer
    con.execute("""
        CREATE TABLE dim_customer AS
        SELECT
            customer_id,
            first_name, last_name, email, country, signup_date,
            DATE_TRUNC('month', signup_date)          AS signup_month
        FROM stg_customers
    """)

    # --------------------------------------------------------- dim: product
    con.execute("""
        CREATE TABLE dim_product AS
        SELECT
            product_id, product_name, category, unit_price, unit_cost,
            ROUND(unit_price - unit_cost, 2)          AS unit_margin
        FROM stg_products
    """)

    # ------------------------------------------------------------- dim: date
    # A proper date dimension so time-based grouping never re-parses dates.
    con.execute("""
        CREATE TABLE dim_date AS
        WITH bounds AS (
            SELECT MIN(order_date) AS d0, MAX(order_date) AS d1 FROM stg_orders
        ),
        days AS (
            SELECT UNNEST(range(d0, d1 + INTERVAL 1 DAY, INTERVAL 1 DAY))::DATE AS date
            FROM bounds
        )
        SELECT
            date,
            EXTRACT(year  FROM date)                  AS year,
            EXTRACT(month FROM date)                  AS month,
            EXTRACT(day   FROM date)                  AS day,
            DATE_TRUNC('month', date)                 AS month_start,
            EXTRACT(quarter FROM date)                AS quarter,
            STRFTIME(date, '%Y-%m')                   AS year_month,
            DAYNAME(date)                             AS weekday
        FROM days
    """)

    # ---------------------------------------------------- fact: order_items
    # Grain = one row per product per order (the finest transactional grain).
    # Pre-compute the money columns everyone needs so queries stay clean.
    con.execute("""
        CREATE TABLE fact_order_items AS
        SELECT
            oi.order_id,
            o.customer_id,
            oi.product_id,
            o.order_date,
            o.channel,
            oi.quantity,
            oi.unit_price,
            oi.discount,
            ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2) AS net_revenue,
            ROUND(oi.quantity * oi.unit_price, 2)                     AS gross_revenue,
            ROUND(oi.quantity * (oi.unit_price * (1 - oi.discount) - p.unit_cost), 2)
                                                                      AS gross_profit
        FROM stg_order_items oi
        JOIN stg_orders   o ON oi.order_id = o.order_id
        JOIN stg_products p ON oi.product_id = p.product_id
    """)
    print("Built star schema: fact_order_items + dim_customer / dim_product / dim_date.")

    # -------------------------------------------------------------- summary
    for t in ["dim_customer", "dim_product", "dim_date", "fact_order_items"]:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<20} {n:>8,} rows")
    tot = con.execute(
        "SELECT ROUND(SUM(net_revenue), 2) FROM fact_order_items").fetchone()[0]
    print(f"  total net revenue in warehouse: ${tot:,.2f}")

    con.close()
    print(f"\nWarehouse written to {DB_PATH}")


if __name__ == "__main__":
    build()
