-- Q3: Top customers by lifetime value, tagged with a value segment.
-- Business question: who are the most valuable customers, and how concentrated
-- is revenue among them?
-- Technique: aggregate per customer, then use CASE to bucket them, and RANK.
-- Shows customer-level rollups plus segmentation logic in SQL.
WITH customer_value AS (
    SELECT
        f.customer_id,
        COUNT(DISTINCT f.order_id)          AS orders,
        ROUND(SUM(f.net_revenue), 2)        AS lifetime_value,
        ROUND(AVG(f.net_revenue), 2)        AS avg_line_value
    FROM fact_order_items f
    GROUP BY f.customer_id
)
SELECT
    cv.customer_id,
    c.country,
    cv.orders,
    cv.lifetime_value,
    CASE
        WHEN cv.lifetime_value >= 5000 THEN 'High-value'
        WHEN cv.lifetime_value >= 1500 THEN 'Mid-value'
        WHEN cv.orders = 1            THEN 'One-time'
        ELSE 'Low-value'
    END                                     AS segment,
    RANK() OVER (ORDER BY cv.lifetime_value DESC) AS ltv_rank
FROM customer_value cv
JOIN dim_customer c ON cv.customer_id = c.customer_id
ORDER BY cv.lifetime_value DESC
LIMIT 15;
