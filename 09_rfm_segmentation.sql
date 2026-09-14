-- Q9: RFM-style customer scoring (Recency, Frequency, Monetary).
-- Business question: a compact, actionable segmentation - score every customer
-- on how recently they bought, how often, and how much, then combine into a
-- single grade marketing can target.
-- Technique: compute the three raw measures per customer, convert each to a
-- 1-4 score with NTILE (quartiles), and concatenate. A standard analytics
-- deliverable that turns raw transactions into a targeting scheme.
WITH rfm_base AS (
    SELECT
        customer_id,
        DATEDIFF('day', MAX(order_date),
                 (SELECT MAX(order_date) FROM fact_order_items)) AS recency_days,
        COUNT(DISTINCT order_id)      AS frequency,
        ROUND(SUM(net_revenue), 2)    AS monetary
    FROM fact_order_items
    GROUP BY customer_id
),
scored AS (
    SELECT *,
        -- recency: fewer days = better, so invert the ntile ordering
        NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(4) OVER (ORDER BY frequency ASC)     AS f_score,
        NTILE(4) OVER (ORDER BY monetary ASC)      AS m_score
    FROM rfm_base
)
SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    r_score, f_score, m_score,
    (r_score + f_score + m_score)                          AS rfm_total,
    CAST(r_score AS VARCHAR) || CAST(f_score AS VARCHAR)
        || CAST(m_score AS VARCHAR)                         AS rfm_cell,
    CASE
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
        WHEN r_score >= 3 AND f_score >= 2                  THEN 'Loyal'
        WHEN r_score >= 3                                   THEN 'Recent'
        WHEN r_score = 1 AND f_score >= 3                   THEN 'At risk'
        ELSE 'Needs attention'
    END                                                    AS rfm_segment
FROM scored
ORDER BY rfm_total DESC, monetary DESC
LIMIT 15;
