-- Q1: Monthly net revenue with month-over-month growth.
-- Business question: how is revenue trending, and which months accelerated or slid?
-- Technique: aggregate to month via the date dimension, then LAG() for the prior
-- month plus a window-based percent change. Demonstrates window functions layered
-- on top of an ordered aggregate.
WITH monthly AS (
    SELECT
        d.year_month,
        SUM(f.net_revenue) AS revenue
    FROM fact_order_items f
    JOIN dim_date d ON f.order_date = d.date
    GROUP BY d.year_month
)
SELECT
    year_month,
    revenue,
    LAG(revenue) OVER (ORDER BY year_month) AS prev_month_revenue,
    ROUND(
        100.0 * (revenue - LAG(revenue) OVER (ORDER BY year_month))
        / NULLIF(LAG(revenue) OVER (ORDER BY year_month), 0), 1
    ) AS mom_growth_pct
FROM monthly
ORDER BY year_month;
