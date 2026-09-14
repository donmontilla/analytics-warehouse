-- Q5: Per-customer purchase sequence - running spend and days between orders.
-- Business question: how do individual customers behave over time - are gaps
-- between purchases widening (disengaging) or tightening (habitual)?
-- Technique: window functions partitioned by customer and ordered by date:
-- a running SUM for cumulative spend and LAG on the date to get the gap between
-- consecutive orders. This is the canonical "window functions" showcase.
WITH order_level AS (
    -- collapse line items to one row per order first
    SELECT
        customer_id,
        order_id,
        order_date,
        SUM(net_revenue) AS order_revenue
    FROM fact_order_items
    GROUP BY customer_id, order_id, order_date
)
SELECT
    customer_id,
    order_id,
    order_date,
    order_revenue,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id)
        AS order_seq,
    SUM(order_revenue) OVER (
        PARTITION BY customer_id ORDER BY order_date, order_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_spend,
    DATEDIFF('day',
        LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id),
        order_date
    ) AS days_since_prev_order
FROM order_level
-- show a single illustrative repeat customer so the sequence is readable
WHERE customer_id = (
    SELECT customer_id
    FROM order_level
    GROUP BY customer_id
    ORDER BY COUNT(*) DESC
    LIMIT 1
)
ORDER BY order_seq;
