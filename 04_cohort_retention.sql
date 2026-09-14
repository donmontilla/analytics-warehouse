-- Q4: Monthly cohort retention (the flagship analysis).
-- Business question: of the customers who first ordered in a given month, what
-- share came back to order again 1, 2, 3... months later?
-- Technique: assign each customer to a cohort (their first-order month), compute
-- the month-offset of every subsequent order, count distinct returning customers
-- per (cohort, offset), and express as a % of the cohort's starting size.
-- This is the query that separates real analysts from beginners: it needs a
-- self-referencing first-purchase calculation, date differencing, and a pivot.
WITH first_order AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM fact_order_items
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT
        f.customer_id,
        fo.cohort_month,
        DATE_TRUNC('month', f.order_date) AS activity_month,
        DATEDIFF('month', fo.cohort_month,
                 DATE_TRUNC('month', f.order_date)) AS month_offset
    FROM fact_order_items f
    JOIN first_order fo ON f.customer_id = fo.customer_id
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS n_customers
    FROM first_order
    GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    cs.n_customers                                          AS cohort_size,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_offset = 0 THEN a.customer_id END)
                / cs.n_customers, 0)                        AS m0,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_offset = 1 THEN a.customer_id END)
                / cs.n_customers, 0)                        AS m1,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_offset = 2 THEN a.customer_id END)
                / cs.n_customers, 0)                        AS m2,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_offset = 3 THEN a.customer_id END)
                / cs.n_customers, 0)                        AS m3
FROM activity a
JOIN cohort_size cs ON a.cohort_month = cs.cohort_month
GROUP BY a.cohort_month, cs.n_customers
ORDER BY a.cohort_month
LIMIT 12;
