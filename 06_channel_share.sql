-- Q6: Sales channel performance, with each channel's share of monthly revenue.
-- Business question: how do Web, Mobile, and In-Store compare, and is the mix
-- shifting over time?
-- Technique: aggregate by month and channel, then a windowed ratio-to-total
-- (SUM OVER a partition) to turn absolute revenue into share-of-month. Shows
-- partitioned window aggregates for percent-of-total.
SELECT
    d.year_month,
    f.channel,
    ROUND(SUM(f.net_revenue), 2) AS channel_revenue,
    ROUND(100.0 * SUM(f.net_revenue)
                / SUM(SUM(f.net_revenue)) OVER (PARTITION BY d.year_month), 1)
        AS pct_of_month
FROM fact_order_items f
JOIN dim_date d ON f.order_date = d.date
GROUP BY d.year_month, f.channel
ORDER BY d.year_month, channel_revenue DESC
LIMIT 18;
