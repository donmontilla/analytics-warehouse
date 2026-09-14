-- Q8: Top 3 products within each category by revenue.
-- Business question: what are the best-selling products in each category - the
-- kind of "top N per group" question dashboards ask constantly?
-- Technique: RANK() within a PARTITION BY category, then filter to rank <= 3.
-- The canonical top-N-per-group pattern, which is awkward without window
-- functions and clean with them.
WITH product_rev AS (
    SELECT
        p.category,
        p.product_id,
        p.product_name,
        ROUND(SUM(f.net_revenue), 2) AS revenue,
        SUM(f.quantity)              AS units
    FROM fact_order_items f
    JOIN dim_product p ON f.product_id = p.product_id
    GROUP BY p.category, p.product_id, p.product_name
),
ranked AS (
    SELECT *,
        RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rank_in_cat
    FROM product_rev
)
SELECT category, rank_in_cat, product_name, revenue, units
FROM ranked
WHERE rank_in_cat <= 3
ORDER BY category, rank_in_cat;
