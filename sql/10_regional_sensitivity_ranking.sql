-- Regional demand variance — which venues need the most careful staffing?
-- Nithin Arisetty
--
-- High variance means big swings between peak and trough weeks.
-- That's operationally harder to manage than a flat demand curve —
-- you can't just maintain a steady rota, you need a flex model.
-- Scotland tends to be high variance because their summer is long (8 weeks)
-- and their off-peak is genuinely quiet.
--
-- STDDEV as a window function gives per-region annual variance in one pass.

WITH region_stats AS (
    SELECT
        region,
        iso_year,
        week_start,
        demand_index,
        AVG(demand_index) OVER (PARTITION BY region, iso_year)    AS mean_demand,
        STDDEV(demand_index) OVER (PARTITION BY region, iso_year) AS stddev_demand,
        MIN(demand_index) OVER (PARTITION BY region, iso_year)    AS min_demand,
        MAX(demand_index) OVER (PARTITION BY region, iso_year)    AS max_demand
    FROM demand_index
),

summary AS (
    SELECT DISTINCT
        region,
        iso_year,
        ROUND(mean_demand, 3)   AS mean_demand,
        ROUND(stddev_demand, 3) AS stddev_demand,
        ROUND(min_demand, 3)    AS min_demand,
        ROUND(max_demand, 3)    AS max_demand,
        ROUND(max_demand - min_demand, 3) AS demand_range,
        -- coefficient of variation: how big is the stddev relative to the mean
        -- useful for comparing regions with different absolute demand levels
        ROUND(stddev_demand / NULLIF(mean_demand, 0) * 100, 1) AS coeff_of_variation_pct
    FROM region_stats
),

ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY iso_year
            ORDER BY stddev_demand DESC
        ) AS variance_rank
    FROM summary
)

SELECT
    variance_rank,
    region,
    iso_year,
    mean_demand,
    stddev_demand,
    coeff_of_variation_pct,
    min_demand,
    max_demand,
    demand_range,
    CASE
        WHEN coeff_of_variation_pct >= 40 THEN 'Very high variance — flex staffing model essential'
        WHEN coeff_of_variation_pct >= 25 THEN 'High variance — needs dynamic rota'
        WHEN coeff_of_variation_pct >= 15 THEN 'Moderate variance — standard seasonal planning'
        ELSE 'Low variance — consistent demand profile'
    END AS staffing_model_recommendation
FROM ranked
ORDER BY iso_year, variance_rank;
