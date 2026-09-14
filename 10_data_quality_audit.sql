-- Q10: Data-quality audit of the warehouse.
-- Business question (data MANAGEMENT, not analysis): can we trust this data?
-- A single query that reports the health checks an analytics-engineering team
-- runs continuously - null rates, orphaned foreign keys, duplicate detection,
-- and range sanity. Showing this signals data-governance maturity, not just
-- query skill.
-- Technique: UNION ALL of independent check subqueries into one tidy report.
SELECT 'customers: missing email'            AS check_name,
       COUNT(*)                              AS failing_rows
FROM dim_customer WHERE email IS NULL
UNION ALL
SELECT 'customers: duplicate email root',
       COUNT(*) - COUNT(DISTINCT REPLACE(email, '+dup', ''))
FROM dim_customer WHERE email IS NOT NULL
UNION ALL
SELECT 'orders: fact rows with no matching customer',
       COUNT(*)
FROM fact_order_items f
LEFT JOIN dim_customer c ON f.customer_id = c.customer_id
WHERE c.customer_id IS NULL
UNION ALL
SELECT 'order_items: non-positive quantity',
       COUNT(*)
FROM fact_order_items WHERE quantity <= 0
UNION ALL
SELECT 'order_items: negative net revenue',
       COUNT(*)
FROM fact_order_items WHERE net_revenue < 0
UNION ALL
SELECT 'order_items: discount outside [0,1]',
       COUNT(*)
FROM fact_order_items WHERE discount < 0 OR discount > 1
ORDER BY failing_rows DESC, check_name;
