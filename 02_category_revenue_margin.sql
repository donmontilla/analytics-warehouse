-- Q2: Revenue, gross profit, and margin % by product category.
-- Business question: which categories drive revenue, and which are actually
-- profitable (high revenue and high margin aren't the same thing)?
-- Technique: join fact to the product dimension, aggregate, and compute a
-- margin ratio. Classic dimensional slice.
SELECT
    p.category,
    COUNT(DISTINCT f.order_id)                           AS orders,
    SUM(f.quantity)                                      AS units_sold,
    ROUND(SUM(f.net_revenue), 2)                         AS net_revenue,
    ROUND(SUM(f.gross_profit), 2)                        AS gross_profit,
    ROUND(100.0 * SUM(f.gross_profit)
                / NULLIF(SUM(f.net_revenue), 0), 1)      AS margin_pct
FROM fact_order_items f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY p.category
ORDER BY net_revenue DESC;
