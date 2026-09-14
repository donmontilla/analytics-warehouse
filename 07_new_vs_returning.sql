-- Q7: New vs. returning customer revenue, by month.
-- Business question: how much of each month's revenue comes from brand-new
-- customers vs. existing ones? A core growth-quality metric - revenue leaning on
-- constant new acquisition is riskier than revenue from a loyal base.
-- Technique: determine each customer's first-order month, then classify every
-- order as 'New' (same month as acquisition) or 'Returning', and pivot with
-- conditional aggregation.
WITH first_order AS (
    SELECT customer_id, DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM fact_order_items
    GROUP BY customer_id
),
tagged AS (
    SELECT
        d.year_month,
        CASE WHEN DATE_TRUNC('month', f.order_date) = fo.cohort_month
             THEN 'New' ELSE 'Returning' END AS customer_type,
        f.net_revenue
    FROM fact_order_items f
    JOIN first_order fo ON f.customer_id = fo.customer_id
    JOIN dim_date d     ON f.order_date = d.date
)
SELECT
    year_month,
    ROUND(SUM(CASE WHEN customer_type = 'New'       THEN net_revenue END), 2)
        AS new_revenue,
    ROUND(SUM(CASE WHEN customer_type = 'Returning' THEN net_revenue END), 2)
        AS returning_revenue,
    ROUND(100.0 * SUM(CASE WHEN customer_type = 'Returning' THEN net_revenue END)
                / NULLIF(SUM(net_revenue), 0), 1)
        AS returning_pct
FROM tagged
GROUP BY year_month
ORDER BY year_month;
